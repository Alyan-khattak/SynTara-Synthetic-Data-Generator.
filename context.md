# context.md — project history, task by task

**Owner: orchestrator only.** Append-only. Newest entry at the bottom. Never edit an old entry; if it was wrong, add a new entry that says what it corrects.
Read the newest entries first when starting a session. Together with `task.md` this file must be enough for someone with no memory to know the state.

## How to read this

- `task.md` says what is planned and its status. This file says what actually happened.
- One entry per task when it reaches `done`, `dropped` or `blocked`. Gates and decisions get their own entries.
- Every entry answers: what was built where, why, what changed, what was removed.

## Entry format

```
### T-000 · <title> · <done | dropped | blocked> · <YYYY-MM-DD HH:MM>
Owner: <agent> · Reviewed by: <agent or none> · Tier: <P0|P1|P2>
Built: what now exists and where (paths, functions, endpoints).
Why: the reason, and the option rejected.
Changed: earlier work that was modified, and why (or "none").
Removed: what was deleted or dropped, and why (or "none").
Contracts: frozen names, fields or payloads touched (or "none").
Evidence: commands run and results (pass/fail counts, key output).
Assumptions / VERIFY: open points.
Next: follow-up task IDs created.
```

Other entry types:

```
### DECISION · <title> · <date>
Chosen: ... Rejected: ... Reason: ... Affects: T-0xx, T-0yy

### GATE n · <date>
P0 done / planned: x / y. Passed: ... Cut: ... Risks: ...

### CORRECTION · <date>
Corrects the entry for T-0xx: what was wrong and what is true now.
```

## Frozen contracts (kept current by the orchestrator)

| Contract | Location | Frozen at | Notes |
|---|---|---|---|
| Spec models | `hackdata/entity/spec_entity.py` | T-008 · 2026-09-29 | Pydantic v2; vocab from constants/spec.py |
| Scores JSON | `data_schema/scores.schema.json` | T-008 · 2026-09-29 | draft-07; validity/fidelity/utility/privacy nullable 0–100 |
| API payloads | `api/schemas.py` | T-008 · 2026-09-29 | GenerateRequest, GenerateResponse, ScoresResponse, ConfigResponse |
| Config entities | `hackdata/entity/config_entity.py` | T-008 · 2026-09-29 | RunConfig + 11 component configs |
| Artifact entities | `hackdata/entity/artifact_entity.py` | T-008 · 2026-09-29 | 11 @dataclass artifacts |
| Request entities | `hackdata/entity/request_entity.py` | T-008 · 2026-09-29 | GenerationRequest, UploadRequest |
| Spec JSON Schema | `data_schema/spec.schema.json` | T-008 · 2026-09-29 | Generated from Spec.model_json_schema() |
| Engine interface | `hackdata/components/` | not yet | Phase 1 |

## Log

### START · Project set up · (fill date)
Owner: orchestrator
Built: `standards.md`, `orchestrator_agent.md`, five role agents (backend, frontend, data-ml, qa, reviewer), `skills_matrix.md`, `task.md`, `context.md`. Planning documents `PRD.md`, `TRD.md` and `HackDataV2_Architecture.md` (v2).
Why: one plan and one history so any agent or person can resume without the chat.
Changed: none. Removed: none. Contracts: none frozen yet.
Assumptions / VERIFY: skills named by the human but not visible in the session are unverified (see `skills_matrix.md`); Google Drive connector is not connected; TRD open items (ID marker digit, GST, Eid dates, lakh default) are unconfirmed.
Next: T-001.

### RECOVERY · Session interrupted · 2026-09-29 19:45
Previous session was interrupted before recording task completions. Repository state on recovery:
- T-001 to T-003 fully implemented and working; context.md and task.md had not been updated.
- No entity, cloud, component, pipeline, utils, or test files present.
Corrections made: T-001, T-002, T-003 marked done in task.md.
Frozen contracts: none yet (T-008 not reached).
Next: dispatch T-004, T-005, T-007, T-009, T-010 in parallel.

### T-001 · Repo skeleton · done · 2026-09-29
Owner: BE · Reviewed by: none · Tier: P0
Built: repo root folders (hackdata/, api/, tests/, scripts/, data_assets/, Artifacts/, cache/, logs/, frontend/), all `__init__.py`, `.gitignore`, `.env.example`, `requirements.txt` (pinned), `requirements-dev.txt`, `setup.py`.
Why: NS-style editable install; `pip install -e .` needed before any import.
Changed: none. Removed: none. Contracts: none.
Evidence: `python -c "import hackdata"` → passes.
Next: T-002.

### T-002 · Exception and logger · done · 2026-09-29
Owner: BE · Reviewed by: none · Tier: P0
Built: `hackdata/exception/exception.py` (HackDataException with file+line enrichment, handles None traceback), `hackdata/logging/logger.py` (per-process-start log file, stream+file handlers).
Why: one exception and one logger for the whole project, NS convention.
Changed: none. Removed: none. Contracts: none.
Evidence: imports clean; logger creates log file in logs/.
Next: T-003.

### T-003 · Constants package · done · 2026-09-29
Owner: BE · Reviewed by: none · Tier: P0
Built: all constants modules — `common`, `paths`, `messages`, `spec`, `llm`, `generation`, `validation`, `evaluation`, `data_mode`, `documents`, `locales`, `export`, `api` — matching TRD section 5.2 exactly.
Why: full constants package up front so all later tasks can import values without hard-coding.
Changed: none. Removed: none. Contracts: none.
Evidence: `from hackdata.constants import common, paths, messages, spec, llm, generation, validation, api, evaluation` → all pass.
Assumptions: LLM model IDs marked VERIFY; locale ID marker digit, GST rate, Eid dates marked VERIFY.
Next: T-004, T-005, T-007, T-009, T-010 (parallel).

### T-004 · Spec entity · done · 2026-09-29
Owner: BE · Reviewed by: none · Tier: P0
Built: `hackdata/entity/spec_entity.py` — 9 Pydantic v2 models: Spec, TableSpec, ColumnSpec, Cardinality, ParentSpec, EdgeCase, DocumentSpec, ConditionSegment, SeasonalityPeriod. All vocabulary fields validated against constants.spec tuples. `extra="forbid"` on all models. Added 7 MSG_INVALID_* constants to messages.py.
Why: closed vocab enforced at parse time; one place to add new generator types.
Changed: messages.py (7 new constants added). Contracts: spec_entity models are now frozen at T-008.
Evidence: valid spec parses; `gen="INVALID_TYPE"` raises ValidationError; invalid module rejected. All pass.
Next: T-006 (API schemas) now unblocked.

### T-005 · Config and artifact entities · done · 2026-09-29
Owner: BE · Reviewed by: none · Tier: P0
Built: `hackdata/entity/config_entity.py` (RunConfig + 11 component configs), `hackdata/entity/artifact_entity.py` (11 @dataclass artifacts), `hackdata/entity/request_entity.py` (GenerationRequest, UploadRequest). Added GEN_DEFAULT_N_ROWS to generation.py; SCHEMA_FILE_NAME, HTML_DIR_NAME, PDF_DIR_NAME to paths.py.
Why: typed contracts between pipeline stages; no plain tuples.
Changed: constants/generation.py (GEN_DEFAULT_N_ROWS), constants/paths.py (3 new path names). Contracts: config and artifact shapes now frozen at T-008.
Evidence: RunConfig(datetime(2026,9,29,12,0,0)) → correct run_id and paths; GenerationRequest defaults correct. T-005 PASS.
Next: T-007, T-009 still in progress.

### T-034 · Frontend shell · done · 2026-09-29
Owner: FE · Reviewed by: none · Tier: P0
Built: `frontend/index.html` (389 lines, Alpine.js v3 + Tailwind CDN, full state machine), `frontend/js/api.js` (apiFetch wrapper + 6 exported functions, base="/api"), `frontend/js/strings.js` (all UI text in one object).
Why: all API calls go through one module; all strings in one place — no scattered literals.
Changed: none. Contracts: api.js functions match api/schemas.py endpoints.
Evidence: index.html 17733 bytes; Alpine x-data present; api.js and strings.js imported; JS syntax valid (node --input-type=module). Graceful fallback when backend not running.
Next: T-035 (query form + results) once T-030 (FastAPI routes) exists.

### T-007 · Utils package · done · 2026-09-29
Owner: BE · Reviewed by: none · Tier: P0
Built: `hackdata/utils/main_utils/` — utils.py (save/load object, yaml, json, ensure_dir), seed_utils.py (derive_seed via blake2b, make_rng, new_master_seed), hash_utils.py (sha256_file/text, query_cache_key), money_utils.py (minor units, round_half_up via decimal.ROUND_HALF_UP), format_utils.py (group_lakh, format_money/date/phone), canonical_io.py (write_csv/json_canonical, write_sql_dump), dataframe_utils.py (read_csv_safely, sample_rows, is_numeric_like), env_utils.py (get_env, get_groq_keys).
Why: shared utils for all components; seeded randomness via blake2b prevents reproducibility bugs.
Changed: dataframe_utils.py — patched magic number 0.9 → data_mode.DM_PARSE_SUCCESS_RATIO (defect found by T-009 hardcoding check). Contracts: none new.
Evidence: derive_seed(42,"orders","amount") reproducible; different keys give different seed; to_minor_units(123.456)=12346; sha256_text len=64. T-007 PASS.
Next: T-008 contract freeze now ready (T-004..T-007 all done).

### T-006 · Scores JSON contract and API schemas · done · 2026-09-29
Owner: BE · Reviewed by: none · Tier: P0
Built: `api/schemas.py` (GenerateRequest, SpecEditRequest, SaveRunRequest, GenerateResponse, ScoresResponse, RunSummary, RunListResponse, HealthResponse, ConfigResponse — all defaults from constants, no literals); `data_schema/scores.schema.json` (draft-07, validity/fidelity/utility/privacy nullable numbers 0-100); `data_schema/spec.schema.json` (generated from Spec.model_json_schema()).
Why: API and scores contracts defined before Phase 1 work begins; frontend can validate against these schemas.
Changed: none. Contracts: api/schemas.py and data_schema/*.json frozen at T-008.
Evidence: GenerateRequest parses, ScoresResponse parses, JSON schemas load and have correct fields. check_no_hardcoding.py → PASS.
Next: T-008 reviewer returning verdict.

### T-011 · LLM client · done · 2026-09-29
Owner: BE · Reviewed by: none · Tier: P0
Built: `hackdata/cloud/key_pool.py` (KeyPool, insertion-order rotation, cooldown), `hackdata/cloud/prompt_loader.py` (load_prompt from data_assets/prompts/), `hackdata/cloud/llm_client.py` (ask_json + ask_text, full chain: cache → key rotation → model fallback → repair → offline). Added MSG_* constants to messages.py; GEN_OFFLINE_FALLBACK_INT_MAX to generation.py.
Post-review fixes: LLM_HTTP_STATUS_RATE_LIMIT=429, LLM_CACHE_KEY_DISPLAY_LEN=8 added to llm.py; `429` literal and `[:8]` slices replaced with constants; internal log strings >40 chars tagged # noqa:hardcode.
Changed: messages.py, generation.py, llm.py, key_pool.py, llm_cache.py, llm_client.py. Contracts: llm_client.ask_json/ask_text interface frozen.
Evidence: KeyPool stub PASS; llm_client imports OK. check_no_hardcoding.py → PASS.
Next: T-013 (spec builder) now unblocked.

### T-012 · Reliability chain · done · 2026-09-29
Owner: BE · Reviewed by: none · Tier: P0
Built: `hackdata/cloud/llm_cache.py` (two-level dir cache, get/put), `hackdata/cloud/offline_fallback.py` (build_offline_spec → Spec-valid dict, no LLM).
Changed: llm_cache.py (slice fix). Contracts: cache key convention (2-char subdir + full key filename).
Evidence: cache put/get roundtrip PASS; offline_fallback returns Spec-valid dict. check_no_hardcoding.py → PASS.

### T-014 · Column generators · done · 2026-09-29
Owner: DM · Reviewed by: none · Tier: P0
Built: `hackdata/components/generators/column_generators.py` — all 19 gen types (16 full + 3 stubs: aggregate/conditional/expr). generate_column() dispatch with per-column seeded RNG.
Post-review fix: `size=10` → `loc_const.LOC_MOBILE_DIGIT_COUNT` (added to locales.py).
Changed: constants/locales.py (LOC_MOBILE_DIGIT_COUNT). Contracts: generate_column(col_spec, n, master_seed, table_name, existing_cols) interface.
Evidence: reproducible; ranges respected; 10k×4 gen types in 0.078s (< 2s). check_no_hardcoding.py → PASS.

### T-020 · Negative validator tests · done · 2026-09-29
Owner: QA · Reviewed by: none · Tier: P0
Built: `tests/negative/test_validator_negative.py` — 7 tests covering tier 1 (null_in_not_null, duplicate_pk), tier 2 (range min/max violation), clean table, status gating (tier 1 fatal, tier 2 non-fatal).
Why: each defect kind must be independently proven catchable.
Changed: none. Contracts: none.
Evidence: 7 passed in 0.53s. Full suite 7 passed. check_no_hardcoding.py → PASS. No bugs found in product code.
Next: T-025 Gate 1 pending T-021 (repro tests, in progress).

### T-018 · Generation pipeline (query to CSV) · done · 2026-09-29
Owner: BE · Reviewed by: none · Tier: P0
Built: `hackdata/pipeline/generation_pipeline.py` — GenerationPipeline + GenerationPipelineResult dataclass. Full chain: SpecBuilder → _generate_tables → _write_tables (write_csv_canonical) → DataValidator → _write_metadata (run_metadata.json).
Why: P0 milestone; first end-to-end path from query to validated CSV artifact.
Changed: constants/paths.py — added GENERATION_RUN_META_FILE_NAME. Contracts: none new.
Evidence: run_id written, table_1 1000 rows 4 cols, validity_score=100.0, status=True, metadata OK. T-018 PASS. check_no_hardcoding.py → PASS.
Next: T-021 (reproducibility tests) now unblocked. T-025 Gate 1 pending T-020 + T-021.

### T-013 · Spec generation from query · done · 2026-09-29
Owner: BE · Reviewed by: none · Tier: P0
Built: `hackdata/components/spec_builder.py` — SpecBuilder with load_template(), ask_llm_for_spec(), validate_spec(), fetch_pools(), initiate_spec_builder(). Prompt stubs: data_assets/prompts/spec_prompt.txt, pool_prompt.txt, narrative_prompt.txt, repair_prompt.txt.
Why: spec_builder is the entry point to all generation; offline_fallback path means it works without Groq keys.
Changed: none. Contracts: SpecBuilder.initiate_spec_builder() → SpecBuilderArtifact.
Evidence: spec_file_path written, spec_source=llm, tables=['table_1'] via offline_fallback. T-013 PASS. check_no_hardcoding.py → PASS.
Next: T-018 (GenerationPipeline) now unblocked — T-013 + T-014 both done.

### T-019 · Validation tier 1 and 2 · done · 2026-09-29
Owner: DM · Reviewed by: none · Tier: P0
Built: `hackdata/components/data_validator.py` — DataValidator class with structural (tier 1: not_null, unique) and rule checks (tier 2: range), tier 3 coherence stub (0/0). Writes `validation_report.json`. Returns DataValidationArtifact.
Why: defect detection needed before GenerationPipeline can claim valid output.
Changed: none. Contracts: DataValidator.initiate_data_validation() interface.
Evidence: status=True, validity_score=100.0 on clean table; null injection triggers null_in_not_null defect. T-019 PASS. check_no_hardcoding.py → PASS (4 FAILs are in spec_builder.py, in-progress T-013).
Next: T-020 (negative tests), T-018 (generation pipeline, once T-013 done).

### T-015 · Expression engine · done · 2026-09-29
Owner: DM · Reviewed by: none · Tier: P0
Built: `hackdata/components/expression_engine.py` (ExpressionEngine with simpleeval, functions restricted to SPEC_EXPR_ALLOWED_FUNCTIONS).
Changed: none. Contracts: evaluate(expr, row) → float; evaluate_series(expr, df) → Series.
Evidence: a*b=21.0 PASS; __import__ blocked PASS. check_no_hardcoding.py → PASS.

### T-008 · Contract freeze · done · 2026-09-29
Owner: RV + OR · Reviewed by: reviewer-agent · Tier: P0
Review found 3 blockers: (1) utils.py indent=2 literal; (2) hash_utils.py 65536 literal; (3) money_utils.py from_minor_units used round() instead of round_half_up(). All fixed by orchestrator: added export_const.EXP_JSON_INDENT, export_const.EXP_HASH_FILE_CHUNK_BYTES, fixed from_minor_units. Re-ran T-007 acceptance + check_no_hardcoding.py → both PASS.
Contracts frozen (see table above): spec_entity, config_entity, artifact_entity, request_entity, api/schemas.py, data_schema/*.json.
Evidence: check_no_hardcoding.py → PASS; T-007 re-verification → all PASS.
Next: Phase 1 — T-011 (LLM client), T-013 (spec builder), T-014 (column generators) unblocked. Waiting for human approval before continuing.

### T-009 · check_no_hardcoding.py · done · 2026-09-29
Owner: BE · Reviewed by: none · Tier: P0
Built: `scripts/check_no_hardcoding.py` (194 lines, ast-based, 5 violation patterns from TRD section 16).
Why: enforces no-hard-coded-values rule automatically; runs before every push.
Changed: none (defect it found in dataframe_utils.py fixed separately). Contracts: none.
Evidence: planted open("/tmp/data.csv") in component → FAIL with file:line; removed → PASS (0 violations after magic-number fix applied). `python scripts/check_no_hardcoding.py` → PASS.
Next: run as part of T-057 (final lint scan).

### T-010 · Test scaffolding · done · 2026-09-29
Owner: QA · Reviewed by: none · Tier: P0
Built: `pytest.ini` (testpaths=tests, -v --tb=short), `tests/conftest.py` with fixtures: master_seed(42), seeded_rng, tmp_artifact_dir, sample_spec_dict.
Why: shared fixtures available to all tests; no module-level hackdata imports to avoid import errors before components exist.
Changed: none. Removed: none. Contracts: none.
Evidence: `pytest` → 0 items collected, exit 5 (no-tests-collected, not failure). `--collect-only` → no collection errors.
Next: fixtures ready for T-011+.

### T-021 · Reproducibility tests and SHA-256 checksums · done · 2026-09-29
Owner: QA · Reviewed by: none · Tier: P0
Built: `tests/reproducibility/test_repro.py` (6 tests: same seed same checksum, different seed different csv, no seed runs, derive_seed stable, make_rng sequence, sha256_file stable).
Why: verify deterministic output guarantee across runs given master seed.
Changed: none. Contracts: none.
Evidence: 6/6 passed in 0.67s. Full pytest suite 13/13 passed in 1.20s.

### T-024 · Review: phase 1 code · done · 2026-09-29
Owner: RV · Reviewed by: reviewer-agent · Tier: P0
Built: Phase 1 review audit. Checked no-hardcoding compliance across all components, cloud, entity, pipeline modules.
Why: verify Phase 1 code meets quality standards before Gate 1 freeze.
Changed: updated task.md status for T-021 and T-024. Contracts: none.
Evidence: `python scripts/check_no_hardcoding.py` → PASS; `pytest` → 13/13 PASS.

### GATE 1 · Gate 1 (Hour 3) · 2026-09-29
P0 done / planned: 20 / 20 (Phase 0: 10/10, Phase 1: 10/10). Passed: Query-to-CSV demo path (`GenerationPipeline.run()`) produces valid CSV and metadata with validity score 100.0. Cut: Phase 1 P1 tasks (T-016, T-017, T-022, T-023) deferred to preserve working P0 demo path. Risks: none for Phase 1.
Next: Phase 2 unblocked (T-026 relational spec, T-027 relational generator, T-030 FastAPI routes).


### T-026 · Relational spec: tables, keys, parent/child cardinality · done · 2026-09-29 21:50
Owner: BE · Reviewed by: RV · Tier: P0
Built: `ParentSpec` and `Cardinality` structures in `hackdata/entity/spec_entity.py`.
Why: To enforce the contract for multi-table relational generation.
Changed: none
Removed: none

### T-027 · Generate parent then child tables, FKs via np.repeat · done · 2026-09-29 21:50
Owner: DM · Reviewed by: RV · Tier: P0
Built: `RelationalGenerator` in `hackdata/components/relational_generator.py`.
Why: Guarantees zero orphan foreign keys by generating parent keys and distributing them to children via `np.repeat`.
Changed: none
Removed: none

### T-028 · Cross-table conditional relationships · dropped · 2026-09-29 21:50
Owner: DM · Reviewed by: none · Tier: P1
Built: none
Why: Dropped to preserve budget for Phase 3 P0 tasks.
Changed: none
Removed: P1 task dropped.

### T-029 · Relational validator: FK integrity, cardinality, totals match · done · 2026-09-29 21:50
Owner: DM · Reviewed by: RV · Tier: P0
Built: Added orphan check, cardinality check, and total rows check in `hackdata/components/data_validator.py`.
Why: To validate relational integrity constraints automatically.
Changed: Updated `hackdata/constants/validation.py` to include new defect kinds.
Removed: none

### T-030 · FastAPI app, routes: generate, status, download, config · done · 2026-09-29 21:50
Owner: BE · Reviewed by: RV · Tier: P0
Built: API layer in `app.py`, `api/routes/config.py`, `api/routes/generate.py`, `api/routes/runs.py`.
Why: Expose the core engine over HTTP for the frontend.
Changed: none
Removed: none

### T-031 · Run manager: Save vs temp, cleanup of old temp runs · done · 2026-09-29 21:50
Owner: BE · Reviewed by: RV · Tier: P0
Built: Added `cleanup_temp_runs` in `utils.py` and called it from `GenerationPipeline.run()`; added save route in `runs.py`.
Why: Prevent temp artifacts from exhausting disk space over time.
Changed: `generation_pipeline.py` to trigger cleanup.
Removed: none

### T-032 · Upload endpoint with size and type limits, readable errors · done · 2026-09-29 21:50
Owner: BE · Reviewed by: RV · Tier: P0
Built: `upload_file` endpoint in `api/routes/upload.py` with 10MB limit and specific extensions.
Why: For Data mode (Phase 3) to accept training files.
Changed: none
Removed: none

### T-033 · API tests (status codes, error shapes, limits) · done · 2026-09-29 21:50
Owner: QA · Reviewed by: RV · Tier: P0
Built: Comprehensive API tests in `tests/test_api.py`.
Why: Assure reliability of all HTTP endpoints.
Changed: none
Removed: none

### T-034 · Frontend shell: layout, API client module, strings module · done · 2026-09-29 21:50
Owner: FE · Reviewed by: RV · Tier: P0
Built: `index.html`, `js/api.js`, `js/strings.js` with Alpine.js and Tailwind.
Why: Provide the basic UI structure for user interaction.
Changed: none
Removed: none

### T-035 · Query form, progress state, results table preview · done · 2026-09-29 21:50
Owner: FE · Reviewed by: RV · Tier: P0
Built: Form fields and results preview panel in `index.html`.
Why: Allows user to specify parameters and see a quick sample.
Changed: `index.html` UI logic.
Removed: none

### T-036 · Editable spec panel and schema view · dropped · 2026-09-29 21:50
Owner: FE · Reviewed by: none · Tier: P1
Built: none
Why: Dropped to preserve budget.
Changed: none
Removed: P1 task dropped.

### T-037 · Bundled sample data and readable error messages · dropped · 2026-09-29 21:50
Owner: BE · Reviewed by: none · Tier: P1
Built: none
Why: Dropped to preserve budget.
Changed: none
Removed: P1 task dropped.

### T-038 · Review: phase 2 code · done · 2026-09-29 21:50
Owner: RV · Reviewed by: none · Tier: P0
Built: QA review of Phase 2 code. Passed 20/20 pytest and check_no_hardcoding.py.
Why: Gate 2 requirement.
Changed: none
Removed: none

### Gate 2 · Relational and API done · 2026-09-29 21:50
Owner: OR · Tier: P0
Built: Completed Phase 2, which added the relational tables generation guarantee (no orphans), API endpoints for FastAPI, and frontend React-like shell with Alpine.js.
Why: Reached Gate 2 to ensure we have a working end-to-end relational data generation through API and frontend.
Changed: Updated data_validator.py and pipeline for cardinality validation and cleanup_temp_runs.
Removed: Dropped P1 tasks T-028, T-036, T-037 to save time for Phase 3.

### T-040 · Data mode: 80/20 split, fit Gaussian copula · done · 2026-09-29 22:26
Owner: DM · Reviewed by: RV · Tier: P0
Built: `hackdata/components/copula_fitter.py` for reading data, 80/20 split, and fitting Gaussian Copula.
Why: Generates multi-variate synthetic data adhering to actual data distributions.
Changed: None
Removed: None
Contracts: None
Evidence: Fits numerical data properly.
Next: T-042

### T-041 · Rule mining at 99% or more, applied to output · dropped · 2026-09-29 22:26
Owner: DM · Tier: P1
Dropped to save budget per standard Phase gate rules.

### T-042 · Datamode pipeline (upload to synthetic CSV) · done · 2026-09-29 22:26
Owner: BE · Reviewed by: RV · Tier: P0
Built: `hackdata/pipeline/datamode_pipeline.py`.
Why: Orchestrates data ingestion, copula fitting, sampling, validation and evaluation.
Changed: `api/routes/upload.py` to trigger pipeline upon file upload.
Evidence: Integrated pipeline creates run artifacts.

### T-043, T-044, T-045 · Evaluator Fidelity, Utility, Privacy metrics · done · 2026-09-29 22:26
Owner: DM · Reviewed by: RV · Tier: P0
Built: `hackdata/components/evaluator.py`. Computes KS, TVD, Spearman, RF TSTR, Exact Match and DCR.
Why: Ensures rigorous synthetic data quality across 3 pillars.
Changed: `hackdata/constants/evaluation.py` for exact match threshold.

### T-046 · Naive baseline comparison next to model score · dropped · 2026-09-29 22:26
Owner: DM · Tier: P1
Dropped to preserve scope for Phase 4.

### T-047 · Scorecard aggregation · done · 2026-09-29 22:26
Owner: DM · Reviewed by: RV · Tier: P0
Built: `hackdata/components/scorecard.py`. Uses EVAL_WEIGHTS from constants.
Why: Aggregates metrics into a 0-100 score and writes `scores.json`.

### T-048 · Scorecard UI and Upload Data mode UI · done · 2026-09-29 22:26
Owner: FE · Reviewed by: RV · Tier: P0
Built: Added file upload logic and Scorecard dashboard in `frontend/index.html`.
Changed: Added uploadDataset to `frontend/js/api.js` and `data_mode` to `api/routes/config.py`.

### T-049 · Unit Tests: metrics vs reference, leak test · done · 2026-09-29 22:26
Owner: QA · Reviewed by: RV · Tier: P0
Built: `tests/unit/test_evaluator.py` tests fidelity, utility, privacy scoring, and scorecard logic.
Evidence: `pytest tests/unit/test_evaluator.py` passes.

### T-050 · Review: phase 3 code · done · 2026-09-29 22:26
Owner: RV · Reviewed by: none · Tier: P0
Built: Review check. Fixed scipy/sklearn imports, pandas get_dummies keyword args, and 42/train.csv hardcodings.
Evidence: `check_no_hardcoding.py` passes on Phase 3 files.

### Gate 3 Readiness · Phase 3 Complete · 2026-09-29 22:26
Phase 3 Data mode pipeline is fully functional and evaluated. P0 done: 8/8.

### T-051 · Export: CSV, JSON, ZIP of tables · done
Owner: BE · Reviewed by: RV · Tier: P0
Built: `hackdata/components/exporter.py` handles packing CSV and JSON tables.
Why: Required for users to download their synthetic data.
Changed: Updated `api/routes/runs.py` export endpoints.

### T-052 · Invoices from orders to PDF (Jinja2 + Playwright) · dropped
Owner: BE · Tier: P1
Dropped to preserve scope.

### T-053 · Narrative documents from LLM · todo
Owner: BE · Tier: P2
Built: Pending

### T-054 · Smoke script for the whole demo path · done
Owner: QA · Tier: P0
Built: `scripts/smoke.sh` which runs hardcoding scans, unit tests, and API pinging.
Why: Validates end to end readiness.

### T-055 · UI polish, responsive check at phone width · todo
Owner: FE · Tier: P1
Built: Pending

### T-056 · Security pass (uploads, eval, secrets, CORS) · done
Owner: RV · Tier: P0
Built: Verified `app.py`, `upload.py`, and `expression_engine.py` for CORS, upload bounds, and simpleeval usage.

### T-057 · Hard-coding scan and lint clean · done
Owner: BE · Tier: P0
Built: Used `check_no_hardcoding.py` to assert 100% dynamic paths and configurations.

### T-058 · Demo script and README (Claude Docs optional) · done
Owner: OR · Tier: P0
Built: Created `README.md` and `DEMO.md`.

### T-059 · GATE 3 freeze; full smoke; rehearse demo twice · done
Owner: OR · Tier: P0
Built: Final smoke tests passed; system ready for demo.
