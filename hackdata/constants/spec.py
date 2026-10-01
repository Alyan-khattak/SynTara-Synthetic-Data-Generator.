# ═══════════════════════════════════════════════════════════════════
# spec.py — generator, rule and distribution vocabularies
# ═══════════════════════════════════════════════════════════════════
# IMP: Pydantic validators in spec_entity.py check membership against
#      these tuples — add a new generator here before using it in a spec.

SPEC_VERSION: str = "1"
SPEC_GENERATORS: tuple = (
    "sequence", "uuid", "int_range", "float_range", "money", "categorical",
    "boolean", "date_range", "date_offset", "pool", "email", "phone", "faker",
    "expr", "aggregate", "conditional", "text", "national_id", "card",
)
SPEC_RULES: tuple = (
    "not_null", "unique", "range", "after", "sum_of", "equals_expr", "running_balance",
    "max_children", "min_children", "status_from_dates", "group_order",
    "bound_by_group", "share_within",
)
SPEC_DISTRIBUTIONS: tuple = ("uniform", "normal", "lognormal", "poisson", "recent_weighted")
SPEC_EXPR_ALLOWED_FUNCTIONS: tuple = ("round", "min", "max", "abs", "int", "float")
SPEC_FAKER_ALLOWLIST: tuple = ("name", "address", "company", "job", "text")  # extend deliberately
