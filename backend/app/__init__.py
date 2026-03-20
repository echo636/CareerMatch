from pathlib import Path

from flask import Flask

from .bootstrap import build_services
from .core.config import get_settings

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional in bare environments
    def load_dotenv(*_args, **_kwargs):
        return False

try:
    from flask_cors import CORS
except ImportError:  # pragma: no cover - optional in bare environments
    def CORS(*_args, **_kwargs):
        return None

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")


def create_app() -> Flask:
    settings = get_settings()
    app = Flask(__name__)
    app.json.ensure_ascii = False
    CORS(
        app,
        resources={
            r"/api/*": {
                "origins": [settings.frontend_origin, "http://127.0.0.1:3000"],
            }
        },
    )
    app.config["services"] = build_services(settings)

    from .api.routes import api_bp

    app.register_blueprint(api_bp, url_prefix="/api")
    return app