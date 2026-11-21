# 02 — Review round 1 + end-to-end test of all three parts

The first versions of `backend/`, `voice/` and `frontend/` were just built by three different workers against
`/home/shan/devin/contracts/` (read README.md and tools-api.yaml first). Nothing is committed yet, so review the
current files directly. You must not change any code. Write one report: `reviews/2026-11-21-round1.md`.

## 1. End-to-end run (do this first, report real command output)
- Backend tests: `cd /home/shan/devin/backend && .venv/bin/pytest -q`
- Voice tests: `cd /home/shan/devin/voice && .venv/bin/pytest -q`
- Frontend: `cd /home/shan/devin/frontend && npm run build && npx vitest run`
- Live flow, in ONE shell command (sandbox networking): start the backend on port 8000, wait for /health, then run
  every script in `voice/scripts/` with `voice/.venv/bin/python sim.py --script ...` against it. For the happy path, complete
  the payment the way the frontend's "Bank confirms" button would (`POST /simulator/payments/{id}/complete`) while
  the voice agent is polling. Then fetch `GET /calls` and `GET /calls/{id}` and check what the frontend would display.
  Stop the server.
- Check the frontend's API client and types (`frontend/src/api.ts`, `types.ts`) parse the real backend responses
  you just captured (field names, nullability, enums).

## 2. Review (rank findings by severity)
- Contract mismatches between any part and `tools-api.yaml`, or between parts (voice ↔ backend, frontend ↔ backend).
- Trust rules: anything that could accept/log OTP, PIN, Aadhaar; payment possible without confirmed number + amount;
  pending reported as anything but pending; missing SIMULATED labelling; unmasked caller phone anywhere.
- Correctness bugs and crashes on bad input; flaky or fake tests (tests that assert nothing real).
- Over-engineering: code or layers the prototype doesn't need.

## Report format
For each finding: severity (blocker / major / minor), owner (backend / voice / frontend / contracts), file:line,
the concrete failure (input → wrong result), suggested fix in words. Start the report with a 5-line summary:
what ran, what passed, what failed. If something is fine, say so plainly.
