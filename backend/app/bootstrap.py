from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json

from app.clients.document_parser import ResumeDocumentParser
from app.clients.embedding import SimpleEmbeddingClient
from app.clients.llm import MockLLMClient
from app.clients.object_storage import LocalObjectStorageClient
from app.clients.vector_store import InMemoryVectorStore
from app.core.config import Settings
from app.repositories.in_memory import JobRepository, ResumeRepository
from app.services.gap_analysis import GapAnalysisService
from app.services.job_pipeline import JobPipelineService
from app.services.matching import MatchingService
from app.services.resume_pipeline import ResumePipelineService

DEMO_RESUME_TEXT = """
陈晨 5 年 Python 与 AI 应用经验。
熟悉 Flask、PostgreSQL、Docker、LLM、Embedding、Prompt Design。
做过简历解析、岗位匹配、语义检索和评分系统相关项目，期望薪资 25000 35000。
""".strip()


@dataclass(slots=True)
class ServiceContainer:
    settings: Settings
    resume_pipeline: ResumePipelineService
    job_pipeline: JobPipelineService
    matching_service: MatchingService
    gap_analysis_service: GapAnalysisService


def build_services(settings: Settings) -> ServiceContainer:
    llm_client = MockLLMClient()
    embedding_client = SimpleEmbeddingClient()
    vector_store = InMemoryVectorStore()
    document_parser = ResumeDocumentParser()
    object_storage = LocalObjectStorageClient(settings.object_storage_root)
    resume_repository = ResumeRepository()
    job_repository = JobRepository()

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

    container = ServiceContainer(
        settings=settings,
        resume_pipeline=resume_pipeline,
        job_pipeline=job_pipeline,
        matching_service=matching_service,
        gap_analysis_service=gap_analysis_service,
    )
    seed_demo_data(container)
    return container


def seed_demo_data(container: ServiceContainer) -> None:
    sample_jobs_path = Path(__file__).resolve().parents[1] / "data" / "sample_jobs.json"
    job_records = json.loads(sample_jobs_path.read_text(encoding="utf-8"))
    container.resume_pipeline.process_resume(
        file_name="陈晨_demo_resume.pdf",
        raw_text=DEMO_RESUME_TEXT,
        resume_id="demo-resume",
        source_content_type="application/pdf",
    )
    container.job_pipeline.import_jobs(job_records)