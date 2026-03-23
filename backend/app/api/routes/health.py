from flask import Blueprint, current_app, jsonify

health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
def health_check():
    services = current_app.config["services"]
    return jsonify(
        {
            "status": "ok",
            "app": services.settings.app_name,
            "ai": {
                "llmProvider": services.settings.llm_provider,
                "llmModel": services.settings.qwen_llm_model if services.settings.llm_provider == "qwen" else "mock",
                "embeddingProvider": services.settings.embedding_provider,
                "embeddingModel": services.settings.qwen_embedding_model if services.settings.embedding_provider == "qwen" else "simple-hash",
            },
            "dependencies": {
                "postgres": "planned",
                "qdrant": "planned",
                "objectStorage": "planned",
            },
        }
    )
