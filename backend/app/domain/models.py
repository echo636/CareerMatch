from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from datetime import datetime, timezone
import re
from typing import Any

PLACEHOLDER_TEXT_MARKERS = {
    "company pending",
    "role pending",
    "project pending",
    "school pending",
    "skill pending",
    "tag pending",
    "language pending",
    "resume summary pending.",
    "job description pending.",
    "untitled role",
    "optional skills",
    "experience pending",
}
SUMMARY_NOISE_LABELS = (
    "联系方式",
    "社交主页",
    "联系电话",
    "手机号",
    "电话",
    "邮箱",
    "微信",
    "wechat",
    "qq",
    "mail",
    "email",
)
CONTACT_URL_PATTERN = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
CONTACT_EMAIL_PATTERN = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b", re.IGNORECASE)
CONTACT_PHONE_PATTERN = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
CONTACT_HANDLE_PATTERN = re.compile(r"\b[a-zA-Z]\d{8,}\b")
WHITESPACE_PATTERN = re.compile(r"\s+")


@dataclass(slots=True)
class SalaryRange:
    min: int
    max: int
    currency: str = "CNY"


def _deduplicate(values: list[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = normalize_profile_token(value)
        if not normalized:
            continue
        marker = normalized.lower()
        if marker in seen:
            continue
        seen.add(marker)
        ordered.append(normalized)
    return ordered


def is_placeholder_text(value: Any) -> bool:
    if value is None:
        return True
    text = str(value).strip()
    if not text:
        return True
    marker = WHITESPACE_PATTERN.sub(" ", text).strip().lower()
    if marker in PLACEHOLDER_TEXT_MARKERS:
        return True
    return marker.endswith(" pending") or marker.endswith(" pending.")


def normalize_profile_token(value: Any) -> str | None:
    if is_placeholder_text(value):
        return None
    text = str(value).strip()
    if not text:
        return None
    if CONTACT_URL_PATTERN.fullmatch(text) or CONTACT_EMAIL_PATTERN.fullmatch(text) or CONTACT_PHONE_PATTERN.fullmatch(text):
        return None
    return text


def clean_resume_summary_text(value: Any) -> str | None:
    if is_placeholder_text(value):
        return None
    text = str(value).strip()
    if not text:
        return None
    text = CONTACT_URL_PATTERN.sub(" ", text)
    text = CONTACT_EMAIL_PATTERN.sub(" ", text)
    text = CONTACT_PHONE_PATTERN.sub(" ", text)
    text = CONTACT_HANDLE_PATTERN.sub(" ", text)
    for label in SUMMARY_NOISE_LABELS:
        text = re.sub(rf"(?i){re.escape(label)}[:：]?", " ", text)
    text = WHITESPACE_PATTERN.sub(" ", text).strip(" ,;，；|")
    return text or None


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
    slug: str | None = None
    filterable: bool = False
    facet_key: str | None = None
    facet_value: str | None = None


@dataclass(slots=True)
class ResumeFilterFacets:
    role_categories: list[str] = field(default_factory=list)
    target_cities: list[str] = field(default_factory=list)
    preferred_work_modes: list[str] = field(default_factory=list)
    ai_capabilities: list[str] = field(default_factory=list)
    seniority_level: str | None = None
    inferred_salary_min: int | None = None
    inferred_salary_max: int | None = None


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
    filter_facets: ResumeFilterFacets = field(default_factory=ResumeFilterFacets)
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
        cleaned_summary = clean_resume_summary_text(self.basic_info.summary)
        cleaned_self_evaluation = clean_resume_summary_text(self.basic_info.self_evaluation)
        cleaned_raw_text = clean_resume_summary_text(self.raw_text)
        return (
            cleaned_summary
            or cleaned_self_evaluation
            or (cleaned_raw_text[:500] if cleaned_raw_text else None)
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
            if project.name:
                values.append(project.name)
            if project.domain:
                values.append(project.domain)
            if project.role:
                values.append(project.role)
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
        inferred_from_text = _infer_resume_work_years_from_text(
            self.basic_info.summary,
            self.basic_info.self_evaluation,
            self.raw_text,
        )
        if inferred_from_text is not None:
            return inferred_from_text
        inferred_from_span = _infer_resume_years_from_work_experiences(self.work_experiences)
        if inferred_from_span is not None:
            return inferred_from_span
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
    slug: str | None = None
    filterable: bool = False
    facet_key: str | None = None
    facet_value: str | None = None


@dataclass(slots=True)
class JobFilterFacets:
    role_categories: list[str]
    work_modes: list[str]
    city_tokens: list[str] = field(default_factory=list)
    ai_capabilities: list[str] = field(default_factory=list)
    is_internship: bool | None = None
    seniority_level: str | None = None
    salary_band: str | None = None
    posted_at: str | None = None
    posted_days_ago: int | None = None
    min_experience_years: float | None = None
    max_experience_years: float | None = None


@dataclass(slots=True)
class MatchFilters:
    role_categories: list[str]
    work_modes: list[str]
    internship_preference: str = "all"
    posted_within_days: int | None = None
    min_experience_years: float | None = None
    max_experience_years: float | None = None

    @property
    def is_active(self) -> bool:
        return any(
            [
                bool(self.role_categories),
                bool(self.work_modes),
                self.internship_preference in {"intern", "fulltime"},
                self.posted_within_days is not None,
                self.min_experience_years is not None,
                self.max_experience_years is not None,
            ]
        )


@dataclass(slots=True)
class JobProfile:
    id: str
    company: str
    basic_info: JobBasicInfo
    skill_requirements: JobSkillRequirements
    experience_requirements: JobExperienceRequirements
    education_constraints: JobEducationConstraints
    tags: list[JobTag]
    filter_facets: JobFilterFacets

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


ROLE_CATEGORY_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("hardware_engineer", ("hardware", "硬件", "electrical", "电子", "射频", "rf", "pcb", "电气")),
    ("embedded_engineer", ("embedded", "嵌入式", "firmware", "bsp", "rtos", "单片机", "驱动")),
    ("frontend_engineer", ("frontend", "front-end", "前端", "web前端", "h5开发")),
    ("backend_engineer", ("backend", "back-end", "后端", "server", "服务端")),
    ("fullstack_engineer", ("full stack", "fullstack", "全栈")),
    ("testing_engineer", ("test", "testing", "qa", "质量", "测试", "验证")),
    ("algorithm_engineer", ("algorithm", "ml", "machine learning", "ai", "llm", "算法", "机器学习", "深度学习")),
    ("data_engineer", ("data", "big data", "database", "etl", "大数据", "数据工程", "数仓")),
    ("devops_engineer", ("devops", "sre", "infra", "platform", "运维", "基础设施")),
    ("mobile_engineer", ("android", "ios", "mobile", "flutter", "react native", "移动开发")),
    ("product_manager", ("product manager", "pm", "产品经理")),
    ("uiux_designer", ("ux", "ui", "designer", "design", "交互设计", "视觉设计", "设计师")),
)

REMOTE_KEYWORDS = ("remote", "work from home", "wfh", "home office", "远程", "居家办公")
HYBRID_KEYWORDS = ("hybrid", "混合办公", "弹性办公")
ONSITE_KEYWORDS = ("onsite", "on-site", "in office", "线下", "坐班", "驻场", "现场")
AI_CAPABILITY_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("llm", ("llm", "\u5927\u6a21\u578b", "foundation model")),
    ("rag", ("rag", "retrieval augmented generation")),
    ("agent", ("agent", "\u667a\u80fd\u4f53", "ai agent")),
    ("prompt", ("prompt", "prompt engineering", "prompt design")),
    ("ai_infra", ("ai infra", "model serving", "inference platform", "mcp")),
)


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _deduplicate_lower(values: list[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = value.strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def _normalize_tag_slug(value: Any) -> str | None:
    token = normalize_profile_token(value)
    if not token:
        return None
    normalized = re.sub(r"[^a-z0-9]+", "_", str(token).strip().lower())
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized or None


def _split_profile_city_tokens(*values: Any) -> list[str]:
    tokens: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value is None:
            continue
        raw_values: list[str]
        if isinstance(value, (list, tuple, set)):
            raw_values = [str(item) for item in value]
        else:
            raw_values = [str(value)]
        for item in raw_values:
            for raw_token in re.split(r"[,，/|、;\s]+", item):
                token = raw_token.strip().strip("[]()")
                if not token:
                    continue
                if token.endswith("\u5e02") and len(token) > 1:
                    token = token[:-1]
                marker = token.lower()
                if marker in seen:
                    continue
                seen.add(marker)
                tokens.append(token)
    return tokens


def _extract_facet_values_from_tags(tags: list[Any], facet_key: str) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for tag in tags or []:
        if not getattr(tag, "filterable", False):
            continue
        if (getattr(tag, "facet_key", None) or "").strip() != facet_key:
            continue
        value = normalize_profile_token(getattr(tag, "facet_value", None) or getattr(tag, "slug", None) or getattr(tag, "name", None))
        if not value:
            continue
        marker = value.lower()
        if marker in seen:
            continue
        seen.add(marker)
        values.append(value)
    return values


def _infer_ai_capabilities(*values: str | None) -> list[str]:
    searchable_text = " ".join(part.lower() for part in values if part)
    matched: list[str] = []
    for capability, keywords in AI_CAPABILITY_KEYWORDS:
        if any(keyword in searchable_text for keyword in keywords):
            matched.append(capability)
    return _deduplicate_lower(matched)


def _merge_resume_tags(base_tags: list[ResumeTag], derived_tags: list[ResumeTag]) -> list[ResumeTag]:
    merged: list[ResumeTag] = []
    seen: set[tuple[str, str, str, str]] = set()
    for tag in [*base_tags, *derived_tags]:
        key = (
            (tag.category or "").strip().lower(),
            (tag.facet_key or "").strip().lower(),
            (tag.facet_value or "").strip().lower(),
            ((tag.slug or tag.name) or "").strip().lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        merged.append(tag)
    return merged


def _merge_job_tags(base_tags: list[JobTag], derived_tags: list[JobTag]) -> list[JobTag]:
    merged: list[JobTag] = []
    seen: set[tuple[str, str, str, str]] = set()
    for tag in [*base_tags, *derived_tags]:
        key = (
            (tag.category or "").strip().lower(),
            (tag.facet_key or "").strip().lower(),
            (tag.facet_value or "").strip().lower(),
            ((tag.slug or tag.name) or "").strip().lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        merged.append(tag)
    return merged


def _parse_datetime_value(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None

    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        parsed = None

    if parsed is None:
        for fmt in (
            "%Y-%m-%d %H:%M:%S%z",
            "%Y-%m-%d %H:%M:%S",
            "%Y/%m/%d %H:%M:%S",
            "%Y-%m-%d",
            "%Y/%m/%d",
        ):
            try:
                parsed = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue

    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _infer_resume_work_years_from_text(*values: str | None) -> int | None:
    for value in values:
        if not value:
            continue
        match = re.search(r"(\d{1,2})\s*年(?:工作)?经验", value)
        if match:
            return int(match.group(1))
    return None


def _normalize_resume_date_value(value: str | None) -> tuple[int, int] | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    if text == "至今":
        now = datetime.now(timezone.utc)
        return now.year, now.month
    match = re.match(r"(?P<year>\d{4})[./-](?P<month>\d{1,2})", text)
    if match is None:
        return None
    return int(match.group("year")), int(match.group("month"))


def _infer_resume_years_from_work_experiences(work_experiences: list[ResumeWorkExperience]) -> int | None:
    spans: list[tuple[tuple[int, int], tuple[int, int]]] = []
    for experience in work_experiences:
        start = _normalize_resume_date_value(experience.start_date)
        end = _normalize_resume_date_value(experience.end_date)
        if start is None:
            continue
        spans.append((start, end or start))
    if not spans:
        return None
    earliest_start = min(spans, key=lambda item: item[0])[0]
    latest_end = max(spans, key=lambda item: item[1])[1]
    months = max(
        0,
        (latest_end[0] - earliest_start[0]) * 12 + (latest_end[1] - earliest_start[1]),
    )
    years = max(1, round(months / 12))
    return years


RESUME_TARGET_CITY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?:\u671f\u671b\u57ce\u5e02|\u610f\u5411\u57ce\u5e02|target city|preferred city)[:\uff1a]\s*([^\n]+)", re.IGNORECASE),
    re.compile(r"(?:\u5de5\u4f5c\u5730\u70b9|\u610f\u5411\u5730\u70b9)[:\uff1a]\s*([^\n]+)", re.IGNORECASE),
)
RESUME_REMOTE_KEYWORDS = (
    "remote",
    "wfh",
    "work from home",
    "\u8fdc\u7a0b",
    "\u5c45\u5bb6\u529e\u516c",
)
RESUME_HYBRID_KEYWORDS = (
    "hybrid",
    "\u6df7\u5408\u529e\u516c",
    "\u5f39\u6027\u529e\u516c",
)
RESUME_MAJOR_CITY_TOKENS = {
    "\u5317\u4eac",
    "\u4e0a\u6d77",
    "\u6df1\u5733",
    "\u5e7f\u5dde",
    "\u676d\u5dde",
}
RESUME_LEAD_KEYWORDS = (
    "architect",
    "tech lead",
    "team lead",
    "leader",
    "\u6280\u672f\u8d1f\u8d23\u4eba",
    "\u8d1f\u8d23\u4eba",
    "\u67b6\u6784\u5e08",
    "\u67b6\u6784",
)
RESUME_AI_KEYWORDS = (
    "llm",
    "rag",
    "agent",
    "ai infra",
    "prompt",
    "\u5927\u6a21\u578b",
    "\u667a\u80fd\u4f53",
    "mcp",
)


def _infer_resume_target_cities(current_city: str | None, raw_text: str) -> list[str]:
    values: list[str] = []
    if current_city:
        values.append(current_city)
    for pattern in RESUME_TARGET_CITY_PATTERNS:
        match = pattern.search(raw_text or "")
        if match:
            values.append(match.group(1))
    return _split_profile_city_tokens(*values)


def _infer_resume_preferred_work_modes(raw_text: str) -> list[str]:
    searchable_text = (raw_text or "").lower()
    matched: list[str] = []
    if any(keyword in searchable_text for keyword in RESUME_REMOTE_KEYWORDS):
        matched.append("remote")
    if any(keyword in searchable_text for keyword in RESUME_HYBRID_KEYWORDS):
        matched.append("hybrid")
    return _deduplicate_lower(matched)


def _infer_resume_seniority_level(title: str | None, summary: str | None, years_experience: int) -> str:
    searchable_text = " ".join(part.lower() for part in [title or "", summary or ""] if part)
    if any(keyword in searchable_text for keyword in RESUME_LEAD_KEYWORDS) or years_experience >= 8:
        return "lead"
    if years_experience >= 5:
        return "senior"
    if years_experience >= 3:
        return "mid"
    return "junior"


def _round_salary_bucket(value: int) -> int:
    return int(round(value / 1000.0) * 1000)


def _infer_resume_salary_range(
    *,
    years_experience: int,
    seniority_level: str,
    role_categories: list[str],
    current_city: str | None,
    raw_text: str,
) -> tuple[int | None, int | None]:
    if years_experience <= 0:
        return None, None

    if years_experience >= 9:
        min_salary, max_salary = 30000, 42000
    elif years_experience >= 7:
        min_salary, max_salary = 26000, 36000
    elif years_experience >= 5:
        min_salary, max_salary = 22000, 30000
    elif years_experience >= 3:
        min_salary, max_salary = 16000, 22000
    else:
        min_salary, max_salary = 10000, 15000

    if seniority_level == "lead":
        min_salary += 5000
        max_salary += 8000
    elif seniority_level == "senior":
        min_salary += 2000
        max_salary += 4000

    role_set = set(role_categories)
    if role_set & {"backend_engineer", "fullstack_engineer", "algorithm_engineer", "data_engineer"}:
        min_salary += 2000
        max_salary += 3000

    searchable_text = (raw_text or "").lower()
    if any(keyword in searchable_text for keyword in RESUME_AI_KEYWORDS):
        min_salary += 3000
        max_salary += 5000

    if current_city and any(city in current_city for city in RESUME_MAJOR_CITY_TOKENS):
        min_salary += 2000
        max_salary += 3000

    return _round_salary_bucket(min_salary), _round_salary_bucket(max_salary)


def build_resume_standard_tags(resume: ResumeProfile) -> list[ResumeTag]:
    role_categories = _infer_role_categories(
        resume.basic_info.current_title or "",
        resume.summary,
        [JobTag(name=tag.name, category=tag.category) for tag in resume.tags if not getattr(tag, "filterable", False)],
    )
    target_cities = _infer_resume_target_cities(resume.basic_info.current_city, resume.raw_text)
    preferred_work_modes = _infer_resume_preferred_work_modes(resume.raw_text)
    seniority_level = _infer_resume_seniority_level(
        resume.basic_info.current_title,
        resume.summary,
        resume.years_experience,
    )
    inferred_salary_min, inferred_salary_max = _infer_resume_salary_range(
        years_experience=resume.years_experience,
        seniority_level=seniority_level,
        role_categories=role_categories,
        current_city=resume.basic_info.current_city,
        raw_text=resume.raw_text,
    )
    ai_capabilities = _infer_ai_capabilities(
        resume.basic_info.current_title,
        resume.summary,
        " ".join(resume.skill_names),
        " ".join(resume.project_keywords),
        resume.raw_text,
    )

    derived_tags: list[ResumeTag] = []
    for role in role_categories:
        derived_tags.append(
            ResumeTag(
                name=role,
                category="role",
                slug=role,
                filterable=True,
                facet_key="role_categories",
                facet_value=role,
            )
        )
    for city in target_cities:
        derived_tags.append(
            ResumeTag(
                name=city,
                category="city",
                slug=_normalize_tag_slug(city),
                filterable=True,
                facet_key="target_cities",
                facet_value=city,
            )
        )
    for mode in preferred_work_modes:
        derived_tags.append(
            ResumeTag(
                name=mode,
                category="work_mode",
                slug=mode,
                filterable=True,
                facet_key="preferred_work_modes",
                facet_value=mode,
            )
        )
    for capability in ai_capabilities:
        derived_tags.append(
            ResumeTag(
                name=capability,
                category="ai_capability",
                slug=capability,
                filterable=True,
                facet_key="ai_capabilities",
                facet_value=capability,
            )
        )
    if seniority_level:
        derived_tags.append(
            ResumeTag(
                name=seniority_level,
                category="seniority",
                slug=seniority_level,
                filterable=True,
                facet_key="seniority_level",
                facet_value=seniority_level,
            )
        )
    if inferred_salary_min and inferred_salary_max:
        derived_tags.append(
            ResumeTag(
                name=f"salary:{inferred_salary_min}-{inferred_salary_max}",
                category="salary_band",
                slug=f"{inferred_salary_min}_{inferred_salary_max}",
                filterable=True,
                facet_key="inferred_salary_range",
                facet_value=f"{inferred_salary_min}:{inferred_salary_max}",
            )
        )
    return derived_tags


def build_resume_filter_facets(resume: ResumeProfile) -> ResumeFilterFacets:
    role_categories = _extract_facet_values_from_tags(resume.tags, "role_categories") or _infer_role_categories(
        resume.basic_info.current_title or "",
        resume.summary,
        [JobTag(name=tag.name, category=tag.category) for tag in resume.tags if not getattr(tag, "filterable", False)],
    )
    target_cities = _extract_facet_values_from_tags(resume.tags, "target_cities") or _infer_resume_target_cities(
        resume.basic_info.current_city,
        resume.raw_text,
    )
    preferred_work_modes = _extract_facet_values_from_tags(resume.tags, "preferred_work_modes") or _infer_resume_preferred_work_modes(
        resume.raw_text
    )
    ai_capabilities = _extract_facet_values_from_tags(resume.tags, "ai_capabilities") or _infer_ai_capabilities(
        resume.basic_info.current_title,
        resume.summary,
        " ".join(resume.skill_names),
        " ".join(resume.project_keywords),
        resume.raw_text,
    )
    seniority_candidates = _extract_facet_values_from_tags(resume.tags, "seniority_level")
    seniority_level = seniority_candidates[0] if seniority_candidates else _infer_resume_seniority_level(
        resume.basic_info.current_title,
        resume.summary,
        resume.years_experience,
    )
    salary_range_candidates = _extract_facet_values_from_tags(resume.tags, "inferred_salary_range")
    if salary_range_candidates and ":" in salary_range_candidates[0]:
        left, right = salary_range_candidates[0].split(":", 1)
        inferred_salary_min = int(left)
        inferred_salary_max = int(right)
    else:
        inferred_salary_min, inferred_salary_max = _infer_resume_salary_range(
            years_experience=resume.years_experience,
            seniority_level=seniority_level,
            role_categories=role_categories,
            current_city=resume.basic_info.current_city,
            raw_text=resume.raw_text,
        )
    return ResumeFilterFacets(
        role_categories=role_categories,
        target_cities=target_cities,
        preferred_work_modes=preferred_work_modes,
        ai_capabilities=ai_capabilities,
        seniority_level=seniority_level,
        inferred_salary_min=inferred_salary_min,
        inferred_salary_max=inferred_salary_max,
    )


def _normalize_posted_at(raw_values: list[Any] | None) -> tuple[str | None, int | None]:
    if not raw_values:
        return None, None
    for raw_value in raw_values:
        parsed = _parse_datetime_value(raw_value)
        if parsed is None:
            continue
        posted_at = parsed.isoformat()
        posted_days_ago = max(0, (datetime.now(timezone.utc).date() - parsed.date()).days)
        return posted_at, posted_days_ago
    return None, None


def _infer_role_categories(title: str, summary: str | None, tags: list[JobTag] | None) -> list[str]:
    searchable_parts = [title, summary or ""]
    searchable_parts.extend(tag.name for tag in tags or [])
    searchable_text = " ".join(part.lower() for part in searchable_parts if part)
    matched = [
        category
        for category, keywords in ROLE_CATEGORY_KEYWORDS
        if any(keyword in searchable_text for keyword in keywords)
    ]
    return _deduplicate_lower(matched)


def _infer_work_modes(title: str, location: str | None, summary: str | None) -> list[str]:
    searchable_text = " ".join(part.lower() for part in [title, location or "", summary or ""] if part)
    matched: list[str] = []
    if any(keyword in searchable_text for keyword in REMOTE_KEYWORDS):
        matched.append("remote")
    if any(keyword in searchable_text for keyword in HYBRID_KEYWORDS):
        matched.append("hybrid")
    if any(keyword in searchable_text for keyword in ONSITE_KEYWORDS):
        matched.append("onsite")
    if not matched and location:
        matched.append("onsite")
    return _deduplicate_lower(matched)


def _infer_is_internship(title: str, job_type: str | None, summary: str | None) -> bool | None:
    searchable_text = " ".join(part.lower() for part in [title, job_type or "", summary or ""] if part)
    if any(keyword in searchable_text for keyword in ("intern", "实习")):
        return True
    if searchable_text:
        return False
    return None


def _infer_job_city_tokens(location: str | None) -> list[str]:
    return _split_profile_city_tokens(location)


def _infer_job_seniority_level(
    title: str,
    summary: str | None,
    job_type: str | None,
    min_total_years: float | None,
    max_total_years: float | None,
) -> str | None:
    searchable_text = " ".join(part.lower() for part in [title, summary or "", job_type or ""] if part)
    if any(keyword in searchable_text for keyword in ("intern", "campus", "graduate", "\u5b9e\u4e60", "\u6821\u62db", "\u5e94\u5c4a")):
        return "entry"
    if any(keyword in searchable_text for keyword in ("senior", "lead", "architect", "principal", "staff")):
        return "senior"
    min_years = _coerce_float(min_total_years)
    max_years = _coerce_float(max_total_years)
    if min_years is not None and min_years >= 5:
        return "senior"
    if max_years is not None and max_years <= 2:
        return "entry"
    if min_years is not None and min_years >= 3:
        return "mid"
    return None


def _infer_job_salary_band(
    salary_min: int | None,
    salary_max: int | None,
    intern_salary_amount: int | None,
) -> str | None:
    ceiling = salary_max or salary_min or intern_salary_amount
    if ceiling is None or ceiling <= 0:
        return None
    if ceiling < 12000:
        return "entry"
    if ceiling < 20000:
        return "mid"
    if ceiling < 30000:
        return "senior"
    return "lead"


def build_job_standard_tags(
    *,
    title: str,
    location: str | None,
    job_type: str | None,
    summary: str | None,
    tags: list[JobTag] | None,
    min_total_years: float | None,
    max_total_years: float | None,
    salary_min: int | None,
    salary_max: int | None,
    intern_salary_amount: int | None,
) -> list[JobTag]:
    role_categories = _infer_role_categories(title, summary, tags)
    work_modes = _infer_work_modes(title, location, summary)
    city_tokens = _infer_job_city_tokens(location)
    ai_capabilities = _infer_ai_capabilities(
        title,
        summary,
        " ".join(tag.name for tag in tags or [] if not getattr(tag, "filterable", False)),
    )
    seniority_level = _infer_job_seniority_level(title, summary, job_type, min_total_years, max_total_years)
    salary_band = _infer_job_salary_band(salary_min, salary_max, intern_salary_amount)
    is_internship = _infer_is_internship(title, job_type, summary)

    derived_tags: list[JobTag] = []
    for role in role_categories:
        derived_tags.append(JobTag(name=role, category="role", slug=role, filterable=True, facet_key="role_categories", facet_value=role))
    for mode in work_modes:
        derived_tags.append(JobTag(name=mode, category="work_mode", slug=mode, filterable=True, facet_key="work_modes", facet_value=mode))
    for city in city_tokens:
        derived_tags.append(
            JobTag(
                name=city,
                category="city",
                slug=_normalize_tag_slug(city),
                filterable=True,
                facet_key="city_tokens",
                facet_value=city,
            )
        )
    for capability in ai_capabilities:
        derived_tags.append(
            JobTag(
                name=capability,
                category="ai_capability",
                slug=capability,
                filterable=True,
                facet_key="ai_capabilities",
                facet_value=capability,
            )
        )
    if seniority_level:
        derived_tags.append(
            JobTag(
                name=seniority_level,
                category="seniority",
                slug=seniority_level,
                filterable=True,
                facet_key="seniority_level",
                facet_value=seniority_level,
            )
        )
    if salary_band:
        derived_tags.append(
            JobTag(
                name=salary_band,
                category="salary_band",
                slug=salary_band,
                filterable=True,
                facet_key="salary_band",
                facet_value=salary_band,
            )
        )
    if is_internship is not None:
        derived_tags.append(
            JobTag(
                name="internship" if is_internship else "fulltime",
                category="job_type",
                slug="internship" if is_internship else "fulltime",
                filterable=True,
                facet_key="is_internship",
                facet_value="true" if is_internship else "false",
            )
        )
    return derived_tags


def build_job_filter_facets(
    *,
    title: str,
    location: str | None,
    job_type: str | None,
    summary: str | None,
    min_total_years: float | None,
    max_total_years: float | None,
    tags: list[JobTag] | None = None,
    raw_posted_at_values: list[Any] | None = None,
) -> JobFilterFacets:
    posted_at, posted_days_ago = _normalize_posted_at(raw_posted_at_values)
    role_categories = _extract_facet_values_from_tags(tags or [], "role_categories") or _infer_role_categories(title, summary, tags)
    work_modes = _extract_facet_values_from_tags(tags or [], "work_modes") or _infer_work_modes(title, location, summary)
    city_tokens = _extract_facet_values_from_tags(tags or [], "city_tokens") or _infer_job_city_tokens(location)
    ai_capabilities = _extract_facet_values_from_tags(tags or [], "ai_capabilities") or _infer_ai_capabilities(
        title,
        summary,
        " ".join(tag.name for tag in tags or [] if not getattr(tag, "filterable", False)),
    )
    seniority_values = _extract_facet_values_from_tags(tags or [], "seniority_level")
    salary_band_values = _extract_facet_values_from_tags(tags or [], "salary_band")
    internship_values = _extract_facet_values_from_tags(tags or [], "is_internship")
    return JobFilterFacets(
        role_categories=role_categories,
        work_modes=work_modes,
        city_tokens=city_tokens,
        ai_capabilities=ai_capabilities,
        is_internship=(
            internship_values[0].lower() == "true"
            if internship_values
            else _infer_is_internship(title, job_type, summary)
        ),
        seniority_level=(
            seniority_values[0]
            if seniority_values
            else _infer_job_seniority_level(title, summary, job_type, min_total_years, max_total_years)
        ),
        salary_band=salary_band_values[0] if salary_band_values else None,
        posted_at=posted_at,
        posted_days_ago=posted_days_ago,
        min_experience_years=_coerce_float(min_total_years),
        max_experience_years=_coerce_float(max_total_years),
    )


@dataclass(slots=True)
class MatchBreakdown:
    vector_similarity: float
    skill_match: float
    experience_match: float
    education_match: float
    salary_match: float
    domain_match: float
    location_match: float
    role_level_fit: float
    title_skill_alignment: float
    transition_score: float
    base_total: float
    penalty_multiplier: float
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
