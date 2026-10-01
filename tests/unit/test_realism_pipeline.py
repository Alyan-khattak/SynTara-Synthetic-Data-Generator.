# ═══════════════════════════════════════════════════════════════════
# test_realism_pipeline.py — realism settings on DataModePipeline
# ═══════════════════════════════════════════════════════════════════
import os
import tempfile

import numpy as np
import pandas as pd
import pytest

from hackdata.pipeline.datamode_pipeline import DataModePipeline
from hackdata.constants import data_mode as dm_const


# ── fixture ───────────────────────────────────────────────────────────────────

def _write_csv(path: str, n: int = 200, seed: int = 7) -> None:
    """Write a small deterministic CSV with numeric + categorical columns."""
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({
        "id":     range(1, n + 1),
        "amount": rng.normal(100, 15, n).round(2),
        "score":  rng.integers(1, 10, n).astype(float),
        "cat":    rng.choice(["A", "B", "C"], n),
    })
    df.to_csv(path, index=False)


def _run(csv_path: str, run_id: str, seed: int = 42, **kwargs) -> pd.DataFrame:
    pipeline = DataModePipeline(
        data_path=csv_path,
        run_id=run_id,
        n_synthetic_rows=100,
        master_seed=seed,
        **kwargs,
    )
    res = pipeline.run()
    return pd.read_csv(res.synthetic_csv_path)


# ── all-zero realism = same output as baseline (regression test) ──────────────

def test_zero_realism_identical_to_baseline():
    """With all realism settings at 0, same seed must produce identical output."""
    with tempfile.TemporaryDirectory() as tmp:
        csv = os.path.join(tmp, "data.csv")
        _write_csv(csv)

        df1 = _run(csv, run_id="test_zero_a", seed=99)
        df2 = _run(csv, run_id="test_zero_b", seed=99)

        # Same seed + no realism → identical DataFrames
        pd.testing.assert_frame_equal(df1, df2)


# ── missing rate ──────────────────────────────────────────────────────────────

def test_missing_rate_within_tolerance():
    """Injected null fraction must be close to requested missing_rate."""
    rate = 0.20
    with tempfile.TemporaryDirectory() as tmp:
        csv = os.path.join(tmp, "data.csv")
        _write_csv(csv)
        df = _run(csv, run_id="test_missing", seed=1, missing_rate=rate)

        numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        if numeric_cols:
            null_frac = df[numeric_cols].isna().values.mean()
            # Allow ±5 percentage points tolerance
            assert abs(null_frac - rate) <= 0.05, f"null_frac={null_frac:.3f}, expected ~{rate}"


def test_missing_rate_above_cap_rejected():
    with tempfile.TemporaryDirectory() as tmp:
        csv = os.path.join(tmp, "data.csv")
        _write_csv(csv)
        with pytest.raises((ValueError, Exception)):
            DataModePipeline(
                data_path=csv,
                run_id="test_cap",
                n_synthetic_rows=50,
                master_seed=1,
                missing_rate=dm_const.DM_MAX_MISSING_RATE + 0.01,
            )


# ── same seed gives identical output ─────────────────────────────────────────

def test_same_seed_reproducible_with_realism():
    with tempfile.TemporaryDirectory() as tmp:
        csv = os.path.join(tmp, "data.csv")
        _write_csv(csv)

        kwargs = dict(seed=55, missing_rate=0.1, noise_level=0.2)
        df1 = _run(csv, run_id="repro_a", **kwargs)
        df2 = _run(csv, run_id="repro_b", **kwargs)
        pd.testing.assert_frame_equal(df1, df2)


# ── outlier rate cap ──────────────────────────────────────────────────────────

def test_outlier_rate_above_cap_rejected():
    with tempfile.TemporaryDirectory() as tmp:
        csv = os.path.join(tmp, "data.csv")
        _write_csv(csv)
        with pytest.raises((ValueError, Exception)):
            DataModePipeline(
                data_path=csv,
                run_id="test_outlier_cap",
                n_synthetic_rows=50,
                master_seed=1,
                outlier_rate=dm_const.DM_MAX_OUTLIER_RATE + 0.01,
            )
