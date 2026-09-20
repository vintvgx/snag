from app.adapters.amazon import AmazonPAAPIAdapter
from app.adapters.ebay import EbayBrowseAdapter
from app.adapters.generic_url import GenericURLAdapter
from app.adapters.google_serp import GoogleSerpAdapter
from app.adapters.tesla import TeslaInventoryAdapter

# Adapter-per-source registry (Section 7 of the product doc). Nothing
# outside this module should know how a source's adapter is constructed.
#
# 'google' (GoogleSerpAdapter) is search-only — it's wired into the /search
# fan-out but must never be handed to a scheduler/poll job. 'web'
# (GenericURLAdapter) is the reverse: never used for the free-text /search
# fan-out, only for per-listing refresh once a Google-discovered or seeded
# specialty-retailer URL has been tracked. See
# docs/search-and-tracking-design.md.
ADAPTERS = {
    "tesla": TeslaInventoryAdapter(),  # parked, see CLAUDE.md "Focus pivot"
    "ebay": EbayBrowseAdapter(),
    "amazon": AmazonPAAPIAdapter(),
    "google": GoogleSerpAdapter(),
    "web": GenericURLAdapter(),
}


def get_adapter(source_key: str):
    adapter = ADAPTERS.get(source_key)
    if adapter is None:
        raise KeyError(f"No adapter registered for source '{source_key}'")
    return adapter
