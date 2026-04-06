from __future__ import annotations

import hashlib

from app.clients.document_parser import ResumeDocumentParser
from app.clients.embedding import BaseEmbeddingClient
from app.clients.llm import BaseLLMClient
from app.clients.object_storage import LocalObjectStorageClient
from app.clients.vector_store import BaseVectorStore
from app.core.logging_utils import get_logger
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

logger = get_logger("services.resume_pipeline")


class ResumePipelineService:
    def __init__(
        self,
        repository,
        llm_client: BaseLLMClient,
        embedding_client: BaseEmbeddingClient,
        vector_store: BaseVectorStore,
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
        normalized_raw_text = self._normalize_raw_text(raw_text)
        logger.info(
            "resume_pipeline.process.start resume_id=%s file_name=%s raw_text_length=%s source_content_type=%s",
            resume_id,
            file_name,
            len(normalized_raw_text),
            source_content_type,
        )
        extracted = self.llm_client.extract_resume(normalized_raw_text, file_name, resume_id)
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
            raw_text=normalized_raw_text,
            source_file_name=file_name,
            source_content_type=source_content_type,
            source_object_key=source_object_key,
        )
        self._ensure_vector("resumes", resume.id, self._vector_payload(resume))
        saved_resume = self.repository.save(resume)
        logger.info(
            "resume_pipeline.process.completed resume_id=%s skills=%s projects=%s work_experiences=%s",
            saved_resume.id,
            len(saved_resume.skills),
            len(saved_resume.projects),
            len(saved_resume.work_experiences),
        )
        return saved_resume

    def process_uploaded_resume(
        self,
        *,
        file_name: str,
        content_type: str,
        file_bytes: bytes,
        resume_id: str,
        raw_text: str = "",
    ) -> ResumeProfile:
        logger.info(
            "resume_pipeline.process_uploaded.start resume_id=%s file_name=%s content_type=%s bytes=%s raw_text_override=%s",
            resume_id,
            file_name,
            content_type,
            len(file_bytes),
            bool(raw_text.strip()),
        )
        normalized_text = raw_text.strip() or self.document_parser.extract_text(
            file_bytes=file_bytes,
            file_name=file_name,
            content_type=content_type,
        )
        object_key = self.object_storage.save_resume(resume_id, file_name, file_bytes)
        logger.info(
            "resume_pipeline.process_uploaded.persisted resume_id=%s object_key=%s normalized_text_length=%s",
            resume_id,
            object_key,
            len(normalized_text),
        )
        return self.process_resume(
            file_name=file_name,
            raw_text=normalized_text,
            resume_id=resume_id,
            source_content_type=content_type,
            source_object_key=object_key,
        )

    def get_resume(self, resume_id: str) -> ResumeProfile | None:
        resume = self.repository.get(resume_id)
        repaired = False
        if resume is not None:
            repaired = self._repair_resume_work_experiences(resume)
        logger.info(
            "resume_pipeline.get resume_id=%s found=%s repaired=%s",
            resume_id,
            resume is not None,
            repaired,
        )
        return resume

    def _vector_payload(self, resume: ResumeProfile) -> str:
        return " ".join([resume.summary, *resume.skill_names, *resume.project_keywords])

    def _normalize_raw_text(self, raw_text: str) -> str:
        if not raw_text:
            return ""
        return raw_text.replace("\x00", " ").replace("\ufeff", " ").strip()

    def _ensure_vector(self, namespace: str, item_id: str, payload: str) -> list[float]:
        payload_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        cached = self.vector_store.get(namespace, item_id)
        if cached is not None and cached.payload_hash == payload_hash:
            logger.info(
                "resume_pipeline.vector.cache_hit namespace=%s item_id=%s payload_hash=%s",
                namespace,
                item_id,
                payload_hash[:12],
            )
            return cached.vector
        logger.info(
            "resume_pipeline.vector.compute namespace=%s item_id=%s payload_hash=%s payload_length=%s",
            namespace,
            item_id,
            payload_hash[:12],
            len(payload),
        )
        vector = self.embedding_client.embed_text(payload)
        self.vector_store.upsert(namespace, item_id, vector, payload_hash)
        logger.info(
            "resume_pipeline.vector.saved namespace=%s item_id=%s dimensions=%s",
            namespace,
            item_id,
            len(vector),
        )
        return vector

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
            school=str(payload.get("school") or "School Pending"),
            degree=payload.get("degree"),
            major=payload.get("major"),
            start_year=payload.get("start_year"),
            end_year=payload.get("end_year"),
        )

    def _build_work_experience(self, payload: dict) -> ResumeWorkExperience:
        return ResumeWorkExperience(
            company_name=str(payload.get("company_name") or ""),
            industry=payload.get("industry"),
            title=str(payload.get("title") or ""),
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
            name=str(payload.get("name") or "Project Pending"),
            role=payload.get("role"),
            domain=payload.get("domain"),
            description=payload.get("description"),
            responsibilities=list(payload.get("responsibilities") or []),
            achievements=list(payload.get("achievements") or []),
            tech_stack=list(payload.get("tech_stack") or []),
        )

    def _build_skill(self, payload: dict) -> ResumeSkill:
        return ResumeSkill(
            name=str(payload.get("name") or "Skill Pending"),
            level=payload.get("level"),
            years=payload.get("years"),
            last_used_year=payload.get("last_used_year"),
        )

    def _build_tag(self, payload: dict) -> ResumeTag:
        return ResumeTag(
            name=str(payload.get("name") or "Tag Pending"),
            category=payload.get("category"),
        )

    def _repair_resume_work_experiences(self, resume: ResumeProfile) -> bool:
        infer_fn = getattr(self.llm_client, "_infer_resume_work_experiences", None)
        merge_fn = getattr(self.llm_client, "_merge_resume_work_experiences", None)
        fill_fn = getattr(self.llm_client, "_fill_resume_work_experiences_from_raw_text", None)
        if not callable(infer_fn) or not callable(merge_fn) or not callable(fill_fn) or not resume.raw_text.strip():
            return False

        existing = [
            {
                "company_name": item.company_name,
                "industry": item.industry,
                "title": item.title,
                "level": item.level,
                "location": item.location,
                "start_date": item.start_date,
                "end_date": item.end_date,
                "responsibilities": list(item.responsibilities or []),
                "achievements": list(item.achievements or []),
                "tech_stack": list(item.tech_stack or []),
            }
            for item in resume.work_experiences
        ]
        filled = fill_fn(existing, resume.raw_text)
        inferred = infer_fn(resume.raw_text)
        merged = merge_fn(filled, inferred)
        latest = merged[0] if merged else {}
        clean_text_fn = getattr(self.llm_client, "_clean_text", None)
        current_title = clean_text_fn(resume.basic_info.current_title) if callable(clean_text_fn) else resume.basic_info.current_title
        current_company = clean_text_fn(resume.basic_info.current_company) if callable(clean_text_fn) else resume.basic_info.current_company
        next_current_title = current_title or latest.get("title")
        next_current_company = current_company or latest.get("company_name")

        changed = (
            merged != existing
            or next_current_title != resume.basic_info.current_title
            or next_current_company != resume.basic_info.current_company
        )
        if not changed:
            return False

        resume.work_experiences = [self._build_work_experience(item) for item in merged]
        resume.basic_info.current_title = next_current_title
        resume.basic_info.current_company = next_current_company
        self.repository.save(resume)
        return True
