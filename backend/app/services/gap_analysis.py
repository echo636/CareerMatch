from __future__ import annotations

from app.clients.llm import BaseLLMClient
from app.core.logging_utils import get_logger
from app.domain.models import GapReport
from app.repositories.in_memory import ResumeRepository
from app.services.matching import MatchingService

logger = get_logger("services.gap_analysis")


class GapAnalysisService:
    def __init__(
        self,
        resume_repository: ResumeRepository,
        matching_service: MatchingService,
        llm_client: BaseLLMClient,
    ) -> None:
        self.resume_repository = resume_repository
        self.matching_service = matching_service
        self.llm_client = llm_client

    def build_report(self, resume_id: str, top_k: int = 3) -> GapReport:
        logger.info("gap_analysis.start resume_id=%s top_k=%s", resume_id, top_k)
        resume = self.resume_repository.get(resume_id)
        if resume is None:
            logger.warning("gap_analysis.missing_resume resume_id=%s", resume_id)
            raise ValueError(f"Resume '{resume_id}' does not exist.")

        matches = self.matching_service.recommend(resume_id, top_k)
        baseline_roles = [match.job.title for match in matches]
        missing_skills = self._collect_missing_skills(matches)
        salary_gap = max(0, round(self._average_target_salary(matches) - resume.expected_salary.max))
        experience_gap = max(0, round(self._average_target_experience(matches) - resume.years_experience))
        insights = self.llm_client.generate_gap_insights(missing_skills, salary_gap, experience_gap)

        report = GapReport(
            baseline_roles=baseline_roles,
            missing_skills=missing_skills,
            salary_gap=salary_gap,
            experience_gap_years=experience_gap,
            insights=insights,
        )
        logger.info(
            "gap_analysis.completed resume_id=%s matches=%s baseline_roles=%s missing_skills=%s insights=%s salary_gap=%s experience_gap=%s",
            resume_id,
            len(matches),
            len(report.baseline_roles),
            len(report.missing_skills),
            len(report.insights),
            report.salary_gap,
            report.experience_gap_years,
        )
        return report

    def _collect_missing_skills(self, matches: list) -> list[str]:
        ordered: list[str] = []
        seen: set[str] = set()
        for match in matches:
            for skill in match.missing_skills:
                normalized = skill.lower()
                if normalized not in seen:
                    seen.add(normalized)
                    ordered.append(skill)
        return ordered

    def _average_target_salary(self, matches: list) -> float:
        if not matches:
            return 0
        return sum(match.job.salary_range.max for match in matches) / len(matches)

    def _average_target_experience(self, matches: list) -> float:
        if not matches:
            return 0
        return sum(match.job.experience_years for match in matches) / len(matches)
