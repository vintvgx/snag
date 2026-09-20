import logging
import os
import re
from urllib.parse import urlsplit, urlunsplit

import requests

from app.adapters.base import AdapterFetchError, AdapterSchemaError

logger = logging.getLogger(__name__)

SERPAPI_URL = "https://serpapi.com/search.json"
PRICE_RE = re.compile(r"[\d,]+\.?\d*")


def _canonicalize(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


class GoogleSerpAdapter:
    """Search-time discovery only, via SerpApi's Google Shopping engine.

    This adapter is NEVER registered with the scheduler and never polled —
    see docs/search-and-tracking-design.md §3/§5. Once a result from here
    is tracked, all future price checks go through GenericURLAdapter
    against the retailer's own page directly, not back through this
    adapter or SerpApi again.
    """

    source_key = "google"
    # Sentinel — this value is meaningless because this adapter is never
    # scheduled for periodic polling. Present only to satisfy the
    # SourceAdapter Protocol's shape.
    recommended_poll_interval_minutes = 0

    def fetch(self, filters: dict) -> list[dict]:
        query = (filters.get("q") or "").strip()
        if not query:
            return []

        api_key = os.environ.get("SERPAPI_KEY")
        if not api_key:
            raise AdapterFetchError(
                "SERPAPI_KEY is not set. Sign up at serpapi.com — see "
                "docs/search-and-tracking-design.md for the full setup steps."
            )

        try:
            response = requests.get(
                SERPAPI_URL,
                params={
                    "engine": "google_shopping",
                    "q": query,
                    "hl": "en",
                    "gl": "us",
                    "api_key": api_key,
                },
                timeout=20,
            )
        except requests.RequestException as exc:
            raise AdapterFetchError(f"SerpApi request failed: {exc}") from exc

        if response.status_code != 200:
            raise AdapterFetchError(
                f"SerpApi returned HTTP {response.status_code}: {response.text[:300]}"
            )

        data = response.json()
        if data.get("error"):
            raise AdapterFetchError(f"SerpApi error: {data['error']}")

        if "shopping_results" not in data:
            status = (data.get("search_metadata") or {}).get("status")
            if status == "Success":
                # A real query can legitimately return zero shopping
                # results (e.g. a very niche/discontinued item) — that's
                # not schema drift.
                return []
            raise AdapterSchemaError(
                "SerpApi response missing 'shopping_results' and didn't report "
                f"a successful search — search_metadata.status was {status!r}. "
                "SerpApi's response shape may have changed."
            )

        return data["shopping_results"]

    def get_stable_id(self, raw: dict) -> str:
        product_id = raw.get("product_id")
        if product_id:
            return f"serp:{product_id}"

        url = raw.get("product_link") or raw.get("link")
        if not url:
            raise AdapterSchemaError(
                f"SerpApi shopping result has neither product_id nor a link — "
                f"keys were: {list(raw.keys())}"
            )
        return _canonicalize(url)

    def normalize(self, raw: dict) -> dict:
        stable_id = self.get_stable_id(raw)

        price = raw.get("extracted_price")
        if price is None:
            price_text = raw.get("price")
            match = PRICE_RE.search(price_text) if price_text else None
            if not match:
                raise AdapterSchemaError(
                    f"SerpApi shopping result {stable_id} has no usable price — "
                    f"price={price_text!r}, extracted_price={raw.get('extracted_price')!r}"
                )
            price = float(match.group().replace(",", ""))

        title = raw.get("title")
        if not title:
            raise AdapterSchemaError(f"SerpApi shopping result {stable_id} missing title")

        url = raw.get("product_link") or raw.get("link")
        if not url:
            raise AdapterSchemaError(f"SerpApi shopping result {stable_id} missing a link")

        return {
            "price": float(price),
            "title": title,
            "attrs": {
                "merchant": raw.get("source"),
                # Product rating, not seller feedback — don't feed this into
                # trust scoring as if it were the latter (see get_seller).
                "product_rating": raw.get("rating"),
                "product_reviews": raw.get("reviews"),
            },
            "location": {"city": None, "state": None, "zip": None},
            "url": url,
            "seller_id": raw.get("source"),
        }

    def get_seller(self, raw: dict) -> dict:
        # SerpApi exposes the merchant name and sometimes a product rating,
        # but no seller feedback score/count — per the non-negotiables,
        # this should render as "Limited trust data" client-side rather
        # than a fabricated score.
        return {
            "is_official_source": False,
            "display_name": raw.get("source"),
            "rating": None,
            "review_count": None,
            "sale_count": None,
        }
