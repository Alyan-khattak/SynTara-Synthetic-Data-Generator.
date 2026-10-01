# ═══════════════════════════════════════════════════════════════════
# validation.py — tolerances, tiers, defect kinds
# ═══════════════════════════════════════════════════════════════════

VAL_TIER_STRUCTURAL: int = 1
VAL_TIER_RULES: int = 2
VAL_TIER_COHERENCE: int = 3
VAL_AGGREGATE_TOLERANCE_MINOR_UNITS: int = 1
VAL_COHERENCE_MIN_GROUP_ROWS: int = 30
VAL_COHERENCE_TOLERANCE_STD_ERRORS: float = 3.0
VAL_COHERENCE_TOLERANCE_MIN_PP: float = 0.01
VAL_DEFECT_KINDS: tuple = (
    "orphan_fk", "duplicate_pk", "missing_parent", "null_in_not_null",
    "negative_quantity", "wrong_total", "bad_status", "group_bound",
    "cardinality_violation", "totals_mismatch",
)
