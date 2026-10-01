# ═══════════════════════════════════════════════════════════════════
# datamode_pipeline.py — End-to-End Data-Mode Generation Pipeline
# ═══════════════════════════════════════════════════════════════════
# Implements T-042: Datamode pipeline (upload to synthetic CSV)
# ═══════════════════════════════════════════════════════════════════

import os
import sys
import json
from datetime import datetime
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Dict, Any, Optional
import pandas as pd
import numpy as np
from scipy.stats import norm

from hackdata.constants import paths, data_mode, common, messages
from hackdata.exception.exception import HackDataException
from hackdata.logging.logger import logging
from hackdata.components.copula_fitter import CopulaFitter
from hackdata.components.sensitive_masker import detect_and_mask
from hackdata.components.data_validator import DataValidator
from hackdata.components.evaluator import DataEvaluator
from hackdata.components.scorecard import ScorecardAggregator
from hackdata.entity.artifact_entity import DataGenerationArtifact
from hackdata.entity.config_entity import DataValidationConfig
from hackdata.entity.spec_entity import ColumnSpec, Spec, TableSpec
from hackdata.utils.main_utils.utils import ensure_dir, load_object
from hackdata.utils.main_utils.canonical_io import write_csv_canonical
from hackdata.utils.main_utils.seed_utils import make_rng, new_master_seed

@dataclass
class DataModePipelineResult:
    run_id: str
    synthetic_csv_path: str
    train_rows: int
    holdout_rows: int
    synthetic_rows: int
    scorecard: Dict[str, Any]
    masked_columns: list = field(default_factory=list)   # columns masked by sensitive_masker
    status: bool = True

class DataModePipeline:
    """
    Executes Data Mode: Ingests uploaded dataset, splits 80/20, fits copula model,
    samples synthetic data, validates structural integrity, evaluates metrics,
    and returns a complete scorecard.
    """
    def __init__(
        self,
        data_path: str,
        run_id: Optional[str] = None,
        n_synthetic_rows: Optional[int] = None,
        master_seed: Optional[int] = None,
        # Step B realism settings — all default to 0 (no effect)
        missing_rate: float = 0.0,
        outlier_rate: float = 0.0,
        noise_level: float = 0.0,
        correlation_adjustment: float = 0.0,
    ):
        self.data_path = data_path
        # AV-06: use the shared timestamp format constant instead of a literal format string.
        self.run_id = run_id or datetime.now().strftime(common.RUN_TIMESTAMP_FORMAT)
        self.n_synthetic_rows = n_synthetic_rows
        # AV-01: store master seed so _sample_synthetic_data can derive per-column RNGs.
        self.master_seed: int = master_seed if master_seed is not None else new_master_seed()

        # Step B: validate and store realism settings
        from hackdata.constants import data_mode as dm_const, messages as msg_const
        for rate, cap, name in [
            (missing_rate,          dm_const.DM_MAX_MISSING_RATE,  "missing_rate"),
            (outlier_rate,          dm_const.DM_MAX_OUTLIER_RATE,  "outlier_rate"),
            (noise_level,           dm_const.DM_MAX_NOISE_LEVEL,   "noise_level"),
        ]:
            if rate > cap:
                raise ValueError(
                    msg_const.MSG_MESSINESS_RATE_TOO_HIGH.format(
                        rate=rate, max_rate=cap, setting=name
                    )
                )
        if abs(correlation_adjustment) > dm_const.DM_MAX_CORR_ADJ:
            raise ValueError(
                f"correlation_adjustment {correlation_adjustment:.2f} must be in [-1, 1]"
            )
        self.missing_rate = missing_rate
        self.outlier_rate = outlier_rate
        self.noise_level = noise_level
        self.correlation_adjustment = correlation_adjustment

        self.artifact_dir = os.path.join(paths.ARTIFACTS_TEMP_DIR, self.run_id)
        ensure_dir(self.artifact_dir)

    def _sample_synthetic_data(
        self,
        train_df: pd.DataFrame,
        model: dict,
        n_rows: int,
        master_seed: int,
        table_name: str,
    ) -> pd.DataFrame:
        """Samples synthetic data using copula for numerics and empirical sampling for categoricals.

        Parameters
        ----------
        train_df    : real training DataFrame
        model       : fitted copula dict (marginals, correlation, columns)
        n_rows      : number of synthetic rows to produce
        master_seed : run-level seed; each column derives its own RNG via make_rng
        table_name  : used as scope key in make_rng for reproducibility
        """
        try:
            synthetic_df = pd.DataFrame(index=range(n_rows))

            if model and "marginals" in model and "correlation" in model:
                marginals = model["marginals"]
                corr_matrix = model["correlation"]
                cols = model["columns"]

                # AV-01: use seeded RNG — copula_sample scope covers the whole multivariate draw.
                # ponytail: one RNG for the whole copula block; per-column RNG if reproducibility
                #           must survive adding/removing columns.
                rng_copula = make_rng(master_seed, table_name, "copula_sample")

                # Draw standard normal samples with covariance structure
                mean_zeros = np.zeros(len(cols))
                normal_samples = rng_copula.multivariate_normal(mean_zeros, corr_matrix, size=n_rows)

                for i, col in enumerate(cols):
                    # Transform normal back to uniform [0, 1]
                    uniforms = norm.cdf(normal_samples[:, i])

                    # Map uniform to empirical quantiles
                    sorted_vals = marginals[col]
                    indices = (uniforms * (len(sorted_vals) - 1)).astype(int)
                    indices = np.clip(indices, 0, len(sorted_vals) - 1)
                    synthetic_df[col] = sorted_vals[indices]

            # For any non-numeric or unmodeled column, sample empirically from train set.
            # AV-01: each column gets its own RNG scoped by (master_seed, table, col).
            for col in train_df.columns:
                if col not in synthetic_df.columns:
                    rng_col = make_rng(master_seed, table_name, col)
                    synthetic_df[col] = rng_col.choice(
                        train_df[col].dropna().values, size=n_rows, replace=True
                    )

            return synthetic_df[train_df.columns]

        except Exception as e:
            raise HackDataException(e, sys)

    def _apply_realism(
        self,
        df: pd.DataFrame,
        train_df: pd.DataFrame,
        protected_cols: set,
    ) -> pd.DataFrame:
        """Apply Step-B realism settings (missing / outlier / noise) post-sampling.

        All effects are seeded from self.master_seed for reproducibility.
        Protected columns (id-like, masked sensitive) are never touched.
        """
        from hackdata.constants import data_mode as dm_const
        from hackdata.components.data_profiler import _infer_col_type

        if not any([self.missing_rate, self.outlier_rate, self.noise_level]):
            return df  # nothing to do — fast path

        out = df.copy()
        rng = make_rng(self.master_seed, "realism", "global")

        for col in out.columns:
            if col in protected_cols:
                continue
            col_type = _infer_col_type(out[col], col)
            n = len(out)

            # MCAR null injection
            if self.missing_rate > 0:
                null_mask = rng.random(n) < self.missing_rate
                out.loc[null_mask, col] = np.nan

            if col_type == "numeric":
                vals = pd.to_numeric(out[col], errors="coerce")
                col_std = pd.to_numeric(train_df[col], errors="coerce").std() if col in train_df else vals.std()
                if col_std == 0 or pd.isna(col_std):
                    continue

                # Gaussian noise: scale by fraction of train std
                if self.noise_level > 0:
                    noise = rng.normal(0, self.noise_level * col_std, n)
                    out[col] = vals + noise

                # Outlier injection: push selected rows beyond DM_OUTLIER_SIGMA std
                if self.outlier_rate > 0:
                    col_mean = pd.to_numeric(train_df[col], errors="coerce").mean() if col in train_df else vals.mean()
                    outlier_mask = rng.random(n) < self.outlier_rate
                    # Randomly above or below the mean
                    directions = rng.choice([-1, 1], n)
                    vals_arr = pd.to_numeric(out[col], errors="coerce").values.copy()
                    vals_arr[outlier_mask] = (
                        col_mean + directions[outlier_mask] * dm_const.DM_OUTLIER_SIGMA * col_std
                    )
                    out[col] = vals_arr

        return out

    def run(self) -> DataModePipelineResult:
        """Executes the data-mode pipeline end-to-end."""
        try:
            logging.info(f"DataModePipeline: Starting run {self.run_id} for file {self.data_path}")
            
            # Step 1: 80/20 split & Copula fitting
            fitter = CopulaFitter(self.data_path, self.run_id)
            fit_result = fitter.run()
            
            train_df = pd.read_csv(os.path.join(fitter.train_dir, paths.TRAIN_FILE_NAME))
            holdout_df = pd.read_csv(os.path.join(fitter.holdout_dir, paths.HOLDOUT_FILE_NAME))
            
            # Load fitted copula model if available
            model = None
            if fit_result.get("model_path") and os.path.exists(fit_result["model_path"]):
                model = load_object(fit_result["model_path"])
                
            n_synth = self.n_synthetic_rows or len(train_df)

            # Derive table name from the uploaded file stem for use as RNG scope key.
            table_name = os.path.splitext(os.path.basename(self.data_path))[0]

            # Step B: apply correlation_adjustment to copula matrix before sampling.
            # Scale off-diagonal by (1 + adj) then repair to nearest PSD matrix.
            # Formula: C'[i,j] = C[i,j] * (1 + adj)  for i≠j, then clip to [-1,1]
            # and project to PSD via eigenvalue floor (same method as CopulaFitter).
            if model and self.correlation_adjustment != 0.0 and "correlation" in model:
                C = np.array(model["correlation"], dtype=float)
                n_c = C.shape[0]
                adj = self.correlation_adjustment
                for i in range(n_c):
                    for j in range(n_c):
                        if i != j:
                            C[i, j] = np.clip(C[i, j] * (1.0 + adj), -1.0, 1.0)
                # Repair to PSD by flooring negative eigenvalues to epsilon
                eigvals, eigvecs = np.linalg.eigh(C)
                from hackdata.constants import data_mode as dm_const_inner
                eigvals = np.maximum(eigvals, dm_const_inner.DM_COPULA_EIGEN_EPSILON)
                C_repaired = eigvecs @ np.diag(eigvals) @ eigvecs.T
                # Renormalize diagonal to exactly 1.0
                d = np.sqrt(np.diag(C_repaired))
                C_repaired = C_repaired / np.outer(d, d)
                model = dict(model)
                model["correlation"] = C_repaired

            # Step 2: Sample synthetic data
            synthetic_df = self._sample_synthetic_data(
                train_df, model, n_synth, self.master_seed, table_name
            )

            # Step 3a: Mask sensitive columns before writing or evaluating.
            # IMP: masking happens on column names only — no values are inspected
            #      or sent to the LLM.  Evaluation uses the masked frame so metrics
            #      reflect what the user actually receives.
            synthetic_df, masked_columns = detect_and_mask(synthetic_df)
            if masked_columns:
                logging.info(
                    messages.MSG_MASKED_COLUMNS.format(columns=masked_columns)
                )

            # Step B: apply realism settings post-masking.
            # Masked and id-like columns are protected — never nulled or perturbed.
            from hackdata.components.data_profiler import _infer_col_type
            protected = set(masked_columns) | {
                c for c in synthetic_df.columns
                if _infer_col_type(synthetic_df[c], c) == "id-like"
            }
            synthetic_df = self._apply_realism(synthetic_df, train_df, protected)

            # Step 3b: Write synthetic CSV
            synthetic_csv_path = os.path.join(self.artifact_dir, paths.SYNTHETIC_DATA_FILE_NAME)
            synthetic_df.to_csv(synthetic_csv_path, index=False)

            # Step 4: Validate synthetic data via DataValidator.
            # BUG-003: replaced hardcoded validity_score = 100.0 with a real check.
            # Build a minimal Spec from the synthetic DataFrame column names.
            # Columns with no nulls in the training data get a not_null rule so
            # any nulls introduced by sampling are caught as tier-1 defects.
            columns = []
            for col in synthetic_df.columns:
                has_train_nulls = (
                    train_df[col].isna().any() if col in train_df.columns else True
                )
                rules = [] if has_train_nulls else ["not_null"]
                columns.append(ColumnSpec(name=col, gen="sequence", rules=rules))
            dm_spec = Spec(
                version="1",
                module="tabular",
                tables=[TableSpec(name=table_name, n_rows=len(synthetic_df), columns=columns)],
            )
            # Proxy supplies artifact_dir to DataValidationConfig without needing a full RunConfig.
            _rc_proxy = SimpleNamespace(artifact_dir=self.artifact_dir)
            val_config = DataValidationConfig(_rc_proxy)
            gen_artifact = DataGenerationArtifact(
                tables_dir=self.artifact_dir,
                table_file_paths={table_name: synthetic_csv_path},
                master_seed=self.master_seed,
                row_counts={table_name: len(synthetic_df)},
            )
            val_artifact = DataValidator(val_config, gen_artifact, dm_spec).initiate_data_validation()
            validity_score = val_artifact.validity_score
            
            # Step 5: Evaluate Fidelity, Utility, Privacy metrics
            evaluator = DataEvaluator(train_df, holdout_df, synthetic_df)
            eval_metrics = evaluator.evaluate_all()
            
            # Step 6: Aggregate scorecard — pass run_dir so scorecard.py does not
            # re-derive the path from ARTIFACTS_TEMP_DIR (AV-05).
            scorecard_agg = ScorecardAggregator(self.run_id, run_dir=self.artifact_dir)
            scorecard = scorecard_agg.calculate_scorecard(
                validity_score=validity_score,
                fidelity_score=eval_metrics["fidelity_score"],
                utility_score=eval_metrics["utility_score"],
                privacy_score=eval_metrics["privacy_score"],
                details=eval_metrics
            )
            
            # Write run metadata
            meta_path = os.path.join(self.artifact_dir, paths.GENERATION_RUN_META_FILE_NAME)
            meta_data = {
                "run_id": self.run_id,
                "mode": "data_mode",
                "seed": self.master_seed,
                "train_rows": len(train_df),
                "holdout_rows": len(holdout_df),
                "synthetic_rows": len(synthetic_df),
                "timestamp": datetime.now().isoformat(),
                # Step B: record realism settings for reproducibility
                "realism": {
                    "missing_rate": self.missing_rate,
                    "outlier_rate": self.outlier_rate,
                    "noise_level": self.noise_level,
                    "correlation_adjustment": self.correlation_adjustment,
                },
            }
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta_data, f, indent=2)

            logging.info(f"DataModePipeline: Run {self.run_id} completed successfully.")
            return DataModePipelineResult(
                run_id=self.run_id,
                synthetic_csv_path=synthetic_csv_path,
                train_rows=len(train_df),
                holdout_rows=len(holdout_df),
                synthetic_rows=len(synthetic_df),
                scorecard=scorecard,
                masked_columns=masked_columns,
                status=True
            )

        except Exception as e:
            raise HackDataException(e, sys)
