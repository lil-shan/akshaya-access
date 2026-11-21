-- v1.6: service categories for grouping in the CRM and the call agent
alter table public.services add column if not exists category text;
create index if not exists services_category_idx on public.services(category);
