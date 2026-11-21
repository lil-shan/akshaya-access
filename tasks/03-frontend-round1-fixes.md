# 03 — Frontend: fix review round 1

Read `/home/shan/devin/reviews/2026-11-21-round1.md` and the new section **"Rules added after review round 1"** in
`/home/shan/devin/contracts/README.md` (plus the updated `tools-api.yaml`: handoff `case_number`).

Fix the findings owned by **frontend**: #11, #12, #16. Also:
- Show the handoff `case_number`.
- The payment card's status (from `payment`) is the only payment truth; the call `outcome` is shown as
  "at end of call: …" wording, and never contradicts the payment card.
- Mock data must follow the new rules (AI identity + no-OTP/PIN opening, normalized citizen lines, case_number).
Keep fixes small.

## Acceptance (run and report real output)
- `npm run build` and `npx vitest run` pass, with new tests for #11 and #12.
