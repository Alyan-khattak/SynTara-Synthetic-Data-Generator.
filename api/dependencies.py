# ═══════════════════════════════════════════════════════════════════
# dependencies.py — shared FastAPI dependency helpers
# ═══════════════════════════════════════════════════════════════════
import re

from fastapi import HTTPException

from hackdata.constants import api as api_const

# Only allow alphanumeric, underscore, and hyphen; max 128 chars.
# This prevents path traversal attacks (e.g. run_id="../secret").
_SAFE_ID = re.compile(r'^[a-zA-Z0-9_\-]{1,128}$')


def validate_run_id(run_id: str) -> str:
    """Raise HTTP 400 if run_id contains path-traversal characters."""
    if not _SAFE_ID.match(run_id):
        raise HTTPException(status_code=api_const.HTTP_400_BAD_REQUEST, detail="Invalid run_id")
    return run_id
