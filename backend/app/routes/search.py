import logging

from flask import Blueprint, jsonify, request

from app.adapters import get_adapter
from app.adapters.base import AdapterFetchError, AdapterSchemaError

logger = logging.getLogger(__name__)

bp = Blueprint("search", __name__)


@bp.get("/search")
def search():
    """Live search against one source — no watch/persistence yet.

    Defaults reproduce the doc's own MVP success criteria: a used 2023
    Tesla Model 3 within 25 miles of Dedham, MA. e.g.:

        GET /search
        GET /search?zip=02026&range=25&year_min=2023&drivetrain=RWD
    """
    source = request.args.get("source", "tesla")
    filters = {
        "model": request.args.get("model", "model3"),
        "condition": request.args.get("condition", "used"),
        "zip": request.args.get("zip", "02026"),
        "range": int(request.args.get("range", 25)),
        "count": int(request.args.get("count", 24)),
    }

    try:
        adapter = get_adapter(source)
    except KeyError as exc:
        return jsonify({"error": str(exc)}), 404

    try:
        raw_listings = adapter.fetch(filters)
    except AdapterFetchError as exc:
        logger.warning("Adapter fetch failed for source=%s: %s", source, exc)
        return jsonify({"error": "upstream_unavailable", "detail": str(exc)}), 502
    except AdapterSchemaError as exc:
        logger.error("Adapter schema drift for source=%s: %s", source, exc)
        return jsonify({"error": "adapter_schema_drift", "detail": str(exc)}), 500

    year_min = request.args.get("year_min", type=int)
    year_max = request.args.get("year_max", type=int)
    drivetrain = request.args.get("drivetrain")

    listings = []
    for raw in raw_listings:
        try:
            normalized = adapter.normalize(raw)
        except AdapterSchemaError as exc:
            logger.error("Skipping listing that failed to normalize: %s", exc)
            continue

        year = normalized["attrs"].get("year")
        if year_min and year and year < year_min:
            continue
        if year_max and year and year > year_max:
            continue
        if drivetrain and normalized["attrs"].get("drivetrain") != drivetrain:
            continue

        listings.append(
            {
                "id": adapter.get_stable_id(raw),
                **normalized,
                "seller": adapter.get_seller(raw),
            }
        )

    return jsonify({"source": source, "count": len(listings), "listings": listings})
