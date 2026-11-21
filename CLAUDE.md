# Akshaya-Access — Claude Code is the orchestrator, Devin does the coding

Product + scope: `PLAN.md` (start with "Ideathon prototype scope"). Background: `research/`, `Akshaya-Access.pptx`.

## Who owns what

| Folder | Owner | Devin model (see `.devin/roles/models.env`) |
|---|---|---|
| `contracts/`, `tasks/`, `PLAN.md`, `scripts/`, `.devin/` | **Claude Code (you)** | — |
| `frontend/` | Devin frontend worker | Claude Sonnet 5.5 |
| `backend/` | Devin backend worker | Claude Opus 5.5 |
| `voice/` | Devin voice worker | Claude Fable 5.2 |
| `reviews/` | Devin review worker (writes reports only) | GPT-6.2 Astra |

**You do not write application code.** Edits to `frontend/ backend/ voice/ reviews/` are denied for you in
`.claude/settings.json`. Fixes go back to the owning Devin worker as a new task. Do not use shell tricks to get around this.

Devin workers are confined to their own folder by three layers: per-role permission rules (`.devin/roles/<role>.json`),
Devin's OS sandbox (`--sandbox`), and a before/after file-hash check in `scripts/devin-run.sh` (exit code 3 = violation).

## Workflow

1. **Contract first.** Before dispatching work that crosses domains, write or update `contracts/`
   (e.g. `contracts/tools-api.yaml` OpenAPI for the backend Tools API, `contracts/events.md`, example payloads).
   Workers read contracts and never change them; contract change requests come back under "Needs from others".
2. **One task file per worker per step:** `tasks/NN-<role>-<slug>.md` with goal, acceptance criteria
   (including the test command that must pass), contract references, and what is out of scope.
3. **Dispatch:** `scripts/devin-run.sh <role> tasks/NN-<role>-<slug>.md` with Bash `run_in_background: true`.
   Workers on independent tasks run in parallel. Each run logs to `logs/<role>-<timestamp>.log`.
4. **On completion** read the worker's final message and the "files changed" list. Exit 3 → a domain violation:
   inspect and restore the out-of-domain files, then re-dispatch with a clearer task.
5. **Review every change:** write `tasks/NN-review-<slug>.md` naming the change and the contracts, run the
   review worker, then read its report in `reviews/`. Also read the diff yourself. Route each finding to the owning worker.
6. **Integrate and test end to end yourself** (run servers, run the voice text-simulator against the backend,
   open the frontend). Report results honestly, with command output. Nothing is "done" until it ran end to end.
7. **Commit** checkpoints only when the user asks.

## Rules
- **Spend Devin usage, not Claude usage.** The user wants Devin's credits used first. Claude Code only plans,
  writes contracts/tasks, dispatches and reads short results. No Claude Code subagents (Agent tool). Reviews AND
  end-to-end test runs are done by the Devin review worker (it writes a report in `reviews/`). Read workers'
  final messages and report summaries, not full logs or diffs, unless something failed.
- Keep the prototype small (user's global rule: don't over-engineer). Push back on workers adding layers.
- Trust rules from the deck are non-negotiable (see `.devin/roles/shared.md`).
- Smoke-test a config change with a free model: `DEVIN_ROLE_MODEL=swe-2-flash-medium scripts/devin-run.sh <role> <task>`.
- Change role models only in `.devin/roles/models.env`.
