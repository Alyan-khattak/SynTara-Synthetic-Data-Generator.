# ═══════════════════════════════════════════════════════════════════
# paths.py — all directory and file name constants
# ═══════════════════════════════════════════════════════════════════
# IMP: never build a literal path in component code; always os.path.join from these.
import os

ARTIFACT_DIR: str = "Artifacts"
ARTIFACT_TEMP_DIR_NAME: str = "temp"
ARTIFACT_SAVED_DIR_NAME: str = "saved"
ARTIFACTS_TEMP_DIR: str = os.path.join(ARTIFACT_DIR, ARTIFACT_TEMP_DIR_NAME)
ARTIFACTS_SAVED_DIR: str = os.path.join(ARTIFACT_DIR, ARTIFACT_SAVED_DIR_NAME)
LOGS_DIR: str = "logs"
CACHE_DIR: str = "cache"
DATA_ASSETS_DIR: str = "data_assets"
TEMPLATES_ASSETS_DIR: str = "templates"
PROMPTS_DIR: str = "prompts"
SAMPLE_DATA_DIR: str = "sample"
SCHEMA_DIR: str = "data_schema"
SPEC_SCHEMA_FILE_NAME: str = "spec.schema.json"

# per-stage artifact directory names
SPEC_BUILDER_DIR_NAME: str = "spec_builder"
FEASIBILITY_DIR_NAME: str = "feasibility"
DATA_INGESTION_DIR_NAME: str = "data_ingestion"
SCHEMA_INFERENCE_DIR_NAME: str = "schema_inference"
MODEL_FITTER_DIR_NAME: str = "model_fitter"
RULE_MINER_DIR_NAME: str = "rule_miner"
DATA_GENERATION_DIR_NAME: str = "data_generation"
DATA_VALIDATION_DIR_NAME: str = "data_validation"
EVALUATION_DIR_NAME: str = "evaluation"
DOCUMENTS_DIR_NAME: str = "documents"
EXPORT_DIR_NAME: str = "export"

# file names
SPEC_FILE_NAME: str = "spec.json"
POOLS_FILE_NAME: str = "pools.json"
SEED_FILE_NAME: str = "seed.txt"
SCORES_FILE_NAME: str = "scores.json"
VALIDATION_REPORT_FILE_NAME: str = "validation_report.json"
FEASIBILITY_REPORT_FILE_NAME: str = "feasibility_report.json"
CHECKSUMS_FILE_NAME: str = "checksums.json"
RUN_META_FILE_NAME: str = "meta.json"
FITTED_MODEL_FILE_NAME: str = "fitted_model.pkl"
LEARNED_SPEC_FILE_NAME: str = "learned_spec.json"
RULES_FILE_NAME: str = "mined_rules.yaml"
TABLES_DIR_NAME: str = "tables"
TRAIN_DIR_NAME: str = "train"
HOLDOUT_DIR_NAME: str = "holdout"
SCHEMA_FILE_NAME: str = "schema.yaml"        # inferred schema written by SchemaInference (TRD 8.4)
HTML_DIR_NAME: str = "html"                  # rendered HTML files under documents/ (TRD 8.4)
PDF_DIR_NAME: str = "pdf"                    # rendered PDF files under documents/ (TRD 8.4)
GENERATION_RUN_META_FILE_NAME: str = "run_metadata.json"  # pipeline-level summary written by GenerationPipeline

TRAIN_FILE_NAME: str = "train.csv"
HOLDOUT_FILE_NAME: str = "holdout.csv"
SYNTHETIC_DATA_FILE_NAME: str = "synthetic_data.csv"
TEMP_RUNS_MAX: int = 10
