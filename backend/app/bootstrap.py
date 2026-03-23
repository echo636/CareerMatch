from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json

from app.clients.document_parser import ResumeDocumentParser
from app.clients.embedding import BaseEmbeddingClient, QwenEmbeddingClient, SimpleEmbeddingClient
from app.clients.llm import BaseLLMClient, MockLLMClient, QwenLLMClient
from app.clients.object_storage import LocalObjectStorageClient
from app.clients.vector_store import InMemoryVectorStore
from app.core.config import Settings
from app.repositories.in_memory import JobRepository, ResumeRepository
from app.services.gap_analysis import GapAnalysisService
from app.services.job_pipeline import JobPipelineService
from app.services.matching import MatchingService
from app.services.resume_pipeline import ResumePipelineService

DEMO_RESUME_TEXT = """
闄堟櫒 5 骞?Python 涓?AI 搴旂敤缁忛獙銆?鐔熸倝 Flask銆丳ostgreSQL銆丏ocker銆丩LM銆丒mbedding銆丳rompt Design銆?鍋氳繃绠€鍘嗚В鏋愩€佸矖浣嶅尮閰嶃€佽涔夋绱㈠拰璇勫垎绯荤粺鐩稿叧椤圭洰锛屾湡鏈涜柂璧?25000 35000銆?""".strip()


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
    vector_store = InMemoryVectorStore()
    document_parser = ResumeDocumentParser()
    object_storage = LocalObjectStorageClient(settings.object_storage_root)
    resume_repository = ResumeRepository()
    job_repository = JobRepository()

    seed_demo_data(
        resume_repository=resume_repository,
        job_repository=job_repository,
        llm_client=mock_llm_client,
        embedding_client=embedding_client,
        vector_store=vector_store,
        document_parser=document_parser,
        object_storage=object_storage,
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


def seed_demo_data(
    *,
    resume_repository: ResumeRepository,
    job_repository: JobRepository,
    llm_client: BaseLLMClient,
    embedding_client: BaseEmbeddingClient,
    vector_store: InMemoryVectorStore,
    document_parser: ResumeDocumentParser,
    object_storage: LocalObjectStorageClient,
) -> None:
    sample_jobs_path = Path(__file__).resolve().parents[1] / "data" / "sample_jobs.json"
    job_records = json.loads(sample_jobs_path.read_text(encoding="utf-8"))
    demo_resume_pipeline = ResumePipelineService(
        repository=resume_repository,
        llm_client=llm_client,
        embedding_client=embedding_client,
        vector_store=vector_store,
        document_parser=document_parser,
        object_storage=object_storage,
    )
    demo_job_pipeline = JobPipelineService(
        repository=job_repository,
        llm_client=llm_client,
        embedding_client=embedding_client,
        vector_store=vector_store,
    )
    demo_resume_pipeline.process_resume(
        file_name="闄堟櫒_demo_resume.pdf",
        raw_text=DEMO_RESUME_TEXT,
        resume_id="demo-resume",
        source_content_type="application/pdf",
    )
    demo_job_pipeline.import_jobs(job_records)
