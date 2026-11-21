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
