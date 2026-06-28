-- شغّل الكود ده مرة واحدة في Supabase: SQL Editor > New query > Run
-- (لو كنت شغّلت نسخة قديمة من الملف ده قبل كده، الكود تحت بيضيف الأعمدة الجديدة بأمان من غير ما يمسح بياناتك)

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
  status text default 'pending',     -- pending | saved | ignored | expired
  notified boolean default false,    -- هل البوت بعتها تلقائيًا قبل كده؟
  created_at timestamptz default now()
);

-- لو الجدول كان موجود من قبل من غير الأعمدة الجديدة، نضيفهم هنا
alter table jobs add column if not exists experience text;
alter table jobs add column if not exists min_experience int;

-- جدول صغير لحفظ إعدادات بسيطة زي ملف الـ CV
create table if not exists settings (
  key text primary key,
  value text
);

create index if not exists idx_jobs_status on jobs (status);
create index if not exists idx_jobs_notified on jobs (notified);
