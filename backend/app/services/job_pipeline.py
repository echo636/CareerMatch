from __future__ import annotations

from typing import Any

from app.clients.embedding import SimpleEmbeddingClient
from app.clients.llm import MockLLMClient
from app.clients.vector_store import InMemoryVectorStore
from app.domain.models import JobProfile, SalaryRange
from app.repositories.in_memory import JobRepository


class JobPipelineService:
    def __init__(
        self,
        repository: JobRepository,
        llm_client: MockLLMClient,
        embedding_client: SimpleEmbeddingClient,
        vector_store: InMemoryVectorStore,
    ) -> None:
        self.repository = repository
        self.llm_client = llm_client
        self.embedding_client = embedding_client
        self.vector_store = vector_store

    def import_jobs(self, records: list[dict[str, Any]]) -> list[JobProfile]:
        normalized_jobs = [self._normalize(record) for record in records]
        for job in normalized_jobs:
            vector = self.embedding_client.embed_text(self._vector_payload(job))
            self.vector_store.upsert("jobs", job.id, vector)
        return self.repository.save_many(normalized_jobs)

    def list_jobs(self) -> list[JobProfile]:
        return self.repository.list()

    def _normalize(self, record: dict[str, Any]) -> JobProfile:
        extracted = self.llm_client.extract_job(record)
        return JobProfile(
            id=extracted["id"],
            title=extracted["title"],
            company=extracted["company"],
            location=extracted["location"],
            summary=extracted["summary"],
            skills=extracted["skills"],
            project_keywords=extracted["project_keywords"],
            hard_requirements=extracted["hard_requirements"],
            salary_range=SalaryRange(
                min=extracted["salary_min"],
                max=extracted["salary_max"],
                currency=extracted["salary_currency"],
            ),
            experience_years=extracted["experience_years"],
        )

    def _vector_payload(self, job: JobProfile) -> str:
        return " ".join([job.summary, *job.skills, *job.project_keywords])
