from typing import Protocol


class AdapterSchemaError(Exception):
    """Raised when a source's response shape doesn't match what the adapter
    expects. Must fail loudly (alerts the dev) rather than silently mapping
    garbage into normalized listings — see Section 7.1/11 of the product doc.
    """


class AdapterFetchError(Exception):
    """Raised when the upstream source can't be reached at all (network
    error, non-2xx, blocked). Distinct from AdapterSchemaError: this is
    "couldn't ask the question," not "got an answer we didn't expect."
    """


class SourceAdapter(Protocol):
    source_key: str
    recommended_poll_interval_minutes: int

    def fetch(self, filters: dict) -> list[dict]:
        """Hit the source, return raw listings (unparsed dicts)."""
        ...

    def normalize(self, raw: dict) -> dict:
        """Map a raw listing to the common shape:
        {price, title, attrs, location, url, seller_id}
        """
        ...

    def get_stable_id(self, raw: dict) -> str:
        """VIN, itemId, ASIN, etc. — the de-dupe key."""
        ...

    def get_seller(self, raw: dict) -> dict:
        """SellerInfo, or an official-source badge."""
        ...
