# Skills, tools and plugins matrix

Status key: **V** = seen in this session's account listing. **?** = named by you, not visible to me, so VERIFY it exists (`/skills`) before relying on it. **Fallback** = what the agent does without it.

Only V items are guaranteed. Every "?" item is a suggestion by name and purpose only. Load a skill only when the task needs it.

## 1. What is verified

**V (seen):** api-backend-security, ui-styling, ui-ux-pro-max, design, design-system, impeccable, graphify, diagram-design, redesign-existing-projects, high-end-visual-design, design-taste-frontend, caveman, docs, computer-use, chrome-browser, built-in-browser, deep-research, import-memory, morning, skill-creator, xlsx, pptx, pdf, docx.

**Plugins / connectors:**
- Claude Docs (MCP): present in this session as tools. **Usable.**
- Google Drive: listed but **not connected**. Cannot be used until you connect it.
- Other plugins: none enabled.

**?** Everything else in your list (superpowers set, ponytail set, caveman suite, dataviz, code-review, simplify, security-review, loop, schedule, claude-api, run, init, and so on).

## 2. Assignment by role

| Role | Use (V) | Use (?) | Fallback if a ? is missing |
|---|---|---|---|
| **orchestrator** | graphify (map the codebase), diagram-design (architecture pictures), docs (living docs), skill-creator (new skills), deep-research (external facts) | writing-plans, executing-plans, dispatching-parallel-agents, subagent-driven-development, using-git-worktrees, brainstorming, finishing-a-development-branch, verification-before-completion, loop / schedule (gates and reminders) | Use the plan-and-brief rules in `orchestrator_agent.md`; run gates by hand |
| **backend-agent** | api-backend-security (API safety review) | test-driven-development, systematic-debugging, security-review, claude-api (if calling Claude), surgical-patch, safe-refactor, lean-build | Plan, write small tests, read the failing output before changing code |
| **frontend-agent** | ui-styling, ui-ux-pro-max, design-system, impeccable, design-taste-frontend, minimalist-ui or high-end-visual-design (pick one look), built-in-browser (open and check the page), chrome-browser (only if a real signed-in browser is needed) | — | Screenshot with the Playwright already in the environment |
| **data-ml-agent** | xlsx (spreadsheet inputs and outputs), docx / pdf only if a report file is required | dataviz (charts), systematic-debugging | Use matplotlib, pandas and scikit-learn directly |
| **qa-agent** | built-in-browser (click through the demo), xlsx (fixtures) | test-driven-development, systematic-debugging, verification-before-completion, verify-and-stop | pytest, parametrise, temp dirs, the smoke script |
| **reviewer-agent** | api-backend-security (checklist), design-taste-frontend (UI review only) | requesting-code-review, receiving-code-review, code-review, simplify, security-review, ponytail-review, caveman-review | The checklist in `reviewer_agent.md` |

## 3. Tools by role

| Tool | orchestrator | backend | frontend | data-ml | qa | reviewer |
|---|---|---|---|---|---|---|
| Read, Glob, Grep | yes | yes | yes | yes | yes | yes |
| Write, Edit | task.md, context.md, standards.md, matrix only | yes | yes | yes | tests and fixtures only | **no** |
| Bash | yes (checks, read-only git) | yes | yes | yes | yes | read-only commands |
| Agent (dispatch) | **yes** | no | no | no | no | no |
| Skill | yes | yes | yes | yes | yes | yes |

## 4. Plugins and connectors by use

| Plugin | Use it for | Who | Status |
|---|---|---|---|
| Claude Docs | Publish PRD, TRD, status report, demo script as a living doc for teammates | orchestrator | Usable now |
| Google Drive | Share files, read reference documents, store the final package | orchestrator | Not connected; connect first or skip |
| Built-in browser | Look at the running UI, exercise flows, screenshots | frontend, qa | V |
| Claude in Chrome | Only when a page needs your real signed-in session | frontend | ? |

## 5. Suggested loadout for this project (HackDataV2)

- **Phase 0, contracts and plan:** orchestrator with graphify, diagram-design, docs. Backend defines Pydantic contracts.
- **Phase 1, core build:** backend (api-backend-security, TDD), data-ml (xlsx only if needed), frontend (ui-styling, ui-ux-pro-max, design-system, one look skill).
- **Phase 2, verification:** qa (built-in-browser, verification-before-completion), reviewer (checklist + security-review).
- **Phase 3, demo:** frontend with impeccable for polish; orchestrator with docs for the write-up.

## 6. Rules

- Do not give every agent every skill. Two or three per role is enough.
- Pick one visual look skill for the UI (minimalist, brutalist, high-end). Mixing them produces an inconsistent interface.
- Skills that write files by themselves (docx, pptx, pdf, xlsx) run only when the task asks for that file type.
- Re-check this file when your installed skills change.
