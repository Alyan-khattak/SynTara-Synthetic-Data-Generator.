# ═══════════════════════════════════════════════════════════════════
# copula_fitter.py — Data Mode Gaussian Copula 80/20 Split & Fit
# ═══════════════════════════════════════════════════════════════════
# Implements T-040: Data mode: 80/20 split, fit Gaussian copula on train only.
###==============================================================
import os
import sys
from typing import Tuple
import pandas as pd
import numpy as np
from scipy.stats import norm

from hackdata.constants import paths, data_mode
from hackdata.exception.exception import HackDataException
from hackdata.logging.logger import logging
from hackdata.utils.main_utils.utils import ensure_dir, save_object

class CopulaFitter:
    """
    Handles data ingestion, 80/20 splitting, and fitting a Gaussian Copula
    model on the training split only, ignoring the hold-out completely.
    """
    def __init__(self, data_path: str, run_id: str):
        self.data_path = data_path
        self.run_id = run_id
        
        self.artifact_dir = os.path.join(paths.ARTIFACTS_TEMP_DIR, run_id)
        self.data_ingestion_dir = os.path.join(self.artifact_dir, paths.DATA_INGESTION_DIR_NAME)
        self.train_dir = os.path.join(self.data_ingestion_dir, paths.TRAIN_DIR_NAME)
        self.holdout_dir = os.path.join(self.data_ingestion_dir, paths.HOLDOUT_DIR_NAME)
        
        self.model_fitter_dir = os.path.join(self.artifact_dir, paths.MODEL_FITTER_DIR_NAME)

    def _split_data(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Reads CSV and performs an 80/20 split."""
        try:
            df = pd.read_csv(self.data_path)
            if len(df) < data_mode.DM_MIN_ROWS_REFUSE:
                raise ValueError(f"Data has {len(df)} rows, minimum allowed is {data_mode.DM_MIN_ROWS_REFUSE}")

            # Shuffle and split
            from hackdata.constants import common
            df = df.sample(frac=1, random_state=common.RANDOM_STATE).reset_index(drop=True)
            split_idx = int(len(df) * (1 - data_mode.DM_TRAIN_TEST_SPLIT_RATIO))
            
            train_df = df.iloc[:split_idx].copy()
            holdout_df = df.iloc[split_idx:].copy()

            ensure_dir(self.train_dir)
            ensure_dir(self.holdout_dir)
            
            train_path = os.path.join(self.train_dir, paths.TRAIN_FILE_NAME)
            holdout_path = os.path.join(self.holdout_dir, paths.HOLDOUT_FILE_NAME)
            
            train_df.to_csv(train_path, index=False)
            holdout_df.to_csv(holdout_path, index=False)
            
            logging.info(f"CopulaFitter: Split complete. Train: {len(train_df)}, Holdout: {len(holdout_df)}")  # noqa:hardcode
            return train_df, holdout_df
            
        except Exception as e:
            raise HackDataException(e, sys)

    def _fit_copula(self, train_df: pd.DataFrame):
        """Fits a Gaussian Copula to the numeric columns of the training set."""
        from hackdata.constants import messages
        try:
            numeric_df = train_df.select_dtypes(include=[np.number])
            if numeric_df.empty:
                logging.warning(messages.MSG_COPULA_NO_NUMERIC)
                return None
            
            # DRY RUN: 
            # 1. Transform marginals to Uniform[0, 1] using empirical CDF.
            # 2. Transform Uniform to Standard Normal using norm.ppf.
            # 3. Compute correlation matrix of standard normals.
            
            marginals = {}
            normal_data = []
            
            for col in numeric_df.columns:
                series = numeric_df[col].dropna()
                if len(series) == 0:
                    continue
                
                # Create grid for Empirical CDF
                sorted_vals = np.sort(series.values)
                # Keep a sample or the exact sorted values depending on size
                if len(sorted_vals) > data_mode.DM_COPULA_QUANTILE_GRID_SIZE:
                    idx = np.linspace(0, len(sorted_vals) - 1, data_mode.DM_COPULA_QUANTILE_GRID_SIZE, dtype=int)
                    sorted_vals = sorted_vals[idx]
                    
                marginals[col] = sorted_vals
                
                # Ranks mapped to (0, 1) to avoid infs in ppf
                ranks = series.rank(method='average')
                uniforms = ranks / (len(series) + 1)
                
                normals = norm.ppf(uniforms)
                # re-index back to match train_df index
                normal_series = pd.Series(normals, index=series.index)
                normal_data.append(normal_series)
            
            if not normal_data:
                return None
                
            normal_df = pd.concat(normal_data, axis=1)
            normal_df.columns = marginals.keys()
            
            # Compute correlation matrix
            corr_matrix = normal_df.corr().fillna(0).values
            
            # Apply eigen epsilon for positive semi-definiteness
            eigvals, eigvecs = np.linalg.eigh(corr_matrix)
            eigvals = np.maximum(eigvals, data_mode.DM_COPULA_EIGEN_EPSILON)
            corr_matrix = eigvecs @ np.diag(eigvals) @ eigvecs.T
            
            model = {
                "marginals": marginals,
                "correlation": corr_matrix,
                "columns": list(marginals.keys())
            }
            
            ensure_dir(self.model_fitter_dir)
            model_path = os.path.join(self.model_fitter_dir, paths.FITTED_MODEL_FILE_NAME)
            save_object(model_path, model)
            logging.info(f"CopulaFitter: Model fitted on {len(model['columns'])} numeric columns.")
            
            return model_path

        except Exception as e:
            raise HackDataException(e, sys)

    def run(self):
        """Orchestrates split and fit."""
        try:
            train_df, holdout_df = self._split_data()
            model_path = self._fit_copula(train_df)
            return {
                "train_rows": len(train_df),
                "holdout_rows": len(holdout_df),
                "model_path": model_path
            }
        except Exception as e:
            raise HackDataException(e, sys)
