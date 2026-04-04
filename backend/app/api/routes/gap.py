from flask import Blueprint, current_app, jsonify, request

from app.api.routes.filter_payloads import parse_match_filters
from app.core.logging_utils import get_logger
from app.domain.models import serialize

logger = get_logger("api.gap")
gap_bp = Blueprint("gap", __name__)


@gap_bp.post("/report")
def build_gap_report():
    services = current_app.config["services"]
    payload = request.get_json(silent=True) or {}
    resume_id = str(payload.get("resume_id") or "").strip()
    if not resume_id:
        logger.warning("gap.report rejected_missing_resume_id")
        return jsonify({"error": "resume_id is required"}), 400
    top_k = int(payload.get("top_k", 3))
    filters = parse_match_filters(payload)
    logger.info("gap.report requested resume_id=%s top_k=%s filters=%s", resume_id, top_k, filters)

    try:
        report = services.gap_analysis_service.build_report(resume_id, top_k, filters)
    except ValueError as exc:
        logger.warning("gap.report missing_resume resume_id=%s error=%s", resume_id, exc)
        return jsonify({"error": str(exc)}), 404
    except RuntimeError as exc:
        logger.exception("gap.report runtime_error resume_id=%s", resume_id)
        return jsonify({"error": str(exc)}), 502

    logger.info(
        "gap.report success resume_id=%s top_k=%s baseline_roles=%s missing_skills=%s insights=%s",
        resume_id,
        top_k,
        len(report.baseline_roles),
        len(report.missing_skills),
        len(report.insights),
    )
    return jsonify({"report": serialize(report)})
