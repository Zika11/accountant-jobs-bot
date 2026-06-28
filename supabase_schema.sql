-- ============================================
-- إنشاء الجداول المطلوبة لتشغيل البوت
-- ============================================

-- 1. جدول الوظائف
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
  auto_applied boolean default false,
  salary_min int,
  salary_max int,
  job_type text,
  qualification text,
  created_at timestamptz default now()
);

-- 2. جدول الإعدادات
create table if not exists settings (
  key text primary key,
  value text
);

-- 3. جدول الملفات الشخصية
create table if not exists user_profiles (
  user_id text primary key,
  name text,
  experience_years int default 0,
  skills text[] default '{}',
  preferred_locations text[] default '{}',
  expected_salary int,
  cv_text text,
  cv_file_id text,
  chat_id text,
  phone text,
  email text,
  auto_apply boolean default true,
  created_at timestamptz default now()
);

-- 4. جدول سجلات الأخطاء (للسكرابر)
create table if not exists scraper_logs (
  id uuid primary key default gen_random_uuid(),
  source text,
  error text,
  traceback text,
  timestamp timestamptz default now()
);

-- ============================================
-- إضافة الأعمدة المفقودة (للتحديث)
-- ============================================

-- jobs
alter table jobs add column if not exists salary_min int;
alter table jobs add column if not exists salary_max int;
alter table jobs add column if not exists job_type text;
alter table jobs add column if not exists qualification text;
alter table jobs add column if not exists auto_applied boolean default false;

-- user_profiles
alter table user_profiles add column if not exists chat_id text;
alter table user_profiles add column if not exists phone text;
alter table user_profiles add column if not exists email text;
alter table user_profiles add column if not exists auto_apply boolean default true;

-- ============================================
-- إنشاء الفهارس (لتحسين الأداء)
-- ============================================

create index if not exists idx_jobs_status on jobs (status);
create index if not exists idx_jobs_notified on jobs (notified);
create index if not exists idx_jobs_source on jobs (source);
create index if not exists idx_jobs_created on jobs (created_at);
create index if not exists idx_jobs_status_created on jobs (status, created_at);
create index if not exists idx_jobs_url on jobs (url);
