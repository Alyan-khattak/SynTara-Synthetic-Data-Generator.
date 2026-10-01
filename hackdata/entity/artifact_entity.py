# ═══════════════════════════════════════════════════════════════════
# artifact_entity.py — typed output contracts for every pipeline component
# ═══════════════════════════════════════════════════════════════════
# IMP: components NEVER return plain tuples; they return one of these
#      dataclasses.  The next component in the pipeline receives the
#      previous artifact as its sole data input.
###==============================================================
"""
artifact_entity

    Each @dataclass here corresponds to exactly one component's output.
    Pipeline step:

        Component.initiate_<stage>() -> <Stage>Artifact
            │
            └─ received by the next Component.__init__() as input

    Fields with mutable defaults (list, dict) use field(default_factory=...)
    to avoid the shared-default trap.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ---------------- GENERATION PIPELINE ARTIFACTS ----------------

@dataclass
class SpecBuilderArtifact:
    """Output of SpecBuilder: validated spec and value pools on disk."""

    spec_file_path: str
    pools_file_path: str
    # IMP: spec_source tracks where the spec came from so the UI can
    #      show the right badge ("from cache", "LLM-generated", etc.)
    spec_source: str                        # "cache" | "llm" | "user_edit" | "offline"
    unsupported: List[str] = field(default_factory=list)


@dataclass
class FeasibilityArtifact:
    """Output of FeasibilityChecker: pass/fail plus collected messages."""

    ok: bool
    report_file_path: str
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class DataGenerationArtifact:
    """Output of DataGenerator: generated table files and reproducibility info."""

    tables_dir: str
    table_file_paths: Dict[str, str]        # table_name → absolute CSV path
    master_seed: int
    row_counts: Dict[str, int]              # table_name → actual rows written


@dataclass
class DataValidationArtifact:
    """Output of DataValidator: validation result across all three tiers."""

    # IMP: status=False means tier-1 structural failure; pipeline halts.
    status: bool
    validity_score: float                   # 0.0–1.0 fraction of checks passed
    report_file_path: str
    coherence_passed: int                   # tier-3 checks passed
    coherence_total: int                    # tier-3 checks attempted


@dataclass
class EvaluationArtifact:
    """Output of Evaluator: scorecard on disk."""

    scores_file_path: str
    # IMP: overall_score is None in query mode (no real hold-out to compare
    #      against); the UI treats None as "N/A".
    overall_score: Optional[float]


# ---------------- DATA-MODE PIPELINE ARTIFACTS ----------------

@dataclass
class DataIngestionArtifact:
    """Output of DataIngestion: split CSVs written to train/ and holdout/."""

    train_dir: str
    holdout_dir: str
    table_names: List[str]
    warnings: List[str] = field(default_factory=list)


@dataclass
class SchemaInferenceArtifact:
    """Output of SchemaInference: inferred types, PKs, FKs, generator hints."""

    schema_file_path: str


@dataclass
class ModelFitterArtifact:
    """Output of ModelFitter: fitted copula model and learned spec on disk."""

    fitted_model_file_path: str
    learned_spec_file_path: str


@dataclass
class RuleMiningArtifact:
    """Output of RuleMiner (P1): mined constraint rules on disk."""

    rules_file_path: str
    rules_count: int


# ---------------- DOCUMENT PIPELINE ARTIFACTS ----------------

@dataclass
class DocumentArtifact:
    """Output of DocumentRenderer: HTML pages and PDF files on disk."""

    documents_dir: str
    html_dir: str
    pdf_file_paths: List[str]
    # IMP: reconciliation_ok=False means rendered totals did not match
    #      the source data; the UI shows a warning badge.
    reconciliation_ok: bool


# ---------------- EXPORT ARTIFACT ----------------

@dataclass
class ExportArtifact:
    """Output of Exporter: final deliverable files and their checksums."""

    export_dir: str
    file_paths: Dict[str, str]              # format_name → absolute file path
    checksums_file_path: str
