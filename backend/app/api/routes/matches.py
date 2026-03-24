from flask import Blueprint, current_app, jsonify, request

from app.domain.models import serialize

matches_bp = Blueprint("matches", __name__)


@matches_bp.post("/recommend")
def recommend_matches():
    services = current_app.config["services"]
    payload = request.get_json(silent=True) or {}
    resume_id = str(payload.get("resume_id") or "").strip()
    if not resume_id:
        return jsonify({"error": "resume_id is required"}), 400
    top_k = int(payload.get("top_k", 5))

    try:
        matches = services.matching_service.recommend(resume_id, top_k)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 502

    return jsonify({"matches": serialize(matches)})
