# ═══════════════════════════════════════════════════════════════════
# app.py — Main FastAPI application entry point
# ═══════════════════════════════════════════════════════════════════
import os
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from dotenv import load_dotenv
load_dotenv()

from api.error_handlers import generic_exception_handler, hackdata_exception_handler
from api.routes import config, generate, health, profile, runs, schema, upload
from hackdata.constants import api as api_const
from hackdata.constants.spec import SPEC_VERSION
from hackdata.exception.exception import HackDataException
from hackdata.logging.logger import logging

app = FastAPI(
    title="HackDataV2 Synthetic Data Platform API",
    version=SPEC_VERSION,
    description="Synthetic Data Generation Platform for Tabular, Relational, and Document Data",
)

# CORS middleware for local frontend dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register exception handlers before routers so they catch all errors
app.add_exception_handler(HackDataException, hackdata_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# Register API routers
app.include_router(health.router)
app.include_router(config.router)
app.include_router(generate.router)
app.include_router(runs.router)
app.include_router(schema.router)
app.include_router(upload.router)
app.include_router(profile.router)

# Mount frontend static directory if present
frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
    logging.info(f"Mounted frontend static files from {frontend_dir}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
