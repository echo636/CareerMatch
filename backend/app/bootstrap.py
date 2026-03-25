from __future__ import annotations

from dataclasses import dataclass
import warnings

from app.clients.document_parser import ResumeDocumentParser
from app.clients.embedding import BaseEmbeddingClient, QwenEmbeddingClient
from app.clients.llm import BaseLLMClient, QwenLLMClient
from app.clients.object_storage import LocalObjectStorageClient
from app.clients.qdrant_store import QdrantVectorStore
from app.clients.vector_store import BaseVectorStore
from app.core.config import Settings
from app.job_seed_loader import load_job_seed_records
from app.repositories.postgres import PostgresJobRepository, PostgresResumeRepository
from app.services.gap_analysis import GapAnalysisService
from app.services.job_pipeline import JobPipelineService
from app.services.matching import MatchingService
from app.services.resume_pipeline import ResumePipelineService

REMOTE_STARTUP_JOB_LIMIT = 20


@dataclass(slots=True)
class ServiceContainer:
    settings: Settings
    resume_pipeline: ResumePipelineService
    job_pipeline: JobPipelineService
    matching_service: MatchingService
    gap_analysis_service: GapAnalysisService


def build_services(settings: Settings) -> ServiceContainer:
    llm_client = _build_llm_client(settings)
    embedding_client = _build_embedding_client(settings)
    vector_store = QdrantVectorStore(settings.qdrant_url, settings.qwen_embedding_dimensions)
    document_parser = ResumeDocumentParser()
    object_storage = LocalObjectStorageClient(settings.object_storage_root)
    resume_repository = PostgresResumeRepository(settings.postgres_dsn)
    job_repository = PostgresJobRepository(settings.postgres_dsn)

    initialize_persistent_data(
        settings=settings,
        job_repository=job_repository,
        resume_repository=resume_repository,
        llm_client=llm_client,
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


def _build_llm_client(settings: Settings) -> BaseLLMClient:
    if settings.llm_provider != "qwen":
        raise ValueError(
            f"Unsupported LLM_PROVIDER '{settings.llm_provider}'. Mock provider has been removed; use 'qwen'."
        )
    if not settings.dashscope_api_key:
        raise ValueError("DASHSCOPE_API_KEY is required when LLM_PROVIDER=qwen.")
    return QwenLLMClient(
        api_key=settings.dashscope_api_key,
        model=settings.qwen_llm_model,
        base_url=settings.dashscope_base_url,
        timeout_sec=settings.dashscope_timeout_sec,
        retry_count=settings.dashscope_llm_retry_count,
        retry_backoff_sec=settings.dashscope_llm_retry_backoff_sec,
    )


def _build_embedding_client(settings: Settings) -> BaseEmbeddingClient:
    if settings.embedding_provider != "qwen":
        raise ValueError(
            f"Unsupported EMBEDDING_PROVIDER '{settings.embedding_provider}'. Mock provider has been removed; use 'qwen'."
        )
    if not settings.dashscope_api_key:
        raise ValueError("DASHSCOPE_API_KEY is required when EMBEDDING_PROVIDER=qwen.")
    return QwenEmbeddingClient(
        api_key=settings.dashscope_api_key,
        model=settings.qwen_embedding_model,
        base_url=settings.dashscope_base_url,
        dimensions=settings.qwen_embedding_dimensions,
        timeout_sec=settings.dashscope_timeout_sec,
    )


def _seed_job_limit(settings: Settings) -> int | None:
    if settings.job_seed_limit is not None:
        return settings.job_seed_limit
    warnings.warn(
        "Real Qwen LLM and embedding are enabled for startup seed jobs. "
        f"Capping startup seed load to {REMOTE_STARTUP_JOB_LIMIT} jobs. "
        "Set JOB_DATA_LIMIT explicitly to override.",
        RuntimeWarning,
        stacklevel=2,
    )
    return REMOTE_STARTUP_JOB_LIMIT


def _remove_legacy_demo_resume(
    resume_repository: PostgresResumeRepository,
    vector_store: BaseVectorStore,
) -> None:
    resume_repository.delete("demo-resume")
    try:
        vector_store.delete("resumes", "demo-resume")
    except Exception:
        pass


def initialize_persistent_data(
    *,
    settings: Settings,
    job_repository: PostgresJobRepository,
    resume_repository: PostgresResumeRepository,
    llm_client: BaseLLMClient,
    embedding_client: BaseEmbeddingClient,
    vector_store: BaseVectorStore,
) -> None:
    _remove_legacy_demo_resume(resume_repository, vector_store)
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
