from datetime import datetime, timedelta
import hashlib

import pytz
from bson.objectid import ObjectId
from flask import Blueprint, jsonify, session, request, abort

import extensions
from utils.auth_utils import is_admin

api_bp = Blueprint("api", __name__)

TIER_RATE_LIMITS = {
    "free": 20,
    "plus": 300,
}


def users_col():
    return extensions.db.utilisateurs


def messages_col():
    return extensions.db.messages


def groups_col():
    return extensions.db.groups


def api_keys_col():
    return extensions.db.api_keys


TZ_BRUSSELS = pytz.timezone("Europe/Brussels")


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def require_api_key(required_scopes=None):
    if required_scopes is None:
        required_scopes = []

    raw_key = (
        request.headers.get("X-API-Key") or request.args.get("api_key") or ""
    ).strip()

    if not raw_key:
        response = jsonify(
            {
                "ok": False,
                "error": "Missing API key. Provide it via X-API-Key or ?api_key=.",
            }
        )
        response.status_code = 401
        return abort(response)

    key_hash = hash_api_key(raw_key)

    k_col = api_keys_col()
    key_doc = k_col.find_one({"key_hash": key_hash})
    if not key_doc:
        response = jsonify(
            {
                "ok": False,
                "error": "Invalid or revoked API key.",
            }
        )
        response.status_code = 403
        return abort(response)

    key_scopes = key_doc.get("scopes", [])
    for scope in required_scopes:
        if scope not in key_scopes:
            response = jsonify(
                {
                    "ok": False,
                    "error": f"API key does not have required scope '{scope }'.",
                }
            )
            response.status_code = 403
            return abort(response)

    enforce_rate_limit(key_doc)

    k_col.update_one(
        {"_id": key_doc["_id"]},
        {"$set": {"last_used_at": datetime.utcnow()}},
    )

    return key_doc


def dt_to_iso8601(dt):
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=pytz.utc)
    return dt.astimezone(pytz.utc).isoformat()


def enforce_rate_limit(key_doc):
    k_col = api_keys_col()
    now = datetime.utcnow()

    max_per_minute = key_doc.get("rate_limit_per_minute")

    if not isinstance(max_per_minute, int) or max_per_minute <= 0:
        tier = key_doc.get("tier", "free")
        max_per_minute = TIER_RATE_LIMITS.get(tier, TIER_RATE_LIMITS["free"])

    if max_per_minute <= 0:
        return

    window_start = key_doc.get("rate_window_start")
    count = key_doc.get("rate_count", 0)

    if (not window_start) or ((now - window_start).total_seconds() >= 60):
        k_col.update_one(
            {"_id": key_doc["_id"]},
            {
                "$set": {
                    "rate_window_start": now,
                    "rate_count": 1,
                }
            },
        )
        key_doc["rate_window_start"] = now
        key_doc["rate_count"] = 1
        return

    if count >= max_per_minute:
        seconds_passed = (now - window_start).total_seconds()
        retry_after = max(1, 60 - int(seconds_passed))

        resp = jsonify(
            {
                "ok": False,
                "error": "Rate limit exceeded for this API key.",
                "details": {
                    "limit_per_minute": max_per_minute,
                    "retry_after_seconds": retry_after,
                },
            }
        )
        resp.status_code = 429
        resp.headers["Retry-After"] = str(retry_after)
        abort(resp)

    k_col.update_one(
        {"_id": key_doc["_id"]},
        {"$inc": {"rate_count": 1}},
    )
    key_doc["rate_count"] = count + 1


@api_bp.route("/api/admin/messages")
def api_admin_messages():
    if not is_admin():
        abort(403)

    m_col = messages_col()
    author = request.args.get("author", "").strip()
    query = {}
    if author:
        query["author"] = author

    cursor = m_col.find(query).sort("created_at", -1).limit(200)

    messages = []

    for m in cursor:
        created_at = m.get("created_at")
        if created_at:
            local_dt = created_at.replace(tzinfo=pytz.utc).astimezone(TZ_BRUSSELS)
            time_str = local_dt.strftime("%d/%m %H:%M")
        else:
            time_str = ""

        messages.append(
            {
                "id": str(m["_id"]),
                "author": m.get("author"),
                "content": m.get("content"),
                "time": time_str,
                "channel": m.get("channel", "general"),
            }
        )

    return jsonify({"messages": messages})


@api_bp.route("/api/check_ban")
def api_check_ban():

    if "util" not in session:
        return jsonify({"logged_in": False, "banned": False})

    u_col = users_col()
    util = u_col.find_one({"nom": session["util"]})
    if not util:
        session.clear()
        return jsonify({"logged_in": False, "banned": False})

    if util.get("banned", 0) == 1:
        reason = util.get("ban_reason") or "Votre compte a été banni."
        return jsonify({"logged_in": True, "banned": True, "reason": reason})

    return jsonify({"logged_in": True, "banned": False})


@api_bp.route("/api/dev/v1/messages/general")
def api_dev_general_messages():

    key_doc = require_api_key(required_scopes=["read:messages"])
    username = key_doc.get("owner")

    m_col = messages_col()

    try:
        limit = int(request.args.get("limit", 100))
    except ValueError:
        limit = 100
    limit = max(1, min(limit, 500))

    since_str = request.args.get("since", "").strip()
    query = {"channel": "general"}
    if since_str:
        try:
            since_dt = datetime.fromisoformat(since_str)
            if since_dt.tzinfo is None:
                since_dt = since_dt.replace(tzinfo=pytz.utc)
            since_dt = since_dt.astimezone(pytz.utc)
            query["created_at"] = {"$gte": since_dt}
        except Exception:
            pass

    cursor = m_col.find(query).sort("created_at", -1).limit(limit)

    messages = []
    for m in cursor:
        messages.append(
            {
                "id": str(m["_id"]),
                "author": m.get("author"),
                "content": m.get("content"),
                "channel": m.get("channel", "general"),
                "created_at": dt_to_iso8601(m.get("created_at")),
            }
        )

    return jsonify(
        {
            "ok": True,
            "owner": username,
            "messages": messages,
        }
    )


@api_bp.route("/api/dev/v1/messages/group/<group_id>")
def api_dev_group_messages(group_id):
    """
    GET /api/dev/v1/messages/group/<group_id>

    - Auth par clé d'API (read:messages)
    - Vérifie que le owner de la clé est membre du groupe
    - Récupère les messages dont channel = "group:<id>"
    """
    key_doc = require_api_key(required_scopes=["read:messages"])
    username = key_doc.get("owner")

    g_col = groups_col()

    try:
        gid = ObjectId(group_id)
    except Exception:
        group = g_col.find_one({"group_id": group_id})
    else:
        group = g_col.find_one({"_id": gid}) or g_col.find_one({"group_id": group_id})

    if not group:
        resp = jsonify({"ok": False, "error": "Group not found."})
        resp.status_code = 404
        return resp

    members = group.get("members", [])
    if username not in members:
        resp = jsonify({"ok": False, "error": "You are not a member of this group."})
        resp.status_code = 403
        return resp

    m_col = messages_col()

    try:
        limit = int(request.args.get("limit", 100))
    except ValueError:
        limit = 100
    limit = max(1, min(limit, 500))

    since_str = request.args.get("since", "").strip()

    channel_variants = set()

    channel_variants.add(f"group:{group_id }")

    if group.get("_id") is not None:
        channel_variants.add(f"group:{group .get ('_id')}")
        channel_variants.add(f"group:{str (group .get ('_id'))}")

    if group.get("group_id") is not None:
        channel_variants.add(f"group:{group .get ('group_id')}")
        channel_variants.add(f"group:{str (group .get ('group_id'))}")

    or_clauses = [{"channel": ch} for ch in channel_variants]

    msg_query = {"$or": or_clauses}

    if since_str:
        try:
            since_dt = datetime.fromisoformat(since_str)
            if since_dt.tzinfo is None:
                since_dt = since_dt.replace(tzinfo=pytz.utc)
            since_dt = since_dt.astimezone(pytz.utc)
            msg_query["created_at"] = {"$gte": since_dt}
        except Exception:
            pass

    cursor = m_col.find(msg_query).sort("created_at", -1).limit(limit)

    messages = []
    for m in cursor:
        messages.append(
            {
                "id": str(m["_id"]),
                "author": m.get("author"),
                "content": m.get("content"),
                "channel": m.get("channel"),
                "created_at": dt_to_iso8601(m.get("created_at")),
                "participants": m.get("participants", []),
            }
        )

    return jsonify(
        {
            "ok": True,
            "owner": username,
            "group_id": group_id,
            "messages": messages,
        }
    )
