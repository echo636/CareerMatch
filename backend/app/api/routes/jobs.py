from flask import Blueprint, current_app, jsonify, request

from app.domain.models import serialize

jobs_bp = Blueprint("jobs", __name__)


@jobs_bp.get("")
def list_jobs():
    services = current_app.config["services"]
    jobs = services.job_pipeline.list_jobs()
    return jsonify({"jobs": serialize(jobs)})


@jobs_bp.post("/import")
def import_jobs():
    services = current_app.config["services"]
    payload = request.get_json(silent=True) or {}
    records = payload.get("jobs") or []
    if not records:
        return jsonify({"error": "jobs is required"}), 400

    try:
        jobs = services.job_pipeline.import_jobs(records)
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 502
    return jsonify({"jobs": serialize(jobs), "count": len(jobs)})
