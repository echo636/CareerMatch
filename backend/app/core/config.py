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
    llm_provider: str
    embedding_provider: str
    qdrant_url: str
    postgres_dsn: str
    object_storage_bucket: str
    object_storage_root: Path
    job_seed_path: Path
    job_seed_limit: int | None
    app_state_db_path: Path
    dashscope_api_key: str
    dashscope_base_url: str
    dashscope_timeout_sec: int
    qwen_llm_model: str
    qwen_embedding_model: str
    qwen_embedding_dimensions: int


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    configured_root = os.getenv("OBJECT_STORAGE_ROOT", "uploads")
    storage_root = Path(configured_root)
    if not storage_root.is_absolute():
        storage_root = BASE_DIR / storage_root

    configured_job_seed_path = os.getenv("JOB_DATA_PATH", "data/sample_jobs.json")
    job_seed_path = Path(configured_job_seed_path)
    if not job_seed_path.is_absolute():
        job_seed_path = BASE_DIR / job_seed_path

    configured_job_seed_limit = os.getenv("JOB_DATA_LIMIT", "").strip()
    job_seed_limit = int(configured_job_seed_limit) if configured_job_seed_limit else None

    configured_state_db_path = os.getenv("APP_STATE_DB_PATH", "data/app_state.sqlite3")
    app_state_db_path = Path(configured_state_db_path)
    if not app_state_db_path.is_absolute():
        app_state_db_path = BASE_DIR / app_state_db_path

    return Settings(
        app_name=os.getenv("APP_NAME", "CareerMatch API"),
        debug=os.getenv("FLASK_DEBUG", "0") == "1",
        port=int(os.getenv("PORT", "5000")),
        frontend_origin=os.getenv("FRONTEND_ORIGIN", "http://localhost:3000"),
        llm_provider=os.getenv("LLM_PROVIDER", "mock").strip().lower(),
        embedding_provider=os.getenv("EMBEDDING_PROVIDER", "mock").strip().lower(),
        qdrant_url=os.getenv("QDRANT_URL", "http://localhost:6333"),
        postgres_dsn=os.getenv(
            "POSTGRES_DSN",
            "postgresql://careermatch:careermatch@localhost:5432/careermatch",
        ),
        object_storage_bucket=os.getenv("OBJECT_STORAGE_BUCKET", "careermatch-resumes"),
        object_storage_root=storage_root.resolve(),
        job_seed_path=job_seed_path.resolve(),
        job_seed_limit=job_seed_limit,
        app_state_db_path=app_state_db_path.resolve(),
        dashscope_api_key=os.getenv("DASHSCOPE_API_KEY", "").strip(),
        dashscope_base_url=os.getenv(
            "DASHSCOPE_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        ).rstrip("/"),
        dashscope_timeout_sec=int(os.getenv("DASHSCOPE_TIMEOUT_SEC", "60")),
        qwen_llm_model=os.getenv("QWEN_LLM_MODEL", "qwen-plus-latest").strip(),
        qwen_embedding_model=os.getenv("QWEN_EMBEDDING_MODEL", "text-embedding-v4").strip(),
        qwen_embedding_dimensions=int(os.getenv("QWEN_EMBEDDING_DIMENSIONS", "1024")),
    )
