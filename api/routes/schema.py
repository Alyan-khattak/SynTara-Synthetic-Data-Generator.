# ═══════════════════════════════════════════════════════════════════
# schema.py — ER diagram endpoint (relational runs only)
# ═══════════════════════════════════════════════════════════════════
import os
import sys

from fastapi import APIRouter, HTTPException

from api.dependencies import validate_run_id
from hackdata.components.er_diagram import spec_to_mermaid, is_relational_with_fk
from hackdata.constants import api as api_const, paths as paths_const, messages as msg_const
from hackdata.entity.spec_entity import Spec
from hackdata.exception.exception import HackDataException
from hackdata.logging.logger import logging
from hackdata.utils.main_utils.utils import read_json_file

router = APIRouter(prefix="/api", tags=["Schema"])


@router.get("/runs/{run_id}/schema")
def get_run_schema(run_id: str):
    """Return Mermaid erDiagram text for a relational run.

    Returns 200 with {mermaid: str} for relational runs with FK relationships.
    Returns 200 with {applicable: false, message: str} for all other runs so the
    frontend can cleanly hide the Schema tab without treating it as an error.
    """
    try:
        validate_run_id(run_id)

        # locate run directory (temp then saved)
        run_dir = os.path.join(paths_const.ARTIFACTS_TEMP_DIR, run_id)
        if not os.path.exists(run_dir):
            run_dir = os.path.join(paths_const.ARTIFACTS_SAVED_DIR, run_id)
        if not os.path.exists(run_dir):
            raise HTTPException(
                status_code=api_const.HTTP_404_NOT_FOUND,
                detail=msg_const.MSG_SCHEMA_RUN_NOT_FOUND.format(run_id=run_id),
            )

        spec_path = os.path.join(run_dir, paths_const.SPEC_BUILDER_DIR_NAME, paths_const.SPEC_FILE_NAME)
        if not os.path.exists(spec_path):
            return {"applicable": False, "message": msg_const.MSG_SCHEMA_NO_FK}

        spec_data = read_json_file(spec_path)
        spec = Spec(**spec_data)

        if not is_relational_with_fk(spec):
            msg = (msg_const.MSG_SCHEMA_NOT_RELATIONAL
                   if spec.module != "relational"
                   else msg_const.MSG_SCHEMA_NO_FK)
            return {"applicable": False, "message": msg}

        diagram = spec_to_mermaid(spec)
        logging.info(f"Schema diagram generated for run {run_id}")
        return {"applicable": True, "mermaid": diagram}

    except HTTPException:
        raise
    except (ValueError, Exception) as e:
        # ValueError = not relational or no FK
        if isinstance(e, ValueError):
            return {"applicable": False, "message": str(e)}
        raise HTTPException(status_code=api_const.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
