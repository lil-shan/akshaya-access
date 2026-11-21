# Contracts — the only interface between frontend, backend and voice

Owned by the orchestrator. Workers read these; they never change them. Request changes under "Needs from others".

## Ports and stack (ideathon prototype)

| Part | Stack | Runs at |
|---|---|---|
| backend | Python 3.12, FastAPI, SQLite file (`backend/data.db`) | `http://localhost:8000` |
| voice | Python 3.12 CLI; Sarvam STT/TTS only in `--audio` mode | talks to `BACKEND_URL` (default `http://localhost:8000`) |
| frontend | Vite + React + TypeScript | `http://localhost:5173`, polls the backend every 1 s |

Backend must allow CORS from `http://localhost:5173`.

## Files
- `tools-api.yaml` — OpenAPI 3.1 for every HTTP endpoint. **Source of truth.**
- `fixtures/bills.json` — the simulated KSEB bills. The backend's simulated biller serves exactly these; voice and frontend tests use them.

## The demo call (sequence)

```
voice                         backend                                frontend (polling)
 │ POST /calls ─────────────► creates call (state=greeting)           shows new call
 │ POST /calls/{id}/events ─► agent_said / citizen_said lines         live transcript
 │ (citizen says number, voice reads it back digit by digit, citizen says yes)
 │ POST /tools/fetch_bill ──► guard: number_confirmed must be true   shows bill (name, amount)
 │   ◄── name, amount, due date (SIMULATED)
 │ (voice reads back name + amount, citizen says yes)
 │ POST /tools/confirm_amount ► marks amount confirmed
 │ POST /tools/start_payment ─► guard: number AND amount confirmed    shows "UPI 123PAY — pending"
 │   ◄── payment_id, status=pending (SIMULATED)
 │ (voice: "you will now enter your UPI PIN on the keypad with your bank; I will not hear it")
 │                                                                   judge clicks Confirm / Fail
 │                            ◄── POST /simulator/payments/{id}/complete
 │ GET /tools/payment_status/{id} (poll every 2 s, max 60 s) ◄─ confirmed | failed | pending
 │ voice reports the result; pending after 60 s is said as pending
 │ POST /calls/{id}/end
 └ any time: POST /tools/handoff (reason) → human case queued        shows handoff
```

## Rules every side must respect
- No endpoint accepts OTP, UPI PIN, Aadhaar or card data. There is deliberately no field for them.
- `caller_phone` is stored and returned **masked** (`******4321`).
- Every response from a simulated integration carries `"simulated": true`; the frontend shows a SIMULATED badge and the voice agent's opening says this is a demo.
- Payment status is only what `GET /tools/payment_status` returns.
- Guard failures return HTTP 409 with `{"error": "guard_failed", "reason": "<code>"}`. Reason codes:
  `number_not_confirmed`, `amount_not_confirmed`, `bill_not_found`, `nothing_due`, `payment_already_started`, `call_ended`.

## Rules added after review round 1 (2026-11-21)
- **Consent is an unambiguous yes.** Voice treats only a whole affirmative reply as consent. Anything qualified,
  mixed or containing a negation/correction ("not correct", "I want to correct it") is NOT consent.
- **Citizen text is never raw.** Voice posts only a normalized meaning for `citizen_said`
  (e.g. "consumer number 1155432100987", "yes", "no", "asked for a person", "[unrecognised speech]").
  The backend also enforces it: in `citizen_said` text/text_en and handoff `note`, every run of 4 or more digits
  (ignoring spaces/dashes between digits) is replaced with `[REDACTED]`, **except** an exact 13-digit consumer number.
  `agent_said` lines are generated from fixed templates and are stored as sent.
- **Duplicate payments:** `payment_already_started` is returned when this call already has a payment, OR when any
  call has a **pending** payment for the same `bill_id`. A bill whose earlier payment is confirmed/failed may be paid
  again (lets the demo replay fixture bills; a real biller would reject a paid bill).
- **Call outcome comes from the payment service.** On `/end`, if the call has a payment, the backend sets
  `outcome` from the payment status (confirmed→`paid`, failed→`payment_failed`, pending→`payment_pending`) and
  ignores any payment outcome the client sent. A client-sent `paid`/`payment_failed`/`payment_pending` without a
  payment is rejected with 409 `payment_outcome_without_payment`. Other outcomes are taken as sent.
  A `state` event with text `ended` behaves exactly like `/end` with outcome `abandoned`.
- **Strict requests, safe errors:** request bodies reject unknown fields. Optional fields may be omitted or `null`.
  Validation errors are HTTP 422 `{"error": "invalid_request", "fields": ["<field name>", ...]}` — never the submitted values.
- **Case numbers are speakable:** each handoff gets `case_number`, a 4-digit string unique among queued cases.

## Phone line via Sarvam Voice Agents (added 2026-11-21)
- The backend also serves a **public phone port 8001** (`backend/public_app.py`, run `uvicorn public_app:app --port 8001`),
  sharing the same database and logic as port 8000. Only port 8001 is exposed to the internet (Tailscale Funnel).
- Port 8001 serves **only**: `GET /health`, `POST /calls`, `POST /calls/{id}/events`, `POST /calls/{id}/end`,
  `POST /tools/fetch_bill`, `POST /tools/confirm_amount`, `POST /tools/start_payment`,
  `GET /tools/payment_status/{id}`, `POST /tools/handoff` — identical request/response shapes to tools-api.yaml.
  It never serves `GET /calls`, `GET /calls/{id}` or `/simulator/*` (those stay on local port 8000).
- Every port-8001 request except `/health` must carry `Authorization: Bearer <PHONE_TOOLS_TOKEN>` (env var; constant-time
  compare). Missing/wrong → 401 `{"error":"unauthorized"}`. If `PHONE_TOOLS_TOKEN` is unset, port 8001 refuses to start.
- Phone calls use `channel: "phone"`. The Sarvam agent configuration is in `sarvam-phone-agent.md`.
