from __future__ import annotations

from typing import Any

from app.clients.embedding import BaseEmbeddingClient
from app.clients.llm import BaseLLMClient
from app.clients.vector_store import InMemoryVectorStore
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
from app.repositories.in_memory import JobRepository


class JobPipelineService:
    def __init__(
        self,
        repository: JobRepository,
        llm_client: BaseLLMClient,
        embedding_client: BaseEmbeddingClient,
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

    def _vector_payload(self, job: JobProfile) -> str:
        return " ".join([job.summary, *job.skills, *job.project_keywords])

    def _build_basic_info(self, payload: dict[str, Any]) -> JobBasicInfo:
        return JobBasicInfo(
            title=str(payload.get("title") or "鏈懡鍚嶅矖浣?"),
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
            name=str(payload.get("name") or "寰呰ˉ鍏呮妧鑳?"),
            level=payload.get("level"),
            min_years=payload.get("min_years"),
            description=payload.get("description"),
        )

    def _build_optional_group(self, payload: dict[str, Any]) -> OptionalSkillGroup:
        return OptionalSkillGroup(
            group_name=str(payload.get("group_name") or "鍙€夋妧鑳界粍"),
            description=payload.get("description"),
            min_required=int(payload.get("min_required", 1)),
            skills=[self._build_optional_skill(item) for item in payload.get("skills") or []],
        )

    def _build_optional_skill(self, payload: dict[str, Any]) -> OptionalSkill:
        return OptionalSkill(
            name=str(payload.get("name") or "寰呰ˉ鍏呮妧鑳?"),
            level=payload.get("level"),
            description=payload.get("description"),
        )

    def _build_bonus_skill(self, payload: dict[str, Any]) -> BonusSkill:
        return BonusSkill(
            name=str(payload.get("name") or "寰呰ˉ鍏呮妧鑳?"),
            weight=payload.get("weight"),
            description=payload.get("description"),
        )

    def _build_core_experience(self, payload: dict[str, Any]) -> CoreExperience:
        return CoreExperience(
            type=str(payload.get("type") or "project"),
            name=str(payload.get("name") or "寰呰ˉ鍏呯粡楠?"),
            min_years=payload.get("min_years"),
            description=payload.get("description"),
            keywords=list(payload.get("keywords") or []),
        )

    def _build_bonus_experience(self, payload: dict[str, Any]) -> BonusExperience:
        return BonusExperience(
            type=str(payload.get("type") or "project"),
            name=str(payload.get("name") or "寰呰ˉ鍏呯粡楠?"),
            weight=payload.get("weight"),
            description=payload.get("description"),
            keywords=list(payload.get("keywords") or []),
        )

    def _build_language(self, payload: dict[str, Any]) -> LanguageRequirement:
        return LanguageRequirement(
            language=str(payload.get("language") or "寰呰ˉ鍏呰瑷€"),
            level=payload.get("level"),
            required=bool(payload.get("required", False)),
        )

    def _build_tag(self, payload: dict[str, Any]) -> JobTag:
        return JobTag(
            name=str(payload.get("name") or "寰呰ˉ鍏呮爣绛?"),
            category=payload.get("category"),
            weight=payload.get("weight"),
        )
