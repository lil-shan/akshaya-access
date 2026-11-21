# CRM + automation contract (v1, 2026-11-21)

Owned by the orchestrator. The CRM agent (`crm/`) and the automation agent (`automation/`) build against this. Change requests
come back to the orchestrator. Product rules: `PLAN.md` → "Product direction v3".

## Infrastructure
- Supabase project `akshaya-access` (ref `gpaavgyyslspiagvdkbf`, Mumbai). Credentials in `/home/shan/devin/.cloud.env`
  (git-ignored): `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_DB_PASSWORD`. Never print or commit them.
- Schema lives in `crm/supabase/migrations/` (CRM agent writes and applies it with `npx supabase db push`).
- Storage bucket **`case-files`** (private): generated PDFs, screenshots, captcha media. Paths: `<case_id>/<job_id>/<file>`.
- The CRM web app uses the anon key + Supabase Auth (email/password). The automation worker uses the service-role key (server only).
- **RLS on every table.** Authenticated users: full read/write. Anon: nothing. Service role bypasses RLS.

## Tables (public schema)

| Table | Columns (type) | Notes |
|---|---|---|
| `citizens` | id uuid pk · full_name text · full_name_ml text · phone_masked text · dob date · gender text · address jsonb · aadhaar_last4 text · created_at timestamptz | **Dummy data only.** Never a full Aadhaar/phone. |
| `services` | id text pk (slug) · name text · name_ml text · tier int (1 PDF, 2 portal, 3 API) · submission text (`pdf`, `mock_portal`, `portal_dry_run`, `api`) · fields jsonb · documents jsonb · fee jsonb · active bool · notes text | The **service catalogue**. Seeded by the CRM agent. |
| `cases` | id uuid pk · case_number text unique (6 digits) · citizen_id uuid fk · service_id text fk · status text · channel text (`crm`, `phone`, `whatsapp`) · data jsonb (field values keyed by field `key`) · created_at · updated_at | status: `draft`, `ready`, `running`, `waiting_citizen`, `done`, `failed`, `cancelled` |
| `case_events` | id bigserial · case_id fk · at timestamptz · actor text (`crm_user`, `voice`, `automation`, `system`) · type text · message text · data jsonb | Timeline. **Never contains OTPs or captcha answers.** |
| `documents` | id uuid · case_id fk · kind text · storage_path text · source text (`upload`, `digilocker`, `generated`, `screenshot`) · created_at | |
| `consents` | id uuid · case_id fk · kind text · text text · given_at timestamptz · channel text | Recorded before any automation run. |
| `automation_jobs` | id uuid · case_id fk · kind text (`fill_pdf`, `portal_fill`) · mode text (`mock`, `dry_run`) · status text · result jsonb · error text · worker text · created_at · started_at · finished_at | status: `queued`, `running`, `waiting_input`, `succeeded`, `failed`, `cancelled`. **There is no `live` mode** — nothing is ever submitted on a real portal. |
| `job_prompts` | id uuid · job_id fk · kind text (`otp`, `captcha_audio`, `captcha_image`, `confirm`, `field`) · prompt_text text · prompt_text_ml text · media_path text · status text (`open`, `answered`, `used`, `expired`, `cancelled`) · answer text · expires_at timestamptz · created_at · answered_at | The relay between automation and the citizen (CRM now, voice later). |
| `payments` | id uuid · case_id fk · provider text (`simulated_123pay`, `razorpay_test`, `eko_uat`) · amount_inr int · status text (`pending`, `confirmed`, `failed`) · reference text · created_at | |

Enable Supabase Realtime on `cases`, `case_events`, `automation_jobs`, `job_prompts`.

## Service catalogue: `services.fields` format
```json
[{"key": "claimant_name", "label": "Claimant name", "label_ml": "അപേക്ഷകന്റെ പേര്", "type": "text",
  "required": true, "pattern": null, "ask_ml": "അപേക്ഷകന്റെ മുഴുവൻ പേര് പറയാമോ?", "source": "citizen.full_name"}]
```
`type`: `text`, `date`, `number`, `phone`, `select` (+ `options`), `yesno`, `ifsc`, `account_number`.
`source` (optional): prefill from the citizen record. `ask_ml`: the question the voice agent will ask later.

### Initial services (build first — all work 100% with dummy data)
| id | tier | submission | What automation does |
|---|---|---|---|
| `pmjjby_claim` | 1 | `pdf` | Fill the PMJJBY claim-cum-discharge form PDF + document checklist |
| `pmsby_claim` | 1 | `pdf` | Fill the PMSBY claim form PDF + checklist |
| `edistrict_income_certificate` | 2 | `mock_portal` | Playwright fills a mock e-District income-certificate portal (login with mobile OTP, audio captcha, form, review page) and stops before submit |
| `kseb_bill_payment` | 3 | `api` | Bill fetch (simulated) + payment (simulated 123PAY now; Razorpay test mode later) |

## Job protocol (automation worker ⇄ CRM/voice)
1. CRM (or voice) sets the case to `ready`, records a `consents` row, inserts `automation_jobs` (status `queued`).
2. The worker claims it atomically (`queued` → `running`, sets `worker`, `started_at`), writes `case_events`.
3. When the portal needs input from the citizen, the worker inserts a `job_prompts` row (`open`, `expires_at` = now + 3 min),
   sets the job to `waiting_input` and the case to `waiting_citizen`, then polls/subscribes for the answer.
   - `otp`: prompt_text says which portal sent it and why.
   - `captcha_audio`: `media_path` = the portal's audio captcha file in storage; the citizen listens and answers.
   - `captcha_image`: `media_path` = the captcha image; shown to the citizen (CRM now / WhatsApp later). **Never OCR'd or auto-solved.**
4. Answerer (CRM user acting as the citizen, later the voice agent) sets `answer` + `status='answered'`.
5. The worker uses the answer once, then immediately sets `answer = null`, `status = 'used'`. OTP/captcha answers are never
   logged, never copied into `case_events`, `result` or screenshots metadata.
6. On finish: `succeeded` with `result` = `{"screenshots": [...], "output_pdf": "...", "stopped_before_submit": true, "summary": "..."}`
   (paths in `case-files`), or `failed` with `error`. Case → `done` / `failed`.
7. Expired prompt → job `failed` with error `citizen_input_timeout`.

## v1.1 additions (2026-11-21)
- **Required-field check:** before any job touches a portal/PDF, the worker validates `cases.data` against `services.fields`
  (required + pattern). Missing/invalid → job `failed`, `error = "missing_fields: key1,key2"` (keys only, never values); case → `draft`.
- **DigiLocker (sandbox):** new `automation_jobs.kind = 'digilocker_fetch'` (mode `mock`). Requires a `consents` row with
  `kind='digilocker'`. The worker calls the **API Setu DigiLocker sandbox** (canned data) — or a clearly-labelled local
  simulation if the sandbox needs credentials — and stores each fetched document in `case-files/<case_id>/<job_id>/` with a
  `documents` row (`source='digilocker'`). `result.documents` lists them. No real citizen data, ever.
- **Uploads from the CRM:** authenticated users may upload to `case-files/<case_id>/uploads/<file>` (storage insert policy);
  each upload gets a `documents` row (`source='upload'`). Max 10 MB; pdf/jpg/png only.
- **Captcha audio:** the mock portal speaks its captcha digits using Sarvam Bulbul TTS (cached wav files); the beep fallback
  remains when no key is available.

## v1.2 additions — real-portal dry runs (2026-11-21)
- New services (CRM seeds them; tier 2, `submission = 'portal_dry_run'`):
  - `voter_form6` — ECI new voter registration (voters.eci.gov.in), mobile-OTP login.
  - `thuna_lost_property` — Kerala Police Thuna lost-property / lost-document report, mobile-OTP login.
  Field definitions: the automation agent writes `automation/portals/<service>/fields.json` (catalogue `fields` format);
  the CRM agent seeds `services` from those files.
- **Dry-run only.** `automation_jobs.mode = 'dry_run'`. The worker never clicks a final submit / confirm / e-sign / pay
  control; it stops at the last preview page, screenshots it, and logs out. A code-level click allowlist + tests enforce it.
- **Runtime-only identifiers:** the login mobile number is requested with a `job_prompts` row `kind='field'`
  (prompt_text: "Mobile number registered for this login"), used once, then nulled like an OTP. Never stored in
  `cases.data`, `citizens`, events or results.
- **Who may start a live dry run:** a CRM user, for a case whose citizen is the person at the keyboard/phone (a team member
  using their own number). The CRM shows a confirmation: "This opens the REAL portal and sends a REAL OTP to your phone.
  Nothing will be submitted." Consent row `kind='portal_dry_run'` required.
- Portals whose login needs a password (EPFO) are out of scope for automated dry runs.

## v1.3 additions — payments + real DigiLocker sandbox (2026-11-22)
Keys: `/home/shan/devin/.integrations.env` (git-ignored; names in `integrations.env.example`). Never print/commit values.
If a provider's keys are empty, its adapter runs in a clearly labelled SIMULATED/MOCK mode and says so in `result`.
- `kseb_bill_payment` (submission `api`) is handled by the worker with two job kinds (mode `mock` = provider sandbox/test):
  - `bbps_fetch` — Eko EPS UAT bill fetch by consumer number (local mock server `npx @ekoindia/eps-mock-server` when no keys).
    Result: `{customer_name, amount_inr, due_date, bill_ref, provider, sandbox:true}`; also merged into `cases.data._bill`.
  - `payment_collect` — requires `cases.data._bill` and a consent `kind='payment'` with the amount read back. Creates a
    **Razorpay test-mode Payment Link** (UPI enabled) for exactly that amount → `payments` row `pending`
    (provider `razorpay_test`, reference = link id); result has `short_url`. Worker polls the link status (≤15 min);
    on `paid` → `payments.status='confirmed'`, then calls Eko UAT bill-pay (mock) and records its reference as top-level `result.eko_reference`.
    Never collect more than the fetched amount; never ask for a UPI PIN (citizen pays in their own UPI app).
    Note: test mode only. Going live needs the aggregator model where funds settle to the biller, not to us (RBI PA rules).
- `digilocker_fetch` with keys present: API Setu DigiLocker OAuth 2.0 + PKCE sandbox. The worker creates the consent URL,
  sends it to the citizen as a `job_prompts` row `kind='confirm'` (prompt_text contains the link; CRM shows it as a link/QR),
  waits for the redirect/callback code (a tiny local callback endpoint in the worker), then fetches issued documents.
  Without keys: existing SIMULATED_DIGILOCKER.

## v1.4 — Thuna password login allowed for the account owner (user decision 2026-11-22)
- `thuna_lost_property` dry runs may log in with the citizen's own Thuna **password**, for the account owner only
  (consent kind `portal_dry_run`, same warning modal, plus the line "Your Thuna password will be used once and erased").
- New `job_prompts.kind = 'password'`: CRM renders `<input type="password" autocomplete="off">`, never stores it client-side,
  clears it after send. Worker uses it once and nulls it like an OTP. Never logged, never in events/results/screenshots
  (take no screenshot while the password field is filled).
- Other password-login portals (EPFO) remain out of scope.

## v1.5 — UPI QR demo payments (user decision 2026-11-22: no Razorpay for now)
- If Razorpay keys are empty and `UPI_DEMO_VPA` is set in `.integrations.env`, `payment_collect` uses provider
  **`upi_qr_demo`**: builds `upi://pay?pa=<UPI_DEMO_VPA>&pn=<UPI_DEMO_NAME or "Akshaya Demo">&am=<amount>.00&cu=INR&tn=<"Akshaya demo case " + case_number>&tr=<payment id>`,
  creates the `payments` row (`pending`, provider `upi_qr_demo`, reference = payment id), puts `result.upi_uri`, then polls
  the `payments` row (≤15 min). When a CRM user sets it to `confirmed`, the worker continues to Eko (mock) bill-pay.
- CRM: renders `upi_uri` as a QR + "Open in UPI app" link, labelled **"DEMO ONLY — pays the team's own UPI ID. Never use
  with real citizens."**, plus a **"Mark received (demo)"** button (and "Mark failed") on the pending `upi_qr_demo` payment.
- No VPA and no Razorpay keys → existing SIMULATED_RAZORPAY.
- The amount is always exactly the fetched bill amount; there is no free-text amount anywhere.

## v1.6 — more services + call agent (2026-11-22)
### Service definition files
Each service lives in `automation/portals/<service_id>/service.json` (automation agent writes it):
`{"id","name","name_ml","category","tier","submission","fields":[...],"documents":[...],"fee":{...},"active":true,"notes"}`
(`fields` in the catalogue format; selects must have `options`). `category` ∈ `certificates`, `insurance`, `bills`,
`elections`, `identity`, `police`, `agriculture`, `employment`. The orchestrator seeds them with `scripts/seed_services.py`
(upsert; preserves `active` of existing rows). Existing services get a `service.json` too (same ids).

### New services (all dummy-data testable; nothing submitted)
| id | tier | submission | automation |
|---|---|---|---|
| edistrict_nativity_certificate / _residence_ / _community_ / _relationship_ | 2 | mock_portal | the e-District mock, parameterised by certificate type |
| ksmart_birth_certificate | 2 | mock_portal | a small K-SMART-style mock (mobile OTP + audio captcha) |
| ration_card_add_member | 2 | mock_portal | a small civil-supplies-style mock |
| voter_form8 | 2 | portal_dry_run | ECI portal, same login as Form 6 (shift / correction) |
| kwa_water_bill | 3 | api | Eko BBPS (mock server) like KSEB, water operator |
| pmfby_crop_loss | 1 | pdf | crop-loss intimation form + 72-hour deadline note |
| pan_form49a_prep | 1 | pdf | filled Form 49A-style sheet + checklist (citizen applies on Protean/IT portal) |
| passport_prep | 1 | pdf | application details sheet + documents + appointment checklist |
| epf_withdrawal_prep | 1 | pdf | Form 31/19-style details sheet + checklist (citizen files on EPFO portal) |

### Call agent (`callagent/`, Sarvam)
- Inbound only. Uses the catalogue: picks a service by voice (category → service), asks each field's `ask_ml`
  (prefill from citizen record when known), reads values back digit-by-digit for numbers, records consent by voice
  (`consents.channel='phone'`), creates/updates the case (`channel='phone'`), queues the job, then relays `job_prompts`:
  `otp`/`field`/`password` → asks the caller, answers the prompt, **never writes the spoken value to transcripts/events**
  (transcript shows `[OTP given]`, `[password given]`); `captcha_audio` → plays the portal's audio to the caller, caller
  repeats the characters; `captcha_image` → tells the caller it needs WhatsApp and hands off (not supported by voice yet);
  `confirm` → reads the prompt and asks yes/no.
- Reports the job result by voice (stopped before submit / PDF ready / payment status).
- Speech: Sarvam Saaras (STT, codemix) + Bulbul (TTS); key from `voice/.env` (last `SARVAM_API_KEY=sk_…` line). Text
  simulator mode (no credits) for most tests; a small audio round-trip test budget (≤ 60 Sarvam calls total).
- Talks to Supabase with the service-role key (server-side process), like the worker.
