from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class MatchingAlgorithmConfig:
    total_weight_vector: float
    total_weight_skill: float
    total_weight_experience: float
    total_weight_education: float
    skill_required_weight: float
    skill_optional_weight: float
    skill_bonus_weight: float
    experience_core_weight: float
    experience_bonus_weight: float
    experience_total_years_weight: float
    education_min_degree_weight: float
    education_prefer_degree_weight: float
    education_required_major_weight: float
    education_preferred_major_weight: float
    minimum_degree_filter_threshold: float
    salary_far_above_budget_ratio: float
    tier_reach_ratio: float
    tier_safety_ratio: float
    direction_mismatch_min_tag_count: int
    recall_small_job_pool_max: int
    recall_medium_job_pool_max: int
    recall_large_job_pool_max: int
    recall_multiplier_small: int
    recall_multiplier_medium: int
    recall_multiplier_large: int
    recall_multiplier_xlarge: int
    filtered_recall_scale: int
    filtered_recall_min_multiplier: int
    semantic_skill_min_similarity: float
    semantic_skill_base_score: float
    semantic_skill_score_scale: float
    semantic_skill_max_score: float


def default_matching_algorithm_config() -> MatchingAlgorithmConfig:
    return MatchingAlgorithmConfig(
        total_weight_vector=0.30,
        total_weight_skill=0.15,
        total_weight_experience=0.40,
        total_weight_education=0.15,
        skill_required_weight=0.60,
        skill_optional_weight=0.25,
        skill_bonus_weight=0.15,
        experience_core_weight=0.60,
        experience_bonus_weight=0.15,
        experience_total_years_weight=0.25,
        education_min_degree_weight=0.50,
        education_prefer_degree_weight=0.20,
        education_required_major_weight=0.20,
        education_preferred_major_weight=0.10,
        minimum_degree_filter_threshold=0.50,
        salary_far_above_budget_ratio=1.50,
        tier_reach_ratio=1.20,
        tier_safety_ratio=0.85,
        direction_mismatch_min_tag_count=3,
        recall_small_job_pool_max=50,
        recall_medium_job_pool_max=200,
        recall_large_job_pool_max=1000,
        recall_multiplier_small=3,
        recall_multiplier_medium=5,
        recall_multiplier_large=8,
        recall_multiplier_xlarge=10,
        filtered_recall_scale=2,
        filtered_recall_min_multiplier=8,
        semantic_skill_min_similarity=0.88,
        semantic_skill_base_score=0.55,
        semantic_skill_score_scale=2.5,
        semantic_skill_max_score=0.85,
    )


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
    app_log_dir: Path
    app_log_level: str
    dashscope_api_key: str
    dashscope_base_url: str
    dashscope_timeout_sec: int
    dashscope_llm_retry_count: int
    dashscope_llm_retry_backoff_sec: float
    qwen_llm_model: str
    qwen_embedding_model: str
    qwen_embedding_dimensions: int
    matching_algorithm: MatchingAlgorithmConfig


def _env_int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _env_float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    default_matching_config = default_matching_algorithm_config()
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

    configured_log_dir = os.getenv("APP_LOG_DIR", "logs")
    app_log_dir = Path(configured_log_dir)
    if not app_log_dir.is_absolute():
        app_log_dir = BASE_DIR / app_log_dir

    return Settings(
        app_name=os.getenv("APP_NAME", "CareerMatch API"),
        debug=os.getenv("FLASK_DEBUG", "0") == "1",
        port=int(os.getenv("PORT", "5000")),
        frontend_origin=os.getenv("FRONTEND_ORIGIN", "http://localhost:3000"),
        llm_provider=os.getenv("LLM_PROVIDER", "qwen").strip().lower(),
        embedding_provider=os.getenv("EMBEDDING_PROVIDER", "qwen").strip().lower(),
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
        app_log_dir=app_log_dir.resolve(),
        app_log_level=os.getenv("APP_LOG_LEVEL", "INFO").strip().upper() or "INFO",
        dashscope_api_key=os.getenv("DASHSCOPE_API_KEY", "").strip(),
        dashscope_base_url=os.getenv(
            "DASHSCOPE_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        ).rstrip("/"),
        dashscope_timeout_sec=int(os.getenv("DASHSCOPE_TIMEOUT_SEC", "120")),
        dashscope_llm_retry_count=int(os.getenv("DASHSCOPE_LLM_RETRY_COUNT", "2")),
        dashscope_llm_retry_backoff_sec=float(os.getenv("DASHSCOPE_LLM_RETRY_BACKOFF_SEC", "2.0")),
        qwen_llm_model=os.getenv("QWEN_LLM_MODEL", "qwen-plus-latest").strip(),
        qwen_embedding_model=os.getenv("QWEN_EMBEDDING_MODEL", "text-embedding-v4").strip(),
        qwen_embedding_dimensions=int(os.getenv("QWEN_EMBEDDING_DIMENSIONS", "1024")),
        matching_algorithm=MatchingAlgorithmConfig(
            total_weight_vector=_env_float("MATCH_TOTAL_WEIGHT_VECTOR", default_matching_config.total_weight_vector),
            total_weight_skill=_env_float("MATCH_TOTAL_WEIGHT_SKILL", default_matching_config.total_weight_skill),
            total_weight_experience=_env_float(
                "MATCH_TOTAL_WEIGHT_EXPERIENCE",
                default_matching_config.total_weight_experience,
            ),
            total_weight_education=_env_float(
                "MATCH_TOTAL_WEIGHT_EDUCATION",
                default_matching_config.total_weight_education,
            ),
            skill_required_weight=_env_float(
                "MATCH_SKILL_REQUIRED_WEIGHT",
                default_matching_config.skill_required_weight,
            ),
            skill_optional_weight=_env_float(
                "MATCH_SKILL_OPTIONAL_WEIGHT",
                default_matching_config.skill_optional_weight,
            ),
            skill_bonus_weight=_env_float(
                "MATCH_SKILL_BONUS_WEIGHT",
                default_matching_config.skill_bonus_weight,
            ),
            experience_core_weight=_env_float(
                "MATCH_EXPERIENCE_CORE_WEIGHT",
                default_matching_config.experience_core_weight,
            ),
            experience_bonus_weight=_env_float(
                "MATCH_EXPERIENCE_BONUS_WEIGHT",
                default_matching_config.experience_bonus_weight,
            ),
            experience_total_years_weight=_env_float(
                "MATCH_EXPERIENCE_TOTAL_YEARS_WEIGHT",
                default_matching_config.experience_total_years_weight,
            ),
            education_min_degree_weight=_env_float(
                "MATCH_EDUCATION_MIN_DEGREE_WEIGHT",
                default_matching_config.education_min_degree_weight,
            ),
            education_prefer_degree_weight=_env_float(
                "MATCH_EDUCATION_PREFER_DEGREE_WEIGHT",
                default_matching_config.education_prefer_degree_weight,
            ),
            education_required_major_weight=_env_float(
                "MATCH_EDUCATION_REQUIRED_MAJOR_WEIGHT",
                default_matching_config.education_required_major_weight,
            ),
            education_preferred_major_weight=_env_float(
                "MATCH_EDUCATION_PREFERRED_MAJOR_WEIGHT",
                default_matching_config.education_preferred_major_weight,
            ),
            minimum_degree_filter_threshold=_env_float(
                "MATCH_MIN_DEGREE_FILTER_THRESHOLD",
                default_matching_config.minimum_degree_filter_threshold,
            ),
            salary_far_above_budget_ratio=_env_float(
                "MATCH_SALARY_FAR_ABOVE_BUDGET_RATIO",
                default_matching_config.salary_far_above_budget_ratio,
            ),
            tier_reach_ratio=_env_float("MATCH_TIER_REACH_RATIO", default_matching_config.tier_reach_ratio),
            tier_safety_ratio=_env_float("MATCH_TIER_SAFETY_RATIO", default_matching_config.tier_safety_ratio),
            direction_mismatch_min_tag_count=_env_int(
                "MATCH_DIRECTION_MISMATCH_MIN_TAG_COUNT",
                default_matching_config.direction_mismatch_min_tag_count,
            ),
            recall_small_job_pool_max=_env_int(
                "MATCH_RECALL_SMALL_JOB_POOL_MAX",
                default_matching_config.recall_small_job_pool_max,
            ),
            recall_medium_job_pool_max=_env_int(
                "MATCH_RECALL_MEDIUM_JOB_POOL_MAX",
                default_matching_config.recall_medium_job_pool_max,
            ),
            recall_large_job_pool_max=_env_int(
                "MATCH_RECALL_LARGE_JOB_POOL_MAX",
                default_matching_config.recall_large_job_pool_max,
            ),
            recall_multiplier_small=_env_int(
                "MATCH_RECALL_MULTIPLIER_SMALL",
                default_matching_config.recall_multiplier_small,
            ),
            recall_multiplier_medium=_env_int(
                "MATCH_RECALL_MULTIPLIER_MEDIUM",
                default_matching_config.recall_multiplier_medium,
            ),
            recall_multiplier_large=_env_int(
                "MATCH_RECALL_MULTIPLIER_LARGE",
                default_matching_config.recall_multiplier_large,
            ),
            recall_multiplier_xlarge=_env_int(
                "MATCH_RECALL_MULTIPLIER_XLARGE",
                default_matching_config.recall_multiplier_xlarge,
            ),
            filtered_recall_scale=_env_int(
                "MATCH_FILTERED_RECALL_SCALE",
                default_matching_config.filtered_recall_scale,
            ),
            filtered_recall_min_multiplier=_env_int(
                "MATCH_FILTERED_RECALL_MIN_MULTIPLIER",
                default_matching_config.filtered_recall_min_multiplier,
            ),
            semantic_skill_min_similarity=_env_float(
                "MATCH_SEMANTIC_SKILL_MIN_SIMILARITY",
                default_matching_config.semantic_skill_min_similarity,
            ),
            semantic_skill_base_score=_env_float(
                "MATCH_SEMANTIC_SKILL_BASE_SCORE",
                default_matching_config.semantic_skill_base_score,
            ),
            semantic_skill_score_scale=_env_float(
                "MATCH_SEMANTIC_SKILL_SCORE_SCALE",
                default_matching_config.semantic_skill_score_scale,
            ),
            semantic_skill_max_score=_env_float(
                "MATCH_SEMANTIC_SKILL_MAX_SCORE",
                default_matching_config.semantic_skill_max_score,
            ),
        ),
    )
