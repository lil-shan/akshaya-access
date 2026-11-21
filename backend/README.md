# Backend: Tools API (SIMULATED KSEB + UPI 123PAY)

Implements `../contracts/tools-api.yaml`. `app.py` holds the routes and guards; `adapters.py` has the `BillerAdapter`
(`SimulatedKSEB`, which serves `../contracts/fixtures/bills.json`) and the `PaymentAdapter` (`SimulatedUPI123Pay`).

- Install: `python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt`
- Run: `.venv/bin/uvicorn app:app --port 8000` (creates `data.db` on startup; `BACKEND_DB_PATH` overrides the path,
  see `.env.example`)
- Run the public phone port too (Sarvam Voice Agents): `PHONE_TOOLS_TOKEN=<token> .venv/bin/uvicorn public_app:app
  --port 8001` — same DB and logic, but only the call-write/tools endpoints, each requiring
  `Authorization: Bearer <PHONE_TOOLS_TOKEN>` (except `/health`). `GET /calls`, `GET /calls/{id}`, `/simulator/*`
  and the API docs stay on local :8000; it refuses to start without the token. Only :8001 may be internet-exposed.
- Test: `.venv/bin/pytest -q`
- Smoke test against a live server: `./smoke.sh` starts its own server on port 8765 (`PORT=` overrides) with a
  throwaway DB, asserts every status/value and exits non-zero on the first failed check.
- Reset demo data: stop the server and delete `data.db`. Delete it too after upgrading (the schema has no migrations).
