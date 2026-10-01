# HackDataV2 — Synthetic Data Platform (hackathon MVP)

A FastAPI backend plus a light frontend that generates synthetic data (tabular, relational, documents) from a text query or an uploaded file, then scores it (validity, fidelity, utility, privacy). Built in about 10 hours by 3 people plus Claude Code.

## Read before any work
1. `standards.md` — team rules and definition of done
2. `TRD.md` — file structure, libraries, constants, layers (**wins over any other document if they disagree**)
3. `PRD.md` — what to build and why
4. `task.md` — the task list (status, owner, acceptance)
5. `context.md` — history so far; read the newest entries first
6. `skills_matrix.md` — which skills and tools each agent uses

`docs/HackDataV2_Architecture.md` is background only. The TRD replaces it for the build.

## Who runs the session
The main session acts as the **orchestrator** (`.claude/agents/orchestrator.md`). It plans, dispatches to `backend-agent`, `frontend-agent`, `data-ml-agent`, `qa-agent` and `reviewer-agent`, verifies by evidence, and does not write product code.
Only the orchestrator writes `task.md` and `context.md`. Agents report to it.

## Four rules for everyone
1. Write simple, readable code with comments (explain why).
2. Plan first, then code.
3. Reuse before writing; search the codebase first.
4. Use a library when one exists (standard library, then installed, then new with a pinned version).

## Project conventions (details in TRD.md)
- Layer order: constants → entity → components → pipeline → utils → exception → logging → cloud → app.
- No hard-coded values: paths, thresholds, URLs and messages live in `hackdata/constants/`.
- Raise `HackDataException(e, sys)` in every `except`; log with `from hackdata.logging.logger import logging`.
- Use `os.path.join`; copy dataframes before changing them; typed dataclasses or Pydantic models across boundaries.
- Money is stored as integer minor units. Every random draw uses an explicit seed derived from the master seed.
- The LLM writes specs and text only; code generates every row, key, number and date.
- The LLM is called only from `hackdata/cloud/`, with timeout, retries and fallback.

## Commands
- Install: `pip install -e .`
- Run API: `uvicorn app:app --reload`
- Tests: `pytest`
- Hard-coding check: `python scripts/check_no_hardcoding.py`
- Smoke test (full demo path): `bash scripts/smoke.sh`

(Adjust if TRD.md section 19 differs; the TRD is the source.)

## Limits
8 GB RAM, about 20 GB disk, no GPU. Keep data in memory small; cap uploads at 10 MB; cap invoice PDFs at 50.

## Never
- Commit `.env`, API keys or generated data.
- Change a frozen contract without the human's approval and a `context.md` entry.
- Mark a task done without running its acceptance check.
