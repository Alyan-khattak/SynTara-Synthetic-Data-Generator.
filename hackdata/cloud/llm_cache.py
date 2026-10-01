# ═══════════════════════════════════════════════════════════════════
# llm_cache.py — disk cache for LLM responses, keyed by any string
# ═══════════════════════════════════════════════════════════════════
# Two-level directory layout: cache/{key[:2]}/{key}.json
# IMP: the same _cache_path() function is used by both get() and put()
#      so they always agree on the file location.
###==============================================================
import os
import sys
from typing import Optional

from hackdata.constants import llm as llm_const, paths as paths_const
from hackdata.exception.exception import HackDataException
from hackdata.logging.logger import logging


# ---------------- INTERNAL ----------------

def _cache_path(cache_key: str) -> str:
    """Build the two-level file path for a cache entry.

    Subdirectory = first 2 chars of the key (padded with '_' if key is
    shorter than 2 chars — avoids directory naming edge cases).

    # DRY RUN: _cache_path("abc123def456…")
    #   subdir = "ab"
    #   → cache/ab/abc123def456….json

    # IMP: two-level dirs keep each subdirectory under ~256 entries for
    #      sha256 keys — the same trick git uses for loose object storage.
    """
    subdir = cache_key[:2] if len(cache_key) >= 2 else cache_key.ljust(2, "_")
    return os.path.join(paths_const.CACHE_DIR, subdir, cache_key + ".json")


# ---------------- PUBLIC API ----------------

def get(cache_key: str) -> Optional[str]:
    """Return cached content for the given key, or None on miss.

    Parameters
    ----------
    cache_key : str
        The cache key (typically a sha256 hex digest, or any string).

    Returns
    -------
    Optional[str]
        The cached string content, or None if not found.
    """
    try:
        path = _cache_path(cache_key)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        logging.info(f"llm_cache get: hit — {cache_key[:llm_const.LLM_CACHE_KEY_DISPLAY_LEN]}…")
        return content
    except Exception as e:
        raise HackDataException(e, sys)


def put(cache_key: str, content: str) -> None:
    """Write content to the disk cache under a two-level directory.

    Parameters
    ----------
    cache_key : str
        The cache key (typically a sha256 hex digest, or any string).
    content : str
        The string to cache (typically a JSON response body).
    """
    try:
        path = _cache_path(cache_key)
        # IMP: exist_ok=True because two requests can race to create the same subdir
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        logging.info(f"llm_cache put: {len(content)} bytes — {cache_key[:llm_const.LLM_CACHE_KEY_DISPLAY_LEN]}…")
    except Exception as e:
        raise HackDataException(e, sys)
