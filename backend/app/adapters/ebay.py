import base64
import logging
import os
import time

import requests

from app.adapters.base import AdapterFetchError, AdapterSchemaError

logger = logging.getLogger(__name__)

OAUTH_URL = "https://api.ebay.com/identity/v1/oauth2/token"
BROWSE_SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
BROWSE_ITEM_URL = "https://api.ebay.com/buy/browse/v1/item/{item_id}"
OAUTH_SCOPE = "https://api.ebay.com/oauth/api_scope"


class EbayBrowseAdapter:
    source_key = "ebay"
    recommended_poll_interval_minutes = 30

    def __init__(self):
        self._token = None
        self._token_expires_at = 0.0

    def _credentials(self) -> tuple[str, str]:
        client_id = os.environ.get("EBAY_CLIENT_ID")
        client_secret = os.environ.get("EBAY_CLIENT_SECRET")
        if not client_id or not client_secret:
            raise AdapterFetchError(
                "EBAY_CLIENT_ID / EBAY_CLIENT_SECRET are not set. Create a "
                "production keyset at developer.ebay.com and set both — see "
                "docs/search-and-tracking-design.md for the full setup steps."
            )
        return client_id, client_secret

    def _access_token(self) -> str:
        # App-level client-credentials token — no eBay user login involved,
        # since Browse API only reads public listings. Cached until ~60s
        # before it actually expires.
        if self._token and time.time() < self._token_expires_at:
            return self._token

        client_id, client_secret = self._credentials()
        basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

        try:
            response = requests.post(
                OAUTH_URL,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Authorization": f"Basic {basic}",
                },
                data={"grant_type": "client_credentials", "scope": OAUTH_SCOPE},
                timeout=15,
            )
        except requests.RequestException as exc:
            raise AdapterFetchError(f"eBay OAuth token request failed: {exc}") from exc

        if response.status_code != 200:
            raise AdapterFetchError(
                f"eBay OAuth token request returned HTTP {response.status_code}: "
                f"{response.text[:300]}"
            )

        payload = response.json()
        token = payload.get("access_token")
        expires_in = payload.get("expires_in", 7200)
        if not token:
            raise AdapterSchemaError(
                f"eBay OAuth response missing access_token — keys were: {list(payload.keys())}"
            )

        self._token = token
        self._token_expires_at = time.time() + expires_in - 60
        return token

    def fetch(self, filters: dict) -> list[dict]:
        query = (filters.get("q") or "").strip()
        if not query:
            return []

        try:
            response = requests.get(
                BROWSE_SEARCH_URL,
                headers={
                    "Authorization": f"Bearer {self._access_token()}",
                    "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
                },
                params={"q": query, "limit": filters.get("limit", 25)},
                timeout=15,
            )
        except requests.RequestException as exc:
            raise AdapterFetchError(f"eBay Browse API request failed: {exc}") from exc

        if response.status_code != 200:
            raise AdapterFetchError(
                f"eBay Browse API returned HTTP {response.status_code}: "
                f"{response.text[:300]}"
            )

        payload = response.json()
        if "itemSummaries" not in payload and "warnings" not in payload:
            raise AdapterSchemaError(
                "eBay Browse API response missing 'itemSummaries' — response shape "
                f"may have changed. Keys were: {list(payload.keys())}"
            )

        return payload.get("itemSummaries", [])

    def refresh_by_id(self, ids: list[str]) -> list[dict]:
        """Per-item refresh for listing watches. Browse API has no bulk
        get-by-ids endpoint, so this loops — fine at MVP scale, revisit if
        the number of tracked eBay listings grows large enough to matter.
        """
        token = self._access_token()
        results = []
        for item_id in ids:
            try:
                response = requests.get(
                    BROWSE_ITEM_URL.format(item_id=item_id),
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=15,
                )
            except requests.RequestException as exc:
                logger.warning("eBay getItem failed for %s: %s", item_id, exc)
                continue

            if response.status_code != 200:
                logger.warning(
                    "eBay getItem for %s returned HTTP %s: %s",
                    item_id,
                    response.status_code,
                    response.text[:200],
                )
                continue

            results.append(response.json())
        return results

    def get_stable_id(self, raw: dict) -> str:
        item_id = raw.get("itemId")
        if not item_id:
            raise AdapterSchemaError(
                f"eBay listing missing itemId — keys were: {list(raw.keys())}"
            )
        return item_id

    def normalize(self, raw: dict) -> dict:
        item_id = self.get_stable_id(raw)
        price_obj = raw.get("price")
        if not price_obj or "value" not in price_obj:
            raise AdapterSchemaError(
                f"eBay listing {item_id} missing price.value — keys were: {list(raw.keys())}"
            )

        title = raw.get("title")
        if not title:
            raise AdapterSchemaError(f"eBay listing {item_id} missing title")

        location = raw.get("itemLocation", {}) or {}
        seller = raw.get("seller", {}) or {}

        return {
            "price": float(price_obj["value"]),
            "title": title,
            "attrs": {
                "condition": raw.get("condition"),
                "image_url": (raw.get("image") or {}).get("imageUrl"),
            },
            "location": {
                "city": location.get("city"),
                "state": location.get("stateOrProvince"),
                "zip": location.get("postalCode"),
            },
            "url": raw.get("itemWebUrl"),
            "seller_id": seller.get("username"),
        }

    def get_seller(self, raw: dict) -> dict:
        seller = raw.get("seller", {}) or {}
        return {
            "is_official_source": False,
            "display_name": seller.get("username"),
            "rating": seller.get("feedbackPercentage"),
            "review_count": seller.get("feedbackScore"),
            "sale_count": None,
        }
