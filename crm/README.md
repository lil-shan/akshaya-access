# Akshaya-Access CRM

Supabase (schema, RLS, realtime, storage) + a small Vite/React/TS web app. Contract: `../contracts/crm.md`. Dummy data only.

## Setup
1. Credentials live in `../.cloud.env` (git-ignored). Copy URL + anon key into `web/.env.local` (see `web/.env.example`). Never put the service-role key in the web app.
2. Apply the schema (already applied to project `gpaavgyyslspiagvdkbf`):
   `cd crm && npx supabase@latest link --project-ref gpaavgyyslspiagvdkbf && SUPABASE_DB_PASSWORD=... npx supabase@latest db push --yes --linked`
3. Seed services + dummy citizens (re-runnable): `npx supabase@latest db query --linked --yes -f supabase/seed.sql`
4. Create the first login yourself: Supabase dashboard -> Authentication -> Users -> Add user (email + password, tick "Auto Confirm"). Or in the CLI: `npx supabase@latest` has no user-create command, so use the dashboard.
5. Run: `cd web && npm install && npm run dev` (http://localhost:5173). Tests: `npm test`. Build: `npm run build`.

## Notes
- All tables have RLS: signed-in users full access, anon nothing. Bucket `case-files` is private; signed-in users can read.
- "Run automation" records a `consents` row, validates the data, sets the case `ready` and inserts a `queued` `automation_jobs` row (`fill_pdf` for pdf services, else `portal_fill`; mode `mock`).
- The "Citizen prompt" panel answers open `job_prompts`; the answer is written only to `job_prompts.answer`, never to the timeline.
