from flask import Blueprint, current_app, jsonify, request

from app.domain.models import serialize

gap_bp = Blueprint("gap", __name__)


@gap_bp.post("/report")
def build_gap_report():
    services = current_app.config["services"]
    payload = request.get_json(silent=True) or {}
    resume_id = payload.get("resume_id", "demo-resume")
    top_k = int(payload.get("top_k", 3))

    try:
        report = services.gap_analysis_service.build_report(resume_id, top_k)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404

    return jsonify({"report": serialize(report)})
