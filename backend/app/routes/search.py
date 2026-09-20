import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
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

PER_SOURCE_TIMEOUT_SECONDS = 8

# While we're standing the new integrations up, cap re-fetching the same
# query to once an hour and remember when it last ran (search-and-tracking
# design doc, resolved open question #3) so the client can show a "checked
# N minutes ago" timestamp instead of implying every pull is live.
SEARCH_CACHE_TTL = timedelta(hours=1)


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


def _cached_result(cache_key: str) -> dict | None:
    try:
        resp = (
            supabase.table("search_cache")
            .select("*")
            .eq("query_hash", cache_key)
            .limit(1)
            .execute()
        )
    except Exception:
        logger.exception("search_cache lookup failed; falling back to a live fetch")
        return None

    if not resp.data:
        return None

    row = resp.data[0]
    fetched_at = datetime.fromisoformat(row["fetched_at"].replace("Z", "+00:00"))
    if datetime.now(timezone.utc) - fetched_at >= SEARCH_CACHE_TTL:
        return None
    return row


def _store_cache(cache_key: str, query: str, listings: list[dict], sources_status: dict, fetched_at: str):
    try:
        supabase.table("search_cache").upsert(
            {
                "query_hash": cache_key,
                "query_text": query,
                "results": listings,
                "sources_status": sources_status,
                "fetched_at": fetched_at,
            }
        ).execute()
    except Exception:
        logger.exception("Failed to write search_cache row (non-fatal)")


@bp.get("/search")
def search():
    """Unified search: fans out to eBay, Amazon, and Google (via SerpApi) in
    parallel and returns one merged, source-tagged feed of listings in the
    common {price, title, attrs, location, url, seller_id} shape.

    GET /search?q=fujifilm ga645

    Query params:
      q       free-text query (required for a real result)
      source  force a single adapter instead of the full fan-out — useful
              for testing one integration at a time, e.g. ?source=ebay
      fresh   any truthy value bypasses the hourly cache

    See docs/search-and-tracking-design.md for why Google/SerpApi never
    appears here as anything but a search-time call.
    """
    query = request.args.get("q", "").strip()
    single_source = request.args.get("source")
    sources = [single_source] if single_source else UNIFIED_SOURCES
    filters = {"q": query}

    cache_key = _query_hash(sources, query)

    if not request.args.get("fresh"):
        cached = _cached_result(cache_key)
        if cached:
            return jsonify(
                {
                    "query": query,
                    "cached": True,
                    "last_searched_at": cached["fetched_at"],
                    "sources_status": cached["sources_status"],
                    "count": len(cached["results"]),
                    "listings": cached["results"],
                }
            )

    sources_status: dict[str, str] = {}
    all_listings: list[dict] = []

    with ThreadPoolExecutor(max_workers=max(len(sources), 1)) as pool:
        futures = {pool.submit(_fetch_source, source, filters): source for source in sources}
        for future, source in futures.items():
            try:
                listings, error = future.result(timeout=PER_SOURCE_TIMEOUT_SECONDS)
            except FutureTimeoutError:
                sources_status[source] = "timeout"
                continue
            sources_status[source] = error or "ok"
            all_listings.extend(listings)

    all_listings.sort(key=lambda listing: (listing.get("price") is None, listing.get("price")))

    fetched_at = datetime.now(timezone.utc).isoformat()
    _store_cache(cache_key, query, all_listings, sources_status, fetched_at)

    return jsonify(
        {
            "query": query,
            "cached": False,
            "last_searched_at": fetched_at,
            "sources_status": sources_status,
            "count": len(all_listings),
            "listings": all_listings,
        }
    )
