# ═══════════════════════════════════════════════════════════════════
# upload.py — API endpoint for user data uploads (data mode)
# ═══════════════════════════════════════════════════════════════════
import glob
import os
import sys
import uuid

import pandas as pd
from fastapi import APIRouter, File, HTTPException, UploadFile

from hackdata.constants import api as api_const
from hackdata.constants import paths as paths_const
from hackdata.exception.exception import HackDataException
from hackdata.logging.logger import logging
from hackdata.utils.main_utils.utils import ensure_dir

router = APIRouter(prefix="/api", tags=["Upload"])


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload dataset file for data-mode synthesis. Max size 10 MB."""
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

        # IMP: enforce the API-layer cap (10 MB) before the pipeline cap.
        # HTTP 413 is the correct status for request entity too large.
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

        logging.info(f"File uploaded successfully: {save_path} ({file_size} bytes)")

        from hackdata.pipeline.datamode_pipeline import DataModePipeline
        
        pipeline = DataModePipeline(data_path=save_path, run_id=upload_id)
        res = pipeline.run()

        # Read first API_PREVIEW_ROWS rows from the synthetic CSV for the preview panel.
        preview_rows: list = []
        try:
            synth_df = pd.read_csv(res.synthetic_csv_path, nrows=api_const.API_PREVIEW_ROWS)
            preview_rows = synth_df.to_dict(orient="records")
        except Exception:
            pass  # preview is best-effort; pipeline result already succeeded

        return {
            "upload_id": upload_id,
            "filename": filename,
            "file_path": save_path,
            "size_bytes": file_size,
            "run_id": res.run_id,
            "synthetic_csv_path": res.synthetic_csv_path,
            "train_rows": res.train_rows,
            "holdout_rows": res.holdout_rows,
            "synthetic_rows": res.synthetic_rows,
            "scorecard": res.scorecard,
            "preview": {"synthetic_data": preview_rows},
            "message": "File uploaded and data mode synthesis completed successfully",
        }

    except HTTPException:
        raise
    except HackDataException as e:
        raise HTTPException(status_code=api_const.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=api_const.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Upload error: {str(e)}")


@router.post("/runs/{run_id}/regenerate")
async def regenerate_run(run_id: str):
    """Re-run DataModePipeline on an existing uploaded file with a new random seed."""
    try:
        run_dir = os.path.join(paths_const.ARTIFACTS_TEMP_DIR, run_id)
        if not os.path.exists(run_dir):
            raise HTTPException(status_code=api_const.HTTP_404_NOT_FOUND, detail=f"Run '{run_id}' not found")

        # Find original uploaded CSV — any .csv in run_dir that isn't synthetic_data.csv
        candidates = [
            p for p in glob.glob(os.path.join(run_dir, "*.csv"))
            if os.path.basename(p) != paths_const.SYNTHETIC_DATA_FILE_NAME
        ]
        if not candidates:
            raise HTTPException(
                status_code=api_const.HTTP_404_NOT_FOUND,
                detail="Original uploaded CSV not found in run directory",
            )
        source_csv = candidates[0]

        from hackdata.pipeline.datamode_pipeline import DataModePipeline

        # Re-use same run_id so the run dir is overwritten with fresh synthetic data.
        pipeline = DataModePipeline(data_path=source_csv, run_id=run_id)
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
