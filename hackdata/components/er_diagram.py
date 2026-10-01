# ═══════════════════════════════════════════════════════════════════
# er_diagram.py — pure function: validated relational spec → Mermaid erDiagram text
# ═══════════════════════════════════════════════════════════════════
# Lives in components/ (layer: components) but has no I/O and no logging
# so it is directly unit-testable.  Called by the schema API route.
###==============================================================
from typing import Optional

from hackdata.constants import messages as msg_const
from hackdata.entity.spec_entity import Spec, TableSpec, ColumnSpec


# IMP: map ColumnSpec.gen values to Mermaid-compatible type tokens
_GEN_TO_TYPE: dict = {
    "sequence":    "int",
    "uuid":        "string",
    "int_range":   "int",
    "float_range": "float",
    "money":       "float",
    "categorical": "string",
    "boolean":     "boolean",
    "date_range":  "date",
    "date_offset": "date",
    "pool":        "string",
    "email":       "string",
    "phone":       "string",
    "faker":       "string",
    "expr":        "string",
    "aggregate":   "float",
    "conditional": "string",
    "text":        "string",
    "national_id": "string",
}


def _is_pk(col: ColumnSpec) -> bool:
    """Infer primary key: sequence/uuid generator with unique constraint."""
    if col.gen in ("sequence", "uuid"):
        return True
    if "unique" in col.rules and "not_null" in col.rules:
        return True
    return False


def _cardinality_notation(table: TableSpec) -> str:
    """Return Mermaid cardinality notation for a child→parent relationship.

    DRY RUN:
        min_per_parent=1, max_per_parent=5  →  ||--o{   (one-to-many)
        min_per_parent=0, max_per_parent=1  →  ||--o|   (zero or one)
        min_per_parent=1, max_per_parent=1  →  ||--||   (exactly one)
    """
    if table.parent is None:
        return "||--o{"
    c = table.parent.cardinality
    min_c = c.min_per_parent
    max_c = c.max_per_parent
    # left side (parent): always exactly one
    left = "||"
    # right side (child)
    if max_c == 1:
        right = "o|" if min_c == 0 else "||"
    else:
        right = "o{" if min_c == 0 else "|{"
    return f"{left}--{right}"


def spec_to_mermaid(spec: Spec) -> str:
    """Convert a validated relational Spec into Mermaid erDiagram text.

    Parameters
    ----------
    spec : Spec
        Must be module == "relational" with >= 2 tables and >= 1 FK relationship.

    Returns
    -------
    str
        Mermaid erDiagram source, ready to pass to mermaid.render().

    Raises
    ------
    ValueError
        When the spec is not relational or has no FK relationships.

    DRY RUN:
        spec.tables = [customers (PK: id), orders (FK: customer_id → customers)]
        →
        erDiagram
            customers {
                int id PK
                string name
            }
            orders {
                int order_id PK
                int customer_id FK
                float amount
            }
            customers ||--o{ orders : "has"
    """
    from hackdata.constants import common

    if spec.module != common.MODULE_RELATIONAL:
        raise ValueError(msg_const.MSG_SCHEMA_NOT_RELATIONAL)

    # Must have at least one FK relationship to be worth rendering
    fk_tables = [t for t in spec.tables if t.parent is not None]
    if len(fk_tables) == 0:
        raise ValueError(msg_const.MSG_SCHEMA_NO_FK)

    lines = ["erDiagram"]

    # Emit one entity block per table
    for table in spec.tables:
        # Collect FK column names for this table
        fk_col_names = {table.parent.key} if table.parent else set()

        lines.append(f"    {table.name} {{")
        for col in table.columns:
            type_token = _GEN_TO_TYPE.get(col.gen, "string")
            if _is_pk(col) and col.name not in fk_col_names:
                marker = " PK"
            elif col.name in fk_col_names:
                marker = " FK"
            else:
                marker = ""
            lines.append(f"        {type_token} {col.name}{marker}")
        lines.append("    }")

    # Emit relationship lines (one per FK)
    for table in fk_tables:
        notation = _cardinality_notation(table)
        parent = table.parent.table
        child = table.name
        lines.append(f"    {parent} {notation} {child} : \"has\"")

    return "\n".join(lines)


def is_relational_with_fk(spec: Spec) -> bool:
    """Return True only when spec warrants an ER diagram (≥2 tables, ≥1 FK)."""
    from hackdata.constants import common
    return (
        spec.module == common.MODULE_RELATIONAL
        and len(spec.tables) >= 2
        and any(t.parent is not None for t in spec.tables)
    )


# ---------------- SELF-CHECK ----------------
if __name__ == "__main__":
    import sys
    from hackdata.entity.spec_entity import (
        Spec, TableSpec, ColumnSpec, ParentSpec, Cardinality,
    )

    customers = TableSpec(name="customers", n_rows=100, columns=[
        ColumnSpec(name="customer_id", gen="sequence", rules=["unique", "not_null"]),
        ColumnSpec(name="name", gen="faker", faker_field="name"),
    ])
    orders = TableSpec(name="orders", n_rows=300, columns=[
        ColumnSpec(name="order_id", gen="sequence", rules=["unique", "not_null"]),
        ColumnSpec(name="customer_id", gen="int_range", ref="customers.customer_id"),
        ColumnSpec(name="amount", gen="money"),
    ], parent=ParentSpec(table="customers", key="customer_id",
                         cardinality=Cardinality(min_per_parent=1, max_per_parent=5)))

    spec = Spec(module="relational", tables=[customers, orders])
    diagram = spec_to_mermaid(spec)
    assert "erDiagram" in diagram
    assert "customers {" in diagram
    assert "orders {" in diagram
    assert "customers ||--|{ orders" in diagram or "customers ||--o{" in diagram
    print("Two-table spec:\n", diagram)

    # single table (no FK) must raise
    single = Spec(module="relational", tables=[customers])
    try:
        spec_to_mermaid(single)
        print("ERROR: should have raised")
        sys.exit(1)
    except ValueError as e:
        print("Correctly rejected no-FK spec:", e)

    # non-relational must raise
    tabular_spec = Spec(module="tabular", tables=[customers])
    try:
        spec_to_mermaid(tabular_spec)
        print("ERROR: should have raised")
        sys.exit(1)
    except ValueError as e:
        print("Correctly rejected tabular spec:", e)

    print("Self-check passed.")
