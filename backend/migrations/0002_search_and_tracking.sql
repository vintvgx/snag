-- Snag — unified search fan-out + per-listing price tracking
-- Run after 0001_init.sql in the Supabase SQL editor.
-- See docs/search-and-tracking-design.md for the design this implements.

alter table public.watches
  add column watch_type text not null default 'query'
    check (watch_type in ('query', 'listing')),
  add column listing_id uuid references public.listings(id),
  add column target_price numeric;

comment on column public.watches.watch_type is
  'query: broad saved-search watch (existing hard/soft filter matching). '
  'listing: tracks the price of one specific listings row.';
comment on column public.watches.listing_id is
  'Set only when watch_type = listing — the exact listing being tracked. '
  'Distinct from matches.listing_id, which records a match after the fact.';
comment on column public.watches.target_price is
  'Set only when watch_type = listing. Null = notify on any price decrease; '
  'set = notify only once the price is at or below this value.';

-- New sources the unified /search fan-out and listing tracking target.
-- 'google' (SerpApi) is deliberately NOT a row here — it's discovery-only
-- and never appears as a listings.source_id; a tracked Google-discovered
-- listing lands under 'web' once GenericURLAdapter takes over polling it
-- directly.
insert into public.sources (id, name, base_poll_interval_minutes, auth_type, rate_limit_policy)
values
  ('ebay', 'eBay Browse API', 30, 'oauth',
   '{"strategy": "standard", "notes": "client-credentials app token, cached until expiry"}'),
  ('amazon', 'Amazon Product Advertising API', 30, 'api_key',
   '{"strategy": "standard", "notes": "PA-API v5, SigV4-signed requests, GetItems batched up to 10 ASINs"}'),
  ('web', 'Generic retailer URL (structured data)', 90, 'none',
   '{"strategy": "conservative", "notes": "per-domain delay; used for Google/SerpApi-discovered and seeded specialty-retailer listings once tracked"}')
on conflict (id) do nothing;

-- Caches one unified /search fan-out per normalized query so repeat
-- searches within the TTL (enforced in application code, currently 1 hour
-- while the new integrations are being validated) don't re-hit paid
-- sources. fetched_at also drives the "last checked" timestamp shown in
-- the client.
create table public.search_cache (
  query_hash text primary key,
  query_text text not null,
  results jsonb not null default '[]',
  sources_status jsonb not null default '{}',
  fetched_at timestamptz not null default now()
);

alter table public.search_cache enable row level security;

-- Same category as listings/sources/sellers: shared, global, read-only for
-- authenticated users; only the Flask service (service-role key) writes.
create policy "authenticated users can read search_cache" on public.search_cache
  for select using (auth.role() = 'authenticated');
