# 01 — Backend: Tools API (simulated KSEB + UPI 123PAY)

## Goal
Implement every endpoint in `/home/shan/devin/contracts/tools-api.yaml`, exactly as specified, following
`/home/shan/devin/contracts/README.md`.

## Requirements
- Python 3.12 + FastAPI + SQLite file `backend/data.db` (create on startup). Virtualenv at `backend/.venv`,
  dependencies in `backend/requirements.txt`. Entry point `backend/app.py` exposing `app`.
- CORS: allow `http://localhost:5173`.
- Simulated biller: load bills from `/home/shan/devin/contracts/fixtures/bills.json` (read-only; do not copy or edit it).
  Put it behind a small `BillerAdapter` interface with one `SimulatedKSEB` implementation.
- Simulated UPI 123PAY: `start_payment` creates a payment with status `pending`; it changes only through
  `POST /simulator/payments/{id}/complete`. Behind a `PaymentAdapter` interface with one simulated implementation.
  Confirmed payments get a fake reference like `SIM123PAY-000001`.
- `POST /calls/{id}/events` with `type=state` sets `call.state` to `text` (must be one of the Call state enum values, else 422).
- `caller_phone` is never stored unmasked: mask to `******` + last 4 digits before saving.
- Guards (HTTP 409, body per contract):
  - fetch_bill with `number_confirmed` false → `number_not_confirmed`
  - start_payment when the bill's amount is not confirmed → `amount_not_confirmed`
  - start_payment when amount_inr is 0 → `nothing_due`
  - start_payment twice for the same bill → `payment_already_started`
  - any tool call or event on an ended call → `call_ended`
  - bill_id not belonging to this call → `bill_not_found`
- No field, log line or table may hold OTP, PIN, Aadhaar or card data.

## Acceptance (run these and report the real output)
1. `cd backend && .venv/bin/pytest -q` — tests cover every guard above, masking, and the happy path
   (create call → fetch bill → confirm amount → start payment → simulator confirm → status confirmed). All pass.
2. Start the server `.venv/bin/uvicorn app:app --port 8000`, run the happy path with `curl`, paste the responses, then stop the server.
3. `backend/README.md`: how to install, run, test (5–10 lines).

## Out of scope
Auth, real KSEB/BBPS/NPCI integrations, deployment, WebSockets/SSE (the frontend polls).
