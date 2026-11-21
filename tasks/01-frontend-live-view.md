# 01 — Frontend: judge-facing live call view

## Goal
A single-page demo screen showing a call as it happens, built only against `/home/shan/devin/contracts/tools-api.yaml`
(read `/home/shan/devin/contracts/README.md` first).

## Requirements
- Vite + React + TypeScript in `frontend/`. Backend URL from `VITE_BACKEND_URL` (default `http://localhost:8000`).
- Poll `GET /calls` and the selected `GET /calls/{id}` every 1 s. Auto-select the newest active call.
- Layout (one screen, laptop projector friendly, large type):
  - Left: list of calls (masked phone, state, start time, outcome).
  - Centre: live transcript — agent vs citizen bubbles, Malayalam text with the English `text_en` below in smaller type.
    Malayalam must render properly (use a font stack that includes Noto Sans Malayalam).
  - Right: step tracker (Greeting → Number confirmed → Bill → Amount confirmed → UPI 123PAY → Result),
    bill card (name, amount ₹, due date, confirmed ✓), payment card (status: pending / confirmed with reference / failed),
    handoff banner if any.
  - A clear **SIMULATED** badge whenever a bill or payment has `simulated: true`.
  - Demo controls on the payment card while status is `pending`: "Bank confirms" / "Bank declines" buttons calling
    `POST /simulator/payments/{id}/complete`. Label them as demo controls.
- Show a visible banner when the backend is unreachable.
- Mock mode `VITE_USE_MOCK=1`: serve a scripted call from local mock data (based on
  `/home/shan/devin/contracts/fixtures/bills.json` values, copied into `frontend/src/mock/`) so the UI can be shown without the backend.
- Keep it small: no state library, no router, no UI framework beyond plain CSS (or CSS modules).

## Acceptance (run and report real output)
1. `cd frontend && npm install && npm run build` succeeds with no TypeScript errors.
2. A few vitest tests for the step-tracker mapping from call state/bill/payment → step, and the SIMULATED badge logic. `npx vitest run` passes.
3. `frontend/README.md`: install, run (`npm run dev`), mock mode.

## Out of scope
Auth, operator workflows, routing, deployment.
