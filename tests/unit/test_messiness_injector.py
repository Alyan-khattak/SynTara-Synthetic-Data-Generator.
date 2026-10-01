# ═══════════════════════════════════════════════════════════════════
# test_messiness_injector.py — unit tests for messiness_injector
# ═══════════════════════════════════════════════════════════════════
import numpy as np
import pandas as pd
import pytest

from hackdata.components.messiness_injector import apply_messiness
from hackdata.constants import generation as gen_const
from hackdata.entity.spec_entity import Spec, TableSpec, ColumnSpec, ParentSpec, Cardinality


def _make_df(n=200):
    """Build a simple DataFrame for testing."""
    return pd.DataFrame({
        "id": range(1, n + 1),
        "val": np.arange(n, dtype=float),
        "cat": np.resize(["A", "B", "C"], n),
        "fk": np.random.randint(1, 11, n),
    })


def _spec_with_nulls(null_rate=0.10):
    return Spec(module="tabular", tables=[TableSpec(name="t", n_rows=200, columns=[
        ColumnSpec(name="id", gen="sequence", rules=["unique", "not_null"]),
        ColumnSpec(name="val", gen="int_range", null_rate=null_rate),
        ColumnSpec(name="cat", gen="categorical", values=["A", "B", "C"]),
        ColumnSpec(name="fk", gen="int_range"),
    ])])


# ── null rate within tolerance ────────────────────────────────────

def test_null_rate_within_tolerance():
    spec = _spec_with_nulls(null_rate=0.15)
    out = apply_messiness({"t": _make_df()}, spec, master_seed=42)
    null_frac = out["t"]["val"].isnull().mean()
    assert 0.05 <= null_frac <= 0.30, f"null_rate out of tolerance: {null_frac:.2f}"


# ── PK column never touched ───────────────────────────────────────

def test_pk_col_never_nulled():
    spec = Spec(module="tabular", tables=[TableSpec(name="t", n_rows=200, columns=[
        ColumnSpec(name="id", gen="sequence", rules=["unique", "not_null"], null_rate=0.50),
        ColumnSpec(name="val", gen="int_range"),
    ])])
    out = apply_messiness({"t": _make_df()}, spec, master_seed=42)
    assert out["t"]["id"].isnull().sum() == 0


# ── FK column never touched ───────────────────────────────────────

def test_fk_col_never_touched():
    child = TableSpec(name="child", n_rows=100, columns=[
        ColumnSpec(name="child_id", gen="sequence", rules=["unique", "not_null"]),
        ColumnSpec(name="parent_id", gen="int_range", null_rate=0.50),
    ], parent=ParentSpec(table="parent", key="parent_id",
                         cardinality=Cardinality(min_per_parent=1, max_per_parent=5)))
    spec = Spec(module="relational", tables=[
        TableSpec(name="parent", n_rows=20, columns=[
            ColumnSpec(name="parent_id", gen="sequence", rules=["unique", "not_null"]),
        ]),
        child,
    ])
    df_child = pd.DataFrame({"child_id": range(1, 101), "parent_id": range(1, 101)})
    df_parent = pd.DataFrame({"parent_id": range(1, 21)})
    out = apply_messiness({"parent": df_parent, "child": df_child}, spec, master_seed=7)
    # parent_id is FK → never touched
    assert out["child"]["parent_id"].isnull().sum() == 0


# ── same seed gives identical results ────────────────────────────

def test_reproducibility():
    spec = _spec_with_nulls(null_rate=0.10)
    df = _make_df()
    out1 = apply_messiness({"t": df.copy()}, spec, master_seed=99)
    out2 = apply_messiness({"t": df.copy()}, spec, master_seed=99)
    assert out1["t"]["val"].equals(out2["t"]["val"])


# ── rate above cap is rejected ────────────────────────────────────

def test_rate_above_cap_rejected():
    spec = Spec(module="tabular", tables=[TableSpec(name="t", n_rows=10, columns=[
        ColumnSpec(name="x", gen="int_range", null_rate=gen_const.GEN_MAX_MISSING_RATE + 0.01),
    ])])
    with pytest.raises(ValueError, match="null_rate"):
        apply_messiness({"t": pd.DataFrame({"x": range(10)})}, spec, master_seed=1)


def test_outlier_rate_above_cap_rejected():
    spec = Spec(module="tabular", tables=[TableSpec(name="t", n_rows=10, columns=[
        ColumnSpec(name="x", gen="int_range", outlier_rate=gen_const.GEN_MAX_OUTLIER_RATE + 0.01),
    ])])
    with pytest.raises(ValueError, match="outlier_rate"):
        apply_messiness({"t": pd.DataFrame({"x": range(10)})}, spec, master_seed=1)
