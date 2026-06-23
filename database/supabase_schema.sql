create extension if not exists pgcrypto;

create table if not exists campus_documents (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  category text not null default 'general',
  content text not null,
  created_at timestamptz not null default now()
);

create table if not exists campus_chunks (
  id uuid primary key default gen_random_uuid(),
  document_id uuid references campus_documents(id) on delete cascade,
  title text not null,
  category text not null default 'general',
  content text not null,
  created_at timestamptz not null default now()
);

create table if not exists admin_notices (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  audience text not null default 'all',
  content text not null,
  deadline date,
  created_at timestamptz not null default now()
);

create table if not exists chat_messages (
  id uuid primary key default gen_random_uuid(),
  user_query text not null,
  intent text not null,
  agent text not null,
  answer jsonb not null,
  created_at timestamptz not null default now()
);

alter table campus_documents enable row level security;
alter table campus_chunks enable row level security;
alter table admin_notices enable row level security;
alter table chat_messages enable row level security;

drop policy if exists "Allow public read documents" on campus_documents;
drop policy if exists "Allow public read chunks" on campus_chunks;
drop policy if exists "Allow public read notices" on admin_notices;
drop policy if exists "Allow public insert documents" on campus_documents;
drop policy if exists "Allow public insert chunks" on campus_chunks;
drop policy if exists "Allow public insert notices" on admin_notices;
drop policy if exists "Allow public insert chats" on chat_messages;

create policy "Allow public read documents"
on campus_documents for select
using (true);

create policy "Allow public read chunks"
on campus_chunks for select
using (true);

create policy "Allow public read notices"
on admin_notices for select
using (true);

create policy "Allow public insert documents"
on campus_documents for insert
with check (true);

create policy "Allow public insert chunks"
on campus_chunks for insert
with check (true);

create policy "Allow public insert notices"
on admin_notices for insert
with check (true);

create policy "Allow public insert chats"
on chat_messages for insert
with check (true);
