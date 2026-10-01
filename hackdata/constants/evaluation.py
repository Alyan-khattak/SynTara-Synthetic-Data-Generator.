# ═══════════════════════════════════════════════════════════════════
# evaluation.py — metric params, weights, thresholds
# ═══════════════════════════════════════════════════════════════════
# IMP: EVAL_RF_N_JOBS is forced to 1 — combining n_jobs>1 RandomForest
#      with heavy init can deadlock; see TRD section 15.5 bug list.

EVAL_WEIGHTS: dict = {"validity": 0.25, "fidelity": 0.25, "utility": 0.30, "privacy": 0.20}
EVAL_RF_N_ESTIMATORS: int = 100
EVAL_RF_MAX_DEPTH: int = 12
EVAL_RF_N_JOBS: int = 1
EVAL_UTILITY_MAX_TRAIN_ROWS: int = 20_000
EVAL_TARGET_MIN_CLASSES: int = 2
EVAL_TARGET_MAX_CLASSES: int = 10
EVAL_ONEHOT_MAX_CARDINALITY: int = 20
EVAL_PRIVACY_MAX_SAMPLE_ROWS: int = 5_000
EVAL_PRIVACY_NN_FLAG_THRESHOLD: float = 0.8
EVAL_PRIVACY_EXACT_MATCH_THRESHOLD: float = 0.05
EVAL_CORRELATION_METHOD: str = "spearman"
EVAL_SCORE_SCALE: int = 100

# Weights for the fidelity sub-score: KS stat, Spearman correlation diff, TVD.
# IMP: must sum to 1.0 — verified at definition time.
FIDELITY_KS_WEIGHT: float = 0.4
FIDELITY_CORR_WEIGHT: float = 0.3
FIDELITY_TVD_WEIGHT: float = 0.3

# Weights for the utility sub-score: TSTR and TRTS.
# IMP: must sum to 1.0.
UTILITY_TSTR_WEIGHT: float = 0.5
UTILITY_TRTS_WEIGHT: float = 0.5

# Weights for the privacy sub-score: exact match rate and DCR.
# IMP: must sum to 1.0.
PRIVACY_EXACT_WEIGHT: float = 0.4
PRIVACY_DCR_WEIGHT: float = 0.6
# Small epsilon guards against division by zero in DCR ratio.
PRIVACY_DCR_EPSILON: float = 1e-9

# Column name fragments used to identify the target column for utility evaluation.
UTILITY_TARGET_KEYWORDS: list = ["target", "label", "churn", "fraud", "default", "outcome", "class"]

EVAL_REFERENCE_REAL_HOLDOUT: str = "vs. real hold-out"
EVAL_REFERENCE_REAL_TRAIN: str = "vs. real train"
EVAL_REFERENCE_SPEC: str = "vs. spec"
EVAL_REFERENCE_STRUCTURAL: str = "structural"
