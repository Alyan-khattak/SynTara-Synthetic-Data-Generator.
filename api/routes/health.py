# ═══════════════════════════════════════════════════════════════════
# health.py — API health check endpoint
# ═══════════════════════════════════════════════════════════════════
import sys
from fastapi import APIRouter

from api.schemas import HealthResponse
from hackdata.constants.spec import SPEC_VERSION
from hackdata.exception.exception import HackDataException

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
@router.get("/api/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """Return platform status and version."""
    try:
        return HealthResponse(status="ok", version=SPEC_VERSION)
    except Exception as e:
        raise HackDataException(e, sys)
