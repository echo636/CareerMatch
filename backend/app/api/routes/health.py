import psycopg
from flask import Blueprint, current_app, jsonify
from qdrant_client import QdrantClient

health_bp = Blueprint("health", __name__)


def _check_postgres(dsn: str) -> str:
    try:
        with psycopg.connect(dsn) as conn:
            conn.execute("SELECT 1")
        return "ok"
    except Exception as exc:
        return f"error: {exc}"


def _check_qdrant(url: str) -> str:
    try:
        client = QdrantClient(url=url, timeout=5)
        client.get_collections()
        return "ok"
    except Exception as exc:
        return f"error: {exc}"


@health_bp.get("/health")
def health_check():
    services = current_app.config["services"]
    settings = services.settings

    pg_status = _check_postgres(settings.postgres_dsn)
    qd_status = _check_qdrant(settings.qdrant_url)

    overall = "ok" if pg_status == "ok" and qd_status == "ok" else "degraded"

    return jsonify(
        {
            "status": overall,
            "app": settings.app_name,
            "ai": {
                "llmProvider": settings.llm_provider,
                "llmModel": settings.qwen_llm_model,
                "embeddingProvider": settings.embedding_provider,
                "embeddingModel": settings.qwen_embedding_model,
            },
            "dependencies": {
                "postgres": pg_status,
                "qdrant": qd_status,
                "objectStorage": "local",
            },
        }
    )
