from uuid import uuid4

from flask import Blueprint, current_app, jsonify, request

from app.clients.document_parser import DocumentParseError
from app.domain.models import serialize

resumes_bp = Blueprint("resumes", __name__)


@resumes_bp.get("/<resume_id>")
def get_resume(resume_id: str):
    services = current_app.config["services"]
    resume = services.resume_pipeline.get_resume(resume_id)
    if resume is None:
        return jsonify({"error": f"Resume '{resume_id}' does not exist."}), 404
    return jsonify({"resume": serialize(resume)})


@resumes_bp.post("/upload")
def upload_resume():
    services = current_app.config["services"]
    payload = request.get_json(silent=True) or {}
    form_payload = request.form or {}

    file_name = payload.get("file_name") or form_payload.get("file_name") or "uploaded_resume.txt"
    raw_text = (payload.get("content") or form_payload.get("content") or "").strip()
    resume_id = payload.get("resume_id") or form_payload.get("resume_id") or f"resume-{uuid4().hex[:8]}"

    uploaded = request.files.get("file")
    if uploaded is not None and uploaded.filename:
        file_name = uploaded.filename
        file_bytes = uploaded.read()
        try:
            resume = services.resume_pipeline.process_uploaded_resume(
                file_name=file_name,
                content_type=uploaded.mimetype or "application/octet-stream",
                file_bytes=file_bytes,
                resume_id=resume_id,
                raw_text=raw_text,
            )
        except DocumentParseError as exc:
            return jsonify({"error": str(exc)}), 400
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 502
        return jsonify({"resume": serialize(resume), "resumeId": resume.id})

    if not raw_text:
        return jsonify({"error": "content is required when no file is uploaded"}), 400

    try:
        resume = services.resume_pipeline.process_resume(
            file_name=file_name,
            raw_text=raw_text,
            resume_id=resume_id,
            source_content_type="text/plain",
        )
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 502
    return jsonify({"resume": serialize(resume), "resumeId": resume.id})
