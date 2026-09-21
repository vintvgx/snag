import hashlib
import hmac
import json
import logging
import os
from datetime import datetime, timezone

import requests

from app.adapters.base import AdapterFetchError, AdapterSchemaError

logger = logging.getLogger(__name__)

SERVICE = "ProductAdvertisingAPI"
SEARCH_ITEMS_PATH = "/paapi5/searchitems"
GET_ITEMS_PATH = "/paapi5/getitems"

DEFAULT_HOST = "webservices.amazon.com"
DEFAULT_REGION = "us-east-1"
DEFAULT_MARKETPLACE = "www.amazon.com"

SEARCH_RESOURCES = [
    "ItemInfo.Title",
    "ItemInfo.ByLineInfo",
    "ItemInfo.Features",
    "Offers.Listings.Price",
    "Offers.Listings.Condition",
    "Offers.Listings.MerchantInfo",
    "Images.Primary.Medium",
]


def _sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode(), hashlib.sha256).digest()


def _signing_key(secret_key: str, date_stamp: str, region: str, service: str) -> bytes:
    k_date = _sign(f"AWS4{secret_key}".encode(), date_stamp)
    k_region = _sign(k_date, region)
    k_service = _sign(k_region, service)
    return _sign(k_service, "aws4_request")


class AmazonPAAPIAdapter:
    source_key = "amazon"
    recommended_poll_interval_minutes = 30

    def _config(self) -> dict:
        access_key = os.environ.get("AMAZON_ACCESS_KEY")
        secret_key = os.environ.get("AMAZON_SECRET_KEY")
        partner_tag = os.environ.get("AMAZON_PARTNER_TAG")
        if not access_key or not secret_key or not partner_tag:
            raise AdapterFetchError(
                "AMAZON_ACCESS_KEY / AMAZON_SECRET_KEY / AMAZON_PARTNER_TAG are not "
                "set. PA-API access also requires an Associates account with recent "
                "qualifying sales — see docs/search-and-tracking-design.md for the "
                "full setup steps."
            )
        return {
            "access_key": access_key,
            "secret_key": secret_key,
            "partner_tag": partner_tag,
            "host": os.environ.get("AMAZON_HOST", DEFAULT_HOST),
            "region": os.environ.get("AMAZON_REGION", DEFAULT_REGION),
            "marketplace": os.environ.get("AMAZON_MARKETPLACE", DEFAULT_MARKETPLACE),
        }

    def _signed_request(self, path: str, target: str, body: dict, config: dict) -> dict:
        payload = json.dumps(body)
        amz_date = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        date_stamp = amz_date[:8]
        host = config["host"]
        region = config["region"]

        canonical_headers = (
            f"content-encoding:amz-1.0\n"
            f"content-type:application/json; charset=utf-8\n"
            f"host:{host}\n"
            f"x-amz-date:{amz_date}\n"
            f"x-amz-target:{target}\n"
        )
        signed_headers = "content-encoding;content-type;host;x-amz-date;x-amz-target"
        payload_hash = hashlib.sha256(payload.encode()).hexdigest()
        canonical_request = "\n".join(
            ["POST", path, "", canonical_headers, signed_headers, payload_hash]
        )

        credential_scope = f"{date_stamp}/{region}/{SERVICE}/aws4_request"
        string_to_sign = "\n".join(
            [
                "AWS4-HMAC-SHA256",
                amz_date,
                credential_scope,
                hashlib.sha256(canonical_request.encode()).hexdigest(),
            ]
        )

        signing_key = _signing_key(config["secret_key"], date_stamp, region, SERVICE)
        signature = hmac.new(
            signing_key, string_to_sign.encode(), hashlib.sha256
        ).hexdigest()

        authorization = (
            f"AWS4-HMAC-SHA256 Credential={config['access_key']}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )

        headers = {
            "content-encoding": "amz-1.0",
            "content-type": "application/json; charset=utf-8",
            "host": host,
            "x-amz-date": amz_date,
            "x-amz-target": target,
            "Authorization": authorization,
        }

        try:
            response = requests.post(
                f"https://{host}{path}", headers=headers, data=payload, timeout=15
            )
        except requests.RequestException as exc:
            raise AdapterFetchError(f"Amazon PA-API request failed: {exc}") from exc

        data = response.json() if response.content else {}
        if response.status_code != 200:
            errors = data.get("Errors") if isinstance(data, dict) else None
            message = errors[0].get("Message") if errors else response.text[:300]
            raise AdapterFetchError(
                f"Amazon PA-API returned HTTP {response.status_code}: {message}"
            )

        return data

    def fetch(self, filters: dict) -> list[dict]:
        query = (filters.get("q") or "").strip()
        if not query:
            return []

        config = self._config()
        body = {
            "Keywords": query,
            "PartnerTag": config["partner_tag"],
            "PartnerType": "Associates",
            "Marketplace": config["marketplace"],
            "Resources": SEARCH_RESOURCES,
        }

        data = self._signed_request(SEARCH_ITEMS_PATH, self._target("SearchItems"), body, config)

        search_result = data.get("SearchResult")
        if search_result is None:
            # A query with zero results still returns SearchResult with an
            # empty Items list — a fully-missing key means the response
            # shape isn't what we expect at all.
            raise AdapterSchemaError(
                f"Amazon PA-API response missing 'SearchResult' — keys were: {list(data.keys())}"
            )

        return search_result.get("Items", [])

    def refresh_by_id(self, asins: list[str]) -> list[dict]:
        """Batched per-item refresh for listing watches — PA-API GetItems
        accepts up to 10 ASINs per call, so batch every active Amazon
        listing watch into as few calls as possible.
        """
        if not asins:
            return []

        config = self._config()
        results: list[dict] = []
        for start in range(0, len(asins), 10):
            batch = asins[start : start + 10]
            body = {
                "ItemIds": batch,
                "PartnerTag": config["partner_tag"],
                "PartnerType": "Associates",
                "Marketplace": config["marketplace"],
                "Resources": SEARCH_RESOURCES,
            }
            data = self._signed_request(GET_ITEMS_PATH, self._target("GetItems"), body, config)
            items_result = data.get("ItemsResult")
            if items_result is None:
                logger.warning(
                    "Amazon GetItems response missing 'ItemsResult' for batch %s", batch
                )
                continue
            results.extend(items_result.get("Items", []))
        return results

    @staticmethod
    def _target(operation: str) -> str:
        return f"com.amazon.paapi5.v1.ProductAdvertisingAPIv1.{operation}"

    def get_stable_id(self, raw: dict) -> str:
        asin = raw.get("ASIN")
        if not asin:
            raise AdapterSchemaError(
                f"Amazon item missing ASIN — keys were: {list(raw.keys())}"
            )
        return asin

    def normalize(self, raw: dict) -> dict:
        asin = self.get_stable_id(raw)
        listings = (raw.get("Offers") or {}).get("Listings") or []
        listing = listings[0] if listings else None
        price = ((listing or {}).get("Price") or {}).get("Amount")
        if price is None:
            raise AdapterSchemaError(
                f"Amazon item {asin} has no Offers.Listings[0].Price.Amount — "
                "likely out of stock or a resources mismatch on the request."
            )

        title = (((raw.get("ItemInfo") or {}).get("Title") or {}).get("DisplayValue"))
        if not title:
            raise AdapterSchemaError(f"Amazon item {asin} missing ItemInfo.Title")

        brand = (
            (((raw.get("ItemInfo") or {}).get("ByLineInfo") or {}).get("Brand") or {})
            .get("DisplayValue")
        )
        merchant_name = ((listing or {}).get("MerchantInfo") or {}).get("Name")
        condition = ((listing or {}).get("Condition") or {}).get("Value")
        image_url = (
            (((raw.get("Images") or {}).get("Primary") or {}).get("Medium") or {}).get("URL")
        )

        return {
            "price": float(price),
            "title": title,
            "attrs": {"brand": brand, "condition": condition, "image_url": image_url},
            "location": {"city": None, "state": None, "zip": None},
            "url": raw.get("DetailPageURL"),
            "seller_id": merchant_name or "amazon",
        }

    def get_seller(self, raw: dict) -> dict:
        listings = (raw.get("Offers") or {}).get("Listings") or []
        merchant_name = ((listings[0].get("MerchantInfo") or {}) if listings else {}).get("Name")

        if not merchant_name or merchant_name.lower() == "amazon.com":
            return {
                "is_official_source": True,
                "display_name": "Amazon",
                "rating": None,
                "review_count": None,
                "sale_count": None,
            }

        # PA-API doesn't expose third-party seller feedback score/count —
        # per the non-negotiables, don't invent one.
        return {
            "is_official_source": False,
            "display_name": merchant_name,
            "rating": None,
            "review_count": None,
            "sale_count": None,
        }
