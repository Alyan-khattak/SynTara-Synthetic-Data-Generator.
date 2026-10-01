# task.md — HackDataV2 implementation plan

Owner of this file: **orchestrator only**. Agents propose changes in their reports.
Status: `todo` · `doing` · `review` · `done` · `blocked` · `dropped` (never delete a row).
Tier: **P0** must ship · **P1** drop at Gate 1 if behind · **P2** only if time is left.
Agents: **BE** backend-agent · **FE** frontend-agent · **DM** data-ml-agent · **QA** qa-agent · **RV** reviewer-agent · **OR** orchestrator.
Every task follows the four team rules in `standards.md` (readable code with comments, plan first, reuse, use a library).
Paths are relative to the repo root; names come from `TRD.md` (sections 3 and 5). Where TRD.md and this file disagree, TRD.md wins and a `context.md` entry is written.

Budget: about 10 hours, 3 humans. **Gate 1 at hour 3**, **Gate 2 at hour 6**, **Gate 3 at hour 9 (freeze, demo rehearsal)**.

## Phase 0 — Foundation and contracts (hours 0 to 1.5)

| ID | Task | Tier | Owner | Files | Depends | Acceptance | Status |
|---|---|---|---|---|---|---|---|
| T-001 | Repo skeleton: folders, `__init__.py`, `.gitignore`, `requirements.txt` (pinned), `.env.example`, `setup.py` | P0 | BE | repo root, `hackdata/**/__init__.py` | — | `pip install -e .` works; `python -c "import hackdata"` passes | done |
| T-002 | Exception class `HackDataException` and logger (`logging` object, per-run file) | P0 | BE | `hackdata/exception/`, `hackdata/logging/` | T-001 | Raising and catching prints file and line; a log file is created | done |
| T-003 | Constants package: `common`, `paths`, `messages` first | P0 | BE | `hackdata/constants/` | T-001 | Modules import; no value duplicated | done |
| T-004 | Spec contract: Pydantic models for the closed spec vocabulary | P0 | BE | `hackdata/entity/spec_entity.py`, `constants/spec.py` | T-003 | Valid spec parses; unknown type rejected with readable message | done |
| T-005 | Config and artifact entities (typed dataclasses) | P0 | BE | `hackdata/entity/config_entity.py`, `artifact_entity.py` | T-003 | Dry run builds a timestamped `Artifacts/temp/<run>` config | done |
| T-006 | Scores JSON contract and API payload schemas | P0 | BE | `hackdata/entity/`, `api/schemas.py` | T-004 | Example payloads validate; frozen in `context.md` | done |
| T-007 | Utils: file IO, seeding (blake2b), hashing, timestamps | P0 | BE | `hackdata/utils/main_utils/` | T-003 | Same seed gives same value; different column gives different seed | done |
| T-008 | **Contract freeze** review | P0 | RV + OR | T-004 to T-007 outputs | T-004..T-007 | Reviewer approves; freeze entry in `context.md` | done |
| T-009 | `check_no_hardcoding.py` enforcement script | P0 | BE | `scripts/` | T-003 | Fails on a planted literal path; passes on clean tree | done |
| T-010 | Test scaffolding: pytest config, shared fixtures, seeded RNG fixture | P0 | QA | `tests/conftest.py` | T-001 | `pytest` runs and reports zero tests cleanly | done |

## Phase 1 — Tabular core (hours 1.5 to 4)

| ID | Task | Tier | Owner | Files | Depends | Acceptance | Status |
|---|---|---|---|---|---|---|---|
| T-011 | LLM boundary: Groq client, timeout, retries, key pool with cooldown | P0 | BE | `hackdata/cloud/llm_client.py`, `constants/llm.py` | T-008 | Stubbed test passes; real call returns text | done |
| T-012 | Reliability chain: cache, model fallback, offline fallback spec | P0 | BE | `cloud/`, `assets/` | T-011 | Killing the key falls through to offline spec | done |
| T-013 | Spec generation from query (prompt, JSON parse, Pydantic validate, one repair retry) | P0 | BE | `components/spec_generator.py` | T-011 | 5 sample queries give valid specs | done |
| T-014 | Column generators: numeric, categorical, date, id, text pools, money in minor units | P0 | DM | `components/table_generator.py`, `utils/ml_utils/` | T-008 | 10k rows in under 2 s; ranges respected; reproducible | done |
| T-015 | Safe expression evaluator for derived columns (`simpleeval`) | P0 | DM | `components/expression_engine.py` | T-014 | `a*b` works; `__import__` is refused | done |
| T-016 | Conditional distributions and rules engine (segment-based) | P1 | DM | `components/conditional_engine.py` | T-014 | Segment means differ as specified | todo |
| T-017 | Seasonality and trend on date columns | P1 | DM | `components/table_generator.py` | T-014 | Monthly counts follow the given profile | todo |
| T-018 | Generation pipeline (query to CSV) with artifacts | P0 | BE | `pipeline/generation_pipeline.py` | T-013, T-014 | One call writes CSV and metadata to `Artifacts/temp` | done |
| T-019 | Validation tier 1 and 2: structural and rule checks | P0 | DM | `components/validator.py` | T-014 | Report lists checks with pass or fail | done |
| T-020 | Negative tests for validator plus corrupt function | P0 | QA | `tests/test_validator_negative.py` | T-019 | Each planted defect is caught with the right count | done |
| T-021 | Reproducibility tests and SHA-256 checksums | P0 | QA | `tests/test_repro.py`, `utils/` | T-018 | Same seed gives equal checksums | done |
| T-022 | Feasibility check of the request | P1 | BE | `components/feasibility.py` | T-013 | Impossible spec returns readable message | dropped |
| T-023 | Locale profile: Pakistan phones, names, PKR grouping | P1 | DM | `constants/locales.py`, `components/` | T-014 | Phone numbers match pattern; **VERIFY** ID, GST, Eid values | dropped |
| T-024 | Review: phase 1 code | P0 | RV | phase 1 files | T-014..T-019 | Report with verdict; blockers fixed | done |
| **T-025** | **GATE 1 (hour 3)** run query to CSV demo; count P0 done; cut P1 if behind | P0 | OR | — | T-018, T-019, T-020 | Gate entry in `context.md` | done |

## Phase 2 — Relational and API (hours 4 to 6)

| ID | Task | Tier | Owner | Files | Depends | Acceptance | Status |
|---|---|---|---|---|---|---|---|
| T-026 | Relational spec: tables, keys, parent/child cardinality | P0 | BE | `entity/spec_entity.py` | T-025 | Multi-table spec validates | done |
| T-027 | Generate parent then child tables, FKs via `np.repeat` | P0 | DM | `components/relational_generator.py` | T-026 | Zero orphan keys | done |
| T-028 | Cross-table conditional relationships | P1 | DM | `components/relational_generator.py` | T-027, T-016 | Child attribute depends on parent segment | dropped |
| T-029 | Relational validator: FK integrity, cardinality, totals match | P0 | DM | `components/validator.py` | T-027 | Orphan and total mismatch detected | done |
| T-030 | FastAPI app, routes: generate, status, download, config | P0 | BE | `app.py`, `api/routes/` | T-018 | `/docs` lists routes; generate returns run id | done |
| T-031 | Run manager: Save vs temp, cleanup of old temp runs | P0 | BE | `pipeline/`, `utils/` | T-030 | Unsaved runs disappear; saved persist | done |
| T-032 | Upload endpoint with size and type limits, readable errors | P0 | BE | `api/routes/upload.py` | T-030 | 10 MB cap; bad file returns clear message | done |
| T-033 | API tests (status codes, error shapes, limits) | P0 | QA | `tests/test_api.py` | T-030, T-032 | All pass with stubbed LLM | done |
| T-034 | Frontend shell: layout, API client module, strings module | P0 | FE | `frontend/` | T-006 | Page loads; one module calls the backend | done |
| T-035 | Query form, progress state, results table preview | P0 | FE | `frontend/` | T-034, T-030 | Query returns preview; loading, empty, error states work | done |
| T-036 | Editable spec panel and schema view | P1 | FE | `frontend/` | T-035 | Edit a field, regenerate, see the change | dropped |
| T-037 | Bundled sample data and readable error messages | P1 | BE | `assets/`, `constants/messages.py` | T-032 | One-click sample loads | dropped |
| T-038 | Review: phase 2 code | P0 | RV | phase 2 files | T-027..T-033 | Verdict; blockers fixed | done |
| **T-039** | **GATE 2 (hour 6)** relational demo end to end through the UI; cut P1 | P0 | OR | — | T-029, T-033, T-035 | Gate entry in `context.md` | done |

## Phase 3 — Data mode and scorecard (hours 6 to 8.5)

| ID | Task | Tier | Owner | Files | Depends | Acceptance | Status |
|---|---|---|---|---|---|---|---|
| T-040 | Data mode: 80/20 split, fit Gaussian copula on train only | P0 | DM | `components/copula_fitter.py` | T-039 | No hold-out rows used in fit | done |
| T-041 | Rule mining at 99% or more, applied to output | P1 | DM | `components/rule_miner.py` | T-040 | Mined rule holds on 99% of synthetic rows | dropped |
| T-042 | Datamode pipeline (upload to synthetic CSV) | P0 | BE | `pipeline/datamode_pipeline.py` | T-040 | Upload CSV in, synthetic CSV out | done |
| T-043 | Fidelity metrics: KS, TVD, Spearman (SciPy) | P0 | DM | `components/evaluator.py` | T-040 | Matches SciPy reference values | done |
| T-044 | Utility metrics: TSTR and TRTS with RandomForest | P0 | DM | `components/evaluator.py` | T-043 | Scores reported with reference badges | done |
| T-045 | Privacy metrics: exact match rate, nearest-neighbour ratio | P0 | DM | `components/evaluator.py` | T-040 | Copy of train gives worst privacy score | done |
| T-046 | Naive baseline comparison next to model score | P1 | DM | `components/evaluator.py` | T-044 | Baseline shown beside each score | dropped |
| T-047 | Scorecard aggregation with weights 0.25/0.25/0.30/0.20 | P0 | DM | `components/scorecard.py` | T-043..T-045 | Overall score in 0 to 100; weights come from constants | done |
| T-048 | Scorecard UI: four panels, badges, vs-spec label | P0 | FE | `frontend/` | T-047, T-035 | Panels render from the JSON contract | done |
| T-049 | Tests: metrics vs reference, leak test (perfect copy flagged) | P0 | QA | `tests/` | T-043..T-047 | Copy-of-train test fails privacy as expected | done |
| T-050 | Review: phase 3 code | P0 | RV | phase 3 files | T-040..T-047 | Verdict; blockers fixed | done |

## Phase 4 — Export, documents, polish (hours 8.5 to 10)

| ID | Task | Tier | Owner | Files | Depends | Acceptance | Status |
|---|---|---|---|---|---|---|---|
| T-051 | Export: CSV, JSON, ZIP of tables | P0 | BE | `components/exporter.py` | T-042 | Download opens correctly | done |
| T-052 | Invoices from orders to PDF (Jinja2 + Playwright), cap 50 | P1 | BE | `components/invoice_builder.py`, `templates/` | T-027 | 50 PDFs; totals match orders | dropped |
| T-053 | Narrative documents from LLM | P2 | BE | `pipeline/document_pipeline.py` | T-052 | One document set generated | todo |
| T-054 | Smoke script for the whole demo path | P0 | QA | `scripts/smoke.sh` | T-051 | One command passes before every push | done |
| T-055 | UI polish, responsive check at phone width | P1 | FE | `frontend/` | T-048 | No horizontal scroll at 375 px | todo |
| T-056 | Security pass (uploads, `eval`, secrets, CORS) | P0 | RV | whole repo | T-051 | No blocker left | done |
| T-057 | Hard-coding scan and lint clean | P0 | BE | whole repo | T-056 | Enforcement script passes | done |
| T-058 | Demo script and README (Claude Docs optional) | P0 | OR | `README.md`, `DEMO.md` | T-054 | A stranger can run it in 5 minutes | done |
| **T-059** | **GATE 3 (hour 9)** freeze; full smoke; rehearse demo twice | P0 | OR | — | T-054, T-056, T-057 | Gate entry; only bug fixes after this | done |

## Open decisions (human)

| ID | Decision | Default if no answer |
|---|---|---|
| D-1 | Track owners (who runs which agents) | Person 1 backend, 2 data-ml, 3 frontend; QA and review shared |
| D-2 | React or plain HTML for the frontend | Plain HTML plus a light library (faster to build) |
| D-3 | Groq model bake-off | Use the fastest model that returns valid JSON on 5 sample queries |
| D-4 | Lakh or western PKR grouping | Lakh (assumed, VERIFY) |
| D-5 | Sample data choice | One small retail dataset |
| D-6 | VERIFY items: ID marker digit, GST 18%, Eid dates | Keep flagged in constants until confirmed |

## Adding tasks

Append new IDs at the end of their phase (`T-0xx`, next free number). A bug becomes a task owned by the agent that wrote the code, checked by QA.
