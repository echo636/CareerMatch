from __future__ import annotations

from app.clients.embedding import SimpleEmbeddingClient
from app.clients.vector_store import InMemoryVectorStore
from app.domain.models import JobProfile, MatchBreakdown, MatchResult, ResumeProfile
from app.repositories.in_memory import JobRepository, ResumeRepository


class MatchingService:
    def __init__(
        self,
        job_repository: JobRepository,
        resume_repository: ResumeRepository,
        embedding_client: SimpleEmbeddingClient,
        vector_store: InMemoryVectorStore,
    ) -> None:
        self.job_repository = job_repository
        self.resume_repository = resume_repository
        self.embedding_client = embedding_client
        self.vector_store = vector_store

    def recommend(self, resume_id: str, top_k: int = 5) -> list[MatchResult]:
        resume = self.resume_repository.get(resume_id)
        if resume is None:
            raise ValueError(f"Resume '{resume_id}' does not exist.")

        resume_vector = self.embedding_client.embed_text(self._resume_payload(resume))
        recall_size = max(top_k * 3, top_k)
        recalled = self.vector_store.query("jobs", resume_vector, recall_size)

        matches: list[MatchResult] = []
        for candidate in recalled:
            job = self.job_repository.get(str(candidate["id"]))
            if job is None or not self._passes_filters(resume, job):
                continue
            breakdown = self._build_breakdown(resume, job, float(candidate["score"]))
            matched_skills = [skill for skill in job.skills if skill.lower() in self._normalize_set(resume.skills)]
            missing_skills = [skill for skill in job.skills if skill.lower() not in self._normalize_set(resume.skills)]
            matches.append(
                MatchResult(
                    job=job,
                    breakdown=breakdown,
                    matched_skills=matched_skills,
                    missing_skills=missing_skills,
                    reasoning=self._build_reasoning(job, matched_skills, missing_skills),
                )
            )

        matches.sort(key=lambda item: item.breakdown.total, reverse=True)
        return matches[:top_k]

    def _passes_filters(self, resume: ResumeProfile, job: JobProfile) -> bool:
        candidate_skills = self._normalize_set(resume.skills)
        hard_requirements = [requirement.lower() for requirement in job.hard_requirements]
        hard_requirement_hit = all(
            requirement in candidate_skills or " " in requirement or len(requirement) <= 2
            for requirement in hard_requirements
        )
        salary_gap = resume.expected_salary.min - job.salary_range.max
        return hard_requirement_hit and salary_gap <= 8000

    def _build_breakdown(self, resume: ResumeProfile, job: JobProfile, vector_similarity: float) -> MatchBreakdown:
        resume_skills = self._normalize_set(resume.skills)
        job_skills = self._normalize_set(job.skills)
        resume_projects = self._normalize_set(resume.project_keywords)
        job_projects = self._normalize_set(job.project_keywords)

        skill_match = self._overlap_ratio(resume_skills, job_skills)
        project_match = self._overlap_ratio(resume_projects, job_projects)
        salary_match = self._salary_score(resume, job)
        total = round(
            0.35 * vector_similarity + 0.35 * skill_match + 0.2 * project_match + 0.1 * salary_match,
            4,
        )
        return MatchBreakdown(
            vector_similarity=round(vector_similarity, 4),
            skill_match=round(skill_match, 4),
            project_match=round(project_match, 4),
            salary_match=round(salary_match, 4),
            total=total,
        )

    def _build_reasoning(self, job: JobProfile, matched_skills: list[str], missing_skills: list[str]) -> str:
        matched_summary = " / ".join(matched_skills[:3]) or "基础能力"
        missing_summary = " / ".join(missing_skills[:2]) or "暂无明显缺口"
        return f"岗位与候选人在 {matched_summary} 上重合度较高，当前主要待补齐 {missing_summary}。"

    def _resume_payload(self, resume: ResumeProfile) -> str:
        return " ".join([resume.summary, *resume.skills, *resume.project_keywords])

    def _normalize_set(self, values: list[str]) -> set[str]:
        return {value.lower() for value in values}

    def _overlap_ratio(self, left: set[str], right: set[str]) -> float:
        if not right:
            return 1.0
        return len(left & right) / len(right)

    def _salary_score(self, resume: ResumeProfile, job: JobProfile) -> float:
        overlap_left = max(resume.expected_salary.min, job.salary_range.min)
        overlap_right = min(resume.expected_salary.max, job.salary_range.max)
        overlap = max(0, overlap_right - overlap_left)
        union_left = min(resume.expected_salary.min, job.salary_range.min)
        union_right = max(resume.expected_salary.max, job.salary_range.max)
        union = max(union_right - union_left, 1)
        return overlap / union
