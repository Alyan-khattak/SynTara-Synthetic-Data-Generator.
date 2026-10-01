# ═══════════════════════════════════════════════════════════════════
# ml_lab_pipeline.py — ML Lab end-to-end pipeline (Steps A-D)
# ═══════════════════════════════════════════════════════════════════
# Supports two sources:
#   "describe" → LLM spec + code-generated data, target column planted
#   "upload"   → existing uploaded CSV (CopulaFitter synthetic or raw)
#
# IMP: uploaded CSV data is NEVER sent to any external model or API.
#      Only the text query (describe source) may touch the LLM layer.
# ═══════════════════════════════════════════════════════════════════
import glob
import json
import os
import sys
import textwrap
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

from hackdata.components.data_profiler import _infer_col_type
from hackdata.components.ml_checker import run_ml_check
from hackdata.constants import common, ml_lab as ml_const, messages as msg_const, paths as paths_const
from hackdata.exception.exception import HackDataException
from hackdata.logging.logger import logging
from hackdata.utils.main_utils.seed_utils import make_rng, new_master_seed
from hackdata.utils.main_utils.utils import ensure_dir, write_json_file


@dataclass
class MLLabResult:
    run_id: str
    source_type: str
    task_type: str
    target_col: str
    train_csv_path: str
    test_csv_path:  str
    ml_check: Dict[str, Any]
    preview: List[dict]          # first N rows of train for UI
    train_rows: int
    test_rows: int
    seed: int
    warning: Optional[str] = None


class MLLabPipeline:
    """
    Orchestrates ML Lab data generation + target planting + ML check + export.

    Parameters
    ----------
    source_type       : 'describe' (LLM query) or 'upload' (existing run CSV)
    query             : natural-language query (describe source only)
    upload_run_id     : run_id of a prior Data Mode or ML upload (upload source)
    target_col        : name of target column to predict
    task_type         : 'classification' | 'regression'
    drivers           : list of driver column names (empty = all non-key cols)
    signal_strength   : 0-1; how clearly the drivers predict the target
    class_balance     : positive-class fraction (classification only)
    label_noise       : fraction of labels to flip/add noise (0 = off)
    n_rows            : number of synthetic rows to generate
    seed              : master random seed (None = random)
    train_ratio       : fraction of rows to put in train split
    """

    def __init__(
        self,
        source_type: str,
        target_col: str,
        task_type: str,
        query: Optional[str] = None,
        upload_run_id: Optional[str] = None,
        drivers: Optional[List[str]] = None,
        signal_strength: float = ml_const.ML_DEFAULT_SIGNAL,
        class_balance: float = ml_const.ML_DEFAULT_CLASS_BALANCE,
        label_noise: float = ml_const.ML_DEFAULT_LABEL_NOISE,
        n_rows: int = 1000,
        seed: Optional[int] = None,
        train_ratio: float = ml_const.ML_DEFAULT_TRAIN_RATIO,
    ):
        # ── validate inputs ───────────────────────────────────────────────────
        if source_type not in (ml_const.ML_SOURCE_DESCRIBE, ml_const.ML_SOURCE_UPLOAD):
            raise ValueError(msg_const.MSG_ML_UNKNOWN_SOURCE.format(
                value=source_type,
                allowed=(ml_const.ML_SOURCE_DESCRIBE, ml_const.ML_SOURCE_UPLOAD),
            ))
        if task_type not in ml_const.ML_TASK_TYPES:
            raise ValueError(msg_const.MSG_ML_UNKNOWN_TASK.format(
                value=task_type, allowed=ml_const.ML_TASK_TYPES,
            ))
        if not (0.0 <= signal_strength <= ml_const.ML_MAX_SIGNAL):
            raise ValueError(msg_const.MSG_ML_SIGNAL_OOB.format(value=signal_strength))
        if not (ml_const.ML_MIN_CLASS_BALANCE <= class_balance <= ml_const.ML_MAX_CLASS_BALANCE):
            raise ValueError(msg_const.MSG_ML_CLASS_BALANCE_OOB.format(
                value=class_balance,
                lo=ml_const.ML_MIN_CLASS_BALANCE,
                hi=ml_const.ML_MAX_CLASS_BALANCE,
            ))
        if not (0.0 <= label_noise <= ml_const.ML_MAX_LABEL_NOISE):
            raise ValueError(msg_const.MSG_ML_NOISE_OOB.format(
                value=label_noise, cap=ml_const.ML_MAX_LABEL_NOISE,
            ))
        if not (ml_const.ML_MIN_TRAIN_RATIO <= train_ratio <= ml_const.ML_MAX_TRAIN_RATIO):
            raise ValueError(msg_const.MSG_ML_TRAIN_RATIO_OOB.format(
                value=train_ratio,
                lo=ml_const.ML_MIN_TRAIN_RATIO,
                hi=ml_const.ML_MAX_TRAIN_RATIO,
            ))
        if n_rows < ml_const.ML_MIN_ROWS:
            raise ValueError(msg_const.MSG_ML_ROWS_TOO_LOW.format(
                n=n_rows, min_rows=ml_const.ML_MIN_ROWS,
            ))
        if n_rows > ml_const.ML_MAX_ROWS:
            raise ValueError(msg_const.MSG_ML_ROWS_TOO_HIGH.format(
                n=n_rows, max_rows=ml_const.ML_MAX_ROWS,
            ))
        if source_type == ml_const.ML_SOURCE_DESCRIBE and not query:
            raise ValueError(msg_const.MSG_ML_NO_QUERY)

        self.source_type    = source_type
        self.query          = query
        self.upload_run_id  = upload_run_id
        self.target_col     = target_col
        self.task_type      = task_type
        self.drivers        = drivers or []
        self.signal_strength = signal_strength
        self.class_balance  = class_balance
        self.label_noise    = label_noise
        self.n_rows         = n_rows
        self.seed           = seed if seed is not None else new_master_seed()
        self.train_ratio    = train_ratio

        # Run lives in Artifacts/temp/<run_id>
        self.run_id = datetime.now().strftime(common.RUN_TIMESTAMP_FORMAT)
        self.run_dir = os.path.join(paths_const.ARTIFACTS_TEMP_DIR, self.run_id)
        self.export_dir = os.path.join(self.run_dir, ml_const.ML_EXPORT_DIR_NAME)

    # ── internal helpers ─────────────────────────────────────────────────────

    def _find_source_csv(self, run_id: str) -> str:
        """Find the original uploaded CSV for a Data Mode run."""
        run_dir = os.path.join(paths_const.ARTIFACTS_TEMP_DIR, run_id)
        if not os.path.exists(run_dir):
            run_dir = os.path.join(paths_const.ARTIFACTS_SAVED_DIR, run_id)
        if not os.path.exists(run_dir):
            raise ValueError(msg_const.MSG_ML_UPLOAD_NOT_FOUND.format(run_id=run_id))

        # Prefer synthetic CSV if generation has already run
        synth = os.path.join(run_dir, paths_const.SYNTHETIC_DATA_FILE_NAME)
        if os.path.exists(synth):
            return synth

        # Fall back to original uploaded CSV
        candidates = [
            p for p in glob.glob(os.path.join(run_dir, "*.csv"))
            if os.path.basename(p) != paths_const.SYNTHETIC_DATA_FILE_NAME
        ]
        if candidates:
            return candidates[0]
        raise ValueError(msg_const.MSG_ML_UPLOAD_NOT_FOUND.format(run_id=run_id))

    def _is_key_col(self, series: pd.Series, col: str) -> bool:
        """True if the column looks like a primary key (id-like)."""
        return _infer_col_type(series, col) == "id-like"

    def _plant_target(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add target column built from driver columns + seeded noise.

        For classification: logistic function → binary label (or multi-class
        via thresholds).  For regression: linear combination + noise.
        If the target column already exists (shouldn't happen for describe
        source) it is overwritten.
        """
        rng = make_rng(self.seed, "ml_lab", "target")

        # Resolve drivers: default to all numeric non-key cols
        all_cols = list(df.columns)
        if self.drivers:
            # Validate every driver exists and is not a key
            for col in self.drivers:
                if col not in all_cols:
                    raise ValueError(msg_const.MSG_ML_UNKNOWN_DRIVER.format(col=col))
                if self._is_key_col(df[col], col):
                    raise ValueError(msg_const.MSG_ML_KEY_DRIVER.format(col=col))
            driver_cols = self.drivers
        else:
            driver_cols = [
                c for c in all_cols
                if c != self.target_col
                and not self._is_key_col(df[c], c)
                and pd.api.types.is_numeric_dtype(df[c])
            ]

        if not driver_cols:
            # Fallback: use all non-target cols; let ml_checker handle encoding
            driver_cols = [c for c in all_cols if c != self.target_col]

        # Numeric representation of drivers (fill missing with median)
        X = df[driver_cols].apply(pd.to_numeric, errors="coerce")
        X = X.fillna(X.median())

        # Normalise each driver to [0,1] range to make signal_strength comparable
        col_range = X.max() - X.min()
        col_range[col_range == 0] = 1   # constant column: avoid divide-by-zero
        X_norm = (X - X.min()) / col_range

        # Linear score: weighted sum of normalised drivers
        n = len(df)
        weights = rng.normal(0, 1, len(driver_cols))
        weights /= (np.abs(weights).sum() + 1e-9)   # unit L1 norm
        score = X_norm.values @ weights              # (n,)

        # Noise component: (1 - signal_strength) fraction
        noise_std = (1.0 - self.signal_strength) + 1e-6
        noise = rng.normal(0, noise_std, n)
        score = score * self.signal_strength + noise * (1.0 - self.signal_strength)

        df = df.copy()

        if self.task_type == ml_const.ML_TASK_CLASSIFICATION:
            # Convert score to binary label via threshold at class_balance quantile
            threshold = np.quantile(score, 1.0 - self.class_balance)
            labels = (score >= threshold).astype(int)

            # Apply label noise: flip `label_noise` fraction of labels
            if self.label_noise > 0:
                flip_rng = make_rng(self.seed, "ml_lab", "label_noise")
                flip_mask = flip_rng.random(n) < self.label_noise
                labels[flip_mask] = 1 - labels[flip_mask]

            df[self.target_col] = labels

        else:  # regression
            # Standardise score to have similar scale as typical targets
            score = (score - score.mean()) / (score.std() + 1e-9)

            # Apply label noise as additive Gaussian
            if self.label_noise > 0:
                noise_rng = make_rng(self.seed, "ml_lab", "label_noise")
                noise_scale = self.label_noise * score.std() + 1e-6
                score = score + noise_rng.normal(0, noise_scale, n)

            df[self.target_col] = score.round(4)

        return df

    def _split_and_save(self, df: pd.DataFrame) -> tuple:
        """Stratified (classification) or random (regression) train/test split."""
        stratify = None
        if self.task_type == ml_const.ML_TASK_CLASSIFICATION:
            # Only stratify if every class has ≥ 2 members
            y = df[self.target_col].astype(str)
            if y.value_counts().min() >= 2:
                stratify = y

        test_size = 1.0 - self.train_ratio
        train_df, test_df = train_test_split(
            df,
            test_size=test_size,
            random_state=self.seed,
            stratify=stratify,
        )

        ensure_dir(self.export_dir)
        train_path = os.path.join(self.export_dir, ml_const.ML_TRAIN_FILE)
        test_path  = os.path.join(self.export_dir, ml_const.ML_TEST_FILE)
        train_df.to_csv(train_path, index=False)
        test_df.to_csv(test_path, index=False)
        return train_df, test_df, train_path, test_path

    def _write_starter_script(self, target_col: str) -> None:
        """Write start_here.py into the export dir."""
        script = textwrap.dedent(f"""\
            # start_here.py — auto-generated starter script for ML Lab
            # Loads the train/test CSVs, trains a baseline, prints the score.
            # Requires only: pandas, scikit-learn
            import pandas as pd
            from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
            from sklearn.preprocessing import LabelEncoder
            from sklearn.impute import SimpleImputer
            from sklearn.pipeline import Pipeline
            from sklearn.metrics import roc_auc_score, r2_score

            TRAIN_FILE  = "{ml_const.ML_TRAIN_FILE}"
            TEST_FILE   = "{ml_const.ML_TEST_FILE}"
            TARGET_COL  = "{target_col}"
            TASK_TYPE   = "{self.task_type}"

            train = pd.read_csv(TRAIN_FILE)
            test  = pd.read_csv(TEST_FILE)

            feature_cols = [c for c in train.columns if c != TARGET_COL]
            X_train, y_train = train[feature_cols], train[TARGET_COL]
            X_test,  y_test  = test[feature_cols],  test[TARGET_COL]

            num_cols = X_train.select_dtypes(include="number").columns.tolist()
            X_train = X_train[num_cols].fillna(0)
            X_test  = X_test[num_cols].fillna(0)

            if TASK_TYPE == "classification":
                le = LabelEncoder()
                y_train = le.fit_transform(y_train.astype(str))
                y_test  = le.transform(y_test.astype(str))
                model = RandomForestClassifier(n_estimators=50, random_state=42)
                model.fit(X_train, y_train)
                score = roc_auc_score(y_test, model.predict_proba(X_test)[:, 1] if len(le.classes_) == 2 else model.predict_proba(X_test), multi_class="ovr", average="macro")
                print(f"AUC: {{score:.4f}}")
            else:
                model = RandomForestRegressor(n_estimators=50, random_state=42)
                model.fit(X_train, y_train)
                score = r2_score(y_test, model.predict(X_test))
                print(f"R²: {{score:.4f}}")
        """)
        path = os.path.join(self.export_dir, ml_const.ML_STARTER_FILE)
        with open(path, "w") as f:
            f.write(script)

    def _write_data_card(
        self, df: pd.DataFrame, ml_check: Dict[str, Any], drivers: List[str]
    ) -> None:
        """Write DATA_CARD.md into the export dir."""
        lines = [
            "# DATA CARD — ML Lab",
            "",
            f"**Run ID:** {self.run_id}",
            f"**Source:** {self.source_type}",
            f"**Task:** {self.task_type}",
            f"**Target column:** {self.target_col}",
            f"**Driver columns:** {', '.join(drivers) if drivers else '(all numeric)'}",
            f"**Signal strength:** {self.signal_strength}",
            f"**Seed:** {self.seed}",
            f"**Rows total:** {len(df)}",
            f"**Train ratio:** {self.train_ratio}",
            "",
            "## Columns",
            "",
            "| Column | Type |",
            "|--------|------|",
        ]
        for col in df.columns:
            col_type = _infer_col_type(df[col], col)
            lines.append(f"| {col} | {col_type} |")

        lines += [
            "",
            "## ML Check Results",
            "",
            f"- Metric: {ml_check.get('metric')}",
            f"- Score: {ml_check.get('score')}",
            f"- Naive baseline: {ml_check.get('baseline')}",
            f"- Gap (score − baseline): {ml_check.get('gap')}",
        ]
        if ml_check.get("warning"):
            lines.append(f"- Warning: {ml_check['warning']}")

        lines += [
            "",
            "## Limitations",
            "",
            "- Synthetic data tests ML pipelines and teaches methods.",
            "- It does **not** replace real data for production modelling.",
            "- Scores reflect learnable signal planted during generation,",
            "  not real-world predictive performance.",
        ]

        path = os.path.join(self.export_dir, ml_const.ML_DATACARD_FILE)
        with open(path, "w") as f:
            f.write("\n".join(lines))

    # ── public API ────────────────────────────────────────────────────────────

    def run(self) -> MLLabResult:
        try:
            ensure_dir(self.run_dir)

            # ── Step 1: acquire data ──────────────────────────────────────────
            if self.source_type == ml_const.ML_SOURCE_DESCRIBE:
                df = self._generate_from_query()
            else:
                df = self._load_from_upload()

            # ── Step 2: plant target (describe source only) ───────────────────
            if self.source_type == ml_const.ML_SOURCE_DESCRIBE:
                df = self._plant_target(df)
            else:
                # Upload source: target must already exist
                if self.target_col not in df.columns:
                    raise ValueError(msg_const.MSG_ML_TARGET_NOT_FOUND.format(
                        col=self.target_col
                    ))

            # ── Step 3: train/test split + save CSVs ─────────────────────────
            train_df, test_df, train_path, test_path = self._split_and_save(df)

            # ── Step 4: ML check ──────────────────────────────────────────────
            check_label = (
                "Planted signal learnable?" if self.source_type == ml_const.ML_SOURCE_DESCRIBE
                else "Real data (train on synthetic, test on real)"
            )
            ml_check = run_ml_check(
                train_df=train_df,
                test_df=test_df,
                target_col=self.target_col,
                task_type=self.task_type,
                seed=self.seed,
                label=check_label,
            )

            # ── Step 5: write start_here.py and DATA_CARD.md ─────────────────
            self._write_starter_script(self.target_col)
            resolved_drivers = (
                self.drivers or
                [c for c in df.columns
                 if c != self.target_col and not self._is_key_col(df[c], c)
                 and pd.api.types.is_numeric_dtype(df[c])]
            )
            self._write_data_card(df, ml_check, resolved_drivers)

            # ── Step 6: save metadata ─────────────────────────────────────────
            meta = {
                "module": common.MODULE_ML_LAB,
                "source_type": self.source_type,
                "task_type": self.task_type,
                "target_col": self.target_col,
                "drivers": resolved_drivers,
                "signal_strength": self.signal_strength,
                "class_balance": self.class_balance,
                "label_noise": self.label_noise,
                "seed": self.seed,
                "train_ratio": self.train_ratio,
                "n_rows": len(df),
                "train_rows": len(train_df),
                "test_rows": len(test_df),
                "ml_check": ml_check,
                "status": True,
                "row_counts": {"train": len(train_df), "test": len(test_df)},
                "mode": "query" if self.source_type == ml_const.ML_SOURCE_DESCRIBE else "data",
            }
            write_json_file(
                os.path.join(self.run_dir, ml_const.ML_METADATA_FILE), meta
            )

            preview = train_df.head(50).to_dict(orient="records")

            logging.info(
                f"MLLabPipeline: done — run_id={self.run_id} "
                f"train={len(train_df)} test={len(test_df)} "
                f"ml_check_score={ml_check.get('score')}"
            )

            return MLLabResult(
                run_id=self.run_id,
                source_type=self.source_type,
                task_type=self.task_type,
                target_col=self.target_col,
                train_csv_path=train_path,
                test_csv_path=test_path,
                ml_check=ml_check,
                preview=preview,
                train_rows=len(train_df),
                test_rows=len(test_df),
                seed=self.seed,
            )

        except (ValueError, HTTPError):
            raise
        except Exception as e:
            raise HackDataException(e, sys)

    # ── data acquisition helpers ──────────────────────────────────────────────

    def _generate_from_query(self) -> pd.DataFrame:
        """Run the existing generation pipeline for query source."""
        from hackdata.pipeline.generation_pipeline import GenerationPipeline
        from hackdata.entity.request_entity import GenerationRequest
        from hackdata.constants import generation as gen_const, locales as loc_const

        gen_req = GenerationRequest(
            module=common.MODULE_TABULAR,
            mode=common.MODE_QUERY,
            query=self.query,
            n_rows=self.n_rows,
            seed=self.seed,
        )

        # Run in a sub-directory so the ML run stays in its own folder.
        # GenerationPipeline creates its own RunConfig with a new run_id;
        # we read the output CSV back into memory.
        pipeline = GenerationPipeline(gen_req)
        result = pipeline.run()

        # Collect all generated CSVs into a single DataFrame
        frames = []
        for table_name, csv_path in result.gen_artifact.table_file_paths.items():
            if os.path.exists(csv_path):
                frames.append(pd.read_csv(csv_path))

        if not frames:
            raise ValueError("Generation pipeline produced no output CSV.")

        # Use first (primary) table; relational tables are separate concern
        df = frames[0]
        if len(df) < ml_const.ML_MIN_ROWS:
            raise ValueError(msg_const.MSG_ML_ROWS_TOO_LOW.format(
                n=len(df), min_rows=ml_const.ML_MIN_ROWS
            ))
        return df

    def _load_from_upload(self) -> pd.DataFrame:
        """Read data from a previously uploaded/generated CSV."""
        if not self.upload_run_id:
            raise ValueError("upload_run_id is required for source_type='upload'.")
        csv_path = self._find_source_csv(self.upload_run_id)
        df = pd.read_csv(csv_path)
        if len(df) < ml_const.ML_MIN_ROWS:
            raise ValueError(msg_const.MSG_ML_ROWS_TOO_LOW.format(
                n=len(df), min_rows=ml_const.ML_MIN_ROWS
            ))
        return df


# ── avoid circular import from typing HTTPError ───────────────────────────────
class HTTPError(Exception):
    pass
