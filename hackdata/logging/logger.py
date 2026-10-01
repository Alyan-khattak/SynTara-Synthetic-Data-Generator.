# ═══════════════════════════════════════════════════════════════════
# logger.py — project-wide logging configuration
# ═══════════════════════════════════════════════════════════════════
# Importing this module is the side-effect that sets up logging.
# Usage: from hackdata.logging.logger import logging
#        logging.info("message")
# IMP: always run from repo root (or with python -m); running a script
#      from inside hackdata/logging/ shadows the stdlib `logging` module.
###==============================================================
import logging
import os
from datetime import datetime
from hackdata.constants import common, paths

# One log file per process start, named by timestamp
LOG_FILE = f"{datetime.now().strftime(common.LOG_TIMESTAMP_FORMAT)}.log"
LOGS_PATH = os.path.join(os.getcwd(), paths.LOGS_DIR)
os.makedirs(LOGS_PATH, exist_ok=True)

logging.basicConfig(
    format=common.LOG_FORMAT,
    level=logging.INFO,
    handlers=[
        logging.FileHandler(os.path.join(LOGS_PATH, LOG_FILE)),
        logging.StreamHandler(),
    ],
)
