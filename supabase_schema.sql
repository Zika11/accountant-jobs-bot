-- إنشاء جدول الوظائف مع عمود المصدر
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
  source text default 'unknown',   -- العمود الجديد
  status text default 'pending',
  notified boolean default false,
  created_at timestamptz default now()
);

-- إضافة العمود إذا كان الجدول موجوداً مسبقاً
alter table jobs add column if not exists source text default 'unknown';

-- باقي الجداول والإندكسات كما هي
create table if not exists settings (
  key text primary key,
  value text
);

create index if not exists idx_jobs_status on jobs (status);
create index if not exists idx_jobs_notified on jobs (notified);
create index if not exists idx_jobs_source on jobs (source);  -- إندكس جديد للمصدر
