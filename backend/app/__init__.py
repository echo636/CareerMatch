from pathlib import Path
from time import perf_counter

from flask import Flask, g, request

from .bootstrap import build_services
from .core.config import get_settings
from .core.logging_utils import configure_logging, get_logger

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


def _mask_dsn(dsn: str) -> str:
    cleaned = (dsn or "").strip()
    if not cleaned or "://" not in cleaned:
        return cleaned or "-"
    scheme, rest = cleaned.split("://", 1)
    if "@" not in rest:
        return cleaned
    credentials, host = rest.rsplit("@", 1)
    if ":" in credentials:
        user = credentials.split(":", 1)[0]
        return f"{scheme}://{user}:***@{host}"
    return f"{scheme}://***@{host}"


def create_app() -> Flask:
    settings = get_settings()
    configure_logging(settings.app_log_dir, settings.app_log_level)
    logger = get_logger("flask")

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

    @app.before_request
    def _log_request_start() -> None:
        g.request_started_at = perf_counter()
        logger.info(
            "request.start method=%s path=%s remote=%s query=%s",
            request.method,
            request.path,
            request.remote_addr,
            request.query_string.decode("utf-8", errors="replace"),
        )

    @app.after_request
    def _log_request_end(response):
        started_at = getattr(g, "request_started_at", None)
        duration_ms = (perf_counter() - started_at) * 1000 if started_at is not None else -1.0
        logger.info(
            "request.end method=%s path=%s status=%s duration_ms=%.1f",
            request.method,
            request.path,
            response.status_code,
            duration_ms,
        )
        return response

    app.config["services"] = build_services(settings)
    services = app.config["services"]
    logger.info(
        "app.initialized app_name=%s llm_provider=%s embedding_provider=%s job_repository=%s resume_repository=%s postgres_dsn=%s log_dir=%s",
        settings.app_name,
        settings.llm_provider,
        settings.embedding_provider,
        type(services.matching_service.job_repository).__name__,
        type(services.resume_pipeline.repository).__name__,
        _mask_dsn(settings.postgres_dsn),
        settings.app_log_dir,
    )

    from .api.routes import api_bp

    app.register_blueprint(api_bp, url_prefix="/api")
    return app
