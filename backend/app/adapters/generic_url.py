import json
import logging
from urllib.parse import urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from app.adapters.base import AdapterFetchError, AdapterSchemaError

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (compatible; SnagBot/0.1; +https://github.com/communite/snag) "
)


def _canonicalize(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _first_offer(offers) -> dict | None:
    if isinstance(offers, list):
        return offers[0] if offers else None
    if isinstance(offers, dict):
        return offers
    return None


def _find_product(node):
    """JSON-LD can nest a Product inside @graph, or list several top-level
    objects — walk both shapes looking for the first one typed Product.
    """
    if isinstance(node, list):
        for item in node:
            found = _find_product(item)
            if found:
                return found
        return None

    if not isinstance(node, dict):
        return None

    node_type = node.get("@type")
    types = node_type if isinstance(node_type, list) else [node_type]
    if any(isinstance(t, str) and t.lower() == "product" for t in types):
        return node

    if "@graph" in node:
        return _find_product(node["@graph"])

    return None


class GenericURLAdapter:
    """Refresh-only: given one product URL, extract price/availability from
    the page's own structured data (JSON-LD schema.org/Product first, then
    OpenGraph as a fallback). Used to track any listing that didn't come
    from a source with its own item-lookup API — Google/SerpApi-discovered
    listings once tracked, and seeded specialty-retailer URLs.

    fetch(filters) takes {"url": "..."} — one URL per call, not a search.
    """

    source_key = "web"
    # Deliberately the slowest/most conservative cadence of any source —
    # arbitrary small-retailer HTML is the least standardized, most
    # fragile thing being polled. See docs/search-and-tracking-design.md §5.
    recommended_poll_interval_minutes = 90

    def fetch(self, filters: dict) -> list[dict]:
        url = (filters.get("url") or "").strip()
        if not url:
            return []

        try:
            response = requests.get(
                url,
                headers={"User-Agent": USER_AGENT},
                timeout=15,
            )
        except requests.RequestException as exc:
            raise AdapterFetchError(f"Failed to fetch {url}: {exc}") from exc

        if response.status_code != 200:
            raise AdapterFetchError(
                f"{url} returned HTTP {response.status_code}"
            )

        raw = self._extract(response.text, url)
        if raw is None:
            raise AdapterSchemaError(
                f"No structured price data found at {url} — this page doesn't "
                "expose a JSON-LD Product/Offer or OpenGraph price meta tag, so "
                "Snag can't track its price."
            )

        return [raw]

    def _extract(self, html: str, url: str) -> dict | None:
        soup = BeautifulSoup(html, "html.parser")

        for script in soup.find_all("script", type="application/ld+json"):
            if not script.string:
                continue
            try:
                data = json.loads(script.string)
            except json.JSONDecodeError:
                continue

            product = _find_product(data)
            if not product:
                continue

            offer = _first_offer(product.get("offers"))
            price = (offer or {}).get("price")
            if price is None:
                continue

            seller = (offer or {}).get("seller")
            seller_name = seller.get("name") if isinstance(seller, dict) else None

            return {
                "url": url,
                "title": product.get("name"),
                "price": price,
                "currency": (offer or {}).get("priceCurrency"),
                "availability": (offer or {}).get("availability"),
                "seller_name": seller_name,
                "image": product.get("image"),
            }

        # OpenGraph / product meta-tag fallback.
        def meta(*names):
            for name in names:
                tag = soup.find("meta", property=name) or soup.find("meta", attrs={"name": name})
                if tag and tag.get("content"):
                    return tag["content"]
            return None

        price = meta("product:price:amount", "og:price:amount")
        if price is None:
            return None

        return {
            "url": url,
            "title": meta("og:title"),
            "price": price,
            "currency": meta("product:price:currency", "og:price:currency"),
            "availability": meta("product:availability", "og:availability"),
            "seller_name": None,
            "image": meta("og:image"),
        }

    def get_stable_id(self, raw: dict) -> str:
        return _canonicalize(raw["url"])

    def normalize(self, raw: dict) -> dict:
        stable_id = self.get_stable_id(raw)
        try:
            price = float(str(raw["price"]).replace(",", ""))
        except (KeyError, ValueError, TypeError) as exc:
            raise AdapterSchemaError(
                f"Listing at {stable_id} has an unparseable price: {raw.get('price')!r}"
            ) from exc

        title = raw.get("title")
        if not title:
            raise AdapterSchemaError(f"Listing at {stable_id} missing a title")

        return {
            "price": price,
            "title": title,
            "attrs": {
                "currency": raw.get("currency"),
                "availability": raw.get("availability"),
                "image_url": raw.get("image"),
            },
            "location": {"city": None, "state": None, "zip": None},
            "url": raw["url"],
            "seller_id": raw.get("seller_name") or urlsplit(raw["url"]).netloc,
        }

    def get_seller(self, raw: dict) -> dict:
        seller_name = raw.get("seller_name")
        # No feedback score/count is available from page structured data —
        # per the non-negotiables, this should render as "Limited trust
        # data" client-side rather than a fabricated score.
        return {
            "is_official_source": False,
            "display_name": seller_name or urlsplit(raw["url"]).netloc,
            "rating": None,
            "review_count": None,
            "sale_count": None,
        }
