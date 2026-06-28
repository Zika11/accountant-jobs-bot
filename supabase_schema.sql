-- شغّل الكود ده مرة واحدة في Supabase: SQL Editor > New query > Run
create table if not exists jobs (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  company text,
  location text,
  posted text,
  experience text,
  min_experience int,
  url text unique not null,
  contact_email text,
  contact_phone text,
  source text default 'unknown',
  status text default 'pending',
  notified boolean default false,
  created_at timestamptz default now()
);

alter table jobs add column if not exists source text default 'unknown';

create table if not exists settings (
  key text primary key,
  value text
);

create table if not exists user_profiles (
  user_id text primary key,
  name text,
  experience_years int default 0,
  skills text[] default '{}',
  preferred_locations text[] default '{}',
  expected_salary int,
  cv_text text,
  cv_file_id text,
  created_at timestamptz default now()
);

create index if not exists idx_jobs_status on jobs (status);
create index if not exists idx_jobs_notified on jobs (notified);
create index if not exists idx_jobs_source on jobs (source);
