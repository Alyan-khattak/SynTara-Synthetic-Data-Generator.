# ═══════════════════════════════════════════════════════════════════
# messiness_injector.py — apply null, outlier, and class-imbalance
#                         settings AFTER generation
# ═══════════════════════════════════════════════════════════════════
# IMP: applied post-generation so structural integrity (PK/FK) is
#      preserved.  Never touches PK or FK columns.
# IMP: every draw uses a seed derived from master_seed so runs are
#      reproducible — same spec + seed → same messiness.
###==============================================================
import sys
from typing import Dict, Optional

import numpy as np
import pandas as pd

from hackdata.constants import generation as gen_const, messages as msg_const
from hackdata.entity.spec_entity import Spec, ColumnSpec
from hackdata.exception.exception import HackDataException
from hackdata.logging.logger import logging
from hackdata.utils.main_utils.seed_utils import derive_seed


# ── helpers ──────────────────────────────────────────────────────

def _pk_fk_col_names(spec: Spec) -> set:
    """Return the union of all PK and FK column names across tables.

    IMP: we never corrupt a PK/FK — it breaks referential integrity.
    """
    protected: set = set()
    for table in spec.tables:
        for col in table.columns:
            # PK inference: same logic as er_diagram._is_pk
            if col.gen in ("sequence", "uuid"):
                protected.add(col.name)
            if "unique" in col.rules and "not_null" in col.rules:
                protected.add(col.name)
        if table.parent:
            protected.add(table.parent.key)
    return protected


def _validate_rates(spec: Spec) -> None:
    """Raise ValueError for any rate that exceeds its cap.

    Checked here rather than in the Pydantic validator so the cap
    constant is a single source of truth in generation.py.
    """
    for table in spec.tables:
        for col in table.columns:
            if col.null_rate is not None and col.null_rate > gen_const.GEN_MAX_MISSING_RATE:
                raise ValueError(
                    msg_const.MSG_MESSINESS_RATE_TOO_HIGH.format(
                        rate=col.null_rate,
                        max_rate=gen_const.GEN_MAX_MISSING_RATE,
                        setting="null_rate",
                    )
                )
            if col.outlier_rate is not None and col.outlier_rate > gen_const.GEN_MAX_OUTLIER_RATE:
                raise ValueError(
                    msg_const.MSG_MESSINESS_RATE_TOO_HIGH.format(
                        rate=col.outlier_rate,
                        max_rate=gen_const.GEN_MAX_OUTLIER_RATE,
                        setting="outlier_rate",
                    )
                )
            if col.class_imbalance is not None and col.class_imbalance > gen_const.GEN_MAX_IMBALANCE_RATE:
                raise ValueError(
                    msg_const.MSG_MESSINESS_RATE_TOO_HIGH.format(
                        rate=col.class_imbalance,
                        max_rate=gen_const.GEN_MAX_IMBALANCE_RATE,
                        setting="class_imbalance",
                    )
                )


def _apply_null_rate(series: pd.Series, rate: float, rng: np.random.Generator) -> pd.Series:
    """Randomly set `rate` fraction of values to None."""
    if rate <= 0:
        return series
    s = series.copy()
    mask = rng.random(len(s)) < rate
    s[mask] = None
    return s


def _apply_outlier_rate(series: pd.Series, rate: float, rng: np.random.Generator) -> pd.Series:
    """Inject outliers at mean ± GEN_OUTLIER_SIGMA * std into `rate` fraction of rows.

    DRY RUN: mean=100, std=10, sigma=3.5, rate=0.05
        → 5% of rows get value ~135 or ~65 (alternating sign)
    """
    if rate <= 0:
        return series
    # only applies to numeric columns
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.isnull().all():
        return series
    s = series.copy()
    mean = numeric.dropna().mean()
    std = numeric.dropna().std()
    if pd.isna(std) or std == 0:
        return series
    n_outliers = max(1, int(rate * len(s)))
    indices = rng.choice(len(s), size=n_outliers, replace=False)
    signs = rng.choice([-1, 1], size=n_outliers)
    for idx, sign in zip(indices, signs):
        s.iloc[idx] = mean + sign * gen_const.GEN_OUTLIER_SIGMA * std
    return s


def _apply_class_imbalance(series: pd.Series, dominant_fraction: float, rng: np.random.Generator) -> pd.Series:
    """Make one class dominate by resampling `dominant_fraction` of rows to the most common value.

    DRY RUN: values=[A,B,C,A,B], dominant_fraction=0.80, n=5
        → most_common=A; 4 rows set to A, 1 row unchanged.
    """
    if dominant_fraction <= 0:
        return series
    s = series.copy()
    if len(s) == 0:
        return s
    mode_vals = s.mode()
    if len(mode_vals) == 0:
        return s
    dominant = mode_vals.iloc[0]
    n_dominant = int(dominant_fraction * len(s))
    all_indices = rng.permutation(len(s))
    for idx in all_indices[:n_dominant]:
        s.iloc[idx] = dominant
    return s


# ── public entry point ─────────────────────────────────────────────

def apply_messiness(
    tables: Dict[str, pd.DataFrame],
    spec: Spec,
    master_seed: int,
) -> Dict[str, pd.DataFrame]:
    """Apply null_rate, outlier_rate, and class_imbalance after generation.

    Parameters
    ----------
    tables      : {table_name: DataFrame} from the generator
    spec        : validated Spec (column settings read from here)
    master_seed : run-level seed for reproducibility

    Returns
    -------
    dict of modified DataFrames (copies — originals not mutated)

    Notes
    -----
    PK/FK columns are never touched.
    """
    try:
        logging.info("MessinessInjector: applying messiness settings")
        _validate_rates(spec)

        protected = _pk_fk_col_names(spec)
        result: Dict[str, pd.DataFrame] = {}

        for table_spec in spec.tables:
            df = tables.get(table_spec.name)
            if df is None:
                result[table_spec.name] = df
                continue
            df = df.copy()

            for col_spec in table_spec.columns:
                col = col_spec.name
                if col not in df.columns:
                    continue
                if col in protected:
                    continue  # IMP: never touch PK/FK

                # Derive a per-column seed for reproducibility
                col_seed = derive_seed(master_seed, table_spec.name, col, "messiness")
                rng = np.random.default_rng(col_seed)

                if col_spec.null_rate and col_spec.null_rate > 0:
                    df[col] = _apply_null_rate(df[col], col_spec.null_rate, rng)

                if col_spec.outlier_rate and col_spec.outlier_rate > 0:
                    df[col] = _apply_outlier_rate(df[col], col_spec.outlier_rate, rng)

                if col_spec.class_imbalance and col_spec.class_imbalance > 0:
                    df[col] = _apply_class_imbalance(df[col], col_spec.class_imbalance, rng)

            result[table_spec.name] = df

        logging.info("MessinessInjector: done")
        return result

    except ValueError:
        raise
    except Exception as e:
        raise HackDataException(e, sys)


# ---------------- SELF-CHECK ----------------
if __name__ == "__main__":
    import sys as _sys
    from hackdata.entity.spec_entity import (
        Spec, TableSpec, ColumnSpec,
    )

    # Build a simple one-table spec with null_rate and outlier_rate
    t = TableSpec(name="t", n_rows=100, columns=[
        ColumnSpec(name="id", gen="sequence", rules=["unique", "not_null"]),
        ColumnSpec(name="val", gen="int_range", min=0, max=100, null_rate=0.10, outlier_rate=0.05),
        ColumnSpec(name="cat", gen="categorical", values=["A", "B", "C"], class_imbalance=0.80),
    ])
    spec = Spec(module="tabular", tables=[t])
    df = pd.DataFrame({
        "id": range(1, 101),
        "val": np.arange(100),
        "cat": np.random.choice(["A", "B", "C"], 100),
    })
    tables = {"t": df}

    out = apply_messiness(tables, spec, master_seed=42)
    df_out = out["t"]

    # null_rate ~10%
    null_frac = df_out["val"].isnull().mean()
    assert 0.03 <= null_frac <= 0.20, f"null_rate out of tolerance: {null_frac}"
    print(f"null_rate fraction: {null_frac:.2f}  ✓")

    # PK (id) never touched
    assert df_out["id"].isnull().sum() == 0, "PK should never be nulled"
    print("PK not touched  ✓")

    # same seed → identical results
    out2 = apply_messiness(tables, spec, master_seed=42)
    assert out2["t"]["val"].equals(df_out["val"]), "Reproducibility failed"
    print("Same seed → same result  ✓")

    # rate above cap raises
    t_bad = TableSpec(name="t", n_rows=10, columns=[
        ColumnSpec(name="x", gen="int_range", null_rate=0.99),
    ])
    spec_bad = Spec(module="tabular", tables=[t_bad])
    try:
        apply_messiness({"t": pd.DataFrame({"x": range(10)})}, spec_bad, 42)
        print("ERROR: should have raised")
        _sys.exit(1)
    except ValueError as e:
        print("Correctly rejected rate > cap:", str(e)[:80])

    print("Self-check passed.")
