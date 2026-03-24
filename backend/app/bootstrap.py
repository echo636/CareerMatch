from __future__ import annotations

from dataclasses import dataclass
import sqlite3
import warnings

from app.clients.document_parser import ResumeDocumentParser
from app.clients.embedding import BaseEmbeddingClient, QwenEmbeddingClient, SimpleEmbeddingClient
from app.clients.llm import BaseLLMClient, MockLLMClient, QwenLLMClient
from app.clients.object_storage import LocalObjectStorageClient
from app.clients.vector_store import BaseVectorStore, SqliteVectorStore
from app.core.config import Settings
from app.job_seed_loader import load_job_seed_records
from app.repositories.sqlite import SqliteJobRepository, SqliteResumeRepository
from app.services.gap_analysis import GapAnalysisService
from app.services.job_pipeline import JobPipelineService
from app.services.matching import MatchingService
from app.services.resume_pipeline import ResumePipelineService

REMOTE_EMBEDDING_STARTUP_JOB_LIMIT = 20


@dataclass(slots=True)
class ServiceContainer:
    settings: Settings
    resume_pipeline: ResumePipelineService
    job_pipeline: JobPipelineService
    matching_service: MatchingService
    gap_analysis_service: GapAnalysisService


def build_services(settings: Settings) -> ServiceContainer:
    mock_llm_client = MockLLMClient()
    llm_client = _build_llm_client(settings, mock_llm_client)
    embedding_client = _build_embedding_client(settings)
    vector_store = SqliteVectorStore(settings.app_state_db_path)
    document_parser = ResumeDocumentParser()
    object_storage = LocalObjectStorageClient(settings.object_storage_root)
    resume_repository = SqliteResumeRepository(settings.app_state_db_path)
    job_repository = SqliteJobRepository(settings.app_state_db_path)

    initialize_persistent_data(
        settings=settings,
        job_repository=job_repository,
        llm_client=mock_llm_client,
        embedding_client=embedding_client,
        vector_store=vector_store,
    )

    resume_pipeline = ResumePipelineService(
        repository=resume_repository,
        llm_client=llm_client,
        embedding_client=embedding_client,
        vector_store=vector_store,
        document_parser=document_parser,
        object_storage=object_storage,
    )
    job_pipeline = JobPipelineService(
        repository=job_repository,
        llm_client=llm_client,
        embedding_client=embedding_client,
        vector_store=vector_store,
    )
    matching_service = MatchingService(
        job_repository=job_repository,
        resume_repository=resume_repository,
        embedding_client=embedding_client,
        vector_store=vector_store,
    )
    gap_analysis_service = GapAnalysisService(
        resume_repository=resume_repository,
        matching_service=matching_service,
        llm_client=llm_client,
    )

    return ServiceContainer(
        settings=settings,
        resume_pipeline=resume_pipeline,
        job_pipeline=job_pipeline,
        matching_service=matching_service,
        gap_analysis_service=gap_analysis_service,
    )


def _build_llm_client(settings: Settings, fallback_client: BaseLLMClient) -> BaseLLMClient:
    if settings.llm_provider == "mock":
        return fallback_client
    if settings.llm_provider == "qwen":
        if not settings.dashscope_api_key:
            raise ValueError("DASHSCOPE_API_KEY is required when LLM_PROVIDER=qwen.")
        return QwenLLMClient(
            api_key=settings.dashscope_api_key,
            model=settings.qwen_llm_model,
            base_url=settings.dashscope_base_url,
            timeout_sec=settings.dashscope_timeout_sec,
            retry_count=settings.dashscope_llm_retry_count,
            retry_backoff_sec=settings.dashscope_llm_retry_backoff_sec,
            fallback_client=fallback_client,
        )
    raise ValueError(f"Unsupported LLM_PROVIDER '{settings.llm_provider}'.")


def _build_embedding_client(settings: Settings) -> BaseEmbeddingClient:
    if settings.embedding_provider == "mock":
        return SimpleEmbeddingClient()
    if settings.embedding_provider == "qwen":
        if not settings.dashscope_api_key:
            raise ValueError("DASHSCOPE_API_KEY is required when EMBEDDING_PROVIDER=qwen.")
        return QwenEmbeddingClient(
            api_key=settings.dashscope_api_key,
            model=settings.qwen_embedding_model,
            base_url=settings.dashscope_base_url,
            dimensions=settings.qwen_embedding_dimensions,
            timeout_sec=settings.dashscope_timeout_sec,
        )
    raise ValueError(f"Unsupported EMBEDDING_PROVIDER '{settings.embedding_provider}'.")


def _seed_job_limit(settings: Settings) -> int | None:
    if settings.job_seed_limit is not None:
        return settings.job_seed_limit
    if settings.embedding_provider == "qwen":
        warnings.warn(
            "EMBEDDING_PROVIDER=qwen without JOB_DATA_LIMIT would request remote embeddings for every seeded job. "
            f"Capping startup seed load to {REMOTE_EMBEDDING_STARTUP_JOB_LIMIT} jobs. "
            "Set JOB_DATA_LIMIT explicitly to override.",
            RuntimeWarning,
            stacklevel=2,
        )
        return REMOTE_EMBEDDING_STARTUP_JOB_LIMIT
    return None


def _remove_legacy_demo_resume(settings: Settings) -> None:
    with sqlite3.connect(settings.app_state_db_path) as connection:
        connection.execute("DELETE FROM resumes WHERE id = 'demo-resume'")
        connection.execute(
            "DELETE FROM vectors WHERE namespace = 'resumes' AND item_id = 'demo-resume'"
        )
        connection.commit()


def initialize_persistent_data(
    *,
    settings: Settings,
    job_repository: SqliteJobRepository,
    llm_client: BaseLLMClient,
    embedding_client: BaseEmbeddingClient,
    vector_store: BaseVectorStore,
) -> None:
    _remove_legacy_demo_resume(settings)
    if job_repository.count() > 0:
        return

    job_records = load_job_seed_records(settings.job_seed_path, _seed_job_limit(settings))
    job_pipeline = JobPipelineService(
        repository=job_repository,
        llm_client=llm_client,
        embedding_client=embedding_client,
        vector_store=vector_store,
    )
    job_pipeline.import_jobs(job_records)
