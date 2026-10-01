# ═══════════════════════════════════════════════════════════════════
# generate.py — API endpoint for synthetic data generation
# ═══════════════════════════════════════════════════════════════════
import os
import sys
from typing import Dict, List

import pandas as pd
from fastapi import APIRouter, HTTPException

from api.schemas import GenerateRequest, GenerateResponse
from hackdata.components.data_validator import DataValidator
from hackdata.components.relational_generator import RelationalGenerator
from hackdata.components.spec_builder import SpecBuilder
from hackdata.constants import api as api_const
from hackdata.constants import common
from hackdata.entity.artifact_entity import DataGenerationArtifact, DataValidationArtifact
from hackdata.entity.config_entity import DataGenerationConfig, DataValidationConfig, RunConfig, SpecBuilderConfig
from hackdata.entity.request_entity import GenerationRequest
from hackdata.exception.exception import HackDataException
from hackdata.logging.logger import logging
from hackdata.pipeline.generation_pipeline import GenerationPipeline
from hackdata.utils.main_utils.canonical_io import write_csv_canonical
from hackdata.utils.main_utils.utils import ensure_dir, write_json_file
from hackdata.constants import paths as paths_const

router = APIRouter(prefix="/api", tags=["Generation"])


def _extract_preview(table_paths: Dict[str, str], max_rows: int) -> Dict[str, List[dict]]:
    """Load top max_rows from each generated CSV table for UI preview."""
    preview: Dict[str, List[dict]] = {}
    for table_name, csv_path in table_paths.items():
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path, nrows=max_rows)
            preview[table_name] = df.to_dict(orient="records")
        else:
            preview[table_name] = []
    return preview


@router.post("/generate", response_model=GenerateResponse)
def generate_synthetic_data(req: GenerateRequest) -> GenerateResponse:
    """Generate synthetic data from natural language query or request params."""
    try:
        logging.info(f"POST /api/generate: module={req.module} mode={req.mode} query='{req.query}'")
        
        # Convert API schema to internal entity request
        gen_req = GenerationRequest(
            module=req.module,
            mode=req.mode,
            query=req.query or "synthetic dataset",
            template=req.template,
            n_rows=req.n_rows,
            seed=req.seed,
            locale=req.locale,
            currency=req.currency,
            privacy=req.privacy,
            null_rate=req.null_rate,
            outlier_rate=req.outlier_rate,
            doc_type=req.doc_type,
            doc_count=req.doc_count,
            spec_override=req.spec_override,
        )

        if req.module == common.MODULE_RELATIONAL:
            # Multi-table relational generation
            run_config = RunConfig()
            spec_config = SpecBuilderConfig(run_config)
            spec_builder = SpecBuilder(spec_config, gen_req)
            spec_artifact = spec_builder.initiate_spec_builder()
            
            from hackdata.entity.spec_entity import Spec
            from hackdata.utils.main_utils.seed_utils import new_master_seed
            from hackdata.utils.main_utils.utils import read_json_file
            spec_data = read_json_file(spec_artifact.spec_file_path)
            spec = Spec(**spec_data)

            master_seed = gen_req.seed if gen_req.seed is not None else new_master_seed()
            rel_gen = RelationalGenerator(
                spec=spec,
                master_seed=master_seed,
            )
            tables = rel_gen.generate_all_tables()

            # Apply messiness after generation (Step C)
            from hackdata.components.messiness_injector import apply_messiness
            tables = apply_messiness(tables, spec, master_seed)

            gen_config = DataGenerationConfig(run_config)
            val_config = DataValidationConfig(run_config)
            table_paths = {}
            row_counts = {}
            for table_name, df in tables.items():
                csv_path = os.path.join(gen_config.tables_dir, f"{table_name}.csv")
                write_csv_canonical(df, csv_path)
                table_paths[table_name] = csv_path
                row_counts[table_name] = len(df)

            # Build typed gen artifact so DataValidator can load tables by path.
            gen_artifact = DataGenerationArtifact(
                tables_dir=gen_config.tables_dir,
                table_file_paths=table_paths,
                master_seed=master_seed,
                row_counts=row_counts,
            )

            # AV-03 / BUG-005: run DataValidator so relational path has the same
            # structural guarantees (null, unique, FK orphan) as the tabular path.
            val_artifact = DataValidator(
                val_config, gen_artifact, spec
            ).initiate_data_validation()

            # Write run metadata in the same format as GenerationPipeline.
            meta_path = os.path.join(
                run_config.artifact_dir,
                paths_const.GENERATION_RUN_META_FILE_NAME,
            )
            write_json_file(meta_path, {
                "run_id": run_config.run_id,
                "row_counts": row_counts,
                "validity_score": val_artifact.validity_score,
                "status": val_artifact.status,
            })

            preview = _extract_preview(table_paths, api_const.API_PREVIEW_ROWS)

            return GenerateResponse(
                run_id=run_config.run_id,
                status=api_const.API_STATUS_GENERATED if val_artifact.status else api_const.API_STATUS_FAILED,
                module=req.module,
                table_names=list(tables.keys()),
                row_counts=row_counts,
                preview=preview,
                scores_status=api_const.API_SCORE_STATUS_PENDING,
                message="Relational data generated successfully" if val_artifact.status else "Validation defects detected",
            )
        else:
            # Tabular and Documents: both run through GenerationPipeline.
            # Documents module uses a document-record spec (invoice/contract rows);
            # if the LLM returns 0 tables, the pipeline produces empty CSVs which
            # surface as an empty preview — catch that case and surface a clear message.
            pipeline = GenerationPipeline(gen_req)
            res = pipeline.run()

            if not res.gen_artifact.table_file_paths:
                raise HTTPException(
                    status_code=api_const.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=(
                        "LLM returned an empty spec (no tables). "
                        "Try rephrasing your query or switching to Tabular mode."
                    ),
                )

            preview = _extract_preview(res.gen_artifact.table_file_paths, api_const.API_PREVIEW_ROWS)
            module_label = "Documents" if req.module == common.MODULE_DOCUMENTS else "Tabular"

            return GenerateResponse(
                run_id=res.run_id,
                status=api_const.API_STATUS_GENERATED if res.status else api_const.API_STATUS_FAILED,
                module=req.module,
                table_names=list(res.gen_artifact.table_file_paths.keys()),
                row_counts=res.gen_artifact.row_counts,
                preview=preview,
                scores_status=api_const.API_SCORE_STATUS_PENDING,
                message=f"{module_label} data generated successfully" if res.status else "Validation defects detected",
            )

    except HackDataException as e:
        raise HTTPException(status_code=api_const.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=api_const.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Generation error: {str(e)}")
