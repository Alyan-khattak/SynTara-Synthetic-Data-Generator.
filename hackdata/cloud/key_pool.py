# ═══════════════════════════════════════════════════════════════════
# key_pool.py — Groq API key rotation with per-key cooldown on 429
# ═══════════════════════════════════════════════════════════════════
# Sits between llm_client and the Groq quota system.
# IMP: keys are tried in insertion order; a 429 puts one key on cooldown
#      for LLM_KEY_COOLDOWN_SECONDS while the others remain usable.
###==============================================================
import sys
import time
from typing import List, Optional

from hackdata.constants import llm as llm_const
from hackdata.exception.exception import HackDataException
from hackdata.logging.logger import logging


class KeyPool:
    """
    Manages a list of Groq API keys with per-key cooldown on rate-limit.

    Each key is stored as [key_str, available_at_float] where
    available_at is a Unix timestamp; 0.0 means immediately available.

    next_key()      → first key where time.time() >= available_at; None if all cooling
    mark_cooldown() → set available_at = now + LLM_KEY_COOLDOWN_SECONDS

    DRY RUN: KeyPool(["k1", "k2"])
      _keys = [["k1", 0.0], ["k2", 0.0]]
      next_key() → "k1"              (time.time() >= 0.0)
      mark_cooldown("k1") → _keys[0][1] = time.time() + 60
      next_key() → "k2"              (k1 still cooling, k2 available at 0.0)
    """

    def __init__(self, keys: List[str]):
        try:
            logging.info(f"KeyPool: initializing with {len(keys)} key(s)")
            # IMP: available_at starts at 0.0 so every key is usable immediately
            self._keys: List[List] = [[k, 0.0] for k in keys]
        except Exception as e:
            raise HackDataException(e, sys)

    def next_key(self) -> Optional[str]:
        """Return the first key whose cooldown has expired, or None if all cooling.

        Returns
        -------
        Optional[str]
            An API key string, or None when every key is still rate-limited.
        """
        try:
            now = time.time()
            for entry in self._keys:
                if now >= entry[1]:
                    return entry[0]
            return None
        except Exception as e:
            raise HackDataException(e, sys)

    def mark_cooldown(self, key: str) -> None:
        """Put a key on cooldown for LLM_KEY_COOLDOWN_SECONDS.

        Parameters
        ----------
        key : str
            The API key that returned a 429 or timed out.
        """
        try:
            cooldown_until = time.time() + llm_const.LLM_KEY_COOLDOWN_SECONDS
            for entry in self._keys:
                if entry[0] == key:
                    entry[1] = cooldown_until
                    # IMP: show only last 4 chars so the key is never logged in full
                    logging.info(
                        f"KeyPool: ...{key[-4:]} cooling for {llm_const.LLM_KEY_COOLDOWN_SECONDS}s"
                    )
                    return
            logging.info("KeyPool: mark_cooldown called with unrecognised key")  # noqa: hardcode
        except Exception as e:
            raise HackDataException(e, sys)
