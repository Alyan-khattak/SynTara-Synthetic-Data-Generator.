# ═══════════════════════════════════════════════════════════════════
# request_entity.py — typed request contracts from the API to the pipeline
# ═══════════════════════════════════════════════════════════════════
# IMP: components import these dataclasses; they never import from api/.
#      The API layer converts its Pydantic models into these so the
#      import direction (api → pipeline → components) is preserved.
###==============================================================
"""
request_entity

    API route
        │  validates with Pydantic (api/schemas.py)
        │  converts to ──▶  GenerationRequest  or  UploadRequest
        ▼
    pipeline / module
        (components receive the dataclass; they never see Pydantic models)
"""

from dataclasses import dataclass, field
from typing import Optional

from hackdata.constants import generation, locales, documents


# ---------------- QUERY-MODE REQUEST ----------------

@dataclass
class GenerationRequest:
    """Everything the generation pipeline needs from the caller.

    Parameters
    ----------
    module      : "tabular" | "relational" | "documents"
    mode        : "query" | "data"
    query       : natural-language description of the dataset
    template    : optional pre-built template name (e.g. "ecommerce")
    n_rows      : target row count for the primary / only table
    seed        : master random seed; None means generate a fresh one
    locale      : BCP-47 locale code used for locale-aware generators
    currency    : ISO-4217 currency code
    privacy     : True → mask / noise PII columns before export
    null_rate   : fraction of nulls to inject; None → use engine default
    outlier_rate: fraction of outliers to inject; None → use engine default
    doc_type    : "invoice" | "statement" (documents module only)
    doc_count   : number of documents to render
    spec_override: partial spec dict that overwrites the LLM output;
                   None → use the spec as-is
    """

    module: str
    mode: str
    query: str
    template: Optional[str] = None
    n_rows: int = field(default_factory=lambda: generation.GEN_DEFAULT_N_ROWS)
    seed: Optional[int] = None
    locale: str = field(default_factory=lambda: locales.LOC_DEFAULT_LOCALE)
    currency: str = field(default_factory=lambda: locales.LOC_DEFAULT_CURRENCY)
    privacy: bool = False
    null_rate: Optional[float] = None
    outlier_rate: Optional[float] = None
    doc_type: Optional[str] = None
    doc_count: int = field(default_factory=lambda: documents.DOC_DEFAULT_INVOICE_PICK_COUNT)
    spec_override: Optional[dict] = None


# ---------------- DATA-MODE REQUEST ----------------

@dataclass
class UploadRequest:
    """Everything the data-mode pipeline needs from the caller.

    Parameters
    ----------
    module    : "tabular" | "relational"
    file_path : absolute path to the uploaded file (written by the API route)
    n_rows    : target row count for generated synthetic data
    seed      : master random seed; None means generate a fresh one
    locale    : BCP-47 locale code
    currency  : ISO-4217 currency code
    """

    module: str
    file_path: str
    n_rows: int = field(default_factory=lambda: generation.GEN_DEFAULT_N_ROWS)
    seed: Optional[int] = None
    locale: str = field(default_factory=lambda: locales.LOC_DEFAULT_LOCALE)
    currency: str = field(default_factory=lambda: locales.LOC_DEFAULT_CURRENCY)
