# HackDataV2 Synthetic Data Platform — Architecture and Decision Record

Version 2 · updated 2026-09-29 (v1 plus the review additions listed in section 0.4) · for the three-person hackathon team building with Claude Code

This is the single reference for what we are building, why, and exactly how. It records every decision made in the design discussion, every assumption I made on your behalf, and every open item. Read section 0 first.

---

## 0. How to read this document

### 0.1 Status labels

Every non-obvious statement carries one of these labels:

| Label | Meaning |
|---|---|
| **DECIDED** | You confirmed it in the discussion. Change it only by team agreement. |
| **ASSUMED** | I chose it because you never answered, or told me to decide. Veto freely. |
| **PROPOSED** | A concrete default I am suggesting for a detail you have not discussed (thresholds, weights, file names). Adjust during the build. |
| **OPEN** | Not decided. Section 24 lists all of them. |
| **VERIFY** | A fact about an outside product or limit that came from third-party web sources. Check it yourself before relying on it. |

### 0.2 Three levels of "what is possible"

You asked me to always separate these:

1. **Existing capability:** what libraries and platforms already do (SDV, Faker, SDMetrics, Groq, and so on).
2. **What we build in 10 hours:** the hackathon MVP, which is what this document specifies.
3. **Production-grade:** what we would build later with time and money. Each section ends with a short "later" note where it matters.

### 0.3 The optimisation target

**DECIDED:** a working, convincing, technically defensible hackathon prototype. Not an enterprise platform. Every choice below trades polish for reliability of the demo.

### 0.4 What changed in version 2

After v1, two outside reviews of the design were analysed and you asked for the accepted suggestions to be added. **Adopting them is DECIDED; their tiers, time estimates and track assignments are PROPOSED.** Estimates are best case: multiply by about 1.5 for integration and debugging.

| # | Addition | Where | Tier | Est. |
|---|---|---|---|---|
| 1 | **Feasibility check** before generation (impossible requests rejected with a plain explanation) | 7.8 | P0 | 30–45 min |
| 2 | **Negative validator tests** plus a "Corrupt this dataset" demo button | 9.6 | P0 | 45 min |
| 3 | **Conditional relationships** across tables (segment drives order behaviour), query mode | 8.4.1 | P0 | 1.5 h |
| 4 | **Three-tier validation layer** (structural, business rules, behavioural coherence) | 9.4 | P0 | with 1–3 |
| 5 | **Reproducibility proof** (SHA-256 checksums beside the seed) | 15.5 | P0 | 20 min |
| 6 | **Editable spec panel** (edit the spec, run with no LLM call) | 7.9 | P0 | 45–60 min |
| 7 | **Bundled sample dataset** and readable upload errors | 10.11 | P0 | 30–45 min |
| 8 | **Pakistan locale profile** (phones, cities, PKR formatting, names, synthetic ID pattern) | 8.13 | P0 basics, rest P1 | 45–60 min |
| 9 | **Naive-baseline comparison** (does our scorecard beat independent-column data?) | 14.10 | P1 | 45 min |
| 10 | **Detected-schema view** with corrections in data mode | 10.2.1 | P1 | 45–60 min |
| 11 | **Seasonality** in dates (weekday, month-end, sale and Eid periods) | 8.12 | P1 | 30–45 min |
| 12 | **Invoices generated from the relational output** | 12.7 | P1 | 45–60 min |
| 13 | **Data-mode conditioning** (group-wise child fitting) | 10.6 | P1 | 1 h |
| 14 | Extra metrics in a details drawer (Wasserstein, Jensen-Shannon, variance) | 14.8 | P2 | 20 min |

**One demotion (ASSUMED, veto freely):** narrative documents move from P1 to P2 to pay for the above. Structured documents (invoice, statement) stay P0.

**Reviewer items we did not adopt, and why:** chunked CSV reading (uploads are capped, so plain pandas is fine); a general constraint-solver or repair loop (we build data correct by construction and apply targeted fixes only, see 9.4); English-sentence business rules in the plan (the engine can only enforce rules from a fixed vocabulary; anything else is listed as `unsupported`); renaming our repo layout to theirs (cosmetic).

**Diagrams:** `architecture.html` still shows v1. The v2 additions (feasibility gate, behavioural tier, corrupt button, baseline, spec panel) are not drawn yet.

---

## 1. What we are building

### 1.1 One-sentence definition

A single-page web workspace that generates realistic, privacy-safe **tabular, relational and document** data on demand, from either a **natural-language query** or an **uploaded CSV**, with strict relational consistency, a fresh valid dataset on every run, and a **scorecard** (validity, fidelity, utility, privacy) attached to every run.

### 1.2 The three modules and two modes (DECIDED)

| Module | Query mode (no real data) | Data mode (upload CSV) |
|---|---|---|
| **Tabular** | Spec describing one table; generators and derived columns produce rows. | One CSV: infer types, fit marginals plus a Gaussian copula, sample new rows. |
| **Relational** | Spec describing several tables with FKs, cardinalities and rules; generated parents first. | Several CSVs: detect PKs and FKs, fit each table, learn children-per-parent counts, mine rules, then same generation order. |
| **Documents** | Query becomes a document spec; structured documents come from the relational core, narrative ones from fact sheets plus LLM text. | Upload a line-items or transactions CSV; learn merchant, amount and credit/debit patterns; same renderer. |

**Why one engine and not three (DECIDED):** tabular is relational with one table. Documents are relational output rendered through a template. Three engines would mean writing seeding, spec validation, LLM calls, privacy controls, edge cases, scoring and export three times. The HackDataV2 deck itself says the three generators "share one schema-aware pipeline". So there is one shared core and three thin module packages on top of it.

### 1.3 What the HackDataV2 PDF actually is

The PDF is a **pitch deck, not a specification**. It states what the team claims to deliver and says little about how. The explicit requirements extracted from it are traced in section 2.

### 1.4 One contradiction in the deck, and how we word around it

The deck says the platform works "without ever touching real records", but also lists a **sample dataset** as an input and a "learn distributions" step. If a user uploads real data and we fit a model to it, we do touch real records.

**Our wording (PROPOSED):** "Query mode never touches real data. Data mode reads your file only to fit and to score. It never copies a real row into the output, and IDs, names, emails and other identifying columns are regenerated." Do not claim "never touches real records" for data mode.

---

## 2. Traceability: every PDF claim and how we meet it

| PDF claim | How we deliver | Status |
|---|---|---|
| Ingest schema: infer tables, columns, types and keys from a sample or a schema file | Data-mode type, PK and FK inference (section 10). A schema-file upload is not built. | Sample: DECIDED. Schema file: not in MVP. |
| Model relationships: learn distributions, correlations, FK cardinalities | Marginals plus Gaussian copula per table, FK children-per-parent histogram (section 10) | DECIDED |
| Generate with AI: realistic names, text, edge cases | Groq value pools, narrative text, edge-case pattern suggestions (section 11) | DECIDED |
| Validate and export: referential integrity, statistical fidelity, export to a format of choice | Validator plus scorecard (sections 9, 14), CSV, JSON, PostgreSQL SQL dump, PDF zip (section 15) | DECIDED |
| Tabular: statistically faithful numeric and categorical distributions | Copula (data mode), spec distributions (query mode) | DECIDED |
| Tabular: configurable row count, random seed, null and outlier rates | Config panel fields, seeded generation, edge-case injection (section 8.10) | DECIDED |
| Tabular: column-level privacy controls (masking, hashing, differential noise) | Masking, salted hashing, Laplace noise (section 8.11). **No formal differential-privacy guarantee is claimed.** | DECIDED, wording PROPOSED |
| Relational: referential integrity automatic across every table | Generation-order construction (section 9) | DECIDED |
| Relational: configurable 1:1, 1:N and N:N cardinalities | Cardinality spec incl. junction tables (section 8.6) | DECIDED |
| Relational: order totals reconcile with line items | Computed aggregate, not sampled (section 8.7) | DECIDED |
| Invoices: line items, tax rules, totals reconcile | Structured document pipeline (section 12.1) | DECIDED |
| Invoices: templated layouts per region (date format, currency, tax labels) | Region profiles (section 12.1.3) | DECIDED |
| Invoices: bulk generation | Zip of PDFs, capped (section 12.5) | DECIDED |
| Bank statements: merchants, amounts, running balances | Statement generator (section 12.2) | DECIDED |
| Bank statements: JSON/CSV or formatted documents | Export formats (section 15) | DECIDED |
| Bank statements: query-style generation, e.g. "last 90 days, balance over $500" | Query parsed into constraints in the spec (section 12.2.3) | DECIDED |
| AI layer: schema understanding from a small sample | Code heuristics plus LLM/Jev classification against a closed vocabulary (section 10.2) | DECIDED |
| AI layer: edge-case injection | LLM proposes patterns, code applies them (section 8.10) | DECIDED |
| UI: one workspace to configure, preview, export, no code | Single-page React workspace (section 17) | UI stack ASSUMED |
| Config: row count, random seed, locale and currency, privacy rules | Config panel (section 17) | DECIDED |

**Additions beyond the deck (yours, from the original brief):** natural-language query as the primary input for every module, DOCX (cut), Urdu/Arabic/Hindi (Urdu is a stretch goal), TSTR/TRTS, privacy attack metrics (only two cheap ones kept), multi-run variation, narrative documents (assignments, letters, reports). **Added in v2 (section 0.4):** feasibility check, conditional relationships, three-tier validation with a corrupt-dataset demo, reproducibility checksums, editable spec panel, bundled sample data, Pakistan locale profile, naive baseline, schema view, seasonality, invoices from generated orders.

---

## 3. Constraints

### 3.1 Hard constraints (from you)

| Constraint | Consequence |
|---|---|
| About 10 hours to build | Strict P0/P1/P2 tiering, everything else cut (section 4) |
| 8 GB RAM, about 20 GB disk | No large models, no GPU training, DataFrames capped at 100k rows per table, one Chromium instance at a time, RandomForest with `n_jobs=1` |
| No large local LLMs | All language work goes through an external API |
| External free or low-cost APIs allowed | Groq (primary) |
| You know FastAPI | Backend is FastAPI |
| Three people, Claude Code allowed | Parallel tracks with contract-first integration (section 20) |
| Strict working MVP | Demo path first, extras only after |

### 3.2 Hardware budget notes (PROPOSED)

- 100k rows × 20 columns in pandas is roughly tens of MB. Fine.
- Playwright's Chromium is about a 200–300 MB download and a few hundred MB of RAM while running. Reuse one browser instance, close it when idle.
- scikit-learn RandomForest: `n_estimators=100`, `max_depth<=12`, `n_jobs=1`, train on at most 20k rows.
- Nearest-neighbour privacy check: at most 5k sampled rows per side.
- Upload limit 20 MB total. Row cap 100k per table. Narrative document cap 20 per run.
- SDV is **not installed** in the MVP environment (it pulls in PyTorch, a multi-GB install). If we add it later it goes in a separate virtual environment (section 10.9).

---

## 4. Scope tiers and the cut list

### 4.1 P0 — the demo path must work (DECIDED)

Version 1 items:

- Query mode for Tabular, Relational and structured Documents (invoice, bank statement to PDF).
- Fresh seed on every Enter, and typed seed reproduces a run.
- Relational validator with validity in the scorecard.
- CSV upload for **Tabular** (copula fit) scored with fidelity and TSTR/TRTS.
- Per-run scorecard and run history.
- Export: CSV, JSON, PostgreSQL SQL dump, PDF zip.

Added in v2 (adoption DECIDED, tier PROPOSED):

- Feasibility check before generation (7.8).
- Three-tier validation layer and the negative test suite with the corrupt-dataset button (9.4, 9.6).
- Conditional relationships in query mode, shipped in the hand-verified e-commerce template (8.4.1).
- Checksums shown next to the seed (15.5).
- Editable spec panel (7.9).
- Bundled sample dataset and readable upload errors (10.11).
- Pakistan locale basics: phone, PKR formatting, name and city pools (8.13).

### 4.2 P1 — built if time allows, in this order (DECIDED as scope, ordering PROPOSED)

1. Invoices generated from the relational output (12.7).
2. Naive-baseline comparison in data mode (14.10).
3. Relational data mode with FK cardinality learning and rule mining (v1 item).
4. Detected-schema view with corrections (10.2.1).
5. Seasonality in dates (8.12).
6. Data-mode group-wise conditioning (10.6).
7. Save and run-history persistence on disk; documents-from-data mode (v1 items).
8. Rest of the Pakistan locale profile: landline codes, full area lists, Urdu names (8.13).

The hour-3 checkpoint decides how far down this list we go (section 20.1).

### 4.3 P2 — cut first (DECIDED, order PROPOSED)

In cut order: Urdu/Arabic PDF polish, Jev, extra-metrics details drawer, reference upload in query mode, advisory LLM realism check, then **narrative documents** (demoted from P1 in v2, ASSUMED).

### 4.4 Cut entirely (DECIDED)

DOCX output; SDV multi-table HMA; CTGAN and TVAE; differential privacy with real guarantees; membership inference, re-identification and attribute-disclosure attacks; learning layout from an uploaded PDF; schema-file upload; real-time collaboration; authentication and multi-user accounts.

---

## 5. Core principles

### 5.1 The split of responsibilities (DECIDED)

| Actor | Does | Never does |
|---|---|---|
| **LLM (Groq)** | Turns the query into a spec; writes value pools (names, merchants, products, cities); writes narrative document bodies; suggests column types and edge-case patterns | Generate rows; produce any number that must reconcile; choose keys; set seeds or row counts |
| **Deterministic code** | Every row, key, date and seed; every amount, total and balance; rule enforcement; validation; masking, hashing and noise; scoring; rendering; export | Invent domain knowledge it was not given (that is the LLM's job) |
| **Statistical code** | Fit and sample marginals and copulas in data mode; compute KS, TVD, correlation, TSTR/TRTS, nearest-neighbour distances | Pretend statistics equal realism when there is no real reference |
| **Constraint engine (our relational core)** | Order tables by dependency; sample FKs from existing keys; compute derived aggregates after children exist | Fix violations after the fact by patching (it prevents them instead) |

### 5.2 Never delegate to an LLM (DECIDED)

Primary keys, foreign keys, arithmetic of any kind, row counts, seeds, dates that must satisfy an ordering, anything that must reconcile across tables.

### 5.3 Where randomness lives

Only in seeded NumPy generators inside the core (section 8.1). The LLM's output is captured once, cached and saved with the run, so the LLM is a source of *content*, never of *nondeterminism inside a run*.

### 5.4 Where validation lives

1. **Before generation:** the feasibility check (7.8) rejects impossible requests with an explanation.
2. **At the spec boundary:** Pydantic validation of every LLM-produced or user-edited spec, with one repair retry for LLM output.
3. **At generation time:** constructive guarantees (sections 8 and 9), so violations cannot be produced.
4. **After generation:** the three-tier validator re-checks structure, rules and behaviour and reports counts (section 9.4). The validator itself is tested against deliberately broken data (9.6).
5. **At scoring time:** fidelity, utility, privacy (section 14).

### 5.5 Honest labelling everywhere

Every score in the UI carries a **reference badge** naming what it was measured against: `vs. real hold-out`, `vs. spec`, or `structural`. We never present a self-consistency number as realism.

---

## 6. System architecture

This matches diagram 01 in `architecture.html`.

```
React workspace  ──HTTP──▶  FastAPI gateway
                               │
             ┌─────────────────┼─────────────────┐
             ▼                 ▼                 
      Spec builder ◀─ ask/JSON ─▶ Groq LLM layer      Data-mode fitter
             │                                              │
             └──────────────▶ Generation core ◀── learned ──┘
                                   │      │
                                   │      └─rows──▶ Document renderer ──PDF──┐
                                   ├─tables──▶ Validator + scorer ──scores──▶ Runs + export
                                   └───────────── dataset ─────────────────▶
```

### 6.1 Component table

| # | Component | Responsibility | Inputs | Outputs | Main tech |
|---|---|---|---|---|---|
| 1 | **React workspace** | One page: module sidebar, query/upload toggle, config panel, preview canvas, scorecard, run history, export | User actions | HTTP calls | Vite, React, Tailwind |
| 2 | **FastAPI gateway** | REST endpoints, in-memory run cache, upload handling, polling for scores | HTTP | JSON, files | FastAPI, uvicorn, python-multipart |
| 3 | **Groq LLM layer** | Every LLM call: cache, key pool, cooldown, fallback chain, JSON validation, offline path | Prompt, schema | Validated JSON or text | httpx or OpenAI-compatible SDK |
| 4 | **Spec builder** | Turns a query into a validated spec (query mode) using the LLM layer; loads templates | Query, template | Spec plus pools | Pydantic, simpleeval |
| 5 | **Data-mode fitter** | Type/key inference, 80/20 split, copula fit, FK cardinality learning, rule mining; output is a *learned spec* | Uploaded CSVs | Learned spec plus fitted models | pandas, numpy, scipy |
| 6 | **Generation core** | Seeded generation in dependency order, derived values, rules, edge cases, privacy transforms | Spec plus seed | Dict of DataFrames plus metadata | pandas, numpy, Faker |
| 7 | **Validator + scorer** | Structural and rule validation; fidelity, utility, privacy; overall score | Tables (plus real train/hold-out) | Scores JSON | scipy, scikit-learn |
| 8 | **Document renderer** | Jinja2 HTML templates to PDF; narrative document pipeline | Rows, document spec | HTML, PDF | Jinja2, Playwright |
| 9 | **Runs + export** | Run lifecycle, temporary cache, Save, exports (CSV, JSON, SQL, PDF zip) | Tables, scores | Files | pandas, sqlite3 (for DDL testing), zipfile |

### 6.2 Two ways to get a spec

The generation core only ever consumes a **spec**. There are exactly two producers:

- **Spec builder** (query mode): the LLM writes it, Pydantic validates it.
- **Data-mode fitter**: code learns it from uploaded data.

This is what makes both modes share one engine.

### 6.3 Key runtime rules

- **Generate is synchronous for data, asynchronous for scores.** `POST /generate` returns the preview and `run_id` as soon as tables exist and structural validity is known. Fidelity, TSTR/TRTS and privacy are computed in a background thread and fetched by polling (section 16).
- **Spec and pools are cached per query** (section 11.5), so pressing Enter again costs zero API calls.
- **Feasibility runs before generation.** `POST /generate` validates the spec, runs the feasibility check (7.8), and only then generates. A failed check returns `422 infeasible` and generates nothing.
- **Temporary runs:** a run lives in an in-memory cache (last 10) until you press **Save** (DECIDED). Download works without saving.

---

## 7. The spec (the contract between the LLM and the engine)

### 7.1 Decision (DECIDED)

**Option C:** a **fixed vocabulary** of column generators and rule types, plus a small **safe expression evaluator** (`simpleeval`) for row-level derived values. Rejected: letting the LLM write Python or pandas code and running it with `eval`, because it is unreliable, a security hole, and impossible to validate or reproduce.

Everything in the spec is validated by Pydantic. If validation fails, the error text is sent back to the LLM **once** for repair. If it still fails, the LLM layer falls back per section 11.4.

### 7.2 Spec top level (PROPOSED field names)

| Field | Type | Meaning |
|---|---|---|
| `spec_version` | string | For future migration |
| `module` | `tabular` \| `relational` \| `documents` | |
| `locale` | string like `en_PK` | Drives Faker locale, date and number formats |
| `currency` | ISO code | e.g. `PKR`, `USD` |
| `as_of` | date | "Today" for the dataset. Timestamps never exceed it |
| `tables` | list | Table definitions (below) |
| `rules` | list | Cross-table and table-level rules (section 7.5) |
| `pools` | map | Named value pools from the LLM (section 11.6) |
| `edge_cases` | list | Suggested null, outlier and rare-pattern rules (section 8.10) |
| `documents` | object | Present for the documents module (section 12) |
| `unsupported` | list | Rules the user asked for that the vocabulary cannot express |

`unsupported` is how we stay honest: if the query asks for something outside the vocabulary, the UI says so instead of silently ignoring it.

### 7.3 Table definition

```
name, rows (int, or "per_parent" for children), pk (column name),
columns: [ {name, gen, ...params} ],
parents: [ {table, fk_column, cardinality: {min, max, dist, params}} ]  # for child tables
conditioned_by: "parent_table.column"   # optional, see section 8.4.1
```

### 7.4 Column generator vocabulary (PROPOSED)

| `gen` | Purpose | Key parameters |
|---|---|---|
| `sequence` | Integer IDs | `start`, `step` |
| `uuid` | Random UUID from the seeded generator (not `uuid4()`) | |
| `int_range` | Integers | `dist` (uniform, normal, lognormal, poisson), params, `min`, `max` |
| `float_range` | Floats | same |
| `money` | Amounts stored as **integer minor units** (cents, paisa) | dist params, `by` (conditional column) |
| `categorical` | Weighted categories | `values`, `weights`, optional `by` |
| `boolean` | | `p` |
| `date_range` | Dates | `start`, `end`, `dist` (uniform, recent_weighted), optional `seasonality` (section 8.12) |
| `date_offset` | Date relative to another column, or the parent row's date | `base` (column or `parent.column`), `offset_days` distribution, `min_offset` |
| `pool` | Sample from a named LLM pool | `pool`, optional `weights` |
| `email` | Derived from name columns and a domain pool | `from` (columns), `domains` |
| `phone` | Locale-formatted | `locale`, `prefixes_by` (e.g. city) |
| `faker` | Any allow-listed Faker provider | `provider`, `locale` |
| `expr` | Row-level derived value | `expression` (simpleeval) |
| `aggregate` | Parent value computed from child rows | `fn` (sum, count, avg, min, max), `table`, `column` |
| `conditional` | Distribution depends on another column | `by`, `map` |
| `text` | Short free text from a pool or template | |
| `national_id` | Synthetic national-ID-like string in a clearly fake pattern (section 8.13) | `locale`, `gender_from` (column) |

Only names in this table are accepted by the Pydantic model. Unknown `gen` values fail validation.

### 7.5 Rule vocabulary (PROPOSED)

| `rule` | Enforced by | Validated by |
|---|---|---|
| `not_null`, `unique` | Generators | Validator |
| `range` (`min`, `max`) | Clip after generation | Validator |
| `after` (column ≥ another column or parent column + optional minimum offset) | `date_offset` sampling | Validator |
| `sum_of` (parent column = Σ child column, tolerance in minor units) | `aggregate` computed after children | Validator |
| `equals_expr` (column equals a safe expression of other columns) | `expr` | Validator |
| `running_balance` (balance = previous balance ± amount, `min_balance`) | Statement generator | Validator |
| `max_children` / `min_children` | Child-count sampling | Validator |
| `status_from_dates` (status derived from timestamps) | `expr` with conditional expression | Validator |
| `group_order` (the mean of a numeric column is ordered across groups, e.g. student < retail < business) | `conditioned_by` (8.4.1) | Validator, behavioural tier, groups of at least 30 rows |
| `bound_by_group` (a per-group cap or floor, e.g. student line total at most Rs 60,000) | Resample then clip in the generator | Validator, behavioural tier |
| `share_within` (a category, null or outlier share stays within tolerance of the spec value) | Edge-case injection and weighted sampling | Validator, behavioural tier |

### 7.6 The safe expression evaluator

`simpleeval` evaluates expressions with a whitelist of functions and operators (for example `qty * unit_price * (1 - discount)`). Allowed function whitelist (PROPOSED): `round`, `min`, `max`, `abs`, `int`, `float`. No attribute access, no imports, no arbitrary calls. Expressions are evaluated **vectorised** over pandas columns where possible; otherwise per row with a hard cap on row count.

### 7.7 Example spec (illustrative, abbreviated)

```json
{
  "spec_version": "1",
  "module": "relational",
  "locale": "en_PK",
  "currency": "PKR",
  "as_of": "2026-09-29",
  "tables": [
    {
      "name": "customers", "rows": 5000, "pk": "customer_id",
      "columns": [
        {"name": "customer_id", "gen": "sequence", "start": 1},
        {"name": "first_name", "gen": "pool", "pool": "first_names"},
        {"name": "last_name", "gen": "pool", "pool": "last_names"},
        {"name": "email", "gen": "email", "from": ["first_name", "last_name"], "domains": ["gmail.com", "yahoo.com"]},
        {"name": "city", "gen": "pool", "pool": "cities"},
        {"name": "signup_date", "gen": "date_range", "start": "2023-01-01", "end": "2026-09-01", "dist": "recent_weighted"},
        {"name": "segment", "gen": "categorical", "values": ["retail", "wholesale", "vip"], "weights": [0.7, 0.2, 0.1]}
      ]
    },
    {
      "name": "products", "rows": 200, "pk": "product_id",
      "columns": [
        {"name": "product_id", "gen": "sequence", "start": 1},
        {"name": "category", "gen": "categorical", "values": ["electronics", "grocery", "apparel"], "weights": [0.3, 0.4, 0.3]},
        {"name": "name", "gen": "pool", "pool": "product_names", "by": "category"},
        {"name": "price", "gen": "money", "by": "category",
         "dists": {"electronics": {"dist": "lognormal", "median": 45000, "sigma": 0.6},
                   "grocery": {"dist": "lognormal", "median": 800, "sigma": 0.5},
                   "apparel": {"dist": "lognormal", "median": 3500, "sigma": 0.5}}}
      ]
    },
    {
      "name": "orders", "pk": "order_id",
      "parents": [{"table": "customers", "fk_column": "customer_id",
                   "cardinality": {"total": 20000, "min": 0, "max": 40, "dist": "lognormal"}}],
      "columns": [
        {"name": "order_id", "gen": "sequence", "start": 1},
        {"name": "order_date", "gen": "date_offset", "base": "parent.signup_date", "offset_days": {"dist": "lognormal", "median": 30, "sigma": 1.0}, "min_offset": 0},
        {"name": "status", "gen": "expr", "expression": "'delivered' if delivered_at is not None else 'shipped'"},
        {"name": "total", "gen": "aggregate", "fn": "sum", "table": "order_items", "column": "line_total"}
      ]
    },
    {
      "name": "order_items", "pk": "item_id",
      "parents": [
        {"table": "orders", "fk_column": "order_id", "cardinality": {"min": 1, "max": 8, "dist": "poisson", "lam": 2.2}},
        {"table": "products", "fk_column": "product_id", "pick": "weighted_popularity"}
      ],
      "columns": [
        {"name": "item_id", "gen": "sequence", "start": 1},
        {"name": "quantity", "gen": "int_range", "dist": "poisson", "lam": 1.4, "min": 1, "max": 10},
        {"name": "unit_price", "gen": "expr", "expression": "product.price"},
        {"name": "line_total", "gen": "expr", "expression": "quantity * unit_price"}
      ]
    }
  ],
  "rules": [
    {"rule": "after", "table": "orders", "column": "order_date", "than": "customers.signup_date"},
    {"rule": "sum_of", "parent": "orders.total", "child": "order_items.line_total"}
  ],
  "unsupported": []
}
```

The exact JSON shape is a **PROPOSED** starting point. Track A owns the final Pydantic models and commits them in the first 45 minutes.

### 7.8 Feasibility check (P0)

**What it is:** a pure-arithmetic pass over the validated spec, in `core/feasibility.py`, that decides whether the requested dataset can exist **before anything is generated**. It returns `{ok, errors[], warnings[]}`. Each entry has a plain-language message and a suggested fix.

| Check | Example failure | Suggested fix shown |
|---|---|---|
| Child totals against parent rows | "10 customers x exactly 20 orders = 200 orders, but 100 were requested" | Raise orders to at least 200, or lower orders per customer to 10 |
| `min_children` and `max_children` against the requested total | 100 orders, 10 customers, max 5 per customer (capacity 50) | Raise the maximum or lower the total |
| 1:1 needs equal row counts | 1,000 accounts for 900 customers, 1:1 | Make the counts equal |
| N:N pair capacity | 50 distinct pairs requested from 5 x 5 with max 3 per side | Reduce pairs or raise the cap |
| Unique columns against pool or pattern capacity | 50,000 unique product names from a pool of 300 | Combine pools, allow suffixes, or reduce rows |
| Date windows | Child dates must precede `as_of`, but the parent date window already ends after it | Move `as_of` or shorten the offset |
| Sanity | Weights not summing to 1 (normalised with a warning), `min` above `max` | Corrected or reported |
| Caps | More than 100k rows per table, more than 20 narrative documents | Clamp with a warning |
| Bank statement balance | `min_balance` above the opening balance | Lower it or raise the opening balance |

**Errors** stop the run: `POST /generate` returns `422` with code `infeasible` (section 16.5) and the UI shows the message in a red box. **Warnings** do not stop the run; they are shown beside the preview (for example "the first-name pool has 300 entries, so repeated first names are expected"). Estimated effort 30–45 minutes.

**Why it matters:** the LLM will occasionally emit contradictory counts, and a judge may type an impossible prompt on purpose. The message shows the system understands its own constraints. It also stops bad specs before they cost API retries. Data mode uses the same check when the user overrides row counts.

### 7.9 Editable spec panel (P0)

The UI shows the validated spec JSON in a collapsible editor beside the query. The user can edit it and press **Run from spec**, which calls `POST /generate` with a `spec` override. The LLM is **not** called.

- The override goes through Pydantic and the feasibility check like any other spec. Errors appear inline with the field path.
- Pools come from the cache for that query. If an edit references a pool name that is not cached, the run falls back to the offline pool with a warning.
- **Why:** it makes the AI step auditable (you can see and change what the LLM decided), and it is the **fallback if the API dies mid-demo**: pre-cached specs plus this panel still run. A **Reset to LLM version** button restores the cached spec.
- Endpoints: `POST /spec/validate` (check without generating) and the `spec` field on `POST /generate`. Estimated effort 45–60 minutes.

---

## 8. The generation core

### 8.1 Seeds, variation and reproducibility (DECIDED behaviour, PROPOSED implementation)

**Behaviour:**

- Each run gets a **master seed**. If the user leaves the seed blank, a random one is chosen at run time and **shown in the UI and saved with the run**.
- Same spec plus same seed = identical dataset. Different seed = a different valid dataset. This holds for all three modules.
- **Values change on every Enter; structure stays fixed** (ASSUMED, your Question 5 was never answered). A separate "re-interpret query" button re-calls the LLM if the user wants a different schema.

**Implementation:** derive a seed per table and per column from the master seed and the *names*, not from the order they happen to be generated in:

```python
import hashlib, numpy as np

def derive_seed(master: int, *keys: str) -> int:
    h = hashlib.blake2b(f"{master}|{'|'.join(keys)}".encode(), digest_size=8).digest()
    return int.from_bytes(h, "big")

rng = np.random.default_rng(derive_seed(master, "orders", "order_date"))
```

Adding a column does not reshuffle any other column, because each has its own stream. This must be in place from the first commit; retrofitting it is painful.

**The recipe for exact reproduction is:** `spec + pools + master seed`. Because the LLM is not deterministic, the spec and pools are stored with the run (section 15). Re-running without the stored spec would call the LLM again and could differ.

**"Infinite variation" wording (PROPOSED):** say **"unlimited variations"**, not "infinite". Variety is bounded by the pools and distributions in the spec, so it is practically unlimited but not literally infinite.

**Reproducibility proof (v2, PROPOSED):** exports are hashed with SHA-256 and the hashes are shown next to the seed (section 15.5). Re-running the same spec and seed shows identical hashes, which is stronger than saying "reproducible". The claim is "same spec, same seed, same software version".

### 8.2 Generation order

1. Build the table dependency graph from `parents` entries.
2. **Topological sort.** A cycle is rejected at spec validation with a clear error.
3. Generate root tables (no parents), then children in order.

### 8.3 Entity-first generation

Columns are never generated independently when they describe one real-world thing. A customer is built as one coherent unit:

```
locale → first name → gender-consistent last name → email derived from name → city → phone prefix consistent with city → currency consistent with country
```

A product is built as `category → name from that category's pool → price from that category's own distribution`. This is what stops a laptop costing 300 rupees.

### 8.4 Conditional distributions

`price | category`, `quantity | category`, `segment | income`. The **LLM supplies the domain knowledge** (typical price ranges per category). **Code validates the shape** (min below max, weights sum to 1) but cannot verify the knowledge is true. The validation report labels LLM-written conditionals for unfamiliar domains as **"unverified domain assumptions"**.

### 8.4.1 Conditional relationships across tables (P0 in query mode)

**The gap this closes:** distributions, correlations and FK cardinality are not enough. Without behaviour tied to who the customer is, an 18-year-old student can place a Rs 2,000,000 machinery order as often as anyone else. The data is valid but not coherent.

**The idea:** the customer's **segment** conditions their orders.

```
customer segment  ->  order count, product categories, quantities, price tier  ->  order total (computed)
```

| Segment | Orders per customer | Categories | Quantity and value |
|---|---|---|---|
| student | low | books, mobiles, grocery | small quantities, low caps |
| retail | medium | broad mix | ordinary |
| business | medium to high | business and bulk products | large quantities |
| premium | highest frequency | electronics, apparel | highest average order value |

**Mechanism (all vectorised, seeded per table, column and group):**

1. The parent gets a categorical `segment` column with weights (optionally itself conditioned, for example by income).
2. Child counts are sampled per parent using the **segment's intensity**, then scaled to the exact requested total (8.6). The total wins; segment parameters act as relative intensities, so their ordering survives the scaling.
3. The FK is built by `np.repeat`. Then each child row looks up its parent's segment with one indexed take, for example `seg = parent_segment[fk_positions]`. Grandchildren (order_items via orders to customers) resolve the join path, at most two hops.
4. For each group (at most 5, so a tiny loop) the generator draws category, product, quantity and price tier from that group's parameters. Products are picked within the chosen category, so a laptop is never priced like grocery.
5. `line_total`, `subtotal` and `total` are then computed by the existing aggregate machinery.

**Important caveat:** the order total cannot be set directly, because it equals the sum of the items. Segment behaviour therefore acts on **which products, how many and at what price tier**; the total follows and stays consistent.

**Spec shape (PROPOSED):**

```json
{"table": "orders", "conditioned_by": "customers.segment",
 "cardinality_by_group": {"student": {"weight": 0.5}, "retail": {"weight": 1.0},
                          "business": {"weight": 1.6}, "premium": {"weight": 3.0}}}
{"table": "order_items", "conditioned_by": "customers.segment",
 "category_weights": {"student": {"books": 0.5, "mobiles": 0.3, "grocery": 0.2},
                      "business": {"machinery": 0.4, "electronics": 0.4, "grocery": 0.2}},
 "quantity_by_group": {"student": {"max": 2}, "business": {"max": 50}},
 "max_line_total_by_group": {"student": 6000000}}
```

Money values are integer minor units, so `6000000` means Rs 60,000.

**Who writes it:** for the e-commerce template a human writes and checks it (hand-verified, so the demo never depends on the LLM). For other domains the LLM proposes the conditioning, flagged as **unverified domain assumptions** (8.4).

**Limits:** one conditioning key per table, at most 5 groups, categorical parent attribute only (a numeric attribute such as income is first binned into at most 5 quantile bands, which is P1). If the LLM omits the block or it fails validation, the engine falls back to unconditional sampling with a warning; the run does not fail.

**Enforcement and checks:** `group_order`, `bound_by_group` and `share_within` (7.5) are checked in the behavioural tier of the validator (9.4.1), against the spec. Data mode gets group-wise conditioning in P1 (10.6). The LLM's conditional structure is part of the hour-one bake-off (11.3).

### 8.5 Hand-verified templates (DECIDED scope, contents PROPOSED)

We ship three templates written and checked by us, so the demo never depends on an LLM inventing a schema:

1. **E-commerce:** customers (with a `segment`), products, orders, order_items (plus optional payments). Orders carry `subtotal`, `discount`, `tax` and `total` so invoices reconcile (12.7). Segment-driven behaviour is hand-written in the template (8.4.1).
2. **Banking:** customers, accounts, transactions.
3. **Invoicing:** customers, products, invoices, invoice_lines.

For a known domain the LLM only customises (rename, add columns, choose locale and sizes). For an unfamiliar domain it writes the conditionals itself, flagged as unverified.

### 8.6 Cardinality and foreign keys (relational)

**Key idea:** we do not sample foreign keys and hope. We sample **how many children each parent gets**, then assign children to parents by repeating parent keys. An orphan cannot occur.

1. For each parent row, sample a child count from the cardinality distribution (bounded by `min` and `max`).
2. **Exact totals:** if the spec says "20,000 orders for 5,000 customers", scale the sampled counts to hit exactly 20,000 by adding or removing children on randomly chosen parents while respecting `min` and `max`.
3. Build the child FK column by `np.repeat(parent_keys, counts)`.
4. **1:1** is `min = max = 1`. **1:N** is the general case. **N:N** uses a **junction table**: sample distinct pairs without replacement from the two parents, up to a per-parent maximum, and never create duplicate pairs.
5. A second parent on a child (for example `product_id` on `order_items`) is sampled from the parent's existing keys with an optional popularity weighting, so some products sell more than others.

### 8.7 Derived and aggregate values

- **Money is stored as integer minor units** (cents, paisa) internally to avoid floating-point drift. Conversion to decimal happens at export and render time only.
- `aggregate` columns (for example `orders.total`) are computed **after** children exist, using a grouped sum over the child table. They are **computed, never sampled**, so they cannot disagree with the children.
- `expr` columns evaluate with `simpleeval` over already-generated columns.
- Rounding rule (PROPOSED): round half up to the minor unit, applied at line level first, then summed. Tax and discount follow the same rule (section 12.1.2).

### 8.8 Date and timeline consistency

Dates form a chain per entity: `signup → first order → shipped → delivered`, each bounded by `as_of`. Implementation: child dates are the parent date plus a sampled offset (`date_offset`), clipped to `as_of`. Status fields are **derived from the timestamps** (a delivered order always has a delivery date; a cancelled order never does). Payments equal the order total, and refunds never exceed what was paid.

### 8.9 Text and categorical values

- Names, merchants, product names, cities and descriptions come from **pools** (LLM-written once per query, cached) or from **Faker**. Code samples from the pools with the seeded generator.
- Categorical values come from the spec's `values` and `weights`.

### 8.10 Edge cases and outliers (DECIDED)

- The **LLM proposes patterns** (for example "10% of orders have a null coupon", "a few very large orders", "rare status value"). It never applies them.
- **Code applies them** at the configured `null_rate` and `outlier_rate`, at seeded random positions, after the main generation so structure stays valid.
- Rules that must not break (PKs, FKs, `not_null` columns) are excluded from null injection automatically.
- Outliers are injected by scaling a seeded subset of a numeric column by a factor drawn from a heavy-tailed distribution, then clipped only by hard `range` rules if any.

### 8.11 Privacy controls (DECIDED scope)

| Control | Implementation |
|---|---|
| **Masking** | Replace characters with `*`, keeping a configurable prefix or suffix (for example phone and email) |
| **Hashing** | Salted SHA-256, with the salt derived from the master seed so the same seed gives the same hashes |
| **Noise** | Laplace noise added to numeric columns with a user-set scale |

**Wording (PROPOSED):** "Laplace noise, no formal differential-privacy guarantee." We do **not** claim differential privacy, because a real guarantee needs sensitivity bounds and privacy-budget accounting that we will not build in 10 hours.

### 8.12 Seasonality in dates (P1)

Real order data is not uniform over time. `date_range` accepts a `seasonality` block:

```json
{"seasonality": {"weekday_weights": [1.0, 1.0, 1.0, 1.0, 1.2, 1.4, 1.3],
                 "month_end_boost": 1.3,
                 "events": [{"name": "11.11", "rule": "fixed:11-11", "boost": 4.0},
                            {"name": "Eid al-Fitr", "rule": "table:eid_fitr", "boost": 2.5, "window_days": [-7, 2]}]}}
```

**Implementation:** build a per-day probability over the date window (base distribution x weekday weight x month-end boost x event boost) and sample days with the seeded generator. For child dates that must not precede the parent date, sample from the global seasonal distribution and resample rows that violate the ordering, up to 5 rounds, then clip the remainder to the parent date. No date ever exceeds `as_of`.

**Calendar data:** `data/calendars/pk.json` holds fixed sale dates (11.11, 12.12, 14 August, Black Friday as the fourth Friday of November) and a small **hardcoded table of Eid and Ramadan dates for 2023–2027**. **VERIFY** those dates against a reliable calendar, because lunar dates shift each year and by a day or two locally.

**Payoff:** the date histogram immediately shows structure (weekend peaks, spikes near events). Estimated effort 30–45 minutes.

### 8.13 Pakistan locale profile (`en_PK`)

Locale is part of the pitch, and this is where a plain Faker script looks weakest. Everything below is code or curated data, never LLM arithmetic.

| Item | Approach | Tier |
|---|---|---|
| **Mobile numbers** | Format `+92 3XX XXXXXXX` (national form `03XX-XXXXXXX`), operator prefixes from an allow-list of valid 03xx ranges (**VERIFY** the list) | P0 |
| **Landlines** | City codes consistent with the city (for example 021 Karachi, 042 Lahore, 051 Islamabad and Rawalpindi), through `prefixes_by` | P1 |
| **Cities and areas** | About 30 cities with approximate population-style weights and a few real areas each (for example Karachi: DHA, Clifton, Gulshan-e-Iqbal; Lahore: Gulberg, DHA, Johar Town; Islamabad: F-7, G-11; Rawalpindi: Saddar, Bahria Town). Curated by the team, extended by the LLM pool. **Weights are approximate; do not claim census accuracy.** | P0 (cities), P1 (areas) |
| **Names** | LLM pools of about 300 first names (split by gender) and 300 surnames, cached, plus a hand-made offline fallback of about 50 each in `locale_pk/names.json`. First name and gender stay consistent with each other. Urdu-script names are a stretch. | P0 |
| **Currency format** | PKR shown as `Rs 1,23,456.00` (lakh grouping) or `Rs 1,234,456.00` (western grouping), as a **locale option**, default **lakh (ASSUMED)**, because both are used in Pakistan. A 10-line hand-written function, not a library, since I cannot confirm Babel's PKR grouping. Exports (CSV, JSON, SQL) keep plain numbers; formatting applies to the UI and PDFs. | P0 |
| **Dates** | `DD/MM/YYYY` in documents, ISO 8601 in exports | P0 |
| **National-ID-like field** | Pattern `#####-#######-#` from `gen: national_id`. **Reserved fake marker:** the first digit is `0` (as far as I know real numbers start with 1 to 7, **VERIFY**), so a generated value cannot coincide with a real person's number. The last digit's parity follows the gender column, for consistency only. The column is flagged synthetic in the UI and masked by default. | P1 |
| **Tax label and rate** | Region profile with "Sales Tax (GST)" and a default rate of 18% (**VERIFY** the current standard rate before showing it) | P0 |
| **Email domains** | Common public providers only (gmail.com, yahoo.com, hotmail.com, outlook.com), never real company domains | P0 |

Estimated effort 45–60 minutes for the P0 items.

---

## 9. Relational consistency: what is guaranteed and what is not

### 9.1 Layer 1 — structural consistency, 100% by construction (DECIDED)

- Every PK is unique.
- Every FK points at a row that exists (parents are generated first, and FKs are built from parent keys).
- Cardinalities match the spec (counts are sampled then scaled to exact totals).
- Derived totals are computed from children.
- NOT NULL, UNIQUE and type constraints hold because generators cannot emit anything else.

### 9.2 Layer 2 — "makes sense", 100% for every encoded rule

Sense comes from: entity-first generation, conditional distributions, entity timelines, hand-verified templates, and the rule vocabulary. It is **100% for every rule we encode**. It is *not* a promise about rules nobody encoded.

### 9.3 What we do not promise

- Semantic correctness for rules nobody encoded in an arbitrary domain. No system can prove that.
- In data mode, the output cannot be more sensible than the learned data. In the P0 build child attributes are not conditioned on parent attributes (section 10.6), so a low-income customer with luxury orders can appear unless a mined rule blocks it. Query mode does condition on segment (8.4.1); data mode gets one conditioning attribute per FK in P1.
- LLM-written domain knowledge (prices per category, typical volumes) is checked for **shape** only, not truth.

### 9.4 The validator: a three-tier layer

The generator is designed so structural and rule violations never fire. The validator is a **seatbelt** for our own bugs and for bad specs, and it is itself tested against broken data (9.6). It has three tiers.

#### 9.4.1 The three tiers

| Tier | What it checks | A failure means | Feeds |
|---|---|---|---|
| **1. Structural** | PK unique and not null; FK exists in parent; types; NOT NULL and UNIQUE; row counts; child count within `min`/`max`; aggregate equals child sum | A bug in the engine | Validity. **Hard fail**, run marked failed |
| **2. Business rules** | Totals equal the sum of items; date ordering; status combinations (a cancelled order is never delivered); non-negative and range checks; running balance never below the minimum; invoice totals recompute | A rule was violated | Validity. Reported with counts |
| **3. Behavioural coherence** | `group_order`, `bound_by_group`, `share_within` (7.5); null, outlier and cancelled-order rates within tolerance | The data is valid but implausible | **Separate panel**, badge `vs. spec`. **Not** part of Validity or the overall score (PROPOSED) |

Tier 3 checks against the **spec**, not against reality, which is the honest thing to do in query mode where no real data exists. Details (PROPOSED): a rate passes when it is within 3 standard errors or 1 percentage point of the spec value, whichever is larger; a `group_order` test needs at least 30 rows in each compared group, otherwise it is skipped and says so.

#### 9.4.2 Order of operations

`feasibility (7.8)` -> `generate` -> `tier 1` -> `tier 2` -> `tier 3` -> `scoring (14)`.

#### 9.4.3 What happens on failure (repair, kept deliberately small)

We do **not** build a general repair-and-regenerate loop; construction makes it unnecessary. Instead:

- **Tier 1 failure:** hard fail, the run is marked failed with the failing check named.
- **Tier 2 failure:** a **targeted, deterministic fix** runs once, then the rule is re-validated. Fixes: recompute an aggregate, clip a range, re-derive a status from timestamps, resample a debit that would breach the balance. If it still fails, it is reported with counts.
- **Tier 3 failure:** reported only. It signals a spec problem, not a data bug.

#### 9.4.4 The check list (v1 table, now mapped to tiers)

| Check | Tier | On failure |
|---|---|---|
| PK unique, not null | 1 | Hard fail, run marked failed |
| FK exists in parent | 1 | Hard fail |
| Child count within `min`/`max` | 1 | Hard fail |
| Aggregate equals child sum (within tolerance) | 1 | Hard fail |
| Date ordering rules | 2 | Targeted fix, then reported with counts |
| `range`, `unique`, `equals_expr` | 2 | Targeted fix, then reported with counts |
| Running balance never below minimum | 2 | Targeted fix, then reported with counts |
| Invoice equals its order (12.7) | 2 | Reported with counts |
| Group order, per-group bounds, rate tolerances | 3 | Reported in the coherence panel |
| Share of LLM-written conditionals flagged "unverified" | Informational | Shown as a note |

The validity score (section 14.2) is the share of tier 1 and tier 2 checks passed. It should always be 100%; showing it is the demo evidence.

### 9.5 Optional advisory check (P2)

One LLM call reviews about 20 joined sample rows and flags implausible combinations. It is **advisory only**: never folded into the overall score and never called a guarantee.

### 9.6 Testing the validator with broken data (P0)

A validator that has only ever seen good data proves nothing. `core/corrupt.py` provides `corrupt(tables, kind, n, seed)`, which returns a modified **copy** plus the list of touched row IDs. The test suite (`tests/test_validator_negative.py`) asserts two things: a clean dataset passes every check, and each defect is caught by the **right** check with the right count.

| Defect (`kind`) | Expected finding |
|---|---|
| `orphan_fk` (child points at a missing parent) | Tier 1, FK check, `n` rows |
| `duplicate_pk` | Tier 1, PK check |
| `missing_parent` (a parent row deleted) | Tier 1, FK check |
| `null_in_not_null` | Tier 1 |
| `negative_quantity` | Tier 2, range rule |
| `wrong_total` (order total no longer equals its items) | Tier 1, aggregate check |
| `bad_status` (cancelled order that has a delivery date) | Tier 2, status rule |
| `group_bound` (student order above the cap) | Tier 3, `bound_by_group` |

**Demo button "Corrupt this dataset":** `POST /runs/{id}/corrupt` creates a **new derived run** labelled "CORRUPTED (demo only)", never modifying the original. The validator turns red and lists each failing check with the affected row IDs. This turns "we check integrity" into something the audience watches happen. Estimated effort 45 minutes; the same suite doubles as our regression net when someone breaks the engine at hour 7.

---

## 10. Data mode (fit from an uploaded CSV)

Data mode's job: read real data, produce a **learned spec** and fitted models, then feed the same generation core.

### 10.1 Pipeline (matches diagram 05)

`Upload → Infer schema → Split 80/20 → Fit tables → Learn structure → Sample → Validate → Score`, with the untouched 20% hold-out routed straight to Score.

### 10.2 Schema inference

**Column type detection (code, PROPOSED thresholds):**

| Detected type | Rule of thumb |
|---|---|
| ID | Unique ratio at least 0.98 and (name matches `id`, `_id`, `uuid`, `code`, `no` **or** values are monotonic integers) |
| Email / phone | Regex match on at least 90% of non-null values |
| Date / datetime | Parses with a date parser on at least 90% of non-null values |
| Numeric | Parses as number; integer if all values are whole |
| Boolean | Two distinct values like true/false, yes/no, 0/1 |
| Categorical | Distinct count at most `max(20, 5% of rows)` |
| Free text | Mean length above 30 characters and high uniqueness |
| Name / address / other PII | Column-name hints **plus** the classification step below |

**Semantic classification (DECIDED: hybrid):** send each column's name and five sample values to Groq (or optionally Jev) and ask it to pick one label from a **closed vocabulary** (the generator vocabulary in section 7.4). Code then **verifies** the answer (for example, an "email" label must pass the email regex on at least 90% of values). If verification fails, the column falls back to the code-detected type. This is why a closed vocabulary matters: the answer can never be a type we do not support.

**Key detection by code, not by an LLM:**

- **PK candidate:** unique and non-null.
- **FK candidate:** for column A in one table and PK column B in another: all non-null values of A are a subset of the values of B (containment at least 0.99), the dtypes are compatible, and a name-similarity check (for example `customer_id` and `customers.customer_id`) breaks ties.
- The UI shows the detected PKs, FKs and generators and lets the user **confirm or edit** them (`PUT /uploads/{id}/schema`). The fuller view is in 10.2.1.

#### 10.2.1 Detected-schema view (P1)

After a multi-CSV upload the UI shows, per table: columns with detected generator, confidence and source (`code`, `llm+verified`), the PK, and the FKs; plus the **parent to child graph** and any rule candidates. Auto-detection is impressive but sometimes wrong, so the user can correct it with **dropdowns**: change the PK, set an FK's parent (or none), change a column's generator from the closed vocabulary. Corrections go to `PUT /uploads/{id}/schema`, and cardinality and rule mining re-run for the affected tables. Low-confidence guesses are flagged, for example "near-FK: 97% of `orders.customer_id` values exist in `customers`, 412 orphans in your data". No drag-and-drop editor. Estimated effort 45–60 minutes.

### 10.3 Train / hold-out split (DECIDED)

Before fitting anything, **split the real data 80/20** (seeded). Fit on the 80%. The 20% is never used for fitting; it is used only for scoring. Scoring against the same rows we fit on would inflate the numbers, and a technical judge would spot it. The same split gives a proper privacy baseline (section 14.5).

For relational uploads, the split is by **parent key** so children stay with their parent.

### 10.4 The fitter interface (DECIDED: so SDV can slot in later)

```python
class Fitter(Protocol):
    def fit(self, df: pd.DataFrame, schema: TableSchema) -> "FittedModel": ...
class FittedModel(Protocol):
    def sample(self, n: int, seed: int) -> pd.DataFrame: ...
```

Our copula is the first implementation.

### 10.5 The copula (DECIDED: Option B, single table, hard time limit)

**Fit:**

1. Drop ID, PII and free-text columns from the *modeled* set; those are regenerated (below).
2. **Numeric and date columns:** convert dates to integer timestamps. Estimate the empirical CDF `u = rank / (n + 1)`. Store a quantile grid (for example 512 points) for the inverse.
3. **Categorical columns:** order categories by frequency, compute cumulative bin edges, and map each value to a uniform draw inside its bin. This treats the categorical as an ordinal proxy. It is simple and it is a **known limitation**.
4. Convert all `u` to normal scores `z = Φ⁻¹(u)`.
5. Estimate the correlation matrix `Σ` of the `z` values. If `Σ` is not positive semi-definite, clip eigenvalues at a small epsilon.
6. Per column, record the **null rate** and min/max.

**Sample:**

1. Draw `z ~ N(0, Σ)` using a seeded Cholesky factor.
2. `u = Φ(z)`.
3. Numeric: inverse quantile lookup, then clip to the observed `[min, max]`. Round if the original column was integer.
4. Categorical: pick the category whose bin contains `u`.
5. Apply per-column nulls independently at the recorded rates (limitation: null patterns are not correlated).

**What is regenerated, not sampled:** IDs (new sequence), names, emails, phones, addresses and free text (from pools or Faker). This is what protects privacy in data mode.

**Time-box (DECIDED):** if the copula is not working within **1.5 hours**, fall back to marginals plus a rank-correlation nudge and move on.

**Rejected:** marginals-only (correlations vanish, so correlation and TSTR scores look bad).

### 10.6 Learning relational structure (DECIDED: Option C, "rule mining")

For multi-table uploads, in addition to per-table fits:

1. **FK cardinality histogram:** for each FK, the distribution of children per parent (bounded by observed min and max). Used exactly like the spec's `cardinality`.
2. **Rule mining:** test a small, **closed** set of rule types against the real data, and enforce any that hold in **at least 99%** of rows (PROPOSED threshold):

| Mined rule | Test | Enforcement in generation |
|---|---|---|
| Date ordering within a table | `col_a <= col_b` holds ≥ 99% | Sample `col_b` as `col_a` + offset |
| Cross-table date ordering | `child.date >= parent.date` (via FK join) ≥ 99% | `date_offset` from the parent date |
| Non-negative numeric | `col >= 0` ≥ 99% | Clip |
| `sum_of` | `parent.col ≈ Σ child.col` (tolerance 0.5% or one minor unit) for ≥ 99% of parents | `aggregate`, computed after children |
| Category → numeric range | Per category, 1st to 99th percentile range | Clip into the per-category range after the copula |
| Row-level product (stretch) | `col_c ≈ col_a × col_b` ≥ 99% | `expr` |

The report lists **which rules were learned**, which is a pitch line: "we mine rules from your data and guarantee them".

**Known limitation of the P0 build (stated openly):** child attributes are **not conditioned on parent attributes**. Big customers' orders will not be systematically bigger. Full conditional fitting of the copula was cut as fragile.

**Group-wise conditioning (P1, adopted in v2, about 1 hour):** for each FK, pick the parent attribute most associated with the child's main columns (Cramér's V for categorical, or a numeric attribute binned into at most 5 quantile bands; PROPOSED). Fit the child's marginals and the children-per-parent histogram **separately per group**. Groups under 30 rows fall back to the global fit. One conditioning attribute per FK. This is the same idea as 8.4.1, learned from data instead of written in the spec. It does **not** make the copula conditional.

### 10.7 Sampling and validation

Sampling uses the same core as query mode, with the learned spec. The same validator runs. Then scoring runs against the hold-out.

### 10.8 Failure handling (PROPOSED)

| Situation | Behaviour |
|---|---|
| Mixed-type or messy column | Degrades to a simpler handling (treated as categorical or text) and adds a warning; never crashes the run |
| Huge free-text column | Regenerated from a pool, not modeled |
| No detectable target column for TSTR | Utility is shown as "n/a: no suitable target", with an option for the user to pick one |
| File over 20 MB or over 100k rows | Rejected with a clear message, or sampled down with a warning |

### 10.9 Adding SDV later (DECIDED)

Because of the `Fitter` interface, an SDV adapter is roughly 30 lines. Install it in a **separate virtual environment** after the core works, because it depends on PyTorch. Nothing else in the design depends on it. We would describe this as "SDV supported as an alternative backend".

### 10.10 What is not built for data mode

Conditional fitting inside the copula itself (only group-wise conditioning is P1), learning from messy real-world types at SDV's level, schema-file ingestion, chunked processing of very large files (uploads are capped instead).

### 10.11 Bundled sample dataset and readable errors (P0)

**Sample data:** `data/sample/` ships a small related set (customers about 2k rows, orders about 8k, order_items about 20k) and a single-table `customers_churn.csv` (about 5k rows with a target column that has real signal, for TSTR). A one-off script generates them with our own query-mode engine with conditional behaviour and planted correlations. **They are demo data made by the team, not real records, and the README and the UI say so.** Uses: the data-mode demo never depends on a judge's file working; a regression fixture; a target for TSTR. A "Try with sample data" button loads them. Scores on this data will look flattering because the same family of generator produced it, so we do not present it as proof of realism; a real public CSV, if the team finds one, is a stronger check (open item 6).

**Readable errors:** every failure returns `{code, message, hint, column?}` and the UI shows the message, never a traceback.

| Situation | Behaviour |
|---|---|
| Empty file, no header, not a CSV | Refuse with a clear message |
| Encoding not UTF-8 | Try `utf-8-sig`, `latin-1`, `cp1252`, then refuse |
| Delimiter not a comma | Sniff `;` and tab |
| Duplicate column names | Refuse, name the columns |
| Fewer than 50 rows | Warn that the fit will be weak; fewer than 10: refuse for fitting |
| More than 100k rows or 20 MB | Sample down with a warning, or reject |
| All-null column, unparseable dates, mixed types | Degrade to a simpler type with a warning (10.8) |
| Anything unexpected | A global handler returns `code: internal` and a log id |

Estimated effort 30–45 minutes for the sample set and the error handling together.

---

## 11. The LLM layer (Groq)

### 11.1 Provider decision (DECIDED)

**Groq**, behind one wrapper. Reasons: free tier without a credit card, OpenAI-compatible API, very fast inference, JSON mode. The wrapper isolates the provider so swapping to OpenRouter is a config change.

### 11.2 Models (ASSUMED assignment, VERIFY all limits)

| Job | Model | Reason |
|---|---|---|
| Query to spec, narrative text | GPT-OSS 120B, with llama-3.3-70b-versatile as the alternate | Reportedly the larger daily token cap (about 200K vs about 100K) |
| Value pools, fallback | llama-3.1-8b-instant | Reportedly about 14,400 requests per day, so it survives heavy demo use |
| Last resort | An OpenRouter free model, then offline templates | Demo never dies |

**VERIFY (from third-party write-ups, not Groq's own pages):** free tier is about 30 requests per minute on chat models; llama-3.1-8b-instant about 14,400 requests and 500K tokens per day; llama-3.3-70b-versatile about 1,000 requests and 100K tokens per day; GPT-OSS 120B and 20B about 30 RPM, 1,000 requests per day, 8,000 tokens per minute and 200,000 tokens per day. Limits apply to the **organization**, not each API key. Groq changes its model roster often. Take the exact model IDs and limits from the Groq console.

**Two things I cannot confirm from here:** whether each model supports strict JSON-schema output, and whether it writes decent Urdu. The **bake-off (DECIDED as a task)** answers both.

### 11.3 The bake-off (first hour)

Run the same spec prompt and a "50 Urdu names" prompt on all three candidate models. Score: valid JSON on first try, passes the Pydantic spec model, Urdu names look plausible to a native reader on the team. Pick the winner for spec and for pools. Record the choice in `llm/config.py`. **Also test (v2):** can the model produce a valid `conditioned_by` block (8.4.1) for an unfamiliar domain, and how often does it omit one?

### 11.4 Reliability chain (DECIDED; matches diagram 07)

```
request → cache hit? ──yes──▶ return
             │no
             ▼
   call Groq with next free key
             │
   response ok? ──no (429, timeout, 5xx)──▶ cooldown that key, next key
             │                                    then model fallback: 70B/120B → 8B → OpenRouter
             │yes                                  then offline templates
   spec valid? ──no──▶ one repair retry (send Pydantic error back)
             │yes
             ▼
        cache + return
```

- **Multiple keys (DECIDED):** the wrapper takes a list. A key that returns 429 goes on a cooldown timer (honoring `retry-after`), and the next key is used.
- **Caution (VERIFY):** limits are per organization in the sources I found, so several keys from one account share one limit. Separate accounts have separate limits, but creating accounts only to dodge limits may violate the provider's terms. Check Groq's terms. Rotation is a **backup layer**; the cache is the first line of defense.
- **Offline mode:** if everything fails, a Faker-plus-built-in-template path still produces valid data from the three templates, with less domain flavor.

### 11.5 Caching

- Cache key: `hash(normalized query text + module + template + locale)`.
- Cached: the validated spec and the value pools (disk, JSON).
- Effect: pressing Enter again costs **zero API calls**. We **pre-run every demo query** before presenting (`scripts/precache_demo.py`), so the live demo never depends on the network.

### 11.6 Calls per query (DECIDED: Option B, pools)

Two to four calls total: one spec call, then one to three pool calls (names, merchants or products, cities). Ask for **large pools** (200–300 names, not 20) so different seeds visibly differ. Pool size is bounded by the tokens-per-minute cap, so pool calls are spaced, not fired back to back.

The LLM is **never** called per row or per batch of rows.

### 11.7 Prompt design (PROPOSED)

- **Spec prompt:** give the fixed vocabulary (section 7.4 and 7.5) as the only allowed values, the JSON schema, one worked example (the e-commerce spec), and ask for JSON only. Validate with Pydantic.
- **Pool prompt:** ask for a JSON array of N distinct items for a given locale and domain, no duplicates.
- **Narrative prompt:** give the fact sheet and required facts, the target length and tone, the language, and ask for the body text only.
- **Repair prompt:** the original prompt plus the Pydantic error text plus "return corrected JSON only".

### 11.8 Jev (OPTIONAL, P2)

**What it is (VERIFY):** Jev is a very new model from TypeSafe AI (public launch 15 September 2026). It does not write text. It answers typed questions (choice, score, yes/no) about a text and returns probabilities. Its speed and accuracy numbers are self-reported by the vendor. Signups opened on 20 September with a small starter credit; it is also listed on OpenRouter and Vercel's gateway. It can be swayed by text written to steer it, which matters because uploaded CSV values are user-controlled.

**Where we would use it:** (1) column classification at ingest (choose from our closed generator vocabulary, with a confidence to show in the UI); (2) the query router (module, document type, locale). **Not** for FK detection (code does that exactly) and **not** for writing the spec or any text.

**Decision:** not in the critical path. Groq with a closed enum plus Pydantic validation gets most of the same reliability. Build it behind the same interface only if time remains (about 30–45 minutes, my estimate).

### 11.9 Multilingual and the LLM

The LLM writes pools and narrative text in the requested language. Structured values (dates, currency, numbers) are **never** produced by the LLM; they are formatted by code according to locale (section 13).

---

## 12. Documents

### 12.1 Structured documents: invoices

Structured documents are relational output rendered through a template. An invoice is one order plus its items plus its customer, with amounts computed by code.

#### 12.1.1 Fields

Customer (billed to), seller, invoice ID, date, due date, line items (description, quantity, unit price, amount), subtotal, discount, tax, total.

#### 12.1.2 Amount computation (DECIDED: code, never the LLM)

```
line_amount = quantity * unit_price                 (integer minor units)
subtotal    = Σ line_amount
discount    = per-line or invoice-level, rounded per rule in 8.7
tax         = rate(region) * (subtotal - discount), rounded half up
total       = subtotal - discount + tax
```

The validator re-checks that `total` equals the recomputed value for every invoice.

#### 12.1.3 Region profiles (DECIDED: templated layouts per region)

A region profile bundles: locale for date and number format, currency and symbol placement, tax label (for example GST, VAT, Sales Tax) and default rate, and invoice-number pattern. Adding a region is a small config entry, not new code.

### 12.2 Structured documents: bank statements

#### 12.2.1 Fields

Date, description (merchant), debit, credit, running balance; header with account holder, account number (masked), period, opening and closing balance.

#### 12.2.2 Generation (DECIDED)

- Per account: `opening_balance`, then a dated stream of transactions sorted by date.
- **Credits:** salary on a monthly cadence with small day jitter, plus occasional transfers.
- **Debits:** merchant categories (groceries, utilities, fuel, food, rent) with per-category amount distributions and frequencies. Merchant names come from the LLM pool.
- **Running balance is computed by code** after every transaction. The `running_balance` rule enforces `balance = previous ± amount` and a `min_balance` (default 0, or the overdraft limit): if a debit would breach it, the amount is reduced or the transaction is resampled.

#### 12.2.3 Query-style generation (DECIDED)

"Last 90 days, balance over $500" is parsed by the spec builder into constraints: `{days: 90, min_balance: 500}`. The generator enforces them by construction (the period is the last 90 days before `as_of`, and the balance rule holds at every transaction). The validator confirms it.

### 12.3 Narrative documents (DECIDED: Option B, structured plus narrative)

Types in the MVP (ASSUMED): **assignment, cover letter, report**. Each type is a small template plus a **fact-sheet definition**.

**Pipeline (diagram 06):**

1. **Document spec:** type, topic, language, length, tone, count.
2. **Fact sheet, by code:** for an assignment, for example: student name, roll number, course, submission date, deadline, marks. The core generates these, so names and dates are consistent within a document and across a set (an assignment's date cannot fall after its deadline unless the spec says so).
3. **LLM writes the body,** told to use the given facts.
4. **Fact check, by code:** every required fact must appear in the text. On failure, regenerate up to two times, then fall back to a plain template body.
5. Render through the HTML template to PDF.

### 12.4 What this costs and its limits (DECIDED, be upfront)

- Every narrative document is an LLM call. From the reported Groq limits, that means **tens of documents per run, not thousands**. **Cap: 20 per run** (PROPOSED), stated in the UI.
- **"New variation on every Enter" costs API calls** for narrative documents (structured ones are free). A new seed changes the facts, and the LLM writes new text. The **seed reproduces the facts, not the wording.** A **saved run stores the generated text**, so a saved run is exactly reproducible.
- **TSTR/TRTS does not apply to prose.** The narrative scorecard shows fact consistency, length and language checks, and near-duplicate diversity across the set. We do not invent a utility score for text.
- Urdu quality depends on the model, tested in the bake-off.

### 12.5 Rendering (DECIDED: Option B, HTML to PDF with Playwright)

- Jinja2 templates produce HTML. **The same templates drive the live preview in the UI**, so each layout is written once.
- **Playwright with headless Chromium** renders the PDF. The browser does text shaping, RTL and fonts correctly, which is why we chose it over ReportLab.
- **Reuse one browser instance** and close it when idle. Expect about a second per PDF (my estimate); fine for tens to low hundreds. If bulk speed becomes a problem, an English-only fallback to ReportLab is acceptable (not planned).
- Bulk output is a **zip** of PDFs.
- WeasyPrint was rejected (needs GTK/Pango libraries that are painful on Windows).
- DOCX is cut.

### 12.6 Documents from data (P1)

Upload a line-items or transactions CSV; the fitter learns merchant, amount and credit/debit patterns (marginals plus copula, same fitter). The same renderer produces documents. Learning layout from an uploaded document is not built.

### 12.7 Invoices generated from the relational output (P1)

**The idea:** the three modules become one pipeline. Generate the e-commerce database, click **Generate invoices**, and get PDFs whose customer, line items, quantities, tax and totals match the tables row for row.

**How:**

1. `POST /runs/{id}/invoices` selects orders (`pick`: latest, random by seed, or specific `order_ids`; default 10; **PDF cap 50** per request).
2. Each invoice is assembled from `orders`, `customers`, `order_items` and `products`. The invoice number derives from the order ID (for example `INV-000123`, PROPOSED). Amounts are **read from the tables**, not recomputed by different logic.
3. A tier 2 check, "invoice equals its order", asserts the invoice total equals `orders.total` for every invoice generated (9.4.4).
4. The full set is also exported without PDFs as `invoices.csv` plus `invoice_lines.csv` for **all** orders, which is cheap.

**Checkable proof for a judge:** open an invoice PDF, look up the same order ID in the orders CSV, and the numbers are identical.

**Limits:** Chromium renders roughly 0.3–1 second per PDF (my estimate), so 20,000 PDFs is not possible; hence the cap of 50 plus the CSV for everything else. The same pattern gives a bank statement for one account from the banking template (stretch). Depends on the relational engine, the e-commerce template's tax and discount columns, and the invoice template, so it is P1. Estimated effort 45–60 minutes.

---

## 13. Multilingual (DECIDED approach, Urdu is a stretch)

**English is the main path.** Other languages must not complicate the architecture.

| Concern | Approach |
|---|---|
| Names, addresses, merchants, descriptions | LLM pools in the requested language, sampled by code |
| Dates, numbers, currency | Formatted by code from the locale, never by the LLM. Babel is suggested for dates (PROPOSED); PKR lakh or western grouping is a small hand-written function (section 8.13) |
| Faker | Locale-specific providers where they exist |
| Unicode | UTF-8 everywhere; CSV exports written with a BOM option so spreadsheet apps show Urdu and Arabic correctly (PROPOSED) |
| RTL documents | Solved by the browser render path (Playwright); templates set `dir="rtl"` and an appropriate font |
| Urdu PDF | Stretch goal. Naskh-style fonts render acceptably; Nastaliq needs extra work and is not promised |
| Multilingual DOCX | Cut |

**Risk (VERIFY):** as far as I know, Llama 3.x officially lists Hindi but not Urdu or Arabic. Quality must be tested in the bake-off, not assumed.

---

## 14. Evaluation and the per-run scorecard

**DECIDED:** the hackathon judging emphasises TSTR/TRTS, fidelity and utility, and the platform **shows the scores of every generation**.

### 14.1 The scorecard (DECIDED)

Each Enter produces a **run record** with the seed, timestamp, row counts, four pillar scores and an overall score. The UI shows the current run's scorecard and a **run history table** (run 1, run 2, run 3, each with seed and scores). Slow scores show a spinner and fill in when finished.

### 14.2 Pillars

| Pillar | Contents | Reference badge |
|---|---|---|
| **Validity** | Share of structural and rule checks passed (FK, PK, sums, dates, ranges) | `structural` |
| **Fidelity** | Per-column KS and TVD plus correlation-matrix difference, converted to 0–100 | `vs. real hold-out` |
| **Utility** | TSTR and TRTS against a real-on-real baseline | `vs. real hold-out` |
| **Privacy** | Exact-match rate and nearest-neighbour distance ratio | `vs. real train` |

Two further panels are shown but **not scored**: **Behavioural coherence** (9.4.1, badge `vs. spec`) and, in data mode, **Naive baseline** (14.10).

### 14.3 Fidelity metrics (build)

- **Numeric columns:** KS statistic `D` (0 to 1), column score `100 × (1 − D)`.
- **Categorical columns:** total variation distance `TVD = 0.5 × Σ|p − q|`, score `100 × (1 − TVD)`.
- **Correlation:** mean absolute difference of **Spearman** correlations over numeric pairs, `Δ`, score `100 × (1 − Δ)`, clipped at 0.
- **Fidelity score:** mean of the column-shape score and the correlation score (PROPOSED equal weighting).

### 14.4 Utility: TSTR and TRTS (build)

**Protocol:** the real data is already split 80/20 (section 10.3).

- **Target column:** user-chosen, otherwise auto-pick a categorical column with 2–10 classes that is not an ID or PII; if none exists, a numeric column for regression (PROPOSED).
- **Preprocessing:** drop ID, PII and free-text columns; one-hot categoricals with cardinality up to 20, ordinal encoding above that; sample at most 20k training rows.
- **Model:** RandomForest, `n_estimators=100`, `max_depth≤12`, `n_jobs=1` (regression uses the regressor variant).
- **TRTR baseline:** train on real-train, test on real hold-out.
- **TSTR:** train on synthetic, test on the real hold-out.
- **TRTS:** train on real-train, test on the synthetic data.
- **Metric:** macro-F1 for classification, R² clipped to [0, 1] for regression.
- **Reported:** each as a **ratio to the TRTR baseline**. **Utility score** = `100 × min(1, mean(TSTR ratio, TRTS ratio))`.
- Data mode only. It runs in seconds on 8 GB.

### 14.5 Privacy (build two cheap checks)

- **Exact-match rate:** fraction of synthetic rows equal to a real train row on the modeled columns.
- **Nearest-neighbour distance ratio:** on at most 5k sampled rows per side, standardise numeric columns and one-hot categoricals. For each synthetic row, find the distance to the nearest real *train* row. For each real *hold-out* row, find the distance to the nearest real *train* row. Report `ratio = median(d_synthetic) / median(d_holdout)`.
- **Interpretation:** a ratio well below 1 means synthetic rows sit closer to the training rows than genuinely unseen real rows do, which is a **memorisation warning** (flag threshold about 0.8, PROPOSED).
- **Privacy score (PROPOSED):** `100 × min(1, ratio) × (1 − exact_match_rate)`.
- These are **heuristics, not proofs**. Read TSTR and privacy together: a high TSTR ratio with a low privacy ratio means near-copies.

### 14.6 Overall score (PROPOSED weights, visible in the UI)

`overall = 0.25 × validity + 0.25 × fidelity + 0.30 × utility + 0.20 × privacy`

Weights are shown in the UI so nobody can say the number was tuned to look good. A validity below 100% shows a red flag regardless of the total.

### 14.7 Query mode scoring (DECIDED: parked)

We parked the query-mode scoring layers (fidelity to the spec, planted-signal recovery, cross-run diversity). **Kept:** basic validity (the same relational validator, free). If time remains, the cheap extras are: KS/TVD against the spec's declared distributions labelled `vs. spec`, and a cross-run diversity check (row overlap near zero, KS between runs small) that directly proves "different data every Enter". We do not show a made-up "realism score" in query mode, and we do not show privacy metrics there ("privacy by construction, no real data used").

Behavioural coherence (9.4.1) is the one extra we show in query mode: group ordering, per-group caps and rate tolerances, all measured against the spec and labelled as such. It is not folded into any score.

### 14.8 Metrics we cut (DECIDED) and why

| Cut | Reason |
|---|---|
| Wasserstein, Jensen–Shannon, variance difference | Redundant with KS and TVD for the score. **Optional P2:** each is a one-line scipy call, shown only in a details drawer and never in the overall score (about 20 minutes) |
| Chi-square | p-values become meaningless at large sample sizes |
| Mutual information | Redundant with the correlation matrix; awkward for mixed types |
| Membership inference, re-identification, attribute disclosure | Need shadow models or quasi-identifier assumptions; a research project |

### 14.9 Documents scoring

Structured documents: reconciliation checks (totals, balances) are part of validity. Narrative documents: fact consistency, length and language checks, and near-duplicate diversity, labelled as such.

### 14.10 Naive-baseline comparison (P1, data mode)

**Question it answers:** "how do we know your score means anything?" We run the **same scorecard** on a Faker-style baseline where every column is sampled **independently** from the real training data's marginals (same row count, IDs regenerated, no learned rules), and show the two side by side.

| Metric | Expected result |
|---|---|
| Per-column shape (KS, TVD) | About equal, because the marginals match by construction. We do not hide this. |
| Correlation difference | Ours clearly better |
| TSTR and TRTS ratio | Ours clearly better, since independent columns destroy feature-target relationships |
| Rule validity (relational) | Ours holds mined rules; the baseline violates them |

**Honesty:** if the real data has weak correlations the gap will be small, and we report it as it is. Query mode has no real reference, so there is no baseline there. Estimated effort 45 minutes, because it reuses the scorecard as a function.

---

## 15. Storage, runs and export

### 15.1 Run lifecycle (DECIDED)

| Action | Effect |
|---|---|
| **Generate** | Creates a run in an in-memory cache (last 10 runs, older unsaved runs are evicted quietly). Preview, structural validity and seed are available at once. |
| **Save** | Promotes the run to `runs/<run_id>/` and adds it to persistent history. |
| **Download** | Streams the export **without requiring a Save**. |

A run you liked can always be reproduced by re-entering its seed (the spec is cached by query).

### 15.2 On-disk layout for a saved run (PROPOSED)

```
runs/<run_id>/
  spec.json          # the validated spec (query mode) or learned spec (data mode)
  pools.json         # the LLM pools
  seed.txt           # master seed
  tables/<name>.parquet or .csv
  scores.json
  documents/         # narrative text and rendered PDFs, if any
  meta.json          # module, mode, timestamps, row counts
  checksums.json     # SHA-256 of every export file (section 15.5)
```

`spec.json` plus `pools.json` plus the seed is the recipe.

### 15.3 Exports (DECIDED)

| Format | How |
|---|---|
| **CSV** | One file per table, zipped for multi-table runs |
| **JSON** | One array of records per table (or one object keyed by table) |
| **SQL dump (PostgreSQL, ASSUMED dialect)** | We emit `CREATE TABLE` statements with types, PKs and FKs, then `INSERT` statements, ordered parents-first so the dump loads without constraint errors. An in-memory SQLite database is used as a quick loading self-test. |
| **PDF** | Individual PDFs in a zip |

Money is converted from minor units to decimal at export. PDF and preview use the same templates.

### 15.4 What we do not build

Cloud storage, sharing links, versioned datasets, DOCX.

### 15.5 Checksums: the reproducibility proof (P0)

Each CSV, JSON and SQL export is hashed with **SHA-256** over its bytes. The hashes appear next to the seed in the UI, in `POST /generate` responses and in `checksums.json`. A **Replay** button re-runs the same spec and seed and shows "hash matches".

**What must hold for hashes to be stable (PROPOSED):**

- A canonical writer: fixed column order, rows sorted by primary key, `\n` line endings, no index column, UTF-8 (the BOM option changes the bytes, so the hash covers the chosen option).
- Money exported as fixed-decimal strings converted from integer minor units, never floats.
- JSON with sorted keys and fixed separators; SQL in a stable table and row order.
- No timestamps inside exported files. `generated_at` lives only in `meta.json` and is excluded.
- **PDFs are excluded** (they embed timestamps and font data). For documents we hash the HTML source instead.
- The spec and pools must come from the cache (11.5); a fresh LLM call would produce a different spec.
- Claim scope: **same spec, same seed, same software versions.** NumPy can change random streams across major versions.

`tests/test_repro_hash.py` runs each demo query twice and compares hashes. Estimated effort about 20 minutes.

---

## 16. API

All endpoints are under `/api`. JSON unless noted. This is the contract track C can mock from minute one.

### 16.1 Endpoints

| Method and path | Purpose |
|---|---|
| `POST /generate` | Every Enter click. Returns `run_id`, `seed`, `preview`, `validity`, `status` |
| `POST /upload` | Multipart, 1–N CSVs. Returns `upload_id` and detected schema |
| `PUT /uploads/{id}/schema` | User confirms or edits detected PK, FK and generators |
| `POST /spec/interpret` | Show or re-interpret the query's spec (cached) |
| `GET /runs/{id}/scores` | Poll until done |
| `GET /runs/{id}/preview` | Page through tables (`table`, `offset`, `limit`) |
| `GET /runs/{id}/documents/{doc}` | Rendered HTML or PDF (`format`) |
| `POST /runs/{id}/save` | Promote a temporary run |
| `GET /runs` | Run history |
| `GET /runs/{id}/export` | Download (`format` = csv, json, sql, pdf; optional `table`, `dialect`) |
| `DELETE /runs/{id}` | Discard a run |
| `GET /templates` | Built-in templates |
| `GET /health` | LLM key status and cooldowns, cache size (useful on demo day) |
| `POST /spec/validate` | Validate an edited spec without generating: Pydantic plus feasibility, errors with field paths |
| `POST /runs/{id}/corrupt` | Demo only: create a derived run with deliberate defects (`kind`, `n`) and return the validator's findings |
| `POST /runs/{id}/invoices` | Generate invoices from a relational run (`pick`, `count`, `order_ids`), returns a zip and the reconciliation result |
| `GET /runs/{id}/checksums` | SHA-256 of each export file |
| `GET /uploads/{id}/schema` | Detected schema for the schema view (10.2.1) |
| `GET /sample-data` | Lists bundled sample datasets; `POST /upload?sample=<name>` loads one |

The first six plus `save`, `export`, `spec/validate` and `checksums` are the P0 set; `corrupt` and `sample-data` are P0 for the demo; `invoices` and the schema `GET` are P1; the rest are polish.

### 16.2 `POST /generate` (PROPOSED shape)

Request:

```json
{
  "module": "relational",
  "mode": "query",
  "query": "Generate an e-commerce database with 5,000 customers, 20,000 orders and order items.",
  "upload_id": null,
  "template": "ecommerce",
  "n_rows": null,
  "seed": null,
  "locale": "en_PK",
  "currency": "PKR",
  "privacy": {"mask": ["phone"], "hash": [], "noise": {}},
  "null_rate": 0.02,
  "outlier_rate": 0.005,
  "doc_type": null,
  "doc_count": null,
  "spec": null
}
```

Response:

```json
{
  "run_id": "r_8f3a…",
  "seed": 918273645,
  "status": "generated",
  "preview": {"tables": {"customers": {"columns": ["customer_id", "…"], "rows": [["1", "…"]], "total_rows": 5000}}},
  "validity": {"passed": 42, "total": 42, "score": 100, "failed_checks": []},
  "spec_source": "cache",
  "feasibility": {"ok": true, "errors": [], "warnings": []},
  "checksums": {"customers.csv": "sha256:9c1f…"},
  "warnings": [],
  "unsupported": []
}
```

`preview` holds only the first N rows per table (for example 50). `seed` is always returned. `status` is `generated` (structural checks done, scores pending) or `failed` (a hard validation failure).

### 16.3 `GET /runs/{id}/scores` (PROPOSED shape)

```json
{
  "status": "partial",
  "validity": {"score": 100, "reference": "structural"},
  "fidelity": {"score": 91, "columns": {"income": {"ks": 0.04, "score": 96}}, "correlation": {"delta": 0.07, "score": 93}, "reference": "vs. real hold-out"},
  "utility": {"target": "segment", "trtr": 0.81, "tstr_ratio": 0.93, "trts_ratio": 0.95, "score": 94, "reference": "vs. real hold-out"},
  "privacy": {"exact_match_rate": 0.0, "nn_ratio": 1.04, "flag": false, "score": 100, "reference": "vs. real train"},
  "coherence": {"reference": "vs. spec", "checks": [{"rule": "group_order", "column": "orders.total", "passed": true}], "passed": 6, "total": 6},
  "baseline": {"reference": "naive independent columns", "fidelity": 88, "correlation": 41, "utility": 52, "rules_valid": 0.62},
  "overall": 96,
  "weights": {"validity": 0.25, "fidelity": 0.25, "utility": 0.30, "privacy": 0.20}
}
```

`status` moves from `pending` to `partial` to `done`. The UI shows a spinner for any pillar not yet present.

### 16.4 `POST /upload` response (PROPOSED)

```json
{
  "upload_id": "u_31c…",
  "tables": [{
    "name": "customers",
    "rows": 12000,
    "columns": [{"name": "email", "dtype": "string", "generator": "email", "confidence": 0.98, "source": "llm+verified"}],
    "pk": "customer_id",
    "fks": []
  }],
  "warnings": []
}
```

### 16.5 Errors

`400` invalid request; `413` upload too large; `422` spec validation failed after repair (body includes the Pydantic error and the `unsupported` list), or code `infeasible` when the feasibility check fails (body includes `errors[]` with a plain-language message and suggested fix each); `503` LLM chain exhausted and offline fallback also unavailable. Every error body has `code` and a human message.

### 16.6 External APIs required

**Groq chat completions (OpenAI-compatible)** is the only mandatory external API. OpenRouter (fallback) and Jev (optional) are optional. No other external service is needed.

---

## 17. Frontend (single page)

### 17.1 Stack decision (ASSUMED, partly OPEN)

You said "I guess we would use React". **OPEN:** confirm who builds the UI and whether they have shipped a small React app recently. **Rule:** React plus Vite plus Tailwind if yes. Otherwise **one plain HTML page served by FastAPI, with Alpine.js and Tailwind from a CDN**, which still meets every requirement in the deck. Decide by **hour 3** at the latest.

**If React:** Vite plus React plus Tailwind, no Next.js (no server rendering or second server needed), no state library (plain `useState`), Vite proxy to FastAPI in development, and `vite build` once for the demo so **FastAPI serves the static files** (one process, one port, no CORS). Estimate: 2.5–3 hours polished, against about 2 hours for the plain-HTML option (my estimates).

### 17.2 Layout (one page, matches the deck's "one workspace, three data types")

- **Left sidebar:** Tabular, Relational, Documents. Clicking swaps the workspace contents; there are no routes and no reloads.
- **Top of workspace:** a **Query / Upload** toggle, with a text box or a file drop zone. For relational upload the drop zone accepts several CSVs, then shows detected PKs, FKs and mined rules for the user to confirm or edit.
- **Right configuration panel:** row count, seed (blank means random each run), locale and currency, privacy rules, null and outlier rates, a **Generate** button and an **Export** button (plus Save).
- **Center preview canvas:** a data table for Tabular; a table switcher with a small FK diagram for Relational; a rendered invoice or statement (or narrative document) for Documents, from the same HTML templates that produce the PDFs.
- **Bottom scorecard strip:** four pillar scores plus the overall score for the current run, and a **run-history table** (run, seed, scores). Slow scores show a spinner and fill in by polling.

### 17.3 Behaviour details

- Pressing Enter in the query box triggers Generate.
- The seed used is shown next to the run and can be copied into the seed field to replay it.
- A "re-interpret query" button calls `POST /spec/interpret` with a force flag.
- Each score chip shows its reference badge as a small label.
- Narrative documents show a visible cap notice.
- If the LLM chain fell back to offline templates, a small banner says so.

**v2 additions to the workspace (PROPOSED):**

- **Spec panel:** collapsible JSON editor with **Run from spec** and **Reset to LLM version**; Pydantic errors shown inline (7.9).
- **Feasibility box:** red message with the suggested fix when a request is impossible; warnings beside the preview (7.8).
- **Corrupt button:** "Corrupt this dataset" creates a labelled derived run and shows failing checks in red with row IDs (9.6).
- **Checksum line** beside the seed, with **Replay and verify** (15.5).
- **Behavioural coherence panel** in every relational run; **Naive baseline** table in data mode (9.4.1, 14.10).
- **Schema view** with dropdown corrections after upload (10.2.1) and a **Try with sample data** button (10.11).
- **Generate invoices** button on relational runs, with the 50-PDF cap stated (12.7).
- Money and dates in the UI follow the locale, including the lakh or western grouping option (8.13).

---

## 18. Repository structure and module boundaries (PROPOSED)

```
hackdata/
  backend/
    app/main.py, app/routes/*.py        # FastAPI (track C)
    core/spec.py                        # Pydantic models (track A owns)
    core/seeds.py, core/generators/, core/relational.py,
    core/rules.py, core/validator.py, core/edge.py, core/privacy.py   # track A
    core/conditional.py, core/corrupt.py, core/seasonality.py          # track A (v2)
    core/feasibility.py                                                # track B (v2)
    locale_pk/ (phones, cities, names.json, pkr_format.py, national_id.py)   # track A (v2)
    llm/client.py, llm/config.py, llm/prompts.py, llm/cache.py, llm/offline.py   # track A
    data_mode/infer.py, fit_copula.py, structure.py, mining.py        # track B
    eval/fidelity.py, utility.py, privacy.py, relational.py, score.py, baseline.py  # track B
    docs/templates/*.html.j2, docs/render.py, docs/invoice.py,
    docs/statement.py, docs/narrative.py, docs/from_orders.py          # track C
    export/csv_json.py, export/sql_dump.py, export/pdf_zip.py, export/checksums.py   # track C
    store/runs.py                                                     # track C
    contracts/spec.schema.json, scores.schema.json, api.md, engine_interface.md
    tests/ (test_validator_negative.py, test_repro_hash.py, test_feasibility.py, test_conditional.py)
  frontend/                             # track C
  data/sample/  data/calendars/pk.json   # bundled demo CSVs and the event calendar
  runs/    cache/                       # runtime, gitignored
  scripts/precache_demo.py, smoke_demo.py
```

**Rule:** each person works in their own directories and requests changes to others' code instead of editing it. One shared repo, small commits, and a **smoke script** (`scripts/smoke_demo.py`) that runs the full demo path and that anyone can run before pushing.

---

## 19. Libraries (existing capability we reuse)

| Need | Library |
|---|---|
| Data | pandas, numpy |
| Statistics | scipy (`ks_2samp`, `norm`, Spearman), scikit-learn (RandomForest, NearestNeighbors, StandardScaler) |
| Fake but realistic values | Faker (locale providers) |
| Spec validation | Pydantic |
| Safe expressions | simpleeval |
| Web | FastAPI, uvicorn, python-multipart |
| LLM | httpx or the OpenAI-compatible SDK pointed at Groq |
| Documents | Jinja2, Playwright (Chromium) |
| Locale formatting | Babel for dates (PROPOSED); PKR grouping is hand-written |
| Frontend | Vite, React, Tailwind (or Alpine.js plus Tailwind CDN) |

**Not used (DECIDED):** SDV (later, separate venv), SDMetrics (our KS, TVD and correlation are a few lines each), CTGAN, TVAE, any local LLM.

**On the commercial tools you listed** (Tonic.ai, Gretel, MOSTLY AI, DataCebo): they are hosted products or SDV's commercial layer. They are not components we can embed in a free 10-hour build. We mention them only as prior art.

---

## 20. Team split, build order and checkpoints

### 20.1 Effort estimate and the honest budget

Three people times 10 hours is **30 nominal person-hours**. After integration, debugging, and demo rehearsal, about **20 productive hours** is realistic (my estimate, roughly one third overhead).

| Bucket | Hours (best case) |
|---|---|
| v1 scope without narrative documents | about 13 |
| v2 P0 additions (rows 1–8 in 0.4) | about 5.5 |
| **P0 total** | **about 18.5** |
| v2 P1 additions (rows 9–13, plus P1 locale items) | about 5 |
| Narrative documents (moved to P2) | about 2 |

P0 alone nearly fills the realistic 20 hours. **P1 cannot all fit.** The rule:

- **Hour-3 gate:** if the engine or data mode is behind at checkpoint 1, every P1 item is dropped and the P0 items are finished properly.
- **Otherwise** P1 items are taken in the order in 4.2, and the next one is started only if the previous one shipped.
- **Free-up list** if we are still short: Jev, Urdu PDF polish, extras drawer, narrative documents (already P2).
- Estimates are optimistic. The build-order and demo prep, not the coding, decide whether we ship.

### 20.2 Tracks (ASSUMED, assign by strengths: OPEN)

| Track | Owns | P0 hours | P1 hours |
|---|---|---|---|
| **A: Engine** | Spec models, generators, seeding, relational engine, three-tier validator, LLM wrapper and query-to-spec, SQL export, **conditional relationships**, **corrupt and negative tests**, **Pakistan generators** (phone, cities, names, ID pattern) | about 7.5 | seasonality 0.6 |
| **B: Data and evaluation** | Type and key inference, copula, FK detection, rule mining, all scoring, **feasibility check**, **sample dataset** | about 6 | baseline 0.75, data-mode conditioning 1, schema backend 0.5 |
| **C: Product** | FastAPI endpoints, UI, run storage, document templates and Playwright renderer, **spec panel**, **checksums**, **readable errors**, PKR and date formatting | about 5.6 | invoices from orders 1, schema view UI 1 |

Track A is the critical path and the most loaded. **If A is behind at hour 3, hand the Pakistan generators to B.** Narrative documents float to whoever frees up first, but only after all P0 items ship. Claude Code helps most on track C boilerplate, so the gap is smaller than the table suggests, but no speed-up is promised.

### 20.3 First 45 minutes: contracts before code (DECIDED principle)

All three commit four files to the repo. Every Claude Code session reads the same ones:

1. **Spec schema** (Pydantic models). Track A writes it; B and C consume it.
2. **Engine interface:** generation returns `dict[str, DataFrame]` plus metadata; the fitter interface `fit(df)` and `sample(n, seed)`.
3. **Scores JSON format** (section 16.3), so C builds the scorecard UI against a mock while B builds the metrics.
4. **API endpoints and payloads** (section 16). C mocks them from minute one.

v2: the spec schema also freezes the `conditioned_by` fields, the new rule types (`group_order`, `bound_by_group`, `share_within`), the `seasonality` block and the feasibility result format `{ok, errors[], warnings[]}`, because tracks A, B and C all depend on them.

### 20.4 Indicative timeline (PROPOSED)

| Hour | A | B | C |
|---|---|---|---|
| 0–0.75 | Contracts (incl. v2 fields), repo skeleton | Contracts | Contracts, mock API |
| 0.75–1 | **Groq bake-off (all)**, now including a `conditioned_by` test | | |
| 1–3 | Spec validation, seeds, generators, relational engine, `conditioned_by` skeleton | Type/PK/FK inference, copula, **feasibility check** | UI shell, upload, preview, invoice template, global error handler |
| **3** | **Checkpoint 1: full demo path end to end. P1 gate decision.** | | |
| 3–5 | Three-tier validator, LLM chain, query-to-spec, e-commerce template with segments, negative tests | Fitter integration, scoring (fidelity, TSTR/TRTS, privacy), **sample dataset generation** | Scorecard UI, run cache, exports with checksums, **spec panel** |
| 5–6 | Corrupt endpoint, Pakistan generators, other templates, edge cases | Rule mining, relational data mode | PDF pipeline, Save and history, corrupt button UI, PKR formatting |
| **6** | **Checkpoint 2: full end-to-end run** | | |
| 6–8 | P1 in rank order: invoices from orders (A with C), naive baseline (B), schema view (B with C), seasonality (A), data-mode conditioning (B) | | |
| 8–10 | Integration fixes, `precache_demo.py`, demo rehearsal, buffer | | |

The 10 hours have **no slack** as budgeted. Anything that slips pushes P1 items out, then P2.

### 20.5 Demo script (PROPOSED, v2)

1. Query mode, relational: "Pakistani e-commerce database with 5,000 customers, 20,000 orders, products and order items". Show the preview, the FK diagram, validity 100%, and the **behavioural coherence** panel (student orders smaller, premium customers order more often).
2. Press Enter twice more: three different datasets, three seeds, three scorecards in run history.
3. Type a seed to reproduce a run and show the **matching checksums**.
4. Type an impossible request (10 customers, exactly 20 orders each, 100 orders) and show the **feasibility message**.
5. Press **Corrupt this dataset**: the validator turns red and names the rows.
6. Open the **spec panel**, edit one weight, run from spec with no LLM call.
7. **Generate invoices** for 10 orders, open one PDF, and match its numbers to the orders CSV.
8. Data mode: **Try with sample data** (or upload a judge's file); show the detected schema, the scorecard with TSTR/TRTS and privacy, and the **naive-baseline comparison**.
9. Export SQL and load it into PostgreSQL.

All demo queries are pre-cached, so the demo survives an API outage.

---

## 21. Risks and mitigations

| Risk | Mitigation |
|---|---|
| **Integration** (three people, three assumptions) | Contracts in the first 45 minutes; checkpoints at hours 3 and 6; shared smoke script |
| **Query to spec reliability** (the last 20% is retries and repair) | Closed vocabulary, Pydantic, one repair retry, hand-verified templates, cache, offline path; pre-cache demo queries |
| **Groq rate limits or model changes** | Cache first, key list with cooldown, model fallback, OpenRouter, offline templates |
| **Groq Urdu or JSON quality unknown** | Bake-off in hour one; Urdu is a stretch goal |
| **Copula takes too long** | 1.5-hour time-box; fall back to marginals plus rank correlation nudge |
| **Playwright install or memory** | One Chromium instance; pre-install; cap document counts |
| **8 GB RAM** | Row caps, sampled scoring, `n_jobs=1` |
| **Overclaiming to judges** | Reference badges; the wording in section 22 |
| **LLM domain knowledge wrong** | Flagged "unverified domain assumptions"; hand-verified templates for the demo domains |
| **Scope creep** | P0/P1/P2 tiers, the cut list, and the hour-3 P1 gate (20.1) |
| **Conditional structure from the LLM is unreliable in unfamiliar domains** | Hand-written for the demo template; optional block with unconditional fallback; flagged "unverified"; tested in the bake-off |
| **Naive baseline gap is small on weakly correlated data** | Report honestly; demo on the sample set with planted signal and say so |
| **Hash mismatch across machines or library versions** | Claim scope "same spec, seed and software versions"; exclude PDFs; hash from cached specs; pin versions |
| **Invoice PDF speed** | Cap 50 per request; everything else as CSV |
| **Synthetic ID pattern collides with a real one** | Reserved fake marker, column flagged synthetic and masked by default |
| **Corrupt button misread as real output** | Derived run, labelled "CORRUPTED (demo only)", original untouched |
| **Sample data is team-generated, so scores look flattering** | Labelled demo data; do not present as realism proof; try to add one real public CSV |
| **P0 total nearly fills the realistic budget** | Track A hand-off rule, hour-3 gate, narrative documents demoted

---

## 22. Claims we can and cannot make (pitch wording, PROPOSED)

**Can say:**
- "Relational integrity is guaranteed by construction: PKs, FKs, cardinalities and totals cannot be violated, and we re-check every run."
- "Every rule we encode holds in every row, and in data mode we mine rules from your data and enforce them."
- "The LLM never generates a row or a number; it writes the spec and text, and code does everything that must reconcile."
- "Every run gets its own scorecard, and each score says what it was measured against."
- "Different data every run, exactly reproducible from the seed plus the saved spec."
- "Unlimited variations."
- "Impossible requests are rejected before generation, with an explanation and a suggested fix."
- "Every validator check is tested against deliberately broken data, and you can watch it catch the defects."
- "Same spec and seed give byte-identical CSV, JSON and SQL exports; verify with the checksums" (same software versions).
- "Order behaviour depends on customer segment in query mode, and the coherence panel checks it against the spec."
- "On the sample data our scorecard clearly separates learned data from independent-column data" (only if the baseline result supports it).
- "Data mode never copies a real row; identifying columns are regenerated."

**Should not say:**
- "Never touches real records" for data mode.
- "Differential privacy" (we do Laplace noise without a formal guarantee).
- "Infinite" variations.
- "Realistic" as a measured claim in query mode (there is no real reference).
- "Guaranteed sensible" beyond the rules we encoded.
- Any Groq or Jev number as verified without checking the vendor's own pages.
- "Behaviourally realistic" as a measured claim: coherence is checked against our spec, not against reality.
- "Byte-identical PDFs" (they embed timestamps), or hash equality across different software versions.
- Any Eid date, GST rate or phone-prefix list as verified before it has been checked.
- That generated national-ID-like numbers are real or validated numbers.

---

## 23. Later, production-grade (not built)

Real differential privacy with budget accounting; SDV or deep generative models for richer fidelity and multi-table learning; conditional child fitting; attack-based privacy metrics (membership inference, attribute disclosure); DOCX and a full multilingual document stack (Nastaliq); authentication, multi-user workspaces and cloud storage; a versioned dataset registry; streaming generation for millions of rows; schema-file ingestion; learning document layout from samples.

---

## 24. Decision log and open items

### 24.1 Decision log

| # | Decision | Status |
|---|---|---|
| 1 | Build all three modules, each with query and data mode | DECIDED |
| 2 | One shared core, three thin modules | DECIDED |
| 3 | Spec: fixed vocabulary plus `simpleeval`, Pydantic-validated, one repair retry | DECIDED |
| 4 | Data-mode fitting: marginals plus Gaussian copula, single table, 1.5-hour time-box | DECIDED |
| 5 | SDV not used now; interface allows adding it later in a separate venv | DECIDED |
| 6 | Relational data mode: per-table fits plus FK cardinality plus mined rules (≥ 99%) | DECIDED |
| 7 | LLM does pools and text; code does every row and number | DECIDED |
| 8 | LLM calls: one spec call plus a few pool calls, cached per query | DECIDED |
| 9 | Groq is the provider, with a key list, cooldown, fallback chain and offline path | DECIDED (limits VERIFY) |
| 10 | Documents: structured (invoice, statement) plus narrative (assignment, letter, report) | DECIDED |
| 11 | PDF rendering via Jinja and Playwright | DECIDED |
| 12 | Scorecard per run: validity, fidelity, utility (TSTR/TRTS), privacy; 80/20 real split | DECIDED |
| 13 | Query-mode scoring parked, except validity | DECIDED |
| 14 | Runs temporary until Save; Download works without saving | DECIDED |
| 15 | Three people plus Claude Code, strict MVP | DECIDED |
| 16 | Values change per Enter, structure fixed | ASSUMED |
| 17 | SQL dump targets PostgreSQL | ASSUMED |
| 18 | Templates: e-commerce, banking, invoicing | ASSUMED |
| 19 | Caps: 100k rows per table, 20 MB upload, 20 narrative documents per run | ASSUMED |
| 20 | Jev optional, P2 | ASSUMED |
| 21 | Privacy wording: Laplace noise, no formal DP guarantee | ASSUMED |
| 22 | Overall score weights 25/25/30/20 | PROPOSED |
| 23 | Track roles A/B/C | ASSUMED |
| 24 | Feasibility check before generation | DECIDED (tier P0, est. PROPOSED) |
| 25 | Three-tier validation, negative test suite and corrupt-dataset demo button | DECIDED (P0) |
| 26 | Conditional relationships: query mode P0, data-mode group-wise P1 | DECIDED (tiers PROPOSED) |
| 27 | Reproducibility checksums beside the seed | DECIDED (P0) |
| 28 | Editable spec panel and run-from-spec | DECIDED (P0) |
| 29 | Bundled sample dataset and readable upload errors | DECIDED (P0) |
| 30 | Pakistan locale profile; lakh grouping as default option | DECIDED; default ASSUMED |
| 31 | Naive-baseline comparison, data mode only | DECIDED (P1) |
| 32 | Detected-schema view with dropdown corrections | DECIDED (P1) |
| 33 | Seasonality in dates | DECIDED (P1) |
| 34 | Invoices from generated orders, 50-PDF cap plus CSV for all | DECIDED (P1) |
| 35 | Narrative documents demoted from P1 to P2 | ASSUMED |
| 36 | Extra metrics (Wasserstein, JS, variance) in a details drawer only | DECIDED (P2) |
| 37 | Not adopted: chunked CSV reading, general repair loop, English-sentence rules, repo rename | DECIDED |

### 24.2 Open items

1. **Who takes which track** (needs each person's strengths).
2. **React or plain HTML:** depends on who builds the UI and whether they have shipped React recently. Decide by hour 3.
3. **The Groq bake-off result** (JSON reliability, Urdu quality, final model IDs).
4. **Whether multiple Groq keys come from separate accounts** and whether that is acceptable under Groq's terms.
5. **Confirm the ASSUMED items** in the decision log (16 to 21, 23), especially the PostgreSQL dialect and the three templates.
6. **A real sample CSV for the demo:** decides which column types the copula must handle best (customers, transactions, or something else).
7. **How the judges test data mode:** whether they bring their own CSV. If yes, most evaluation polish goes to data mode.
8. **Lakh or western grouping** as the default PKR display.
9. **Eid, Ramadan and event dates** for 2023–2027, the current GST rate, and the valid mobile prefix list: all need checking (VERIFY).
10. **Narrative documents demoted to P2:** confirm, or say what else should be dropped instead.
11. **Sample data:** is team-generated demo data acceptable for the demo, or do we also find a real public CSV?
12. **Who owns the Pakistan generators** if track A is behind at hour 3 (default: B).

---

*End of document. The visual companion is `architecture.html` (eight diagrams).*
