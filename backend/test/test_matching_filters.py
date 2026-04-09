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
    CoreExperience,
    GapInsight,
    JobBasicInfo,
    JobEducationConstraints,
    JobExperienceRequirements,
    JobFilterFacets,
    JobProfile,
    JobSkillRequirements,
    JobTag,
    MatchFilters,
    ResumeBasicInfo,
    ResumeEducation,
    ResumeProfile,
    ResumeProject,
    ResumeSkill,
    ResumeTag,
    RequiredSkill,
    SalaryRange,
)
from app.repositories.in_memory import JobRepository, ResumeRepository
from app.repositories.payload_codec import job_from_payload
from app.core.config import default_matching_algorithm_config
from app.services.gap_analysis import GapAnalysisService
from app.services.matching import MatchingService


class StaticEmbeddingClient(BaseEmbeddingClient):
    def embed_text(self, text: str, dimensions: int | None = None) -> list[float]:
        return [1.0, 0.0]


class MappingEmbeddingClient(BaseEmbeddingClient):
    def __init__(self, mapping: dict[str, list[float]]) -> None:
        self.mapping = {key.lower(): value for key, value in mapping.items()}

    def embed_text(self, text: str, dimensions: int | None = None) -> list[float]:
        normalized = text.strip().lower()
        return list(self.mapping.get(normalized, [1.0, 0.0]))


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

    def test_semantic_skill_match_can_cover_non_alias_skill_names(self) -> None:
        embedding_client = MappingEmbeddingClient(
            {
                "prompt engineering": [1.0, 0.0],
                "prompt design": [0.99, 0.01],
                "java": [0.0, 1.0],
            }
        )
        job_repository = JobRepository()
        resume_repository = ResumeRepository()
        vector_store = InMemoryVectorStore()
        matching_service = MatchingService(
            job_repository=job_repository,
            resume_repository=resume_repository,
            embedding_client=embedding_client,
            vector_store=vector_store,
        )

        resume = ResumeProfile(
            id="resume-semantic",
            basic_info=ResumeBasicInfo(name="Semantic Candidate", work_years=2),
            educations=[],
            work_experiences=[],
            projects=[],
            skills=[ResumeSkill(name="Prompt Engineering")],
            tags=[],
            expected_salary=SalaryRange(min=0, max=0),
            raw_text="semantic resume",
        )
        resume_repository.save(resume)

        semantic_job = self._make_job(
            job_id="job-semantic",
            title="Product Engineer",
            location="Shanghai",
            job_type="fulltime",
            role_categories=["backend_engineer"],
            work_modes=["onsite"],
            is_internship=False,
            posted_at=datetime.now(timezone.utc),
            min_years=1,
            max_years=3,
        )
        semantic_job.skill_requirements = JobSkillRequirements(
            required=[RequiredSkill(name="Prompt Design")],
            optional_groups=[],
            bonus=[],
        )

        unrelated_job = self._make_job(
            job_id="job-unrelated",
            title="Backend Engineer",
            location="Shanghai",
            job_type="fulltime",
            role_categories=["backend_engineer"],
            work_modes=["onsite"],
            is_internship=False,
            posted_at=datetime.now(timezone.utc),
            min_years=1,
            max_years=3,
        )
        unrelated_job.skill_requirements = JobSkillRequirements(
            required=[RequiredSkill(name="Java")],
            optional_groups=[],
            bonus=[],
        )

        job_repository.save_many([semantic_job, unrelated_job])
        vector_store.upsert("jobs", semantic_job.id, [1.0, 0.0], "semantic")
        vector_store.upsert("jobs", unrelated_job.id, [0.95, 0.05], "unrelated")

        matches = matching_service.recommend(resume.id, top_k=2)
        match_index = {match.job.id: match for match in matches}

        self.assertIn(semantic_job.id, match_index)
        self.assertIn(unrelated_job.id, match_index)
        self.assertGreater(match_index[semantic_job.id].breakdown.skill_match, 0.5)
        self.assertGreater(
            match_index[semantic_job.id].breakdown.skill_match,
            match_index[unrelated_job.id].breakdown.skill_match,
        )
        self.assertIn("Prompt Design", match_index[semantic_job.id].matched_skills)
        self.assertNotIn("Prompt Design", match_index[semantic_job.id].missing_skills)

    def test_candidate_skill_index_infers_frontend_foundations_from_vue(self) -> None:
        resume = ResumeProfile(
            id="resume-frontend-foundation",
            basic_info=ResumeBasicInfo(name="Frontend Candidate", work_years=2),
            educations=[],
            work_experiences=[],
            projects=[],
            skills=[ResumeSkill(name="Vue.js")],
            tags=[],
            expected_salary=SalaryRange(min=0, max=0),
            raw_text="Vue.js frontend candidate",
        )

        index = self.matching_service._build_candidate_skill_index(resume)

        self.assertIn("vue", index)
        self.assertIn("html", index)
        self.assertIn("css", index)
        self.assertIn("javascript", index)
        self.assertLess(float(index["html"].get("confidence") or 1.0), 1.0)

    def test_experience_score_uses_project_text_and_skill_bridge(self) -> None:
        resume = ResumeProfile(
            id="resume-experience-bridge",
            basic_info=ResumeBasicInfo(name="Experienced Frontend", work_years=2),
            educations=[],
            work_experiences=[],
            projects=[
                ResumeProject(
                    name="数字孪生可视化平台",
                    role="前端开发",
                    description="使用 Vue3、TypeScript、Vite、ECharts 开发可视化大屏，并负责性能优化。",
                    responsibilities=["负责大屏可视化模块开发"],
                    achievements=[],
                    tech_stack=[],
                )
            ],
            skills=[ResumeSkill(name="Vue.js")],
            tags=[],
            expected_salary=SalaryRange(min=0, max=0),
            raw_text="2年前端经验，负责 Vue3 TypeScript Vite 大屏可视化平台开发。",
        )
        candidate_skill_index = self.matching_service._build_candidate_skill_index(resume)
        candidate_terms = self.matching_service._build_candidate_terms(resume)

        job = self._make_job(
            job_id="job-exp-bridge",
            title="Frontend Engineer",
            location="Shanghai",
            job_type="fulltime",
            role_categories=["frontend_engineer"],
            work_modes=["onsite"],
            is_internship=False,
            posted_at=datetime.now(timezone.utc),
            min_years=1,
            max_years=3,
        )
        job.skill_requirements = JobSkillRequirements(
            required=[RequiredSkill(name="Vue"), RequiredSkill(name="TypeScript")],
            optional_groups=[],
            bonus=[],
        )
        job.experience_requirements = JobExperienceRequirements(
            core=[
                CoreExperience(
                    type="project",
                    name="大屏可视化",
                    min_years=1,
                    keywords=["Vue3", "TypeScript"],
                    description="负责前端可视化大屏开发",
                )
            ],
            bonus=[],
            min_total_years=1,
            max_total_years=3,
        )

        breakdown = self.matching_service._build_breakdown(
            resume,
            job,
            0.6,
            candidate_skill_index,
            candidate_terms,
            {},
            {},
        )

        self.assertGreaterEqual(breakdown.skill_match, 0.6)
        self.assertGreaterEqual(breakdown.experience_match, 0.6)

    def test_direction_mismatch_allows_same_role_direction_despite_zero_tag_overlap(self) -> None:
        resume = ResumeProfile(
            id="resume-direction-frontend",
            basic_info=ResumeBasicInfo(name="Frontend Candidate", current_title="Frontend Engineer", work_years=2),
            educations=[],
            work_experiences=[],
            projects=[],
            skills=[ResumeSkill(name="Vue"), ResumeSkill(name="TypeScript")],
            tags=[
                ResumeTag(name="GIS", category="domain"),
                ResumeTag(name="Visualization", category="tech"),
                ResumeTag(name="Digital Twin", category="industry"),
            ],
            expected_salary=SalaryRange(min=0, max=0),
            raw_text="2 years frontend engineer, Vue and TypeScript",
        )
        job = self._make_job(
            job_id="job-direction-frontend",
            title="Frontend Engineer",
            location="Shanghai",
            job_type="fulltime",
            role_categories=["frontend_engineer"],
            work_modes=["onsite"],
            is_internship=False,
            posted_at=datetime.now(timezone.utc),
            min_years=1,
            max_years=3,
        )
        job.tags = [
            JobTag(name="Advertising", category="domain"),
            JobTag(name="Growth", category="industry"),
            JobTag(name="A/B Testing", category="tech"),
        ]

        self.assertFalse(self.matching_service._direction_mismatch(resume, job))

    def test_direction_mismatch_allows_skill_direction_overlap_for_generic_titles(self) -> None:
        resume = ResumeProfile(
            id="resume-direction-skill-overlap",
            basic_info=ResumeBasicInfo(name="Frontend Candidate", work_years=2),
            educations=[],
            work_experiences=[],
            projects=[],
            skills=[ResumeSkill(name="Vue"), ResumeSkill(name="TypeScript"), ResumeSkill(name="ECharts")],
            tags=[
                ResumeTag(name="GIS", category="domain"),
                ResumeTag(name="Visualization", category="tech"),
                ResumeTag(name="Digital Twin", category="industry"),
            ],
            expected_salary=SalaryRange(min=0, max=0),
            raw_text="Vue TypeScript frontend candidate",
        )
        job = self._make_job(
            job_id="job-direction-generic",
            title="Software Development Engineer",
            location="Shanghai",
            job_type="fulltime",
            role_categories=[],
            work_modes=["onsite"],
            is_internship=False,
            posted_at=datetime.now(timezone.utc),
            min_years=1,
            max_years=3,
        )
        job.skill_requirements = JobSkillRequirements(
            required=[RequiredSkill(name="Vue"), RequiredSkill(name="TypeScript")],
            optional_groups=[],
            bonus=[],
        )
        job.tags = [
            JobTag(name="Advertising", category="domain"),
            JobTag(name="Growth", category="industry"),
            JobTag(name="Operations Platform", category="tech"),
        ]

        self.assertFalse(self.matching_service._direction_mismatch(resume, job))

    def test_direction_mismatch_still_filters_conflicting_direction(self) -> None:
        resume = ResumeProfile(
            id="resume-direction-conflict",
            basic_info=ResumeBasicInfo(name="Frontend Candidate", current_title="Frontend Engineer", work_years=2),
            educations=[],
            work_experiences=[],
            projects=[],
            skills=[ResumeSkill(name="Vue"), ResumeSkill(name="TypeScript")],
            tags=[
                ResumeTag(name="GIS", category="domain"),
                ResumeTag(name="Visualization", category="tech"),
                ResumeTag(name="Digital Twin", category="industry"),
            ],
            expected_salary=SalaryRange(min=0, max=0),
            raw_text="2 years frontend engineer, Vue and TypeScript",
        )
        job = self._make_job(
            job_id="job-direction-backend",
            title="Backend Engineer",
            location="Shanghai",
            job_type="fulltime",
            role_categories=["backend_engineer"],
            work_modes=["onsite"],
            is_internship=False,
            posted_at=datetime.now(timezone.utc),
            min_years=1,
            max_years=3,
        )
        job.skill_requirements = JobSkillRequirements(
            required=[RequiredSkill(name="Java"), RequiredSkill(name="Spring Boot")],
            optional_groups=[],
            bonus=[],
        )
        job.tags = [
            JobTag(name="Payments", category="domain"),
            JobTag(name="Trading", category="industry"),
            JobTag(name="Microservices", category="tech"),
        ]

        self.assertTrue(self.matching_service._direction_mismatch(resume, job))

    def test_education_score_is_deemphasized_and_experience_weight_is_higher(self) -> None:
        config = default_matching_algorithm_config()
        self.assertGreater(config.total_weight_experience, config.total_weight_education)

        resume = ResumeProfile(
            id="resume-master",
            basic_info=ResumeBasicInfo(name="Master Candidate", work_years=2, first_degree="master"),
            educations=[ResumeEducation(school="Example University", degree="master", major="software engineering")],
            work_experiences=[],
            projects=[],
            skills=[],
            tags=[],
            expected_salary=SalaryRange(min=0, max=0),
            raw_text="master candidate",
        )
        constraints = JobEducationConstraints(min_degree="bachelor")

        score = self.matching_service._education_score(resume, constraints)

        self.assertLess(score, 0.9)
        self.assertGreaterEqual(score, 0.8)

    def test_default_recommend_filters_overqualified_internship_and_campus_roles(self) -> None:
        job_repository = JobRepository()
        resume_repository = ResumeRepository()
        vector_store = InMemoryVectorStore()
        matching_service = MatchingService(
            job_repository=job_repository,
            resume_repository=resume_repository,
            embedding_client=StaticEmbeddingClient(),
            vector_store=vector_store,
        )

        resume = ResumeProfile(
            id="resume-senior-default-filter",
            basic_info=ResumeBasicInfo(name="Senior Candidate", current_title="Senior Backend Engineer", work_years=8),
            educations=[],
            work_experiences=[],
            projects=[],
            skills=[ResumeSkill(name="Java"), ResumeSkill(name="Spring"), ResumeSkill(name="Netty")],
            tags=[],
            expected_salary=SalaryRange(min=0, max=0),
            raw_text="8 years senior backend engineer",
        )
        resume_repository.save(resume)

        now = datetime.now(timezone.utc)
        internship_job = self._make_job(
            job_id="job-overqualified-intern",
            title="Backend Engineer Intern",
            location="Shanghai",
            job_type="intern",
            role_categories=["backend_engineer"],
            work_modes=["onsite"],
            is_internship=True,
            posted_at=now,
            min_years=0,
            max_years=1,
        )
        campus_job = self._make_job(
            job_id="job-overqualified-campus",
            title="Campus Graduate Java Engineer",
            location="Shanghai",
            job_type="fulltime",
            role_categories=["backend_engineer"],
            work_modes=["onsite"],
            is_internship=False,
            posted_at=now,
            min_years=0,
            max_years=2,
        )
        regular_job = self._make_job(
            job_id="job-regular-senior",
            title="Senior Java Engineer",
            location="Shanghai",
            job_type="fulltime",
            role_categories=["backend_engineer"],
            work_modes=["onsite"],
            is_internship=False,
            posted_at=now,
            min_years=5,
            max_years=10,
        )

        job_repository.save_many([internship_job, campus_job, regular_job])
        vector_store.upsert("jobs", internship_job.id, [0.98, 0.02], "intern")
        vector_store.upsert("jobs", campus_job.id, [0.97, 0.03], "campus")
        vector_store.upsert("jobs", regular_job.id, [1.0, 0.0], "regular")

        matches = matching_service.recommend(resume.id, top_k=5)
        matched_job_ids = [match.job.id for match in matches]

        self.assertIn(regular_job.id, matched_job_ids)
        self.assertNotIn(internship_job.id, matched_job_ids)
        self.assertNotIn(campus_job.id, matched_job_ids)

    def test_role_level_penalty_demotes_entry_level_roles_for_senior_candidate(self) -> None:
        resume = ResumeProfile(
            id="resume-role-level",
            basic_info=ResumeBasicInfo(name="Senior Candidate", current_title="Senior Java Engineer", work_years=8),
            educations=[],
            work_experiences=[],
            projects=[],
            skills=[ResumeSkill(name="Java"), ResumeSkill(name="Spring")],
            tags=[],
            expected_salary=SalaryRange(min=0, max=0),
            raw_text="8 years senior java engineer",
        )
        candidate_skill_index = self.matching_service._build_candidate_skill_index(resume)
        candidate_terms = self.matching_service._build_candidate_terms(resume)

        junior_job = self._make_job(
            job_id="job-junior-java",
            title="Junior Java Engineer",
            location="Shanghai",
            job_type="fulltime",
            role_categories=["backend_engineer"],
            work_modes=["onsite"],
            is_internship=False,
            posted_at=datetime.now(timezone.utc),
            min_years=0,
            max_years=2,
        )
        junior_job.skill_requirements = JobSkillRequirements(
            required=[RequiredSkill(name="Java"), RequiredSkill(name="Spring")],
            optional_groups=[],
            bonus=[],
        )

        senior_job = self._make_job(
            job_id="job-senior-java",
            title="Senior Java Engineer",
            location="Shanghai",
            job_type="fulltime",
            role_categories=["backend_engineer"],
            work_modes=["onsite"],
            is_internship=False,
            posted_at=datetime.now(timezone.utc),
            min_years=5,
            max_years=10,
        )
        senior_job.skill_requirements = JobSkillRequirements(
            required=[RequiredSkill(name="Java"), RequiredSkill(name="Spring")],
            optional_groups=[],
            bonus=[],
        )

        junior_breakdown = self.matching_service._build_breakdown(
            resume,
            junior_job,
            0.64,
            candidate_skill_index,
            candidate_terms,
            {},
            {},
        )
        senior_breakdown = self.matching_service._build_breakdown(
            resume,
            senior_job,
            0.64,
            candidate_skill_index,
            candidate_terms,
            {},
            {},
        )

        self.assertLess(junior_breakdown.role_level_fit, senior_breakdown.role_level_fit)
        self.assertLess(junior_breakdown.total, senior_breakdown.total)
        self.assertLess(junior_breakdown.penalty_multiplier, senior_breakdown.penalty_multiplier)

    def test_stack_transition_keeps_adjacent_backend_roles_competitive(self) -> None:
        matching_service = MatchingService(
            job_repository=JobRepository(),
            resume_repository=ResumeRepository(),
            embedding_client=MappingEmbeddingClient(
                {
                    "java": [1.0, 0.0],
                    "spring": [0.95, 0.05],
                    "go": [0.0, 1.0],
                    "tcp/ip": [0.5, 0.5],
                }
            ),
            vector_store=InMemoryVectorStore(),
        )
        resume = ResumeProfile(
            id="resume-stack-transition",
            basic_info=ResumeBasicInfo(name="Backend Candidate", current_title="Senior Java Backend Engineer", work_years=8),
            educations=[],
            work_experiences=[],
            projects=[],
            skills=[
                ResumeSkill(name="Java"),
                ResumeSkill(name="Spring"),
                ResumeSkill(name="Netty"),
                ResumeSkill(name="TCP/IP"),
            ],
            tags=[],
            expected_salary=SalaryRange(min=0, max=0),
            raw_text="8 years java backend engineer with netty tcp ip distributed systems",
        )
        candidate_skill_index = matching_service._build_candidate_skill_index(resume)
        candidate_terms = matching_service._build_candidate_terms(resume)

        go_job = self._make_job(
            job_id="job-go-backend",
            title="Senior Go Backend Engineer",
            location="Shanghai",
            job_type="fulltime",
            role_categories=["backend_engineer"],
            work_modes=["onsite"],
            is_internship=False,
            posted_at=datetime.now(timezone.utc),
            min_years=5,
            max_years=10,
        )
        go_job.skill_requirements = JobSkillRequirements(
            required=[RequiredSkill(name="Go"), RequiredSkill(name="TCP/IP")],
            optional_groups=[],
            bonus=[],
        )
        go_job.basic_info.summary = "High concurrency distributed backend with network protocols"

        breakdown = matching_service._build_breakdown(
            resume,
            go_job,
            0.64,
            candidate_skill_index,
            candidate_terms,
            {},
            {},
        )

        self.assertEqual(breakdown.title_skill_alignment, 0.0)
        self.assertGreaterEqual(breakdown.transition_score, 0.55)
        self.assertGreaterEqual(breakdown.role_level_fit, 0.9)
        self.assertGreaterEqual(breakdown.penalty_multiplier, 0.45)
        self.assertGreaterEqual(breakdown.total, 0.2)

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
