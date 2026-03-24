from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterable

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
    ResumeBasicInfo,
    ResumeEducation,
    ResumeProfile,
    ResumeProject,
    ResumeSkill,
    ResumeTag,
    ResumeWorkExperience,
    SalaryRange,
)


class _SqliteJsonRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS resumes (
                    id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.commit()


class SqliteResumeRepository(_SqliteJsonRepository):
    def count(self) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) FROM resumes").fetchone()
        return int(row[0]) if row is not None else 0

    def save(self, resume: ResumeProfile) -> ResumeProfile:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO resumes (id, payload_json)
                VALUES (?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (resume.id, json.dumps(asdict(resume), ensure_ascii=False, separators=(",", ":"))),
            )
            connection.commit()
        return resume

    def get(self, resume_id: str) -> ResumeProfile | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM resumes WHERE id = ?",
                (resume_id,),
            ).fetchone()
        if row is None:
            return None
        return _resume_from_payload(json.loads(row[0]))

    def list(self) -> list[ResumeProfile]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload_json FROM resumes ORDER BY updated_at DESC, id ASC"
            ).fetchall()
        return [_resume_from_payload(json.loads(row[0])) for row in rows]


class SqliteJobRepository(_SqliteJsonRepository):
    def count(self) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) FROM jobs").fetchone()
        return int(row[0]) if row is not None else 0

    def save(self, job: JobProfile) -> JobProfile:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO jobs (id, payload_json)
                VALUES (?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (job.id, json.dumps(asdict(job), ensure_ascii=False, separators=(",", ":"))),
            )
            connection.commit()
        return job

    def save_many(self, jobs: Iterable[JobProfile]) -> list[JobProfile]:
        values = list(jobs)
        if not values:
            return []
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO jobs (id, payload_json)
                VALUES (?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                [
                    (job.id, json.dumps(asdict(job), ensure_ascii=False, separators=(",", ":")))
                    for job in values
                ],
            )
            connection.commit()
        return values

    def get(self, job_id: str) -> JobProfile | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        if row is None:
            return None
        return _job_from_payload(json.loads(row[0]))

    def list(self) -> list[JobProfile]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload_json FROM jobs ORDER BY updated_at DESC, id ASC"
            ).fetchall()
        return [_job_from_payload(json.loads(row[0])) for row in rows]


def _resume_from_payload(payload: dict[str, Any]) -> ResumeProfile:
    return ResumeProfile(
        id=str(payload.get("id") or ""),
        basic_info=ResumeBasicInfo(**(payload.get("basic_info") or {})),
        educations=[ResumeEducation(**item) for item in payload.get("educations") or []],
        work_experiences=[ResumeWorkExperience(**item) for item in payload.get("work_experiences") or []],
        projects=[ResumeProject(**item) for item in payload.get("projects") or []],
        skills=[ResumeSkill(**item) for item in payload.get("skills") or []],
        tags=[ResumeTag(**item) for item in payload.get("tags") or []],
        expected_salary=SalaryRange(**(payload.get("expected_salary") or {"min": 0, "max": 0, "currency": "CNY"})),
        is_resume=payload.get("is_resume"),
        raw_text=str(payload.get("raw_text") or ""),
        source_file_name=str(payload.get("source_file_name") or ""),
        source_content_type=str(payload.get("source_content_type") or ""),
        source_object_key=str(payload.get("source_object_key") or ""),
    )


def _job_from_payload(payload: dict[str, Any]) -> JobProfile:
    skill_requirements = payload.get("skill_requirements") or {}
    experience_requirements = payload.get("experience_requirements") or {}
    education_constraints = payload.get("education_constraints") or {}
    return JobProfile(
        id=str(payload.get("id") or ""),
        company=str(payload.get("company") or "Company Pending"),
        basic_info=JobBasicInfo(**(payload.get("basic_info") or {"title": "Untitled Role"})),
        skill_requirements=JobSkillRequirements(
            required=[RequiredSkill(**item) for item in skill_requirements.get("required") or []],
            optional_groups=[
                OptionalSkillGroup(
                    group_name=str(item.get("group_name") or "Optional Skills"),
                    description=item.get("description"),
                    min_required=int(item.get("min_required", 1)),
                    skills=[OptionalSkill(**skill) for skill in item.get("skills") or []],
                )
                for item in skill_requirements.get("optional_groups") or []
            ],
            bonus=[BonusSkill(**item) for item in skill_requirements.get("bonus") or []],
        ),
        experience_requirements=JobExperienceRequirements(
            core=[CoreExperience(**item) for item in experience_requirements.get("core") or []],
            bonus=[BonusExperience(**item) for item in experience_requirements.get("bonus") or []],
            min_total_years=experience_requirements.get("min_total_years"),
            max_total_years=experience_requirements.get("max_total_years"),
        ),
        education_constraints=JobEducationConstraints(
            min_degree=education_constraints.get("min_degree"),
            prefer_degrees=list(education_constraints.get("prefer_degrees") or []),
            required_majors=list(education_constraints.get("required_majors") or []),
            preferred_majors=list(education_constraints.get("preferred_majors") or []),
            languages=[LanguageRequirement(**item) for item in education_constraints.get("languages") or []],
            certifications=list(education_constraints.get("certifications") or []),
            age_range=education_constraints.get("age_range"),
            other=list(education_constraints.get("other") or []),
        ),
        tags=[JobTag(**item) for item in payload.get("tags") or []],
    )
