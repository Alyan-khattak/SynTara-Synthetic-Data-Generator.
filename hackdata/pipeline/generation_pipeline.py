# ═══════════════════════════════════════════════════════════════════
# generation_pipeline.py — query-mode end-to-end pipeline
# ═══════════════════════════════════════════════════════════════════
# Orchestrates: SpecBuilder → table generation → CSV write →
#               DataValidator → metadata write → GenerationPipelineResult.
#
# Position in the layer order (TRD section 3):
#   components → pipeline → api / app / main
#
# IMP: this file owns orchestration only; no business logic lives here.
#      Each step delegates to its component; all paths come from configs.
###==============================================================
"""
GenerationPipeline

    GenerationRequest
        │
        ▼  SpecBuilder.initiate_spec_builder()
        │   → SpecBuilderArtifact (spec.json, pools.json on disk)
        ▼  _generate_tables(spec, pools, master_seed)
        │   → {table_name: pd.DataFrame}
        ▼  _write_tables(tables)
        │   → {table_name: csv_path}   (DataGenerationArtifact built here)
        ▼  DataValidator.initiate_data_validation()
        │   → DataValidationArtifact
        ▼  _write_metadata(...)
        └─▶ GenerationPipelineResult

# DRY RUN: query="50 sales records"
#   1. SpecBuilder → spec.json with tables=[{name:"sales",n_rows:50,columns:[...]}]
#   2. _generate_tables → {"sales": DataFrame(50 rows)}
#   3. _write_tables → {"sales": "Artifacts/temp/<run_id>/data_generation/tables/sales.csv"}
#   4. DataValidator → DataValidationArtifact(status=True, validity_score=100.0, ...)
#   5. run_metadata.json written to Artifacts/temp/<run_id>/run_metadata.json
#   6. GenerationPipelineResult returned
"""

import os
import sys
from dataclasses import dataclass

import pandas as pd

from hackdata.components.data_validator import DataValidator
from hackdata.components.generators.column_generators import generate_column
from hackdata.components.spec_builder import SpecBuilder
from hackdata.constants import paths as paths_const
from hackdata.entity.artifact_entity import (
    DataGenerationArtifact,
    DataValidationArtifact,
    SpecBuilderArtifact,
)
from hackdata.entity.config_entity import (
    DataGenerationConfig,
    DataValidationConfig,
    RunConfig,
    SpecBuilderConfig,
)
from hackdata.entity.request_entity import GenerationRequest
from hackdata.entity.spec_entity import Spec
from hackdata.exception.exception import HackDataException
from hackdata.logging.logger import logging
from hackdata.utils.main_utils.canonical_io import write_csv_canonical
from hackdata.utils.main_utils.seed_utils import new_master_seed
from hackdata.utils.main_utils.utils import ensure_dir, read_json_file, write_json_file


# ─────────────────────────────────────────────────────────────────────
# RESULT DATACLASS
# ─────────────────────────────────────────────────────────────────────

@dataclass
class GenerationPipelineResult:
    """Typed output of the entire generation pipeline.

    Holds references to every artifact produced during the run so the
    API layer and run_manager can surface them without knowing about
    the internal step order.

    Fields
    ------
    run_id         : timestamp-based run identifier (from RunConfig)
    artifact_dir   : root directory for this run (Artifacts/temp/<run_id>)
    spec_artifact  : SpecBuilder output — spec.json and pools.json paths
    gen_artifact   : DataGenerator output — CSV paths and row counts
    val_artifact   : DataValidator output — report path and validity score
    validity_score : shortcut to val_artifact.validity_score
    status         : shortcut to val_artifact.status (False = tier-1 failure)
    """

    run_id: str
    artifact_dir: str
    spec_artifact: SpecBuilderArtifact
    gen_artifact: DataGenerationArtifact
    val_artifact: DataValidationArtifact
    validity_score: float
    status: bool


# ─────────────────────────────────────────────────────────────────────
# PIPELINE CLASS
# ─────────────────────────────────────────────────────────────────────

class GenerationPipeline:
    """Query-mode generation pipeline.

    Takes a GenerationRequest, runs SpecBuilder + column generation +
    DataValidator, writes all artifacts to Artifacts/temp/<run_id>/,
    and returns a GenerationPipelineResult.

    Parameters
    ----------
    request : GenerationRequest
        Caller's intent: query, module, seed, n_rows, etc.
    """

    def __init__(self, request: GenerationRequest):
        try:
            self.request = request
            # IMP: RunConfig creates the timestamped run_id once; all
            #      component configs share it so everything goes into one folder.
            self.run_config = RunConfig()
            self.spec_config = SpecBuilderConfig(self.run_config)
            self.gen_config = DataGenerationConfig(self.run_config)
            self.val_config = DataValidationConfig(self.run_config)
        except Exception as e:
            raise HackDataException(e, sys)

    # ──────────────────────────────────────────────────────────────
    # STEP 2 — GENERATE TABLES
    # ──────────────────────────────────────────────────────────────

    def _generate_tables(
        self, spec: Spec, pools: dict, master_seed: int, locale: str = "en"
    ) -> dict:
        """Generate all tables defined in spec using column_generators.

        For each TableSpec, columns are generated left-to-right so that
        ref-based generators (date_offset, conditional, expr) can read
        already-generated columns from existing_cols.

        Parameters
        ----------
        spec        : validated Spec Pydantic model
        pools       : {table_name: {col_name: [values]}} from pools.json
        master_seed : run-level seed; each column derives its own rng

        Returns
        -------
        dict
            {table_name: pd.DataFrame}

        # DRY RUN: spec has table "orders" with 3 columns: id(sequence), name(faker), total(money)
        #   existing_cols = {}
        #   col "id"    → generate_column → Series([1,2,...,n])
        #   existing_cols = {"id": Series}
        #   col "name"  → generate_column → Series(["Alice","Bob",...])
        #   existing_cols = {"id": ..., "name": ...}
        #   col "total" → generate_column → Series([5000, 12000, ...])
        #   df = DataFrame({"id":..., "name":..., "total":...}, n rows)
        """
        try:
            logging.info("GenerationPipeline._generate_tables: started")  # noqa: hardcode
            tables = {}

            for table_spec in spec.tables:
                existing_cols: dict = {}
                # Pool values for this table (may be empty dict if no pool columns)
                table_pools = pools.get(table_spec.name, {})

                for col in table_spec.columns:
                    # IMP: model_dump() converts Pydantic ColumnSpec → plain dict,
                    #      which is what generate_column expects.
                    col_dict = col.model_dump()

                    # IMP: inject pool values from pools.json for "pool" columns.
                    #      The Spec stores None for 'values' on pool columns;
                    #      the real value list lives in pools.json written by SpecBuilder.
                    if col.gen == "pool" and col.name in table_pools:
                        col_dict["values"] = table_pools[col.name]

                    series = generate_column(
                        col_dict,
                        table_spec.n_rows,
                        master_seed,
                        table_spec.name,
                        existing_cols,
                        locale=locale,
                    )
                    existing_cols[col.name] = series

                tables[table_spec.name] = pd.DataFrame(existing_cols)

            logging.info(
                f"GenerationPipeline._generate_tables: done — "
                f"{len(tables)} table(s): {list(tables.keys())}"
            )
            return tables
        except HackDataException:
            raise
        except Exception as e:
            raise HackDataException(e, sys)

    # ──────────────────────────────────────────────────────────────
    # STEP 3 — WRITE TABLES TO CSV
    # ──────────────────────────────────────────────────────────────

    def _write_tables(self, tables: dict) -> dict:
        """Write each DataFrame to a canonical CSV file.

        Parameters
        ----------
        tables : dict
            {table_name: pd.DataFrame}

        Returns
        -------
        dict
            {table_name: absolute_csv_path}
        """
        try:
            logging.info("GenerationPipeline._write_tables: started")  # noqa: hardcode
            ensure_dir(self.gen_config.tables_dir)
            paths_map: dict = {}

            for table_name, df in tables.items():
                path = os.path.join(
                    self.gen_config.tables_dir, f"{table_name}.csv"
                )
                write_csv_canonical(df, path)
                paths_map[table_name] = path

            logging.info(
                f"GenerationPipeline._write_tables: done — "
                f"{len(paths_map)} file(s) written"
            )
            return paths_map
        except HackDataException:
            raise
        except Exception as e:
            raise HackDataException(e, sys)

    # ──────────────────────────────────────────────────────────────
    # STEP 5 — WRITE METADATA
    # ──────────────────────────────────────────────────────────────

    def _write_metadata(
        self,
        spec_artifact: SpecBuilderArtifact,
        gen_artifact: DataGenerationArtifact,
        val_artifact: DataValidationArtifact,
    ) -> None:
        """Write run_metadata.json to the run's root artifact directory.

        Parameters
        ----------
        spec_artifact : SpecBuilderArtifact
        gen_artifact  : DataGenerationArtifact
        val_artifact  : DataValidationArtifact
        """
        try:
            meta_path = os.path.join(
                self.run_config.artifact_dir,
                paths_const.GENERATION_RUN_META_FILE_NAME,
            )
            meta = {
                "run_id": self.run_config.run_id,
                "row_counts": gen_artifact.row_counts,
                "validity_score": val_artifact.validity_score,
                "status": val_artifact.status,
            }
            write_json_file(meta_path, meta)
            logging.info(f"GenerationPipeline._write_metadata: written to {meta_path}")
        except HackDataException:
            raise
        except Exception as e:
            raise HackDataException(e, sys)

    # ──────────────────────────────────────────────────────────────
    # MAIN ENTRY POINT
    # ──────────────────────────────────────────────────────────────

    def run(self) -> GenerationPipelineResult:
        """Run the full generation pipeline.

        Returns
        -------
        GenerationPipelineResult
            Typed result holding all artifact references.

        Raises
        ------
        HackDataException
            On any unrecoverable failure in any pipeline step.
        """
        try:
            logging.info(
                f"GenerationPipeline.run: started — "
                f"run_id={self.run_config.run_id} "
                f"query='{self.request.query}'"
            )

            # ── STEP 1: build spec ──────────────────────────────
            spec_artifact = SpecBuilder(
                self.spec_config, self.request
            ).initiate_spec_builder()

            # ── load spec and pools from disk into typed objects ─
            # IMP: read from the written JSON so the pipeline uses exactly
            #      what was persisted, not an in-memory copy.
            spec_dict = read_json_file(spec_artifact.spec_file_path)
            spec: Spec = Spec(**spec_dict)
            pools: dict = read_json_file(spec_artifact.pools_file_path)

            # ── resolve master seed ─────────────────────────────
            # IMP: use caller-supplied seed for reproducibility; fall back
            #      to a fresh CSPRNG seed for one-shot runs.
            master_seed: int = (
                self.request.seed if self.request.seed is not None
                else new_master_seed()
            )
            logging.info(f"GenerationPipeline.run: master_seed={master_seed}")

            # ── STEP 2: generate table DataFrames ───────────────
            tables = self._generate_tables(spec, pools, master_seed, locale=self.request.locale)

            # ── STEP 2b: apply messiness (null/outlier/imbalance) ─
            # IMP: applied after generation so PK/FK integrity is intact.
            from hackdata.components.messiness_injector import apply_messiness
            tables = apply_messiness(tables, spec, master_seed)

            # ── STEP 3: write CSVs and build gen artifact ───────
            table_paths = self._write_tables(tables)
            row_counts = {name: len(df) for name, df in tables.items()}

            gen_artifact = DataGenerationArtifact(
                tables_dir=self.gen_config.tables_dir,
                table_file_paths=table_paths,
                master_seed=master_seed,
                row_counts=row_counts,
            )

            # ── STEP 4: validate ────────────────────────────────
            val_artifact = DataValidator(
                self.val_config, gen_artifact, spec
            ).initiate_data_validation()

            # ── STEP 5: write run metadata ──────────────────────
            self._write_metadata(spec_artifact, gen_artifact, val_artifact)

            result = GenerationPipelineResult(
                run_id=self.run_config.run_id,
                artifact_dir=self.run_config.artifact_dir,
                spec_artifact=spec_artifact,
                gen_artifact=gen_artifact,
                val_artifact=val_artifact,
                validity_score=val_artifact.validity_score,
                status=val_artifact.status,
            )

            logging.info(
                f"GenerationPipeline.run: done — "
                f"tables={list(row_counts.keys())} "
                f"validity_score={val_artifact.validity_score:.1f} "
                f"status={val_artifact.status}"
            )
            return result

        except HackDataException:
            raise
        except Exception as e:
            raise HackDataException(e, sys)
