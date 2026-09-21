import hashlib
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request

from app.adapters import get_adapter
from app.adapters.base import AdapterFetchError, AdapterSchemaError
from app.extensions import supabase

logger = logging.getLogger(__name__)

bp = Blueprint("search", __name__)

# Fanned out to on every unified free-text search. 'google' (SerpApi) is
# discovery-only here — it never runs as a background poll job, only from
# this request path. See docs/search-and-tracking-design.md.
UNIFIED_SOURCES = ["ebay", "amazon", "google"]

# How long the request handler waits synchronously before responding, giving
# fast sources (eBay/Amazon — real indexed APIs, typically sub-second) a
# chance to be included in the first response. Google/SerpApi's
# google_shopping engine can take 20-30s on a cold query (it's a live scrape,
# not an index lookup) — this deliberately does NOT wait for it. Slow
# sources keep running in the background pool below and the client picks
# them up on its next poll via `in_progress`.
FAST_WINDOW_SECONDS = 2.5

# While we're standing the new integrations up, cap re-fetching the same
# fully-resolved query to once an hour (search-and-tracking design doc,
# resolved open question #3) so the client can show a "checked N minutes
# ago" timestamp instead of implying every pull is live.
SEARCH_CACHE_TTL = timedelta(hours=1)

# If a search_cache row has been sitting `in_progress` longer than this with
# no update, treat it as abandoned (e.g. a background thread lost to a
# worker restart mid-fetch) rather than waiting on it forever.
STUCK_THRESHOLD = timedelta(minutes=3)

# Deliberately NOT a context-managed `with ThreadPoolExecutor()` — that would
# block the request thread until every submitted task finishes (Python's
# Executor.__exit__ calls shutdown(wait=True) regardless of any shorter
# per-future .result(timeout=) elsewhere), which is exactly what made the
# old implementation take as long as the slowest source no matter what. This
# pool is created once and never shut down, so submitted fetches keep
# running after the request that started them has already responded.
_BACKGROUND_POOL = ThreadPoolExecutor(max_workers=8)

# Serializes read-modify-write updates to the same search_cache row across
# the background threads racing to write their own source's results into it
# (single gunicorn worker at MVP scale — this only needs to guard within one
# process, not across multiple).
_row_locks: dict[str, threading.Lock] = {}
_row_locks_guard = threading.Lock()


def _lock_for(cache_key: str) -> threading.Lock:
    with _row_locks_guard:
        return _row_locks.setdefault(cache_key, threading.Lock())


def _query_hash(sources: list[str], query: str) -> str:
    normalized_query = " ".join(query.strip().lower().split())
    key = f"{','.join(sorted(sources))}:{normalized_query}"
    return hashlib.sha256(key.encode()).hexdigest()


def _fetch_source(source: str, filters: dict) -> tuple[list[dict], str | None]:
    try:
        adapter = get_adapter(source)
    except KeyError as exc:
        return [], str(exc)

    try:
        raw_listings = adapter.fetch(filters)
    except AdapterFetchError as exc:
        logger.warning("Adapter fetch failed for source=%s: %s", source, exc)
        return [], f"unavailable: {exc}"
    except AdapterSchemaError as exc:
        logger.error("Adapter schema drift for source=%s: %s", source, exc)
        return [], f"schema_drift: {exc}"

    listings = []
    for raw in raw_listings:
        try:
            normalized = adapter.normalize(raw)
            listing_id = adapter.get_stable_id(raw)
            seller = adapter.get_seller(raw)
        except AdapterSchemaError as exc:
            logger.error("Skipping %s listing that failed to normalize: %s", source, exc)
            continue

        listings.append({"id": listing_id, "source": source, **normalized, "seller": seller})

    return listings, None


def _get_row(cache_key: str) -> dict | None:
    try:
        resp = (
            supabase.table("search_cache")
            .select("*")
            .eq("query_hash", cache_key)
            .limit(1)
            .execute()
        )
    except Exception:
        logger.exception("search_cache lookup failed")
        return None
    return resp.data[0] if resp.data else None


def _init_row(cache_key: str, query: str, sources: list[str]) -> None:
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        supabase.table("search_cache").upsert(
            {
                "query_hash": cache_key,
                "query_text": query,
                "results": [],
                "sources_status": {source: "pending" for source in sources},
                "fetched_at": now_iso,
            }
        ).execute()
    except Exception:
        logger.exception("Failed to initialize search_cache row (non-fatal)")


def _record_source_result(
    cache_key: str, source: str, listings: list[dict], error: str | None
) -> None:
    """Runs in the background pool once one source's fetch finishes —
    merges just that source's contribution into the shared row without
    clobbering whatever the other in-flight sources have already written.
    """
    with _lock_for(cache_key):
        row = _get_row(cache_key)
        if row is None:
            logger.warning("search_cache row for %s vanished before %s finished", cache_key, source)
            return

        existing = [item for item in row.get("results", []) if item.get("source") != source]
        merged = existing + listings
        merged.sort(key=lambda listing: (listing.get("price") is None, listing.get("price")))

        sources_status = dict(row.get("sources_status") or {})
        sources_status[source] = error or "ok"

        try:
            supabase.table("search_cache").update(
                {
                    "results": merged,
                    "sources_status": sources_status,
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                }
            ).eq("query_hash", cache_key).execute()
        except Exception:
            logger.exception("Failed to record %s result for %s (non-fatal)", source, cache_key)


def _run_and_record(source: str, filters: dict, cache_key: str) -> None:
    listings, error = _fetch_source(source, filters)
    _record_source_result(cache_key, source, listings, error)


def _is_in_progress(sources_status: dict) -> bool:
    return any(status == "pending" for status in sources_status.values())


def _response_from_row(row: dict, cached: bool) -> dict:
    return {
        "query": row["query_text"],
        "cached": cached,
        "in_progress": _is_in_progress(row.get("sources_status") or {}),
        "last_searched_at": row["fetched_at"],
        "sources_status": row.get("sources_status") or {},
        "count": len(row.get("results") or []),
        "listings": row.get("results") or [],
    }


@bp.get("/search")
def search():
    """Unified search: fans out to eBay, Amazon, and Google (via SerpApi).
    eBay/Amazon are real indexed APIs (typically sub-second); Google/SerpApi
    does a live scrape that can take 20-30s on a cold query — this endpoint
    does NOT block the response on it. It waits a short FAST_WINDOW for
    quick sources, then returns whatever's ready with `in_progress: true` if
    anything's still running. Poll the same URL again to pick up the rest;
    slow sources keep running in the background regardless of whether
    anyone's polling and write their result into the shared cache row when
    done, so a second poll (or a completely different client polling the
    same query) sees the update.

    GET /search?q=fujifilm ga645

    Query params:
      q       free-text query (required for a real result)
      source  force a single adapter instead of the full fan-out — useful
              for testing one integration at a time, e.g. ?source=ebay
      fresh   any truthy value forces a brand-new search even if a fully
              resolved, fresh cache entry already exists

    See docs/search-and-tracking-design.md for why Google/SerpApi never
    appears here as anything but a search-time call.
    """
    query = request.args.get("q", "").strip()
    single_source = request.args.get("source")
    sources = [single_source] if single_source else UNIFIED_SOURCES
    filters = {"q": query}

    cache_key = _query_hash(sources, query)
    force_fresh = bool(request.args.get("fresh"))

    row = _get_row(cache_key)

    if row and not force_fresh:
        in_progress = _is_in_progress(row.get("sources_status") or {})
        fetched_at = datetime.fromisoformat(row["fetched_at"].replace("Z", "+00:00"))
        age = datetime.now(timezone.utc) - fetched_at

        if not in_progress and age < SEARCH_CACHE_TTL:
            # Fully resolved and still fresh — serve as-is.
            return jsonify(_response_from_row(row, cached=True))

        if in_progress and age < STUCK_THRESHOLD:
            # A search for this exact query is already running (started by
            # this request or someone else's) — report current progress
            # rather than kicking off duplicate fetches and double-billing
            # SerpApi for the same in-flight query.
            return jsonify(_response_from_row(row, cached=False))

        # Otherwise: resolved-but-stale, or in_progress-but-abandoned. Fall
        # through and start a fresh search.

    _init_row(cache_key, query, sources)
    for source in sources:
        _BACKGROUND_POOL.submit(_run_and_record, source, filters, cache_key)

    time.sleep(FAST_WINDOW_SECONDS)

    row = _get_row(cache_key)
    if row is None:
        # search_cache write failed entirely (e.g. Supabase hiccup) — fail
        # honestly instead of pretending there's a result.
        return jsonify({"error": "search_unavailable"}), 502

    return jsonify(_response_from_row(row, cached=False))
