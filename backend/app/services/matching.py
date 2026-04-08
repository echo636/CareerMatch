from __future__ import annotations

import hashlib
from math import sqrt
import re

from app.clients.embedding import BaseEmbeddingClient
from app.clients.vector_store import BaseVectorStore
from app.core.config import MatchingAlgorithmConfig, default_matching_algorithm_config
from app.core.logging_utils import get_logger, get_score_logger, to_log_json
from app.domain.models import (
    BonusExperience,
    BonusSkill,
    CoreExperience,
    JobEducationConstraints,
    JobProfile,
    MatchBreakdown,
    MatchFilters,
    MatchResult,
    OptionalSkill,
    OptionalSkillGroup,
    RequiredSkill,
    ResumeProfile,
    is_placeholder_text,
)
from app.job_enrichment import infer_skills
from app.repositories.in_memory import JobRepository, ResumeRepository
from app.services.skill_aliases import normalize_skill_name

LEVEL_RANK = {
    "basic": 1,
    "intermediate": 2,
    "advanced": 3,
    "expert": 4,
}

SKILL_VECTOR_NAMESPACE = "skill_terms"
DOMAIN_VECTOR_NAMESPACE = "domain_terms"
FRONTEND_FRAMEWORK_SKILLS = {
    "vue",
    "react",
    "angular",
    "next.js",
    "nuxt.js",
    "svelte",
}
FRONTEND_SIGNAL_SKILLS = FRONTEND_FRAMEWORK_SKILLS | {
    "javascript",
    "typescript",
    "html",
    "css",
    "vite",
    "webpack",
    "pinia",
    "vue router",
    "element-ui",
    "tailwindcss",
    "echarts",
    "uniapp",
}
BACKEND_SIGNAL_SKILLS = {
    "java",
    "spring",
    "spring boot",
    "python",
    "django",
    "flask",
    "fastapi",
    "php",
    "laravel",
    "go",
    "mysql",
    "postgresql",
    "redis",
}
MOBILE_SIGNAL_SKILLS = {
    "android",
    "ios",
    "flutter",
    "react native",
    "swift",
    "objective-c",
    "kotlin",
    "uniapp",
}
DIRECTIONAL_SIGNAL_SKILLS = FRONTEND_SIGNAL_SKILLS | BACKEND_SIGNAL_SKILLS | MOBILE_SIGNAL_SKILLS
GIT_PLATFORM_SKILLS = {"gitee", "github", "gitlab"}
TEXT_DERIVED_SKILL_CONFIDENCE = 0.92
INFERRED_FOUNDATION_CONFIDENCE = 0.78
INFERRED_TOOL_CONFIDENCE = 0.84

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

TITLE_PRIMARY_SKILL_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("java", ("java",)),
    ("python", ("python",)),
    ("go", ("golang", "go", "go语言")),
    ("php", ("php",)),
    ("c++", ("c++", "cpp")),
    ("c#", ("c#", "csharp", ".net", "dotnet")),
    ("javascript", ("javascript", "js", "前端")),
    ("typescript", ("typescript", "ts")),
    ("react", ("react",)),
    ("vue", ("vue",)),
    ("flutter", ("flutter",)),
    ("android", ("android",)),
    ("ios", ("ios", "swift", "objective-c")),
    ("kotlin", ("kotlin",)),
    ("llm", ("llm", "大模型", "ai", "人工智能")),
)

SPECIALIZED_ROLE_KEYWORDS = (
    "高级",
    "专家",
    "核心自研",
    "大模型",
    "银行",
    "保险",
    "交易",
    "稳定性",
    "高并发",
    "分布式",
    "云原生",
    "平台方向",
)

LEAD_ROLE_KEYWORDS = (
    "主管",
    "主程",
    "经理",
    "总监",
    "负责人",
    "leader",
    "架构师",
)

GENERIC_ROLE_PATTERNS = (
    "前端，后端，测试岗位均有",
    "前端、后端，测试岗位均有",
    "前端/后端/测试",
    "前后端开发/测试",
    "前端后端测试",
    "多方向",
    "均有",
)

RESUME_ROLE_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("frontend_engineer", ("前端", "frontend", "react", "vue", "javascript", "typescript", "web前端")),
    ("backend_engineer", ("后端", "backend", "server", "php", "laravel", "python", "java", "spring", "golang", "go语言")),
    ("fullstack_engineer", ("全栈", "full stack", "fullstack")),
    ("algorithm_engineer", ("算法", "algorithm", "机器学习", "machine learning", "深度学习", "llm", "大模型", "nlp", "cv")),
    ("data_engineer", ("数据", "data", "etl", "数仓", "大数据")),
    ("mobile_engineer", ("android", "ios", "flutter", "uniapp", "react native", "小程序", "app")),
    ("testing_engineer", ("测试", "qa", "test", "testing")),
)

STACK_TRANSITION_BRIDGES: dict[str, dict[str, float]] = {
    "go": {"php": 0.72, "laravel": 0.74, "python": 0.58, "java": 0.60, "mysql": 0.18, "redis": 0.18},
    "python": {"php": 0.68, "laravel": 0.70, "java": 0.35, "go": 0.52, "mysql": 0.20, "redis": 0.20},
    "java": {"php": 0.42, "laravel": 0.44, "python": 0.35, "go": 0.55, "mysql": 0.18, "redis": 0.18},
    "php": {"python": 0.62, "go": 0.58, "java": 0.40, "mysql": 0.22, "redis": 0.22},
    "react": {"vue": 0.90, "javascript": 0.92, "typescript": 0.94, "uniapp": 0.58, "flutter": 0.38},
    "vue": {"react": 0.88, "javascript": 0.92, "typescript": 0.94, "uniapp": 0.74, "flutter": 0.36},
    "flutter": {"uniapp": 0.70, "android": 0.58, "ios": 0.52, "react": 0.42, "vue": 0.34},
    "javascript": {"typescript": 0.96, "vue": 0.92, "react": 0.92},
    "typescript": {"javascript": 0.96, "vue": 0.92, "react": 0.92},
}

CITY_REGION_GROUPS: tuple[set[str], ...] = (
    {"上海", "杭州", "苏州", "南京", "无锡", "宁波", "嘉兴", "绍兴", "湖州", "常州", "昆山"},
    {"北京", "天津", "石家庄", "廊坊"},
    {"深圳", "广州", "东莞", "佛山", "珠海", "惠州"},
)

CLOSE_CITY_PAIRS: set[frozenset[str]] = {
    frozenset({"上海", "杭州"}),
    frozenset({"上海", "苏州"}),
    frozenset({"上海", "昆山"}),
    frozenset({"深圳", "广州"}),
    frozenset({"深圳", "东莞"}),
    frozenset({"广州", "佛山"}),
    frozenset({"北京", "天津"}),
    frozenset({"杭州", "宁波"}),
    frozenset({"南京", "苏州"}),
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
        algorithm_config: MatchingAlgorithmConfig | None = None,
    ) -> None:
        self.job_repository = job_repository
        self.resume_repository = resume_repository
        self.embedding_client = embedding_client
        self.vector_store = vector_store
        self.algorithm_config = algorithm_config or default_matching_algorithm_config()

    def recommend(self, resume_id: str, top_k: int = 5, filters: MatchFilters | None = None) -> list[MatchResult]:
        active_filters = filters if filters and filters.is_active else None
        logger.info(
            "matching.start resume_id=%s top_k=%s filters=%s",
            resume_id,
            top_k,
            self._serialize_filters(active_filters),
        )
        resume = self.resume_repository.get(resume_id)
        if resume is None:
            logger.warning("matching.missing_resume resume_id=%s", resume_id)
            raise ValueError(f"Resume '{resume_id}' does not exist.")

        resume_vector = self._ensure_resume_vector(resume)
        job_count = self._job_count()
        recall_size = self._dynamic_recall_size(top_k, job_count, active_filters)
        recalled = self.vector_store.query("jobs", resume_vector, recall_size)

        candidate_skill_index = self._build_candidate_skill_index(resume)
        candidate_terms = self._build_candidate_terms(resume)
        skill_vector_cache: dict[str, list[float] | None] = {}
        domain_vector_cache: dict[str, list[float] | None] = {}
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

            passed_filters, filter_reason = self._filter_decision(resume, job, active_filters)
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
                skill_vector_cache,
                domain_vector_cache,
            )
            matched_skills = [
                skill
                for skill in job.skills
                if self._skill_match_exists(skill, candidate_skill_index, skill_vector_cache)
            ]
            missing_skills = [
                skill
                for skill in job.skills
                if not self._skill_match_exists(skill, candidate_skill_index, skill_vector_cache)
            ]
            tier = self._classify_tier(resume, job, breakdown)
            match = MatchResult(
                job=job,
                breakdown=breakdown,
                matched_skills=matched_skills,
                missing_skills=missing_skills,
                reasoning=self._build_reasoning(job, matched_skills, missing_skills, breakdown),
                tier=tier,
            )
            matches.append(match)
            candidate_logs.append(
                {
                    "job_id": job.id,
                    "job_title": job.title,
                    "status": "matched",
                    "filter_reason": filter_reason,
                    "vector_similarity": round(candidate_score, 4),
                    "tier": tier,
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
        result = self._diversify_matches(matches, top_k)
        logger.info(
            "matching.completed resume_id=%s recalled=%s filtered_out=%s matched=%s returned=%s top_job=%s filters=%s",
            resume_id,
            len(recalled),
            filtered_out,
            len(matches),
            len(result),
            result[0].job.title if result else None,
            self._serialize_filters(active_filters),
        )
        score_logger.info(
            to_log_json(
                {
                    "event": "matching.recommend",
                    "resume_id": resume_id,
                    "top_k": top_k,
                    "filters": self._serialize_filters(active_filters),
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
        filters: MatchFilters | None = None,
    ) -> tuple[bool, str]:
        if filters is not None:
            passed_requested_filters, requested_filter_reason = self._matches_requested_filters(job, filters)
            if not passed_requested_filters:
                return False, requested_filter_reason
        if self._minimum_degree_gate(resume, job.education_constraints) < self.algorithm_config.minimum_degree_filter_threshold:
            return False, "education_below_threshold"
        if self._salary_far_above_budget(resume, job):
            return False, "salary_far_above_budget"
        if self._direction_mismatch(resume, job):
            return False, "direction_mismatch"
        if self._clear_role_mismatch(resume, job):
            return False, "role_mismatch"
        return True, "passed"

    def _serialize_filters(self, filters: MatchFilters | None) -> dict[str, object] | None:
        if filters is None or not filters.is_active:
            return None
        return {
            "role_categories": list(filters.role_categories),
            "work_modes": list(filters.work_modes),
            "internship_preference": filters.internship_preference,
            "posted_within_days": filters.posted_within_days,
            "min_experience_years": filters.min_experience_years,
            "max_experience_years": filters.max_experience_years,
        }

    def _matches_requested_filters(self, job: JobProfile, filters: MatchFilters) -> tuple[bool, str]:
        job_role_categories = {value.lower() for value in job.filter_facets.role_categories}
        if filters.role_categories and not (job_role_categories & {value.lower() for value in filters.role_categories}):
            return False, "user_role_category_filtered"

        job_work_modes = {value.lower() for value in job.filter_facets.work_modes}
        if filters.work_modes and not (job_work_modes & {value.lower() for value in filters.work_modes}):
            return False, "user_work_mode_filtered"

        if filters.internship_preference == "intern" and job.filter_facets.is_internship is not True:
            return False, "user_internship_filtered"
        if filters.internship_preference == "fulltime" and job.filter_facets.is_internship is True:
            return False, "user_fulltime_filtered"

        if filters.posted_within_days is not None:
            posted_days_ago = job.filter_facets.posted_days_ago
            if posted_days_ago is None or posted_days_ago > filters.posted_within_days:
                return False, "user_post_time_filtered"

        if not self._matches_experience_range(job, filters):
            return False, "user_experience_filtered"

        return True, "passed"

    def _matches_experience_range(self, job: JobProfile, filters: MatchFilters) -> bool:
        if filters.min_experience_years is None and filters.max_experience_years is None:
            return True

        job_min = job.filter_facets.min_experience_years
        job_max = job.filter_facets.max_experience_years
        if job_min is None and job_max is None:
            return True

        effective_min = job_min if job_min is not None else job_max
        effective_max = job_max if job_max is not None else job_min

        if filters.min_experience_years is not None and effective_max is not None and effective_max < filters.min_experience_years:
            return False
        if filters.max_experience_years is not None and effective_min is not None and effective_min > filters.max_experience_years:
            return False
        return True

    def _salary_far_above_budget(self, resume: ResumeProfile, job: JobProfile) -> bool:
        """Filter out jobs where the candidate's minimum salary expectation
        is far above the job's maximum budget (> 1.5×)."""
        if not job.has_salary_reference:
            return False
        if resume.expected_salary.min <= 0:
            return False
        return resume.expected_salary.min > job.salary_range.max * self.algorithm_config.salary_far_above_budget_ratio

    def _classify_tier(
        self,
        resume: ResumeProfile,
        job: JobProfile,
        breakdown: MatchBreakdown,
    ) -> str:
        """Classify the match as reach/match/safety (冲/稳/保).

        After ranking by non-salary match score, classify each job based on
        how the job's salary compares to the candidate's expectation:
          - 冲 (reach):  job pays significantly above expectations
          - 稳 (match):  job salary roughly aligns with expectations
          - 保 (safety): job pays at or below expectations
        """
        ratio = self._salary_aspiration_ratio(resume, job)

        # No salary data on either side → default to 稳
        if ratio == 1.0 and (
            resume.expected_salary.min <= 0 or not job.has_salary_reference
        ):
            return "match"

        if ratio >= self.algorithm_config.tier_reach_ratio:
            return "reach"
        if ratio <= self.algorithm_config.tier_safety_ratio:
            return "safety"
        return "match"

    def _salary_aspiration_ratio(self, resume: ResumeProfile, job: JobProfile) -> float:
        """How aspirational is the job's salary relative to the candidate's expectation.

        Returns job_midpoint / resume_midpoint.  A ratio > 1 means the job pays
        more than the candidate expects; < 1 means it pays less.
        Returns 1.0 (neutral) when either side lacks salary data.
        """
        resume_mid = (resume.expected_salary.min + resume.expected_salary.max) / 2
        if resume_mid <= 0:
            return 1.0
        if not job.has_salary_reference:
            return 1.0
        job_mid = (job.salary_range.min + job.salary_range.max) / 2
        if job_mid <= 0:
            return 1.0
        return job_mid / resume_mid

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
        min_tag_count = self.algorithm_config.direction_mismatch_min_tag_count
        if len(resume_tags) < min_tag_count or len(job_tags) < min_tag_count:
            return False
        if resume_tags & job_tags:
            return False
        return not self._has_directional_alignment(resume, job)

    def _has_directional_alignment(self, resume: ResumeProfile, job: JobProfile) -> bool:
        candidate_roles = self._resume_role_categories(resume)
        job_roles = {value.lower() for value in job.filter_facets.role_categories}

        if candidate_roles & job_roles:
            return True
        if "fullstack_engineer" in candidate_roles and job_roles & {"frontend_engineer", "backend_engineer"}:
            return True
        if "fullstack_engineer" in job_roles and candidate_roles & {"frontend_engineer", "backend_engineer"}:
            return True

        resume_signals = self._directional_signal_skills(
            [
                resume.basic_info.current_title or "",
                *resume.skill_names[:24],
                *resume.project_keywords[:12],
            ]
        )
        job_signals = self._directional_signal_skills(
            [
                job.title,
                *job.hard_requirements[:12],
                *job.skills[:20],
                *job.project_keywords[:12],
            ]
        )
        return bool(resume_signals & job_signals)

    def _directional_signal_skills(self, values: list[str]) -> set[str]:
        signals: set[str] = set()
        for value in values:
            for expanded_name in self._expand_skill_names(value):
                normalized = self._normalize_skill(expanded_name)
                if normalized in DIRECTIONAL_SIGNAL_SKILLS:
                    signals.add(normalized)
        return signals

    def _clear_role_mismatch(self, resume: ResumeProfile, job: JobProfile) -> bool:
        candidate_roles = self._resume_role_categories(resume)
        job_roles = {value.lower() for value in job.filter_facets.role_categories}

        candidate_frontend = "frontend_engineer" in candidate_roles
        candidate_backend = bool(candidate_roles & {"backend_engineer", "fullstack_engineer"})
        job_frontend = "frontend_engineer" in job_roles
        job_backend = bool(job_roles & {"backend_engineer", "fullstack_engineer"})

        if candidate_frontend and not candidate_backend and job_backend and not job_frontend:
            return True
        if "algorithm_engineer" in job_roles and "algorithm_engineer" not in candidate_roles:
            return True
        if "data_engineer" in job_roles and not (candidate_roles & {"data_engineer", "backend_engineer", "fullstack_engineer"}):
            return True
        return False

    def _dynamic_recall_size(self, top_k: int, job_count: int, filters: MatchFilters | None = None) -> int:
        """Scale recall multiplier based on job pool size."""
        config = self.algorithm_config
        if job_count <= config.recall_small_job_pool_max:
            multiplier = config.recall_multiplier_small
        elif job_count <= config.recall_medium_job_pool_max:
            multiplier = config.recall_multiplier_medium
        elif job_count <= config.recall_large_job_pool_max:
            multiplier = config.recall_multiplier_large
        else:
            multiplier = config.recall_multiplier_xlarge
        recall_size = max(top_k * multiplier, top_k)
        if filters is not None and filters.is_active:
            recall_size = max(
                recall_size,
                top_k * max(multiplier * config.filtered_recall_scale, config.filtered_recall_min_multiplier),
            )
        if job_count > 0:
            return min(recall_size, job_count)
        return recall_size

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
        skill_vector_cache: dict[str, list[float] | None],
        domain_vector_cache: dict[str, list[float] | None],
    ) -> MatchBreakdown:
        required_scores = self._required_skill_scores(job, candidate_skill_index, skill_vector_cache)
        optional_scores = self._optional_group_scores(job, candidate_skill_index, skill_vector_cache)
        bonus_skill_score = self._bonus_skill_score(job, candidate_skill_index, skill_vector_cache)
        required_coverage = self._average(required_scores)
        transition_score = self._stack_transition_score(resume, job, candidate_skill_index)
        skill_match = self._weighted_score(
            [
                (
                    required_coverage,
                    self.algorithm_config.skill_required_weight if required_scores else 0.0,
                ),
                (
                    self._average(optional_scores),
                    self.algorithm_config.skill_optional_weight if optional_scores else 0.0,
                ),
                (
                    bonus_skill_score,
                    self.algorithm_config.skill_bonus_weight if job.skill_requirements.bonus else 0.0,
                ),
            ],
            default=0.5,
        )
        title_skill_alignment = self._title_primary_skill_alignment(job, candidate_skill_index, skill_vector_cache)
        if title_skill_alignment == 0.0:
            skill_match = max(min(skill_match * 0.25, 0.10), round(transition_score * 0.6, 4))

        core_experience_scores = self._core_experience_scores(
            resume,
            job,
            candidate_skill_index,
            candidate_terms,
            skill_vector_cache,
        )
        bonus_experience_score = self._bonus_experience_score(
            resume,
            job,
            candidate_skill_index,
            candidate_terms,
            skill_vector_cache,
        )
        total_years_score = self._total_years_score(resume, job)
        experience_match = self._weighted_score(
            [
                (
                    self._average(core_experience_scores),
                    self.algorithm_config.experience_core_weight if core_experience_scores else 0.0,
                ),
                (
                    bonus_experience_score,
                    self.algorithm_config.experience_bonus_weight if job.experience_requirements.bonus else 0.0,
                ),
                (
                    total_years_score,
                    self.algorithm_config.experience_total_years_weight
                    if job.experience_requirements.min_total_years is not None
                    else 0.0,
                ),
            ],
            default=0.5,
        )

        education_match = self._education_score(resume, job.education_constraints)
        salary_match = self._salary_score(resume, job)
        domain_match = self._domain_relevance_score(resume, job, candidate_terms, domain_vector_cache)
        location_match = self._location_match_score(resume, job)
        total = round(
            self._weighted_score(
                [
                    (vector_similarity, self.algorithm_config.total_weight_vector),
                    (skill_match, self.algorithm_config.total_weight_skill),
                    (experience_match, self.algorithm_config.total_weight_experience),
                    (
                        education_match,
                        self.algorithm_config.total_weight_education
                        if self._has_education_constraints(job.education_constraints)
                        else 0.0,
                    ),
                    (domain_match, self.algorithm_config.total_weight_domain),
                    (location_match, self.algorithm_config.total_weight_location),
                    (
                        salary_match,
                        self.algorithm_config.total_weight_salary if job.has_salary_reference else 0.0,
                    ),
                ]
            ),
            4,
        )
        total = round(
            total
            * self._hard_skill_penalty(job, required_scores, candidate_skill_index, skill_vector_cache),
            4,
        )
        total = round(
            total
            * self._specialized_role_penalty(job, domain_match, title_skill_alignment),
            4,
        )
        total = round(
            total
            * self._underpay_location_penalty(resume, job, location_match),
            4,
        )
        total = round(
            total
            * self._lead_role_penalty(job, title_skill_alignment, transition_score, location_match, salary_match),
            4,
        )
        total = round(
            self._cap_zero_skill_transition_mismatch(
                total,
                job,
                skill_match,
                required_coverage,
                title_skill_alignment,
                transition_score,
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
        self._augment_text_derived_candidate_skills(index, resume)
        self._augment_inferred_candidate_skills(index)
        return index

    def _normalize_skill(self, name: str) -> str:
        return normalize_skill_name(name)

    def _upsert_skill(
        self,
        index: dict[str, dict[str, float | str | None]],
        name: str,
        level: str | None,
        years: float | None,
        confidence: float = 1.0,
    ) -> None:
        if is_placeholder_text(name):
            return
        level_rank = float(self._level_rank(level))
        for expanded_name in self._expand_skill_names(name):
            normalized = self._normalize_skill(expanded_name)
            if not normalized:
                continue
            current = index.get(normalized)
            if current is None:
                index[normalized] = {
                    "name": expanded_name.strip(),
                    "level_rank": level_rank,
                    "years": years,
                    "confidence": confidence,
                }
                continue
            current_level_rank = float(current.get("level_rank") or 0.0)
            current["level_rank"] = max(current_level_rank, level_rank)
            current_years = current.get("years")
            if years is not None:
                if current_years is None or float(current_years) < years:
                    current["years"] = years
            current_confidence = float(current.get("confidence") or 0.0)
            current["confidence"] = max(current_confidence, confidence)

    def _expand_skill_names(self, value: str) -> list[str]:
        cleaned = value.strip()
        if not cleaned or is_placeholder_text(cleaned):
            return []
        delimiter_pattern = r"[\\/|、，,；;]+"
        extracted = infer_skills({}, cleaned)
        parts = [
            token.strip("()（）[]{}+·• ")
            for token in re.split(
                delimiter_pattern,
                cleaned.replace("（", "/").replace("）", "/").replace("(", "/").replace(")", "/"),
            )
            if token.strip("()（）[]{}+·• ")
        ]
        candidates = [*parts, *extracted]
        if not candidates:
            candidates = [cleaned]
        elif len(candidates) == 1 and self._normalize_skill(candidates[0]) == self._normalize_skill(cleaned):
            candidates = [cleaned]

        ordered: list[str] = []
        seen: set[str] = set()
        for item in candidates:
            normalized = self._normalize_skill(item)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            ordered.append(item.strip())
        return ordered or [cleaned]

    def _augment_text_derived_candidate_skills(
        self,
        index: dict[str, dict[str, float | str | None]],
        resume: ResumeProfile,
    ) -> None:
        text_parts: list[str] = [resume.summary, resume.raw_text]
        for experience in resume.work_experiences:
            text_parts.extend(experience.responsibilities or [])
            text_parts.extend(experience.achievements or [])
            if experience.title:
                text_parts.append(experience.title)
        for project in resume.projects:
            if project.name:
                text_parts.append(project.name)
            if project.role:
                text_parts.append(project.role)
            if project.description:
                text_parts.append(project.description)
            text_parts.extend(project.responsibilities or [])
            text_parts.extend(project.achievements or [])
        derived_skills = infer_skills({}, "\n".join(part for part in text_parts if part))
        for skill_name in derived_skills:
            self._upsert_skill(index, skill_name, None, None, TEXT_DERIVED_SKILL_CONFIDENCE)

    def _augment_inferred_candidate_skills(
        self,
        index: dict[str, dict[str, float | str | None]],
    ) -> None:
        normalized_skills = set(index.keys())
        has_frontend_signal = bool(normalized_skills & FRONTEND_FRAMEWORK_SKILLS) or len(
            normalized_skills & FRONTEND_SIGNAL_SKILLS
        ) >= 2
        if has_frontend_signal:
            for skill_name in ("html", "css", "javascript"):
                self._upsert_skill(index, skill_name, None, None, INFERRED_FOUNDATION_CONFIDENCE)
        if "git" not in normalized_skills and normalized_skills & GIT_PLATFORM_SKILLS:
            self._upsert_skill(index, "git", None, None, INFERRED_TOOL_CONFIDENCE)

    def _build_candidate_terms(self, resume: ResumeProfile) -> set[str]:
        terms: set[str] = set()
        self._add_terms(terms, resume.skill_names)
        self._add_terms(terms, resume.project_keywords)
        self._add_terms(terms, [project.name for project in resume.projects])
        self._add_terms(terms, [project.domain for project in resume.projects if project.domain])
        self._add_terms(terms, [project.description for project in resume.projects if project.description])
        self._add_terms(terms, [item for project in resume.projects for item in (project.responsibilities or [])])
        self._add_terms(terms, [item for project in resume.projects for item in (project.achievements or [])])
        self._add_terms(terms, [tag.name for tag in resume.tags])
        self._add_terms(terms, [experience.industry for experience in resume.work_experiences if experience.industry])
        self._add_terms(terms, [experience.title for experience in resume.work_experiences if experience.title])
        self._add_terms(terms, [item for experience in resume.work_experiences for item in (experience.responsibilities or [])])
        self._add_terms(terms, [item for experience in resume.work_experiences for item in (experience.achievements or [])])
        self._add_terms(terms, [resume.basic_info.current_title] if resume.basic_info.current_title else [])
        self._add_terms(terms, [resume.basic_info.current_company] if resume.basic_info.current_company else [])
        return terms

    def _add_terms(self, target: set[str], values: list[str]) -> None:
        for value in values:
            if is_placeholder_text(value):
                continue
            normalized = value.strip().lower()
            if normalized:
                target.add(normalized)

    def _hard_skill_penalty(
        self,
        job: JobProfile,
        required_scores: list[float],
        candidate_skill_index: dict[str, dict[str, float | str | None]],
        skill_vector_cache: dict[str, list[float] | None],
    ) -> float:
        config = self.algorithm_config
        penalty = self._title_skill_penalty(job, candidate_skill_index, skill_vector_cache)
        if job.skill_requirements.required and required_scores:
            primary_scores = required_scores[: min(2, len(required_scores))]
            primary_coverage = self._average(primary_scores)
            required_coverage = self._average(required_scores)
            if primary_coverage < config.hard_skill_primary_threshold:
                penalty *= config.hard_skill_primary_penalty
            if required_coverage < config.hard_skill_required_threshold:
                penalty *= config.hard_skill_required_penalty
        return penalty

    def _title_skill_penalty(
        self,
        job: JobProfile,
        candidate_skill_index: dict[str, dict[str, float | str | None]],
        skill_vector_cache: dict[str, list[float] | None],
    ) -> float:
        alignment = self._title_primary_skill_alignment(job, candidate_skill_index, skill_vector_cache)
        penalty_floor = self.algorithm_config.title_skill_mismatch_penalty
        return round(penalty_floor + ((1.0 - penalty_floor) * alignment), 4)

    def _title_primary_skill_alignment(
        self,
        job: JobProfile,
        candidate_skill_index: dict[str, dict[str, float | str | None]],
        skill_vector_cache: dict[str, list[float] | None],
    ) -> float:
        title_primary_skills = self._extract_title_primary_skills(job.title)
        if not title_primary_skills:
            return 1.0
        matched = sum(
            1
            for skill_name in title_primary_skills
            if self._skill_match_exists(skill_name, candidate_skill_index, skill_vector_cache)
        )
        return matched / len(title_primary_skills)

    def _specialized_role_penalty(
        self,
        job: JobProfile,
        domain_match: float,
        title_skill_alignment: float,
    ) -> float:
        searchable_text = f"{job.title} {job.summary}".lower()
        if not any(keyword.lower() in searchable_text for keyword in SPECIALIZED_ROLE_KEYWORDS):
            return 1.0
        if title_skill_alignment >= 0.5 and domain_match >= 0.65:
            return 1.0
        if title_skill_alignment >= 0.5 and domain_match >= 0.5:
            return 0.9
        if title_skill_alignment > 0 and domain_match >= 0.5:
            return 0.85
        return self.algorithm_config.specialized_role_penalty

    def _underpay_location_penalty(
        self,
        resume: ResumeProfile,
        job: JobProfile,
        location_match: float,
    ) -> float:
        if not job.has_salary_reference or resume.expected_salary.min <= 0:
            return 1.0
        ceiling_ratio = job.salary_range.max / max(resume.expected_salary.min, 1)
        if ceiling_ratio >= 1.0:
            return 1.0
        if "remote" in job.filter_facets.work_modes:
            return 1.0
        if ceiling_ratio < 0.8 and location_match < 1.0:
            return 0.72
        if ceiling_ratio < 0.8:
            return 0.86
        if ceiling_ratio < 0.9 and location_match < 0.7:
            return 0.88
        return 1.0

    def _lead_role_penalty(
        self,
        job: JobProfile,
        title_skill_alignment: float,
        transition_score: float,
        location_match: float,
        salary_match: float,
    ) -> float:
        title = job.title.lower()
        if not any(keyword in title for keyword in LEAD_ROLE_KEYWORDS):
            return 1.0
        if title_skill_alignment >= 1.0:
            return 1.0
        if transition_score >= 0.75 and location_match >= 1.0 and salary_match >= 0.9:
            return 1.0
        if location_match < 1.0 and salary_match < 0.9:
            return 0.72
        if location_match < 0.7 or salary_match < 0.8:
            return 0.82
        return 0.9

    def _resume_role_categories(self, resume: ResumeProfile) -> set[str]:
        searchable_parts = [
            resume.basic_info.current_title or "",
            resume.summary,
            resume.raw_text,
            " ".join(resume.skill_names[:16]),
            " ".join(resume.project_keywords[:16]),
        ]
        searchable_text = " ".join(part.lower() for part in searchable_parts if part)
        matched = {
            category
            for category, keywords in RESUME_ROLE_KEYWORDS
            if any(keyword in searchable_text for keyword in keywords)
        }
        if "fullstack_engineer" in matched:
            matched.add("backend_engineer")
            matched.add("frontend_engineer")
        return matched

    def _stack_transition_score(
        self,
        resume: ResumeProfile,
        job: JobProfile,
        candidate_skill_index: dict[str, dict[str, float | str | None]],
    ) -> float:
        target_primary_skills = set(self._extract_title_primary_skills(job.title))
        target_primary_skills.update(
            self._normalize_skill(item.name)
            for item in job.skill_requirements.required[:3]
            if self._normalize_skill(item.name) in STACK_TRANSITION_BRIDGES
        )
        if not target_primary_skills:
            return 0.0

        candidate_skill_keys = set(candidate_skill_index)
        candidate_roles = self._resume_role_categories(resume)
        if "fullstack_engineer" in candidate_roles:
            candidate_roles.add("backend_engineer")

        best_score = 0.0
        for target_skill in target_primary_skills:
            if target_skill in candidate_skill_keys:
                return 1.0
            bridge_scores = [
                bridge_score
                for source_skill, bridge_score in STACK_TRANSITION_BRIDGES.get(target_skill, {}).items()
                if source_skill in candidate_skill_keys
            ]
            score = max(bridge_scores, default=0.0)
            if target_skill in {"go", "python", "php", "java"} and "backend_engineer" in candidate_roles:
                score = max(score, 0.38)
            if target_skill in {"react", "vue", "javascript", "typescript"} and (
                candidate_roles & {"frontend_engineer", "fullstack_engineer", "mobile_engineer"}
            ):
                score = max(score, 0.42)
            best_score = max(best_score, score)
        return best_score

    def _cap_zero_skill_transition_mismatch(
        self,
        total: float,
        job: JobProfile,
        skill_match: float,
        required_coverage: float,
        title_skill_alignment: float,
        transition_score: float,
    ) -> float:
        job_roles = {value.lower() for value in job.filter_facets.role_categories}
        if title_skill_alignment > 0 or transition_score >= 0.35:
            return total
        if required_coverage > 0.15 or skill_match > 0.18:
            return total
        if job_roles & {"algorithm_engineer", "data_engineer"}:
            return min(total, 0.08)
        if any(keyword.lower() in f"{job.title} {job.summary}".lower() for keyword in SPECIALIZED_ROLE_KEYWORDS):
            return min(total, 0.10)
        return min(total, 0.12)

    def _extract_title_primary_skills(self, title: str) -> list[str]:
        normalized_title = title.strip().lower()
        if not normalized_title:
            return []
        matched: list[str] = []
        for canonical, patterns in TITLE_PRIMARY_SKILL_PATTERNS:
            if any(pattern in normalized_title for pattern in patterns):
                matched.append(canonical)
        return matched

    def _domain_relevance_score(
        self,
        resume: ResumeProfile,
        job: JobProfile,
        candidate_terms: set[str],
        domain_vector_cache: dict[str, list[float] | None],
    ) -> float:
        term_overlap = self._domain_term_overlap_score(job, candidate_terms)
        resume_payload = self._resume_domain_payload(resume)
        job_payload = self._job_domain_payload(job)
        if not resume_payload or not job_payload:
            return max(term_overlap, 0.5 if term_overlap == 0 else term_overlap)

        resume_vector = self._ensure_aux_text_vector(DOMAIN_VECTOR_NAMESPACE, resume_payload, domain_vector_cache)
        job_vector = self._ensure_aux_text_vector(DOMAIN_VECTOR_NAMESPACE, job_payload, domain_vector_cache)
        if resume_vector is None or job_vector is None:
            return max(term_overlap, 0.5 if term_overlap == 0 else term_overlap)

        semantic_score = max(0.0, self._cosine_similarity(resume_vector, job_vector))
        if term_overlap == 0:
            return max(semantic_score, 0.5)
        return max(term_overlap, semantic_score)

    def _location_match_score(self, resume: ResumeProfile, job: JobProfile) -> float:
        target_cities = self._resume_target_cities(resume)
        if "remote" in job.filter_facets.work_modes:
            return 1.0
        if not target_cities:
            return 0.5
        job_locations = self._job_location_tokens(job)
        if not job_locations:
            return 0.5
        if target_cities & job_locations:
            return 1.0
        if self._are_close_cities(target_cities, job_locations):
            return 0.55
        if self._share_city_region(target_cities, job_locations):
            return 0.35
        return 0.10

    def _are_close_cities(self, left: set[str], right: set[str]) -> bool:
        for city_a in left:
            for city_b in right:
                if frozenset({city_a, city_b}) in CLOSE_CITY_PAIRS:
                    return True
        return False

    def _domain_term_overlap_score(self, job: JobProfile, candidate_terms: set[str]) -> float:
        if not candidate_terms:
            return 0.0
        job_terms: set[str] = set()
        self._add_terms(job_terms, job.project_keywords)
        self._add_terms(job_terms, [tag.name for tag in job.tags if (tag.category or "").lower() in {"domain", "industry", "project"}])
        self._add_terms(job_terms, [job.title, job.company])
        if not job_terms:
            return 0.0

        exact_hits = len(job_terms & candidate_terms)
        if exact_hits > 0:
            denominator = max(1, min(len(job_terms), 4))
            return min(exact_hits / denominator, 1.0)

        summary_text = f"{job.title} {job.summary}".lower()
        fuzzy_hits = sum(
            1
            for term in candidate_terms
            if len(term) >= 2 and (term in summary_text or summary_text.find(term) != -1)
        )
        if fuzzy_hits == 0:
            return 0.0
        denominator = max(1, min(len(candidate_terms), 4))
        return min((fuzzy_hits / denominator) * 0.8, 0.8)

    def _resume_domain_payload(self, resume: ResumeProfile) -> str:
        parts: list[str] = [resume.summary]
        parts.extend(resume.project_keywords[:12])
        parts.extend(project.name for project in resume.projects[:6] if project.name)
        parts.extend(project.description or "" for project in resume.projects[:4] if project.description)
        parts.extend(experience.title or "" for experience in resume.work_experiences[:4] if experience.title)
        parts.extend(experience.industry or "" for experience in resume.work_experiences[:4] if experience.industry)
        return " ".join(part for part in parts if part).strip()

    def _job_domain_payload(self, job: JobProfile) -> str:
        parts: list[str] = [job.title, job.summary, job.company]
        parts.extend(job.project_keywords[:12])
        parts.extend(tag.name for tag in job.tags[:12] if tag.name)
        parts.extend((job.basic_info.responsibilities or [])[:4])
        return " ".join(part for part in parts if part).strip()

    def _resume_target_cities(self, resume: ResumeProfile) -> set[str]:
        cities: set[str] = set()
        if resume.basic_info.current_city:
            cities.update(self._split_city_tokens(resume.basic_info.current_city))
        if resume.raw_text:
            for label in ("期望城市", "意向城市"):
                match = re.search(rf"{label}[:：]\s*([^\n]+)", resume.raw_text)
                if match:
                    cities.update(self._split_city_tokens(match.group(1)))
        return cities

    def _job_location_tokens(self, job: JobProfile) -> set[str]:
        return self._split_city_tokens(job.basic_info.location)

    def _split_city_tokens(self, value: str | None) -> set[str]:
        if value is None:
            return set()
        values: list[str]
        if isinstance(value, (list, tuple, set)):
            values = [str(item) for item in value if str(item).strip()]
        else:
            values = [str(value)]
        tokens: set[str] = set()
        for item in values:
            text = item.strip()
            if not text:
                continue
            candidates = re.split(r"[,，/|、;；\s\[\]'\"()\-·]+", text)
            for candidate in candidates:
                normalized = candidate.strip()
                if not normalized:
                    continue
                if normalized.endswith("市") and len(normalized) > 1:
                    normalized = normalized[:-1]
                tokens.add(normalized)
        return tokens

    def _share_city_region(self, left: set[str], right: set[str]) -> bool:
        for group in CITY_REGION_GROUPS:
            if left & group and right & group:
                return True
        return False

    def _diversify_matches(self, matches: list[MatchResult], top_k: int) -> list[MatchResult]:
        selected: list[MatchResult] = []
        remaining = list(matches)
        seen_company_title: set[tuple[str, str]] = set()
        seen_companies: dict[str, int] = {}
        seen_titles: dict[str, int] = {}
        seen_templates: dict[str, int] = {}

        while remaining and len(selected) < top_k:
            best_index = 0
            best_score = float("-inf")
            for index, candidate in enumerate(remaining):
                score = candidate.breakdown.total
                company = candidate.job.company.strip().lower()
                title = candidate.job.title.strip().lower()
                template = self._job_template_signature(candidate.job)
                if (company, title) in seen_company_title:
                    score -= 0.05
                score -= seen_companies.get(company, 0) * 0.02
                score -= seen_titles.get(title, 0) * 0.015
                score -= seen_templates.get(template, 0) * 0.045
                score -= self._generic_job_penalty(candidate.job)
                if score > best_score:
                    best_score = score
                    best_index = index

            chosen = remaining.pop(best_index)
            selected.append(chosen)
            company = chosen.job.company.strip().lower()
            title = chosen.job.title.strip().lower()
            template = self._job_template_signature(chosen.job)
            seen_company_title.add((company, title))
            seen_companies[company] = seen_companies.get(company, 0) + 1
            seen_titles[title] = seen_titles.get(title, 0) + 1
            seen_templates[template] = seen_templates.get(template, 0) + 1

        return selected

    def _job_template_signature(self, job: JobProfile) -> str:
        summary = " ".join((job.basic_info.responsibilities or [])[:2]) or job.summary
        normalized_title = re.sub(r"\d+", "", job.title.strip().lower())
        normalized_summary = re.sub(r"\s+", " ", summary.strip().lower())
        normalized_summary = re.sub(r"\d+", "", normalized_summary)
        summary_head = normalized_summary[:120]
        return f"{job.company.strip().lower()}::{normalized_title}::{summary_head}"

    def _generic_job_penalty(self, job: JobProfile) -> float:
        searchable_text = f"{job.title} {job.summary}".lower()
        if any(pattern in searchable_text for pattern in GENERIC_ROLE_PATTERNS):
            return 0.03
        if "软件开发工程师" in searchable_text and any(
            token in searchable_text for token in ("前端", "后端", "测试")
        ):
            return 0.02
        return 0.0

    def _ensure_aux_text_vector(
        self,
        namespace: str,
        payload: str,
        cache: dict[str, list[float] | None],
    ) -> list[float] | None:
        normalized = " ".join(payload.split()).strip().lower()
        if not normalized:
            return None
        payload_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        cache_key = f"{namespace}:{payload_hash}"
        if cache_key in cache:
            return cache[cache_key]

        cached = self.vector_store.get(namespace, payload_hash)
        if cached is not None and cached.payload_hash == payload_hash:
            cache[cache_key] = cached.vector
            return cached.vector

        try:
            vector = self.embedding_client.embed_text(normalized)
        except Exception as exc:
            logger.warning("matching.aux_vector.failed namespace=%s error=%s", namespace, exc)
            cache[cache_key] = None
            return None

        self.vector_store.upsert(namespace, payload_hash, vector, payload_hash)
        cache[cache_key] = vector
        return vector

    def _required_skill_scores(
        self,
        job: JobProfile,
        candidate_skill_index: dict[str, dict[str, float | str | None]],
        skill_vector_cache: dict[str, list[float] | None],
    ) -> list[float]:
        return [
            self._score_required_skill(item, candidate_skill_index, skill_vector_cache)
            for item in job.skill_requirements.required
        ]

    def _score_required_skill(
        self,
        requirement: RequiredSkill,
        candidate_skill_index: dict[str, dict[str, float | str | None]],
        skill_vector_cache: dict[str, list[float] | None],
    ) -> float:
        candidate = candidate_skill_index.get(self._normalize_skill(requirement.name))
        base_score = 1.0
        if candidate is None:
            base_score, candidate = self._best_semantic_skill_match(
                requirement.name,
                candidate_skill_index,
                skill_vector_cache,
            )
            if candidate is None or base_score <= 0:
                return 0.0
        base_score = min(base_score, self._candidate_confidence(candidate))
        scores = [base_score]
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
        skill_vector_cache: dict[str, list[float] | None],
    ) -> list[float]:
        scores: list[float] = []
        for group in job.skill_requirements.optional_groups:
            scores.append(self._score_optional_group(group, candidate_skill_index, skill_vector_cache))
        return scores

    def _score_optional_group(
        self,
        group: OptionalSkillGroup,
        candidate_skill_index: dict[str, dict[str, float | str | None]],
        skill_vector_cache: dict[str, list[float] | None],
    ) -> float:
        skill_scores = sorted(
            [
                self._score_optional_skill(skill, candidate_skill_index, skill_vector_cache)
                for skill in group.skills or []
            ],
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
        skill_vector_cache: dict[str, list[float] | None],
    ) -> float:
        candidate = candidate_skill_index.get(self._normalize_skill(skill.name))
        base_score = 1.0
        if candidate is None:
            base_score, candidate = self._best_semantic_skill_match(
                skill.name,
                candidate_skill_index,
                skill_vector_cache,
            )
            if candidate is None or base_score <= 0:
                return 0.0
        base_score = min(base_score, self._candidate_confidence(candidate))
        if not skill.level:
            return base_score
        level_score = self._level_score(float(candidate.get("level_rank") or 0.0), skill.level)
        return (base_score + level_score) / 2

    def _bonus_skill_score(
        self,
        job: JobProfile,
        candidate_skill_index: dict[str, dict[str, float | str | None]],
        skill_vector_cache: dict[str, list[float] | None],
    ) -> float:
        weighted_components: list[tuple[float, float]] = []
        for skill in job.skill_requirements.bonus:
            weighted_components.append(
                (
                    self._score_bonus_skill(skill, candidate_skill_index, skill_vector_cache),
                    float(skill.weight or 1),
                )
            )
        return self._weighted_score(weighted_components, default=1.0)

    def _score_bonus_skill(
        self,
        skill: BonusSkill,
        candidate_skill_index: dict[str, dict[str, float | str | None]],
        skill_vector_cache: dict[str, list[float] | None],
    ) -> float:
        candidate = candidate_skill_index.get(self._normalize_skill(skill.name))
        if candidate is not None:
            return self._candidate_confidence(candidate)
        semantic_score, candidate = self._best_semantic_skill_match(skill.name, candidate_skill_index, skill_vector_cache)
        if candidate is None:
            return semantic_score
        return min(semantic_score, self._candidate_confidence(candidate))

    def _skill_match_exists(
        self,
        skill_name: str,
        candidate_skill_index: dict[str, dict[str, float | str | None]],
        skill_vector_cache: dict[str, list[float] | None],
    ) -> bool:
        if self._normalize_skill(skill_name) in candidate_skill_index:
            return True
        semantic_score, _ = self._best_semantic_skill_match(skill_name, candidate_skill_index, skill_vector_cache)
        return semantic_score > 0

    def _candidate_confidence(self, candidate: dict[str, float | str | None] | None) -> float:
        if candidate is None:
            return 1.0
        confidence = candidate.get("confidence")
        if isinstance(confidence, (int, float)):
            return max(0.0, min(float(confidence), 1.0))
        return 1.0

    def _best_semantic_skill_match(
        self,
        skill_name: str,
        candidate_skill_index: dict[str, dict[str, float | str | None]],
        skill_vector_cache: dict[str, list[float] | None],
    ) -> tuple[float, dict[str, float | str | None] | None]:
        requirement_vector = self._ensure_skill_vector(skill_name, skill_vector_cache)
        if requirement_vector is None:
            return 0.0, None

        best_similarity = 0.0
        best_candidate: dict[str, float | str | None] | None = None
        for candidate in candidate_skill_index.values():
            candidate_name = candidate.get("name")
            if not isinstance(candidate_name, str) or not candidate_name.strip():
                continue
            candidate_vector = self._ensure_skill_vector(candidate_name, skill_vector_cache)
            if candidate_vector is None:
                continue
            similarity = self._cosine_similarity(requirement_vector, candidate_vector)
            if similarity > best_similarity:
                best_similarity = similarity
                best_candidate = candidate

        if best_candidate is None or best_similarity < self.algorithm_config.semantic_skill_min_similarity:
            return 0.0, None
        return self._semantic_similarity_to_score(best_similarity), best_candidate

    def _ensure_skill_vector(
        self,
        skill_name: str,
        skill_vector_cache: dict[str, list[float] | None],
    ) -> list[float] | None:
        normalized = self._normalize_skill(skill_name)
        if not normalized:
            return None
        if normalized in skill_vector_cache:
            return skill_vector_cache[normalized]

        payload_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        cached = self.vector_store.get(SKILL_VECTOR_NAMESPACE, normalized)
        if cached is not None and cached.payload_hash == payload_hash:
            skill_vector_cache[normalized] = cached.vector
            return cached.vector

        try:
            vector = self.embedding_client.embed_text(normalized)
        except Exception as exc:
            logger.warning("matching.skill_vector.failed skill=%s error=%s", normalized, exc)
            skill_vector_cache[normalized] = None
            return None

        self.vector_store.upsert(SKILL_VECTOR_NAMESPACE, normalized, vector, payload_hash)
        skill_vector_cache[normalized] = vector
        return vector

    def _semantic_similarity_to_score(self, similarity: float) -> float:
        config = self.algorithm_config
        if similarity < config.semantic_skill_min_similarity:
            return 0.0
        scaled = config.semantic_skill_base_score + (
            similarity - config.semantic_skill_min_similarity
        ) * config.semantic_skill_score_scale
        return min(max(scaled, config.semantic_skill_base_score), config.semantic_skill_max_score)

    def _cosine_similarity(self, left: list[float], right: list[float]) -> float:
        dot_product = sum(a * b for a, b in zip(left, right))
        left_norm = sqrt(sum(a * a for a in left))
        right_norm = sqrt(sum(b * b for b in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return dot_product / (left_norm * right_norm)

    def _core_experience_scores(
        self,
        resume: ResumeProfile,
        job: JobProfile,
        candidate_skill_index: dict[str, dict[str, float | str | None]],
        candidate_terms: set[str],
        skill_vector_cache: dict[str, list[float] | None],
    ) -> list[float]:
        return [
            self._score_experience_item(item, resume, candidate_skill_index, candidate_terms, skill_vector_cache)
            for item in job.experience_requirements.core
        ]

    def _bonus_experience_score(
        self,
        resume: ResumeProfile,
        job: JobProfile,
        candidate_skill_index: dict[str, dict[str, float | str | None]],
        candidate_terms: set[str],
        skill_vector_cache: dict[str, list[float] | None],
    ) -> float:
        weighted_components: list[tuple[float, float]] = []
        for item in job.experience_requirements.bonus:
            weighted_components.append(
                (
                    self._score_bonus_experience(
                        item,
                        resume,
                        candidate_skill_index,
                        candidate_terms,
                        skill_vector_cache,
                    ),
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
        skill_vector_cache: dict[str, list[float] | None],
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
            skill_vector_cache,
        )

    def _score_experience_item(
        self,
        item: CoreExperience,
        resume: ResumeProfile,
        candidate_skill_index: dict[str, dict[str, float | str | None]],
        candidate_terms: set[str],
        skill_vector_cache: dict[str, list[float] | None],
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
            skill_vector_cache,
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
        skill_vector_cache: dict[str, list[float] | None],
    ) -> float:
        raw_text = resume.raw_text.lower()
        content_scores = [self._term_hit_score(name, candidate_terms, raw_text)]
        content_scores.extend(self._term_hit_score(keyword, candidate_terms, raw_text) for keyword in keywords)
        if description:
            content_scores.append(self._term_hit_score(description, candidate_terms, raw_text, exact=False))
        experience_skill_hints = infer_skills(
            {},
            " ".join(
                part
                for part in [name, description or "", *keywords]
                if part
            ),
        )
        if experience_skill_hints:
            skill_bridge_scores = [
                self._score_bonus_skill(
                    BonusSkill(name=skill_name),
                    candidate_skill_index,
                    skill_vector_cache,
                )
                for skill_name in experience_skill_hints[:8]
            ]
            bridge_multiplier = 1.0 if item_type.lower() == "tech" else 0.8
            content_scores.append(max(skill_bridge_scores, default=0.0) * bridge_multiplier)
        if item_type.lower() == "tech":
            tech_scores = [
                self._score_bonus_skill(
                    BonusSkill(name=name),
                    candidate_skill_index,
                    skill_vector_cache,
                )
            ]
            tech_scores.extend(
                self._score_bonus_skill(
                    BonusSkill(name=keyword),
                    candidate_skill_index,
                    skill_vector_cache,
                )
                for keyword in keywords
            )
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
            weighted_components.append(
                (self._minimum_degree_gate(resume, constraints), self.algorithm_config.education_min_degree_weight)
            )
        if constraints.prefer_degrees:
            weighted_components.append(
                (
                    self._preferred_degree_score(resume, constraints.prefer_degrees),
                    self.algorithm_config.education_prefer_degree_weight,
                )
            )
        if constraints.required_majors:
            weighted_components.append(
                (
                    self._major_score(resume, constraints.required_majors, strict=True),
                    self.algorithm_config.education_required_major_weight,
                )
            )
        if constraints.preferred_majors:
            weighted_components.append(
                (
                    self._major_score(resume, constraints.preferred_majors, strict=False),
                    self.algorithm_config.education_preferred_major_weight,
                )
            )
        return self._weighted_score(weighted_components, default=1.0)

    def _minimum_degree_gate(self, resume: ResumeProfile, constraints: JobEducationConstraints) -> float:
        if not constraints.min_degree:
            return 1.0
        candidate_rank = self._candidate_degree_rank(resume)
        target_rank = self._degree_rank(constraints.min_degree)
        if target_rank == 0:
            return 1.0
        if candidate_rank == 0:
            return 0.55 if target_rank <= DEGREE_RANK["bachelor"] else 0.35
        if candidate_rank < target_rank:
            return max(0.2, (candidate_rank / target_rank) * 0.6)
        if candidate_rank == target_rank:
            return 0.85
        return 0.88

    def _preferred_degree_score(self, resume: ResumeProfile, preferred_degrees: list[str]) -> float:
        candidate_rank = self._candidate_degree_rank(resume)
        if candidate_rank == 0:
            return 0.55
        target_ranks = [self._degree_rank(value) for value in preferred_degrees if self._degree_rank(value) > 0]
        if not target_ranks:
            return 1.0
        scores: list[float] = []
        for target_rank in target_ranks:
            if candidate_rank >= target_rank:
                scores.append(0.8 if candidate_rank == target_rank else 0.84)
                continue
            scores.append(max(0.3, (candidate_rank / target_rank) * 0.65))
        return max(scores, default=1.0)

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
            return 0.4 if strict else 0.55
        for target_major in target_majors:
            normalized = target_major.strip().lower()
            if not normalized:
                continue
            if normalized in candidate_majors:
                return 0.85
            if any(normalized in major or major in normalized for major in candidate_majors):
                return 0.72
        return 0.0 if strict else 0.45

    def _salary_score(self, resume: ResumeProfile, job: JobProfile) -> float:
        if not job.has_salary_reference:
            return 1.0
        if resume.expected_salary.min <= 0 or resume.expected_salary.max <= 0:
            return 1.0

        resume_min = resume.expected_salary.min
        resume_max = resume.expected_salary.max
        job_min = job.salary_range.min
        job_max = job.salary_range.max

        if job_max < resume_min:
            shortfall_ratio = max(job_max, 0) / max(resume_min, 1)
            return round(max(0.02, min(shortfall_ratio, 1.0) ** 2 * 0.18), 4)

        if job_min > resume_max:
            overshoot_ratio = job_min / max(resume_max, 1)
            if overshoot_ratio <= 1.5:
                return 0.92
            if overshoot_ratio <= 2.0:
                return 0.86
            return 0.8

        overlap_left = max(resume_min, job_min)
        overlap_right = min(resume_max, job_max)
        overlap = max(0, overlap_right - overlap_left)
        resume_span = max(resume_max - resume_min, 1)
        overlap_ratio = overlap / resume_span
        upside_bonus = 0.08 if job_max >= resume_max else 0.0
        return round(min(1.0, 0.72 + overlap_ratio * 0.20 + upside_bonus), 4)

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
