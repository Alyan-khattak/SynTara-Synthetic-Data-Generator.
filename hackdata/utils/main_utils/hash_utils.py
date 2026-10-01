# ═══════════════════════════════════════════════════════════════════
# hash_utils.py — SHA-256 helpers for files, text and LLM cache keys
# ═══════════════════════════════════════════════════════════════════
# Used by the LLM cache (llm_cache.py) and the export checksum writer.
# IMP: query_cache_key uses canonical JSON (sort_keys=True) so that
#      the same logical query always maps to the same cache entry,
#      regardless of Python dict insertion order.
###==============================================================
import hashlib
import json
import sys
from typing import Optional

from hackdata.constants import export as export_const
from hackdata.exception.exception import HackDataException
from hackdata.logging.logger import logging


def sha256_file(path: str) -> str:
    """Return the SHA-256 hex digest of a file's raw bytes.

    Parameters
    ----------
    path : str
        Path to the file to hash.

    Returns
    -------
    str
        64-character lowercase hex digest.
    """
    try:
        logging.info(f"sha256_file: hashing {path}")
        h = hashlib.sha256()
        with open(path, "rb") as f:
            # Read in 64 KB chunks to keep RAM flat on large files
            for chunk in iter(lambda: f.read(export_const.EXP_HASH_FILE_CHUNK_BYTES), b""):
                h.update(chunk)
        digest = h.hexdigest()
        logging.info(f"sha256_file: done — {path}")
        return digest
    except Exception as e:
        raise HackDataException(e, sys)


def sha256_text(text: str) -> str:
    """Return the SHA-256 hex digest of a UTF-8 encoded string.

    Parameters
    ----------
    text : str
        Input text.

    Returns
    -------
    str
        64-character lowercase hex digest.
    """
    try:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
    except Exception as e:
        raise HackDataException(e, sys)


def query_cache_key(
    query: str,
    module: str,
    template: Optional[str],
    locale: str,
) -> str:
    """Build a stable cache key for an LLM spec request.

    The key is the SHA-256 of the canonical JSON of the four fields
    (sorted keys, so order never matters).

    Parameters
    ----------
    query : str
        The free-text generation request.
    module : str
        One of the MODULE_* constants ("tabular", "relational", "documents").
    template : Optional[str]
        Template name, or None.
    locale : str
        Locale string, e.g. "en_PK".

    Returns
    -------
    str
        64-character hex digest.

    # DRY RUN: query_cache_key("orders", "relational", None, "en_PK")
    #   payload = {"locale": "en_PK", "module": "relational",
    #              "query": "orders", "template": null}
    #   canonical = json.dumps(payload, sort_keys=True)
    #   → sha256(canonical.encode("utf-8")).hexdigest()
    """
    try:
        payload = {
            "query": query,
            "module": module,
            "template": template,
            "locale": locale,
        }
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return sha256_text(canonical)
    except Exception as e:
        raise HackDataException(e, sys)
