from app.adapters.tesla import TeslaInventoryAdapter

# Adapter-per-source registry (Section 7 of the product doc). Add eBay etc.
# here in Phase 1 — nothing outside this module should know how a source's
# adapter is constructed.
ADAPTERS = {
    "tesla": TeslaInventoryAdapter(),
}


def get_adapter(source_key: str):
    adapter = ADAPTERS.get(source_key)
    if adapter is None:
        raise KeyError(f"No adapter registered for source '{source_key}'")
    return adapter
