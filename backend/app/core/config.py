from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    app_name: str
    debug: bool
    port: int
    frontend_origin: str
    qdrant_url: str
    postgres_dsn: str
    object_storage_bucket: str
    object_storage_root: Path


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    configured_root = os.getenv("OBJECT_STORAGE_ROOT", "uploads")
    storage_root = Path(configured_root)
    if not storage_root.is_absolute():
        storage_root = BASE_DIR / storage_root

    return Settings(
        app_name=os.getenv("APP_NAME", "CareerMatch API"),
        debug=os.getenv("FLASK_DEBUG", "0") == "1",
        port=int(os.getenv("PORT", "5000")),
        frontend_origin=os.getenv("FRONTEND_ORIGIN", "http://localhost:3000"),
        qdrant_url=os.getenv("QDRANT_URL", "http://localhost:6333"),
        postgres_dsn=os.getenv(
            "POSTGRES_DSN",
            "postgresql://careermatch:careermatch@localhost:5432/careermatch",
        ),
        object_storage_bucket=os.getenv("OBJECT_STORAGE_BUCKET", "careermatch-resumes"),
        object_storage_root=storage_root.resolve(),
    )