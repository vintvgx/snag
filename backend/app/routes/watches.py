import logging

from flask import Blueprint, jsonify, request

from app.extensions import supabase

logger = logging.getLogger(__name__)

bp = Blueprint("watches", __name__)

VALID_WATCH_TYPES = {"query", "listing"}


@bp.post("/watches")
def create_watch():
    """Create a watch — either a 'query' watch (existing saved-search
    behavior: hard/soft filters, broad polling for new matches) or a
    'listing' watch (tracks one specific listing's price, optionally down
    to a target_price). See docs/search-and-tracking-design.md.

    NOTE: takes user_id directly in the request body for now. There's no
    auth middleware yet (magic-link sign-in is its own unbuilt ticket per
    CLAUDE.md) — swap this for the authenticated session's user id once
    that lands, rather than building a placeholder auth layer here.
    """
    body = request.get_json(force=True, silent=True) or {}

    user_id = body.get("user_id")
    watch_type = body.get("watch_type", "query")
    if not user_id:
        return jsonify({"error": "user_id is required"}), 400
    if watch_type not in VALID_WATCH_TYPES:
        return jsonify({"error": f"watch_type must be one of {sorted(VALID_WATCH_TYPES)}"}), 400

    row = {"user_id": user_id, "watch_type": watch_type, "status": "active"}

    if watch_type == "listing":
        listing_id = body.get("listing_id")
        source = body.get("source")
        if not listing_id or not source:
            return jsonify({"error": "listing_id and source are required for a listing watch"}), 400
        row.update(
            {
                "listing_id": listing_id,
                "source": source,
                "name": body.get("name", "Tracked listing"),
                "target_price": body.get("target_price"),
                "poll_interval_minutes": body.get("poll_interval_minutes", 60),
            }
        )
    else:
        for field in ("source", "name"):
            if not body.get(field):
                return jsonify({"error": f"{field} is required for a query watch"}), 400
        row.update(
            {
                "source": body["source"],
                "name": body["name"],
                "hard_filters": body.get("hard_filters", {}),
                "soft_filters": body.get("soft_filters", {}),
                "poll_interval_minutes": body.get("poll_interval_minutes", 30),
            }
        )

    result = supabase.table("watches").insert(row).execute()
    return jsonify(result.data[0]), 201


@bp.get("/watches")
def list_watches():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    result = supabase.table("watches").select("*").eq("user_id", user_id).execute()
    return jsonify({"watches": result.data})


@bp.patch("/watches/<watch_id>")
def update_watch(watch_id):
    body = request.get_json(force=True, silent=True) or {}
    allowed = {
        "status",
        "target_price",
        "hard_filters",
        "soft_filters",
        "poll_interval_minutes",
        "name",
    }
    updates = {key: value for key, value in body.items() if key in allowed}
    if not updates:
        return jsonify({"error": "no updatable fields provided"}), 400

    result = supabase.table("watches").update(updates).eq("id", watch_id).execute()
    if not result.data:
        return jsonify({"error": "watch not found"}), 404
    return jsonify(result.data[0])


@bp.delete("/watches/<watch_id>")
def delete_watch(watch_id):
    supabase.table("watches").delete().eq("id", watch_id).execute()
    return "", 204
