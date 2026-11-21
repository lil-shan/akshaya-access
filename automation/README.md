# automation

Worker + mock portal + PDF filler for Akshaya-Access. Contract: `../contracts/crm.md` ("Job protocol").
Rules: never submit on a real portal, never auto-solve a captcha, OTP/captcha values are never stored or logged.

## Setup
```
python3.12 -m venv .venv && .venv/bin/pip install playwright supabase reportlab pypdf pillow pytest
```
Spoken captcha: `tts.py` (Sarvam Bulbul, cached in mock_portals/edistrict/tts_cache, beep fallback). DigiLocker: `digilocker_sim.py` (SIMULATED_DIGILOCKER). E2E: `scripts/e2e_all.py`.
Chromium comes from `~/.cache/ms-playwright`. Credentials: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` are read from
`automation/.env` or `../.cloud.env` (see `.env.example`). Optional `MOCK_URL` (default `http://127.0.0.1:8765`).

## Run
- Worker: `.venv/bin/python worker.py` (`--once` drains the queue and exits). Handles `pdf` and `mock_portal`;
  `portal_dry_run` fails with a clear error (not built); `api` jobs are skipped. It starts the mock portal itself if needed.
- Mock portal only: `.venv/bin/python mock_portals/edistrict/server.py 8765`. Flow: mobile -> OTP -> captcha (image + audio) ->
  form -> review with Submit (never clicked). Test hooks: `sms.log` (OTP), `captcha_answer.txt` (test only).
  Audio limitation: no TTS installed, so the audio captcha is one DTMF-style two-tone beep per digit, not speech.
- PDFs: `pdf_filler.py` regenerates PMJJBY/PMSBY claim-cum-discharge forms (the official Jan Suraksha PDFs are flat, not fillable)
  plus a checklist page. Output: `case-files/<case_id>/<job_id>/claim.pdf`.
- Captcha survey: `.venv/bin/python scripts/captcha_survey.py` -> `reports/captcha-survey.md`.

## Tests
- Unit: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q` (the env var avoids ROS pytest plugins on this machine).
- E2E (real Supabase, dummy data, test-only OTP/captcha shortcuts for the mock): `.venv/bin/python scripts/e2e_mock.py`
