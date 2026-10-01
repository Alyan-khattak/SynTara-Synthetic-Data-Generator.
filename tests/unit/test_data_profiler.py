# ═══════════════════════════════════════════════════════════════════
# test_data_profiler.py — unit tests for data_profiler component
# ═══════════════════════════════════════════════════════════════════
import math

import numpy as np
import pandas as pd
import pytest
from scipy.stats import pearsonr, spearmanr

from hackdata.components.data_profiler import (
    _cramers_v,
    _eta_squared,
    _pearson,
    _spearman,
    profile_dataframe,
)


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_df():
    """Small deterministic DataFrame with numeric, categorical and id-like cols."""
    rng = np.random.default_rng(42)
    n = 100
    x = rng.normal(10, 2, n)
    y = 2 * x + rng.normal(0, 0.5, n)   # strongly correlated with x
    cat = np.where(x > 10, "high", "low")
    return pd.DataFrame({"id": range(1, n + 1), "x": x, "y": y, "cat": cat})


# ── Pearson / Spearman ───────────────────────────────────────────────────────

def test_pearson_known():
    df = _make_df()
    got = _pearson(df["x"], df["y"])
    expected, _ = pearsonr(df["x"], df["y"])
    assert got is not None
    assert abs(got - round(float(expected), 4)) <= 1e-3


def test_spearman_known():
    df = _make_df()
    got = _spearman(df["x"], df["y"])
    expected, _ = spearmanr(df["x"], df["y"])
    assert got is not None
    assert abs(got - round(float(expected), 4)) <= 1e-3


def test_pearson_too_few_rows_returns_none():
    s = pd.Series([1.0, 2.0])
    assert _pearson(s, s) is None


# ── Cramér's V ───────────────────────────────────────────────────────────────

def test_cramers_v_identical_cols():
    s = pd.Series(["a", "b", "a", "b", "a"] * 10)
    v = _cramers_v(s, s)
    # identical → V should be close to 1
    assert v is not None
    assert v > 0.99


def test_cramers_v_independent():
    rng = np.random.default_rng(0)
    a = pd.Series(rng.choice(["x", "y", "z"], 200))
    b = pd.Series(rng.choice(["p", "q"], 200))
    v = _cramers_v(a, b)
    assert v is not None
    assert v < 0.3   # should be low for random data


def test_cramers_v_too_few_returns_none():
    s = pd.Series(["a", "b"])
    assert _cramers_v(s, s) is None


# ── η² (eta squared) ─────────────────────────────────────────────────────────

def test_eta_squared_perfect_split():
    # Group "a" always 0, group "b" always 10 → η² should be near 1
    num = pd.Series([0.0] * 50 + [10.0] * 50)
    cat = pd.Series(["a"] * 50 + ["b"] * 50)
    eta = _eta_squared(num, cat)
    assert eta is not None
    assert eta > 0.99


def test_eta_squared_no_relationship():
    rng = np.random.default_rng(1)
    num = pd.Series(rng.normal(5, 1, 200))
    cat = pd.Series(rng.choice(["x", "y"], 200))
    eta = _eta_squared(num, cat)
    assert eta is not None
    assert eta < 0.2


def test_eta_squared_constant_numeric_returns_none():
    num = pd.Series([5.0] * 50)
    cat = pd.Series(["a"] * 25 + ["b"] * 25)
    assert _eta_squared(num, cat) is None


# ── profile_dataframe ────────────────────────────────────────────────────────

def test_profile_structure():
    df = _make_df()
    p = profile_dataframe(df, label="original")
    assert p["label"] == "original"
    assert p["n_rows"] == 100
    assert p["n_cols"] == 4
    assert isinstance(p["profiles"], list)
    assert len(p["profiles"]) == 4
    assert isinstance(p["matrix"], list)
    assert isinstance(p["findings"], list)
    assert "columns" in p
    assert "relationships" in p


def test_profile_constant_col_does_not_crash():
    df = pd.DataFrame({"a": [1] * 50, "b": [1.0] * 50, "c": range(50)})
    p = profile_dataframe(df)
    assert p["n_rows"] == 50


def test_profile_all_missing_col_does_not_crash():
    df = pd.DataFrame({"x": [None] * 30, "y": range(30)})
    p = profile_dataframe(df)
    assert p["n_rows"] == 30


def test_profile_single_col_no_matrix():
    df = pd.DataFrame({"x": range(20)})
    p = profile_dataframe(df)
    # only 1 non-constant col → no pairwise matrix
    assert p["matrix"] == []
