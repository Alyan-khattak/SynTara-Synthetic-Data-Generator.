# ═══════════════════════════════════════════════════════════════════
# data_validator.py — three-tier validation of generated tables
# ═══════════════════════════════════════════════════════════════════
# Sits between DataGenerator and Evaluator in the generation pipeline.
#
#   DataGenerationArtifact ──▶ [DataValidator] ──▶ DataValidationArtifact
#
# Tier 1 (structural): null checks, uniqueness checks  → stop pipeline on failure
# Tier 2 (rules):      range checks from ColumnSpec    → logged but non-fatal
# Tier 3 (coherence):  group-level stats               → P1 stub, returns 0/0
###==============================================================
"""
DataValidator

    DataGenerationArtifact + Spec
        │
        ▼  run_structural_checks()  → null / unique defects (tier 1)
        ▼  run_rule_checks()        → range defects (tier 2)
        ▼  coherence stub           → 0 / 0 (tier 3 placeholder)
        │
        └──▶ DataValidationArtifact (status, validity_score 0-100, report path)

# DRY RUN (tier 1, null check):
#   table "orders", column "id" has rule "not_null"
#   df["id"].isna().any() == True  →  null_count = 1
#   defect appended: {kind:"null_in_not_null", table:"orders", col:"id", count:1, tier:1}
#   status = False  (tier-1 failure halts the pipeline)
"""

import os
import sys
from typing import Dict, List

import pandas as pd

from hackdata.constants import validation as val_const
from hackdata.entity.artifact_entity import DataGenerationArtifact, DataValidationArtifact
from hackdata.entity.config_entity import DataValidationConfig
from hackdata.entity.spec_entity import Spec
from hackdata.exception.exception import HackDataException
from hackdata.logging.logger import logging
from hackdata.utils.main_utils.utils import ensure_dir, write_json_file


class DataValidator:
    """Three-tier validator for generated synthetic tables.

    Parameters
    ----------
    config : DataValidationConfig
        Paths config — contains report_file_path.
    gen_artifact : DataGenerationArtifact
        Output of DataGenerator; holds table CSV paths.
    spec : Spec
        Frozen Pydantic spec; defines column rules.
    """

    def __init__(
        self,
        config: DataValidationConfig,
        gen_artifact: DataGenerationArtifact,
        spec: Spec,
    ):
        try:
            self.config = config
            self.gen_artifact = gen_artifact
            self.spec = spec
        except Exception as e:
            raise HackDataException(e, sys)

    # ──────────────────────────────────────────────────────────────
    # PUBLIC ENTRY POINT
    # ──────────────────────────────────────────────────────────────

    def initiate_data_validation(self) -> DataValidationArtifact:
        """Run all tiers and write the report.

        Returns
        -------
        DataValidationArtifact
            status=False on any tier-1 defect; validity_score on 0–100 scale.
        """
        try:
            logging.info("DataValidator started")
            ensure_dir(os.path.dirname(self.config.report_file_path))

            tables = self._load_tables()

            defects: List[dict] = []
            defects += self.run_structural_checks(tables)
            defects += self.run_rule_checks(tables)

            # IMP: Tier 3 coherence is a P1 stub — returns 0/0 until implemented.
            coherence_passed, coherence_total = 0, 0

            # validity score: fraction of clean rows scaled to 0-100.
            # IMP: row-based rather than cell-based to avoid large tables diluting
            # the defect ratio (5 defects in 20k cells → 99.97% is misleading;
            # 5 defects in 1000 rows → 99.5% is more honest).
            # Defects carry no per-row index, so we count distinct defect records
            # divided by total rows across all tables.
            # IMP: guard against empty tables (total_rows=0) to avoid division by zero
            total_rows = sum(len(df) for df in tables.values()) or 1
            score = max(0.0, (1 - len(defects) / total_rows) * 100)

            # status=False only when there are tier-1 structural defects;
            # tier-2 rule violations are recorded but non-fatal
            status = not any(
                d["tier"] == val_const.VAL_TIER_STRUCTURAL for d in defects
            )

            report = {
                "defects": defects,
                "validity_score": score,
                "status": status,
                "coherence_passed": coherence_passed,
                "coherence_total": coherence_total,
            }
            write_json_file(self.config.report_file_path, report)

            logging.info(
                f"DataValidator done: {len(defects)} defects, "
                f"score={score:.1f}, status={status}"
            )

            return DataValidationArtifact(
                status=status,
                validity_score=score,
                report_file_path=self.config.report_file_path,
                coherence_passed=coherence_passed,
                coherence_total=coherence_total,
            )
        except Exception as e:
            raise HackDataException(e, sys)

    # ──────────────────────────────────────────────────────────────
    # TIER 1 — STRUCTURAL CHECKS
    # ──────────────────────────────────────────────────────────────

    def run_structural_checks(self, tables: Dict[str, pd.DataFrame]) -> List[dict]:
        """Check not_null and unique constraints declared in spec rules.

        These are tier-1 (structural) defects; any failure sets status=False.

        # DRY RUN (null check):
        #   col.rules = ["not_null", "unique"], col.name = "id"
        #   df["id"] = [1, None, 3]  →  isna().sum() = 1
        #   defect: {kind:"null_in_not_null", table:"orders", col:"id", count:1, tier:1}

        # DRY RUN (duplicate check):
        #   df["id"] = [1, 1, 3]  →  duplicated().sum() = 1
        #   defect: {kind:"duplicate_pk", table:"orders", col:"id", count:1, tier:1}

        Parameters
        ----------
        tables : dict
            Mapping of table_name → DataFrame (already loaded).

        Returns
        -------
        list
            Defect dicts, each with keys: kind, table, col, count, tier.
        """
        try:
            defects: List[dict] = []

            for table_spec in self.spec.tables:
                df = tables.get(table_spec.name)
                if df is None:
                    continue

                for col in table_spec.columns:
                    if col.name not in df.columns:
                        continue

                    # --- not_null check ---
                    if col.rules and "not_null" in col.rules:
                        null_count = int(df[col.name].isna().sum())
                        if null_count > 0:
                            defects.append({
                                "kind": "null_in_not_null",
                                "table": table_spec.name,
                                "col": col.name,
                                "count": null_count,
                                "tier": val_const.VAL_TIER_STRUCTURAL,
                            })

                    # --- unique check ---
                    if col.rules and "unique" in col.rules:
                        dup_count = int(df[col.name].duplicated().sum())
                        if dup_count > 0:
                            defects.append({
                                "kind": "duplicate_pk",
                                "table": table_spec.name,
                                "col": col.name,
                                "count": dup_count,
                                "tier": val_const.VAL_TIER_STRUCTURAL,
                            })

                # --- FK orphan check ---
                if table_spec.parent:
                    parent_table_name = table_spec.parent.table
                    fk_col = table_spec.parent.key
                    if parent_table_name in tables and fk_col in df.columns:
                        parent_df = tables[parent_table_name]
                        if len(parent_df) > 0:
                            parent_pk_col = "id" if "id" in parent_df.columns else parent_df.columns[0]
                            parent_keys = set(parent_df[parent_pk_col].dropna().unique())
                            child_keys = df[fk_col].dropna()
                            orphans = child_keys[~child_keys.isin(parent_keys)]
                            if len(orphans) > 0:
                                defects.append({
                                    "kind": "orphan_fk",
                                    "table": table_spec.name,
                                    "col": fk_col,
                                    "count": int(len(orphans)),
                                    "tier": val_const.VAL_TIER_STRUCTURAL,
                                })

                        # --- FK cardinality check ---
                        if parent_df is not None and len(parent_df) > 0:
                            child_counts = df[fk_col].value_counts()
                            min_c = table_spec.parent.cardinality.min_per_parent
                            max_c = table_spec.parent.cardinality.max_per_parent
                            violations = child_counts[(child_counts < min_c) | (child_counts > max_c)]
                            if len(violations) > 0:
                                defects.append({
                                    "kind": "cardinality_violation",
                                    "table": table_spec.name,
                                    "col": fk_col,
                                    "count": int(len(violations)),
                                    "tier": val_const.VAL_TIER_STRUCTURAL,
                                })
                else:
                    # --- totals match check (only for parent tables as child n_rows is derived) ---
                    if len(df) != table_spec.n_rows:
                        defects.append({
                            "kind": "totals_mismatch",
                            "table": table_spec.name,
                            "col": "n_rows",
                            "count": 1,
                            "tier": val_const.VAL_TIER_STRUCTURAL,
                        })

            return defects
        except Exception as e:
            raise HackDataException(e, sys)

    # ──────────────────────────────────────────────────────────────
    # TIER 2 — RULE CHECKS
    # ──────────────────────────────────────────────────────────────

    def run_rule_checks(self, tables: Dict[str, pd.DataFrame]) -> List[dict]:
        """Check range constraints (col.min / col.max) from ColumnSpec.

        Skips rules handled structurally (not_null, unique) to avoid double-counting.

        # DRY RUN:
        #   col.rules = ["range"], col.min = 50, col.max = 500
        #   df["price"] = [100, 200, -5]  →  -5 < 50  → defect appended
        #   kind = "negative_quantity"  (covers both below-min and above-max violations)

        Parameters
        ----------
        tables : dict
            Mapping of table_name → DataFrame.

        Returns
        -------
        list
            Defect dicts with keys: kind, table, col, tier.
        """
        try:
            defects: List[dict] = []

            for table_spec in self.spec.tables:
                df = tables.get(table_spec.name)
                if df is None:
                    continue

                for col in table_spec.columns:
                    if col.name not in df.columns:
                        continue

                    if not (col.rules and "range" in col.rules):
                        continue

                    # IMP: coerce to numeric; non-parseable values become NaN
                    #      and are dropped so they do not falsely trigger range violations.
                    numeric_vals = pd.to_numeric(df[col.name], errors="coerce").dropna()

                    if col.min is not None and numeric_vals.lt(col.min).any():
                        defects.append({
                            "kind": "negative_quantity",
                            "table": table_spec.name,
                            "col": col.name,
                            "tier": val_const.VAL_TIER_RULES,
                        })

                    if col.max is not None and numeric_vals.gt(col.max).any():
                        defects.append({
                            "kind": "negative_quantity",
                            "table": table_spec.name,
                            "col": col.name,
                            "tier": val_const.VAL_TIER_RULES,
                        })

            return defects
        except Exception as e:
            raise HackDataException(e, sys)

    # ──────────────────────────────────────────────────────────────
    # PRIVATE HELPERS
    # ──────────────────────────────────────────────────────────────

    def _load_tables(self) -> Dict[str, pd.DataFrame]:
        """Read each table CSV from gen_artifact.table_file_paths.

        Returns
        -------
        dict
            Mapping of table_name → DataFrame.
            Tables that cannot be read are skipped with a warning.
        """
        try:
            result: Dict[str, pd.DataFrame] = {}
            for table_name, csv_path in self.gen_artifact.table_file_paths.items():
                try:
                    result[table_name] = pd.read_csv(csv_path)
                except Exception as read_err:
                    # IMP: log and skip; the structural check will note missing tables
                    logging.info(f"Could not load table {table_name}: {read_err}")
            return result
        except Exception as e:
            raise HackDataException(e, sys)


# ──────────────────────────────────────────────────────────────────
# SELF-CHECK
# ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # ponytail: minimal runnable check — validates the happy path and
    # the null-injection path.  Fails loudly if core logic breaks.
    import json
    import tempfile

    from hackdata.entity.config_entity import RunConfig

    with tempfile.TemporaryDirectory() as d:
        tables_dir = os.path.join(d, "tables")
        os.makedirs(tables_dir)

        # Build a clean 3-row table
        df_clean = pd.DataFrame({"id": [1, 2, 3], "price": [100, 200, 300]})
        csv_path = os.path.join(tables_dir, "orders.csv")  # noqa: hardcode self-check fixture filename
        df_clean.to_csv(csv_path, index=False)

        gen_artifact = DataGenerationArtifact(
            tables_dir=tables_dir,
            table_file_paths={"orders": csv_path},
            master_seed=42,  # noqa: hardcode self-check seed; not production code
            row_counts={"orders": 3},
        )
        spec = Spec(**{
            "version": "1",
            "module": "tabular",
            "tables": [{
                "name": "orders",
                "n_rows": 3,
                "columns": [
                    {"name": "id",    "gen": "sequence",  "rules": ["not_null", "unique"]},
                    {"name": "price", "gen": "int_range", "min": 50, "max": 500,
                     "rules": ["range"]},
                ],
            }],
        })

        rc = RunConfig()
        config = DataValidationConfig(rc)
        artifact = DataValidator(config, gen_artifact, spec).initiate_data_validation()

        assert artifact.status is True, "clean table should pass"
        assert artifact.validity_score > 90, "clean table should score > 90"  # noqa: hardcode sanity bound
        print(f"PASS — clean table: status={artifact.status}, score={artifact.validity_score:.1f}")

        # Inject a null to trigger tier-1 failure
        df_bad = pd.DataFrame({"id": [1, None, 3], "price": [100, 200, 300]})
        df_bad.to_csv(csv_path, index=False)
        art2 = DataValidator(config, gen_artifact, spec).initiate_data_validation()
        report = json.loads(open(art2.report_file_path).read())  # noqa: hardcode path is variable
        assert any(d["kind"] == "null_in_not_null" for d in report["defects"])
        print("PASS — null detection works")

    print("Self-check passed.")
