# ═══════════════════════════════════════════════════════════════════
# runs.py — API routes for run status, listing, downloading, and saving
# ═══════════════════════════════════════════════════════════════════
import os
import shutil
import sys
import zipfile
from typing import List

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from api.dependencies import validate_run_id
from api.schemas import RunListResponse, RunSummary, SaveRunRequest
from hackdata.constants import api as api_const
from hackdata.constants import paths as paths_const
from hackdata.exception.exception import HackDataException
from hackdata.logging.logger import logging
from hackdata.utils.main_utils.utils import read_json_file

router = APIRouter(prefix="/api", tags=["Runs"])


def _scan_runs_in_dir(base_dir: str, saved_flag: bool) -> List[RunSummary]:
    """Scan directory for timestamped run folders containing run_metadata.json."""
    summaries: List[RunSummary] = []
    if not os.path.exists(base_dir):
        return summaries

    for run_id in os.listdir(base_dir):
        run_path = os.path.join(base_dir, run_id)
        if not os.path.isdir(run_path):
            continue

        meta_path = os.path.join(run_path, paths_const.GENERATION_RUN_META_FILE_NAME)
        if os.path.exists(meta_path):
            try:
                meta = read_json_file(meta_path)
                summaries.append(
                    RunSummary(
                        run_id=run_id,
                        module=meta.get("module", "tabular"),
                        mode=meta.get("mode", "query"),
                        status=api_const.API_STATUS_GENERATED if meta.get("status") else api_const.API_STATUS_FAILED,
                        created_at=run_id,
                        row_counts=meta.get("row_counts", {}),
                        saved=saved_flag,
                    )
                )
            except Exception as err:
                logging.info(f"Could not parse run metadata at {meta_path}: {err}")

    return summaries


@router.get("/runs", response_model=RunListResponse)
def list_runs() -> RunListResponse:
    """Return list of all temp and saved runs."""
    try:
        temp_runs = _scan_runs_in_dir(paths_const.ARTIFACTS_TEMP_DIR, saved_flag=False)
        saved_runs = _scan_runs_in_dir(paths_const.ARTIFACTS_SAVED_DIR, saved_flag=True)
        return RunListResponse(runs=temp_runs + saved_runs)
    except Exception as e:
        raise HTTPException(status_code=api_const.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/status/{run_id}")
def get_run_status(run_id: str):
    """Return run status and metadata for a specific run_id."""
    try:
        validate_run_id(run_id)
        # Check temp then saved
        run_dir = os.path.join(paths_const.ARTIFACTS_TEMP_DIR, run_id)
        if not os.path.exists(run_dir):
            run_dir = os.path.join(paths_const.ARTIFACTS_SAVED_DIR, run_id)

        if not os.path.exists(run_dir):
            raise HTTPException(status_code=api_const.HTTP_404_NOT_FOUND, detail=f"Run '{run_id}' not found")

        meta_path = os.path.join(run_dir, paths_const.GENERATION_RUN_META_FILE_NAME)
        if os.path.exists(meta_path):
            meta = read_json_file(meta_path)
            return {"run_id": run_id, "metadata": meta}

        return {"run_id": run_id, "status": "running"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=api_const.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/runs/{run_id}/scores")
def get_run_scores(run_id: str):
    """Return scores for a run. Query mode scoring is parked per TRD 14.7."""
    try:
        validate_run_id(run_id)
        run_dir = os.path.join(paths_const.ARTIFACTS_TEMP_DIR, run_id)
        if not os.path.exists(run_dir):
            run_dir = os.path.join(paths_const.ARTIFACTS_SAVED_DIR, run_id)
            
        if not os.path.exists(run_dir):
            raise HTTPException(status_code=api_const.HTTP_404_NOT_FOUND, detail=f"Run '{run_id}' not found")
            
        # Try to read scores.json if it exists (Data Mode)
        scores_path = os.path.join(run_dir, paths_const.EVALUATION_DIR_NAME, paths_const.SCORES_FILE_NAME)
        if os.path.exists(scores_path):
            scores = read_json_file(scores_path)
            return {"run_id": run_id, "scores_status": "done", "scores": scores}
            
        # Query Mode scoring is parked
        return {"run_id": run_id, "scores_status": "parked", "scores": None, "message": "Query mode scoring is parked"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=api_const.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/runs/{run_id}/save")
def save_run(run_id: str):
    """Move run folder from Artifacts/temp to Artifacts/saved."""
    try:
        validate_run_id(run_id)
        src = os.path.join(paths_const.ARTIFACTS_TEMP_DIR, run_id)
        if not os.path.exists(src):
            raise HTTPException(status_code=api_const.HTTP_404_NOT_FOUND, detail=f"Temp run '{run_id}' not found")

        dst = os.path.join(paths_const.ARTIFACTS_SAVED_DIR, run_id)
        if os.path.exists(dst):
            shutil.rmtree(dst)

        os.makedirs(paths_const.ARTIFACTS_SAVED_DIR, exist_ok=True)
        shutil.move(src, dst)
        return {"run_id": run_id, "saved": True, "message": "Run saved successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=api_const.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/runs/{run_id}/export")
def download_run_artifacts(run_id: str, format: str = "csv"):
    """Package run tables into a ZIP (csv/json) or PDF for documents runs."""
    from hackdata.components.exporter import Exporter
    try:
        validate_run_id(run_id)
        exporter = Exporter(run_id)

        if format == "pdf":
            pdf_path = exporter.export_pdf()
            return FileResponse(
                path=pdf_path,
                filename=f"hackdata_{run_id}_documents.pdf",
                media_type="application/pdf",
            )

        zip_filename = exporter.export(format)
        return FileResponse(
            path=zip_filename,
            filename=f"hackdata_{run_id}_export.{format}.zip",
            media_type="application/zip",
        )

    except HackDataException as hde:
        raise HTTPException(status_code=api_const.HTTP_404_NOT_FOUND, detail=str(hde.original_exception))
    except Exception as e:
        raise HTTPException(status_code=api_const.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/runs/{run_id}/export/table/{table_name}")
def download_table_csv(run_id: str, table_name: str):
    """Return a single table as a raw CSV file (no ZIP wrapper).

    Step B: per-table CSV download button in the frontend.
    Filename is <table_name>.csv — safe characters only (validated via run_id check).
    """
    try:
        validate_run_id(run_id)

        run_dir = os.path.join(paths_const.ARTIFACTS_TEMP_DIR, run_id)
        if not os.path.exists(run_dir):
            run_dir = os.path.join(paths_const.ARTIFACTS_SAVED_DIR, run_id)
        if not os.path.exists(run_dir):
            raise HTTPException(status_code=api_const.HTTP_404_NOT_FOUND, detail=f"Run '{run_id}' not found")

        # IMP: sanitise table_name — only alphanumeric/underscore/hyphen to prevent path traversal
        safe_name = "".join(c for c in table_name if c.isalnum() or c in ("_", "-"))
        if not safe_name:
            raise HTTPException(status_code=400, detail="Invalid table name")

        csv_path = os.path.join(
            run_dir,
            paths_const.DATA_GENERATION_DIR_NAME,
            paths_const.TABLES_DIR_NAME,
            f"{safe_name}.csv",
        )

        # fallback: data-mode synthetic_data.csv
        if not os.path.exists(csv_path):
            dm_path = os.path.join(run_dir, paths_const.SYNTHETIC_DATA_FILE_NAME)
            if os.path.exists(dm_path):
                csv_path = dm_path
                safe_name = "synthetic_data"

        if not os.path.exists(csv_path):
            raise HTTPException(status_code=api_const.HTTP_404_NOT_FOUND, detail=f"Table '{table_name}' not found in run")

        return FileResponse(
            path=csv_path,
            filename=f"{safe_name}.csv",
            media_type="text/csv",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=api_const.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
