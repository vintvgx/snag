import logging
import os
import re
from typing import Callable
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup

from app.adapters.base import AdapterFetchError, AdapterSchemaError

logger = logging.getLogger(__name__)

TESLA_BASE_URL = "https://www.tesla.com"
SCRAPER_API_URL = "https://api.scraperapi.com"

HtmlFetcher = Callable[[str], str]

# Public filter vocabulary (matches the watch filter schema in the spec,
# e.g. hard.model = "model3") mapped to Tesla's internal query codes.
MODEL_CODES = {
    "model3": "m3",
    "modely": "my",
    "models": "ms",
    "modelx": "mx",
}

PRICE_RE = re.compile(r"\$([\d,]+)")
CONDITION_RE = re.compile(
    r"^(?P<year>\d{4})\s+(?P<repaired>Repaired\s+)?(?P<label>.+?) with "
    r"(?P<odometer>[\d,]+)\s*mi$"
)
LOCATION_RE = re.compile(r"^Located in (?P<city>.+)$")


def fetch_html_via_scraper_api(target_url: str) -> str:
    """Default HTML transport: a residential-proxy scraping API.

    Tesla's inventory pages (and the internal JSON API behind them) sit
    behind Akamai. Confirmed live, from two different network origins:
    plain `requests`, a Chrome-TLS-impersonated client, and a real headless
    Chromium with full JS execution were ALL denied outright. That rules
    out "need a better fingerprint" — Akamai is blocking by IP/ASN
    reputation, which means any datacenter host (Railway included) hits
    the same wall regardless of client sophistication. This is what
    Railway (and anything else running from a datacenter) should use.
    Swapping providers only means editing this function — the adapter's
    parsing/contract doesn't change.
    """
    api_key = os.environ.get("SCRAPER_API_KEY")
    if not api_key:
        raise AdapterFetchError(
            "SCRAPER_API_KEY is not set. Tesla's inventory pages are "
            "behind Akamai bot protection that blocks direct requests "
            "from datacenter IPs (Railway included) even with a real "
            "headless browser — confirmed live. This adapter fetches "
            "through a residential-proxy scraping API instead; sign up "
            "for one (e.g. scraperapi.com) and set SCRAPER_API_KEY."
        )

    try:
        response = requests.get(
            SCRAPER_API_URL,
            params={
                "api_key": api_key,
                "url": target_url,
                "country_code": "us",
            },
            timeout=60,
        )
    except requests.RequestException as exc:
        raise AdapterFetchError(f"Scraper API request failed: {exc}") from exc

    if response.status_code != 200:
        snippet = response.text[:300].replace("\n", " ")
        raise AdapterFetchError(
            f"Scraper API returned HTTP {response.status_code} for "
            f"{target_url}: {snippet}"
        )

    return response.text


class TeslaInventoryAdapter:
    source_key = "tesla"
    # Car turnover is slow enough that hourly is plenty — also keeps the
    # scraping-API bill trivial at MVP scale (one request per watch/hour).
    recommended_poll_interval_minutes = 60

    def __init__(self, html_fetcher: HtmlFetcher | None = None):
        # Injectable so a non-datacenter caller (e.g. a script running on a
        # home network, where Tesla's Akamai config doesn't block you) can
        # swap in a plain Playwright/requests fetch instead of paying for
        # the scraping API. The parsing/validation below is identical
        # either way — only the transport differs.
        self._html_fetcher = html_fetcher or fetch_html_via_scraper_api

    def fetch(self, filters: dict) -> list[dict]:
        model_key = filters.get("model", "model3")
        model = MODEL_CODES.get(model_key, "m3")
        condition = filters.get("condition", "used")
        target_url = self._build_target_url(model, condition, filters)

        html = self._html_fetcher(target_url)

        if "Access Denied" in html and "edgesuite.net" in html:
            raise AdapterFetchError(
                "Tesla returned an Akamai block page — this fetch strategy "
                "no longer clears their bot protection (proxy tier/region, "
                "IP reputation, or Tesla's detection may have changed)."
            )

        if "inventory-search-app" not in html:
            raise AdapterSchemaError(
                "Response didn't look like a Tesla inventory page at all "
                "(missing the 'inventory-search-app' marker) — either "
                "Tesla changed the page structure or the fetch returned "
                f"something else. First 300 chars: {html[:300]!r}"
            )

        return self._parse_cards(html, model_key)

    def _build_target_url(self, model: str, condition: str, filters: dict) -> str:
        query = urlencode(
            {
                "arrangeby": "plh",
                "zip": filters.get("zip", "02026"),
                "range": filters.get("range", 25),
            }
        )
        return f"{TESLA_BASE_URL}/inventory/{condition}/{model}?{query}"

    def _parse_cards(self, html: str, model_key: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select("article.result.card[data-id]")

        raw_listings = []
        for card in cards:
            vin = card.get("data-id", "").replace(
                "-search-result-container", ""
            ).strip()
            if not vin:
                continue

            trim_el = card.select_one(".trim-name")
            trim = trim_el.get_text(strip=True) if trim_el else None

            price = self._extract_price(card)
            year, odometer, is_repaired, city = self._extract_detail_lines(card)

            if price is None or year is None:
                logger.warning(
                    "Skipping unparseable Tesla card vin=%s price=%s year=%s "
                    "— selectors may need updating for a layout change",
                    vin,
                    price,
                    year,
                )
                continue

            raw_listings.append(
                {
                    "vin": vin,
                    "trim": trim,
                    "price": price,
                    "year": year,
                    "odometer": odometer,
                    "is_repaired": is_repaired,
                    "city": city,
                    "_requested_model": model_key,
                }
            )

        if cards and not raw_listings:
            raise AdapterSchemaError(
                f"Found {len(cards)} Tesla result cards but couldn't parse "
                "price/year out of any of them — Tesla's card markup likely "
                "changed. Update TeslaInventoryAdapter's parsing regexes."
            )

        return raw_listings

    def _extract_price(self, card) -> int | None:
        # The visible cash price lives in this span; the hidden APR-terms
        # tooltip (sibling markup) also contains a "$X down" dollar amount,
        # so we deliberately scope to this element rather than the whole
        # price block to avoid picking up the down-payment figure instead.
        price_el = card.select_one("span.tds-text--medium.tds-text--contrast-high")
        if not price_el:
            return None
        matches = PRICE_RE.findall(price_el.get_text(strip=True))
        if not matches:
            return None
        # Format is "Est $<monthly>/mo financing • $<cash price>" — last
        # match is the total price.
        return int(matches[-1].replace(",", ""))

    def _extract_detail_lines(self, card):
        year = odometer = None
        is_repaired = False
        city = None
        for line_el in card.select("section.card-info-details > div.tds-text--contrast-low"):
            line = line_el.get_text(strip=True)
            cond_match = CONDITION_RE.match(line)
            loc_match = LOCATION_RE.match(line)
            if cond_match:
                year = int(cond_match.group("year"))
                odometer = int(cond_match.group("odometer").replace(",", ""))
                is_repaired = bool(cond_match.group("repaired"))
            elif loc_match:
                city = loc_match.group("city")
        return year, odometer, is_repaired, city

    def get_stable_id(self, raw: dict) -> str:
        vin = raw.get("vin")
        if not vin:
            raise AdapterSchemaError(
                f"Tesla listing missing VIN — keys were: {list(raw.keys())}"
            )
        return vin

    def normalize(self, raw: dict) -> dict:
        vin = self.get_stable_id(raw)
        price = raw.get("price")
        if price is None:
            raise AdapterSchemaError(
                f"Tesla listing {vin} missing a price — keys were: {list(raw.keys())}"
            )

        year = raw.get("year")
        trim = raw.get("trim")
        drivetrain = None
        if trim:
            if "All-Wheel Drive" in trim:
                drivetrain = "AWD"
            elif "Rear-Wheel Drive" in trim:
                drivetrain = "RWD"

        title_parts = [str(part) for part in (year, trim) if part]
        title = " ".join(title_parts) or f"Tesla ({vin})"

        model_key = raw.get("_requested_model", "model3")
        model_code = MODEL_CODES.get(model_key, "m3")

        return {
            "price": price,
            "title": title,
            "attrs": {
                "year": year,
                "trim": trim,
                "drivetrain": drivetrain,
                "odometer": raw.get("odometer"),
                "is_repaired": raw.get("is_repaired", False),
            },
            "location": {
                "city": raw.get("city"),
                "state": None,
                "zip": None,
            },
            # Best-effort deep link — verify against a real fetch once
            # SCRAPER_API_KEY is set; Tesla's used-inventory detail route
            # may differ from this guess.
            "url": f"{TESLA_BASE_URL}/inventory/used/{model_code}/{vin}",
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
