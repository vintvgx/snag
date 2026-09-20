#!/usr/bin/env python3
"""Personal Tesla inventory watcher — runs on your home network.

Why this exists: Tesla's inventory pages sit behind Akamai bot protection
that blocks any datacenter IP (Railway included), confirmed live even
against a real headless-Chromium render (see app/adapters/tesla.py). Your
home IP doesn't have that problem — your own browser already loads these
pages fine. This script reuses TeslaInventoryAdapter's parsing/validation
but swaps in a local Playwright fetch instead of the scraping-API fetch
Railway uses, and fires a macOS notification when a listing matches your
saved filters for the first time (or its price drops).

This is a standalone personal tool — it does not touch Supabase, Flask,
or the RN app. Nothing here is part of the production watch/match/push
pipeline (that doesn't exist yet); it's just "get me an alert."

Setup (one-time):
    pip install -r scripts/requirements.txt
    playwright install chromium
    cp scripts/watch_config.example.json scripts/watch_config.json
    # edit watch_config.json with your price ceiling / year / drivetrain

Run once (good for cron/launchd, hourly):
    python scripts/tesla_watch.py

Run in a loop (good for an ad-hoc terminal session):
    python scripts/tesla_watch.py --loop

First run: use --headed once so you can see the browser and confirm Tesla
isn't showing an interactive challenge before you trust headless runs.
"""

import argparse
import json
import logging
import subprocess
import sys
import time
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.adapters.base import AdapterFetchError, AdapterSchemaError  # noqa: E402
from app.adapters.tesla import TeslaInventoryAdapter  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("tesla_watch")

SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = SCRIPT_DIR / "watch_config.json"
STATE_PATH = SCRIPT_DIR / ".tesla_watch_state.json"

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)


def fetch_via_playwright(url: str, *, headless: bool) -> str:
    """Local, home-IP fetch — the counterpart to fetch_html_via_scraper_api
    in app/adapters/tesla.py. Prefers the real installed Chrome (closer
    fingerprint to the browser you already use) and falls back to
    Playwright's bundled Chromium if Chrome isn't found.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="chrome", headless=headless)
        except Exception:
            logger.info("System Chrome not found for Playwright, using bundled Chromium")
            browser = p.chromium.launch(headless=headless)

        try:
            context = browser.new_context(
                user_agent=DEFAULT_USER_AGENT,
                viewport={"width": 1280, "height": 900},
            )
            page = context.new_page()
            response = page.goto(url, wait_until="load", timeout=45000)
            page.wait_for_timeout(2000)  # let any late render settle
            status = response.status if response else None
            html = page.content()
        finally:
            browser.close()

    if status and status >= 400:
        raise AdapterFetchError(f"Playwright navigation to {url} returned HTTP {status}")

    return html


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise SystemExit(
            f"Missing {CONFIG_PATH}. Copy watch_config.example.json to "
            "watch_config.json and fill in your search criteria."
        )
    return json.loads(CONFIG_PATH.read_text())


def load_state() -> dict:
    if not STATE_PATH.exists():
        return {}
    return json.loads(STATE_PATH.read_text())


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2))


def matches_filters(normalized: dict, config: dict) -> bool:
    attrs = normalized["attrs"]
    year = attrs.get("year")
    drivetrain = attrs.get("drivetrain")

    year_min = config.get("year_min")
    year_max = config.get("year_max")
    if year_min and year and year < year_min:
        return False
    if year_max and year and year > year_max:
        return False

    wanted_drivetrain = config.get("drivetrain")
    if wanted_drivetrain and drivetrain != wanted_drivetrain:
        return False

    price_max = config.get("price_max")
    if price_max and normalized["price"] > price_max:
        return False

    return True


def notify_macos(title: str, subtitle: str, message: str) -> None:
    script = (
        f'display notification "{message}" with title "{title}" '
        f'subtitle "{subtitle}" sound name "Glass"'
    )
    try:
        subprocess.run(["osascript", "-e", script], check=True)
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        logger.warning("Couldn't fire macOS notification (%s) — printing instead", exc)


def run_once(config: dict, headless: bool) -> None:
    adapter = TeslaInventoryAdapter(
        html_fetcher=lambda url: fetch_via_playwright(url, headless=headless)
    )
    filters = {
        "model": config.get("model", "model3"),
        "condition": config.get("condition", "used"),
        "zip": config.get("zip", "02026"),
        "range": config.get("range", 25),
    }

    try:
        raw_listings = adapter.fetch(filters)
    except AdapterFetchError as exc:
        logger.error("Fetch failed: %s", exc)
        return
    except AdapterSchemaError as exc:
        logger.error("Tesla's page structure may have changed: %s", exc)
        return

    state = load_state()
    matched_count = 0
    new_matches = 0

    for raw in raw_listings:
        try:
            normalized = adapter.normalize(raw)
        except AdapterSchemaError as exc:
            logger.warning("Skipping listing that failed to normalize: %s", exc)
            continue

        if not matches_filters(normalized, config):
            continue

        matched_count += 1
        vin = adapter.get_stable_id(raw)
        price = normalized["price"]
        previous = state.get(vin)

        if previous is None:
            logger.info("NEW MATCH: %s — $%s — %s", vin, price, normalized["url"])
            notify_macos(
                "Snag: Tesla match found",
                normalized["title"],
                f"${price:,} in {normalized['location']['city'] or 'unknown location'} — {normalized['url']}",
            )
            new_matches += 1
        elif previous.get("price") is not None and price < previous["price"]:
            logger.info("PRICE DROP: %s — $%s -> $%s", vin, previous["price"], price)
            notify_macos(
                "Snag: Price drop",
                normalized["title"],
                f"${previous['price']:,} -> ${price:,} — {normalized['url']}",
            )
            new_matches += 1

        state[vin] = {"price": price, "url": normalized["url"]}

    save_state(state)
    logger.info(
        "Checked %d listings, %d matched filters, %d new/changed notifications sent",
        len(raw_listings),
        matched_count,
        new_matches,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--loop", action="store_true", help="Keep running, polling once per hour."
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Show the browser window instead of running headless. Do this "
        "on your first run to confirm Tesla isn't serving a challenge page.",
    )
    args = parser.parse_args()

    config = load_config()

    if args.loop:
        while True:
            run_once(config, headless=not args.headed)
            logger.info("Sleeping 1 hour...")
            time.sleep(3600)
    else:
        run_once(config, headless=not args.headed)


if __name__ == "__main__":
    main()
