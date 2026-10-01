# ═══════════════════════════════════════════════════════════════════
# data_mode.py — inference thresholds, copula params, caps
# ═══════════════════════════════════════════════════════════════════

DM_TRAIN_TEST_SPLIT_RATIO: float = 0.2
DM_ID_UNIQUE_RATIO: float = 0.98
DM_PARSE_SUCCESS_RATIO: float = 0.90
DM_CATEGORICAL_MAX_DISTINCT_FLOOR: int = 20
DM_CATEGORICAL_MAX_DISTINCT_FRACTION: float = 0.05
DM_FREE_TEXT_MIN_MEAN_LENGTH: int = 30
DM_FK_CONTAINMENT_MIN: float = 0.99
DM_RULE_MINING_MIN_SUPPORT: float = 0.99
DM_COPULA_QUANTILE_GRID_SIZE: int = 512
DM_COPULA_EIGEN_EPSILON: float = 1e-6
DM_COPULA_TIME_BOX_HOURS: float = 1.5
# DM_MAX_UPLOAD_BYTES removed — api_const.MAX_UPLOAD_BYTES (10 MB) is the single source
DM_MIN_ROWS_WARN: int = 50
DM_MIN_ROWS_REFUSE: int = 10
DM_ENCODINGS_TO_TRY: tuple = ("utf-8", "utf-8-sig", "latin-1", "cp1252")
DM_DELIMITERS_TO_TRY: tuple = (",", ";", "\t")
DM_CLASSIFICATION_MIN_GROUP_ROWS: int = 30
DM_MAX_CONDITION_BINS: int = 5

# ── Step A: row count cap (8 GB RAM; 50k rows × typical col count stays safe) ──
DM_MAX_SYNTH_ROWS: int = 50_000
DM_UPLOAD_PREVIEW_ROWS: int = 20   # rows of uploaded data shown in UI

# ── Step B: realism / noise caps ────────────────────────────────────────────
DM_MAX_MISSING_RATE: float = 0.50   # fraction of cells to null out
DM_MAX_OUTLIER_RATE: float = 0.20   # fraction of numeric rows to push to outlier range
DM_MAX_NOISE_LEVEL: float = 1.0     # fraction of column std to add as Gaussian noise
DM_OUTLIER_SIGMA: float = 3.5       # std multiplier for outlier injection
DM_MAX_CORR_ADJ: float = 1.0        # max absolute value of correlation_adjustment

# ── Step C: profiler caps ────────────────────────────────────────────────────
DM_MAX_PROFILE_COLS: int = 50       # heatmap skips columns beyond this cap
DM_MAX_FINDINGS: int = 10           # plain-language finding sentences cap
DM_TOP_CATEGORIES: int = 10         # max categories shown per categorical column
