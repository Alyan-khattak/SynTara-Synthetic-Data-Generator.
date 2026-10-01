# ═══════════════════════════════════════════════════════════════════
# evaluator.py — Quantitative Evaluation Metrics (Fidelity, Utility, Privacy)
# ═══════════════════════════════════════════════════════════════════
# Implements T-043 (Fidelity), T-044 (Utility), T-045 (Privacy), T-046 (Baseline)
# ═══════════════════════════════════════════════════════════════════

import os
import sys
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple
from scipy.stats import ks_2samp, spearmanr
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.metrics import f1_score, r2_score
from sklearn.metrics.pairwise import euclidean_distances

from hackdata.constants import evaluation, paths, messages, common
from hackdata.exception.exception import HackDataException
from hackdata.logging.logger import logging
from hackdata.utils.main_utils.dataframe_utils import is_numeric_like

class DataEvaluator:
    """
    Evaluates synthetic data against real training and hold-out sets across:
    1. Fidelity: KS-statistic (numerics), TVD (categoricals), Spearman correlation matrix diff.
    2. Utility: Train-on-Synthetic Test-on-Real (TSTR) via RandomForest.
    3. Privacy: Exact match rate & Distance to Closest Record (DCR) ratio.
    """
    def __init__(self, real_train_df: pd.DataFrame, real_holdout_df: pd.DataFrame, synthetic_df: pd.DataFrame):
        self.real_train = real_train_df.copy()
        self.real_holdout = real_holdout_df.copy()
        self.synthetic = synthetic_df.copy()
        
        # Keep overlapping columns only
        common_cols = [c for c in self.real_train.columns if c in self.synthetic.columns]
        self.real_train = self.real_train[common_cols]
        self.real_holdout = self.real_holdout[common_cols]
        self.synthetic = self.synthetic[common_cols]

    def compute_fidelity(self) -> Tuple[float, Dict[str, Any]]:
        """
        Calculates fidelity score (0-100) using KS test, TVD, and Spearman correlation.
        Weights: KS=0.4, Spearman corr=0.3, TVD=0.3 (defined in constants/evaluation.py).
        """
        try:
            numeric_cols = [c for c in self.real_train.columns if is_numeric_like(self.real_train[c])]
            categorical_cols = [c for c in self.real_train.columns if c not in numeric_cols]

            # ── KS test per numeric column ───────────────────────────────────
            ks_scores = []
            for col in numeric_cols:
                train_vals = pd.to_numeric(self.real_train[col], errors='coerce').dropna()
                synth_vals = pd.to_numeric(self.synthetic[col], errors='coerce').dropna()
                if len(train_vals) > 0 and len(synth_vals) > 0:
                    stat, _ = ks_2samp(train_vals, synth_vals)
                    # 1 - KS statistic scaled to 0-100
                    ks_scores.append(max(0.0, 1.0 - float(stat)) * evaluation.EVAL_SCORE_SCALE)

            avg_ks = float(np.mean(ks_scores)) if ks_scores else evaluation.EVAL_SCORE_SCALE

            # ── Spearman correlation matrix diff (numeric cols only) ──────────
            corr_score = evaluation.EVAL_SCORE_SCALE
            if len(numeric_cols) >= 2:
                train_num = self.real_train[numeric_cols].apply(pd.to_numeric, errors='coerce').fillna(0)
                synth_num = self.synthetic[numeric_cols].apply(pd.to_numeric, errors='coerce').fillna(0)

                train_corr, _ = spearmanr(train_num)
                synth_corr, _ = spearmanr(synth_num)

                if isinstance(train_corr, np.ndarray) and isinstance(synth_corr, np.ndarray):
                    diff = np.abs(train_corr - synth_corr)
                    mean_diff = float(np.nanmean(diff))
                    corr_score = max(0.0, (1.0 - mean_diff) * evaluation.EVAL_SCORE_SCALE)

            # ── TVD per categorical column ────────────────────────────────────
            # TVD = 0.5 * |p - q|.sum(); ranges [0, 1]; lower = more similar.
            # tvd_score maps 0 (identical) → 100, 1 (totally different) → 0.
            tvd_score = evaluation.EVAL_SCORE_SCALE
            if categorical_cols:
                tvd_vals = []
                for col in categorical_cols:
                    p = self.real_train[col].value_counts(normalize=True)
                    q = self.synthetic[col].value_counts(normalize=True)
                    # Align on union of categories; missing category → probability 0
                    p, q = p.align(q, fill_value=0)
                    tvd = 0.5 * float(np.abs(p.values - q.values).sum())
                    tvd_vals.append(tvd)
                # Mean TVD across all categorical columns, then invert to a 0-100 score
                tvd_score = max(0.0, (1.0 - float(np.mean(tvd_vals))) * evaluation.EVAL_SCORE_SCALE)

            overall_fidelity = round(
                evaluation.FIDELITY_KS_WEIGHT * avg_ks
                + evaluation.FIDELITY_CORR_WEIGHT * corr_score
                + evaluation.FIDELITY_TVD_WEIGHT * tvd_score,
                2,
            )

            details = {
                "ks_score": round(avg_ks, 2),
                "correlation_score": round(corr_score, 2),
                "tvd_score": round(tvd_score, 2),
                "numeric_columns_evaluated": len(numeric_cols),
                "categorical_columns_evaluated": len(categorical_cols),
            }
            logging.info(f"DataEvaluator: Fidelity score = {overall_fidelity}")
            return overall_fidelity, details

        except Exception as e:
            raise HackDataException(e, sys)

    def _is_date_col(self, col: str) -> bool:
        """Return True if column looks like a date (name hint or parseable values)."""
        if any(kw in col.lower() for kw in ("date", "time", "created", "updated", "timestamp")):
            return True
        sample = self.real_train[col].dropna().head(5).astype(str)
        import re as _re
        date_pat = _re.compile(r"\d{4}-\d{2}-\d{2}")
        return all(date_pat.search(v) for v in sample) if len(sample) else False

    def _select_target_column(self) -> str:
        """
        Heuristic to pick the best target column for utility evaluation.

        Priority:
          1. First bool-dtype column.
          2. First column whose name contains a known outcome keyword.
          3. Last numeric or low-cardinality categorical column, skipping IDs and dates.
          4. Absolute last non-date column as fallback.
        Returns "" if the table has no columns at all.
        """
        cols = list(self.real_train.columns)
        if not cols:
            return ""

        # 1. Bool columns are almost always binary targets
        bool_cols = [c for c in cols if self.real_train[c].dtype == bool]
        if bool_cols:
            return bool_cols[0]

        # 2. Keyword match (case-insensitive), skip date columns
        for c in cols:
            if any(kw in c.lower() for kw in evaluation.UTILITY_TARGET_KEYWORDS):
                if not self._is_date_col(c):
                    return c

        # 3. Last non-id, non-date column
        non_id_date = [
            c for c in cols
            if not c.lower().endswith("_id") and not self._is_date_col(c)
        ]
        if non_id_date:
            return non_id_date[-1]

        # 4. Last non-date column (even if id-like)
        non_date = [c for c in cols if not self._is_date_col(c)]
        return non_date[-1] if non_date else cols[-1]

    def _fit_predict_rf(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_test: pd.DataFrame,
        y_test: pd.Series,
        is_numeric_target: bool,
    ) -> float:
        """
        Fit a RandomForest and return a 0-100 score (R² for regression, F1 for classification).
        Shared by TSTR and TRTS to avoid code duplication.
        """
        if is_numeric_target:
            y_tr = pd.to_numeric(y_train, errors='coerce').fillna(0)
            y_te = pd.to_numeric(y_test, errors='coerce').fillna(0)
            rf = RandomForestRegressor(
                n_estimators=evaluation.EVAL_RF_N_ESTIMATORS,
                max_depth=evaluation.EVAL_RF_MAX_DEPTH,
                n_jobs=evaluation.EVAL_RF_N_JOBS,
                random_state=common.RANDOM_STATE,
            )
            rf.fit(X_train, y_tr)
            preds = rf.predict(X_test)
            r2 = r2_score(y_te, preds)
            # Map R² (−∞, 1] → [0, 100]; negative R² is clipped to 0
            return max(0.0, min(1.0, float(r2))) * evaluation.EVAL_SCORE_SCALE
        else:
            le = LabelEncoder()
            y_tr_enc = le.fit_transform(y_train.astype(str))
            # Map unseen test labels to the first known class to avoid transform errors
            y_te_clean = y_test.astype(str).map(lambda s: s if s in le.classes_ else le.classes_[0])
            y_te_enc = le.transform(y_te_clean)
            rf = RandomForestClassifier(
                n_estimators=evaluation.EVAL_RF_N_ESTIMATORS,
                max_depth=evaluation.EVAL_RF_MAX_DEPTH,
                n_jobs=evaluation.EVAL_RF_N_JOBS,
                random_state=common.RANDOM_STATE,
            )
            rf.fit(X_train, y_tr_enc)
            preds = rf.predict(X_test)
            f1 = f1_score(y_te_enc, preds, average='weighted')
            return float(f1) * evaluation.EVAL_SCORE_SCALE

    def compute_utility(self) -> Tuple[float, Dict[str, Any]]:
        """
        Calculates utility score (0-100).
        Combines TSTR (Train Synthetic Test Real) and TRTS (Train Real Test Synthetic)
        with equal weights (defined in constants/evaluation.py).
        """
        try:
            if len(self.synthetic) == 0 or len(self.real_holdout) == 0:
                return 0.0, {"error": "Empty dataframe"}

            # ── Pick target column using heuristic ───────────────────────────
            target_col = self._select_target_column()
            if not target_col:
                return 50.0, {"note": "no suitable target column found"}  # noqa: hardcode cannot evaluate

            feature_cols = [c for c in self.real_train.columns if c != target_col]
            if not feature_cols:
                return evaluation.EVAL_SCORE_SCALE, {"note": "Single column table, utility defaulted"}

            is_numeric_target = is_numeric_like(self.real_train[target_col])

            # ── TSTR: train on synthetic, test on real hold-out ───────────────
            X_synth = pd.get_dummies(self.synthetic[feature_cols].astype(str))
            X_real_ho = pd.get_dummies(self.real_holdout[feature_cols].astype(str))
            X_synth_aligned, X_real_ho_aligned = X_synth.align(X_real_ho, join='left', axis=1, fill_value=0)

            tstr_raw = self._fit_predict_rf(
                X_synth_aligned,
                self.synthetic[target_col],
                X_real_ho_aligned,
                self.real_holdout[target_col],
                is_numeric_target,
            )

            # ── TRTS: train on real_train, test on synthetic ──────────────────
            X_real_tr = pd.get_dummies(self.real_train[feature_cols].astype(str))
            X_synth_te = pd.get_dummies(self.synthetic[feature_cols].astype(str))
            X_real_tr_aligned, X_synth_te_aligned = X_real_tr.align(X_synth_te, join='left', axis=1, fill_value=0)

            trts_raw = self._fit_predict_rf(
                X_real_tr_aligned,
                self.real_train[target_col],
                X_synth_te_aligned,
                self.synthetic[target_col],
                is_numeric_target,
            )

            utility_score = round(
                evaluation.UTILITY_TSTR_WEIGHT * tstr_raw
                + evaluation.UTILITY_TRTS_WEIGHT * trts_raw,
                2,
            )
            details = {
                "target_column": target_col,
                "tstr_score": round(tstr_raw, 2),
                "trts_score": round(trts_raw, 2),
                "model": "RandomForest",
            }
            logging.info(f"DataEvaluator: Utility score = {utility_score}")
            return utility_score, details

        except Exception as e:
            raise HackDataException(e, sys)

    def compute_privacy(self) -> Tuple[float, Dict[str, Any]]:
        """
        Calculates privacy score (0-100).
        High score = High privacy (low risk of memorizing/leaking training data).
        Combines exact match rate (weight 0.4) and DCR ratio (weight 0.6).
        Both weights are defined in constants/evaluation.py.
        """
        try:
            if len(self.synthetic) == 0 or len(self.real_train) == 0:
                return 100.0, {"exact_matches": 0}

            # ── Cap rows for speed on large datasets ─────────────────────────
            synth_sample = self.synthetic.head(evaluation.EVAL_PRIVACY_MAX_SAMPLE_ROWS)
            train_sample = self.real_train.head(evaluation.EVAL_PRIVACY_MAX_SAMPLE_ROWS)
            holdout_sample = self.real_holdout.head(evaluation.EVAL_PRIVACY_MAX_SAMPLE_ROWS)

            # ── 1. Exact match rate ──────────────────────────────────────────
            train_tuples = set(tuple(x) for x in train_sample.astype(str).to_numpy())
            synth_tuples = [tuple(x) for x in synth_sample.astype(str).to_numpy()]

            exact_matches = sum(1 for t in synth_tuples if t in train_tuples)
            exact_match_ratio = exact_matches / len(synth_tuples) if synth_tuples else 0.0

            # ── 2. DCR (Distance to Closest Record) ratio ────────────────────
            # Algorithm: standardise numeric cols on train; compute per-row
            # nearest-neighbour L2 distance for synthetic vs train and for
            # holdout vs train; ratio >= 1 means synthetic is at least as far
            # from training data as real unseen data, which is good for privacy.
            numeric_cols = [c for c in self.real_train.columns if is_numeric_like(self.real_train[c])]
            if not numeric_cols or len(holdout_sample) == 0:
                # No numeric columns or no holdout — DCR defaults to perfect privacy
                dcr_score = 1.0
            else:
                train_num = train_sample[numeric_cols].apply(pd.to_numeric, errors='coerce').fillna(0)
                synth_num = synth_sample[numeric_cols].apply(pd.to_numeric, errors='coerce').fillna(0)
                holdout_num = holdout_sample[numeric_cols].apply(pd.to_numeric, errors='coerce').fillna(0)

                # Fit scaler on real training data only (no leakage)
                scaler = StandardScaler()
                train_scaled = scaler.fit_transform(train_num)
                synth_scaled = scaler.transform(synth_num)
                holdout_scaled = scaler.transform(holdout_num)

                # Min L2 distance from each synthetic row to any real training row
                syn_dists = euclidean_distances(synth_scaled, train_scaled)
                syn_nn_dists = np.min(syn_dists, axis=1)

                # Min L2 distance from each holdout row to any real training row
                # (baseline: how close are real unseen rows to the training set)
                real_dists = euclidean_distances(holdout_scaled, train_scaled)
                real_nn_dists = np.min(real_dists, axis=1)

                # Ratio > 1 → synthetic is further from training than real holdout is
                dcr = float(np.median(syn_nn_dists)) / (float(np.median(real_nn_dists)) + evaluation.PRIVACY_DCR_EPSILON)
                dcr_score = min(1.0, dcr)  # clamp; > 1.0 already means good privacy

            # ── Combine exact-match and DCR scores ───────────────────────────
            privacy_score = max(
                0.0,
                (evaluation.PRIVACY_EXACT_WEIGHT * (1.0 - exact_match_ratio)
                 + evaluation.PRIVACY_DCR_WEIGHT * dcr_score)
                * evaluation.EVAL_SCORE_SCALE,
            )

            details = {
                "exact_match_count": exact_matches,
                "exact_match_ratio": round(exact_match_ratio, 4),
                "dcr_score": round(dcr_score, 4),
                "privacy_flag": exact_match_ratio > evaluation.EVAL_PRIVACY_EXACT_MATCH_THRESHOLD,
            }
            logging.info(f"DataEvaluator: Privacy score = {round(privacy_score, 2)}")
            return round(privacy_score, 2), details

        except Exception as e:
            raise HackDataException(e, sys)

    def evaluate_all(self) -> Dict[str, Any]:
        """Runs fidelity, utility, and privacy metrics."""
        fid_score, fid_details = self.compute_fidelity()
        util_score, util_details = self.compute_utility()
        priv_score, priv_details = self.compute_privacy()
        
        return {
            "fidelity_score": fid_score,
            "fidelity_details": fid_details,
            "utility_score": util_score,
            "utility_details": util_details,
            "privacy_score": priv_score,
            "privacy_details": priv_details
        }
