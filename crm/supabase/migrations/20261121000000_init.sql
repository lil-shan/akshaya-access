-- Akshaya-Access CRM schema (contracts/crm.md). Dummy data only.
create table citizens (
  id uuid primary key default gen_random_uuid(),
  full_name text not null,
  full_name_ml text,
  phone_masked text,
  dob date,
  gender text,
  address jsonb not null default '{}',
  aadhaar_last4 text check (aadhaar_last4 ~ '^[0-9]{4}$'),
  created_at timestamptz not null default now()
);
create table services (
  id text primary key,
  name text not null,
  name_ml text,
  tier int not null check (tier in (1,2,3)),
  submission text not null check (submission in ('pdf','mock_portal','portal_dry_run','api')),
  fields jsonb not null default '[]',
  documents jsonb not null default '[]',
  fee jsonb not null default '{}',
  active boolean not null default true,
  notes text
);
create sequence case_number_seq start 100001;
create table cases (
  id uuid primary key default gen_random_uuid(),
  case_number text not null unique default lpad(nextval('case_number_seq')::text, 6, '0'),
  citizen_id uuid not null references citizens(id),
  service_id text not null references services(id),
  status text not null default 'draft' check (status in ('draft','ready','running','waiting_citizen','done','failed','cancelled')),
  channel text not null default 'crm' check (channel in ('crm','phone','whatsapp')),
  data jsonb not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index on cases(status); create index on cases(service_id); create index on cases(citizen_id);
create function touch_updated_at() returns trigger language plpgsql as $$
begin new.updated_at = now(); return new; end $$;
create trigger cases_touch before update on cases for each row execute function touch_updated_at();

create table case_events (
  id bigserial primary key,
  case_id uuid not null references cases(id) on delete cascade,
  at timestamptz not null default now(),
  actor text not null check (actor in ('crm_user','voice','automation','system')),
  type text not null,
  message text,
  data jsonb not null default '{}'
);
create index on case_events(case_id, at);
create table documents (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references cases(id) on delete cascade,
  kind text not null,
  storage_path text not null,
  source text not null check (source in ('upload','digilocker','generated','screenshot')),
  created_at timestamptz not null default now()
);
create index on documents(case_id);
create table consents (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references cases(id) on delete cascade,
  kind text not null,
  text text not null,
  given_at timestamptz not null default now(),
  channel text not null
);
create index on consents(case_id);
create table automation_jobs (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references cases(id) on delete cascade,
  kind text not null check (kind in ('fill_pdf','portal_fill')),
  mode text not null check (mode in ('mock','dry_run')),
  status text not null default 'queued' check (status in ('queued','running','waiting_input','succeeded','failed','cancelled')),
  result jsonb,
  error text,
  worker text,
  created_at timestamptz not null default now(),
  started_at timestamptz,
  finished_at timestamptz
);
create index on automation_jobs(case_id); create index on automation_jobs(status);
create table job_prompts (
  id uuid primary key default gen_random_uuid(),
  job_id uuid not null references automation_jobs(id) on delete cascade,
  kind text not null check (kind in ('otp','captcha_audio','captcha_image','confirm','field')),
  prompt_text text,
  prompt_text_ml text,
  media_path text,
  status text not null default 'open' check (status in ('open','answered','used','expired','cancelled')),
  answer text,
  expires_at timestamptz,
  created_at timestamptz not null default now(),
  answered_at timestamptz
);
create index on job_prompts(job_id); create index on job_prompts(status);
create table payments (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references cases(id) on delete cascade,
  provider text not null check (provider in ('simulated_123pay','razorpay_test','eko_uat')),
  amount_inr int not null,
  status text not null default 'pending' check (status in ('pending','confirmed','failed')),
  reference text,
  created_at timestamptz not null default now()
);
create index on payments(case_id);

-- RLS: authenticated full access, anon none (service role bypasses)
do $$ declare t text; begin
  foreach t in array array['citizens','services','cases','case_events','documents','consents','automation_jobs','job_prompts','payments'] loop
    execute format('alter table %I enable row level security', t);
    execute format('create policy "auth full access" on %I for all to authenticated using (true) with check (true)', t);
  end loop;
end $$;

alter publication supabase_realtime add table cases, case_events, automation_jobs, job_prompts;

-- private storage bucket
insert into storage.buckets (id, name, public) values ('case-files','case-files',false) on conflict (id) do nothing;
create policy "auth read case-files" on storage.objects for select to authenticated using (bucket_id = 'case-files');
