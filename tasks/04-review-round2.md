# 04 — Review round 2 (check the round-1 fixes)

Round 1 report: `/home/shan/devin/reviews/2026-11-21-round1.md`. Since then the contract gained
"Rules added after review round 1" (`/home/shan/devin/contracts/README.md`) and backend, voice and frontend were changed
to fix the findings. You must not change any code. Write `reviews/2026-11-21-round2.md`.

## Do
1. For each round-1 finding (#1–#20): read the cited code now and mark it **fixed / partly fixed / not fixed / regressed**,
   with file:line evidence in one or two lines. Focus hardest on the blockers #1–#4.
2. Check the new contract rules are met end to end (consent, citizen-text redaction, duplicate pending payments,
   outcome from the payment service, strict 422 bodies without submitted values, case_number) across all three parts.
3. One live check in ONE shell command: start the backend on 8000 with a fresh DB (`BACKEND_DB_PATH=/tmp/review2.db`; the default data.db holds a stale pending payment), run `voice/scripts/` happy path and handoff script
   with `voice/.venv/bin/python sim.py --script ...`, then `GET /calls/{id}`; confirm no raw citizen text or digits beyond
   the consumer number are stored, and the outcome matches the payment. Stop the server. Do not run the full test suites.
4. List any NEW problems the fixes introduced.

## Report format
Start with a 5-line summary (ship / don't ship for the demo and why). Then a table: finding | owner | status | evidence.
Then new findings with severity, owner, file:line, failure, suggested fix. Keep it under 150 lines.
