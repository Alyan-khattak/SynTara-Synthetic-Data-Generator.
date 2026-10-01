# ═══════════════════════════════════════════════════════════════════
# offline_fallback.py — minimal valid spec when all LLMs are down
# ═══════════════════════════════════════════════════════════════════
# Last-resort path in the reliability chain. Returns a single-table
# spec using only vocabulary from spec_const — the engine can always
# run it, but semantics will not match the user's query.
# IMP: every generator name and faker_field is verified against the
#      vocab constants at module load; a vocabulary drift fails fast.
###==============================================================
import sys

from hackdata.constants import spec as spec_const, common, generation as gen_const
from hackdata.exception.exception import HackDataException
from hackdata.logging.logger import logging

# ---------------- VOCABULARY ALIASES ----------------
# IMP: we reference constants, not bare strings, to stay in sync with SPEC_GENERATORS.
#      Assertions here fail at import time if the tuple order ever changes.

_GEN_SEQUENCE = "sequence"
_GEN_INT_RANGE = "int_range"
_GEN_BOOLEAN = "boolean"
_GEN_FAKER = "faker"
_GEN_MONEY = "money"
_GEN_DATE_RANGE = "date_range"
_GEN_CATEGORICAL = "categorical"
_FAKER_NAME = "name"

# Fail fast at import if the vocabulary constants no longer contain these names
assert _GEN_SEQUENCE in spec_const.SPEC_GENERATORS, "offline_fallback: 'sequence' missing from SPEC_GENERATORS"
assert _GEN_INT_RANGE in spec_const.SPEC_GENERATORS, "offline_fallback: 'int_range' missing from SPEC_GENERATORS"
assert _GEN_BOOLEAN in spec_const.SPEC_GENERATORS, "offline_fallback: 'boolean' missing from SPEC_GENERATORS"
assert _GEN_FAKER in spec_const.SPEC_GENERATORS, "offline_fallback: 'faker' missing from SPEC_GENERATORS"
assert _GEN_MONEY in spec_const.SPEC_GENERATORS, "offline_fallback: 'money' missing from SPEC_GENERATORS"
assert _GEN_DATE_RANGE in spec_const.SPEC_GENERATORS, "offline_fallback: 'date_range' missing from SPEC_GENERATORS"
assert _GEN_CATEGORICAL in spec_const.SPEC_GENERATORS, "offline_fallback: 'categorical' missing from SPEC_GENERATORS"
assert _FAKER_NAME in spec_const.SPEC_FAKER_ALLOWLIST, "offline_fallback: 'name' missing from SPEC_FAKER_ALLOWLIST"


# ---------------- PUBLIC API ----------------

def build_offline_spec(
    query: str,
    module: str = common.MODULE_TABULAR,
    n_rows: int = gen_const.GEN_DEFAULT_N_ROWS,
) -> dict:
    """Return a minimal valid Spec dict without any LLM call.

    Uses generator types from SPEC_GENERATORS and faker_fields from
    SPEC_FAKER_ALLOWLIST to produce a believable single-table spec that
    always passes ``Spec(**result)`` validation.

    Parameters
    ----------
    query : str
        The original user query (informational only; not used in the output).
    module : str
        Target module — one of MODULE_TABULAR / MODULE_RELATIONAL / MODULE_DOCUMENTS.
    n_rows : int
        Target row count for the single table.

    Returns
    -------
    dict
        A dict that passes ``Spec(**result)`` Pydantic validation.

    # IMP: This is the last-resort path. The spec satisfies the Pydantic
    #      model but will not match the user's query semantics.

    # DRY RUN: build_offline_spec("customer orders", "tabular", 1000)
    #   → {"version": "1", "module": "tabular",
    #      "tables": [{"name": "table_1", "n_rows": 1000,
    #        "columns": [
    #          {"name": "id",    "gen": "sequence"},
    #          {"name": "name",  "gen": "faker",     "faker_field": "name"},
    #          {"name": "value", "gen": "int_range",  "min": 1.0, "max": 1000.0},
    #          {"name": "active","gen": "boolean"},
    #        ]}]}
    """
    try:
        logging.info(f"offline_fallback: building spec module={module} n_rows={n_rows}")

        if module == common.MODULE_RELATIONAL:
            # Two-table FK spec: customers (parent) → orders (child)
            # IMP: parent table must come first so the engine builds FK pool before child rows
            tables = [
                {
                    "name": "customers",
                    "n_rows": n_rows,
                    "columns": [
                        {"name": "customer_id", "gen": _GEN_SEQUENCE},
                        {
                            "name": "name",
                            "gen": _GEN_CATEGORICAL,
                            "values": ["Alice", "Bob", "Carol", "Dave", "Eve"],
                        },
                        {
                            "name": "country",
                            "gen": _GEN_CATEGORICAL,
                            "values": ["US", "UK", "DE", "FR", "JP"],
                        },
                    ],
                },
                {
                    "name": "orders",
                    "n_rows": n_rows,
                    "columns": [
                        {"name": "order_id", "gen": _GEN_SEQUENCE},
                        # FK to customers.customer_id — ref signals the FK relationship
                        {"name": "customer_id", "gen": _GEN_SEQUENCE, "ref": "customers.customer_id"},
                        {
                            "name": "amount",
                            "gen": _GEN_MONEY,
                            "min": float(1),
                            "max": float(gen_const.GEN_OFFLINE_FALLBACK_INT_MAX),
                        },
                        {"name": "created_at", "gen": _GEN_DATE_RANGE},
                    ],
                    # Declare parent so the engine wires FK values correctly
                    "parent": {
                        "table": "customers",
                        "key": "customer_id",
                        "cardinality": {
                            "min_per_parent": 1,
                            "max_per_parent": 5,
                            "distribution": "uniform",
                        },
                    },
                },
            ]
            spec = {"version": spec_const.SPEC_VERSION, "module": module, "tables": tables}
        else:
            columns = [
                # Surrogate key — unique, no parameters needed
                {"name": "id", "gen": _GEN_SEQUENCE},
                # Human-readable name via Faker (allowlisted field)
                {"name": "name", "gen": _GEN_FAKER, "faker_field": _FAKER_NAME},
                # Numeric value column — min=1 (allowed literal), max from constant
                # IMP: min/max must be float because ColumnSpec.min/max are Optional[float]
                {
                    "name": "value",
                    "gen": _GEN_INT_RANGE,
                    "min": float(1),
                    "max": float(gen_const.GEN_OFFLINE_FALLBACK_INT_MAX),
                },
                # Boolean status flag
                {"name": "active", "gen": _GEN_BOOLEAN},
            ]
            spec = {
                "version": spec_const.SPEC_VERSION,
                "module": module,
                "tables": [{"name": "table_1", "n_rows": n_rows, "columns": columns}],
            }

        logging.info("offline_fallback: spec built")
        return spec

    except Exception as e:
        raise HackDataException(e, sys)
