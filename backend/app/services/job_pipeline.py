from __future__ import annotations

import hashlib
from typing import Any

from app.clients.embedding import BaseEmbeddingClient
from app.clients.llm import BaseLLMClient
from app.clients.vector_store import BaseVectorStore
from app.core.logging_utils import get_logger
from app.domain.models import (
    BonusExperience,
    BonusSkill,
    CoreExperience,
    JobBasicInfo,
    JobEducationConstraints,
    JobExperienceRequirements,
    JobProfile,
    JobSkillRequirements,
    JobTag,
    LanguageRequirement,
    OptionalSkill,
    OptionalSkillGroup,
    RequiredSkill,
)

logger = get_logger("services.job_pipeline")


class JobPipelineService:
    def __init__(
        self,
        repository,
        llm_client: BaseLLMClient,
        embedding_client: BaseEmbeddingClient,
        vector_store: BaseVectorStore,
    ) -> None:
        self.repository = repository
        self.llm_client = llm_client
        self.embedding_client = embedding_client
        self.vector_store = vector_store

    def import_jobs(self, records: list[dict[str, Any]]) -> list[JobProfile]:
        logger.info("job_pipeline.import.start records=%s", len(records))
        normalized_jobs = [self._normalize(record) for record in records]
        for job in normalized_jobs:
            self._ensure_vector("jobs", job.id, self._vector_payload(job))
        saved_jobs = self.repository.save_many(normalized_jobs)
        logger.info("job_pipeline.import.completed records=%s saved=%s", len(records), len(saved_jobs))
        return saved_jobs

    def list_jobs(self) -> list[JobProfile]:
        jobs = self.repository.list()
        logger.info("job_pipeline.list count=%s", len(jobs))
        return jobs

    def _normalize(self, record: dict[str, Any]) -> JobProfile:
        extracted = self.llm_client.extract_job(record)
        job = JobProfile(
            id=extracted["id"],
            company=extracted["company"],
            basic_info=self._build_basic_info(extracted.get("basic_info") or {}),
            skill_requirements=self._build_skill_requirements(extracted.get("skill_requirements") or {}),
            experience_requirements=self._build_experience_requirements(
                extracted.get("experience_requirements") or {}
            ),
            education_constraints=self._build_education_constraints(
                extracted.get("education_constraints") or {}
            ),
            tags=[self._build_tag(item) for item in extracted.get("tags") or []],
        )
        logger.info(
            "job_pipeline.normalize job_id=%s title=%s required_skills=%s bonus_skills=%s",
            job.id,
            job.basic_info.title,
            len(job.skill_requirements.required),
            len(job.skill_requirements.bonus),
        )
        return job

    def _vector_payload(self, job: JobProfile) -> str:
        return " ".join([job.summary, *job.skills, *job.project_keywords])

    def _ensure_vector(self, namespace: str, item_id: str, payload: str) -> list[float]:
        payload_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        cached = self.vector_store.get(namespace, item_id)
        if cached is not None and cached.payload_hash == payload_hash:
            logger.debug(
                "job_pipeline.vector.cache_hit namespace=%s item_id=%s payload_hash=%s",
                namespace,
                item_id,
                payload_hash[:12],
            )
            return cached.vector
        logger.info(
            "job_pipeline.vector.compute namespace=%s item_id=%s payload_hash=%s payload_length=%s",
            namespace,
            item_id,
            payload_hash[:12],
            len(payload),
        )
        vector = self.embedding_client.embed_text(payload)
        self.vector_store.upsert(namespace, item_id, vector, payload_hash)
        logger.info(
            "job_pipeline.vector.saved namespace=%s item_id=%s dimensions=%s",
            namespace,
            item_id,
            len(vector),
        )
        return vector

    def _build_basic_info(self, payload: dict[str, Any]) -> JobBasicInfo:
        return JobBasicInfo(
            title=str(payload.get("title") or "Untitled Role"),
            department=payload.get("department"),
            location=payload.get("location"),
            job_type=payload.get("job_type"),
            salary_negotiable=payload.get("salary_negotiable"),
            salary_min=payload.get("salary_min"),
            salary_max=payload.get("salary_max"),
            salary_months_min=payload.get("salary_months_min"),
            salary_months_max=payload.get("salary_months_max"),
            intern_salary_amount=payload.get("intern_salary_amount"),
            intern_salary_unit=payload.get("intern_salary_unit"),
            currency=payload.get("currency"),
            summary=payload.get("summary"),
            responsibilities=list(payload.get("responsibilities") or []),
            highlights=list(payload.get("highlights") or []),
        )

    def _build_skill_requirements(self, payload: dict[str, Any]) -> JobSkillRequirements:
        return JobSkillRequirements(
            required=[self._build_required_skill(item) for item in payload.get("required") or []],
            optional_groups=[
                self._build_optional_group(item) for item in payload.get("optional_groups") or []
            ],
            bonus=[self._build_bonus_skill(item) for item in payload.get("bonus") or []],
        )

    def _build_experience_requirements(self, payload: dict[str, Any]) -> JobExperienceRequirements:
        return JobExperienceRequirements(
            core=[self._build_core_experience(item) for item in payload.get("core") or []],
            bonus=[self._build_bonus_experience(item) for item in payload.get("bonus") or []],
            min_total_years=payload.get("min_total_years"),
            max_total_years=payload.get("max_total_years"),
        )

    def _build_education_constraints(self, payload: dict[str, Any]) -> JobEducationConstraints:
        return JobEducationConstraints(
            min_degree=payload.get("min_degree"),
            prefer_degrees=list(payload.get("prefer_degrees") or []),
            required_majors=list(payload.get("required_majors") or []),
            preferred_majors=list(payload.get("preferred_majors") or []),
            languages=[self._build_language(item) for item in payload.get("languages") or []],
            certifications=list(payload.get("certifications") or []),
            age_range=payload.get("age_range"),
            other=list(payload.get("other") or []),
        )

    def _build_required_skill(self, payload: dict[str, Any]) -> RequiredSkill:
        return RequiredSkill(
            name=str(payload.get("name") or "Skill Pending"),
            level=payload.get("level"),
            min_years=payload.get("min_years"),
            description=payload.get("description"),
        )

    def _build_optional_group(self, payload: dict[str, Any]) -> OptionalSkillGroup:
        return OptionalSkillGroup(
            group_name=str(payload.get("group_name") or "Optional Skills"),
            description=payload.get("description"),
            min_required=int(payload.get("min_required", 1)),
            skills=[self._build_optional_skill(item) for item in payload.get("skills") or []],
        )

    def _build_optional_skill(self, payload: dict[str, Any]) -> OptionalSkill:
        return OptionalSkill(
            name=str(payload.get("name") or "Skill Pending"),
            level=payload.get("level"),
            description=payload.get("description"),
        )

    def _build_bonus_skill(self, payload: dict[str, Any]) -> BonusSkill:
        return BonusSkill(
            name=str(payload.get("name") or "Skill Pending"),
            weight=payload.get("weight"),
            description=payload.get("description"),
        )

    def _build_core_experience(self, payload: dict[str, Any]) -> CoreExperience:
        return CoreExperience(
            type=str(payload.get("type") or "project"),
            name=str(payload.get("name") or "Experience Pending"),
            min_years=payload.get("min_years"),
            description=payload.get("description"),
            keywords=list(payload.get("keywords") or []),
        )

    def _build_bonus_experience(self, payload: dict[str, Any]) -> BonusExperience:
        return BonusExperience(
            type=str(payload.get("type") or "project"),
            name=str(payload.get("name") or "Experience Pending"),
            weight=payload.get("weight"),
            description=payload.get("description"),
            keywords=list(payload.get("keywords") or []),
        )

    def _build_language(self, payload: dict[str, Any]) -> LanguageRequirement:
        return LanguageRequirement(
            language=str(payload.get("language") or "Language Pending"),
            level=payload.get("level"),
            required=bool(payload.get("required", False)),
        )

    def _build_tag(self, payload: dict[str, Any]) -> JobTag:
        return JobTag(
            name=str(payload.get("name") or "Tag Pending"),
            category=payload.get("category"),
            weight=payload.get("weight"),
        )
