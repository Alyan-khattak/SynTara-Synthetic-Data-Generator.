# conftest.py — shared fixtures for all test suites
# No hackdata imports at module level; import inside fixtures to avoid
# errors when components are not yet built.

import pytest
import numpy as np


@pytest.fixture
def master_seed():
    """Fixed master seed for all reproducibility tests."""
    return 42


@pytest.fixture
def seeded_rng(master_seed):
    """Seeded numpy Generator.

    Use hackdata.utils.make_rng in tests that need the project helper;
    use this fixture when you only need a bare numpy generator.
    """
    return np.random.default_rng(master_seed)


@pytest.fixture
def tmp_artifact_dir(tmp_path):
    """Temporary directory for artifact outputs during tests.

    Mirrors the Artifacts/temp/<run>/ layout used in production
    (TRD section 1, adaptation 4) without touching the real artifact tree.
    """
    d = tmp_path / "Artifacts" / "temp" / "test_run"
    d.mkdir(parents=True)
    return str(d)


@pytest.fixture
def sample_spec_dict():
    """Minimal valid spec dict for tabular generator tests.

    Covers the three most common column generators (sequence, int_range,
    categorical) with a small row count so tests stay fast.
    """
    return {
        "version": "1",
        "module": "tabular",   # MODULE_TABULAR from hackdata.constants.common
        "tables": [
            {
                "name": "items",
                "n_rows": 100,
                "columns": [
                    {"name": "id", "gen": "sequence"},
                    # price stored as integer minor units (TRD convention)
                    {"name": "price", "gen": "int_range", "min": 100, "max": 10000},
                    {"name": "category", "gen": "categorical", "values": ["A", "B", "C"]},
                ],
            }
        ],
    }
