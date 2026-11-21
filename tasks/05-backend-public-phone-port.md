# 05 — Backend: public phone port 8001 for Sarvam Voice Agents

Read the new section "Phone line via Sarvam Voice Agents" at the end of `/home/shan/devin/contracts/README.md` and implement it.

- `backend/public_app.py` exposing `app`: reuse the existing route handlers/logic from `app.py` (no duplicated business
  logic), include only the listed endpoints, add the bearer-token check, refuse to start without `PHONE_TOOLS_TOKEN`.
- Add `PHONE_TOOLS_TOKEN=` to `backend/.env.example`; document running both ports in `backend/README.md`.
- Tests: token missing/wrong → 401 on each listed endpoint; correct token → works; `/simulator/*`, `GET /calls`,
  `GET /calls/{id}` → 404 on port 8001 app; a call created via 8001 is visible via the 8000 app (same DB).
- Run only the new tests plus one quick existing-suite run. Keep it small.
