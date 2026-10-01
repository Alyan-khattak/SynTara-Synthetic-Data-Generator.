# ═══════════════════════════════════════════════════════════════════
# config_entity.py — RunConfig + one config class per pipeline component
# ═══════════════════════════════════════════════════════════════════
# IMP: holds path strings and primitive values ONLY; no I/O, no logic.
#      Every component receives its config from the pipeline so it never
#      hard-codes a path or threshold.  Tests can override individual
#      fields on an instance to redirect writes.
###==============================================================
"""
config_entity

    RunConfig(timestamp?)
       │  run_id = "MM_DD_YYYY_HH_MM_SS_ffffff"
       └─ artifact_dir = Artifacts/temp/<run_id>
           ├─ SpecBuilderConfig   → spec_builder/<run_id>/
           ├─ FeasibilityConfig   → feasibility/<run_id>/
           ├─ DataIngestionConfig → data_ingestion/<run_id>/
           ├─ ...
           └─ ExportConfig        → export/<run_id>/

# DRY RUN:
#   rc = RunConfig(datetime(2026, 9, 29, 12, 0, 0))
#   rc.run_id          → "09_29_2026_12_00_00_000000"
#   rc.artifact_dir    → "Artifacts/temp/09_29_2026_12_00_00_000000"
#   SpecBuilderConfig(rc).spec_file_path
#                      → "Artifacts/temp/09_29_2026_12_00_00_000000/spec_builder/spec.json"
"""

import os
from datetime import datetime
from typing import Optional

from hackdata.constants import common, paths, generation, data_mode


# ---------------- ROOT RUN CONFIG ----------------

class RunConfig:
    """Timestamp and root folder shared by every component of one run.

    Parameters
    ----------
    timestamp : datetime, optional
        Fixed point in time for the run.  Pass one in tests to get
        a predictable run_id; omit in production for the current time.
    """

    def __init__(self, timestamp: Optional[datetime] = None):
        # IMP: create the stamp once here so all component configs
        # in the same run share the identical folder path.
        stamp = (timestamp or datetime.now()).strftime(common.RUN_TIMESTAMP_FORMAT)
        self.pipeline_name: str = common.PIPELINE_NAME
        self.run_id: str = stamp
        self.artifact_root: str = os.path.join(paths.ARTIFACT_DIR, paths.ARTIFACT_TEMP_DIR_NAME)
        self.artifact_dir: str = os.path.join(self.artifact_root, stamp)


# ---------------- COMPONENT CONFIGS ----------------
# Pattern: each class takes RunConfig, builds its sub-directory inside
# artifact_dir, then builds file paths inside that sub-directory.
# No logic; no default values that are not from constants.

class SpecBuilderConfig:
    """Paths for the SpecBuilder component output."""

    def __init__(self, run_config: RunConfig):
        self.spec_builder_dir: str = os.path.join(
            run_config.artifact_dir, paths.SPEC_BUILDER_DIR_NAME
        )
        self.spec_file_path: str = os.path.join(
            self.spec_builder_dir, paths.SPEC_FILE_NAME
        )
        self.pools_file_path: str = os.path.join(
            self.spec_builder_dir, paths.POOLS_FILE_NAME
        )


class FeasibilityConfig:
    """Paths for the FeasibilityChecker component output."""

    def __init__(self, run_config: RunConfig):
        self.feasibility_dir: str = os.path.join(
            run_config.artifact_dir, paths.FEASIBILITY_DIR_NAME
        )
        self.report_file_path: str = os.path.join(
            self.feasibility_dir, paths.FEASIBILITY_REPORT_FILE_NAME
        )


class DataIngestionConfig:
    """Paths for the DataIngestion component output (data-mode only)."""

    def __init__(self, run_config: RunConfig):
        self.data_ingestion_dir: str = os.path.join(
            run_config.artifact_dir, paths.DATA_INGESTION_DIR_NAME
        )
        # IMP: train/ and holdout/ live inside data_ingestion_dir so
        #      the whole ingestion subtree stays under one run folder.
        self.train_dir: str = os.path.join(
            self.data_ingestion_dir, paths.TRAIN_DIR_NAME
        )
        self.holdout_dir: str = os.path.join(
            self.data_ingestion_dir, paths.HOLDOUT_DIR_NAME
        )


class SchemaInferenceConfig:
    """Paths for the SchemaInference component output (data-mode only)."""

    def __init__(self, run_config: RunConfig):
        self.schema_inference_dir: str = os.path.join(
            run_config.artifact_dir, paths.SCHEMA_INFERENCE_DIR_NAME
        )
        self.schema_file_path: str = os.path.join(
            self.schema_inference_dir, paths.SCHEMA_FILE_NAME
        )


class ModelFitterConfig:
    """Paths for the ModelFitter component output (data-mode only)."""

    def __init__(self, run_config: RunConfig):
        self.model_fitter_dir: str = os.path.join(
            run_config.artifact_dir, paths.MODEL_FITTER_DIR_NAME
        )
        self.fitted_model_file_path: str = os.path.join(
            self.model_fitter_dir, paths.FITTED_MODEL_FILE_NAME
        )
        self.learned_spec_file_path: str = os.path.join(
            self.model_fitter_dir, paths.LEARNED_SPEC_FILE_NAME
        )


class RuleMinerConfig:
    """Paths for the RuleMiner component output (P1)."""

    def __init__(self, run_config: RunConfig):
        self.rule_miner_dir: str = os.path.join(
            run_config.artifact_dir, paths.RULE_MINER_DIR_NAME
        )
        self.rules_file_path: str = os.path.join(
            self.rule_miner_dir, paths.RULES_FILE_NAME
        )


class DataGenerationConfig:
    """Paths for the DataGenerator component output."""

    def __init__(self, run_config: RunConfig):
        self.data_generation_dir: str = os.path.join(
            run_config.artifact_dir, paths.DATA_GENERATION_DIR_NAME
        )
        # tables/ sub-directory holds one CSV per generated table
        self.tables_dir: str = os.path.join(
            self.data_generation_dir, paths.TABLES_DIR_NAME
        )
        self.seed_file_path: str = os.path.join(
            self.data_generation_dir, paths.SEED_FILE_NAME
        )


class DataValidationConfig:
    """Paths for the DataValidator component output."""

    def __init__(self, run_config: RunConfig):
        self.data_validation_dir: str = os.path.join(
            run_config.artifact_dir, paths.DATA_VALIDATION_DIR_NAME
        )
        self.report_file_path: str = os.path.join(
            self.data_validation_dir, paths.VALIDATION_REPORT_FILE_NAME
        )


class EvaluationConfig:
    """Paths for the Evaluator component output."""

    def __init__(self, run_config: RunConfig):
        self.evaluation_dir: str = os.path.join(
            run_config.artifact_dir, paths.EVALUATION_DIR_NAME
        )
        self.scores_file_path: str = os.path.join(
            self.evaluation_dir, paths.SCORES_FILE_NAME
        )


class DocumentConfig:
    """Paths for the DocumentRenderer component output."""

    def __init__(self, run_config: RunConfig):
        self.documents_dir: str = os.path.join(
            run_config.artifact_dir, paths.DOCUMENTS_DIR_NAME
        )
        # html/ holds the intermediate Jinja-rendered pages
        self.html_dir: str = os.path.join(
            self.documents_dir, paths.HTML_DIR_NAME
        )
        # pdf/ holds the Playwright-rendered PDFs
        self.pdf_dir: str = os.path.join(
            self.documents_dir, paths.PDF_DIR_NAME
        )


class ExportConfig:
    """Paths for the Exporter component output."""

    def __init__(self, run_config: RunConfig):
        self.export_dir: str = os.path.join(
            run_config.artifact_dir, paths.EXPORT_DIR_NAME
        )
        self.checksums_file_path: str = os.path.join(
            self.export_dir, paths.CHECKSUMS_FILE_NAME
        )
