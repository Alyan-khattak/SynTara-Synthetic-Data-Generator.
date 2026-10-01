# ═══════════════════════════════════════════════════════════════════
# api.py — API prefix, cache sizes, status names
# ═══════════════════════════════════════════════════════════════════

API_PREFIX: str = "/api"
API_PREVIEW_ROWS: int = 10_000
API_STATUS_GENERATED: str = "generated"
API_STATUS_FAILED: str = "failed"
API_SCORE_STATUS_PENDING: str = "pending"
API_SCORE_STATUS_PARTIAL: str = "partial"
API_SCORE_STATUS_DONE: str = "done"

UPLOAD_ID_HEX_LENGTH: int = 12  # chars of uuid4 hex used in upload_id

# Permitted file extensions for data-mode uploads.
ALLOWED_EXTENSIONS: frozenset = frozenset({".csv", ".json", ".parquet"})

HTTP_200_OK: int = 200
HTTP_400_BAD_REQUEST: int = 400
HTTP_404_NOT_FOUND: int = 404
HTTP_413_REQUEST_ENTITY_TOO_LARGE: int = 413
HTTP_500_INTERNAL_SERVER_ERROR: int = 500

# Maximum upload size enforced at the API boundary (CLAUDE.md: 10 MB cap)
MAX_UPLOAD_BYTES: int = 10 * 1024 * 1024
