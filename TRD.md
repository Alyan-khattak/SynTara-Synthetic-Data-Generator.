# HackDataV2 Synthetic Data Platform — Technical Requirements Document (TRD)

Version 1.0 · 2026-09-29 · Build specification. Read `PRD.md` for what we build and `HackDataV2_Architecture.md` (the "architecture record", **AR**) for why we decided each thing.

This TRD follows the project structure and coding standards of your **Network Security MLOps** project (also used in Car Price ANN and Movie Sentiment RNN): constants, config and artifact entities, separate components, a pipeline, common code in utils, one custom exception, one logger, and **no hard-coded values**.

**Status labels:** **DECIDED** confirmed · **ASSUMED** my choice, veto freely · **PROPOSED** default for an undiscussed detail · **OPEN** undecided · **VERIFY** outside fact to check.

---

## 1. Can we build it like Network Security? Yes, with four adaptations

Everything carries over: the layered architecture, typed entities, timestamped artifacts, one exception, one logger, constants-only values. Four things must change because this is a **generation platform, not a training pipeline**, and because **three people** work in it at once.

| # | Network Security convention | HackDataV2 adaptation | Reason |
|---|---|---|---|
| 1 | One constants file `constants/training_pipeline/__init__.py` | **A constants package with one module per domain** (`common`, `paths`, `llm`, `generation`, `validation`, `evaluation`, `data_mode`, `documents`, `locales`, `export`, `api`, `messages`), each using the NS prefix style (`LLM_…`, `GEN_…`) | Three people editing one file means constant merge conflicts. Same rule, split by domain. |
| 2 | Pipeline is Ingestion → Validation → Transformation → ModelTrainer | **Three pipelines** (`generation`, `datamode`, `document`) composed of shared components; `ModelTrainer` becomes `ModelFitter` (data mode only) | We generate, validate and score data; only data mode fits a model. |
| 3 | Everything in `app.py` | **Thin `app.py` plus `api/routes/`** | About 20 endpoints; one file would be unmanageable. |
| 4 | Artifacts written in every run, timestamped | Same, in `Artifacts/temp/<timestamp>/`; **Save moves the run to `Artifacts/saved/`**; only the last 10 temp runs are kept | Preserves "temporary until Save" (AR 15.1) while keeping NS-style path-based typed artifacts. This replaces the in-memory cache described in AR 6.3 and 15.1; user-visible behaviour is identical. |

**Honest cost:** this structure adds boilerplate (constants, config classes, artifact dataclasses). I estimate about 1 extra hour across the team, on a budget that is already tight (AR 20.1). It is paid for by generating the whole skeleton with Claude Code **in the first 45 minutes** and by fewer integration bugs. I still recommend it.

**Deviations from the NS standard** are listed in section 21 so nothing is silent.

---

## 2. Technology stack

### 2.1 Runtime and libraries (DECIDED unless noted)

| Layer | Package | Role | Note |
|---|---|---|---|
| Language | Python 3.11 or newer | Everything | Pin one version team-wide |
| Web | `fastapi`, `uvicorn`, `python-multipart` | API, uploads, static frontend | |
| Spec and API models | `pydantic` v2 | Spec validation, request and response models | |
| Safe expressions | `simpleeval` | Row-level derived values | Never `eval` |
| Data | `pandas`, `numpy` | Generation and I/O | |
| Statistics | `scipy` | `ks_2samp`, `norm`, Spearman, Cholesky helpers | |
| ML evaluation | `scikit-learn` | RandomForest (TSTR/TRTS), NearestNeighbors, scalers | `n_jobs=1` |
| Fake values | `faker` | Fallback and offline path | |
| Documents | `jinja2`, `playwright` (Chromium) | HTML templates to PDF | One browser instance |
| LLM HTTP | `httpx` | Groq and OpenRouter through OpenAI-compatible endpoints | No LangChain |
| Config | `python-dotenv`, `pyyaml` | `.env`, YAML templates and schemas | |
| Serialisation | `dill` | Saving fitted objects (NS convention) | Argument order: `dill.dump(obj, file)` |
| Dates | `babel` (dates only, PROPOSED) | Locale date formats | PKR grouping is hand-written |
| Packaging | `setuptools` | `pip install -e .` via `setup.py` | NS convention |

### 2.2 Dev and quality tools

| Tool | Use |
|---|---|
| `pytest`, `pytest-cov` | Unit, integration, negative and reproducibility tests |
| `flake8` (NS used it in CI) or `ruff` | Lint. Pick one, ASSUMED `ruff` for speed |
| `httpx` `TestClient` (FastAPI) | API tests |
| `scripts/check_no_hardcoding.py` | Enforces the no-hard-coded-values rule (section 16) |

### 2.3 Frontend (OPEN, decide by hour 3)

| Option | Stack | Choose when |
|---|---|---|
| **A** | Vite, React, Tailwind; Chart.js; Mermaid for the FK diagram; `vite build` served by FastAPI | Someone has shipped a React app recently |
| **B (my lean)** | One HTML page, Alpine.js and Tailwind from a CDN; Chart.js; Mermaid; served by FastAPI | Otherwise |

### 2.4 External services

| Service | Required | Use |
|---|---|---|
| **Groq** (OpenAI-compatible) | Yes | Spec, pools, narrative text |
| OpenRouter | Optional | Fallback |
| Jev (TypeSafe AI) | Optional, P2 | Column classification, routing |

Not used: SDV (later, in a separate venv), SDMetrics, CTGAN, TVAE, LangChain, any database server, Redis, Celery. **MLflow, DagsHub and HuggingFace Hub** (used in NS) are **not in the MVP**: there is no trained model to register. A `track_mlflow()` hook for run scores can be added as P2 behind a constant flag, following the NS rule that `dagshub.init()` lives inside the function.

### 2.5 Files that pin the environment

`requirements.txt` (runtime, exact versions, because reproducibility hashes depend on the NumPy version), `requirements-dev.txt` (pytest, lint), `setup.py` (reads `requirements.txt`, ignores `-e .`, as in NS).

---

## 3. Repository structure

Track owners: **A** engine and LLM, **B** data mode and evaluation, **C** product (API, UI, documents). Tier in brackets when not P0.

```
HackDataV2/
│
├── app.py                              ← FastAPI app: lifespan, routers, static files (thin)            [C]
├── main.py                             ← CLI entry: run a pipeline without the API                      [A]
├── setup.py                            ← pip install -e .  (reads requirements.txt)                     [A]
├── requirements.txt                    ← pinned runtime deps
├── requirements-dev.txt                ← pytest, lint
├── .env.example                        ← key names only, never values
├── .gitignore
├── Readme.md
├── PRD.md   TRD.md
├── Dockerfile   .dockerignore          ← P2
├── .github/workflows/main.yml          ← P2: lint + tests
│
├── hackdata/                           ← main package (lowercase, no spaces)
│   ├── __init__.py
│   │
│   ├── constants/                      ← ALL fixed values (section 5)
│   │   ├── __init__.py
│   │   ├── common.py                   ← pipeline name, timestamp formats, env var names
│   │   ├── paths.py                    ← directory and file names
│   │   ├── messages.py                 ← every user-facing message and error template
│   │   ├── llm.py                      ← models, URLs, limits, cooldowns, prompt file names
│   │   ├── spec.py                     ← generator, rule and distribution vocabularies
│   │   ├── generation.py               ← seeds, caps, sizes, edge-case defaults
│   │   ├── validation.py               ← tolerances, tiers, defect kinds
│   │   ├── evaluation.py               ← metric params, weights, thresholds
│   │   ├── data_mode.py                ← inference thresholds, copula params, caps
│   │   ├── documents.py                ← PDF options, caps, region profiles keys
│   │   ├── locales.py                  ← locale codes and formats (plural, so it never clashes with stdlib locale)
│   │   ├── export.py                   ← formats, SQL dialect, hash algorithm
│   │   └── api.py                      ← API prefix, cache sizes, status names
│   │
│   ├── entity/                         ← typed contracts (section 6)
│   │   ├── __init__.py
│   │   ├── config_entity.py            ← RunConfig + one config class per component     [A]
│   │   ├── artifact_entity.py          ← one @dataclass per component output            [A]
│   │   ├── spec_entity.py              ← Pydantic spec models (the LLM/engine contract) [A]
│   │   └── request_entity.py           ← GenerationRequest, UploadRequest dataclasses   [A]
│   │
│   ├── components/                     ← one class per stage (section 7)
│   │   ├── __init__.py
│   │   ├── spec_builder.py             ← query to validated spec             [A]
│   │   ├── feasibility_checker.py      ← impossible-request check            [B]
│   │   ├── data_ingestion.py           ← upload read, encoding sniff, 80/20 split [B]
│   │   ├── schema_inference.py         ← types, PK, FK detection             [B]
│   │   ├── model_fitter.py             ← copula and cardinality fit          [B]
│   │   ├── rule_miner.py               ← closed-set rule mining              [B] (P1)
│   │   ├── data_generator.py           ← seeded generation orchestrator      [A]
│   │   ├── data_validator.py           ← three-tier validation               [A]
│   │   ├── evaluator.py                ← scorecard                           [B]
│   │   ├── document_renderer.py        ← Jinja2 to HTML to PDF               [C]
│   │   ├── exporter.py                 ← CSV, JSON, SQL, PDF zip, checksums  [C]
│   │   ├── dataset_corruptor.py        ← demo and tests: inject defects      [A]
│   │   └── generators/                 ← engine internals used by DataGenerator
│   │       ├── __init__.py
│   │       ├── column_generators.py    ← the generator vocabulary            [A]
│   │       ├── relational_engine.py    ← order, cardinality, FK, aggregates  [A]
│   │       ├── conditional.py          ← segment-driven behaviour            [A]
│   │       ├── seasonality.py          ← date weighting                      [A] (P1)
│   │       ├── edge_cases.py           ← nulls, outliers                     [A]
│   │       ├── privacy_controls.py     ← mask, hash, Laplace noise           [A]
│   │       └── document_facts.py       ← structured document data            [C]
│   │
│   ├── modules/                        ← the three product modules (thin)
│   │   ├── __init__.py
│   │   ├── tabular.py                  ← request → spec → pipeline           [A]
│   │   ├── relational.py               ←                                     [A]
│   │   └── documents.py                ←                                     [C]
│   │
│   ├── pipeline/                       ← orchestration (section 8)
│   │   ├── __init__.py
│   │   ├── generation_pipeline.py      ← query mode                          [A]
│   │   ├── datamode_pipeline.py        ← upload mode                         [B]
│   │   ├── document_pipeline.py        ← documents, invoices from orders     [C]
│   │   └── run_manager.py              ← temp cache, Save, eviction, history [C]
│   │
│   ├── cloud/                          ← the ONLY place that talks to outside services
│   │   ├── __init__.py
│   │   ├── llm_client.py               ← Groq/OpenRouter calls, fallback chain, repair retry [A]
│   │   ├── key_pool.py                 ← key list, cooldown on 429           [A]
│   │   ├── llm_cache.py                ← disk cache by query hash            [A]
│   │   ├── offline_fallback.py         ← Faker plus templates when all else fails [A]
│   │   ├── prompt_loader.py            ← loads prompt files from data_assets [A]
│   │   └── jev_client.py               ← P2                                  [B]
│   │
│   ├── utils/                          ← common functionality (section 9)
│   │   ├── __init__.py
│   │   ├── main_utils/
│   │   │   ├── __init__.py
│   │   │   ├── utils.py                ← save/load object, yaml, json, numpy, ensure_dir
│   │   │   ├── seed_utils.py           ← derive_seed, make_rng
│   │   │   ├── hash_utils.py           ← sha256 of files and text
│   │   │   ├── money_utils.py          ← minor units, rounding
│   │   │   ├── format_utils.py         ← PKR lakh or western grouping, dates, phones
│   │   │   ├── canonical_io.py         ← deterministic CSV, JSON, SQL writers
│   │   │   ├── dataframe_utils.py      ← safe CSV read, dtype helpers
│   │   │   └── env_utils.py            ← read env vars, key lists
│   │   └── ml_utils/
│   │       ├── __init__.py
│   │       ├── metric/
│   │       │   ├── __init__.py
│   │       │   ├── fidelity_metric.py  ← KS, TVD, correlation difference
│   │       │   ├── utility_metric.py   ← TSTR, TRTS, TRTR
│   │       │   ├── privacy_metric.py   ← exact match, nearest neighbour
│   │       │   ├── coherence_metric.py ← group order, bounds, rate tolerance
│   │       │   └── overall_score.py    ← weights and aggregation
│   │       └── model/
│   │           ├── __init__.py
│   │           ├── fitter_interface.py ← Fitter protocol (SDV slot)
│   │           └── copula_model.py     ← FittedTableModel: fit and sample
│   │
│   ├── exception/
│   │   ├── __init__.py
│   │   └── exception.py                ← HackDataException
│   └── logging/
│       ├── __init__.py
│       └── logger.py                   ← logging setup
│
├── api/                                ← HTTP layer (section 12)                      [C]
│   ├── __init__.py
│   ├── schemas.py                      ← Pydantic request and response models
│   ├── dependencies.py                 ← shared FastAPI dependencies
│   ├── error_handlers.py               ← exceptions to readable JSON
│   └── routes/
│       ├── __init__.py
│       ├── generate.py   upload.py   spec.py   runs.py
│       ├── documents.py  export.py   demo.py   health.py
│
├── data_schema/                        ← JSON Schemas for the contracts
│   ├── spec.schema.json
│   └── scores.schema.json
│
├── data_assets/                        ← content, not constants (section 14)
│   ├── templates/          ecommerce.yaml  banking.yaml  invoicing.yaml
│   ├── locales/pk/         names.json  cities.json  areas.json  mobile_prefixes.json  landline_codes.json
│   ├── calendars/          pk.json
│   ├── prompts/            spec_prompt.txt  pool_prompt.txt  narrative_prompt.txt  repair_prompt.txt
│   ├── document_templates/ invoice.html.j2  statement.html.j2  base.css  (narrative: P2)
│   └── sample/             customers.csv  orders.csv  order_items.csv  customers_churn.csv  README.md
│
├── frontend/                           ← option A or B (section 2.3)                 [C]
├── templates/                          ← only if the frontend is served as Jinja pages
│
├── tests/
│   ├── unit/           test_seed_utils.py  test_feasibility.py  test_conditional.py …
│   ├── integration/    test_generation_pipeline.py  test_datamode_pipeline.py  test_api.py
│   ├── negative/       test_validator_negative.py
│   ├── reproducibility/ test_repro_hash.py
│   └── fixtures/
│
├── scripts/
│   ├── scaffold.sh                     ← creates empty package tree and __init__.py files
│   ├── smoke_demo.py                   ← full demo path; run before every push
│   ├── precache_demo.py                ← pre-run every demo query
│   ├── make_sample_data.py             ← builds data_assets/sample
│   └── check_no_hardcoding.py          ← lint rule for constants-only values
│
├── Artifacts/                          ← generated, gitignored (section 8.4)
│   ├── temp/<timestamp>/
│   └── saved/<timestamp>/
├── cache/                              ← LLM cache, gitignored
└── logs/                               ← log files, gitignored
```

**Import direction (enforced by review and by the script in section 16):**

```
constants  →  exception, logging  →  entity  →  utils  →  cloud  →  components  →  modules  →  pipeline  →  api / app / main
```

A layer may import from layers to its left only. `components` never import from `pipeline` or `api`. Only `cloud/` makes network calls.

**Note on package names:** `hackdata/logging/` shadows the stdlib name only if you run a script from inside that folder. Always run from the repo root after `pip install -e .`, or use `python -m`. This is the same trap as the NS `ModuleNotFoundError` you hit; fix is the same.

---

## 4. Layered architecture

```
                      ┌───────────────────────────────┐
   Browser  ─────────▶│  app.py + api/routes (thin)   │
                      └───────────────┬───────────────┘
                                      ▼
                      ┌───────────────────────────────┐
                      │ modules/  tabular · relational · documents │   (request → spec, pick pipeline)
                      └───────────────┬───────────────┘
                                      ▼
   ┌──────────────── pipeline/ ──────────────────────────────────────────────┐
   │ generation_pipeline   datamode_pipeline   document_pipeline   run_manager │
   └───────────────┬──────────────────────────────────────────────────────────┘
                   ▼
   ┌──────────────── components/ (one class per stage) ──────────────────────┐
   │ SpecBuilder · FeasibilityChecker · DataIngestion · SchemaInference        │
   │ ModelFitter · RuleMiner · DataGenerator(+generators/) · DataValidator     │
   │ Evaluator · DocumentRenderer · Exporter · DatasetCorruptor                │
   └───────┬─────────────────────────┬────────────────────────────────────────┘
           ▼                         ▼
   utils/ (common)              cloud/ (Groq, cache, keys, offline)
           ▼                         ▼
   entity/ (config, artifact, spec)   constants/   exception/   logging/
```

Data flow is exactly the AR system architecture (AR 6): the LLM produces a spec and pools, the generation core builds all data, the validator and scorer check it, the exporter delivers it.

---

## 5. Constants (no hard-coded values)

### 5.1 Rules

1. **Every fixed value lives in `hackdata/constants/`.** That includes paths, file names, directory names, thresholds, sizes, weights, model IDs, URLs, vocabulary lists, format strings and **user-facing messages** (`messages.py`).
2. **Naming** follows NS: `ALL_CAPS_SNAKE_CASE` with a domain prefix (`LLM_`, `GEN_`, `VAL_`, `EVAL_`, `DM_`, `DOC_`, `LOC_`, `EXP_`, `API_`), type-hinted.
3. **Import the module, not the name:** `from hackdata.constants import generation` then `generation.GEN_MAX_ROWS_PER_TABLE`. This makes every use greppable.
4. **Secrets are never constants.** Only environment variable **names** are constants (`ENV_GROQ_API_KEYS`); values come from `.env`.
5. **Content is not a constant.** Prompts, templates, name pools, calendars and sample data live in `data_assets/` and are referenced by constant file names.
6. Paths are built with `os.path.join` from constant parts, never with literal slashes.

### 5.2 Contents by module (values from the architecture record; PROPOSED unless noted)

**`common.py`**

```python
PIPELINE_NAME: str = "HackDataV2"
PACKAGE_NAME: str = "hackdata"
RUN_TIMESTAMP_FORMAT: str = "%m_%d_%Y_%H_%M_%S_%f"   # NS format plus microseconds: two quick Enters must not collide
LOG_TIMESTAMP_FORMAT: str = "%m_%d_%Y_%H_%M_%S"
LOG_FORMAT: str = "[ %(asctime)s ] %(lineno)d %(name)s - %(levelname)s - %(message)s"
ENV_GROQ_API_KEYS: str = "GROQ_API_KEYS"             # comma separated
ENV_OPENROUTER_API_KEY: str = "OPENROUTER_API_KEY"
ENV_JEV_API_KEY: str = "JEV_API_KEY"
MODE_QUERY: str = "query"
MODE_DATA: str = "data"
MODULE_TABULAR: str = "tabular"
MODULE_RELATIONAL: str = "relational"
MODULE_DOCUMENTS: str = "documents"
```

**`paths.py`**

```python
ARTIFACT_DIR: str = "Artifacts"
ARTIFACT_TEMP_DIR_NAME: str = "temp"
ARTIFACT_SAVED_DIR_NAME: str = "saved"
LOGS_DIR: str = "logs"
CACHE_DIR: str = "cache"
DATA_ASSETS_DIR: str = "data_assets"
TEMPLATES_ASSETS_DIR: str = "templates"
PROMPTS_DIR: str = "prompts"
SAMPLE_DATA_DIR: str = "sample"
SCHEMA_DIR: str = "data_schema"
SPEC_SCHEMA_FILE_NAME: str = "spec.schema.json"
# per-stage artifact directory names
SPEC_BUILDER_DIR_NAME: str = "spec_builder"
FEASIBILITY_DIR_NAME: str = "feasibility"
DATA_INGESTION_DIR_NAME: str = "data_ingestion"
SCHEMA_INFERENCE_DIR_NAME: str = "schema_inference"
MODEL_FITTER_DIR_NAME: str = "model_fitter"
RULE_MINER_DIR_NAME: str = "rule_miner"
DATA_GENERATION_DIR_NAME: str = "data_generation"
DATA_VALIDATION_DIR_NAME: str = "data_validation"
EVALUATION_DIR_NAME: str = "evaluation"
DOCUMENTS_DIR_NAME: str = "documents"
EXPORT_DIR_NAME: str = "export"
# file names
SPEC_FILE_NAME: str = "spec.json"
POOLS_FILE_NAME: str = "pools.json"
SEED_FILE_NAME: str = "seed.txt"
SCORES_FILE_NAME: str = "scores.json"
VALIDATION_REPORT_FILE_NAME: str = "validation_report.json"
FEASIBILITY_REPORT_FILE_NAME: str = "feasibility_report.json"
CHECKSUMS_FILE_NAME: str = "checksums.json"
RUN_META_FILE_NAME: str = "meta.json"
FITTED_MODEL_FILE_NAME: str = "fitted_model.pkl"
LEARNED_SPEC_FILE_NAME: str = "learned_spec.json"
RULES_FILE_NAME: str = "mined_rules.yaml"
TABLES_DIR_NAME: str = "tables"
TRAIN_DIR_NAME: str = "train"
HOLDOUT_DIR_NAME: str = "holdout"
```

**`generation.py`**

```python
GEN_MAX_ROWS_PER_TABLE: int = 100_000
GEN_DEFAULT_NULL_RATE: float = 0.02
GEN_DEFAULT_OUTLIER_RATE: float = 0.005
GEN_OUTLIER_SCALE_MIN: float = 3.0
GEN_MAX_CONDITION_GROUPS: int = 5
GEN_SEED_DIGEST_SIZE: int = 8                 # blake2b bytes
GEN_SEED_SEPARATOR: str = "|"
GEN_MAX_PARENT_HOPS: int = 2
GEN_SEASONALITY_MAX_RESAMPLE_ROUNDS: int = 5
GEN_ROUNDING_MODE: str = "half_up"
GEN_MAX_RUNS_KEPT_TEMP: int = 10
GEN_MASK_CHAR: str = "*"
GEN_NOISE_DEFAULT_SCALE: float = 0.0
GEN_POOL_SIZE_MIN: int = 200
GEN_POOL_SIZE_MAX: int = 300
```

**`spec.py`** (vocabularies used by Pydantic validators)

```python
SPEC_VERSION: str = "1"
SPEC_GENERATORS: tuple = ("sequence", "uuid", "int_range", "float_range", "money", "categorical",
                          "boolean", "date_range", "date_offset", "pool", "email", "phone", "faker",
                          "expr", "aggregate", "conditional", "text", "national_id")
SPEC_RULES: tuple = ("not_null", "unique", "range", "after", "sum_of", "equals_expr", "running_balance",
                     "max_children", "min_children", "status_from_dates", "group_order",
                     "bound_by_group", "share_within")
SPEC_DISTRIBUTIONS: tuple = ("uniform", "normal", "lognormal", "poisson", "recent_weighted")
SPEC_EXPR_ALLOWED_FUNCTIONS: tuple = ("round", "min", "max", "abs", "int", "float")
SPEC_FAKER_ALLOWLIST: tuple = ("name", "address", "company", "job", "text")   # extend deliberately
```

**`llm.py`** (model IDs and limits are **VERIFY**; take exact values from the Groq console after the bake-off)

```python
LLM_GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
LLM_OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
LLM_MODEL_SPEC_PRIMARY: str = "openai/gpt-oss-120b"        # VERIFY
LLM_MODEL_SPEC_ALTERNATE: str = "llama-3.3-70b-versatile"  # VERIFY
LLM_MODEL_POOL: str = "llama-3.1-8b-instant"               # VERIFY
LLM_MODEL_FALLBACK_CHAIN: tuple = (LLM_MODEL_SPEC_PRIMARY, LLM_MODEL_POOL)
LLM_TIMEOUT_SECONDS: float = 30.0
LLM_MAX_REPAIR_RETRIES: int = 1
LLM_KEY_COOLDOWN_SECONDS: int = 60
LLM_POOL_CALL_SPACING_SECONDS: float = 2.0
LLM_CALLS_PER_QUERY_MAX: int = 4
LLM_CACHE_KEY_ALGORITHM: str = "sha256"
LLM_PROMPT_FILES: dict = {"spec": "spec_prompt.txt", "pool": "pool_prompt.txt",
                          "narrative": "narrative_prompt.txt", "repair": "repair_prompt.txt"}
```

**`validation.py`**

```python
VAL_TIER_STRUCTURAL: int = 1
VAL_TIER_RULES: int = 2
VAL_TIER_COHERENCE: int = 3
VAL_AGGREGATE_TOLERANCE_MINOR_UNITS: int = 1
VAL_COHERENCE_MIN_GROUP_ROWS: int = 30
VAL_COHERENCE_TOLERANCE_STD_ERRORS: float = 3.0
VAL_COHERENCE_TOLERANCE_MIN_PP: float = 0.01
VAL_DEFECT_KINDS: tuple = ("orphan_fk", "duplicate_pk", "missing_parent", "null_in_not_null",
                           "negative_quantity", "wrong_total", "bad_status", "group_bound")
```

**`evaluation.py`**

```python
EVAL_WEIGHTS: dict = {"validity": 0.25, "fidelity": 0.25, "utility": 0.30, "privacy": 0.20}
EVAL_RF_N_ESTIMATORS: int = 100
EVAL_RF_MAX_DEPTH: int = 12
EVAL_RF_N_JOBS: int = 1
EVAL_UTILITY_MAX_TRAIN_ROWS: int = 20_000
EVAL_TARGET_MIN_CLASSES: int = 2
EVAL_TARGET_MAX_CLASSES: int = 10
EVAL_ONEHOT_MAX_CARDINALITY: int = 20
EVAL_PRIVACY_MAX_SAMPLE_ROWS: int = 5_000
EVAL_PRIVACY_NN_FLAG_THRESHOLD: float = 0.8
EVAL_CORRELATION_METHOD: str = "spearman"
EVAL_SCORE_SCALE: int = 100
EVAL_REFERENCE_REAL_HOLDOUT: str = "vs. real hold-out"
EVAL_REFERENCE_REAL_TRAIN: str = "vs. real train"
EVAL_REFERENCE_SPEC: str = "vs. spec"
EVAL_REFERENCE_STRUCTURAL: str = "structural"
```

**`data_mode.py`**

```python
DM_TRAIN_TEST_SPLIT_RATIO: float = 0.2
DM_ID_UNIQUE_RATIO: float = 0.98
DM_PARSE_SUCCESS_RATIO: float = 0.90
DM_CATEGORICAL_MAX_DISTINCT_FLOOR: int = 20
DM_CATEGORICAL_MAX_DISTINCT_FRACTION: float = 0.05
DM_FREE_TEXT_MIN_MEAN_LENGTH: int = 30
DM_FK_CONTAINMENT_MIN: float = 0.99
DM_RULE_MINING_MIN_SUPPORT: float = 0.99
DM_COPULA_QUANTILE_GRID_SIZE: int = 512
DM_COPULA_EIGEN_EPSILON: float = 1e-6
DM_COPULA_TIME_BOX_HOURS: float = 1.5
DM_MAX_UPLOAD_BYTES: int = 20 * 1024 * 1024
DM_MIN_ROWS_WARN: int = 50
DM_MIN_ROWS_REFUSE: int = 10
DM_ENCODINGS_TO_TRY: tuple = ("utf-8", "utf-8-sig", "latin-1", "cp1252")
DM_DELIMITERS_TO_TRY: tuple = (",", ";", "\t")
DM_CLASSIFICATION_MIN_GROUP_ROWS: int = 30
DM_MAX_CONDITION_BINS: int = 5
```

**`documents.py`**, **`locales.py`**, **`export.py`**, **`api.py`**

```python
DOC_MAX_NARRATIVE_PER_RUN: int = 20
DOC_MAX_INVOICE_PDFS_PER_REQUEST: int = 50
DOC_DEFAULT_INVOICE_PICK_COUNT: int = 10
DOC_INVOICE_NUMBER_PATTERN: str = "INV-{order_id:06d}"
DOC_PDF_FORMAT: str = "A4"
DOC_PDF_TIMEOUT_SECONDS: float = 30.0
DOC_TEMPLATE_INVOICE: str = "invoice.html.j2"
DOC_TEMPLATE_STATEMENT: str = "statement.html.j2"

LOC_DEFAULT_LOCALE: str = "en_PK"
LOC_DEFAULT_CURRENCY: str = "PKR"
LOC_CURRENCY_SYMBOLS: dict = {"PKR": "Rs", "USD": "$"}
LOC_GROUPING_LAKH: str = "lakh"
LOC_GROUPING_WESTERN: str = "western"
LOC_DEFAULT_GROUPING: str = "lakh"                 # ASSUMED
LOC_DOC_DATE_FORMAT: str = "%d/%m/%Y"
LOC_EXPORT_DATE_FORMAT: str = "%Y-%m-%d"
LOC_MOBILE_TEMPLATE: str = "+92 3{operator}{block1} {block2}"   # exact tokens defined in format_utils
LOC_NATIONAL_ID_PATTERN: str = "#####-#######-#"
LOC_NATIONAL_ID_FAKE_MARKER: str = "0"             # first digit; VERIFY real numbers never start with 0
LOC_DEFAULT_TAX_LABEL: str = "Sales Tax (GST)"
LOC_DEFAULT_TAX_RATE: float = 0.18                 # VERIFY

EXP_FORMATS: tuple = ("csv", "json", "sql", "pdf")
EXP_SQL_DIALECT: str = "postgresql"                # ASSUMED
EXP_HASH_ALGORITHM: str = "sha256"
EXP_CSV_LINE_TERMINATOR: str = "\n"
EXP_CSV_ENCODING: str = "utf-8"
EXP_JSON_INDENT: int = 2

API_PREFIX: str = "/api"
API_PREVIEW_ROWS: int = 50
API_STATUS_GENERATED: str = "generated"
API_STATUS_FAILED: str = "failed"
API_SCORE_STATUS_PENDING: str = "pending"
API_SCORE_STATUS_PARTIAL: str = "partial"
API_SCORE_STATUS_DONE: str = "done"
```

**`messages.py`** (all user-visible text, so wording is one edit and tests can assert on it)

```python
MSG_INFEASIBLE_CHILD_TOTAL: str = ("{parent_rows} {parent} x exactly {per_parent} {child} = {needed} {child}, "
                                   "but {requested} were requested. Raise {child} to at least {needed} "
                                   "or lower {child} per {parent} to {max_per_parent}.")
MSG_UNSUPPORTED_RULE: str = "This request asked for something the engine cannot enforce: {detail}"
MSG_UPLOAD_EMPTY: str = "The file is empty."
MSG_UPLOAD_TOO_LARGE: str = "The upload is larger than {limit_mb} MB."
MSG_NO_TRACEBACK: str = "error occurred (no traceback available): {error}"
MSG_ERROR_DETAIL: str = "error occurred in python script [ {file} ], line [ {line} ], message [ {error} ]"
# … one constant per message used in the UI
```

### 5.3 Where the AR's numbers live

Every threshold in the AR maps to one constant above. If a number appears in a component file, that is a bug (section 16).

---

## 6. Entity layer

### 6.1 `config_entity.py` — configuration only (paths and primitives, no logic)

`RunConfig` plays the role of NS `TrainingPipelineConfig`: it creates the timestamp once and every component config takes it, so all stages of one run share one folder.

```python
# hackdata/entity/config_entity.py
import os
from datetime import datetime
from typing import Optional
from hackdata.constants import common, paths, generation, data_mode


class RunConfig:
    """Timestamp and root folder shared by every component of one run.

        RunConfig
           │  run_id = "09_29_2026_18_20_11_123456"
           └─ artifact_dir = Artifacts/temp/<run_id>
    """
    def __init__(self, timestamp: Optional[datetime] = None):
        stamp = (timestamp or datetime.now()).strftime(common.RUN_TIMESTAMP_FORMAT)
        self.pipeline_name: str = common.PIPELINE_NAME
        self.run_id: str = stamp
        self.artifact_root: str = os.path.join(paths.ARTIFACT_DIR, paths.ARTIFACT_TEMP_DIR_NAME)
        self.artifact_dir: str = os.path.join(self.artifact_root, stamp)


class SpecBuilderConfig:
    def __init__(self, run_config: RunConfig):
        self.spec_builder_dir: str = os.path.join(run_config.artifact_dir, paths.SPEC_BUILDER_DIR_NAME)
        self.spec_file_path: str = os.path.join(self.spec_builder_dir, paths.SPEC_FILE_NAME)
        self.pools_file_path: str = os.path.join(self.spec_builder_dir, paths.POOLS_FILE_NAME)
```

One class per component, same pattern: `FeasibilityConfig`, `DataIngestionConfig`, `SchemaInferenceConfig`, `ModelFitterConfig`, `RuleMinerConfig`, `DataGenerationConfig`, `DataValidationConfig`, `EvaluationConfig`, `DocumentConfig`, `ExportConfig`. Each builds its directory and file paths with `os.path.join` from constants and holds any numeric setting it needs (copied from constants, so tests can override one instance).

### 6.2 `artifact_entity.py` — typed outputs, never tuples

```python
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class SpecBuilderArtifact:
    spec_file_path: str
    pools_file_path: str
    spec_source: str                     # "cache" | "llm" | "user_edit" | "offline"
    unsupported: List[str] = field(default_factory=list)

@dataclass
class FeasibilityArtifact:
    ok: bool
    report_file_path: str
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

@dataclass
class DataIngestionArtifact:             # data mode
    train_dir: str
    holdout_dir: str
    table_names: List[str]
    warnings: List[str] = field(default_factory=list)

@dataclass
class SchemaInferenceArtifact:
    schema_file_path: str                # detected types, PKs, FKs, generators, confidence

@dataclass
class ModelFitterArtifact:
    fitted_model_file_path: str
    learned_spec_file_path: str

@dataclass
class RuleMiningArtifact:
    rules_file_path: str
    rules_count: int

@dataclass
class DataGenerationArtifact:
    tables_dir: str
    table_file_paths: Dict[str, str]
    master_seed: int
    row_counts: Dict[str, int]

@dataclass
class DataValidationArtifact:
    status: bool                         # False on any tier 1 failure
    validity_score: float
    report_file_path: str
    coherence_passed: int
    coherence_total: int

@dataclass
class EvaluationArtifact:
    scores_file_path: str
    overall_score: Optional[float]       # None in query mode

@dataclass
class DocumentArtifact:
    documents_dir: str
    html_dir: str
    pdf_file_paths: List[str]
    reconciliation_ok: bool

@dataclass
class ExportArtifact:
    export_dir: str
    file_paths: Dict[str, str]
    checksums_file_path: str
```

### 6.3 `spec_entity.py` — Pydantic spec models

Implements AR 7: `Spec`, `TableSpec`, `ColumnSpec`, `ParentSpec`, `Cardinality`, `Rule`, `EdgeCase`, `DocumentSpec`. Membership of `gen`, `rule` and `dist` values is checked against `constants.spec` tuples in field validators, so the vocabulary is defined once. Also defines the `conditioned_by` block (AR 8.4.1) and the `seasonality` block (AR 8.12). Track A commits these and `data_schema/spec.schema.json` in the first 45 minutes.

### 6.4 `request_entity.py`

`GenerationRequest` (module, mode, query, template, n_rows, seed, locale, currency, privacy, null and outlier rates, doc type and count, optional `spec` override) and `UploadRequest`. The API converts its Pydantic models into these dataclasses so components never import from `api/`.

---

## 7. Components

Every component is a class taking its config (and the previous artifact when it has one) and exposing **`initiate_<stage>()`** that returns a typed artifact, exactly like NS `initiate_data_ingestion()`. Each public method logs at start and end and wraps its body in `try/except` raising `HackDataException(e, sys)`.

| Component | Config | Input | Output artifact | Key methods | AR ref |
|---|---|---|---|---|---|
| **SpecBuilder** | `SpecBuilderConfig` | `GenerationRequest` | `SpecBuilderArtifact` | `load_template()`, `ask_llm_for_spec()`, `validate_spec()`, `fetch_pools()`, `initiate_spec_builder()` | 7, 11 |
| **FeasibilityChecker** | `FeasibilityConfig` | spec, overrides | `FeasibilityArtifact` | `check_child_totals()`, `check_unique_capacity()`, `check_date_windows()`, `check_caps()`, `initiate_feasibility_check()` | 7.8 |
| **DataIngestion** | `DataIngestionConfig` | `UploadRequest` | `DataIngestionArtifact` | `read_csv_safely()`, `enforce_caps()`, `split_train_holdout()`, `initiate_data_ingestion()` | 10.3, 10.11 |
| **SchemaInference** | `SchemaInferenceConfig` | `DataIngestionArtifact` | `SchemaInferenceArtifact` | `detect_column_types()`, `classify_with_llm()`, `verify_classification()`, `detect_primary_keys()`, `detect_foreign_keys()`, `initiate_schema_inference()` | 10.2 |
| **ModelFitter** | `ModelFitterConfig` | schema artifact | `ModelFitterArtifact` | `fit_table()` (via `Fitter`), `learn_cardinality()`, `group_condition()` (P1), `initiate_model_fitter()` | 10.4–10.6 |
| **RuleMiner** (P1) | `RuleMinerConfig` | ingestion and schema artifacts | `RuleMiningArtifact` | `mine_date_order()`, `mine_sum_of()`, `mine_category_range()`, `initiate_rule_mining()` | 10.6 |
| **DataGenerator** | `DataGenerationConfig` | spec (query or learned), seed | `DataGenerationArtifact` | `build_dependency_order()`, `generate_table()`, `assign_foreign_keys()`, `compute_aggregates()`, `inject_edge_cases()`, `apply_privacy()`, `initiate_data_generation()` | 8, 9 |
| **DataValidator** | `DataValidationConfig` | generation artifact, spec | `DataValidationArtifact` | `run_structural_checks()`, `run_rule_checks()`, `apply_targeted_fixes()`, `run_coherence_checks()`, `initiate_data_validation()` | 9.4 |
| **Evaluator** | `EvaluationConfig` | generation artifact, holdout (data mode) | `EvaluationArtifact` | `score_validity()`, `score_fidelity()`, `score_utility()`, `score_privacy()`, `score_baseline()` (P1), `aggregate()`, `initiate_evaluation()` | 14 |
| **DocumentRenderer** | `DocumentConfig` | tables or fact sheets | `DocumentArtifact` | `build_invoice_data()`, `build_statement_data()`, `render_html()`, `render_pdf()`, `check_reconciliation()`, `initiate_document_rendering()` | 12 |
| **Exporter** | `ExportConfig` | generation and document artifacts | `ExportArtifact` | `write_csv()`, `write_json()`, `write_sql()`, `zip_pdfs()`, `write_checksums()`, `initiate_export()` | 15 |
| **DatasetCorruptor** | (none) | tables, defect kind | corrupted copy plus touched IDs | `corrupt(tables, kind, n, seed)` | 9.6 |

**Rules for components:**

- One class per file. A component never calls another component directly; the **pipeline** passes artifacts (NS rule: the next component always receives the previous artifact).
- A component never contains a literal path, threshold or message; it reads its config or `constants`.
- Shared logic goes to `utils/`, not copied between components.
- `DataGenerator` delegates to `components/generators/*`. Those are plain functions and small classes with no I/O and no logging beyond debug, so they are unit-testable.

### 7.1 The three modules (`modules/`)

`tabular.py`, `relational.py`, `documents.py` are thin adapters. Each converts a `GenerationRequest` into the right spec and pipeline: tabular is a spec with one table, relational a spec with parents and rules, documents a document spec. No module contains generation logic.

---

## 8. Pipelines

### 8.1 `GenerationPipeline` (query mode)

```
GenerationRequest
   │
   ▼  SpecBuilder ───────────────▶ SpecBuilderArtifact
   ▼  FeasibilityChecker ────────▶ FeasibilityArtifact       (stop with 422 if not ok)
   ▼  DataGenerator ─────────────▶ DataGenerationArtifact
   ▼  DataValidator ─────────────▶ DataValidationArtifact     (stop if tier 1 fails)
   ▼  Evaluator (background) ────▶ EvaluationArtifact
   ▼  Exporter (on demand) ──────▶ ExportArtifact
```

### 8.2 `DataModePipeline` (upload mode)

```
UploadRequest
   ▼ DataIngestion ─▶ SchemaInference ─▶ (RuleMiner, P1) ─▶ ModelFitter
   ▼ produces a learned spec + fitted models
   ▼ hands off to GenerationPipeline steps:  DataGenerator ─▶ DataValidator ─▶ Evaluator (real hold-out) ─▶ Exporter
```

Data mode changes only where the spec comes from (AR 6.2); the same generation, validation, scoring and export components run.

### 8.3 `DocumentPipeline`

`DocumentRenderer` on structured fact data (invoice, statement) or on an existing relational run (invoices from orders, cap 50 PDFs, AR 12.7), then `Exporter`. Narrative documents (P2) add a fact-sheet builder, an LLM body call and a fact check.

### 8.4 Run lifecycle and the Artifacts tree

`run_manager.py` owns: create `RunConfig`, run a pipeline, keep the last **`GEN_MAX_RUNS_KEPT_TEMP`** runs in `Artifacts/temp/`, **Save** (move to `Artifacts/saved/`), list history, delete.

```
Artifacts/
├── temp/                                  ← last 10 unsaved runs, oldest evicted
└── saved/
    └── 09_29_2026_18_20_11_123456/        ← run_id
        ├── meta.json                      ← module, mode, timestamps, row counts, seed
        ├── spec_builder/        spec.json  pools.json
        ├── feasibility/         feasibility_report.json
        ├── data_ingestion/      train/  holdout/            (data mode)
        ├── schema_inference/    schema.yaml                 (data mode)
        ├── model_fitter/        fitted_model.pkl  learned_spec.json
        ├── rule_miner/          mined_rules.yaml            (P1)
        ├── data_generation/     tables/<name>.csv
        ├── data_validation/     validation_report.json
        ├── evaluation/          scores.json
        ├── documents/           html/  pdf/
        └── export/              <files>  checksums.json
```

**Exact reproduction recipe** stays `spec.json` + `pools.json` + seed (AR 15.2). `Artifacts/`, `cache/`, `logs/`, `*.pkl` and `.env` are gitignored.

---

## 9. Utils (common functionality)

Anything used by more than one component belongs here. All functions have type hints, a docstring, logging and the standard exception wrapper.

### 9.1 `utils/main_utils/utils.py` (NS parity)

```python
def save_object(file_path: str, obj: object) -> None          # os.makedirs + dill.dump(obj, file_obj)
def load_object(file_path: str) -> object                       # dill.load(file_obj)
def save_numpy_array_data(file_path: str, array) -> None
def load_numpy_array(file_path: str)
def read_yaml_file(file_path: str) -> dict                      # yaml.safe_load
def write_yaml_file(file_path: str, content: object, replace: bool = False) -> None
def read_json_file(file_path: str) -> dict
def write_json_file(file_path: str, content: object) -> None
def ensure_dir(path: str) -> str                                # os.makedirs(path, exist_ok=True)
```

### 9.2 Other `main_utils`

| File | Functions |
|---|---|
| `seed_utils.py` | `derive_seed(master, *keys) -> int` (blake2b), `make_rng(master, *keys) -> np.random.Generator`, `new_master_seed() -> int` |
| `hash_utils.py` | `sha256_file(path)`, `sha256_text(text)`, `query_cache_key(query, module, template, locale)` |
| `money_utils.py` | `to_minor_units`, `from_minor_units`, `round_half_up`, `apply_rate(amount_minor, rate)` |
| `format_utils.py` | `format_money(minor, currency, grouping)`, `group_lakh(int)`, `format_date(d, locale, context)`, `format_phone(locale, parts)` |
| `canonical_io.py` | `write_csv_canonical(df, path)`, `write_json_canonical(obj, path)`, `write_sql_dump(tables, spec, path)` — fixed column order, sorted by PK, no timestamps (needed for checksums) |
| `dataframe_utils.py` | `read_csv_safely(path)` (encoding and delimiter sniffing), `sample_rows(df, n, rng)`, `is_numeric_like(series)` |
| `env_utils.py` | `get_env(name, default=None)`, `get_groq_keys() -> list[str]` |

### 9.3 `ml_utils/metric/` (NS `classification_metric.py` counterpart)

| File | Functions | Returns |
|---|---|---|
| `fidelity_metric.py` | `column_shape_scores(real, synth)`, `correlation_score(real, synth)` | Typed metric objects (small dataclasses defined in the same file, like NS `ClassificationMetricArtifact`) |
| `utility_metric.py` | `tstr_trts(real_train, real_holdout, synth, target)` | TRTR, TSTR, TRTS and ratios |
| `privacy_metric.py` | `exact_match_rate(...)`, `nn_distance_ratio(...)` | ratio, flag |
| `coherence_metric.py` | `check_group_order(...)`, `check_bound_by_group(...)`, `check_share_within(...)` | pass/fail plus detail |
| `overall_score.py` | `aggregate(pillars, weights)` | overall, with weights echoed |

### 9.4 `ml_utils/model/` (NS `estimator.py` counterpart)

`fitter_interface.py` defines the `Fitter` and `FittedModel` protocols (AR 10.4), the slot where an SDV adapter goes later. `copula_model.py` implements `FittedTableModel` (`fit`, `sample(n, seed)`), bundling marginals, correlation and null rates into **one saved object**, the same idea as the NS `ModelWrapper` that bundles preprocessor and model.

---

## 10. Exception and logging (one each, used everywhere)

### 10.1 `hackdata/exception/exception.py`

```python
# ═══════════════════════════════════════════════════════════════════
# exception.py — one custom exception for the whole project
# ═══════════════════════════════════════════════════════════════════
# Adds FILE NAME + LINE NUMBER to any error. Raise it everywhere instead of plain Exception.
###==============================================================
import sys
from hackdata.constants import messages


def error_message_detail(error: Exception, error_detail: sys) -> str:
    _, _, exc_tb = error_detail.exc_info()
    if exc_tb is None:                                   # IMP: raised outside an except block
        return messages.MSG_NO_TRACEBACK.format(error=error)
    return messages.MSG_ERROR_DETAIL.format(
        file=exc_tb.tb_frame.f_code.co_filename,
        line=exc_tb.tb_lineno,
        error=str(error),
    )


class HackDataException(Exception):
    def __init__(self, error_message: Exception, error_detail: sys):
        super().__init__(error_message)
        self.error_message: str = error_message_detail(error_message, error_detail)

    def __str__(self) -> str:
        return self.error_message
```

Improvements over the NS version: it handles `exc_tb is None`, and its text comes from `messages.py`. **`__main__` blocks must `raise HackDataException(e, sys)`**, not just construct it (NS bug you hit).

### 10.2 `hackdata/logging/logger.py`

```python
import logging
import os
from datetime import datetime
from hackdata.constants import common, paths

LOG_FILE = f"{datetime.now().strftime(common.LOG_TIMESTAMP_FORMAT)}.log"
LOGS_PATH = os.path.join(os.getcwd(), paths.LOGS_DIR)
os.makedirs(LOGS_PATH, exist_ok=True)

logging.basicConfig(
    format=common.LOG_FORMAT,
    level=logging.INFO,
    handlers=[logging.FileHandler(os.path.join(LOGS_PATH, LOG_FILE)), logging.StreamHandler()],
)
```

Usage everywhere: `from hackdata.logging.logger import logging` then `logging.info("…")`. This matches the Movie Sentiment pattern (the object is named `logging`, not `logger`). Log at the start and end of every component method and at every pipeline step.

### 10.3 API error mapping

`api/error_handlers.py` converts `HackDataException` and `RequestValidationError` into `{code, message, hint}` JSON with the status codes in AR 16.5. Users never see tracebacks; the full text goes to the log.

---

## 11. LLM layer (`cloud/`)

`llm_client.py` exposes one function set (`ask_json(prompt_name, variables, schema)`, `ask_text(...)`) and hides everything else:

1. cache lookup (`llm_cache.py`, key from `hash_utils.query_cache_key`) → return on hit;
2. next free key from `key_pool.py`; on 429 or timeout the key gets `LLM_KEY_COOLDOWN_SECONDS` and the next key is tried;
3. on exhausted keys, next model in `LLM_MODEL_FALLBACK_CHAIN`, then OpenRouter, then `offline_fallback.py`;
4. JSON validated with Pydantic; on failure one repair call (`LLM_MAX_REPAIR_RETRIES`) with the error text;
5. result cached and returned.

Prompts are files in `data_assets/prompts/` loaded by `prompt_loader.py`, never inline strings. Keys come only from `env_utils.get_groq_keys()`. Rotation is a backup: rate limits are reported as per organisation (**VERIFY**), the cache is the first defence (AR 11.4). Nothing outside `cloud/` imports `httpx` or knows a provider URL.

---

## 12. API layer

- **`app.py`** builds the FastAPI app, registers a **lifespan** handler (create folders, warm the prompt and template caches, start the Playwright browser lazily), includes the routers, adds `CORSMiddleware`, and mounts the built frontend as static files. No route logic.
- **`api/routes/`** one router per concern: `generate`, `upload`, `spec`, `runs`, `documents`, `export`, `demo` (corrupt, sample data), `health`. Each route validates input with `api/schemas.py`, builds a `GenerationRequest`, calls one function in `pipeline/`, and returns the result.
- The endpoint list and payloads are in AR 16 (with v2 additions). Prefix `API_PREFIX`.
- **Scores are asynchronous:** `POST /generate` returns after generation and tier 1 to 3 validation; `Evaluator` runs in a background thread and `GET /runs/{id}/scores` is polled (AR 6.3).
- Starlette's `TemplateResponse` needs `request=request, name=...` keyword form (a bug you hit in Movie Sentiment) if any Jinja page is served.

---

## 13. Frontend

Section 2.3 decides the stack. Either way the frontend contains no business logic and no hard-coded numbers that mirror backend constants: caps, weights and messages arrive from `GET /api/config` (returns the public subset of constants), so the UI can never disagree with the engine.

Panels: module sidebar, query/upload toggle, configuration, preview (table, FK diagram, document), scorecard with reference badges, run history, spec editor, feasibility box, corrupt button, checksum line with replay, coherence panel, baseline table, schema view, invoices button, sample-data button (AR 17).

---

## 14. Data assets (content, not constants)

| Path | Contents | Referenced by |
|---|---|---|
| `data_assets/templates/*.yaml` | Hand-verified specs: e-commerce (with segments and tax fields), banking, invoicing | `SpecBuilder.load_template()` via `paths` constants |
| `data_assets/locales/pk/*.json` | Names (first by gender, surnames), cities with weights, areas, mobile prefixes, landline codes | `format_utils`, `column_generators` |
| `data_assets/calendars/pk.json` | Fixed sale dates, Eid and Ramadan dates 2023 to 2027 (**VERIFY**) | `seasonality.py` |
| `data_assets/prompts/*.txt` | Spec, pool, narrative and repair prompts | `prompt_loader.py` |
| `data_assets/document_templates/*.j2` | Invoice and statement HTML (same file drives preview and PDF) | `DocumentRenderer` |
| `data_assets/sample/*.csv` | Team-generated demo data, labelled as such | `demo` route, tests |
| `data_schema/*.json` | JSON Schemas for spec and scores | tests, mock API |

**Test for the line between constants and content:** if changing it changes *behaviour of the engine* (a threshold, a cap, a path), it is a constant; if it changes *what is generated or shown* (a name list, a prompt, a layout), it is an asset.

---

## 15. Coding standards

These reproduce your NS conventions with two team-driven adjustments (section 21).

### 15.1 Absolute rules (NS list, adapted)

```
 1. NO hard-coded values in components or utils; everything comes from constants/ or data_assets/
 2. NO np.random.* global calls; every random draw uses make_rng(master, table, column)
 3. NO fit_transform on hold-out data; fit on train only (data mode)
 4. NO mutating input DataFrames; always df.copy()
 5. ALWAYS dill for saving fitted objects, dill.dump(obj, file_obj)
 6. ALWAYS typed artifact dataclasses; never return plain tuples between components
 7. ALWAYS timestamped run folders: Artifacts/temp/<run_id>/
 8. ALWAYS logging.info() at the start and end of every component method
 9. ALWAYS raise HackDataException(e, sys) inside except blocks
10. ALWAYS separate config from logic: config_entity holds paths and values only
11. ALWAYS os.path.join(); never hand-write slashes
12. ALWAYS integer minor units for money; convert only at export and render
13. NEVER let the LLM produce rows, keys, totals, dates that must order, or seeds
14. NEVER call an external service outside cloud/
15. NEVER use eval; expressions go through simpleeval with the whitelist
```

### 15.2 Comment and docstring style (NS)

```python
# ═══════════════════════════════════════════════════════════════════
# filename.py
# ═══════════════════════════════════════════════════════════════════
# One line: what this file does and where it sits in the pipeline
###==============================================================
"""
ClassName / function_name

input  → process → output

    upstream artifact ──▶ [this component] ──▶ downstream artifact
"""

# ---------------- SECTION NAME ----------------
# IMP: critical decision and why
# BUG FIXED: what was wrong → what is correct
# DRY RUN: input → step 1 → step 2 → output, with actual values
```

- Section dividers, `# IMP:`, `# BUG FIXED:` and ASCII flow docstrings are **required**.
- **Dry-run comments are required for the core algorithms** (seed derivation, cardinality and FK assignment, aggregates, conditional sampling, feasibility, validator tiers, copula fit and sample, checksums) and optional elsewhere. Reason: the standard is right for learning and for judges reading the code, but blanket dry runs on every function would cost hours we do not have.
- **Comment language: English** (ASSUMED) because three people and judges read this repo; Hinglish stays in your personal notes. Tell me if you want Hinglish in your files.
- Every function: type hints, docstring with Parameters and Returns, logging, try/except.
- Naming: constants `ALL_CAPS`, classes `PascalCase`, functions and variables `snake_case`.

### 15.3 Component template

```python
class FeasibilityChecker:
    def __init__(self, config: FeasibilityConfig, spec_artifact: SpecBuilderArtifact):
        try:
            self.config = config                     # BUG FIXED: assign the parameter, not self.config = self.config
            self.spec_artifact = spec_artifact
        except Exception as e:
            raise HackDataException(e, sys)

    def initiate_feasibility_check(self) -> FeasibilityArtifact:
        try:
            logging.info("Feasibility check started")
            spec = read_json_file(self.spec_artifact.spec_file_path)
            errors, warnings = [], []
            errors += self.check_child_totals(spec)
            errors += self.check_unique_capacity(spec)
            warnings += self.check_caps(spec)
            write_json_file(self.config.report_file_path, {"errors": errors, "warnings": warnings})
            logging.info(f"Feasibility check finished: ok={not errors}")
            return FeasibilityArtifact(ok=not errors, report_file_path=self.config.report_file_path,
                                       errors=errors, warnings=warnings)
        except Exception as e:
            raise HackDataException(e, sys)
```

### 15.4 Pipeline template

```python
class GenerationPipeline:
    def __init__(self):
        self.run_config = RunConfig()

    def run(self, request: GenerationRequest) -> DataValidationArtifact:
        try:
            spec_art = SpecBuilder(SpecBuilderConfig(self.run_config), request).initiate_spec_builder()
            feas_art = FeasibilityChecker(FeasibilityConfig(self.run_config), spec_art).initiate_feasibility_check()
            if not feas_art.ok:
                raise InfeasibleRequest(feas_art.errors)          # mapped to 422 by the API layer
            gen_art = DataGenerator(DataGenerationConfig(self.run_config), spec_art, request.seed).initiate_data_generation()
            return DataValidator(DataValidationConfig(self.run_config), gen_art, spec_art).initiate_data_validation()
        except InfeasibleRequest:
            raise
        except Exception as e:
            raise HackDataException(e, sys)
```

### 15.5 Bugs to avoid (NS list plus ours)

```python
dill.dump(obj, file_obj)                       # ✅   dill.dump(file_obj, obj) ❌
X_hold = model.transform(X_hold)               # ✅   fit_transform on hold-out ❌ (leakage)
dagshub.init() inside track_mlflow()           # ✅ (if MLflow is added), never at module level
os.makedirs(path, exist_ok=True)               # ✅   os.makedirs(path) ❌
if __name__ == "__main__":                     # ✅   "__name__" ❌
def __init__(self):                            # ✅   __int__ ❌
self.config = config                           # ✅   self.config = self.config ❌
np.random.default_rng(derive_seed(...))        # ✅   np.random.seed(...) or global draws ❌
df = df.copy()                                 # ✅   mutate the caller's DataFrame ❌
dill.dump / load with same sklearn+numpy versions   # pin versions; unpickling across versions breaks
```

---

## 16. Enforcing "no hard-coded values"

A rule nobody checks decays within hours in a three-person team. `scripts/check_no_hardcoding.py` (about 30–45 minutes, P1, PROPOSED) parses `hackdata/components/`, `hackdata/utils/`, `hackdata/pipeline/`, `hackdata/cloud/` and `api/` with `ast` and fails on:

| Pattern | Why |
|---|---|
| A string literal containing `/`, `\`, `.csv`, `.json`, `.pkl`, `.yaml`, `.log` used in `open`, `os.path.join`, `pd.read_*`, `to_*` | Literal path or file name |
| A numeric literal other than `0`, `1`, `-1`, `2` outside `constants/` in a comparison, slice, function default or keyword argument | Hidden threshold |
| A string literal longer than 40 characters passed to `raise`, `logging`, or returned to the API | User-facing text belongs in `messages.py` |
| An import from a layer to the right of the module in the import-direction chain (section 3) | Layer violation |
| `httpx`, `requests` or provider URLs outside `cloud/` | External calls |

Allowlist by trailing `# noqa: hardcode` with a reason. It runs in `pytest` (one test) and in the smoke script. `flake8` or `ruff` covers the rest.

---

## 17. Testing

| Suite | Contents | Owner |
|---|---|---|
| **Unit** | `derive_seed` stability, money rounding, lakh grouping, feasibility cases, conditional sampling, aggregates, canonical writers | A, B |
| **Negative** | `test_validator_negative.py`: for each defect in `VAL_DEFECT_KINDS`, `DatasetCorruptor` breaks a clean dataset and the right check fires with the right count; a clean dataset passes all (AR 9.6) | A |
| **Reproducibility** | `test_repro_hash.py`: each demo query twice with one seed gives identical checksums; adding a column leaves other columns unchanged | A |
| **Integration** | Generation pipeline end to end on the three templates with the LLM stubbed; data-mode pipeline on `data_assets/sample`; API tests with `TestClient` | A, B, C |
| **Smoke** | `scripts/smoke_demo.py` runs the full demo path including export and SQL load; **run before every push** | all |
| **Hardcode check** | Section 16 | A |

CI (P2): GitHub Actions running lint, `check_no_hardcoding.py` and the fast tests (as in NS, on push and pull request to `main`).

---

## 18. Configuration, environment and packaging

`.env.example` (names only):

```
GROQ_API_KEYS=key1,key2
OPENROUTER_API_KEY=
JEV_API_KEY=
```

`.gitignore` (NS list adapted): `Artifacts/`, `cache/`, `logs/`, `*.pkl`, `*.npy`, `.env`, `__pycache__/`, `*.egg-info/`, `mlruns/`, `node_modules/`, `frontend/dist/`.

`setup.py` follows NS: `find_packages()`, `install_requires` read from `requirements.txt`, skipping `-e .`. Install once with `pip install -e .`, then `playwright install chromium` (about 300 MB; do this in hour zero on every machine).

---

## 19. Running it

| Task | Command |
|---|---|
| Install | `pip install -e .` then `playwright install chromium` |
| Run API and UI | `python app.py` (uvicorn started from `app.py`, one port serves API and frontend) |
| Run without the API | `python main.py --mode query --module relational --query "…" --seed 123` |
| Smoke test | `python scripts/smoke_demo.py` |
| Pre-cache demo | `python scripts/precache_demo.py` |
| Build sample data | `python scripts/make_sample_data.py` |
| Tests | `pytest` |
| Hardcode check | `python scripts/check_no_hardcoding.py` |

Docker (P2): a slim Python base image, `requirements.txt`, `playwright install --with-deps chromium`, `EXPOSE 8000`, `CMD ["python", "app.py"]`, following the NS Dockerfile. It is heavier than NS because of Chromium, so it is last on the list.

---

## 20. Team ownership and build order

### 20.1 File creation order (NS order, adapted) and who does it

| Step | Files | Owner | When |
|---|---|---|---|
| 1 | `scripts/scaffold.sh`: whole package tree and empty `__init__.py` files (Claude Code generates it) | A | hour 0 |
| 2 | `constants/*` (all modules with the values in section 5) | A drafts, B and C append their own prefixes | first 45 min |
| 3 | `exception/exception.py`, `logging/logger.py` | A | first 45 min |
| 4 | `entity/config_entity.py`, `artifact_entity.py`, `spec_entity.py`, `request_entity.py`, `data_schema/*.json` | A | first 45 min (**the contract**) |
| 5 | `utils/main_utils/*` | A (seed, money, hash), B (dataframe, canonical), C (format) | hour 0.75 to 2 |
| 6 | `cloud/*`, `data_assets/prompts` | A | hour 1 to 3, bake-off at 0.75 |
| 7 | `components/generators/*`, `components/data_generator.py`, `spec_builder.py` | A | hour 1 to 3 |
| 8 | `components/feasibility_checker.py`, `data_ingestion.py`, `schema_inference.py`, `model_fitter.py` | B | hour 1 to 3 |
| 9 | `pipeline/generation_pipeline.py`, first API routes, UI shell | A, C | by checkpoint 1 (hour 3) |
| 10 | `data_validator.py`, `evaluator.py` and `ml_utils/*` | A, B | hour 3 to 5 |
| 11 | `document_renderer.py`, `exporter.py`, `run_manager.py`, spec panel, scorecard UI | C | hour 3 to 6 |
| 12 | `rule_miner.py`, `datamode_pipeline.py`, corruptor and negative tests | B, A | hour 5 to 6 |
| 13 | P1 items in the ranked order of PRD section 13 | as free | hour 6 to 8 (only if the hour-3 gate passed) |
| 14 | `precache_demo.py`, smoke script, rehearsal, buffer | all | hour 8 to 10 |

### 20.2 Contract freeze

After step 4 nobody changes `constants` names, entity fields or spec models without telling the other two. Adding new constants is free; renaming or removing one is a team decision. This is the single most important integration rule.

---

## 21. Deviations from the Network Security standard, risks and open items

### 21.1 Deviations (all deliberate)

| Deviation | Why |
|---|---|
| Constants split into modules | Three-person merge conflicts (section 1) |
| Microseconds in the run timestamp | Two Enters in one second must not collide |
| Temp and saved artifact folders | "Temporary until Save" behaviour |
| Thin `app.py` plus routers | About 20 endpoints |
| `cloud/` holds LLM code instead of HuggingFace sync | Different external service; same isolation idea |
| No MLflow, DagsHub, HuggingFace in MVP | Nothing to train or register; hook available as P2 |
| English comments, dry runs only for core algorithms | Team readability and hackathon time |
| `HackDataException` handles `exc_tb is None` and takes text from `messages.py` | Fixes an NS weak spot |
| Messages as constants | Extends "no hard-coded values" to user-visible text |

### 21.2 Risks specific to this structure

| Risk | Mitigation |
|---|---|
| Boilerplate slows the first hours | Claude Code generates the skeleton; contract freeze at 45 minutes |
| Constants drift between teammates | Prefix ownership per module and the enforcement script |
| Over-engineering for a 10-hour build | If the hour-3 checkpoint fails, drop P1 items, not the structure; the structure is what makes P0 integrable |
| Artifacts writing slows the interactive loop | Tables are CSV at most 100k rows; measure at checkpoint 1; if slow, keep frames in memory and write on demand behind one `run_manager` flag |
| Logging package name shadows stdlib when run from inside its folder | Always run from repo root or with `python -m` |

### 21.3 Open items (also in AR 24.2 and PRD section 14)

1. Track owners (A, B, C).
2. Frontend option A or B by hour 3.
3. Groq bake-off results and final model IDs (update `constants/llm.py`).
4. Comment language: English (assumed) or Hinglish.
5. Whether to include the enforcement script and CI in P0 or leave them P1/P2 (my recommendation: script P1, CI P2).
6. Values marked VERIFY: Groq limits and model IDs, Eid dates, GST rate, mobile prefixes, the ID marker digit.
