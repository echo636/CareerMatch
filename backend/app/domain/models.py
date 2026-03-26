from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from typing import Any


@dataclass(slots=True)
class SalaryRange:
    min: int
    max: int
    currency: str = "CNY"


def _deduplicate(values: list[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = value.strip()
        if not normalized:
            continue
        marker = normalized.lower()
        if marker in seen:
            continue
        seen.add(marker)
        ordered.append(normalized)
    return ordered


@dataclass(slots=True)
class ResumeBasicInfo:
    name: str
    gender: str | None = None
    age: int | None = None
    work_years: int | None = None
    current_city: str | None = None
    current_title: str | None = None
    current_company: str | None = None
    status: str | None = None
    email: str | None = None
    phone: str | None = None
    wechat: str | None = None
    ethnicity: str | None = None
    birth_date: str | None = None
    native_place: str | None = None
    residence: str | None = None
    political_status: str | None = None
    id_number: str | None = None
    marital_status: str | None = None
    summary: str | None = None
    self_evaluation: str | None = None
    first_degree: str | None = None
    avatar: str | None = None


@dataclass(slots=True)
class ResumeEducation:
    school: str
    degree: str | None = None
    major: str | None = None
    start_year: str | None = None
    end_year: str | None = None


@dataclass(slots=True)
class ResumeWorkExperience:
    company_name: str
    industry: str | None = None
    title: str = ""
    level: str | None = None
    location: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    responsibilities: list[str] | None = None
    achievements: list[str] | None = None
    tech_stack: list[str] | None = None


@dataclass(slots=True)
class ResumeProject:
    name: str
    role: str | None = None
    domain: str | None = None
    description: str | None = None
    responsibilities: list[str] | None = None
    achievements: list[str] | None = None
    tech_stack: list[str] | None = None


@dataclass(slots=True)
class ResumeSkill:
    name: str
    level: str | None = None
    years: int | None = None
    last_used_year: int | None = None


@dataclass(slots=True)
class ResumeTag:
    name: str
    category: str | None = None


@dataclass(slots=True)
class ResumeProfile:
    id: str
    basic_info: ResumeBasicInfo
    educations: list[ResumeEducation]
    work_experiences: list[ResumeWorkExperience]
    projects: list[ResumeProject]
    skills: list[ResumeSkill]
    tags: list[ResumeTag]
    expected_salary: SalaryRange
    is_resume: bool | None = None
    raw_text: str = ""
    source_file_name: str = ""
    source_content_type: str = ""
    source_object_key: str = ""

    @property
    def candidate_name(self) -> str:
        return self.basic_info.name

    @property
    def summary(self) -> str:
        return (
            self.basic_info.summary
            or self.basic_info.self_evaluation
            or self.raw_text.strip()[:500]
            or "Resume summary pending."
        )

    @property
    def skill_names(self) -> list[str]:
        values = [skill.name for skill in self.skills]
        for experience in self.work_experiences:
            values.extend(experience.tech_stack or [])
        for project in self.projects:
            values.extend(project.tech_stack or [])
        values.extend(tag.name for tag in self.tags if (tag.category or "").lower() == "tech")
        return _deduplicate(values)

    @property
    def project_keywords(self) -> list[str]:
        values: list[str] = []
        for project in self.projects:
            values.append(project.name)
            if project.domain:
                values.append(project.domain)
        values.extend(
            tag.name
            for tag in self.tags
            if (tag.category or "").lower() in {"project", "domain", "industry"}
        )
        return _deduplicate(values)

    @property
    def years_experience(self) -> int:
        if self.basic_info.work_years is not None:
            return self.basic_info.work_years
        skill_years = [skill.years for skill in self.skills if skill.years is not None]
        return max(skill_years, default=0)


@dataclass(slots=True)
class JobBasicInfo:
    title: str
    department: str | None = None
    location: str | None = None
    job_type: str | None = None
    salary_negotiable: bool | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_months_min: int | None = None
    salary_months_max: int | None = None
    intern_salary_amount: int | None = None
    intern_salary_unit: str | None = None
    currency: str | None = None
    summary: str | None = None
    responsibilities: list[str] | None = None
    highlights: list[str] | None = None


@dataclass(slots=True)
class RequiredSkill:
    name: str
    level: str | None = None
    min_years: float | None = None
    description: str | None = None


@dataclass(slots=True)
class OptionalSkill:
    name: str
    level: str | None = None
    description: str | None = None


@dataclass(slots=True)
class OptionalSkillGroup:
    group_name: str
    description: str | None = None
    min_required: int = 1
    skills: list[OptionalSkill] | None = None


@dataclass(slots=True)
class BonusSkill:
    name: str
    weight: int | None = None
    description: str | None = None


@dataclass(slots=True)
class JobSkillRequirements:
    required: list[RequiredSkill]
    optional_groups: list[OptionalSkillGroup]
    bonus: list[BonusSkill]


@dataclass(slots=True)
class CoreExperience:
    type: str
    name: str
    min_years: float | None = None
    description: str | None = None
    keywords: list[str] | None = None


@dataclass(slots=True)
class BonusExperience:
    type: str
    name: str
    weight: int | None = None
    description: str | None = None
    keywords: list[str] | None = None


@dataclass(slots=True)
class JobExperienceRequirements:
    core: list[CoreExperience]
    bonus: list[BonusExperience]
    min_total_years: float | None = None
    max_total_years: float | None = None


@dataclass(slots=True)
class LanguageRequirement:
    language: str
    level: str | None = None
    required: bool = False


@dataclass(slots=True)
class JobEducationConstraints:
    min_degree: str | None = None
    prefer_degrees: list[str] | None = None
    required_majors: list[str] | None = None
    preferred_majors: list[str] | None = None
    languages: list[LanguageRequirement] | None = None
    certifications: list[str] | None = None
    age_range: str | None = None
    other: list[str] | None = None


@dataclass(slots=True)
class JobTag:
    name: str
    category: str | None = None
    weight: int | None = None


@dataclass(slots=True)
class JobProfile:
    id: str
    company: str
    basic_info: JobBasicInfo
    skill_requirements: JobSkillRequirements
    experience_requirements: JobExperienceRequirements
    education_constraints: JobEducationConstraints
    tags: list[JobTag]

    @property
    def title(self) -> str:
        return self.basic_info.title

    @property
    def location(self) -> str:
        return self.basic_info.location or "remote"

    @property
    def summary(self) -> str:
        return (
            self.basic_info.summary
            or "; ".join((self.basic_info.responsibilities or [])[:2])
            or "Job description pending."
        )

    @property
    def skills(self) -> list[str]:
        values = [skill.name for skill in self.skill_requirements.required]
        for group in self.skill_requirements.optional_groups:
            values.extend(skill.name for skill in (group.skills or []))
        values.extend(skill.name for skill in self.skill_requirements.bonus)
        values.extend(tag.name for tag in self.tags if (tag.category or "").lower() == "tech")
        return _deduplicate(values)

    @property
    def hard_requirements(self) -> list[str]:
        return _deduplicate([skill.name for skill in self.skill_requirements.required])

    @property
    def project_keywords(self) -> list[str]:
        values: list[str] = []
        for experience in self.experience_requirements.core:
            values.append(experience.name)
            values.extend(experience.keywords or [])
        for experience in self.experience_requirements.bonus:
            values.append(experience.name)
            values.extend(experience.keywords or [])
        values.extend(
            tag.name
            for tag in self.tags
            if (tag.category or "").lower() in {"project", "domain", "industry"}
        )
        return _deduplicate(values)

    @property
    def salary_range(self) -> SalaryRange:
        salary_min = self.basic_info.salary_min
        salary_max = self.basic_info.salary_max
        if salary_min is None and self.basic_info.intern_salary_amount is not None:
            salary_min = self.basic_info.intern_salary_amount
        if salary_max is None and self.basic_info.intern_salary_amount is not None:
            salary_max = self.basic_info.intern_salary_amount
        if salary_min is None and salary_max is not None:
            salary_min = salary_max
        if salary_max is None and salary_min is not None:
            salary_max = salary_min
        return SalaryRange(
            min=salary_min or 0,
            max=salary_max or 0,
            currency=self.basic_info.currency or "CNY",
        )

    @property
    def has_salary_reference(self) -> bool:
        return self.basic_info.salary_negotiable is not True and self.salary_range.max > 0

    @property
    def experience_years(self) -> int:
        baseline = (
            self.experience_requirements.min_total_years
            or self.experience_requirements.max_total_years
            or 0
        )
        return int(round(baseline))


@dataclass(slots=True)
class MatchBreakdown:
    vector_similarity: float
    skill_match: float
    experience_match: float
    education_match: float
    salary_match: float
    total: float


@dataclass(slots=True)
class MatchResult:
    job: JobProfile
    breakdown: MatchBreakdown
    matched_skills: list[str]
    missing_skills: list[str]
    reasoning: str
    tier: str = "match"


@dataclass(slots=True)
class GapInsight:
    dimension: str
    current_state: str
    target_state: str
    suggestion: str


@dataclass(slots=True)
class GapReport:
    baseline_roles: list[str]
    missing_skills: list[str]
    salary_gap: int
    experience_gap_years: int
    insights: list[GapInsight]


def _to_camel_case(value: str) -> str:
    parts = value.split("_")
    return parts[0] + "".join(part.capitalize() for part in parts[1:])


def serialize(value: Any) -> Any:
    if is_dataclass(value):
        return {
            _to_camel_case(field.name): serialize(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, dict):
        return {_to_camel_case(str(key)): serialize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [serialize(item) for item in value]
    return value
