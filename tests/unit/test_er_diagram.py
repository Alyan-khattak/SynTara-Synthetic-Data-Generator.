# ═══════════════════════════════════════════════════════════════════
# test_er_diagram.py — unit tests for er_diagram.spec_to_mermaid
# ═══════════════════════════════════════════════════════════════════
import pytest

from hackdata.components.er_diagram import spec_to_mermaid, is_relational_with_fk
from hackdata.entity.spec_entity import (
    Spec, TableSpec, ColumnSpec, ParentSpec, Cardinality,
)


def _customers():
    return TableSpec(name="customers", n_rows=100, columns=[
        ColumnSpec(name="customer_id", gen="sequence", rules=["unique", "not_null"]),
        ColumnSpec(name="name", gen="faker", faker_field="name"),
    ])


def _orders(parent="customers"):
    return TableSpec(name="orders", n_rows=300, columns=[
        ColumnSpec(name="order_id", gen="sequence", rules=["unique", "not_null"]),
        ColumnSpec(name="customer_id", gen="int_range"),
        ColumnSpec(name="amount", gen="money"),
    ], parent=ParentSpec(
        table=parent, key="customer_id",
        cardinality=Cardinality(min_per_parent=1, max_per_parent=5),
    ))


def _items():
    return TableSpec(name="items", n_rows=900, columns=[
        ColumnSpec(name="item_id", gen="sequence", rules=["unique", "not_null"]),
        ColumnSpec(name="order_id", gen="int_range"),
        ColumnSpec(name="sku", gen="categorical", values=["A", "B"]),
    ], parent=ParentSpec(
        table="orders", key="order_id",
        cardinality=Cardinality(min_per_parent=1, max_per_parent=4),
    ))


# ── two-table spec ────────────────────────────────────────────────

def test_two_table_spec():
    spec = Spec(module="relational", tables=[_customers(), _orders()])
    diagram = spec_to_mermaid(spec)
    assert "erDiagram" in diagram
    assert "customers {" in diagram
    assert "orders {" in diagram
    # FK column marked
    assert "customer_id FK" in diagram
    # PK column marked (sequence)
    assert "customer_id PK" in diagram or "order_id PK" in diagram
    # relationship line present
    assert "customers" in diagram and "orders" in diagram
    # cardinality: min=1, max=5 → one-or-many
    assert "||--|{" in diagram or "||--o{" in diagram


# ── three-table spec ──────────────────────────────────────────────

def test_three_table_spec():
    spec = Spec(module="relational", tables=[_customers(), _orders(), _items()])
    diagram = spec_to_mermaid(spec)
    assert "customers {" in diagram
    assert "orders {" in diagram
    assert "items {" in diagram
    # both FK relationships present
    assert "customers" in diagram
    assert "orders" in diagram


# ── single table with no FK: rejected ────────────────────────────

def test_single_table_no_fk_rejected():
    spec = Spec(module="relational", tables=[_customers()])
    with pytest.raises(ValueError):
        spec_to_mermaid(spec)


# ── two tables but no FK: rejected ────────────────────────────────

def test_two_tables_no_fk_rejected():
    spec = Spec(module="relational", tables=[
        _customers(),
        TableSpec(name="orders", n_rows=100, columns=[
            ColumnSpec(name="order_id", gen="sequence"),
        ]),
    ])
    with pytest.raises(ValueError):
        spec_to_mermaid(spec)


# ── non-relational module: rejected ──────────────────────────────

def test_tabular_spec_rejected():
    spec = Spec(module="tabular", tables=[_customers()])
    with pytest.raises(ValueError):
        spec_to_mermaid(spec)


# ── is_relational_with_fk helper ─────────────────────────────────

def test_is_relational_with_fk():
    assert is_relational_with_fk(Spec(module="relational", tables=[_customers(), _orders()]))
    assert not is_relational_with_fk(Spec(module="tabular", tables=[_customers()]))
    # single table with no FK
    assert not is_relational_with_fk(Spec(module="relational", tables=[_customers()]))
