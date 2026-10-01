# ═══════════════════════════════════════════════════════════════════
# spec_entity.py — Pydantic models for the closed spec vocabulary
# ═══════════════════════════════════════════════════════════════════
# Implements TRD 6.3: the contract between the LLM/user and the
# generation engine. Every vocabulary field (gen, dist, rules,
# faker_field, module) is validated against the tuples in
# constants/spec.py — vocabulary is defined once there; here we
# just enforce it at the boundary.
###==============================================================
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, field_validator

from hackdata.constants import spec as spec_const, common, messages, validation


# ---------------- SEGMENT / SEASONALITY (AR 8.4.1 / AR 8.12) ----------------

class ConditionSegment(BaseModel):
    """
    One segment inside a conditioned_by block.

    when      → filter expression evaluated via simpleeval (never eval)
    overrides → ColumnSpec fields to apply for rows matching `when`

    DRY RUN:
        when="category == 'A'", overrides={"min": 100, "max": 500}
        → rows where category is A get amount drawn from [100, 500]
    """

    model_config = ConfigDict(extra="ignore")

    when: str                          # IMP: eval'd by simpleeval only; plain eval is forbidden
    overrides: Dict[str, Any] = {}


class SeasonalityPeriod(BaseModel):
    """
    One period in a seasonality weight profile (AR 8.12).

    start / end  → "MM-DD" strings; engine normalises weights to sum 1.0
    weight       → relative weight for date draws in this window
    """

    model_config = ConfigDict(extra="ignore")

    start: str    # "MM-DD"
    end: str      # "MM-DD"
    weight: float


# ---------------- COLUMN SPEC ----------------

class ColumnSpec(BaseModel):
    """
    Spec for a single generated column.

    ColumnSpec  ──▶  DataGenerator  ──▶  column values in DataFrame

    Only `name` and `gen` are required; everything else is an optional
    modifier consumed by the matching generator in column_generators.py.
    """

    model_config = ConfigDict(extra="ignore")

    name: str
    gen: str                                   # must be in SPEC_GENERATORS

    # numeric bounds (money, int_range, float_range, date_range, date_offset)
    min: Optional[Any] = None
    max: Optional[Any] = None

    # categorical values list or pool reference
    values: Optional[List[Any]] = None

    # shape of numeric draws
    dist: Optional[str] = None                # must be in SPEC_DISTRIBUTIONS

    # validation rules applied after generation
    rules: List[str] = []                     # each item must be in SPEC_RULES

    # expression body for "expr" generator (simpleeval only)
    expr: Optional[str] = None

    # FK reference: "table.column"
    ref: Optional[str] = None

    # quality knobs — engine uses GEN_DEFAULT_* when None
    null_rate: Optional[float] = None
    outlier_rate: Optional[float] = None
    noise_scale: Optional[float] = None
    # class_imbalance: fraction the dominant class holds (0.0–1.0); only for categorical columns
    class_imbalance: Optional[float] = None

    # faker passthrough — allowed only for fields in SPEC_FAKER_ALLOWLIST
    faker_field: Optional[str] = None

    # conditional overrides by segment (AR 8.4.1)
    conditioned_by: Optional[List[ConditionSegment]] = None

    # date-weight profile (AR 8.12)
    seasonality: Optional[List[SeasonalityPeriod]] = None

    # IMP: validators run after type coercion; they raise ValueError on unknown vocab

    @field_validator("gen")
    @classmethod
    def gen_must_be_known(cls, v: str) -> str:
        if v not in spec_const.SPEC_GENERATORS:
            raise ValueError(
                messages.MSG_INVALID_GEN.format(value=v, allowed=spec_const.SPEC_GENERATORS)
            )
        return v

    @field_validator("dist")
    @classmethod
    def dist_must_be_known(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in spec_const.SPEC_DISTRIBUTIONS:
            raise ValueError(
                messages.MSG_INVALID_DIST.format(value=v, allowed=spec_const.SPEC_DISTRIBUTIONS)
            )
        return v

    @field_validator("rules", mode="before")
    @classmethod
    def rules_must_be_known(cls, v: List[str]) -> List[str]:
        # IMP: mode="before" so we see the raw list before Pydantic wraps each item
        for rule in v:
            if rule not in spec_const.SPEC_RULES:
                raise ValueError(
                    messages.MSG_INVALID_RULE.format(value=rule, allowed=spec_const.SPEC_RULES)
                )
        return v

    @field_validator("faker_field")
    @classmethod
    def faker_field_must_be_allowed(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in spec_const.SPEC_FAKER_ALLOWLIST:
            raise ValueError(
                messages.MSG_INVALID_FAKER_FIELD.format(
                    value=v, allowed=spec_const.SPEC_FAKER_ALLOWLIST
                )
            )
        return v


# ---------------- TABLE-LEVEL STRUCTURES ----------------

class Cardinality(BaseModel):
    """
    Child-rows-per-parent distribution for a relational table.

    DRY RUN:
        min_per_parent=2, max_per_parent=5, distribution="uniform"
        → each parent gets between 2 and 5 children, drawn uniformly
    """

    model_config = ConfigDict(extra="ignore")

    min_per_parent: int
    max_per_parent: int
    distribution: str = "uniform"             # must be in SPEC_DISTRIBUTIONS

    @field_validator("distribution")
    @classmethod
    def distribution_must_be_known(cls, v: str) -> str:
        if v not in spec_const.SPEC_DISTRIBUTIONS:
            raise ValueError(
                messages.MSG_INVALID_CARDINALITY_DIST.format(
                    value=v, allowed=spec_const.SPEC_DISTRIBUTIONS
                )
            )
        return v


class ParentSpec(BaseModel):
    """FK relationship declaration: parent table, the key column, and cardinality bounds."""

    model_config = ConfigDict(extra="ignore")

    table: str            # parent table name
    key: str              # FK column name in THIS (child) table
    cardinality: Cardinality


class EdgeCase(BaseModel):
    """
    A defect type and injection rate, used by DatasetCorruptor for demo / tests.

    kind must be one of VAL_DEFECT_KINDS so the validator can route it.
    rate is the fraction of rows to affect (0.0 – 1.0).
    """

    model_config = ConfigDict(extra="ignore")

    kind: str             # must be in VAL_DEFECT_KINDS
    rate: float

    @field_validator("kind")
    @classmethod
    def kind_must_be_known(cls, v: str) -> str:
        if v not in validation.VAL_DEFECT_KINDS:
            raise ValueError(
                messages.MSG_INVALID_DEFECT_KIND.format(
                    value=v, allowed=validation.VAL_DEFECT_KINDS
                )
            )
        return v


class TableSpec(BaseModel):
    """Spec for one table: name, target row count, columns, and optional FK / edge-case info."""

    model_config = ConfigDict(extra="ignore")

    name: str
    n_rows: int
    columns: List[ColumnSpec]
    parent: Optional[ParentSpec] = None
    edge_cases: Optional[List[EdgeCase]] = None


# ---------------- DOCUMENT SPEC ----------------

class DocumentSpec(BaseModel):
    """Spec for a documents-module run (invoices, statements)."""

    model_config = ConfigDict(extra="ignore")

    doc_type: str
    count: int


# ---------------- TOP-LEVEL SPEC ----------------

class Spec(BaseModel):
    """
    Top-level spec: the frozen contract between LLM/user and the engine.

    version       → default SPEC_VERSION; checked during repair to detect schema drift
    module        → one of MODULE_TABULAR / MODULE_RELATIONAL / MODULE_DOCUMENTS
    tables        → list of table specs (empty list for documents-only runs)
    document_spec → required when module == MODULE_DOCUMENTS

    DRY RUN:
        {"version": "1", "module": "tabular",
         "tables": [{"name": "orders", "n_rows": 1000,
                     "columns": [{"name": "id", "gen": "sequence"},
                                 {"name": "amount", "gen": "money",
                                  "min": 100, "max": 50000, "rules": ["not_null"]}]}]}
        ──▶ Spec(version="1", module="tabular", tables=[TableSpec(name="orders", ...)])
    """

    model_config = ConfigDict(extra="ignore")

    version: str = spec_const.SPEC_VERSION      # IMP: default keeps old specs valid after version bumps
    module: str
    tables: List[TableSpec] = []
    document_spec: Optional[DocumentSpec] = None

    @field_validator("module")
    @classmethod
    def module_must_be_known(cls, v: str) -> str:
        allowed = (common.MODULE_TABULAR, common.MODULE_RELATIONAL, common.MODULE_DOCUMENTS)
        if v not in allowed:
            raise ValueError(
                messages.MSG_INVALID_MODULE.format(value=v, allowed=allowed)
            )
        return v


# ---------------- SELF-CHECK ----------------
if __name__ == "__main__":
    # ponytail: minimal runnable check — parse a valid spec, reject an invalid one
    import sys

    valid_dict = {
        "version": "1",
        "module": "tabular",
        "tables": [{"name": "t", "n_rows": 100, "columns": [{"name": "id", "gen": "sequence"}]}],
    }
    s = Spec(**valid_dict)
    assert s.tables[0].name == "t", "valid spec should parse"
    print("Valid spec parsed:", s.tables[0].name)

    try:
        Spec(
            **{
                "version": "1",
                "module": "tabular",
                "tables": [
                    {"name": "t", "n_rows": 10, "columns": [{"name": "x", "gen": "INVALID_TYPE"}]}
                ],
            }
        )
        print("ERROR: should have raised")
        sys.exit(1)
    except Exception as e:
        print("Correctly rejected invalid gen:", str(e)[:80])

    print("Self-check passed.")
