from __future__ import annotations

from app.clients.document_parser import ResumeDocumentParser
from app.clients.embedding import SimpleEmbeddingClient
from app.clients.llm import MockLLMClient
from app.clients.object_storage import LocalObjectStorageClient
from app.clients.vector_store import InMemoryVectorStore
from app.domain.models import ResumeProfile, SalaryRange
from app.repositories.in_memory import ResumeRepository


class ResumePipelineService:
    def __init__(
        self,
        repository: ResumeRepository,
        llm_client: MockLLMClient,
        embedding_client: SimpleEmbeddingClient,
        vector_store: InMemoryVectorStore,
        document_parser: ResumeDocumentParser,
        object_storage: LocalObjectStorageClient,
    ) -> None:
        self.repository = repository
        self.llm_client = llm_client
        self.embedding_client = embedding_client
        self.vector_store = vector_store
        self.document_parser = document_parser
        self.object_storage = object_storage

    def process_resume(
        self,
        file_name: str,
        raw_text: str,
        resume_id: str,
        source_content_type: str = "",
        source_object_key: str = "",
    ) -> ResumeProfile:
        extracted = self.llm_client.extract_resume(raw_text, file_name, resume_id)
        resume = ResumeProfile(
            id=extracted["id"],
            candidate_name=extracted["candidate_name"],
            summary=extracted["summary"],
            skills=extracted["skills"],
            project_keywords=extracted["project_keywords"],
            years_experience=extracted["years_experience"],
            expected_salary=SalaryRange(
                min=extracted["salary_min"],
                max=extracted["salary_max"],
            ),
            raw_text=raw_text,
            source_file_name=file_name,
            source_content_type=source_content_type,
            source_object_key=source_object_key,
        )
        vector = self.embedding_client.embed_text(self._vector_payload(resume))
        self.vector_store.upsert("resumes", resume.id, vector)
        return self.repository.save(resume)

    def process_uploaded_resume(
        self,
        *,
        file_name: str,
        content_type: str,
        file_bytes: bytes,
        resume_id: str,
        raw_text: str = "",
    ) -> ResumeProfile:
        normalized_text = raw_text.strip() or self.document_parser.extract_text(
            file_bytes=file_bytes,
            file_name=file_name,
            content_type=content_type,
        )
        object_key = self.object_storage.save_resume(resume_id, file_name, file_bytes)
        return self.process_resume(
            file_name=file_name,
            raw_text=normalized_text,
            resume_id=resume_id,
            source_content_type=content_type,
            source_object_key=object_key,
        )

    def get_resume(self, resume_id: str) -> ResumeProfile | None:
        return self.repository.get(resume_id)

    def _vector_payload(self, resume: ResumeProfile) -> str:
        return " ".join([resume.summary, *resume.skills, *resume.project_keywords])