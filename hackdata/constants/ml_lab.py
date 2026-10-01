# ═══════════════════════════════════════════════════════════════════
# ml_lab.py — ML Lab module constants
# ═══════════════════════════════════════════════════════════════════

# ── source types ─────────────────────────────────────────────────────────────
ML_SOURCE_DESCRIBE: str = "describe"      # user writes a text query → LLM spec
ML_SOURCE_UPLOAD:   str = "upload"        # user uploads a CSV (no model sees it)

# ── task types ────────────────────────────────────────────────────────────────
ML_TASK_CLASSIFICATION: str = "classification"
ML_TASK_REGRESSION:     str = "regression"
ML_TASK_TYPES: tuple = (ML_TASK_CLASSIFICATION, ML_TASK_REGRESSION)

# ── target signal ─────────────────────────────────────────────────────────────
ML_MAX_SIGNAL:     float = 1.0   # signal_strength upper bound
ML_DEFAULT_SIGNAL: float = 0.7   # sensible default for "clearly learnable" pattern

# ── class balance (classification only) ──────────────────────────────────────
ML_MIN_CLASS_BALANCE: float = 0.05   # positive-class fraction lower bound
ML_MAX_CLASS_BALANCE: float = 0.95   # positive-class fraction upper bound
ML_DEFAULT_CLASS_BALANCE: float = 0.5

# ── label noise ──────────────────────────────────────────────────────────────
ML_MAX_LABEL_NOISE: float = 0.30    # fraction of labels that may be flipped/noised
ML_DEFAULT_LABEL_NOISE: float = 0.0

# ── train / test split ───────────────────────────────────────────────────────
ML_DEFAULT_TRAIN_RATIO: float = 0.8   # 80 % train, 20 % test
ML_MIN_TRAIN_RATIO:     float = 0.5
ML_MAX_TRAIN_RATIO:     float = 0.95

# ── row caps ─────────────────────────────────────────────────────────────────
ML_MIN_ROWS: int = 20        # refuse run below this
ML_MAX_ROWS: int = 100_000   # cap to protect 8 GB RAM limit

# ── ML checker caps ───────────────────────────────────────────────────────────
ML_CHECKER_RF_N_ESTIMATORS: int = 50    # small forest — fast enough for demo
ML_CHECKER_RF_MAX_DEPTH:    int = 6
ML_CHECKER_N_JOBS:          int = 1     # see TRD 15.5 – n_jobs > 1 can deadlock
ML_CHECKER_MAX_ONEHOT_CATS: int = 20    # high-cardinality cats are label-encoded
ML_CHECKER_MIN_ROWS:        int = 10    # below this, skip check and warn

# ── export ────────────────────────────────────────────────────────────────────
ML_EXPORT_DIR_NAME: str  = "ml_export"
ML_TRAIN_FILE:      str  = "train.csv"
ML_TEST_FILE:       str  = "test.csv"
ML_STARTER_FILE:    str  = "start_here.py"
ML_DATACARD_FILE:   str  = "DATA_CARD.md"
ML_METADATA_FILE:   str  = "run_metadata.json"
