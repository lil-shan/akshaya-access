# callagent — inbound phone call agent (contract v1.6)

Deterministic state machine, no LLM. Flow: greeting (AI, never asks UPI PIN) -> category -> service (from `services` where
active) -> identify citizen (by phone if known, else name) -> each field's `ask_ml` (prefill from citizen; type/pattern validation;
numbers read back digit by digit; strict whole-word yes) -> summary + voice consent (`consents.channel='phone'`) -> case
(`channel='phone'`) -> job (pdf: fill_pdf/mock, mock_portal: portal_fill/mock, portal_dry_run: portal_fill/dry_run,
api: bbps_fetch, then after amount read-back + `payment` consent: payment_collect) -> relays `job_prompts` -> reports result.

## Run
```
python3.12 -m venv .venv && .venv/bin/pip install supabase httpx pytest numpy sounddevice
.venv/bin/python call.py --text [--phone 9XXXXXXXXX]     # typed citizen
.venv/bin/python call.py --script FILE                   # one citizen line per line, '#' comments
.venv/bin/python call.py --audio                         # mic + speaker, Sarvam Saaras (codemix STT) + Bulbul TTS (needs PortAudio)
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q     # unit tests (Supabase faked, no network)
.venv/bin/python e2e_real.py [income pmjjby kseb]        # REAL Supabase + real worker; rows tagged "E2E " / data._e2e
.venv/bin/python audio_roundtrip.py                      # Sarvam TTS->STT test, hard budget 40 calls
```
A worker (`automation/.venv/bin/python worker.py`) must be running for jobs to progress in real use.

## Env
`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` from `../.cloud.env`; `SARVAM_API_KEY` from `../voice/.env` (last `sk_` line).
Never printed or logged. `--tag-e2e` marks cases `_e2e` for cleanup. `CALLAGENT_TEST_HOOKS=1` (tests only) lets script lines
use `{{SMS_OTP}}` / `{{CAPTCHA_ANSWER}}` from the mock portal files.

## Safety guarantees
- Says it is an AI; never asks for a UPI PIN; asks OTP/password only when the portal's prompt asks.
- OTP / password / captcha / login-mobile (`field`) answers go only into the prompt's `answer`; transcripts show
  `[OTP given]`, `[password given]`, `[captcha answer given]`; events hold normalized meanings, and a scrubber blocks any
  known secret string from events. Values are not read back (secrets). No raw transcripts are stored.
- Consent is recorded before any job; payment consent states the exact fetched amount; amount is read back digit by digit.
- `captcha_image` -> says WhatsApp is needed and hands off. "Talk to a person" / unsupported -> case event + handoff text with no promise.
- Never submits; failures are reported without promises.

## Costs
Text/script modes: no Sarvam calls. Audio: ~1 TTS call per new agent sentence (cached by text hash in `tts_cache/`) and 1 STT
call per caller turn; a typical PDF call is ~40 turns, so the audio round-trip test is capped at 40 calls.
