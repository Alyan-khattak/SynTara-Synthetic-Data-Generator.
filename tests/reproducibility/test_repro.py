# ═══════════════════════════════════════════════════════════════════
# test_repro.py — reproducibility tests and SHA-256 checksum checks
# ═══════════════════════════════════════════════════════════════════
# Proves that:
#   - same seed + same spec → byte-identical CSV output (checksum equality)
#   - different seed         → different CSV output  (checksum inequality)
#   - seed=None              → pipeline completes without error
#   - derive_seed is stable  → same int for same inputs
#   - make_rng is stable     → same sequence for same inputs
#   - sha256_file is stable  → same hash for same bytes, different for different
#
# IMP: the GenerationPipeline calls SpecBuilder which calls the LLM.
#      We bypass the LLM entirely by supplying spec_override in the request,
#      which routes through SpecBuilder.validate_spec() only (no network call).
#
# IMP: the pipeline writes to Artifacts/temp/<run_id>/ by default.
#      We monkeypatch hackdata.constants.paths.ARTIFACT_DIR so all artifact
#      output lands inside pytest's tmp_path instead.
###==============================================================

import os

import numpy as np
import pytest

from hackdata.entity.request_entity import GenerationRequest
from hackdata.pipeline.generation_pipeline import GenerationPipeline
from hackdata.utils.main_utils.hash_utils import sha256_file
from hackdata.utils.main_utils.seed_utils import derive_seed, make_rng


# ─────────────────────────────────────────────────────────────────────
# HELPER
# ─────────────────────────────────────────────────────────────────────

def _run(spec_dict: dict, seed, tmp_path, monkeypatch):
    """Create and run a GenerationPipeline with artifacts in tmp_path.

    Parameters
    ----------
    spec_dict  : validated spec dict passed as spec_override (no LLM call)
    seed       : master seed; pass None to let the pipeline pick one
    tmp_path   : pytest tmp_path; redirected artifact base directory
    monkeypatch: pytest monkeypatch; patches ARTIFACT_DIR for this test

    Returns
    -------
    GenerationPipelineResult
    """
    import hackdata.constants.paths as paths_const  # noqa: import inside function

    # Redirect all artifact writes to the test's isolated temp directory
    monkeypatch.setattr(paths_const, "ARTIFACT_DIR", str(tmp_path))

    request = GenerationRequest(
        module="tabular",
        mode="query",
        query="reproducibility test data",  # noqa: hardcode
        spec_override=spec_dict,
        seed=seed,
    )
    return GenerationPipeline(request).run()


# ─────────────────────────────────────────────────────────────────────
# PIPELINE REPRODUCIBILITY TESTS
# ─────────────────────────────────────────────────────────────────────

def test_same_seed_same_csv_checksum(tmp_path, monkeypatch, sample_spec_dict):
    """Two runs with the same seed and spec produce byte-identical CSV files.

    Arrange: spec_override bypasses LLM; seed=42 fixes all random draws.
    Act    : run the pipeline twice in the same tmp_path.
    Assert : SHA-256 checksums of the first table CSV are equal.
    """
    result1 = _run(sample_spec_dict, seed=42, tmp_path=tmp_path, monkeypatch=monkeypatch)  # noqa: hardcode
    result2 = _run(sample_spec_dict, seed=42, tmp_path=tmp_path, monkeypatch=monkeypatch)  # noqa: hardcode

    # IMP: both results have one table; extract the single CSV path each time
    csv1 = list(result1.gen_artifact.table_file_paths.values())[0]
    csv2 = list(result2.gen_artifact.table_file_paths.values())[0]

    assert sha256_file(csv1) == sha256_file(csv2), (
        "Same seed must produce byte-identical CSV output"
    )


def test_different_seed_different_csv(tmp_path, monkeypatch, sample_spec_dict):
    """Two runs with different seeds produce different CSV files.

    Arrange: seed=42 for run 1, seed=99 for run 2.
    Act    : run the pipeline twice.
    Assert : SHA-256 checksums differ (statistically certain for any non-trivial n_rows).

    IMP: with 100 rows of int_range data, the probability of a collision
         is astronomically small; no special random-seed protection needed.
    """
    result1 = _run(sample_spec_dict, seed=42, tmp_path=tmp_path, monkeypatch=monkeypatch)  # noqa: hardcode
    result2 = _run(sample_spec_dict, seed=99, tmp_path=tmp_path, monkeypatch=monkeypatch)  # noqa: hardcode

    csv1 = list(result1.gen_artifact.table_file_paths.values())[0]
    csv2 = list(result2.gen_artifact.table_file_paths.values())[0]

    assert sha256_file(csv1) != sha256_file(csv2), (
        "Different seeds must produce different CSV output"
    )


def test_no_seed_still_runs(tmp_path, monkeypatch, sample_spec_dict):
    """Pipeline runs without error when seed=None (auto-generates fresh seed).

    Arrange: seed=None; pipeline calls new_master_seed() internally.
    Act    : run the pipeline.
    Assert : result.status is True; CSV exists on disk; at least one row written.
    """
    result = _run(sample_spec_dict, seed=None, tmp_path=tmp_path, monkeypatch=monkeypatch)

    # Pipeline must complete cleanly
    assert result.status is True, "Pipeline status should be True (no tier-1 failures)"

    # CSV must exist on disk and contain at least the header + one data row
    csv_path = list(result.gen_artifact.table_file_paths.values())[0]
    assert os.path.isfile(csv_path), "CSV file must exist on disk"

    with open(csv_path, encoding="utf-8") as f:
        lines = f.readlines()
    # lines[0] is the header; lines[1:] are data rows
    assert len(lines) > 1, "CSV must contain at least one data row"


# ─────────────────────────────────────────────────────────────────────
# SEED UTILITY UNIT TESTS  (no pipeline, no I/O)
# ─────────────────────────────────────────────────────────────────────

def test_derive_seed_stable():
    """derive_seed returns the same integer for identical inputs.

    IMP: this is a pure function; calling it twice with the same args
         must return the same result (no global state, no randomness).
    """
    seed_a = derive_seed(42, "orders", "amount")  # noqa: hardcode
    seed_b = derive_seed(42, "orders", "amount")  # noqa: hardcode

    assert isinstance(seed_a, int), "derive_seed must return an int"
    assert seed_a == seed_b, "Same inputs must always yield the same derived seed"


def test_make_rng_same_seed_same_sequence():
    """make_rng with the same master+keys produces identical integer sequences.

    Arrange: call make_rng(42, "t", "col") twice.
    Act    : draw 10 integers in [0, 100) from each generator.
    Assert : the two arrays are element-wise equal.

    IMP: np.random.default_rng is per-instance; no global state is touched,
         so replaying the exact seed reproduces the exact sequence.
    """
    arr1 = make_rng(42, "t", "col").integers(0, 100, 10)  # noqa: hardcode
    arr2 = make_rng(42, "t", "col").integers(0, 100, 10)  # noqa: hardcode

    np.testing.assert_array_equal(arr1, arr2, err_msg="Same seed must produce the same integer sequence")


# ─────────────────────────────────────────────────────────────────────
# SHA-256 FILE HASH UNIT TESTS  (no pipeline)
# ─────────────────────────────────────────────────────────────────────

def test_sha256_file_stable(tmp_path):
    """sha256_file returns equal digests for equal content and different digests for different content.

    Arrange: write identical bytes to two files; write different bytes to a third.
    Act    : hash all three files.
    Assert : hash(file_a) == hash(file_b); hash(file_a) != hash(file_c).
    """
    content_x = b"reproducible content for checksum test\n"  # noqa: hardcode
    content_y = b"different content that must hash differently\n"  # noqa: hardcode

    file_a = str(tmp_path / "file_a.bin")
    file_b = str(tmp_path / "file_b.bin")
    file_c = str(tmp_path / "file_c.bin")

    with open(file_a, "wb") as f:
        f.write(content_x)
    with open(file_b, "wb") as f:
        f.write(content_x)  # same content as file_a
    with open(file_c, "wb") as f:
        f.write(content_y)  # different content

    assert sha256_file(file_a) == sha256_file(file_b), (
        "Same content must produce identical SHA-256 digests"
    )
    assert sha256_file(file_a) != sha256_file(file_c), (
        "Different content must produce different SHA-256 digests"
    )
