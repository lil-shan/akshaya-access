-- v1.1: CRM uploads + digilocker_fetch jobs
alter table automation_jobs drop constraint if exists automation_jobs_kind_check;
alter table automation_jobs add constraint automation_jobs_kind_check check (kind in ('fill_pdf','portal_fill','digilocker_fetch'));

create policy "auth upload case-files uploads" on storage.objects for insert to authenticated
  with check (bucket_id = 'case-files' and (storage.foldername(name))[2] = 'uploads'
    and (storage.foldername(name))[1] ~ '^[0-9a-f-]{36}$');
