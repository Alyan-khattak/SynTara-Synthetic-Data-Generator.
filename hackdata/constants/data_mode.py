# ═══════════════════════════════════════════════════════════════════
# data_mode.py — inference thresholds, copula params, caps
# ═══════════════════════════════════════════════════════════════════
# IMP: DM_MAX_UPLOAD_BYTES is 20 MB here (CLAUDE.md cap is 10 MB for the API
#      layer — the API layer enforces its own limit; this is the data-mode
#      pipeline's internal cap applied after the upload is accepted).

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
DM_MAX_UPLOAD_BYTES: int = 20 * 1024 * 1024
DM_MIN_ROWS_WARN: int = 50
DM_MIN_ROWS_REFUSE: int = 10
DM_ENCODINGS_TO_TRY: tuple = ("utf-8", "utf-8-sig", "latin-1", "cp1252")
DM_DELIMITERS_TO_TRY: tuple = (",", ";", "\t")
DM_CLASSIFICATION_MIN_GROUP_ROWS: int = 30
DM_MAX_CONDITION_BINS: int = 5
