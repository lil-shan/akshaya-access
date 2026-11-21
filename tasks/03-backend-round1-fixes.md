# 03 — Backend: fix review round 1

Read `/home/shan/devin/reviews/2026-11-21-round1.md` and the new section **"Rules added after review round 1"** in
`/home/shan/devin/contracts/README.md` (plus the updated `tools-api.yaml`: `case_number`, `InvalidRequest`,
`payment_outcome_without_payment`, handoff 409).

Fix the findings owned by **backend**: #2, #4, #6, #7, #10, #14, #18 — as the contract rules now specify them.
Also add `case_number` to handoffs. Keep fixes small; do not add layers.

## Acceptance (run and report real output)
- New tests for each finding (assert DB contents and response bodies for redaction; 422 bodies contain no submitted
  values; outcome derived from payment for missing/pending/failed/confirmed; pending payment on the same bill across
  two calls → 409; replay after confirmed allowed; `state=ended` behaves like /end; confirmation tied to the current bill).
- `.venv/bin/pytest -q` all pass. `smoke.sh` exits non-zero on any failed check.
- Write `backend/.env.example` (now allowed).
