from uuid import uuid4

from flask import Blueprint, current_app, jsonify, request

from app.clients.document_parser import DocumentParseError
from app.core.logging_utils import get_logger
from app.domain.models import serialize

logger = get_logger("api.resumes")
resumes_bp = Blueprint("resumes", __name__)


@resumes_bp.get("/<resume_id>")
def get_resume(resume_id: str):
    logger.info("resume.get requested resume_id=%s", resume_id)
    services = current_app.config["services"]
    resume = services.resume_pipeline.get_resume(resume_id)
    if resume is None:
        logger.warning("resume.get missing resume_id=%s", resume_id)
        return jsonify({"error": f"Resume '{resume_id}' does not exist."}), 404
    logger.info("resume.get success resume_id=%s name=%s", resume_id, resume.basic_info.name)
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
    logger.info(
        "resume.upload received resume_id=%s file_name=%s has_file=%s raw_text_length=%s",
        resume_id,
        file_name,
        uploaded is not None and bool(uploaded.filename),
        len(raw_text),
    )

    if uploaded is not None and uploaded.filename:
        file_name = uploaded.filename
        file_bytes = uploaded.read()
        logger.info(
            "resume.upload file resume_id=%s file_name=%s content_type=%s bytes=%s",
            resume_id,
            file_name,
            uploaded.mimetype or "application/octet-stream",
            len(file_bytes),
        )
        try:
            resume = services.resume_pipeline.process_uploaded_resume(
                file_name=file_name,
                content_type=uploaded.mimetype or "application/octet-stream",
                file_bytes=file_bytes,
                resume_id=resume_id,
                raw_text=raw_text,
            )
        except DocumentParseError as exc:
            logger.warning("resume.upload parse_error resume_id=%s error=%s", resume_id, exc)
            return jsonify({"error": str(exc)}), 400
        except RuntimeError as exc:
            logger.exception("resume.upload runtime_error resume_id=%s", resume_id)
            return jsonify({"error": str(exc)}), 502
        logger.info(
            "resume.upload success resume_id=%s source=file skills=%s projects=%s",
            resume.id,
            len(resume.skills),
            len(resume.projects),
        )
        return jsonify({"resume": serialize(resume), "resumeId": resume.id})

    if not raw_text:
        logger.warning("resume.upload rejected_missing_content resume_id=%s", resume_id)
        return jsonify({"error": "content is required when no file is uploaded"}), 400

    try:
        resume = services.resume_pipeline.process_resume(
            file_name=file_name,
            raw_text=raw_text,
            resume_id=resume_id,
            source_content_type="text/plain",
        )
    except RuntimeError as exc:
        logger.exception("resume.upload runtime_error resume_id=%s source=text", resume_id)
        return jsonify({"error": str(exc)}), 502

    logger.info(
        "resume.upload success resume_id=%s source=text skills=%s projects=%s",
        resume.id,
        len(resume.skills),
        len(resume.projects),
    )
    return jsonify({"resume": serialize(resume), "resumeId": resume.id})
