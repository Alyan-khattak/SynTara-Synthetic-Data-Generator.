# ═══════════════════════════════════════════════════════════════════
# common.py — pipeline-wide constants shared by every module
# ═══════════════════════════════════════════════════════════════════
# Values here are used in at least two layers; keep them general.
# IMP: import the module, not the name — `from hackdata.constants import common`

PIPELINE_NAME: str = "HackDataV2"
PACKAGE_NAME: str = "hackdata"
RUN_TIMESTAMP_FORMAT: str = "%m_%d_%Y_%H_%M_%S_%f"   # microseconds prevent collision on fast Enter
LOG_TIMESTAMP_FORMAT: str = "%m_%d_%Y_%H_%M_%S"
LOG_FORMAT: str = "[ %(asctime)s ] %(lineno)d %(name)s - %(levelname)s - %(message)s"
ENV_GROQ_API_KEYS: str = "GROQ_API_KEYS"             # comma-separated list in .env
ENV_JEV_API_KEY: str = "JEV_API_KEY"
MODE_QUERY: str = "query"
MODE_DATA: str = "data"
MODULE_TABULAR: str = "tabular"
MODULE_RELATIONAL: str = "relational"
MODULE_DOCUMENTS: str = "documents"
MODULE_ML_LAB: str = "ml_lab"
RANDOM_STATE: int = 42
