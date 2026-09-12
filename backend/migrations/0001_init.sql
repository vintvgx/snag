-- Snag — initial schema (matches the data model in CLAUDE.md / the product doc)
-- Run this once in the Supabase SQL editor (Project -> SQL Editor -> New query).

create table public.users (
  id uuid primary key references auth.users(id),
  push_token text,
  created_at timestamptz default now()
);

create table public.watches (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id),
  source text not null,                 -- 'tesla' | 'ebay' | ...
  name text not null,
  hard_filters jsonb not null default '{}',
  soft_filters jsonb not null default '{}',
  poll_interval_minutes int not null default 30,
  status text not null default 'active', -- 'active' | 'paused'
  created_at timestamptz default now()
);

create table public.sources (
  id text primary key,                  -- adapter_key, e.g. 'tesla'
  name text not null,
  base_poll_interval_minutes int not null,
  auth_type text not null,              -- 'none' | 'oauth' | 'api_key'
  rate_limit_policy jsonb
);

create table public.listings (
  id uuid primary key default gen_random_uuid(),
  source_id text not null references public.sources(id),
  external_id text not null,            -- VIN for tesla, itemId for ebay
  raw_payload jsonb not null,
  normalized jsonb not null,            -- {price, title, attrs, location, url, seller_id}
  first_seen_at timestamptz default now(),
  last_seen_at timestamptz default now(),
  last_price numeric,
  unique (source_id, external_id)
);

create table public.sellers (
  id uuid primary key default gen_random_uuid(),
  source_id text not null references public.sources(id),
  external_seller_id text not null,
  display_name text,
  rating numeric,
  review_count int,
  sale_count int,
  is_official_source boolean default false,
  unique (source_id, external_seller_id)
);

create table public.matches (
  id uuid primary key default gen_random_uuid(),
  watch_id uuid not null references public.watches(id),
  listing_id uuid not null references public.listings(id),
  matched_filters jsonb,
  trust_score int,
  price_delta_pct numeric,
  notified_at timestamptz,
  created_at timestamptz default now(),
  unique (watch_id, listing_id)
);

create table public.notification_log (
  id uuid primary key default gen_random_uuid(),
  match_id uuid not null references public.matches(id),
  channel text not null,                -- 'push' | 'email'
  status text not null,                 -- 'sent' | 'failed' | 'pending'
  sent_at timestamptz
);

-- RLS ---------------------------------------------------------------------

alter table public.users enable row level security;
alter table public.watches enable row level security;
alter table public.matches enable row level security;
alter table public.listings enable row level security;
alter table public.sources enable row level security;
alter table public.sellers enable row level security;
alter table public.notification_log enable row level security;

-- Owner-scoped tables: readable/writable only by their own user_id.
create policy "users can view own row" on public.users
  for select using (auth.uid() = id);
create policy "users can update own row" on public.users
  for update using (auth.uid() = id);

create policy "users can view own watches" on public.watches
  for select using (auth.uid() = user_id);
create policy "users can insert own watches" on public.watches
  for insert with check (auth.uid() = user_id);
create policy "users can update own watches" on public.watches
  for update using (auth.uid() = user_id);
create policy "users can delete own watches" on public.watches
  for delete using (auth.uid() = user_id);

create policy "users can view matches for own watches" on public.matches
  for select using (
    exists (
      select 1 from public.watches
      where watches.id = matches.watch_id and watches.user_id = auth.uid()
    )
  );

-- Global read-only reference/inventory tables: any authenticated user can
-- read (inventory is shared across watches), only the Flask service
-- (service-role key, which bypasses RLS entirely) writes to them.
create policy "authenticated users can read sources" on public.sources
  for select using (auth.role() = 'authenticated');
create policy "authenticated users can read listings" on public.listings
  for select using (auth.role() = 'authenticated');
create policy "authenticated users can read sellers" on public.sellers
  for select using (auth.role() = 'authenticated');

-- notification_log has no client-facing policy — service-role only.

-- Seed ----------------------------------------------------------------------

insert into public.sources (id, name, base_poll_interval_minutes, auth_type, rate_limit_policy)
values (
  'tesla',
  'Tesla Used Inventory',
  20,
  'none',
  '{"strategy": "conservative", "notes": "unofficial endpoint, poll politely, back off on 429/403"}'
);
