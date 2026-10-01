# HackDataV2 Synthetic Data Platform — Product Requirements Document (PRD)

Version 1.0 · 2026-09-29 · Companion to `TRD.md` (how we build it) and `HackDataV2_Architecture.md` (why we decided it)

**Status labels used below** (same as the architecture record): **DECIDED** you confirmed it · **ASSUMED** I chose it for you, veto freely · **PROPOSED** a default for a detail not yet discussed · **OPEN** not decided · **VERIFY** an outside fact to check before relying on it.

---

## 1. Summary

HackDataV2 is a single-page web workspace that generates **realistic, privacy-safe synthetic data** in three forms — **tabular**, **relational (multi-table)** and **documents** (invoices, bank statements, and later narrative documents) — from either a **natural-language query** or an **uploaded CSV**.

Every run produces a fresh valid dataset (or an exactly reproducible one from a seed), enforces relational consistency by construction, and shows a **scorecard** (validity, fidelity, utility, privacy) so the user can see how good the data is and what each score was measured against.

**One-line pitch (PROPOSED):** *Describe the data you need, or drop a sample. Our AI turns that into a generation plan, our engine builds consistent data from it, our validators verify it, and our scorecard tells you how faithful and useful it is.*

**Context:** hackathon deliverable, about 10 hours, 3 people plus Claude Code, 8 GB RAM laptop, no GPU, free external LLM API. Optimising for a working, convincing, defensible prototype, not an enterprise platform.

---

## 2. Problem

Teams need realistic data for testing, demos and ML work but cannot use real records because of privacy, legal and access limits. Existing options each fail in a specific way:

| Approach | Failure |
|---|---|
| Faker-style scripts | Columns are independent, so nothing is consistent across tables and nothing correlates. |
| "Ask an LLM for rows" | Slow, expensive, breaks keys and totals, cannot scale to thousands of rows, not reproducible. |
| Heavy generative models (CTGAN, TVAE) | Need GPUs and tuning; multi-table consistency is still weak. |
| Enterprise tools (Tonic, Gretel, MOSTLY AI) | Hosted, paid, not something a small team can embed. |

**Core problem to solve:** produce data that is *structurally valid* (keys, cardinalities, totals), *behaviourally coherent* (students do not place machinery orders), *reproducible*, and *measurably good*, using only lightweight tools.

---

## 3. Users

| Persona | Need | What success looks like |
|---|---|---|
| **QA / backend developer** | Seed a test database with consistent multi-table data | Types one sentence, downloads a SQL dump that loads with no constraint errors |
| **ML practitioner** | Get more training data or a shareable stand-in for a sensitive CSV | Uploads a CSV, gets a synthetic one plus TSTR/TRTS scores against a hold-out |
| **Product / demo builder** | Realistic invoices and statements for a demo | Generates a batch of invoices whose totals reconcile, exports PDFs |
| **Hackathon judge** (evaluator, DECIDED to test both modes) | Verify the claims quickly | Sees validity, scores, reproducibility and a "break it" demo in minutes |

Non-users: end customers, anyone needing certified anonymisation (see non-goals).

---

## 4. Goals and non-goals

### 4.1 Goals

1. Generate tabular, relational and document data from a query **and** from uploaded data (DECIDED).
2. Guarantee relational integrity by construction and prove it in every run (DECIDED).
3. Make each Enter produce a new valid dataset, with a typed seed reproducing a run (DECIDED).
4. Show per-run scores with honest reference labels (DECIDED).
5. Export CSV, JSON, PostgreSQL SQL dump and PDF (DECIDED; dialect ASSUMED).
6. Run on an 8 GB laptop with an external free LLM API (DECIDED).

### 4.2 Non-goals

| Not doing | Why |
|---|---|
| Formal differential privacy or any "privacy guaranteed" claim | Needs sensitivity bounds and budget accounting; we ship Laplace noise and label it honestly |
| Deep generative models (CTGAN, TVAE), local LLMs, GPU training | Hardware and time |
| DOCX output | Cut |
| Authentication, multi-user accounts, cloud storage, sharing links | Out of hackathon scope |
| Schema-file upload; learning document layout from uploaded PDFs | Cut |
| Attack-based privacy metrics (membership inference, re-identification) | Research-level; only two cheap heuristics kept |
| Query-mode realism score | There is no real reference to score against; we show validity and spec-based coherence only |

---

## 5. Scope: three modules, two modes

| Module | Query mode (no real data) | Data mode (upload CSV) |
|---|---|---|
| **Tabular** | Describe one table; engine generates rows | One CSV: infer types, fit marginals plus Gaussian copula, sample new rows |
| **Relational** | Describe several tables with keys, cardinalities, rules; parents generated first | Several CSVs: detect PKs/FKs, fit each table, learn children-per-parent counts, mine rules |
| **Documents** | Invoice, bank statement (P0); assignment, cover letter, report (P2) | Upload line items or transactions; learn patterns; same renderer (P1) |

All three share **one generation core** (DECIDED). The modules are thin front ends.

---

## 6. User stories

1. As a developer I type "Pakistani e-commerce database with 5,000 customers, 20,000 orders, products and order items" and get four consistent tables with **0 FK violations**.
2. As a user I press Enter again and get **different data with the same structure**, each with its own seed and scorecard in a run history.
3. As a user I type a seed and get **exactly the same data**, and I can verify it with checksums.
4. As a user I ask for something impossible (10 customers, exactly 20 orders each, 100 orders) and am told **why it is impossible and how to fix it** before anything runs.
5. As a user I open the generated **spec**, edit one weight and re-run with **no LLM call**.
6. As a user I press **Generate invoices** on a relational run and receive PDFs whose numbers match the orders table.
7. As a user I upload a CSV and see the **detected schema**, correct a wrong guess, generate, and read **fidelity, TSTR/TRTS and privacy** scores against a real hold-out and against a naive baseline.
8. As a judge I press **Corrupt this dataset** and watch the validator catch each defect.
9. As a user I export CSV, JSON, a SQL dump or PDFs, whether or not I saved the run.

---

## 7. Functional requirements

Priorities: **P0** demo path must work · **P1** if time allows, in the order given · **P2** cut first. Section references point to `HackDataV2_Architecture.md` (the "architecture record", AR).

### 7.1 Input and query interpretation

| ID | Requirement | Pri | Acceptance |
|---|---|---|---|
| FR-01 | Accept a natural-language query and turn it into a validated spec | P0 | Spec passes Pydantic validation; one repair retry on failure (AR 7.1, 11.4) |
| FR-02 | Provide hand-verified templates: e-commerce, banking, invoicing | P0 | Each generates with the LLM fully offline (AR 8.5) |
| FR-03 | Report requested features outside the rule vocabulary as `unsupported` instead of ignoring them | P0 | UI lists them (AR 7.2) |
| FR-04 | Cache spec and value pools per query so Enter costs zero API calls | P0 | Second identical query makes 0 LLM calls (AR 11.5) |
| FR-05 | Show the spec, allow editing, and run from the edited spec without an LLM call | P0 | Bad edits return field-level errors (AR 7.9) |
| FR-06 | Reject impossible requests before generation with a plain message and suggested fix | P0 | Example in story 4 fails with code `infeasible` (AR 7.8) |

### 7.2 Generation core

| ID | Requirement | Pri | Acceptance |
|---|---|---|---|
| FR-10 | Generate from a master seed; blank seed picks a random one, shown and saved | P0 | Seed always returned |
| FR-11 | Same spec plus same seed yields identical data; a new seed yields a different valid dataset | P0 | Checksums match on replay (AR 8.1, 15.5) |
| FR-12 | Derive per-table and per-column seeds from names so adding a column does not reshuffle others | P0 | Test: adding a column leaves others unchanged |
| FR-13 | All row values, keys, dates, amounts come from code; the LLM never generates rows or numbers | P0 | Enforced by design and review |
| FR-14 | Store money as integer minor units; convert at export and render | P0 | No float drift in totals |
| FR-15 | Support configurable row count, null rate, outlier rate, locale, currency | P0 | Config panel fields |
| FR-16 | Apply masking, salted hashing and Laplace noise per column | P0 | Labelled "no formal DP guarantee" (AR 8.11) |
| FR-17 | Generate entity-first values (name, email, city, phone consistent) | P0 | Spot-check tests |

### 7.3 Relational consistency

| ID | Requirement | Pri | Acceptance |
|---|---|---|---|
| FR-20 | Generate tables in dependency order; reject cycles at validation | P0 | Cycle spec fails cleanly |
| FR-21 | Every FK references an existing parent; every PK unique | P0 | Validity 100% on every run (AR 9.1) |
| FR-22 | Support 1:1, 1:N and N:N (junction tables, no duplicate pairs) with exact requested totals | P0 | Totals match request |
| FR-23 | Compute aggregates (for example `orders.total`) from child rows, never sample them | P0 | `sum_of` rule holds for every row |
| FR-24 | Keep entity timelines consistent (signup < order < delivery, all ≤ `as_of`; status derived from timestamps) | P0 | Rule checks pass |
| FR-25 | Condition child behaviour on a parent attribute (segment drives order count, categories, quantities) | P0 query / P1 data mode | Coherence panel passes (AR 8.4.1) |

### 7.4 Data mode

| ID | Requirement | Pri | Acceptance |
|---|---|---|---|
| FR-30 | Accept CSV uploads with readable errors (encoding, delimiter, size, duplicates) | P0 | No tracebacks shown (AR 10.11) |
| FR-31 | Infer column types (code plus closed-vocabulary LLM classification verified by code) | P0 | Falls back to code type when verification fails |
| FR-32 | Detect PKs and FKs by uniqueness and containment (≥ 0.99) and let the user correct them | P0 detect / P1 edit UI | Corrections re-run cardinality and rule mining |
| FR-33 | Split real data 80/20 before fitting; use the 20% only for scoring | P0 | Verified by test |
| FR-34 | Fit marginals plus Gaussian copula for one table; regenerate IDs and PII | P0 | 1.5-hour time-box then fallback (AR 10.5) |
| FR-35 | Learn children-per-parent histogram and mine closed-set rules at ≥ 99% | P1 | Rules listed in the report |
| FR-36 | Bundled sample dataset and a "Try with sample data" button | P0 | Demo never depends on a judge's file |
| FR-37 | Group-wise conditioning of child tables on one parent attribute | P1 | AR 10.6 |

### 7.5 Documents

| ID | Requirement | Pri | Acceptance |
|---|---|---|---|
| FR-40 | Generate invoices: line items, tax, discount, totals computed by code | P0 | Recomputed totals equal stored totals |
| FR-41 | Generate bank statements with running balance never below the minimum | P0 | `running_balance` rule holds |
| FR-42 | Region profiles (date format, currency, tax label, invoice-number pattern) | P0 | New region = config entry |
| FR-43 | Render preview and PDF from the same HTML template | P0 | One template per layout |
| FR-44 | Support query-style constraints ("last 90 days, balance over 500") | P0 | Constraints enforced by construction |
| FR-45 | Generate invoices from a relational run, capped at 50 PDFs, all invoices also as CSV | P1 | Invoice total equals its order total |
| FR-46 | Narrative documents via fact sheet, LLM body, fact check; cap 20 per run | P2 | Required facts appear in text |

### 7.6 Validation

| ID | Requirement | Pri | Acceptance |
|---|---|---|---|
| FR-50 | Tier 1 structural checks (PK, FK, types, counts, aggregates); hard fail | P0 | AR 9.4.1 |
| FR-51 | Tier 2 business-rule checks with targeted deterministic fixes | P0 | Fixes logged |
| FR-52 | Tier 3 behavioural coherence checks against the spec, shown separately, not scored | P0 | Panel visible on relational runs |
| FR-53 | Test the validator with deliberately broken data (8 defect types) and provide a "Corrupt this dataset" demo button | P0 | Each defect caught by the right check (AR 9.6) |

### 7.7 Evaluation and scorecard

| ID | Requirement | Pri | Acceptance |
|---|---|---|---|
| FR-60 | Per-run scorecard: validity, fidelity, utility, privacy, overall (weights shown) | P0 | AR 14 |
| FR-61 | Fidelity: KS, TVD, Spearman correlation difference | P0 | Data mode |
| FR-62 | Utility: TSTR and TRTS against a real-on-real baseline (RandomForest) | P0 | Ratios reported |
| FR-63 | Privacy heuristics: exact-match rate and nearest-neighbour distance ratio | P0 | Labelled heuristics, not proofs |
| FR-64 | Every score shows a reference badge (`vs. real hold-out`, `vs. spec`, `structural`) | P0 | UI |
| FR-65 | Run history table with seed and scores | P0 | Last runs listed |
| FR-66 | Naive-baseline comparison (independent columns) in data mode | P1 | AR 14.10 |
| FR-67 | Slow scores computed in the background and shown as they finish | P0 | Polling |

### 7.8 Export and runs

| ID | Requirement | Pri | Acceptance |
|---|---|---|---|
| FR-70 | Runs are temporary until Save; Download works without saving | P0 | AR 15.1 |
| FR-71 | Export CSV, JSON, PostgreSQL SQL dump (parents first, loads without errors), PDF zip | P0 | SQL loads into PostgreSQL |
| FR-72 | Show SHA-256 checksums beside the seed and support replay-and-verify | P0 | AR 15.5 |

### 7.9 Locale

| ID | Requirement | Pri | Acceptance |
|---|---|---|---|
| FR-80 | Pakistan profile: phones (+92 3XX XXXXXXX), cities, names, PKR formatting with lakh or western grouping option, DD/MM/YYYY in documents | P0 basics | AR 8.13 |
| FR-81 | Seasonality in dates (weekday, month end, sale and Eid periods) | P1 | Visible in date histogram |
| FR-82 | Synthetic national-ID-like values with a reserved fake marker, masked by default | P1 | Cannot match a real number |
| FR-83 | Urdu output (pools and PDF) | P2 | Depends on bake-off |

### 7.10 Interface

One page, no routes, no reloads (DECIDED):

- Left sidebar: Tabular, Relational, Documents.
- Top: Query / Upload toggle.
- Right: configuration panel (rows, seed, locale, currency, privacy, null and outlier rates, Generate, Save, Export).
- Centre: preview canvas (table, FK diagram, or rendered document).
- Bottom: scorecard strip and run history.
- v2 additions: spec panel, feasibility message, corrupt button, checksum line with replay, coherence panel, baseline table, schema view, generate-invoices button, sample-data button.

---

## 8. Non-functional requirements

| Area | Requirement |
|---|---|
| **Performance** | 5,000 customers and 20,000 orders with items generate in seconds on the target laptop (PROPOSED target: under 10 s excluding LLM and scoring). Scoring finishes within about a minute. |
| **Memory** | Fit within 8 GB: 100k rows per table, RandomForest `n_jobs=1` on at most 20k rows, nearest-neighbour on at most 5k rows per side, one Chromium instance. |
| **Reliability** | Demo survives an LLM outage: cache, key rotation with cooldown, model fallback, OpenRouter, offline templates, pre-cached demo queries. |
| **Reproducibility** | Same spec, seed and software versions give byte-identical CSV, JSON and SQL. PDFs are excluded. |
| **Correctness** | Structural validity 100% by construction; every encoded rule 100%. No claim about unencoded rules. |
| **Honesty of claims** | No "differential privacy", "infinite", "never touches real records" (data mode) or "realistic" as a measured claim in query mode. |
| **Privacy** | Data mode never copies a real row; IDs, names, emails and other identifying columns are regenerated. API keys only in environment variables. |
| **Usability** | No code needed to use it; errors are readable messages, never tracebacks. |
| **Maintainability** | Every component separate; common code in utils; **no hard-coded values** (all constants live in the constants package); consistent logging and one custom exception type (TRD sections 1, 5, 10, 16). |
| **Portability** | Runs locally on Linux, macOS or Windows with Python 3.11 or newer; Docker is optional (P2). |
| **Security** | Safe expression evaluation only (`simpleeval`), no `eval` of LLM output; upload size and row caps; no secrets in the repo. |

---

## 9. Success criteria

### 9.1 Demo acceptance checklist (PROPOSED)

- [ ] Relational e-commerce query yields four tables, validity 100%, coherence panel green.
- [ ] Three consecutive Enters give three different datasets, three seeds, three scorecards in history.
- [ ] Typing a seed reproduces a run; checksums match.
- [ ] An impossible request shows the feasibility message.
- [ ] "Corrupt this dataset" turns the validator red and names the rows.
- [ ] Editing the spec and running from it works with the LLM disabled.
- [ ] Invoices for 10 orders match the orders CSV.
- [ ] Sample CSV upload shows schema, TSTR/TRTS, privacy and the naive-baseline comparison.
- [ ] SQL dump loads into PostgreSQL without errors.
- [ ] Whole demo path works with the network off (pre-cached).

### 9.2 Quality bars (PROPOSED)

| Measure | Bar |
|---|---|
| FK validity, PK uniqueness | 100% |
| Encoded rule satisfaction | 100% |
| Validator negative tests | 8 of 8 defect types caught with correct counts |
| TSTR ratio on sample data | Reported honestly; target at least 0.85 (PROPOSED; sample data is team-made, so this is a sanity check, not proof) |
| Naive baseline | Ours beats it on correlation and utility, or we report that it does not |

---

## 10. Constraints and assumptions

**Constraints (DECIDED):** about 10 hours; 3 people plus Claude Code; 8 GB RAM, about 20 GB disk; no GPU or large local LLM; free or low-cost external APIs; FastAPI backend.

**Assumptions (ASSUMED, veto freely):** values change on every Enter while structure stays fixed; PostgreSQL SQL dialect; three templates (e-commerce, banking, invoicing); caps of 100k rows per table, 20 MB upload, 20 narrative documents, 50 invoice PDFs; Jev optional; lakh grouping as the default PKR display; narrative documents demoted to P2.

---

## 11. Dependencies

| Dependency | Use | Risk |
|---|---|---|
| **Groq API** (OpenAI-compatible) | Spec, pools, text | Rate limits are per organisation, not per key (VERIFY); mitigated by cache and fallbacks |
| OpenRouter (optional) | Fallback model | Availability |
| Jev by TypeSafe AI (optional, P2) | Column classification and routing | Very new, vendor-reported numbers (VERIFY) |
| Playwright + Chromium | PDF rendering | About 300 MB download, memory |
| Python libraries | See `TRD.md` section 2 | Version pinning for reproducible hashes |

---

## 12. Risks

| Risk | Mitigation |
|---|---|
| Integration between three people | Contract-first: constants, entities, spec models and API payloads committed in the first 45 minutes |
| P0 nearly fills realistic capacity (about 18.5 of about 20 productive hours) | Hour-3 gate that drops all P1 items if behind; narrative documents already P2 |
| LLM spec unreliable | Closed vocabulary, Pydantic, one repair retry, hand-verified templates, cache, offline path |
| Groq limits or model changes | Bake-off in hour one; key rotation is a backup layer only |
| Copula takes too long | Time-box 1.5 hours; fall back to marginals plus rank-correlation nudge |
| Overclaiming to judges | Reference badges; approved wording in the architecture record, section 22 |
| Structure discipline slows the build | Scaffold generated by Claude Code in the first 45 minutes; one enforcement script (TRD section 16) |

---

## 13. Release plan

| Tier | Contents |
|---|---|
| **P0** | Everything marked P0 above: query mode for all three modules, feasibility, three-tier validation with corrupt demo, conditional relationships (query mode), seeds and checksums, spec panel, sample data and readable errors, Pakistan basics, tabular data mode with scoring, exports |
| **P1 (ranked)** | 1 invoices from orders · 2 naive baseline · 3 relational data mode with rule mining · 4 schema view · 5 seasonality · 6 data-mode conditioning · 7 save and history persistence, documents-from-data · 8 rest of the Pakistan profile |
| **P2** | Urdu PDF, Jev, extra-metrics drawer, reference upload in query mode, advisory LLM check, narrative documents |

Checkpoints at hour 3 (full demo path end to end, decide P1) and hour 6 (full run). Hours 8–10 are integration, pre-caching and rehearsal.

---

## 14. Open questions

1. Who takes which track (A engine, B data and evaluation, C product)?
2. React or plain HTML plus Alpine.js (decide by hour 3)?
3. Groq bake-off results: JSON reliability, Urdu quality, final model IDs.
4. Are multiple Groq keys from separate accounts, and is that acceptable under Groq's terms?
5. Real sample CSV for the demo, and how judges will test data mode.
6. Lakh or western grouping default; Eid dates, GST rate and mobile prefixes to verify.
7. Confirm the ASSUMED items in section 10.

---

## 15. Traceability to the HackDataV2 pitch deck

| Deck claim | Requirements |
|---|---|
| Ingest schema from a sample | FR-30 to FR-32 (schema-file upload not built) |
| Model relationships: distributions, correlations, FK cardinalities | FR-34, FR-35, FR-37 |
| Generate with AI: names, text, edge cases | FR-01, FR-13, FR-15 |
| Validate and export: integrity, fidelity, export formats | FR-50 to FR-53, FR-60 to FR-72 |
| Tabular: fidelity, row count, seed, null and outlier rates, privacy controls | FR-10 to FR-16, FR-61 |
| Relational: automatic referential integrity, 1:1, 1:N, N:N, totals reconcile | FR-20 to FR-24 |
| Invoices and bank statements, region layouts, bulk | FR-40 to FR-45 |
| One workspace, no code | Section 7.10 |

---

## 16. Glossary

| Term | Meaning |
|---|---|
| **Spec** | Validated JSON plan (tables, columns, rules, pools) that the engine consumes |
| **Pool** | LLM-written list of values (names, merchants, cities) sampled by code |
| **Master seed** | One integer per run from which all table and column seeds derive |
| **TSTR / TRTS** | Train on synthetic, test on real / train on real, test on synthetic |
| **KS / TVD** | Kolmogorov-Smirnov statistic / total variation distance |
| **Copula** | Model that keeps each column's distribution and the correlations between columns |
| **Minor units** | Integer paisa or cents used instead of floats for money |
| **Feasibility check** | Arithmetic pre-check that a requested dataset can exist |
| **Coherence** | Whether behaviour matches the spec (students order less than businesses), distinct from structural validity |
| **Reference badge** | Label on each score naming what it was measured against |
