# ═══════════════════════════════════════════════════════════════════
# schemas.py — Pydantic request and response models for the HTTP layer
# ═══════════════════════════════════════════════════════════════════
# These are the API boundary models. FastAPI receives/returns these.
# Components never import from api/; routes convert these into
# entity.request_entity dataclasses before passing them inward.
#
# IMP: All numeric/string defaults come from constants modules, never
#      literals. Import the module, not the name — every use greppable.
###==============================================================

from typing import Dict, List, Optional

from pydantic import BaseModel

from hackdata.constants import api as api_const
from hackdata.constants import data_mode as dm_const
from hackdata.constants import documents as doc_const
from hackdata.constants import evaluation as eval_const
from hackdata.constants import generation as gen_const
from hackdata.constants import locales as loc_const
from hackdata.constants import spec as spec_const
from hackdata.constants import common


# ---------------- REQUEST MODELS ----------------

class GenerateRequest(BaseModel):
    """
    Body for POST /api/generate (query mode).

    module   → which product module to run (tabular | relational | documents)
    mode     → query (LLM spec) or data (upload; uses UploadRequest instead)
    query    → natural-language description; required when mode == query
    template → optional named template from data_assets/templates/
    n_rows   → target rows for the primary table; capped at GEN_MAX_ROWS_PER_TABLE
    seed     → explicit master seed; None lets the engine pick one
    """

    module: str
    mode: str                                                        # MODE_QUERY | MODE_DATA
    query: Optional[str] = None
    template: Optional[str] = None
    n_rows: int = gen_const.GEN_DEFAULT_N_ROWS                       # IMP: constant default, not literal
    seed: Optional[int] = None
    locale: str = loc_const.LOC_DEFAULT_LOCALE                       # "en_PK"
    currency: str = loc_const.LOC_DEFAULT_CURRENCY                   # "PKR"
    privacy: bool = False
    null_rate: Optional[float] = None
    outlier_rate: Optional[float] = None
    doc_type: Optional[str] = None
    doc_count: int = doc_const.DOC_DEFAULT_INVOICE_PICK_COUNT        # 10
    spec_override: Optional[dict] = None


class SpecEditRequest(BaseModel):
    """Body for PATCH /api/runs/{id}/spec — user-edited spec JSON."""

    # IMP: the route validates this dict against spec_entity.Spec before passing inward
    spec: dict


class SaveRunRequest(BaseModel):
    """Body for POST /api/runs/{id}/save — move run from temp to saved."""

    run_id: str


class DataModeGenerateRequest(BaseModel):
    """Body for POST /api/runs/{run_id}/generate-dm (Step A).

    Sent after the user reviews the uploaded-data panel and clicks Generate.
    All noise settings default to 0 (no effect) per spec.
    """

    n_rows: Optional[int] = None          # None → use uploaded row count
    seed: Optional[int] = None
    # Step B realism settings (all default to 0 = no effect)
    missing_rate: float = 0.0             # fraction of cells to null (MCAR)
    outlier_rate: float = 0.0             # fraction of numeric rows to push beyond 3.5σ
    noise_level: float = 0.0             # Gaussian noise as fraction of column std
    correlation_adjustment: float = 0.0  # scale off-diagonal copula corr: -1..+1


# ---------------- RESPONSE MODELS ----------------

class GenerateResponse(BaseModel):
    """
    Response from POST /api/generate.

    scores_status is always pending immediately after generation;
    poll GET /runs/{id}/scores — the Evaluator runs in a background thread.
    preview contains the first api_const.API_PREVIEW_ROWS rows per table.
    """

    run_id: str
    status: str                                    # API_STATUS_GENERATED | API_STATUS_FAILED
    module: str
    table_names: List[str]
    row_counts: Dict[str, int]
    preview: Dict[str, List[dict]]                 # table_name → first API_PREVIEW_ROWS rows
    scores_status: str                             # API_SCORE_STATUS_PENDING | PARTIAL | DONE
    message: Optional[str] = None


class ScoresResponse(BaseModel):
    """
    Response from GET /api/runs/{id}/scores.

    All score fields are None while evaluation is running (scores_status = pending).
    Scores are on the 0–100 scale (EVAL_SCORE_SCALE).
    """

    run_id: str
    scores_status: str                             # pending | partial | done
    validity: Optional[float] = None
    fidelity: Optional[float] = None
    utility: Optional[float] = None
    privacy: Optional[float] = None
    overall: Optional[float] = None
    details: Optional[dict] = None                # full scores.json content when done


class RunSummary(BaseModel):
    """One item in the run-history list (GET /api/runs)."""

    run_id: str
    module: str
    mode: str
    status: str
    created_at: str
    row_counts: Dict[str, int]
    saved: bool


class RunListResponse(BaseModel):
    """Response from GET /api/runs."""

    runs: List[RunSummary]


class HealthResponse(BaseModel):
    """Response from GET /api/health."""

    status: str = "ok"
    version: str


class ConfigResponse(BaseModel):
    """
    Public subset of constants for the frontend (GET /api/config).

    IMP: The UI reads these values from the API rather than hard-coding them,
    so caps, weights and limits can never drift between engine and UI.
    """

    preview_rows: int                  # api_const.API_PREVIEW_ROWS
    max_rows: int                      # gen_const.GEN_MAX_ROWS_PER_TABLE
    max_upload_mb: int                 # api_const.MAX_UPLOAD_BYTES // (1024*1024)
    dm_max_synth_rows: int             # dm_const.DM_MAX_SYNTH_ROWS
    score_weights: Dict[str, float]    # eval_const.EVAL_WEIGHTS
    generators: List[str]              # list(spec_const.SPEC_GENERATORS)
    modules: List[str]                 # [MODULE_TABULAR, MODULE_RELATIONAL, MODULE_DOCUMENTS]


# ---------------- ML LAB REQUEST / RESPONSE ----------------

class MLLabRequest(BaseModel):
    """Body for POST /api/ml/generate."""

    source_type: str                              # 'describe' | 'upload'
    query: Optional[str] = None                  # required for source_type='describe'
    upload_run_id: Optional[str] = None          # required for source_type='upload'
    target_col: str                              # column to predict
    task_type: str                               # 'classification' | 'regression'
    drivers: List[str] = []                      # driver columns (empty = auto)
    signal_strength: float = 0.7
    class_balance: float = 0.5
    label_noise: float = 0.0
    n_rows: int = gen_const.GEN_DEFAULT_N_ROWS
    seed: Optional[int] = None
    train_ratio: float = 0.8


class MLLabResponse(BaseModel):
    """Response from POST /api/ml/generate."""

    run_id: str
    source_type: str
    task_type: str
    target_col: str
    train_rows: int
    test_rows: int
    seed: int
    ml_check: dict
    preview: List[dict]
    message: Optional[str] = None
