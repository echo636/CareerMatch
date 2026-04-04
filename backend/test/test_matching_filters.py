from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.clients.embedding import BaseEmbeddingClient
from app.clients.llm import BaseLLMClient
from app.clients.vector_store import InMemoryVectorStore
from app.domain.models import (
    GapInsight,
    JobBasicInfo,
    JobEducationConstraints,
    JobExperienceRequirements,
    JobFilterFacets,
    JobProfile,
    JobSkillRequirements,
    MatchFilters,
    ResumeBasicInfo,
    ResumeProfile,
    SalaryRange,
)
from app.repositories.in_memory import JobRepository, ResumeRepository
from app.repositories.payload_codec import job_from_payload
from app.services.gap_analysis import GapAnalysisService
from app.services.matching import MatchingService


class StaticEmbeddingClient(BaseEmbeddingClient):
    def embed_text(self, text: str, dimensions: int | None = None) -> list[float]:
        return [1.0, 0.0]


class FakeLLMClient(BaseLLMClient):
    def extract_resume(self, raw_text: str, file_name: str, resume_id: str) -> dict[str, object]:
        raise NotImplementedError

    def extract_job(self, payload: dict[str, object]) -> dict[str, object]:
        raise NotImplementedError

    def generate_gap_insights(
        self,
        missing_skills: list[str],
        salary_gap: int,
        experience_gap_years: int,
    ) -> list[GapInsight]:
        return [
            GapInsight(
                dimension="skills",
                current_state="current",
                target_state="target",
                suggestion="suggestion",
            )
        ]

    def score_job_match(self, resume_text: str, job_context: str) -> dict[str, object]:
        raise NotImplementedError


class MatchingFiltersTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.job_repository = JobRepository()
        self.resume_repository = ResumeRepository()
        self.vector_store = InMemoryVectorStore()
        self.matching_service = MatchingService(
            job_repository=self.job_repository,
            resume_repository=self.resume_repository,
            embedding_client=StaticEmbeddingClient(),
            vector_store=self.vector_store,
        )

        self.resume = ResumeProfile(
            id="resume-1",
            basic_info=ResumeBasicInfo(name="Candidate", work_years=2),
            educations=[],
            work_experiences=[],
            projects=[],
            skills=[],
            tags=[],
            expected_salary=SalaryRange(min=0, max=0),
            raw_text="candidate resume",
        )
        self.resume_repository.save(self.resume)

        now = datetime.now(timezone.utc)
        self.hardware_job = self._make_job(
            job_id="job-hardware",
            title="Hardware Engineer",
            location="Shanghai",
            job_type="fulltime",
            role_categories=["hardware_engineer"],
            work_modes=["onsite"],
            is_internship=False,
            posted_at=now - timedelta(days=2),
            min_years=3,
            max_years=5,
        )
        self.embedded_intern_job = self._make_job(
            job_id="job-embedded-intern",
            title="Embedded Engineer Intern",
            location="Beijing",
            job_type="intern",
            role_categories=["embedded_engineer"],
            work_modes=["onsite"],
            is_internship=True,
            posted_at=now - timedelta(days=1),
            min_years=0,
            max_years=1,
        )
        self.remote_frontend_job = self._make_job(
            job_id="job-frontend-remote",
            title="Frontend Engineer",
            location="Remote",
            job_type="fulltime",
            role_categories=["frontend_engineer"],
            work_modes=["remote"],
            is_internship=False,
            posted_at=now - timedelta(days=45),
            min_years=1,
            max_years=3,
        )

        self.job_repository.save_many(
            [
                self.hardware_job,
                self.embedded_intern_job,
                self.remote_frontend_job,
            ]
        )
        self.vector_store.upsert("jobs", self.hardware_job.id, [1.0, 0.0], "hardware")
        self.vector_store.upsert("jobs", self.embedded_intern_job.id, [0.98, 0.1], "embedded")
        self.vector_store.upsert("jobs", self.remote_frontend_job.id, [0.96, 0.2], "frontend")

    def test_recommend_filters_by_role_work_mode_and_post_time(self) -> None:
        filters = MatchFilters(
            role_categories=["frontend_engineer"],
            work_modes=["remote"],
            internship_preference="all",
            posted_within_days=90,
            min_experience_years=None,
            max_experience_years=None,
        )

        matches = self.matching_service.recommend(self.resume.id, top_k=5, filters=filters)

        self.assertEqual([match.job.id for match in matches], [self.remote_frontend_job.id])

    def test_recommend_filters_by_internship_and_experience(self) -> None:
        filters = MatchFilters(
            role_categories=["embedded_engineer", "hardware_engineer"],
            work_modes=[],
            internship_preference="intern",
            posted_within_days=None,
            min_experience_years=0,
            max_experience_years=1,
        )

        matches = self.matching_service.recommend(self.resume.id, top_k=5, filters=filters)

        self.assertEqual([match.job.id for match in matches], [self.embedded_intern_job.id])

    def test_gap_analysis_uses_same_filters(self) -> None:
        gap_analysis = GapAnalysisService(
            resume_repository=self.resume_repository,
            matching_service=self.matching_service,
            llm_client=FakeLLMClient(),
        )
        filters = MatchFilters(
            role_categories=["embedded_engineer"],
            work_modes=[],
            internship_preference="intern",
            posted_within_days=7,
            min_experience_years=None,
            max_experience_years=1,
        )

        report = gap_analysis.build_report(self.resume.id, top_k=3, filters=filters)

        self.assertEqual(report.baseline_roles, ["Embedded Engineer Intern"])

    def test_legacy_job_payload_gets_default_filter_facets(self) -> None:
        legacy_payload = {
            "id": "legacy-job",
            "company": "Example",
            "basic_info": {
                "title": "Embedded Engineer",
                "location": "Remote",
                "job_type": "intern",
                "summary": "Remote embedded intern role",
            },
            "skill_requirements": {"required": [], "optional_groups": [], "bonus": []},
            "experience_requirements": {"core": [], "bonus": [], "min_total_years": 0, "max_total_years": 1},
            "education_constraints": {},
            "tags": [],
            "created_at": "2026-04-01T00:00:00+00:00",
        }

        job = job_from_payload(legacy_payload)

        self.assertEqual(job.filter_facets.role_categories, ["embedded_engineer"])
        self.assertEqual(job.filter_facets.work_modes, ["remote"])
        self.assertTrue(job.filter_facets.is_internship)
        self.assertEqual(job.filter_facets.min_experience_years, 0.0)
        self.assertEqual(job.filter_facets.max_experience_years, 1.0)
        self.assertIsNotNone(job.filter_facets.posted_at)
        self.assertIsNotNone(job.filter_facets.posted_days_ago)

    def _make_job(
        self,
        *,
        job_id: str,
        title: str,
        location: str,
        job_type: str,
        role_categories: list[str],
        work_modes: list[str],
        is_internship: bool,
        posted_at: datetime,
        min_years: float,
        max_years: float,
    ) -> JobProfile:
        return JobProfile(
            id=job_id,
            company="Example Company",
            basic_info=JobBasicInfo(
                title=title,
                location=location,
                job_type=job_type,
                summary=title,
            ),
            skill_requirements=JobSkillRequirements(required=[], optional_groups=[], bonus=[]),
            experience_requirements=JobExperienceRequirements(
                core=[],
                bonus=[],
                min_total_years=min_years,
                max_total_years=max_years,
            ),
            education_constraints=JobEducationConstraints(),
            tags=[],
            filter_facets=JobFilterFacets(
                role_categories=role_categories,
                work_modes=work_modes,
                is_internship=is_internship,
                posted_at=posted_at.isoformat(),
                posted_days_ago=max(0, (datetime.now(timezone.utc).date() - posted_at.date()).days),
                min_experience_years=min_years,
                max_experience_years=max_years,
            ),
        )


if __name__ == "__main__":
    unittest.main()
