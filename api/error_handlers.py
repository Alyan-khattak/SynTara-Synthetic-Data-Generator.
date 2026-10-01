# ═══════════════════════════════════════════════════════════════════
# error_handlers.py — FastAPI exception handlers for the whole app
# ═══════════════════════════════════════════════════════════════════
# Registered in app.py so that HackDataException and bare Exception
# both return structured JSON instead of FastAPI's default 500 HTML.
###==============================================================
import sys

from fastapi import Request
from fastapi.responses import JSONResponse

from hackdata.constants import api as api_const
from hackdata.exception.exception import HackDataException
from hackdata.logging.logger import logging


async def hackdata_exception_handler(request: Request, exc: HackDataException) -> JSONResponse:
    """Convert HackDataException to a structured JSON 500 response."""
    logging.error(f"HackDataException: {exc.error_message}")
    return JSONResponse(
        status_code=api_const.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": exc.error_message},
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler — prevents raw tracebacks reaching the client."""
    logging.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=api_const.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )
