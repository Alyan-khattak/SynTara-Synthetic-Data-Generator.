# SynTara — Synthetic Data Platform

> Describe the data you need, or drop a sample. SynTara turns that into a generation plan, builds consistent data from it, validates it, and scores it.

Built in ~10 hours at a hackathon by 3 people + Claude Code. Runs on a laptop (8 GB RAM, no GPU).

---

## What it does

SynTara generates **realistic, privacy-safe synthetic data** in three forms:

| Mode | What you get |
|------|-------------|
| **Tabular** | Single CSV with typed columns, rules and distributions |
| **Relational** | Multi-table schema with enforced foreign keys and consistency |
| **Documents** | Invoices and bank statements as PDF/JSON |
| **Data Mode** | Upload a real CSV → synthesise structurally similar data (copula-based) |
| **ML Lab** | Plant a predictable target signal, split train/test, run an ML check |

Every run returns a **scorecard** (validity, fidelity, utility, privacy) so you know how good the data is.

---

## Features

- Natural-language query → LLM writes a generation spec → engine generates every row deterministically
- Uploaded data **never** sent to any external model or API
- Fully reproducible: every random draw uses an explicit seed derived from a master seed via blake2b
- Gaussian copula preserves column correlations in Data Mode
- Column profiler: Pearson/Spearman, Cramér's V, η², heatmap matrix, auto-findings
- ML Lab: RandomForest check, AUC (classification) or R² (regression) vs baseline
- Bilingual UI (English / Urdu) via Alpine.js i18n
- No database; artifacts stored in `Artifacts/temp/` and `Artifacts/saved/`

---

## Quick Start

```bash
# 1. clone and install
git clone <repo-url>
cd HacktoberFest
pip install -e .

# 2. set API keys
cp .env.example .env
# edit .env — fill in GROQ_API_KEYS (comma-separated) and JEV_API_KEY

# 3. start the server
uvicorn app:app --reload

# 4. open http://localhost:8000
```

### Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEYS` | Yes | Comma-separated Groq API keys (key rotation built in) |
| `JEV_API_KEY` | No | TypeSafe AI key for Jev validation scoring |

---

## How it works

```
User query / uploaded file
        │
        ▼
   LLM (Groq)              ← spec generation only; never sees uploaded data
   writes a JSON Spec
        │
        ▼
   Generation Engine        ← pure Python; no ML needed
   (GenerationPipeline)
   → sequence, uuid, money, categorical, faker, expr, conditional, …
   → relational: FK graph resolved in dependency order
   → documents: Jinja2 templates → ReportLab PDFs
        │
        ▼
   Validators               ← every rule checked; score returned
   Evaluators               ← fidelity, utility, privacy metrics
        │
        ▼
   Artifacts/temp/<run_id>/ ← CSV / JSON / PDF files + scores JSON
```

### Data Mode (upload path)

```
User CSV
   │
   ▼
Profile & fit CopulaFitter (scipy + pandas)
   │
   ▼
Draw n_rows synthetic rows
   │
   ▼
Apply realism (missing values, outliers, noise, correlation adjustment)
   │
   ▼
Artifacts/temp/<run_id>/synthesised_data.csv
```

### ML Lab

```
Data source (describe query → GenerationPipeline, OR uploaded CSV)
   │
   ▼
Plant target column via logistic/linear function of driver columns + label noise
   │
   ▼
Stratified train/test split
   │
   ▼
RandomForest ML check → AUC or R² vs naive baseline
   │
   ▼
Export: train.csv, test.csv, start_here.py, DATA_CARD.md, run_metadata.json
```

---

## Models

All models are served through the **Groq Cloud API** (`groq` Python SDK). No model weights are downloaded locally.

| Model ID | Params | Open-weight | Access | Used for | License |
|----------|--------|-------------|--------|----------|---------|
| `openai/gpt-oss-120b` | 120 B | Yes | Groq API | Spec generation (primary) | Apache 2.0 |
| `openai/gpt-oss-20b` | 20 B | Yes | Groq API | Spec generation (backup) | Apache 2.0 |
| `jev-1` | — | No | TypeSafe AI API | Validation scoring | Proprietary |

**Bake-off results** (`docs/model_bakeoff.md`):

| Model | Valid/5 | Avg latency |
|-------|---------|-------------|
| `openai/gpt-oss-120b` | 5/5 | 2.1 s |
| `openai/gpt-oss-20b` | 4/5 | 1.6 s |

Primary model was chosen for reliability; backup kicks in automatically on rate-limit or timeout.

> License links to verify: [openai/gpt-oss-120b on HuggingFace](https://huggingface.co/openai/gpt-oss-120b) · [openai/gpt-oss-20b on HuggingFace](https://huggingface.co/openai/gpt-oss-20b)

---

## API Reference

Start the server and visit **`http://localhost:8000/docs`** for the interactive OpenAPI docs.

Key endpoints:

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/generate` | Generate tabular, relational, or document data |
| `POST` | `/api/upload` | Upload a CSV for Data Mode |
| `POST` | `/api/runs/{id}/generate-dm` | Synthesise from uploaded data |
| `GET`  | `/api/runs/{id}/profile` | Column profiles and correlation matrix |
| `POST` | `/api/ml/generate` | Run ML Lab pipeline |
| `GET`  | `/api/runs/{id}/scores` | Scorecard (validity, fidelity, utility, privacy) |
| `GET`  | `/api/runs/{id}/export` | Download CSV / JSON / SQL / PDF |
| `POST` | `/api/runs/{id}/save` | Move run from temp to saved |
| `GET`  | `/api/config` | Public config (caps, weights, module flags) |
| `GET`  | `/api/health` | Health check |

---

## Running Tests

```bash
pytest                        # all 84 tests
pytest tests/unit/            # unit tests only
pytest --cov=hackdata         # with coverage
```

Additional checks:

```bash
python scripts/check_no_hardcoding.py   # no bare strings/numbers in source
bash scripts/smoke.sh                   # full demo path end-to-end
```

---

## Project Structure

```
hackdata/
  constants/     — all literals: paths, thresholds, messages, model IDs
  entity/        — typed dataclasses and Pydantic models
  components/    — reusable logic (profiler, ML checker, copula, evaluators)
  pipeline/      — orchestrated end-to-end flows
  utils/         — shared helpers
  exception/     — HackDataException wrapper
  logging/       — logger setup
  cloud/         — LLM client, key pool, cache, offline fallback

api/
  routes/        — FastAPI routers (one file per domain)
  schemas.py     — Pydantic request/response models

frontend/
  index.html     — Alpine.js SPA (no build step)
  js/api.js      — fetch wrapper; all network calls go here

Artifacts/
  temp/          — active runs (last 10 kept)
  saved/         — runs the user explicitly saved
```

---

## Limits

| Resource | Cap |
|----------|-----|
| Upload size | 10 MB |
| Synthetic rows (Data Mode) | 50 000 |
| Invoice PDFs per run | 50 |
| RAM | 8 GB |
| GPU | None required |

---

## Security Notes

- Uploaded files are written only to the run's own temp folder; they are **never sent to any external API**.
- API keys are loaded from `.env` (excluded from git); see `.gitignore`.
- All user inputs validated with Pydantic v2 models before processing.

---

## License

MIT — see [LICENSE](LICENSE).

Third-party dependency licenses: [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).
