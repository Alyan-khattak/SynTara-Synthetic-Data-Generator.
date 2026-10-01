# ═══════════════════════════════════════════════════════════════════
# test_ml_lab.py — unit + API tests for ML Lab module
# ═══════════════════════════════════════════════════════════════════
import os
import tempfile

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_csv(path: str, n: int = 200, seed: int = 0) -> None:
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({
        "id":     range(1, n + 1),
        "amount": rng.normal(100, 15, n).round(2),
        "score":  rng.integers(1, 10, n).astype(float),
        "cat":    rng.choice(["A", "B", "C"], n),
    })
    df.to_csv(path, index=False)


# ── ml_checker unit tests ─────────────────────────────────────────────────────

def test_ml_checker_classification_high_signal():
    """High signal strength → model should clearly beat baseline."""
    from hackdata.components.ml_checker import run_ml_check

    rng = np.random.default_rng(7)
    n = 300
    x = rng.normal(0, 1, n)
    # Perfect binary signal from x
    y = (x > 0).astype(int)
    df = pd.DataFrame({"x": x, "label": y})
    train, test = df.iloc[:240], df.iloc[240:]
    res = run_ml_check(train, test, "label", "classification", seed=42)
    assert res["score"] is not None
    assert res["score"] > 0.8, f"Expected high AUC, got {res['score']}"
    assert res["gap"] is not None and res["gap"] > 0


def test_ml_checker_regression_r2():
    """Linear target → R² should be positive."""
    from hackdata.components.ml_checker import run_ml_check

    rng = np.random.default_rng(3)
    n = 200
    x = rng.normal(5, 2, n)
    y = 3 * x + rng.normal(0, 0.1, n)
    df = pd.DataFrame({"x": x, "y": y})
    train, test = df.iloc[:160], df.iloc[160:]
    res = run_ml_check(train, test, "y", "regression", seed=42)
    assert res["score"] is not None
    assert res["score"] > 0.5


def test_ml_checker_single_class_returns_warning():
    """Single-class target: checker must not crash, must return warning."""
    from hackdata.components.ml_checker import run_ml_check

    df = pd.DataFrame({"x": range(50), "label": [0] * 50})
    train, test = df.iloc[:40], df.iloc[40:]
    res = run_ml_check(train, test, "label", "classification", seed=0)
    assert res["warning"] is not None


def test_ml_checker_too_few_rows():
    """Too few rows: warning returned, no crash."""
    from hackdata.components.ml_checker import run_ml_check

    df = pd.DataFrame({"x": [1, 2], "y": [0, 1]})
    res = run_ml_check(df, df, "y", "classification", seed=0)
    assert res["warning"] is not None


# ── pipeline unit tests ───────────────────────────────────────────────────────

def test_ml_lab_invalid_task_type():
    from hackdata.pipeline.ml_lab_pipeline import MLLabPipeline
    with pytest.raises(ValueError, match="task_type"):
        MLLabPipeline(source_type="describe", target_col="t", task_type="unknown", query="x")


def test_ml_lab_invalid_signal():
    from hackdata.pipeline.ml_lab_pipeline import MLLabPipeline
    with pytest.raises(ValueError, match="signal_strength"):
        MLLabPipeline(source_type="describe", target_col="t", task_type="classification",
                      query="x", signal_strength=1.5)


def test_ml_lab_rows_too_low():
    from hackdata.pipeline.ml_lab_pipeline import MLLabPipeline
    with pytest.raises(ValueError, match="n_rows"):
        MLLabPipeline(source_type="describe", target_col="t", task_type="classification",
                      query="x", n_rows=5)


def test_ml_lab_describe_no_query():
    from hackdata.pipeline.ml_lab_pipeline import MLLabPipeline
    with pytest.raises(ValueError, match="query"):
        MLLabPipeline(source_type="describe", target_col="t", task_type="classification")


def test_ml_lab_same_seed_identical():
    """Same seed → identical train CSV rows."""
    from hackdata.pipeline.ml_lab_pipeline import MLLabPipeline

    with tempfile.TemporaryDirectory() as tmp:
        csv = os.path.join(tmp, "d.csv")
        _make_csv(csv, n=100)

        # Upload source: read the CSV directly
        # (we bypass the full upload endpoint by pointing at the temp CSV)
        # Actually we need to test describe source to stay self-contained:
        # Use signal=0 so randomness is dominated by copula + seeded noise
        kwargs = dict(
            source_type="upload",
            upload_run_id="__test__",   # will fail at _find_source_csv
            target_col="cat",
            task_type="classification",
            seed=55,
        )
        # Can't run upload without a real run dir, so test the planting logic only
        # by calling _plant_target on a fixed DataFrame:
        p = MLLabPipeline(
            source_type="describe",
            query="placeholder",  # won't actually be called
            target_col="cat",
            task_type="classification",
            seed=55,
        )
        df = pd.DataFrame({"a": range(100), "b": np.arange(100, 200)})
        df1 = p._plant_target(df.copy())

        p2 = MLLabPipeline(
            source_type="describe",
            query="placeholder",
            target_col="cat",
            task_type="classification",
            seed=55,
        )
        df2 = p2._plant_target(df.copy())
        pd.testing.assert_series_equal(df1["cat"], df2["cat"])


# ── API route tests ───────────────────────────────────────────────────────────

def test_ml_api_invalid_task_type():
    """POST /api/ml/generate with unknown task_type → 400."""
    res = client.post("/api/ml/generate", json={
        "source_type": "describe",
        "query": "50 employees",
        "target_col": "income",
        "task_type": "segmentation",   # invalid
    })
    assert res.status_code == 400


def test_ml_api_invalid_signal():
    """signal_strength > 1 → 400."""
    res = client.post("/api/ml/generate", json={
        "source_type": "describe",
        "query": "50 employees",
        "target_col": "income",
        "task_type": "regression",
        "signal_strength": 2.0,
    })
    assert res.status_code == 400


def test_ml_api_missing_query_for_describe():
    """describe source without query → 400."""
    res = client.post("/api/ml/generate", json={
        "source_type": "describe",
        "target_col": "label",
        "task_type": "classification",
    })
    assert res.status_code == 400


def test_ml_api_unknown_upload_run():
    """upload source with nonexistent run_id → 400 or 500 (not 200)."""
    res = client.post("/api/ml/generate", json={
        "source_type": "upload",
        "upload_run_id": "nonexistent_run_abc123",
        "target_col": "label",
        "task_type": "classification",
    })
    assert res.status_code in (400, 500)


def test_ml_api_ml_check_not_found():
    """GET /api/runs/bad_id/ml-check → 404."""
    res = client.get("/api/runs/nonexistent_run_xyz/ml-check")
    assert res.status_code == 404
