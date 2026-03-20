from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from typing import Any


@dataclass(slots=True)
class SalaryRange:
    min: int
    max: int
    currency: str = "CNY"


@dataclass(slots=True)
class ResumeProfile:
    id: str
    candidate_name: str
    summary: str
    skills: list[str]
    project_keywords: list[str]
    years_experience: int
    expected_salary: SalaryRange
    raw_text: str = ""
    source_file_name: str = ""
    source_content_type: str = ""
    source_object_key: str = ""


@dataclass(slots=True)
class JobProfile:
    id: str
    title: str
    company: str
    location: str
    summary: str
    skills: list[str]
    project_keywords: list[str]
    hard_requirements: list[str]
    salary_range: SalaryRange
    experience_years: int = 0


@dataclass(slots=True)
class MatchBreakdown:
    vector_similarity: float
    skill_match: float
    project_match: float
    salary_match: float
    total: float


@dataclass(slots=True)
class MatchResult:
    job: JobProfile
    breakdown: MatchBreakdown
    matched_skills: list[str]
    missing_skills: list[str]
    reasoning: str


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