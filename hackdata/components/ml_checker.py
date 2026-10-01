# ═══════════════════════════════════════════════════════════════════
# ml_checker.py — quick ML check for ML Lab (Step C)
# ═══════════════════════════════════════════════════════════════════
# Trains a simple scikit-learn model on the train split, scores on
# the test split, and returns the result dict.  No external API is
# called; all computation is local.
# ═══════════════════════════════════════════════════════════════════
import sys
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import roc_auc_score, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder
from sklearn.impute import SimpleImputer
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from hackdata.constants import ml_lab as ml_const, messages as msg_const
from hackdata.exception.exception import HackDataException
from hackdata.logging.logger import logging


def _build_preprocessor(X: pd.DataFrame):
    """Build a ColumnTransformer that imputes + encodes numeric and categorical cols."""
    numeric_cols = X.select_dtypes(include="number").columns.tolist()
    cat_cols = [c for c in X.columns if c not in numeric_cols]

    # High-cardinality categoricals: label-encode instead of OHE to stay lean
    ohe_cols = [c for c in cat_cols if X[c].nunique() <= ml_const.ML_CHECKER_MAX_ONEHOT_CATS]
    le_cols  = [c for c in cat_cols if c not in ohe_cols]

    transformers = []
    if numeric_cols:
        transformers.append(("num", SimpleImputer(strategy="median"), numeric_cols))
    if ohe_cols:
        transformers.append((
            "ohe",
            Pipeline([
                ("imp", SimpleImputer(strategy="most_frequent")),
                ("enc", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
            ]),
            ohe_cols,
        ))
    if le_cols:
        # Label-encode by filling missing with "__missing__" then converting to codes
        for col in le_cols:
            X[col] = X[col].fillna("__missing__").astype(str)
        transformers.append(("le_passthru", "passthrough", le_cols))

    if not transformers:
        # All columns dropped somehow — return identity transformer
        return None

    return ColumnTransformer(transformers=transformers, remainder="drop")


def run_ml_check(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    target_col: str,
    task_type: str,
    seed: int,
    label: str = "synthetic",
) -> Dict[str, Any]:
    """Train a small model on train_df, score on test_df.

    Parameters
    ----------
    train_df   : training data (includes target_col)
    test_df    : test / hold-out data (includes target_col)
    target_col : column to predict
    task_type  : 'classification' | 'regression'
    seed       : random seed for model reproducibility
    label      : tag describing the data source (shown in results)

    Returns
    -------
    dict with keys: score, baseline, gap, metric, task_type, label, warning
    """
    result: Dict[str, Any] = {
        "task_type": task_type,
        "label": label,
        "score": None,
        "baseline": None,
        "gap": None,
        "metric": "AUC" if task_type == "classification" else "R²",
        "warning": None,
    }

    try:
        if len(train_df) < ml_const.ML_CHECKER_MIN_ROWS or len(test_df) < 2:
            result["warning"] = msg_const.MSG_ML_TOO_FEW_ROWS.format(n=len(train_df))
            return result

        feature_cols = [c for c in train_df.columns if c != target_col]
        if not feature_cols:
            result["warning"] = "No feature columns available."
            return result

        X_train = train_df[feature_cols].copy()
        X_test  = test_df[feature_cols].copy()
        y_train = train_df[target_col].copy()
        y_test  = test_df[target_col].copy()

        if task_type == "classification":
            # Encode labels to integers
            le = LabelEncoder()
            y_train_enc = le.fit_transform(y_train.astype(str).fillna("__missing__"))
            y_test_enc  = le.transform(
                y_test.astype(str).fillna("__missing__").apply(
                    lambda v: v if v in le.classes_ else le.classes_[0]
                )
            )

            n_classes = len(le.classes_)
            if n_classes < 2:
                result["warning"] = msg_const.MSG_ML_SINGLE_CLASS
                return result

            preprocessor = _build_preprocessor(X_train)
            model = RandomForestClassifier(
                n_estimators=ml_const.ML_CHECKER_RF_N_ESTIMATORS,
                max_depth=ml_const.ML_CHECKER_RF_MAX_DEPTH,
                n_jobs=ml_const.ML_CHECKER_N_JOBS,
                random_state=seed,
            )

            if preprocessor:
                pipe = Pipeline([("prep", preprocessor), ("model", model)])
            else:
                pipe = Pipeline([("model", model)])

            pipe.fit(X_train, y_train_enc)

            # AUC: binary → predict_proba[:,1]; multi-class → OVR macro
            if n_classes == 2:
                proba = pipe.predict_proba(X_test)[:, 1]
                score = float(roc_auc_score(y_test_enc, proba))
            else:
                proba = pipe.predict_proba(X_test)
                score = float(roc_auc_score(y_test_enc, proba, multi_class="ovr", average="macro"))

            # Baseline: majority-class AUC (predict always majority)
            majority = int(np.bincount(y_train_enc).argmax())
            baseline_pred = np.zeros((len(y_test_enc), n_classes))
            baseline_pred[:, majority] = 1.0
            if n_classes == 2:
                baseline = float(roc_auc_score(y_test_enc, baseline_pred[:, 1]))
            else:
                baseline = float(roc_auc_score(y_test_enc, baseline_pred, multi_class="ovr", average="macro"))

        else:  # regression
            y_train_num = pd.to_numeric(y_train, errors="coerce").fillna(0)
            y_test_num  = pd.to_numeric(y_test, errors="coerce").fillna(0)

            preprocessor = _build_preprocessor(X_train)
            model_r = RandomForestRegressor(
                n_estimators=ml_const.ML_CHECKER_RF_N_ESTIMATORS,
                max_depth=ml_const.ML_CHECKER_RF_MAX_DEPTH,
                n_jobs=ml_const.ML_CHECKER_N_JOBS,
                random_state=seed,
            )

            if preprocessor:
                pipe = Pipeline([("prep", preprocessor), ("model", model_r)])
            else:
                pipe = Pipeline([("model", model_r)])

            pipe.fit(X_train, y_train_num)
            preds = pipe.predict(X_test)
            score = float(r2_score(y_test_num, preds))

            # Baseline: predict mean of train target
            baseline_pred_r = np.full(len(y_test_num), float(y_train_num.mean()))
            baseline = float(r2_score(y_test_num, baseline_pred_r))

        result["score"]    = round(score, 4)
        result["baseline"] = round(baseline, 4)
        result["gap"]      = round(score - baseline, 4)

    except Exception as e:
        result["warning"] = f"ML check failed: {e}"
        logging.info(f"ml_checker: {e}")

    return result
