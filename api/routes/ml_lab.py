# ═══════════════════════════════════════════════════════════════════
# ml_lab.py — API routes for ML Lab module
# ═══════════════════════════════════════════════════════════════════
# POST /api/ml/generate   → run MLLabPipeline, return result
# GET  /api/runs/{id}/ml-check  → return saved ML check from metadata
# GET  /api/runs/{id}/export/ml-train → download train CSV
# GET  /api/runs/{id}/export/ml-test  → download test CSV
# ═══════════════════════════════════════════════════════════════════
import os
import sys

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from api.schemas import MLLabRequest, MLLabResponse
from hackdata.constants import api as api_const, messages as msg_const
from hackdata.constants import ml_lab as ml_const, paths as paths_const
from hackdata.exception.exception import HackDataException
from hackdata.logging.logger import logging
from hackdata.utils.main_utils.utils import read_json_file

router = APIRouter(prefix="/api", tags=["ML Lab"])


def _run_dir(run_id: str) -> str:
    """Return run dir path (checks temp then saved)."""
    for base in (paths_const.ARTIFACTS_TEMP_DIR, paths_const.ARTIFACTS_SAVED_DIR):
        p = os.path.join(base, run_id)
        if os.path.exists(p):
            return p
    return ""


@router.post("/ml/generate", response_model=MLLabResponse)
def ml_generate(req: MLLabRequest) -> MLLabResponse:
    """Run ML Lab pipeline: generate data, plant target, ML check, export splits."""
    try:
        from hackdata.pipeline.ml_lab_pipeline import MLLabPipeline

        pipeline = MLLabPipeline(
            source_type=req.source_type,
            query=req.query,
            upload_run_id=req.upload_run_id,
            target_col=req.target_col,
            task_type=req.task_type,
            drivers=req.drivers,
            signal_strength=req.signal_strength,
            class_balance=req.class_balance,
            label_noise=req.label_noise,
            n_rows=req.n_rows,
            seed=req.seed,
            train_ratio=req.train_ratio,
        )
        res = pipeline.run()

        return MLLabResponse(
            run_id=res.run_id,
            source_type=res.source_type,
            task_type=res.task_type,
            target_col=res.target_col,
            train_rows=res.train_rows,
            test_rows=res.test_rows,
            seed=res.seed,
            ml_check=res.ml_check,
            preview=res.preview,
            message=res.warning,
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=api_const.HTTP_400_BAD_REQUEST, detail=str(e))
    except HackDataException as e:
        raise HTTPException(status_code=api_const.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=api_const.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ML Lab error: {e}",
        )


@router.get("/runs/{run_id}/ml-check")
def get_ml_check(run_id: str):
    """Return saved ML check results from run_metadata.json."""
    rdir = _run_dir(run_id)
    if not rdir:
        raise HTTPException(
            status_code=api_const.HTTP_404_NOT_FOUND,
            detail=f"Run '{run_id}' not found.",
        )
    meta_path = os.path.join(rdir, ml_const.ML_METADATA_FILE)
    if not os.path.exists(meta_path):
        raise HTTPException(
            status_code=api_const.HTTP_404_NOT_FOUND,
            detail="ML check metadata not found for this run.",
        )
    meta = read_json_file(meta_path)
    return {"run_id": run_id, "ml_check": meta.get("ml_check", {})}


@router.get("/runs/{run_id}/export/ml-train")
def download_ml_train(run_id: str):
    """Download the training split CSV."""
    rdir = _run_dir(run_id)
    if not rdir:
        raise HTTPException(status_code=api_const.HTTP_404_NOT_FOUND, detail=f"Run '{run_id}' not found.")
    path = os.path.join(rdir, ml_const.ML_EXPORT_DIR_NAME, ml_const.ML_TRAIN_FILE)
    if not os.path.exists(path):
        raise HTTPException(status_code=api_const.HTTP_404_NOT_FOUND, detail="Train CSV not found.")
    return FileResponse(path, media_type="text/csv", filename=f"{run_id}_train.csv")


@router.get("/runs/{run_id}/export/ml-test")
def download_ml_test(run_id: str):
    """Download the test split CSV."""
    rdir = _run_dir(run_id)
    if not rdir:
        raise HTTPException(status_code=api_const.HTTP_404_NOT_FOUND, detail=f"Run '{run_id}' not found.")
    path = os.path.join(rdir, ml_const.ML_EXPORT_DIR_NAME, ml_const.ML_TEST_FILE)
    if not os.path.exists(path):
        raise HTTPException(status_code=api_const.HTTP_404_NOT_FOUND, detail="Test CSV not found.")
    return FileResponse(path, media_type="text/csv", filename=f"{run_id}_test.csv")
