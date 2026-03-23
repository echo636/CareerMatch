from __future__ import annotations

from app.clients.document_parser import ResumeDocumentParser
from app.clients.embedding import BaseEmbeddingClient
from app.clients.llm import BaseLLMClient
from app.clients.object_storage import LocalObjectStorageClient
from app.clients.vector_store import InMemoryVectorStore
from app.domain.models import (
    ResumeBasicInfo,
    ResumeEducation,
    ResumeProfile,
    ResumeProject,
    ResumeSkill,
    ResumeTag,
    ResumeWorkExperience,
    SalaryRange,
)
from app.repositories.in_memory import ResumeRepository


class ResumePipelineService:
    def __init__(
        self,
        repository: ResumeRepository,
        llm_client: BaseLLMClient,
        embedding_client: BaseEmbeddingClient,
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
        expected_salary = extracted.get("expected_salary") or {}
        resume = ResumeProfile(
            id=extracted["id"],
            is_resume=extracted.get("is_resume"),
            basic_info=self._build_basic_info(extracted.get("basic_info") or {}, file_name),
            educations=[self._build_education(item) for item in extracted.get("educations") or []],
            work_experiences=[
                self._build_work_experience(item) for item in extracted.get("work_experiences") or []
            ],
            projects=[self._build_project(item) for item in extracted.get("projects") or []],
            skills=[self._build_skill(item) for item in extracted.get("skills") or []],
            tags=[self._build_tag(item) for item in extracted.get("tags") or []],
            expected_salary=SalaryRange(
                min=int(expected_salary.get("min", 25000)),
                max=int(expected_salary.get("max", 35000)),
                currency=str(expected_salary.get("currency", "CNY")),
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
        return " ".join([resume.summary, *resume.skill_names, *resume.project_keywords])

    def _build_basic_info(self, payload: dict, file_name: str) -> ResumeBasicInfo:
        return ResumeBasicInfo(
            name=str(payload.get("name") or file_name),
            gender=payload.get("gender"),
            age=payload.get("age"),
            work_years=payload.get("work_years"),
            current_city=payload.get("current_city"),
            current_title=payload.get("current_title"),
            current_company=payload.get("current_company"),
            status=payload.get("status"),
            email=payload.get("email"),
            phone=payload.get("phone"),
            wechat=payload.get("wechat"),
            ethnicity=payload.get("ethnicity"),
            birth_date=payload.get("birth_date"),
            native_place=payload.get("native_place"),
            residence=payload.get("residence"),
            political_status=payload.get("political_status"),
            id_number=payload.get("id_number"),
            marital_status=payload.get("marital_status"),
            summary=payload.get("summary"),
            self_evaluation=payload.get("self_evaluation"),
            first_degree=payload.get("first_degree"),
            avatar=payload.get("avatar") or payload.get("avator"),
        )

    def _build_education(self, payload: dict) -> ResumeEducation:
        return ResumeEducation(
            school=str(payload.get("school") or "寰呰ˉ鍏呴櫌鏍?"),
            degree=payload.get("degree"),
            major=payload.get("major"),
            start_year=payload.get("start_year"),
            end_year=payload.get("end_year"),
        )

    def _build_work_experience(self, payload: dict) -> ResumeWorkExperience:
        return ResumeWorkExperience(
            company_name=str(payload.get("company_name") or "寰呰ˉ鍏呭叕鍙?"),
            industry=payload.get("industry"),
            title=str(payload.get("title") or "寰呰ˉ鍏呭矖浣?"),
            level=payload.get("level"),
            location=payload.get("location"),
            start_date=payload.get("start_date"),
            end_date=payload.get("end_date"),
            responsibilities=list(payload.get("responsibilities") or []),
            achievements=list(payload.get("achievements") or []),
            tech_stack=list(payload.get("tech_stack") or []),
        )

    def _build_project(self, payload: dict) -> ResumeProject:
        return ResumeProject(
            name=str(payload.get("name") or "寰呰ˉ鍏呴」鐩?"),
            role=payload.get("role"),
            domain=payload.get("domain"),
            description=payload.get("description"),
            responsibilities=list(payload.get("responsibilities") or []),
            achievements=list(payload.get("achievements") or []),
            tech_stack=list(payload.get("tech_stack") or []),
        )

    def _build_skill(self, payload: dict) -> ResumeSkill:
        return ResumeSkill(
            name=str(payload.get("name") or "寰呰ˉ鍏呮妧鑳?"),
            level=payload.get("level"),
            years=payload.get("years"),
            last_used_year=payload.get("last_used_year"),
        )

    def _build_tag(self, payload: dict) -> ResumeTag:
        return ResumeTag(
            name=str(payload.get("name") or "寰呰ˉ鍏呮爣绛?"),
            category=payload.get("category"),
        )
