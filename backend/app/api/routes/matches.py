from flask import Blueprint, current_app, jsonify, request

from app.core.logging_utils import get_logger
from app.domain.models import serialize

logger = get_logger("api.matches")
matches_bp = Blueprint("matches", __name__)


@matches_bp.post("/recommend")
def recommend_matches():
    services = current_app.config["services"]
    payload = request.get_json(silent=True) or {}
    resume_id = str(payload.get("resume_id") or "").strip()
    if not resume_id:
        logger.warning("matches.recommend rejected_missing_resume_id")
        return jsonify({"error": "resume_id is required"}), 400
    top_k = int(payload.get("top_k", 5))
    logger.info("matches.recommend requested resume_id=%s top_k=%s", resume_id, top_k)

    try:
        matches = services.matching_service.recommend(resume_id, top_k)
    except ValueError as exc:
        logger.warning("matches.recommend missing_resume resume_id=%s error=%s", resume_id, exc)
        return jsonify({"error": str(exc)}), 404
    except RuntimeError as exc:
        logger.exception("matches.recommend runtime_error resume_id=%s", resume_id)
        return jsonify({"error": str(exc)}), 502

    logger.info(
        "matches.recommend success resume_id=%s top_k=%s returned=%s top_job=%s",
        resume_id,
        top_k,
        len(matches),
        matches[0].job.title if matches else None,
    )
    return jsonify({"matches": serialize(matches)})
