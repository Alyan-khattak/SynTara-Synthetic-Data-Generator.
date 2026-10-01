# ═══════════════════════════════════════════════════════════════════
# jev_client.py — TypeSafe Jev integration for query routing
# ═══════════════════════════════════════════════════════════════════
# Called by spec_builder BEFORE the expensive LLM spec call to:
#   1. Guard: reject queries that are not data-gen requests (Noul).
#   2. Route: pick the right module — tabular/relational/documents (Choice).
#
# Fully optional: returns (None, None) when JEV_API_KEY is absent so
# the rest of the pipeline continues unchanged.
#
# IMP: lives in cloud/ — the only layer allowed to call external APIs.
#      Nothing outside cloud/ may import this module.
###==============================================================
import sys
from typing import Optional, Tuple

from hackdata.constants import common, llm as llm_const
from hackdata.exception.exception import HackDataException
from hackdata.logging.logger import logging
from hackdata.utils.main_utils.env_utils import get_env


def route_query(query: str, requested_module: str) -> Tuple[Optional[float], Optional[str]]:
    """Ask Jev whether the query is valid and which module it needs.

    Parameters
    ----------
    query : str
        The user's free-text data-generation request.
    requested_module : str
        The module the caller already believes it needs (may be empty/default).

    Returns
    -------
    (valid_prob, module)
        valid_prob : float | None — Noul probability (0-1) that the query is a
                     genuine data-gen request; None when Jev is unavailable.
        module     : str | None  — 'tabular', 'relational', or 'documents';
                     None when Jev is unavailable.

    Notes
    -----
    Both questions run in one parallel Jev request (no sequential latency).
    Caller is responsible for threshold logic (LLM_JEV_VALID_THRESHOLD).
    """
    api_key = get_env(common.ENV_JEV_API_KEY)
    if not api_key:
        logging.info("jev_client.route_query: JEV_API_KEY not set — skipping")
        return None, None

    try:
        from typesafe_sdk import TypeSafeClient, Choice, Noul  # late import — optional dep
    except ImportError:
        logging.info("jev_client.route_query: typesafe-sdk not installed — skipping")
        return None, None

    try:
        state = {
            "query": query,
            "requested_module": requested_module,
        }
        questions = {
            "valid": Noul(
                instructions=(
                    "Is this a request to generate synthetic data? "
                    "A valid request asks for rows, records, tables, a dataset, "
                    "invoices, documents, or similar structured/semi-structured output. "
                    "Reject greetings, gibberish, code questions, and off-topic prompts."
                )
            ),
            "module": Choice(
                instructions=(
                    "Which generation module does this request need? "
                    "Use `query.requested_module` as a hint if it is already set."
                ),
                criteria={
                    common.MODULE_TABULAR: "Single flat table of rows and columns.",
                    common.MODULE_RELATIONAL: (
                        "Multiple related tables with foreign-key relationships."
                    ),
                    common.MODULE_DOCUMENTS: (
                        "Semi-structured documents such as invoices, receipts, or reports."
                    ),
                },
            ),
        }

        with TypeSafeClient(api_key=api_key) as client:
            response = client.system_one(state=state, questions=questions)

        valid_prob: float = response.nouls["valid"].noul
        module: str = response.choices["module"].choice

        logging.info(
            f"jev_client.route_query: valid_prob={valid_prob:.3f} module={module}"
        )
        return valid_prob, module

    except Exception as e:
        # IMP: Jev failure must never break the main pipeline — log and return None.
        logging.info(f"jev_client.route_query: error — {e} — falling through to LLM")
        return None, None


# ─────────────────────────────────────────────────────────────────────
# SELF-CHECK
# ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import os
    # Without a key the function must return (None, None) gracefully.
    os.environ.pop(common.ENV_JEV_API_KEY, None)
    prob, mod = route_query("100 customer records", common.MODULE_TABULAR)
    assert prob is None and mod is None, f"expected (None, None) without key, got ({prob}, {mod})"
    print("jev_client self-check PASS — graceful no-key path confirmed")
