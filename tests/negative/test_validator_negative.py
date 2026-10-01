# ═══════════════════════════════════════════════════════════════════
# test_validator_negative.py — negative tests for DataValidator
# ═══════════════════════════════════════════════════════════════════
# For each tier-1 and tier-2 defect kind we:
#   1. Build a clean DataFrame that matches the spec.
#   2. Plant exactly one defect.
#   3. Assert the right defect kind appears in the report.
#
# Test isolation: every test builds its own tmp dir, DataFrame, spec
# and DataValidator instance.  No shared mutable state.
###==============================================================

import os

import pandas as pd
import pytest

from hackdata.constants import validation as val_const
from hackdata.entity.artifact_entity import DataGenerationArtifact
from hackdata.entity.config_entity import DataValidationConfig, RunConfig
from hackdata.entity.spec_entity import Spec
from hackdata.components.data_validator import DataValidator


# ──────────────────────────────────────────────────────────────────
# HELPER
# ──────────────────────────────────────────────────────────────────

def _make_validator(df: pd.DataFrame, spec_dict: dict, tmp_path) -> DataValidator:
    """Write df to CSV, wrap into artifacts, return a ready DataValidator.

    Parameters
    ----------
    df        : DataFrame to validate (the "generated" data).
    spec_dict : raw spec dict; the first table's name must match df's columns.
    tmp_path  : pytest-provided temporary directory (pathlib.Path).
    """
    tables_dir = str(tmp_path / "tables")
    os.makedirs(tables_dir, exist_ok=True)

    table_name = spec_dict["tables"][0]["name"]
    csv_path = os.path.join(tables_dir, f"{table_name}.csv")  # noqa: hardcode test fixture filename
    df.to_csv(csv_path, index=False)

    gen_art = DataGenerationArtifact(
        tables_dir=tables_dir,
        table_file_paths={table_name: csv_path},
        master_seed=42,  # noqa: hardcode test fixture seed
        row_counts={table_name: len(df)},
    )

    spec = Spec(**spec_dict)
    rc = RunConfig()
    config = DataValidationConfig(rc)
    return DataValidator(config, gen_art, spec)


def _base_spec() -> dict:
    """Minimal spec with one not-null/unique 'id' and one range-checked 'price'.

    Keeping price without not_null so range-only violations stay in tier 2.
    """
    return {
        "version": "1",
        "module": "tabular",
        "tables": [
            {
                "name": "orders",  # noqa: hardcode test fixture table name
                "n_rows": 5,
                "columns": [
                    # id: tier-1 rules (structural)
                    {"name": "id",    "gen": "sequence",  "rules": ["not_null", "unique"]},  # noqa: hardcode
                    # price: tier-2 rule (range) — no not_null so nulls don't bleed into tier 1
                    {"name": "price", "gen": "int_range", "min": 100, "max": 10000, "rules": ["range"]},  # noqa: hardcode
                ],
            }
        ],
    }


def _clean_df() -> pd.DataFrame:
    """Five rows that fully satisfy the base spec (no defects)."""
    return pd.DataFrame({
        "id":    [1, 2, 3, 4, 5],  # noqa: hardcode test fixture values
        "price": [200, 500, 1000, 5000, 9000],  # noqa: hardcode all within [100, 10000]
    })


# ──────────────────────────────────────────────────────────────────
# NEGATIVE TESTS — tier 1 (structural)
# ──────────────────────────────────────────────────────────────────

def test_null_in_not_null_col_detected(tmp_path):
    """Plant a None in the 'id' (not_null) column; expect null_in_not_null defect."""
    # Arrange: one None in id column
    df = _clean_df().copy()
    df.loc[2, "id"] = None  # noqa: hardcode row index for isolation

    # Act
    result = _make_validator(df, _base_spec(), tmp_path).initiate_data_validation()

    # IMP: DataValidationArtifact holds status and score only; defects are in the JSON report.
    # Re-read the report to inspect defects without breaking the artifact contract.
    import json
    with open(result.report_file_path) as fh:
        report = json.load(fh)

    kinds = [d["kind"] for d in report["defects"]]
    assert "null_in_not_null" in kinds, f"Expected null_in_not_null in {kinds}"


def test_duplicate_pk_detected(tmp_path):
    """Plant a duplicate in the 'id' (unique) column; expect duplicate_pk defect."""
    # Arrange: row 1 and row 3 share id=1
    df = _clean_df().copy()
    df.loc[3, "id"] = 1  # noqa: hardcode duplicate value

    # Act
    result = _make_validator(df, _base_spec(), tmp_path).initiate_data_validation()

    # Assert
    import json
    with open(result.report_file_path) as fh:
        report = json.load(fh)

    kinds = [d["kind"] for d in report["defects"]]
    assert "duplicate_pk" in kinds, f"Expected duplicate_pk in {kinds}"


# ──────────────────────────────────────────────────────────────────
# NEGATIVE TESTS — tier 2 (rule checks)
# ──────────────────────────────────────────────────────────────────

def test_range_min_violation_detected(tmp_path):
    """Plant a value below col.min in 'price'; expect negative_quantity at tier VAL_TIER_RULES."""
    # Arrange: price=50 is below col.min=100
    df = _clean_df().copy()
    df.loc[0, "price"] = 50  # noqa: hardcode value below min

    # Act
    result = _make_validator(df, _base_spec(), tmp_path).initiate_data_validation()

    # Assert: defect present with correct kind and tier
    import json
    with open(result.report_file_path) as fh:
        report = json.load(fh)

    rule_defects = [d for d in report["defects"] if d["kind"] == "negative_quantity"]
    assert rule_defects, "Expected at least one negative_quantity defect"
    assert all(
        d["tier"] == val_const.VAL_TIER_RULES for d in rule_defects
    ), f"All range defects must be tier VAL_TIER_RULES={val_const.VAL_TIER_RULES}"


def test_range_max_violation_detected(tmp_path):
    """Plant a value above col.max in 'price'; expect negative_quantity defect."""
    # Arrange: price=99999 is above col.max=10000
    df = _clean_df().copy()
    df.loc[0, "price"] = 99999  # noqa: hardcode value above max

    # Act
    result = _make_validator(df, _base_spec(), tmp_path).initiate_data_validation()

    # Assert
    import json
    with open(result.report_file_path) as fh:
        report = json.load(fh)

    kinds = [d["kind"] for d in report["defects"]]
    assert "negative_quantity" in kinds, f"Expected negative_quantity in {kinds}"


# ──────────────────────────────────────────────────────────────────
# POSITIVE / STATUS TESTS
# ──────────────────────────────────────────────────────────────────

def test_clean_table_no_defects(tmp_path):
    """Perfectly valid DataFrame produces zero defects, score==100.0, status==True."""
    # Arrange: clean df
    df = _clean_df()

    # Act
    result = _make_validator(df, _base_spec(), tmp_path).initiate_data_validation()

    # Assert
    import json
    with open(result.report_file_path) as fh:
        report = json.load(fh)

    assert report["defects"] == [], f"Expected no defects; got {report['defects']}"
    assert result.validity_score == 100.0, f"Expected 100.0; got {result.validity_score}"
    assert result.status is True, "Clean table must have status=True"


def test_tier1_defect_sets_status_false(tmp_path):
    """A tier-1 null violation must flip status to False."""
    # Arrange: inject null into the not_null column
    df = _clean_df().copy()
    df.loc[0, "id"] = None  # noqa: hardcode row index

    # Act
    result = _make_validator(df, _base_spec(), tmp_path).initiate_data_validation()

    # Assert: status False because tier 1 failed
    assert result.status is False, (
        f"Tier-1 defect must set status=False; got status={result.status}"
    )


def test_tier2_defect_does_not_set_status_false(tmp_path):
    """A tier-2 range violation alone must NOT flip status to False.

    IMP: Only tier-1 (structural) defects gate the pipeline.  Tier-2 rule
    violations are logged and reported but are non-fatal (TRD section 7,
    DataValidator table, and data_validator.py status logic).
    """
    # Arrange: inject a value below col.min in 'price' only — id column stays clean
    df = _clean_df().copy()
    df.loc[0, "price"] = 50  # noqa: hardcode value below price.min=100

    # Act
    result = _make_validator(df, _base_spec(), tmp_path).initiate_data_validation()

    # Assert: tier-2 defect exists but status is still True
    import json
    with open(result.report_file_path) as fh:
        report = json.load(fh)

    tier2_defects = [d for d in report["defects"] if d["tier"] == val_const.VAL_TIER_RULES]
    assert tier2_defects, "Expected at least one tier-2 defect to confirm defect was planted"
    assert result.status is True, (
        f"Tier-2 defect alone must leave status=True; got status={result.status}"
    )
