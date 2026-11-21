alter table automation_jobs drop constraint if exists automation_jobs_kind_check;
alter table automation_jobs add constraint automation_jobs_kind_check check (kind in ('fill_pdf','portal_fill','digilocker_fetch','bbps_fetch','payment_collect'));
do $$ begin alter publication supabase_realtime add table payments; exception when duplicate_object then null; end $$;
