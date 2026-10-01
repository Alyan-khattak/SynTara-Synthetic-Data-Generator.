# ═══════════════════════════════════════════════════════════════════
# test_llm_client.py — prove the LLM is central and retry path works
# ═══════════════════════════════════════════════════════════════════
# Step 4 of the open-weight migration:
#   T-A: stub the model → main feature depends on its output
#   T-B: bad JSON on first call → repair path fires → fallback offline spec
###==============================================================
import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

# Load .env so constants initialise correctly
from dotenv import load_dotenv
load_dotenv()

from hackdata.cloud import llm_client
from hackdata.entity.spec_entity import Spec


# ── helpers ───────────────────────────────────────────────────────

def _minimal_spec_json() -> str:
    """Smallest valid JSON the LLM could return for a spec request."""
    return json.dumps({
        "version": "1",
        "module": "tabular",
        "tables": [
            {
                "name": "customers",
                "n_rows": 10,
                "columns": [
                    {"name": "id", "gen": "sequence"},
                    {"name": "name", "gen": "faker", "faker_field": "name"},
                ],
            }
        ],
    })


def _mock_groq_response(content: str) -> MagicMock:
    """Build a mock groq SDK response object with the given content."""
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


# ── T-A: main feature depends on LLM output ──────────────────────

def test_ask_json_uses_llm_output(tmp_path, monkeypatch):
    """
    T-A: ask_json returns what the LLM says.

    If the LLM stub returns a different table name, the result reflects
    that — proving ask_json is driven by model output, not a fixed response.
    """
    # Force cache to a fresh temp dir so no prior cache hit masks the call
    monkeypatch.setattr(llm_client, "_build_cache_key", lambda *a: "test_key_ta")

    # Patch cache to always miss so the LLM is always called
    monkeypatch.setattr("hackdata.cloud.llm_client.cache_get", lambda key: None)
    captured_puts = []
    monkeypatch.setattr("hackdata.cloud.llm_client.cache_put", lambda k, v: captured_puts.append(v))

    # Stub _try_model to return a valid spec with a distinct table name
    stub_spec = json.dumps({
        "version": "1",
        "module": "tabular",
        "tables": [{"name": "stub_table", "n_rows": 5, "columns": [
            {"name": "id", "gen": "sequence"},
        ]}],
    })
    monkeypatch.setattr(llm_client, "_try_model", lambda *a, **kw: stub_spec)

    # Stub prompt loader to return a simple template
    monkeypatch.setattr("hackdata.cloud.llm_client.load_prompt", lambda name: "{query}")

    result = llm_client.ask_json("spec", {"query": "test", "module": "tabular", "n_rows": 5}, Spec)

    # The result must come from the stub, not from any fixed fallback
    assert result["tables"][0]["name"] == "stub_table", (
        "ask_json output must reflect what the LLM returned"
    )
    # Result was cached (proves the model ran, not offline_fallback)
    assert len(captured_puts) == 1


def test_pipeline_stalls_without_llm(monkeypatch):
    """
    T-A cont.: when LLM is removed (all models exhausted + no offline match),
    ask_json raises HackDataException — proving the feature depends on the model.

    We achieve this by making offline_fallback return an invalid dict.
    """
    from hackdata.exception.exception import HackDataException

    monkeypatch.setattr("hackdata.cloud.llm_client.cache_get", lambda key: None)
    monkeypatch.setattr("hackdata.cloud.llm_client.cache_put", lambda k, v: None)
    monkeypatch.setattr(llm_client, "_try_model", lambda *a, **kw: None)  # all models fail
    monkeypatch.setattr("hackdata.cloud.llm_client.load_prompt", lambda name: "{query}")
    # offline_fallback returns something that fails Spec validation
    monkeypatch.setattr(
        "hackdata.cloud.llm_client.build_offline_spec",
        lambda *a, **kw: {"version": "1", "module": "INVALID_MODULE", "tables": []},
    )

    with pytest.raises(HackDataException):
        llm_client.ask_json("spec", {"query": "test"}, Spec)


# ── T-B: bad-JSON retry path ──────────────────────────────────────

def test_ask_json_repairs_bad_json(monkeypatch):
    """
    T-B: when the first LLM call returns garbage JSON, _repair_json is called;
    if the repair succeeds the result is used.
    """
    monkeypatch.setattr("hackdata.cloud.llm_client.cache_get", lambda key: None)
    monkeypatch.setattr("hackdata.cloud.llm_client.cache_put", lambda k, v: None)
    # Repair template uses {broken_json} and {error}; spec template uses {query}
    def _stub_prompt(name):
        if name == "repair":
            return "Fix this: {broken_json} error: {error}"
        return "{query}"

    monkeypatch.setattr("hackdata.cloud.llm_client.load_prompt", _stub_prompt)

    calls = []

    def fake_call_with_fallback(prompt_name, messages_list, as_json):
        calls.append(prompt_name)
        if prompt_name == "spec":
            return "THIS IS NOT JSON {{{"
        if prompt_name == "repair":
            # Repair returns valid spec
            return json.dumps({
                "version": "1",
                "module": "tabular",
                "tables": [{"name": "repaired_table", "n_rows": 3, "columns": [
                    {"name": "id", "gen": "sequence"},
                ]}],
            })
        return None

    monkeypatch.setattr(llm_client, "_call_with_fallback", fake_call_with_fallback)

    result = llm_client.ask_json("spec", {"query": "test", "module": "tabular"}, Spec)

    assert "repair" in calls, "repair path must be attempted on bad JSON"
    assert result["tables"][0]["name"] == "repaired_table"


def test_ask_json_falls_back_to_offline_when_repair_also_fails(monkeypatch):
    """
    T-B cont.: when both LLM and repair return bad JSON, offline_fallback is used.
    """
    from hackdata.cloud.offline_fallback import build_offline_spec as real_offline

    monkeypatch.setattr("hackdata.cloud.llm_client.cache_get", lambda key: None)
    monkeypatch.setattr("hackdata.cloud.llm_client.cache_put", lambda k, v: None)
    monkeypatch.setattr("hackdata.cloud.llm_client.load_prompt", lambda name: "{query}")

    # Both spec and repair calls return broken JSON
    monkeypatch.setattr(llm_client, "_call_with_fallback", lambda *a, **kw: "NOT JSON")

    offline_called = []
    original_offline = real_offline

    def tracked_offline(*args, **kwargs):
        offline_called.append(True)
        return original_offline(*args, **kwargs)

    monkeypatch.setattr("hackdata.cloud.llm_client.build_offline_spec", tracked_offline)

    result = llm_client.ask_json("spec", {"query": "test orders", "module": "tabular"}, Spec)

    assert len(offline_called) >= 1, "offline_fallback must be called when LLM fails"
    assert "tables" in result
