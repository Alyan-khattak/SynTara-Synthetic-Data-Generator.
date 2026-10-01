# ═══════════════════════════════════════════════════════════════════
# profile.py — GET /api/runs/{run_id}/profile
# ═══════════════════════════════════════════════════════════════════
# Returns per-column statistics, pairwise relationship matrix,
# and (when synthetic data exists) a comparison matrix.
# Everything computed locally — no model is called.
# ═══════════════════════════════════════════════════════════════════
import glob
import os
import sys

import pandas as pd
from fastapi import APIRouter, HTTPException

from hackdata.components.data_profiler import profile_dataframe
from hackdata.constants import api as api_const, messages as msg_const, paths as paths_const
from hackdata.exception.exception import HackDataException
from hackdata.logging.logger import logging

router = APIRouter(prefix="/api", tags=["Profile"])


def _find_source_csv(run_dir: str):
    """Find the original uploaded CSV (not synthetic_data.csv)."""
    candidates = [
        p for p in glob.glob(os.path.join(run_dir, "*.csv"))
        if os.path.basename(p) != paths_const.SYNTHETIC_DATA_FILE_NAME
    ]
    return candidates[0] if candidates else None


@router.get("/runs/{run_id}/profile")
def get_profile(run_id: str):
    """Return column profile + relationship matrix for uploaded and synthetic data.

    Steps C + D:
    - 'original': profile of the uploaded CSV
    - 'synthetic': profile of synthetic_data.csv (if generation has run)
    Both use the same profiler so matrices are comparable.
    """
    try:
        run_dir = os.path.join(paths_const.ARTIFACTS_TEMP_DIR, run_id)
        if not os.path.exists(run_dir):
            run_dir = os.path.join(paths_const.ARTIFACTS_SAVED_DIR, run_id)
        if not os.path.exists(run_dir):
            raise HTTPException(
                status_code=api_const.HTTP_404_NOT_FOUND,
                detail=msg_const.MSG_DM_UPLOAD_NOT_FOUND.format(run_id=run_id),
            )

        source_csv = _find_source_csv(run_dir)
        if not source_csv:
            raise HTTPException(
                status_code=api_const.HTTP_404_NOT_FOUND,
                detail="Uploaded CSV not found for this run.",
            )

        original_df = pd.read_csv(source_csv)
        original_profile = profile_dataframe(original_df, label="original")

        # Step D: compare with synthetic if generation has run
        synthetic_profile = None
        synth_path = os.path.join(run_dir, paths_const.SYNTHETIC_DATA_FILE_NAME)
        if os.path.exists(synth_path):
            try:
                synth_df = pd.read_csv(synth_path)
                synthetic_profile = profile_dataframe(synth_df, label="synthetic")
            except Exception as e:
                logging.info(f"profile: could not read synthetic CSV: {e}")

        # Step D summary: mean absolute difference between relationship matrices
        mad = None
        if synthetic_profile and original_profile.get("matrix") and synthetic_profile.get("matrix"):
            orig_cols = original_profile["columns"]
            synth_cols = synthetic_profile["columns"]
            shared = [c for c in orig_cols if c in synth_cols]
            if len(shared) >= 2:
                import numpy as np
                def _sub_matrix(profile, cols):
                    all_cols = profile["columns"]
                    idx = {c: i for i, c in enumerate(all_cols)}
                    m = profile["matrix"]
                    return np.array(
                        [[m[idx[r]][idx[c]] if r in idx and c in idx else None
                          for c in cols] for r in cols],
                        dtype=float,
                    )
                om = _sub_matrix(original_profile, shared)
                sm = _sub_matrix(synthetic_profile, shared)
                diff = np.abs(om - sm)
                mad = round(float(np.nanmean(diff)), 4)

        return {
            "run_id": run_id,
            "original": original_profile,
            "synthetic": synthetic_profile,
            "matrix_mad": mad,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=api_const.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Profile error: {str(e)}",
        )
