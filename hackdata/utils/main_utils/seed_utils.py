# ═══════════════════════════════════════════════════════════════════
# seed_utils.py — deterministic seeding from blake2b, RNG factory
# ═══════════════════════════════════════════════════════════════════
# Every random draw in the engine must use make_rng(master, table, column)
# so the same spec + seed always produces identical data.
# IMP: never use np.random.seed() — global state causes reproducibility bugs
#      across threads and between calls in the same process.
###==============================================================
import hashlib
import secrets
import sys

import numpy as np

from hackdata.constants import generation
from hackdata.exception.exception import HackDataException
from hackdata.logging.logger import logging


def derive_seed(master: int, *keys: str) -> int:
    """Derive a deterministic per-column seed from the master seed and key path.

    The seed string is ``str(master) + SEP + key1 + SEP + key2 + ...``.
    blake2b truncated to GEN_SEED_DIGEST_SIZE bytes is converted to int.

    Parameters
    ----------
    master : int
        The run-level master seed.
    *keys : str
        Ordered scope keys, e.g. ``("orders", "amount")``.

    Returns
    -------
    int
        A stable non-negative integer seed; identical inputs always give identical output.

    # DRY RUN: derive_seed(42, "orders", "amount")
    #   seed_str = "42|orders|amount"
    #   blake2b(b"42|orders|amount", digest_size=8) → 8-byte digest
    #   int.from_bytes(digest, "big") → e.g. 3735928559 (deterministic)
    #   → same integer every call for the same (master, keys)
    """
    try:
        sep = generation.GEN_SEED_SEPARATOR
        seed_str = sep.join([str(master)] + list(keys))
        digest = hashlib.blake2b(
            seed_str.encode("utf-8"),
            digest_size=generation.GEN_SEED_DIGEST_SIZE,
        ).digest()
        return int.from_bytes(digest, "big")
    except Exception as e:
        raise HackDataException(e, sys)


def make_rng(master: int, *keys: str) -> np.random.Generator:
    """Build a reproducible NumPy Generator scoped to a master seed + key path.

    Parameters
    ----------
    master : int
        The run-level master seed.
    *keys : str
        Ordered scope keys passed through to derive_seed.

    Returns
    -------
    np.random.Generator
        A freshly seeded Generator; call again with the same args to replay.

    # IMP: np.random.default_rng is per-instance; no global state is touched.
    """
    try:
        seed = derive_seed(master, *keys)
        return np.random.default_rng(seed)
    except Exception as e:
        raise HackDataException(e, sys)


def new_master_seed() -> int:
    """Generate a cryptographically random master seed that fits in int32.

    Returns
    -------
    int
        A random integer in [0, 2**31).

    # IMP: secrets.randbelow is CSPRNG; fits int32 so it can be stored in
    #      any DB column or passed in a URL without overflow.
    """
    try:
        return secrets.randbelow(2 ** 31)
    except Exception as e:
        raise HackDataException(e, sys)
