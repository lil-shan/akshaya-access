# 03 — Voice: fix review round 1

Read `/home/shan/devin/reviews/2026-11-21-round1.md` and the new section **"Rules added after review round 1"** in
`/home/shan/devin/contracts/README.md` (plus the updated `tools-api.yaml`: handoff `case_number`, `InvalidRequest`).

Fix the findings owned by **voice**: #1, #3, #5, #8, #9, #13, #15, #17, #20. Decisions:
- #1: consent = a whole, unambiguous affirmative reply only. Add tests that corrections/negations never start a fetch or payment.
- #3: post only normalized citizen meanings (see contract). Keep audio mode — the team will demo it with Sarvam —
  but never post/print raw text of unrecognized speech. Say in the opening that speech is processed by a speech service.
- #5: if TTS or playback of the opening or a read-back fails, do not listen for consent; hand off or end safely.
- #9: do not promise anything the prototype doesn't do. Read the handoff `case_number` aloud digit by digit.
- `/end`: the backend now decides payment outcomes; send `payment_*` outcomes only when a payment exists.
Keep fixes small; do not add layers.

## Acceptance (run and report real output)
- `.venv/bin/pytest -q` all pass, with new tests per finding.
- Every script in `voice/scripts/` runs against the live backend (same shell command as the server) and ends as expected.
- Write `voice/.env.example` (now allowed).
