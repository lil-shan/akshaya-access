# Voice: Malayalam call engine + simulator

The phone conversation for the demo flow in `../PLAN.md`, as a deterministic state machine (no LLM). It talks to the
backend only through `../contracts/tools-api.yaml`. Bills and payments are **SIMULATED**, and the agent says so.

| File | What it is |
|---|---|
| `engine.py` | The call state machine (states = the contract's Call states) |
| `lines.py` | Everything the agent says, Malayalam + English |
| `parsing.py` | Digits (Malayalam/English words, numerals), yes/no, "talk to a person" |
| `backend.py` | HTTP client for the Tools API; HTTP 409 becomes `GuardFailed` |
| `sim.py` | Simulator: interactive, `--script FILE`, `--audio` |
| `sarvam.py` | Sarvam REST adapter (Saaras STT, Bulbul TTS), used only by `--audio` |
| `scripts/` | Demo scripts: `happy_path`, `nothing_due`, `handoff`, `handoff_number_unclear` |

## Install

```
cd voice
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Test (backend mocked)

```
.venv/bin/pytest -q
```

## Run against the backend

Start the backend first (`../backend/README.md`), then:

```
.venv/bin/python sim.py                                  # interactive: type the citizen's lines, Ctrl-D hangs up
.venv/bin/python sim.py --script scripts/happy_path.txt  # fixture 1155432100987, Rs 640
.venv/bin/python sim.py --script scripts/nothing_due.txt # fixture 1150000000000, nothing to pay
.venv/bin/python sim.py --script scripts/handoff.txt     # citizen asks for a person
```

In the happy path the payment stays **pending** until someone plays the bank: press Confirm/Fail in the frontend, or
use the payment id that the simulator prints (`-- note: payment <id> started`):

```
curl -X POST localhost:8000/simulator/payments/<id>/complete -H 'content-type: application/json' -d '{"outcome":"confirmed"}'
```

If nobody does, the agent says the payment is still pending after `PAYMENT_POLL_TIMEOUT_S` and ends the call as
`payment_pending`.

Script files have one citizen line per line; blank lines and lines starting with `#` are skipped. When the lines
run out the citizen has hung up.

## Audio mode

```
export SARVAM_API_KEY=...
.venv/bin/python sim.py --audio
```

Same engine. Each citizen turn: press Enter, speak, press Enter. The recording goes to Saaras (`saaras:v4`, `ml-IN`)
and is deleted; agent lines are spoken with Bulbul (`bulbul:v3`). The opening and the PIN line are spoken in
Malayalam and then English. Needs `arecord`/`aplay` (Linux, `alsa-utils`). Without the key it exits with a message.
**Not tested with a real key**; only the request shapes are tested, against the current docs.sarvam.ai reference.

## Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `BACKEND_URL` | `http://localhost:8000` | Backend Tools API |
| `PAYMENT_POLL_INTERVAL_S` | `2` | Seconds between payment status checks |
| `PAYMENT_POLL_TIMEOUT_S` | `60` | Give up waiting and report pending after this long |
| `CALLER_PHONE` | `+919999904321` | Caller number sent to `POST /calls` (fake demo number) |
| `SARVAM_API_KEY` | none | Only for `--audio` |

## Trust rules in this code

- The opening says it is an AI, that this is a demo with simulated payments, and that it never asks for OTP, PIN or Aadhaar.
- The consumer number is read back digit by digit and the name and amount are read back; each needs an explicit yes.
  An unclear answer is asked once more, then counts as no.
- The citizen is not listened to during or after the PIN step. The PIN goes from the keypad to the bank's 123PAY
  line; no function here takes one.
- If the citizen says 4 or more digits that are not a 13-digit consumer number being collected (it could be a PIN,
  OTP or Aadhaar said by mistake), the line is posted and printed as `[അക്കങ്ങൾ മറച്ചു]` / `[digits hidden]`.
- Payment status is only what `GET /tools/payment_status` returns. Pending is said as pending.
- A backend 409 guard is explained and handed off to a person. It is never retried.
- Two failed number attempts (wrong length, rejected read-back, or no bill found) hand off as `number_unclear`.
