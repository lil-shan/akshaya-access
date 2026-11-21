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
  `portal_dry_run` jobs run `dry_run.py` (see below); `api` jobs are skipped. It starts the mock portal itself if needed.
- Mock portal only: `.venv/bin/python mock_portals/edistrict/server.py 8765`. Flow: mobile -> OTP -> captcha (image + audio) ->
  form -> review with Submit (never clicked). Test hooks: `sms.log` (OTP), `captcha_answer.txt` (test only).
  Audio limitation: no TTS installed, so the audio captcha is one DTMF-style two-tone beep per digit, not speech.
- PDFs: `pdf_filler.py` regenerates PMJJBY/PMSBY claim-cum-discharge forms (the official Jan Suraksha PDFs are flat, not fillable)
  plus a checklist page. Output: `case-files/<case_id>/<job_id>/claim.pdf`.
- Captcha survey: `.venv/bin/python scripts/captcha_survey.py` -> `reports/captcha-survey.md`.

## Tests
- Unit: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q` (the env var avoids ROS pytest plugins on this machine).
- E2E (real Supabase, dummy data, test-only OTP/captcha shortcuts for the mock): `.venv/bin/python scripts/e2e_mock.py`

## Real-portal dry run (contract v1.2)
Services `voter_form6` (ECI) and `thuna_lost_property` (Kerala Police). Specs/notes: `portals/<service>/flow.md` ([seen] vs [assumed]), fields: `portals/<service>/fields.json`.
Engine: `dry_run.py` (`run_dry`), wired in `worker.run_portal_dry`. Needs job `mode='dry_run'` and consent `kind='portal_dry_run'`.
Flow: mobile (prompt kind `field`) -> captcha (audio preferred, image fallback) -> OTP -> fill pages from `cases.data` -> stop at last preview -> screenshot -> log out.
Thuna also needs a password (prompt kind `field`, used once) and has image-only captcha; ECI has an audio captcha. See flow.md.
Human only: `python scripts/dry_run_live.py <case_id> --i-am-the-citizen` (TTY required; run by the person whose phone gets the OTP). Never run by agents/CI.
Safety guarantees (all tested in `tests/test_dry_run.py`, no real portal touched):
- Click allowlist per page + global denylist `submit|confirm|e-?sign|final|pay|register|declare` on the element's text/id/name/value/aria-label/title; a denylisted control is refused even if allowlisted.
- Unknown page -> abort with screenshot. Aadhaar field on a page -> stop ("citizen enters on portal").
- Mobile, password, OTP, captcha values: used once, nulled in `job_prompts` (cancelled sibling prompts too), never in events/results/cases.
- Replay tests serve saved snapshots locally with all non-localhost requests aborted; post-login pages are local [assumed] stand-ins.
