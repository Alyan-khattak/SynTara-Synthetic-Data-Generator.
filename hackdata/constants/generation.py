# ═══════════════════════════════════════════════════════════════════
# generation.py — seeds, caps, sizes, edge-case defaults
# ═══════════════════════════════════════════════════════════════════

GEN_MAX_ROWS_PER_TABLE: int = 100_000
GEN_DEFAULT_N_ROWS: int = 1_000              # default when caller does not specify n_rows
GEN_DEFAULT_MASTER_SEED: int = 42
GEN_DEFAULT_NULL_RATE: float = 0.02
GEN_DEFAULT_OUTLIER_RATE: float = 0.005
GEN_OUTLIER_SCALE_MIN: float = 3.0
GEN_MAX_CONDITION_GROUPS: int = 5
GEN_SEED_DIGEST_SIZE: int = 8                 # blake2b bytes
GEN_SEED_SEPARATOR: str = "|"
GEN_MAX_PARENT_HOPS: int = 2
GEN_SEASONALITY_MAX_RESAMPLE_ROUNDS: int = 5
GEN_ROUNDING_MODE: str = "half_up"
GEN_MAX_RUNS_KEPT_TEMP: int = 10
GEN_MASK_CHAR: str = "*"
GEN_NOISE_DEFAULT_SCALE: float = 0.0
GEN_POOL_SIZE_MIN: int = 200
GEN_POOL_SIZE_MAX: int = 300
GEN_OFFLINE_FALLBACK_INT_MAX: int = 1_000   # int_range max used by offline_fallback spec

# ── Sensitive-field safety ────────────────────────────────────────
# Published processor test card numbers — safe to ship, designed for testing.
# Sources: Stripe (https://stripe.com/docs/testing), Adyen test cards.
# IMP: gen_card ONLY draws from this list. CVV and expiry are never generated.
GEN_CARD_TEST_NUMBERS: tuple = (
    "4111111111111111",   # Visa test card
    "5500005555555559",   # Mastercard test card
    "378282246310005",    # Amex test card
    "6011111111111117",   # Discover test card
)
GEN_CARD_MASK_SUFFIX_LEN: int = 4   # digits kept visible in masked card output

# Lowercase substrings matched against column names in upload mode to detect
# columns that should be masked before returning synthetic data to the user.
# ── Messiness caps (Step C) ───────────────────────────────────────
# IMP: rates above these are rejected at the API boundary with a clear message.
GEN_MAX_MISSING_RATE: float = 0.50     # max null injection rate per column
GEN_MAX_OUTLIER_RATE: float = 0.20     # max outlier injection rate per numeric column
GEN_MAX_IMBALANCE_RATE: float = 0.95   # max fraction the dominant class may hold
GEN_OUTLIER_SIGMA: float = 3.5         # outlier placed at mean ± sigma * std

GEN_SENSITIVE_COL_PATTERNS: tuple = (
    "card", "cc_num", "credit", "pan", "iban",
    "account_no", "account_number",
    "national_id", "cnic", "nid", "ssn", "passport",
    "email", "phone", "mobile",
)
