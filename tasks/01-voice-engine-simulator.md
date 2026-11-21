# 01 — Voice: Malayalam call engine + text simulator

## Goal
The phone conversation for the demo flow in `/home/shan/devin/PLAN.md` ("Ideathon prototype scope"), talking to the
backend only through `/home/shan/devin/contracts/tools-api.yaml`. Read `/home/shan/devin/contracts/README.md` first.

## Requirements
- Python 3.12. Virtualenv `voice/.venv`, deps in `voice/requirements.txt`. Backend URL from env `BACKEND_URL`
  (default `http://localhost:8000`).
- **Deterministic state machine** (no LLM). States match the contract's Call states. Post every agent line and
  citizen line to `/calls/{id}/events` (Malayalam `text` + English `text_en`), and every state change as `type=state`.
- Opening (Malayalam + English): it is an AI assistant, this is a demo with simulated payments, it will never ask
  for OTP, PIN or Aadhaar.
- Consumer number: accept digits typed or spoken as Malayalam/English digit words (e.g. "ഒന്ന് ഒന്ന് അഞ്ച്…",
  "one one five…", "11554…"). Must be 13 digits. Read back **digit by digit in Malayalam**, ask yes/no.
  Correction → ask again. After 2 failed attempts → `POST /tools/handoff` reason `number_unclear`.
- Yes/no understanding in Malayalam and English (e.g. അതെ, ശരി, ഉവ്വ്, ആം / അല്ല, വേണ്ട, ഇല്ല / yes, no).
  Anything unclear → ask once more, then treat as no.
- After fetch_bill: read back the customer name and amount in Malayalam, ask to confirm, then confirm_amount.
  If amount is 0 → say nothing is due, end call outcome `nothing_due`, do **not** start a payment.
- Payment: start_payment, then say (Malayalam + English) that the citizen will now enter the UPI PIN on the keypad
  with their bank's 123PAY line and that the assistant cannot hear it. Never prompt for, accept or log a PIN.
  Poll payment_status every 2 s up to 60 s (both configurable). Report confirmed (with reference) / failed /
  still pending — pending must be said as pending.
- "Talk to a person" (മനുഷ്യൻ / ആളെ / person / human) at any point → handoff `citizen_request`.
- Handle backend 409 guard responses by explaining and handing off, never by retrying around the guard.
- **Text simulator**: `python sim.py` (interactive: citizen types lines) and `python sim.py --script FILE`
  (non-interactive: one citizen line per line; prints the conversation).
- **Audio mode** `python sim.py --audio`: same engine; Sarvam Saaras STT for citizen audio from the mic and Bulbul
  TTS for agent speech, via the Sarvam REST API with key from env `SARVAM_API_KEY`. Check current Sarvam docs
  (docs.sarvam.ai) for the exact endpoints/models. If the key is missing, exit with a clear message. Keep the
  Sarvam code in one small adapter file. It is fine if audio mode is untested because there is no key.

## Acceptance (run and report real output)
1. `cd voice && .venv/bin/pytest -q` — unit tests with the backend mocked: digit parsing (Malayalam words, English
   words, numerals, wrong length), yes/no parsing, happy path, correction path, 2-failures handoff, nothing_due,
   failed payment, pending-after-timeout, "person" handoff, 409 handling.
2. Scripts in `voice/scripts/` for: happy path (fixture 1155432100987), nothing due (1150000000000), handoff.
3. `voice/README.md`: install, run simulator, run against the backend, env vars.

## Out of scope
Real telephony (Exotel/Plivo), Sarvam Voice Agents platform, LLMs, other languages.
