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
    ):
        self.data_path = data_path
        # AV-06: use the shared timestamp format constant instead of a literal format string.
        self.run_id = run_id or datetime.now().strftime(common.RUN_TIMESTAMP_FORMAT)
        self.n_synthetic_rows = n_synthetic_rows
        # AV-01: store master seed so _sample_synthetic_data can derive per-column RNGs.
        self.master_seed: int = master_seed if master_seed is not None else new_master_seed()

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
                "train_rows": len(train_df),
                "holdout_rows": len(holdout_df),
                "synthetic_rows": len(synthetic_df),
                "timestamp": datetime.now().isoformat()
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
