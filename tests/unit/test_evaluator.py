# ═══════════════════════════════════════════════════════════════════
# test_evaluator.py — Unit Tests for DataEvaluator & Privacy Leak Detection
# ═══════════════════════════════════════════════════════════════════
# Implements T-049: Tests metrics vs reference, leak test (perfect copy flagged)
# ═══════════════════════════════════════════════════════════════════

import pytest
import pandas as pd
import numpy as np
from hackdata.components.evaluator import DataEvaluator
from hackdata.components.scorecard import ScorecardAggregator

@pytest.fixture
def sample_data():
    np.random.seed(42)
    train_df = pd.DataFrame({
        "age": np.random.randint(18, 65, size=100),
        "income": np.random.normal(50000, 15000, size=100),
        "label": np.random.choice(["A", "B"], size=100)
    })
    holdout_df = pd.DataFrame({
        "age": np.random.randint(18, 65, size=100),
        "income": np.random.normal(50000, 15000, size=100),
        "label": np.random.choice(["A", "B"], size=100)
    })
    synthetic_df = pd.DataFrame({
        "age": np.random.randint(18, 65, size=100),
        "income": np.random.normal(50000, 15000, size=100),
        "label": np.random.choice(["A", "B"], size=100)
    })
    return train_df, holdout_df, synthetic_df

def test_fidelity_metrics(sample_data):
    train_df, holdout_df, synthetic_df = sample_data
    evaluator = DataEvaluator(train_df, holdout_df, synthetic_df)
    score, details = evaluator.compute_fidelity()
    assert 0.0 <= score <= 100.0
    assert "ks_score" in details
    assert details["numeric_columns_evaluated"] == 2

def test_utility_metrics(sample_data):
    train_df, holdout_df, synthetic_df = sample_data
    evaluator = DataEvaluator(train_df, holdout_df, synthetic_df)
    score, details = evaluator.compute_utility()
    assert 0.0 <= score <= 100.0
    assert "tstr_score" in details

def test_privacy_leak_detection(sample_data):
    """Verifies that a perfect copy of training data triggers privacy flag and low score."""
    train_df, holdout_df, _ = sample_data
    # Synthetic data is an exact duplicate of training set
    perfect_copy_synth = train_df.copy()
    
    evaluator = DataEvaluator(train_df, holdout_df, perfect_copy_synth)
    score, details = evaluator.compute_privacy()
    
    # Perfect copy must result in 0.0 privacy score and privacy_flag True
    assert score == 0.0
    assert details["exact_match_count"] == len(train_df)
    assert details["privacy_flag"] is True

def test_scorecard_aggregation(tmp_path, monkeypatch):
    import hackdata.constants.paths as paths
    monkeypatch.setattr(paths, "ARTIFACTS_TEMP_DIR", str(tmp_path))
    
    agg = ScorecardAggregator(run_id="test_run_123")
    card = agg.calculate_scorecard(
        validity_score=100.0,
        fidelity_score=80.0,
        utility_score=70.0,
        privacy_score=90.0
    )
    
    # 0.25*100 + 0.25*80 + 0.30*70 + 0.20*90 = 25 + 20 + 21 + 18 = 84.0
    assert card["overall_score"] == 84.0
    assert card["validity"] == 100.0
    assert card["fidelity"] == 80.0
    assert card["utility"] == 70.0
    assert card["privacy"] == 90.0
