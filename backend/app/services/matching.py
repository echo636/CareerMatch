from __future__ import annotations

import hashlib

from app.clients.embedding import BaseEmbeddingClient
from app.clients.vector_store import BaseVectorStore
from app.core.logging_utils import get_logger, get_score_logger, to_log_json
from app.domain.models import (
    BonusExperience,
    BonusSkill,
    CoreExperience,
    JobEducationConstraints,
    JobProfile,
    MatchBreakdown,
    MatchResult,
    OptionalSkill,
    OptionalSkillGroup,
    RequiredSkill,
    ResumeProfile,
)
from app.repositories.in_memory import JobRepository, ResumeRepository
from app.services.skill_aliases import normalize_skill_name

LEVEL_RANK = {
    "basic": 1,
    "intermediate": 2,
    "advanced": 3,
    "expert": 4,
}

DEGREE_RANK = {
    "high_school": 1,
    "高中": 1,
    "college": 2,
    "associate": 2,
    "大专": 2,
    "专科": 2,
    "bachelor": 3,
    "本科": 3,
    "学士": 3,
    "master": 4,
    "mba": 4,
    "硕士": 4,
    "研究生": 4,
    "phd": 5,
    "doctor": 5,
    "博士": 5,
}

logger = get_logger("services.matching")
score_logger = get_score_logger()


class MatchingService:
    def __init__(
        self,
        job_repository: JobRepository,
        resume_repository: ResumeRepository,
        embedding_client: BaseEmbeddingClient,
        vector_store: BaseVectorStore,
    ) -> None:
        self.job_repository = job_repository
        self.resume_repository = resume_repository
        self.embedding_client = embedding_client
        self.vector_store = vector_store

    def recommend(self, resume_id: str, top_k: int = 5) -> list[MatchResult]:
        logger.info("matching.start resume_id=%s top_k=%s", resume_id, top_k)
        resume = self.resume_repository.get(resume_id)
        if resume is None:
            logger.warning("matching.missing_resume resume_id=%s", resume_id)
            raise ValueError(f"Resume '{resume_id}' does not exist.")

        resume_vector = self._ensure_resume_vector(resume)
        job_count = self._job_count()
        recall_size = self._dynamic_recall_size(top_k, job_count)
        recalled = self.vector_store.query("jobs", resume_vector, recall_size)

        candidate_skill_index = self._build_candidate_skill_index(resume)
        candidate_terms = self._build_candidate_terms(resume)
        matches: list[MatchResult] = []
        candidate_logs: list[dict[str, object]] = []
        filtered_out = 0

        for candidate in recalled:
            candidate_score = float(candidate["score"])
            job = self.job_repository.get(str(candidate["id"]))
            if job is None:
                candidate_logs.append(
                    {
                        "job_id": str(candidate["id"]),
                        "status": "job_missing",
                        "vector_similarity": round(candidate_score, 4),
                    }
                )
                continue

            passed_filters, filter_reason = self._filter_decision(resume, job)
            if not passed_filters:
                filtered_out += 1
                candidate_logs.append(
                    {
                        "job_id": job.id,
                        "job_title": job.title,
                        "status": "filtered",
                        "filter_reason": filter_reason,
                        "vector_similarity": round(candidate_score, 4),
                    }
                )
                continue

            breakdown = self._build_breakdown(
                resume,
                job,
                candidate_score,
                candidate_skill_index,
                candidate_terms,
            )
            matched_skills = [skill for skill in job.skills if self._normalize_skill(skill) in candidate_skill_index]
            missing_skills = [skill for skill in job.skills if self._normalize_skill(skill) not in candidate_skill_index]
            match = MatchResult(
                job=job,
                breakdown=breakdown,
                matched_skills=matched_skills,
                missing_skills=missing_skills,
                reasoning=self._build_reasoning(job, matched_skills, missing_skills, breakdown),
            )
            matches.append(match)
            candidate_logs.append(
                {
                    "job_id": job.id,
                    "job_title": job.title,
                    "status": "matched",
                    "filter_reason": filter_reason,
                    "vector_similarity": round(candidate_score, 4),
                    "breakdown": {
                        "vector_similarity": breakdown.vector_similarity,
                        "skill_match": breakdown.skill_match,
                        "experience_match": breakdown.experience_match,
                        "education_match": breakdown.education_match,
                        "salary_match": breakdown.salary_match,
                        "total": breakdown.total,
                    },
                    "matched_skills": matched_skills,
                    "missing_skills": missing_skills,
                }
            )

        matches.sort(key=lambda item: item.breakdown.total, reverse=True)
        result = matches[:top_k]
        logger.info(
            "matching.completed resume_id=%s recalled=%s filtered_out=%s matched=%s returned=%s top_job=%s",
            resume_id,
            len(recalled),
            filtered_out,
            len(matches),
            len(result),
            result[0].job.title if result else None,
        )
        score_logger.info(
            to_log_json(
                {
                    "event": "matching.recommend",
                    "resume_id": resume_id,
                    "top_k": top_k,
                    "recall_size": recall_size,
                    "recalled_count": len(recalled),
                    "filtered_out": filtered_out,
                    "returned_count": len(result),
                    "candidates": candidate_logs,
                }
            )
        )
        return result

    def _filter_decision(
        self,
        resume: ResumeProfile,
        job: JobProfile,
    ) -> tuple[bool, str]:
        if self._minimum_degree_gate(resume, job.education_constraints) < 0.5:
            return False, "education_below_threshold"
        if self._salary_far_above_budget(resume, job):
            return False, "salary_far_above_budget"
        if self._direction_mismatch(resume, job):
            return False, "direction_mismatch"
        return True, "passed"

    def _salary_far_above_budget(self, resume: ResumeProfile, job: JobProfile) -> bool:
        """Filter out jobs where the candidate's minimum salary expectation
        is far above the job's maximum budget (> 1.5×)."""
        if not job.has_salary_reference:
            return False
        if resume.expected_salary.min <= 0:
            return False
        return resume.expected_salary.min > job.salary_range.max * 1.5

    def _direction_mismatch(self, resume: ResumeProfile, job: JobProfile) -> bool:
        """Filter out jobs that have zero tag overlap with the resume when both sides
        have meaningful tags, indicating a fundamental direction mismatch."""
        resume_tags = {
            normalize_skill_name(tag.name)
            for tag in resume.tags
            if (tag.category or "").lower() in {"tech", "domain", "industry"}
        }
        job_tags = {
            normalize_skill_name(tag.name)
            for tag in job.tags
            if (tag.category or "").lower() in {"tech", "domain", "industry"}
        }
        if len(resume_tags) < 3 or len(job_tags) < 3:
            return False
        return len(resume_tags & job_tags) == 0

    def _dynamic_recall_size(self, top_k: int, job_count: int) -> int:
        """Scale recall multiplier based on job pool size."""
        if job_count <= 50:
            multiplier = 3
        elif job_count <= 200:
            multiplier = 5
        elif job_count <= 1000:
            multiplier = 8
        else:
            multiplier = 10
        return max(top_k * multiplier, top_k)

    def _job_count(self) -> int:
        try:
            return len(self.job_repository.list())
        except Exception:
            return 0

    def _build_breakdown(
        self,
        resume: ResumeProfile,
        job: JobProfile,
        vector_similarity: float,
        candidate_skill_index: dict[str, dict[str, float | str | None]],
        candidate_terms: set[str],
    ) -> MatchBreakdown:
        required_scores = self._required_skill_scores(job, candidate_skill_index)
        optional_scores = self._optional_group_scores(job, candidate_skill_index)
        bonus_skill_score = self._bonus_skill_score(job, candidate_skill_index)
        skill_match = self._weighted_score(
            [
                (self._average(required_scores), 0.6 if required_scores else 0.0),
                (self._average(optional_scores), 0.25 if optional_scores else 0.0),
                (bonus_skill_score, 0.15 if job.skill_requirements.bonus else 0.0),
            ]
        )

        core_experience_scores = self._core_experience_scores(resume, job, candidate_skill_index, candidate_terms)
        bonus_experience_score = self._bonus_experience_score(resume, job, candidate_skill_index, candidate_terms)
        total_years_score = self._total_years_score(resume, job)
        experience_match = self._weighted_score(
            [
                (self._average(core_experience_scores), 0.6 if core_experience_scores else 0.0),
                (bonus_experience_score, 0.15 if job.experience_requirements.bonus else 0.0),
                (total_years_score, 0.25 if job.experience_requirements.min_total_years is not None else 0.0),
            ]
        )

        education_match = self._education_score(resume, job.education_constraints)
        salary_match = self._salary_score(resume, job)
        total = round(
            self._weighted_score(
                [
                    (vector_similarity, 0.2),
                    (skill_match, 0.35),
                    (experience_match, 0.25),
                    (education_match, 0.1 if self._has_education_constraints(job.education_constraints) else 0.0),
                    (salary_match, 0.1 if job.has_salary_reference else 0.0),
                ]
            ),
            4,
        )
        return MatchBreakdown(
            vector_similarity=round(vector_similarity, 4),
            skill_match=round(skill_match, 4),
            experience_match=round(experience_match, 4),
            education_match=round(education_match, 4),
            salary_match=round(salary_match, 4),
            total=total,
        )

    def _build_reasoning(
        self,
        job: JobProfile,
        matched_skills: list[str],
        missing_skills: list[str],
        breakdown: MatchBreakdown,
    ) -> str:
        strengths: list[str] = []
        if breakdown.skill_match >= 0.8:
            strengths.append("strong skill alignment")
        if breakdown.experience_match >= 0.75:
            strengths.append("experience matches well")
        if breakdown.education_match >= 0.8:
            strengths.append("education fits")
        if breakdown.salary_match >= 0.85:
            strengths.append("salary expectations overlap")

        strengths_summary = "; ".join(strengths[:2]) or "overall structured fit is reasonable"
        matched_summary = " / ".join(matched_skills[:3]) or "core skills"
        missing_summary = " / ".join(missing_skills[:2]) or "no obvious gaps"
        return f"{strengths_summary}; matched {matched_summary}; still missing {missing_summary}."

    def _resume_payload(self, resume: ResumeProfile) -> str:
        return " ".join([resume.summary, *resume.skill_names, *resume.project_keywords])

    def _ensure_resume_vector(self, resume: ResumeProfile) -> list[float]:
        payload = self._resume_payload(resume)
        payload_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        cached = self.vector_store.get("resumes", resume.id)
        if cached is not None and cached.payload_hash == payload_hash:
            logger.info(
                "matching.resume_vector.cache_hit resume_id=%s payload_hash=%s",
                resume.id,
                payload_hash[:12],
            )
            return cached.vector
        logger.info(
            "matching.resume_vector.compute resume_id=%s payload_hash=%s payload_length=%s",
            resume.id,
            payload_hash[:12],
            len(payload),
        )
        vector = self.embedding_client.embed_text(payload)
        self.vector_store.upsert("resumes", resume.id, vector, payload_hash)
        logger.info(
            "matching.resume_vector.saved resume_id=%s dimensions=%s",
            resume.id,
            len(vector),
        )
        return vector

    def _build_candidate_skill_index(self, resume: ResumeProfile) -> dict[str, dict[str, float | str | None]]:
        index: dict[str, dict[str, float | str | None]] = {}
        for skill in resume.skills:
            self._upsert_skill(index, skill.name, skill.level, float(skill.years) if skill.years is not None else None)
        for experience in resume.work_experiences:
            for skill_name in experience.tech_stack or []:
                self._upsert_skill(index, skill_name, None, None)
        for project in resume.projects:
            for skill_name in project.tech_stack or []:
                self._upsert_skill(index, skill_name, None, None)
        for tag in resume.tags:
            if (tag.category or "").lower() == "tech":
                self._upsert_skill(index, tag.name, None, None)
        return index

    def _normalize_skill(self, name: str) -> str:
        return normalize_skill_name(name)

    def _upsert_skill(
        self,
        index: dict[str, dict[str, float | str | None]],
        name: str,
        level: str | None,
        years: float | None,
    ) -> None:
        normalized = self._normalize_skill(name)
        if not normalized:
            return
        current = index.get(normalized)
        level_rank = float(self._level_rank(level))
        if current is None:
            index[normalized] = {
                "name": name.strip(),
                "level_rank": level_rank,
                "years": years,
            }
            return
        current_level_rank = float(current.get("level_rank") or 0.0)
        current["level_rank"] = max(current_level_rank, level_rank)
        current_years = current.get("years")
        if years is not None:
            if current_years is None or float(current_years) < years:
                current["years"] = years

    def _build_candidate_terms(self, resume: ResumeProfile) -> set[str]:
        terms: set[str] = set()
        self._add_terms(terms, resume.project_keywords)
        self._add_terms(terms, [project.name for project in resume.projects])
        self._add_terms(terms, [project.domain for project in resume.projects if project.domain])
        self._add_terms(terms, [tag.name for tag in resume.tags])
        self._add_terms(terms, [experience.industry for experience in resume.work_experiences if experience.industry])
        self._add_terms(terms, [experience.title for experience in resume.work_experiences if experience.title])
        self._add_terms(terms, [resume.basic_info.current_title] if resume.basic_info.current_title else [])
        self._add_terms(terms, [resume.basic_info.current_company] if resume.basic_info.current_company else [])
        return terms

    def _add_terms(self, target: set[str], values: list[str]) -> None:
        for value in values:
            normalized = value.strip().lower()
            if normalized:
                target.add(normalized)

    def _required_skill_scores(
        self,
        job: JobProfile,
        candidate_skill_index: dict[str, dict[str, float | str | None]],
    ) -> list[float]:
        return [
            self._score_required_skill(item, candidate_skill_index)
            for item in job.skill_requirements.required
        ]

    def _score_required_skill(
        self,
        requirement: RequiredSkill,
        candidate_skill_index: dict[str, dict[str, float | str | None]],
    ) -> float:
        candidate = candidate_skill_index.get(self._normalize_skill(requirement.name))
        if candidate is None:
            return 0.0
        scores = [1.0]
        if requirement.level:
            scores.append(
                self._level_score(
                    float(candidate.get("level_rank") or 0.0),
                    requirement.level,
                )
            )
        if requirement.min_years is not None:
            candidate_years = candidate.get("years")
            scores.append(
                self._ratio_score(
                    float(candidate_years) if candidate_years is not None else None,
                    float(requirement.min_years),
                )
            )
        return sum(scores) / len(scores)

    def _optional_group_scores(
        self,
        job: JobProfile,
        candidate_skill_index: dict[str, dict[str, float | str | None]],
    ) -> list[float]:
        scores: list[float] = []
        for group in job.skill_requirements.optional_groups:
            scores.append(self._score_optional_group(group, candidate_skill_index))
        return scores

    def _score_optional_group(
        self,
        group: OptionalSkillGroup,
        candidate_skill_index: dict[str, dict[str, float | str | None]],
    ) -> float:
        skill_scores = sorted(
            [self._score_optional_skill(skill, candidate_skill_index) for skill in group.skills or []],
            reverse=True,
        )
        required_count = max(group.min_required, 1)
        selected = skill_scores[:required_count]
        if len(selected) < required_count:
            selected.extend([0.0] * (required_count - len(selected)))
        return self._average(selected)

    def _score_optional_skill(
        self,
        skill: OptionalSkill,
        candidate_skill_index: dict[str, dict[str, float | str | None]],
    ) -> float:
        candidate = candidate_skill_index.get(self._normalize_skill(skill.name))
        if candidate is None:
            return 0.0
        if not skill.level:
            return 1.0
        return self._level_score(float(candidate.get("level_rank") or 0.0), skill.level)

    def _bonus_skill_score(
        self,
        job: JobProfile,
        candidate_skill_index: dict[str, dict[str, float | str | None]],
    ) -> float:
        weighted_components: list[tuple[float, float]] = []
        for skill in job.skill_requirements.bonus:
            weighted_components.append(
                (
                    self._score_bonus_skill(skill, candidate_skill_index),
                    float(skill.weight or 1),
                )
            )
        return self._weighted_score(weighted_components, default=1.0)

    def _score_bonus_skill(
        self,
        skill: BonusSkill,
        candidate_skill_index: dict[str, dict[str, float | str | None]],
    ) -> float:
        return 1.0 if self._normalize_skill(skill.name) in candidate_skill_index else 0.0

    def _core_experience_scores(
        self,
        resume: ResumeProfile,
        job: JobProfile,
        candidate_skill_index: dict[str, dict[str, float | str | None]],
        candidate_terms: set[str],
    ) -> list[float]:
        return [
            self._score_experience_item(item, resume, candidate_skill_index, candidate_terms)
            for item in job.experience_requirements.core
        ]

    def _bonus_experience_score(
        self,
        resume: ResumeProfile,
        job: JobProfile,
        candidate_skill_index: dict[str, dict[str, float | str | None]],
        candidate_terms: set[str],
    ) -> float:
        weighted_components: list[tuple[float, float]] = []
        for item in job.experience_requirements.bonus:
            weighted_components.append(
                (
                    self._score_bonus_experience(item, resume, candidate_skill_index, candidate_terms),
                    float(item.weight or 1),
                )
            )
        return self._weighted_score(weighted_components, default=1.0)

    def _score_bonus_experience(
        self,
        item: BonusExperience,
        resume: ResumeProfile,
        candidate_skill_index: dict[str, dict[str, float | str | None]],
        candidate_terms: set[str],
    ) -> float:
        return self._score_experience_term(
            item.type,
            item.name,
            item.keywords or [],
            item.description,
            None,
            resume,
            candidate_skill_index,
            candidate_terms,
        )

    def _score_experience_item(
        self,
        item: CoreExperience,
        resume: ResumeProfile,
        candidate_skill_index: dict[str, dict[str, float | str | None]],
        candidate_terms: set[str],
    ) -> float:
        return self._score_experience_term(
            item.type,
            item.name,
            item.keywords or [],
            item.description,
            item.min_years,
            resume,
            candidate_skill_index,
            candidate_terms,
        )

    def _score_experience_term(
        self,
        item_type: str,
        name: str,
        keywords: list[str],
        description: str | None,
        min_years: float | None,
        resume: ResumeProfile,
        candidate_skill_index: dict[str, dict[str, float | str | None]],
        candidate_terms: set[str],
    ) -> float:
        raw_text = resume.raw_text.lower()
        content_scores = [self._term_hit_score(name, candidate_terms, raw_text)]
        content_scores.extend(self._term_hit_score(keyword, candidate_terms, raw_text) for keyword in keywords)
        if description:
            content_scores.append(self._term_hit_score(description, candidate_terms, raw_text, exact=False))
        if item_type.lower() == "tech":
            tech_scores = [1.0 if self._normalize_skill(name) in candidate_skill_index else 0.0]
            tech_scores.extend(1.0 if self._normalize_skill(keyword) in candidate_skill_index else 0.0 for keyword in keywords)
            content_scores.append(max(tech_scores, default=0.0))

        content_score = max(content_scores, default=0.0)
        if content_score == 0.0:
            return 0.0

        weighted_components = [(content_score, 0.75)]
        if min_years is not None:
            weighted_components.append((self._ratio_score(float(resume.years_experience), float(min_years), 0.7), 0.25))
        return self._weighted_score(weighted_components, default=content_score)

    def _term_hit_score(
        self,
        term: str,
        candidate_terms: set[str],
        raw_text: str,
        exact: bool = True,
    ) -> float:
        normalized = term.strip().lower()
        if not normalized:
            return 0.0
        if normalized in candidate_terms:
            return 1.0
        if exact and normalized in raw_text:
            return 0.85
        if any(normalized in item or item in normalized for item in candidate_terms):
            return 0.7
        return 0.0

    def _total_years_score(self, resume: ResumeProfile, job: JobProfile) -> float:
        min_total_years = job.experience_requirements.min_total_years
        if min_total_years is None:
            return 1.0
        return self._ratio_score(float(resume.years_experience), float(min_total_years), 0.7)

    def _education_score(self, resume: ResumeProfile, constraints: JobEducationConstraints) -> float:
        weighted_components: list[tuple[float, float]] = []
        if constraints.min_degree:
            weighted_components.append((self._minimum_degree_gate(resume, constraints), 0.5))
        if constraints.prefer_degrees:
            weighted_components.append((self._preferred_degree_score(resume, constraints.prefer_degrees), 0.2))
        if constraints.required_majors:
            weighted_components.append((self._major_score(resume, constraints.required_majors, strict=True), 0.2))
        if constraints.preferred_majors:
            weighted_components.append((self._major_score(resume, constraints.preferred_majors, strict=False), 0.1))
        return self._weighted_score(weighted_components, default=1.0)

    def _minimum_degree_gate(self, resume: ResumeProfile, constraints: JobEducationConstraints) -> float:
        if not constraints.min_degree:
            return 1.0
        candidate_rank = self._candidate_degree_rank(resume)
        target_rank = self._degree_rank(constraints.min_degree)
        if target_rank == 0:
            return 1.0
        if candidate_rank == 0:
            return 0.65
        return min(candidate_rank / target_rank, 1.0)

    def _preferred_degree_score(self, resume: ResumeProfile, preferred_degrees: list[str]) -> float:
        candidate_rank = self._candidate_degree_rank(resume)
        if candidate_rank == 0:
            return 0.75
        target_ranks = [self._degree_rank(value) for value in preferred_degrees if self._degree_rank(value) > 0]
        if not target_ranks:
            return 1.0
        return max(min(candidate_rank / target_rank, 1.0) for target_rank in target_ranks)

    def _candidate_degree_rank(self, resume: ResumeProfile) -> float:
        ranks = [self._degree_rank(resume.basic_info.first_degree)]
        ranks.extend(self._degree_rank(education.degree) for education in resume.educations if education.degree)
        return max(ranks, default=0.0)

    def _major_score(self, resume: ResumeProfile, target_majors: list[str], strict: bool) -> float:
        candidate_majors = {
            education.major.lower()
            for education in resume.educations
            if education.major
        }
        if not candidate_majors:
            return 0.65 if strict else 0.8
        for target_major in target_majors:
            normalized = target_major.strip().lower()
            if not normalized:
                continue
            if normalized in candidate_majors:
                return 1.0
            if any(normalized in major or major in normalized for major in candidate_majors):
                return 0.85
        return 0.0 if strict else 0.7

    def _salary_score(self, resume: ResumeProfile, job: JobProfile) -> float:
        if not job.has_salary_reference:
            return 1.0
        overlap_left = max(resume.expected_salary.min, job.salary_range.min)
        overlap_right = min(resume.expected_salary.max, job.salary_range.max)
        overlap = max(0, overlap_right - overlap_left)
        union_left = min(resume.expected_salary.min, job.salary_range.min)
        union_right = max(resume.expected_salary.max, job.salary_range.max)
        union = max(union_right - union_left, 1)
        return overlap / union

    def _has_education_constraints(self, constraints: JobEducationConstraints) -> bool:
        return any(
            [
                constraints.min_degree,
                constraints.prefer_degrees,
                constraints.required_majors,
                constraints.preferred_majors,
            ]
        )

    def _weighted_score(self, components: list[tuple[float, float]], default: float = 1.0) -> float:
        active_components = [(score, weight) for score, weight in components if weight > 0]
        if not active_components:
            return default
        total_weight = sum(weight for _, weight in active_components)
        return sum(score * weight for score, weight in active_components) / total_weight

    def _average(self, values: list[float]) -> float:
        if not values:
            return 0.5
        return sum(values) / len(values)

    def _ratio_score(self, actual: float | None, target: float, unknown_floor: float = 0.65) -> float:
        if target <= 0:
            return 1.0
        if actual is None:
            return unknown_floor
        return max(0.0, min(actual / target, 1.0))

    def _level_score(self, candidate_rank: float, requirement_level: str) -> float:
        target_rank = self._level_rank(requirement_level)
        if target_rank == 0:
            return 1.0
        if candidate_rank == 0:
            return 0.65
        return min(candidate_rank / target_rank, 1.0)

    def _level_rank(self, level: str | None) -> int:
        return LEVEL_RANK.get((level or "").strip().lower(), 0)

    def _degree_rank(self, degree: str | None) -> int:
        return DEGREE_RANK.get((degree or "").strip().lower(), 0)
