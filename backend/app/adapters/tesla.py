import json
import logging

import requests

from app.adapters.base import AdapterFetchError, AdapterSchemaError

logger = logging.getLogger(__name__)

INVENTORY_URL = "https://www.tesla.com/inventory/api/v4/inventory-results"

# Public filter vocabulary (matches the watch filter schema in the spec,
# e.g. hard.model = "model3") mapped to Tesla's internal query codes.
MODEL_CODES = {
    "model3": "m3",
    "modely": "my",
    "models": "ms",
    "modelx": "mx",
}

# Real browser-like headers — the endpoint is protected by Akamai and can
# reject requests that don't look like they came from a browser tab that
# actually loaded tesla.com first. Even with these, expect occasional
# blocks; see Section 15/17 of the product doc.
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.tesla.com",
}


class TeslaInventoryAdapter:
    source_key = "tesla"
    recommended_poll_interval_minutes = 20

    def fetch(self, filters: dict) -> list[dict]:
        model_key = filters.get("model", "model3")
        model = MODEL_CODES.get(model_key, "m3")
        query = {
            "query": {
                "model": model,
                "condition": filters.get("condition", "used"),
                "options": {},
                "arrangeby": "Price",
                "order": "asc",
                "market": "US",
                "language": "en",
                "super_region": "north america",
                "zip": filters.get("zip", "02026"),
                "range": filters.get("range", 25),
            },
            "offset": 0,
            "count": filters.get("count", 24),
            "outsideOffset": 0,
            "outsideSearch": False,
        }
        # Tesla's endpoint doesn't expose a documented year/drivetrain param;
        # the filter/match engine (Phase 1) applies those against `attrs`
        # after normalization instead of here.

        try:
            response = requests.get(
                INVENTORY_URL,
                params={"query": json.dumps(query)},
                headers=REQUEST_HEADERS,
                timeout=15,
            )
        except requests.RequestException as exc:
            raise AdapterFetchError(f"Tesla inventory request failed: {exc}") from exc

        if response.status_code != 200:
            snippet = response.text[:300].replace("\n", " ")
            raise AdapterFetchError(
                f"Tesla inventory returned HTTP {response.status_code}: {snippet}"
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise AdapterSchemaError(
                f"Tesla inventory response wasn't JSON: {response.text[:300]!r}"
            ) from exc

        if "results" not in payload or not isinstance(payload["results"], list):
            raise AdapterSchemaError(
                "Tesla inventory response is missing a 'results' list — "
                f"top-level keys were: {list(payload.keys())}. "
                "Tesla's response shape may have changed; update the adapter."
            )

        if payload["results"]:
            logger.info(
                "Tesla inventory sample result keys: %s",
                list(payload["results"][0].keys()),
            )

        # Tag each raw result with the model code it was fetched under, so
        # normalize() can build an accurate deep link without needing the
        # original filters passed back in.
        for result in payload["results"]:
            result["_requested_model"] = model_key

        return payload["results"]

    def get_stable_id(self, raw: dict) -> str:
        vin = raw.get("VIN")
        if not vin:
            raise AdapterSchemaError(
                f"Tesla listing missing VIN — keys were: {list(raw.keys())}"
            )
        return vin

    def normalize(self, raw: dict) -> dict:
        vin = self.get_stable_id(raw)
        price = raw.get("Price") or raw.get("PurchasePrice") or raw.get("InventoryPrice")
        if price is None:
            raise AdapterSchemaError(
                f"Tesla listing {vin} missing a price field — keys were: {list(raw.keys())}"
            )

        year = raw.get("Year") or raw.get("year")
        trim = raw.get("TrimName") or raw.get("Trim")
        drivetrain = raw.get("DrivetrainOptions") or raw.get("Drivetrain")
        title_parts = [str(part) for part in (year, trim) if part]
        title = " ".join(title_parts) or f"Tesla ({vin})"

        return {
            "price": price,
            "title": title,
            "attrs": {
                "year": year,
                "trim": trim,
                "drivetrain": drivetrain,
                "odometer": raw.get("Odometer"),
                "color": raw.get("PAINT") or raw.get("Color"),
            },
            "location": {
                "city": raw.get("City"),
                "state": raw.get("StateProvince") or raw.get("State"),
                "zip": raw.get("Zip") or raw.get("PostalCode"),
            },
            # Best-effort deep link — verify against a real response and
            # correct once Akamai stops blocking this sandbox's requests.
            "url": (
                f"https://www.tesla.com/"
                f"{MODEL_CODES.get(raw.get('_requested_model', 'model3'), 'm3')}"
                f"/order/{vin}"
            ),
            "seller_id": "tesla-direct",
        }

    def get_seller(self, raw: dict) -> dict:
        return {
            "is_official_source": True,
            "display_name": "Tesla",
            "rating": None,
            "review_count": None,
            "sale_count": None,
        }
