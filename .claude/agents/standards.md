# Team Standards

Shared by every agent and every person on the team. Agents stay general; **this file is where project conventions live**. Edit it per project. If a project document (`TRD.md`, `PRD.md`, `CLAUDE.md`) disagrees with this file, the project document wins, and you say so in your report.

---

## 1. The four team rules (every agent, every task)

These apply to every agent. The orchestrator repeats them in every brief and checks them before accepting work.

### Rule 1 — Simple, readable code with comments

- Prefer the simple solution over the clever one. A new teammate should follow it without help.
- Small functions with one job (aim for under about 40 lines). Clear names that say what a thing is.
- Comments explain **why**, not what. Add a short docstring to every function and a one-line note on any non-obvious decision (`# IMP:` for critical choices).
- No dead code, no commented-out code, no unused imports.
- Leave the code easier to read than you found it, but only inside the task's scope.

### Rule 2 — Plan first, then code

- Before editing anything, write a **short plan**: goal, files to touch, the steps, the approach chosen, risks. Three to eight lines is enough.
- For a non-trivial task, show the plan first (in your reply or in `TASKS.md`) and follow the orchestrator's instruction on whether to wait for approval.
- For a trivial change (a few lines), a one-line plan is enough. Never skip planning entirely.
- If the plan changes halfway, update it and say why.

### Rule 3 — Reuse before you write

- **Search first:** `Grep` and `Glob` for an existing function, constant, component, fixture or util before writing a new one.
- If something you need already exists, use it. If it almost fits, extend it instead of copying it.
- When a second place needs the same logic, extract it into a shared helper in the common location (`utils/`, `shared/`, a common component). No copy-paste.
- Reuse constants too: never redefine a value that already exists.

### Rule 4 — Use a library when one exists

- Before hand-writing anything non-trivial (parsing, dates, hashing, validation, statistics, retries, HTTP, formatting, PDF, charts), check whether the **standard library**, an **already-installed dependency**, or a **well-maintained library** does it. Use it.
- Order of preference: standard library → dependency already in the project → new dependency.
- A new dependency needs: a one-line reason, a pinned version in the requirements file, and a check that it fits the project's limits (size, memory, licence, platform). Do not add a heavy package for three lines of code.
- Do not reinvent solved problems. Do not build your own version of what a library gives you correctly.

---

## 2. Shared working rules

1. **Read first:** `CLAUDE.md`, this file, `TRD.md`, `PRD.md`, `TASKS.md`, whichever exist. Note owners, tiers (P0/P1/P2), frozen contracts, and any value marked VERIFY or OPEN.
2. **Stay in scope.** Do the smallest change that satisfies the task. No drive-by refactors, no unrelated reformatting.
3. **Stay in your lane.** Edit only what your task assigns. If you need a change elsewhere, describe it precisely in your report instead of making it.
4. **Contracts are frozen** once the orchestrator or TRD says so (constant names, entity fields, schemas, API payloads, interfaces). Adding is fine; renaming or removing needs the requester's approval.
5. **Ask only when the answer changes what you build** and cannot be found in the documents. Otherwise choose the conventional option, build, and list the assumption.
6. **Never state a fact you did not verify.** Outside facts (API limits, library behaviour, dates, rates) are marked VERIFY. Say plainly what you did not run.
7. **No secrets** in code, logs, prompts or commits. Do not commit `.env`, keys, artifacts or large files.
8. **Commit only when asked.** Small commits with clear messages when you do.
9. **Evidence over assertion.** "Done" means you ran the tests or the app and can show the result.

---

## 3. Report format (every agent, every task)

Keep it short and factual. No recap of steps.

1. **Plan:** the plan you followed (or the one-line plan).
2. **What changed:** files created or edited, one line each.
3. **Verified by:** commands run and their results. Say plainly if something was not run.
4. **Reuse and libraries:** what you reused, which library you used, any new dependency and why.
5. **Assumptions:** anything you decided without confirmation.
6. **Contract impact:** none, or exactly what others must update.
7. **Follow-ups or blockers:** open questions, VERIFY items.

---

## 4. Default engineering standards (edit per project)

Python 3.11+ and FastAPI by default. For other stacks keep the principles and translate the syntax.

### 4.1 Layers

```
constants → exception, logging → entity → utils → cloud → components → modules → pipeline → api / app / main
```

A layer imports only from layers to its **left**. Components never call each other; the pipeline passes each artifact to the next stage. `cloud/` is the only place that talks to outside services.

### 4.2 No hard-coded values

Every fixed value lives in `constants/` (paths, file names, thresholds, limits, weights, model IDs, URLs, formats, allow-lists, status names, user-facing messages). Import the module, not the name: `from pkg.constants import paths` then `paths.ARTIFACT_DIR`. Secrets are never constants (only env-var names). Content such as prompts, templates and name lists lives in `data_assets/`.

### 4.3 Typed contracts

Config classes hold paths and primitive settings only. One `@dataclass` artifact per component output, never a plain tuple. Pydantic models for anything crossing a trust boundary (uploads, LLM output, API bodies).

### 4.4 One exception, one logger

- Every `except` raises the project exception (`raise ProjectException(e, sys)`), which adds file and line. No bare `except`, no swallowed errors. In `__main__` demos, **raise** it.
- One logger: `from pkg.logging.logger import logging`, then `logging.info(...)`. Log at the start and end of every public component method with key numbers. Never log secrets, full bodies or personal data.
- Run code from the repo root (after `pip install -e .`) or with `python -m`; never from inside the `logging/` folder, or it shadows the standard library.

### 4.5 Other defaults

- `os.path.join` or `pathlib` for paths. `os.makedirs(path, exist_ok=True)`.
- Never mutate an input DataFrame or dict; work on a copy.
- Explicitly seeded random generators only; no global random state.
- `eval` and `exec` are never used on generated or user text. Use a whitelist evaluator.
- Every external call has a timeout, bounded retries, a fallback or a clear error, and validated output.
- API routes are thin: validate, build a request entity, call one pipeline function, return.

---

## 5. Definition of done

- [ ] The four team rules are followed (readable and commented, planned first, reused, library used where one exists).
- [ ] Layer order respected; no hard-coded values; typed artifacts; exception and logging in place.
- [ ] Tests added or updated **and run**; a negative case exists where a check was added.
- [ ] Nothing outside scope changed; contracts unchanged or the change was flagged.
- [ ] No secrets, artifacts or logs staged.
- [ ] Report written in the format of section 3.

---

## 6. Common bugs

```python
dill.dump(obj, file_obj)             # correct   |  dill.dump(file_obj, obj) wrong
X_hold = fitted.transform(X_hold)    # correct   |  fit_transform on hold-out data = leakage
os.makedirs(path, exist_ok=True)     # correct   |  os.makedirs(path) crashes if it exists
if __name__ == "__main__":           # correct   |  "__name__" is always False
def __init__(self):                  # correct   |  __int__ is a typo
self.config = config                 # correct   |  self.config = self.config assigns nothing
df = df.copy()                       # never mutate the caller's frame
# pin versions for anything saved with dill/pickle; unpickling across versions breaks
# n_jobs=1 when combining grid search with TensorFlow; heavy init inside the function, not at import
```

---

## 7. Brief template (used by the orchestrator when dispatching)

```
GOAL:        one sentence
CONTEXT:     files to read first (CLAUDE.md, standards.md, TRD.md section X, TASKS.md item Y)
SCOPE:       files you may create or edit; files you must not touch
CONSTRAINTS: frozen contracts, limits (memory, time), values marked VERIFY
TEAM RULES:  1 simple readable commented code · 2 plan first, then code · 3 reuse before writing · 4 use a library when one exists
ACCEPTANCE:  exact commands or checks that must pass
REPORT:      format in standards.md section 3
```
