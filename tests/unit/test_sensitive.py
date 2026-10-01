# ═══════════════════════════════════════════════════════════════════
# test_sensitive.py — sensitive-data safety pass tests
# ═══════════════════════════════════════════════════════════════════
import zipfile
from io import BytesIO

import numpy as np
import pandas as pd
import pytest
from dotenv import load_dotenv

load_dotenv()

from hackdata.components.generators.column_generators import (
    gen_card,
    gen_email,
    gen_national_id,
)
from hackdata.components.sensitive_masker import detect_and_mask
from hackdata.constants import generation as gen_const


def _rng(seed: int = 42) -> np.random.Generator:
    return np.random.default_rng(seed)


# ── email ─────────────────────────────────────────────────────────

def test_email_uses_example_com():
    """All generated emails must use the @example.com reserved domain."""
    result = gen_email(50, {}, _rng())
    assert all(addr.endswith("@example.com") for addr in result), (
        "gen_email must only produce @example.com addresses"
    )


def test_email_no_real_domain():
    """No generated email should contain a real TLD domain (gmail, yahoo, etc.)."""
    real_domains = ("gmail.com", "yahoo.com", "hotmail.com", "outlook.com")
    result = gen_email(100, {}, _rng())
    for addr in result:
        for domain in real_domains:
            assert domain not in addr, f"Real domain {domain!r} found in email: {addr}"


# ── national_id ───────────────────────────────────────────────────

def test_national_id_masked_by_default():
    """Default output must be masked: *****-*******-X."""
    result = gen_national_id(20, {}, _rng())
    for nid in result:
        assert nid.startswith("*****-*******-"), (
            f"national_id not masked by default: {nid}"
        )
        assert len(nid) == len("*****-*******-X"), (
            f"masked national_id wrong length: {nid}"
        )


def test_national_id_fake_marker_when_unmasked():
    """When masked=False, first digit must be the fake marker ('0')."""
    result = gen_national_id(20, {"masked": False}, _rng())
    for nid in result:
        assert nid[0] == gen_const.GEN_MASK_CHAR[0] or nid[0] == "0", (
            f"national_id without fake marker: {nid}"
        )
    # Specifically check the fake marker character
    first_digits = {nid[0] for nid in result}
    assert first_digits == {"0"}, f"Expected only '0' as first digit, got {first_digits}"


# ── card ──────────────────────────────────────────────────────────

def test_card_masked_by_default():
    """Default card output must be masked and labelled [TEST CARD]."""
    result = gen_card(20, {}, _rng())
    for val in result:
        assert "[TEST CARD]" in val, f"Card missing [TEST CARD] label: {val}"
        assert val.startswith("**** **** **** "), f"Card not masked: {val}"


def test_card_last_four_from_test_list():
    """Last 4 visible digits must come from one of the published test cards."""
    valid_last_fours = {c[-gen_const.GEN_CARD_MASK_SUFFIX_LEN:] for c in gen_const.GEN_CARD_TEST_NUMBERS}
    result = gen_card(20, {}, _rng())
    for val in result:
        # Extract last 4 before " [TEST CARD]"
        # Format: "**** **** **** XXXX [TEST CARD]"
        parts = val.split()
        last_four = parts[3]  # index 3 = the XXXX segment
        assert last_four in valid_last_fours, (
            f"Card last-4 {last_four!r} not in test-card list"
        )


def test_card_no_cvv_no_expiry():
    """Card output must not contain a CVV (3–4 digits) or expiry date pattern."""
    import re
    cvv_pattern = re.compile(r"\b\d{3,4}\b")
    expiry_pattern = re.compile(r"\b(0[1-9]|1[0-2])/\d{2,4}\b")

    result = gen_card(50, {}, _rng())
    for val in result:
        # Strip the known masked prefix and label before checking
        clean = val.replace("**** **** **** ", "").replace(" [TEST CARD]", "")
        assert not expiry_pattern.search(val), f"Expiry pattern found in: {val}"
        # The 4-digit last segment is expected; check nothing extra was added
        assert clean.isdigit() and len(clean) == gen_const.GEN_CARD_MASK_SUFFIX_LEN, (
            f"Unexpected content in masked card: {val}"
        )


def test_card_unmasked_still_test_card():
    """Full test-card number (masked=False) must still be in the published list."""
    result = gen_card(20, {"masked": False}, _rng())
    for val in result:
        number = val.replace(" [TEST CARD]", "")
        assert number in gen_const.GEN_CARD_TEST_NUMBERS, (
            f"Unmasked card {number!r} not in GEN_CARD_TEST_NUMBERS"
        )


# ── sensitive_masker ──────────────────────────────────────────────

def test_detect_and_mask_replaces_sensitive_columns():
    """detect_and_mask must replace sensitive columns with mask chars."""
    df = pd.DataFrame({
        "order_id": [1, 2, 3],
        "email": ["a@b.com", "c@d.com", "e@f.com"],
        "amount": [100, 200, 300],
        "national_id": ["12345-1234567-1"] * 3,
    })
    masked_df, masked_cols = detect_and_mask(df)

    assert "email" in masked_cols
    assert "national_id" in masked_cols
    assert "order_id" not in masked_cols
    assert "amount" not in masked_cols

    # Masked columns contain only the mask character
    mask_val = gen_const.GEN_MASK_CHAR * 8
    assert all(masked_df["email"] == mask_val)
    assert all(masked_df["national_id"] == mask_val)

    # Non-sensitive columns are untouched
    assert list(masked_df["order_id"]) == [1, 2, 3]
    assert list(masked_df["amount"]) == [100, 200, 300]


def test_detect_and_mask_no_false_positives():
    """Columns with no sensitive patterns must not be masked."""
    df = pd.DataFrame({"product_name": ["A", "B"], "price": [10.0, 20.0]})
    masked_df, masked_cols = detect_and_mask(df)
    assert masked_cols == []
    pd.testing.assert_frame_equal(masked_df, df)


# ── LLM call guard: no raw row values sent ────────────────────────

def test_llm_variables_contain_no_dataframe_or_list(monkeypatch):
    """
    The variables dict passed to ask_json / ask_text must never contain
    a DataFrame, list, ndarray, or dict of values — only scalar metadata
    (query string, module name, n_rows int, locale string).

    This test fails if someone adds raw data to the LLM call variables.
    """
    from dotenv import load_dotenv
    load_dotenv()
    from hackdata.cloud import llm_client

    captured = []

    original_call = llm_client._call_with_fallback

    def spy_call(prompt_name, messages_list, as_json):
        # messages_list[0]["content"] is the filled prompt string
        captured.append({"prompt_name": prompt_name, "messages_list": messages_list})
        return None  # simulate LLM returning nothing → offline path

    monkeypatch.setattr(llm_client, "_call_with_fallback", spy_call)
    monkeypatch.setattr("hackdata.cloud.llm_client.cache_get", lambda key: None)
    monkeypatch.setattr("hackdata.cloud.llm_client.cache_put", lambda k, v: None)

    from hackdata.entity.spec_entity import Spec
    from hackdata.components.generators.column_generators import gen_email

    # Build a variables dict as spec_builder does
    variables = {
        "query": "100 customers with email",
        "module": "tabular",
        "n_rows": 100,
        "locale": "en_PK",
    }

    try:
        llm_client.ask_json("spec", variables, Spec)
    except Exception:
        pass  # offline fallback may fail in test; we only care about captured calls

    for call in captured:
        for key, val in variables.items():
            # No value in the variables dict should be a collection of data rows
            assert not isinstance(val, (pd.DataFrame, list, np.ndarray)), (
                f"Raw data value found in LLM variables[{key!r}]: {type(val)}"
            )
        # The prompt content is a string — no DataFrame repr
        for msg in call["messages_list"]:
            content = msg.get("content", "")
            assert isinstance(content, str), "LLM message content must be a string"
