from flask import Blueprint, current_app, jsonify

health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
def health_check():
    services = current_app.config["services"]
    return jsonify(
        {
            "status": "ok",
            "app": services.settings.app_name,
            "dependencies": {
                "postgres": "planned",
                "qdrant": "planned",
                "objectStorage": "planned",
            },
        }
    )
