# ═══════════════════════════════════════════════════════════════════
# config.py — API configuration endpoint
# ═══════════════════════════════════════════════════════════════════
import sys
from fastapi import APIRouter

from api.schemas import ConfigResponse
from hackdata.constants import api as api_const
from hackdata.constants import common
from hackdata.constants import data_mode
from hackdata.constants import evaluation as eval_const
from hackdata.constants import generation as gen_const
from hackdata.constants import spec as spec_const
from hackdata.exception.exception import HackDataException

router = APIRouter(prefix="/api", tags=["Config"])


@router.get("/config", response_model=ConfigResponse)
def get_config() -> ConfigResponse:
    """Return public engine constants for frontend alignment."""
    try:
        max_mb = api_const.MAX_UPLOAD_BYTES // (1024 * 1024)
        return ConfigResponse(
            preview_rows=api_const.API_PREVIEW_ROWS,
            max_rows=gen_const.GEN_MAX_ROWS_PER_TABLE,
            max_upload_mb=max_mb,
            dm_max_synth_rows=data_mode.DM_MAX_SYNTH_ROWS,
            score_weights=eval_const.EVAL_WEIGHTS,
            generators=list(spec_const.SPEC_GENERATORS),
            modules=[
                common.MODULE_TABULAR,
                common.MODULE_RELATIONAL,
                common.MODULE_DOCUMENTS,
                # data_mode is added as a static button in the frontend nav
                # so it must NOT be in this list — otherwise it renders twice.
            ],
        )
    except Exception as e:
        raise HackDataException(e, sys)
