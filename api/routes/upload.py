# ═══════════════════════════════════════════════════════════════════
# upload.py — upload-only + Data-Mode generate endpoints
# ═══════════════════════════════════════════════════════════════════
# Step A split: POST /api/upload  → save file, return uploaded-data preview
#               POST /api/runs/{run_id}/generate-dm → generate synthetic data
#               POST /api/runs/{run_id}/regenerate  → re-run with new seed
# ═══════════════════════════════════════════════════════════════════
import glob
import os
import sys
import uuid

import pandas as pd
from fastapi import APIRouter, File, HTTPException, UploadFile

from api.schemas import DataModeGenerateRequest
from hackdata.constants import api as api_const
from hackdata.constants import data_mode as dm_const
from hackdata.constants import messages as msg_const
from hackdata.constants import paths as paths_const
from hackdata.components.data_profiler import _infer_col_type
from hackdata.exception.exception import HackDataException
from hackdata.logging.logger import logging
from hackdata.utils.main_utils.utils import ensure_dir

router = APIRouter(prefix="/api", tags=["Upload"])


def _uploaded_preview(df: pd.DataFrame) -> list:
    """First DM_UPLOAD_PREVIEW_ROWS rows as dicts for the uploaded-data panel."""
    return df.head(dm_const.DM_UPLOAD_PREVIEW_ROWS).to_dict(orient="records")


def _col_types(df: pd.DataFrame) -> dict:
    """Infer display type for each column."""
    return {col: _infer_col_type(df[col], col) for col in df.columns}


def _find_source_csv(run_dir: str) -> str:
    """Locate the original uploaded CSV in run_dir (not synthetic_data.csv)."""
    candidates = [
        p for p in glob.glob(os.path.join(run_dir, "*.csv"))
        if os.path.basename(p) != paths_const.SYNTHETIC_DATA_FILE_NAME
    ]
    if not candidates:
        raise HTTPException(
            status_code=api_const.HTTP_404_NOT_FOUND,
            detail="Original uploaded CSV not found in run directory",
        )
    return candidates[0]


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload dataset file for Data Mode.

    Step A: only saves the file and returns a preview of the UPLOADED data.
    Generation is triggered separately by POST /api/runs/{run_id}/generate-dm.
    """
    try:
        filename = file.filename or "uploaded_file.csv"
        ext = os.path.splitext(filename)[1].lower()

        if ext not in api_const.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=api_const.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type '{ext}'. Allowed types: {api_const.ALLOWED_EXTENSIONS}",
            )

        content = await file.read()
        file_size = len(content)

        if file_size > api_const.MAX_UPLOAD_BYTES:
            max_mb = api_const.MAX_UPLOAD_BYTES // (1024 * 1024)
            raise HTTPException(
                status_code=api_const.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds {max_mb} MB limit",
            )

        upload_id = f"upload_{uuid.uuid4().hex[:api_const.UPLOAD_ID_HEX_LENGTH]}"
        upload_dir = os.path.join(paths_const.ARTIFACTS_TEMP_DIR, upload_id)
        ensure_dir(upload_dir)

        save_path = os.path.join(upload_dir, filename)
        with open(save_path, "wb") as f:
            f.write(content)

        # Read uploaded CSV to build the preview panel
        df = pd.read_csv(save_path)
        n_rows, n_cols = df.shape

        logging.info(f"Uploaded {filename} ({file_size} bytes) → {upload_id}")

        return {
            "upload_id": upload_id,
            "run_id": upload_id,
            "filename": filename,
            "size_bytes": file_size,
            "n_rows": n_rows,
            "n_cols": n_cols,
            "col_types": _col_types(df),
            "uploaded_preview": _uploaded_preview(df),
            "message": "File uploaded. Set rows and settings, then click Generate.",
        }

    except HTTPException:
        raise
    except HackDataException as e:
        raise HTTPException(status_code=api_const.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=api_const.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Upload error: {str(e)}")


@router.post("/runs/{run_id}/generate-dm")
async def generate_dm(run_id: str, req: DataModeGenerateRequest):
    """Generate synthetic data from a previously uploaded CSV (Step A).

    Accepts row count, seed, and realism settings (Step B).
    Validates n_rows and rate caps before running the pipeline.
    """
    try:
        run_dir = os.path.join(paths_const.ARTIFACTS_TEMP_DIR, run_id)
        if not os.path.exists(run_dir):
            raise HTTPException(
                status_code=api_const.HTTP_404_NOT_FOUND,
                detail=msg_const.MSG_DM_UPLOAD_NOT_FOUND.format(run_id=run_id),
            )

        source_csv = _find_source_csv(run_dir)

        # Validate n_rows
        uploaded_df = pd.read_csv(source_csv)
        default_rows = len(uploaded_df)
        n_rows = req.n_rows if req.n_rows is not None else default_rows

        if n_rows < 1:
            raise HTTPException(
                status_code=api_const.HTTP_400_BAD_REQUEST,
                detail=msg_const.MSG_DM_ROWS_TOO_LOW,
            )
        if n_rows > dm_const.DM_MAX_SYNTH_ROWS:
            raise HTTPException(
                status_code=api_const.HTTP_400_BAD_REQUEST,
                detail=msg_const.MSG_DM_ROWS_TOO_HIGH.format(
                    n=n_rows, max_rows=dm_const.DM_MAX_SYNTH_ROWS
                ),
            )

        from hackdata.pipeline.datamode_pipeline import DataModePipeline
        from hackdata.utils.main_utils.seed_utils import new_master_seed

        master_seed = req.seed if req.seed is not None else new_master_seed()

        pipeline = DataModePipeline(
            data_path=source_csv,
            run_id=run_id,
            n_synthetic_rows=n_rows,
            master_seed=master_seed,
            missing_rate=req.missing_rate,
            outlier_rate=req.outlier_rate,
            noise_level=req.noise_level,
            correlation_adjustment=req.correlation_adjustment,
        )
        res = pipeline.run()

        preview_rows: list = []
        try:
            synth_df = pd.read_csv(res.synthetic_csv_path, nrows=api_const.API_PREVIEW_ROWS)
            preview_rows = synth_df.to_dict(orient="records")
        except Exception:
            pass

        return {
            "run_id": res.run_id,
            "seed": master_seed,
            "train_rows": res.train_rows,
            "holdout_rows": res.holdout_rows,
            "synthetic_rows": res.synthetic_rows,
            "masked_columns": res.masked_columns,
            "scorecard": res.scorecard,
            "preview": {"synthetic_data": preview_rows},
            "module": "data_mode",
        }

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=api_const.HTTP_400_BAD_REQUEST, detail=str(e))
    except HackDataException as e:
        raise HTTPException(status_code=api_const.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=api_const.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Generate error: {str(e)}")


@router.post("/runs/{run_id}/regenerate")
async def regenerate_run(run_id: str):
    """Re-run DataModePipeline on an existing uploaded file with a new random seed."""
    try:
        run_dir = os.path.join(paths_const.ARTIFACTS_TEMP_DIR, run_id)
        if not os.path.exists(run_dir):
            raise HTTPException(status_code=api_const.HTTP_404_NOT_FOUND, detail=f"Run '{run_id}' not found")

        source_csv = _find_source_csv(run_dir)

        # Read existing metadata to reuse settings (seed will be re-randomised)
        import json
        meta_path = os.path.join(run_dir, paths_const.GENERATION_RUN_META_FILE_NAME)
        meta: dict = {}
        if os.path.exists(meta_path):
            with open(meta_path) as mf:
                meta = json.load(mf)

        realism = meta.get("realism", {})

        from hackdata.pipeline.datamode_pipeline import DataModePipeline
        from hackdata.utils.main_utils.seed_utils import new_master_seed

        pipeline = DataModePipeline(
            data_path=source_csv,
            run_id=run_id,
            n_synthetic_rows=meta.get("synthetic_rows"),
            master_seed=new_master_seed(),   # new seed on every regenerate
            missing_rate=realism.get("missing_rate", 0.0),
            outlier_rate=realism.get("outlier_rate", 0.0),
            noise_level=realism.get("noise_level", 0.0),
            correlation_adjustment=realism.get("correlation_adjustment", 0.0),
        )
        res = pipeline.run()

        preview_rows: list = []
        try:
            synth_df = pd.read_csv(res.synthetic_csv_path, nrows=api_const.API_PREVIEW_ROWS)
            preview_rows = synth_df.to_dict(orient="records")
        except Exception:
            pass

        return {
            "run_id": res.run_id,
            "train_rows": res.train_rows,
            "holdout_rows": res.holdout_rows,
            "synthetic_rows": res.synthetic_rows,
            "scorecard": res.scorecard,
            "preview": {"synthetic_data": preview_rows},
        }

    except HTTPException:
        raise
    except HackDataException as e:
        raise HTTPException(status_code=api_const.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=api_const.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Regenerate error: {str(e)}")
