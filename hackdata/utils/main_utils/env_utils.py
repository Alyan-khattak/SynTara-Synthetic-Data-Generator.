# ═══════════════════════════════════════════════════════════════════
# env_utils.py — environment variable helpers
# ═══════════════════════════════════════════════════════════════════
# The only place that reads os.environ for application config.
# IMP: ENV_GROQ_API_KEYS holds a comma-separated list; callers get a
#      clean Python list with empty entries stripped.
###==============================================================
import os
import sys
from typing import List, Optional

from hackdata.constants import common
from hackdata.exception.exception import HackDataException
from hackdata.logging.logger import logging


def get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    """Read a single environment variable.

    Parameters
    ----------
    name : str
        Environment variable name.
    default : Optional[str]
        Returned when the variable is not set.

    Returns
    -------
    Optional[str]
        The value, or ``default`` if absent.
    """
    try:
        return os.getenv(name, default)
    except Exception as e:
        raise HackDataException(e, sys)


def get_groq_keys() -> List[str]:
    """Read and parse the GROQ_API_KEYS environment variable.

    Splits on comma, strips whitespace, and filters empty strings so that
    the key pool never receives a blank key.

    Returns
    -------
    List[str]
        Ordered list of Groq API key strings; may be empty if the variable
        is not set or is blank.
    """
    try:
        raw = os.getenv(common.ENV_GROQ_API_KEYS, "")
        keys = [k.strip() for k in raw.split(",") if k.strip()]
        logging.info(f"get_groq_keys: found {len(keys)} key(s)")
        return keys
    except Exception as e:
        raise HackDataException(e, sys)
