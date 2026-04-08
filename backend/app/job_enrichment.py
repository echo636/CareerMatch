from __future__ import annotations

from typing import Any
import re

from app.job_seed_loader import _extract_skills

PLACEHOLDER_TEXTS = {
    "company pending",
    "untitled role",
    "job description pending.",
    "skill pending",
    "experience pending",
    "optional skills",
    "language pending",
    "tag pending",
}

RESPONSIBILITY_MARKERS = ["岗位职责", "工作职责", "职责描述", "职位职责", "工作内容", "你将参与", "职责"]
HIGHLIGHT_SECTION_MARKERS = ["福利待遇", "加分项", "优选条件", "优先条件", "优选项", "加分"]
SECTION_END_MARKERS = [
    "岗位要求",
    "任职要求",
    "任职资格",
    "职位要求",
    "我们希望你",
    "岗位核心方向补充",
    "福利待遇",
    "加分项",
    "优选条件",
    "优先条件",
    "其他要求",
]
HIGHLIGHT_KEYWORDS = [
    "优先",
    "加分",
    "优选",
    "福利",
    "待遇",
    "可转正",
    "弹性",
    "双休",
    "六险一金",
    "期权",
    "奖金",
    "补贴",
    "餐补",
    "房补",
    "落户",
    "班车",
    "商业保险",
]
LANGUAGE_PATTERNS = {
    "英语": ["英语", "英文", "cet-4", "cet4", "cet-6", "cet6", "四级", "六级", "toeic", "toefl", "ielts"],
    "日语": ["日语", "jlpt", "n1", "n2"],
    "韩语": ["韩语"],
    "法语": ["法语"],
    "德语": ["德语"],
}
CERTIFICATION_PATTERNS = [
    "PMP",
    "CPA",
    "CFA",
    "软考",
    "信息系统项目管理师",
    "教师资格证",
    "证券从业",
    "基金从业",
    "一级建造师",
    "二级建造师",
    "注册会计师",
]
MAJOR_STOPWORDS = {
    "相关专业",
    "专业",
    "等",
    "以及",
    "及",
    "或",
    "优先",
    "者优先",
    "岗位要求",
    "任职要求",
    "任职资格",
    "职位要求",
    "我们希望你",
    "具备",
    "本科",
    "硕士",
    "博士",
    "学历",
    "海内外",
    "统招",
}
TOPIC_LEADING_VERBS = ("负责", "参与", "协助", "推进", "完成", "执行", "主导", "支持", "开展", "进行")
VALID_TAG_CATEGORIES = {"tech", "project", "domain", "industry", "education", "language", "general"}
TAG_CATEGORY_LIMITS = {
    "tech": 8,
    "project": 4,
    "domain": 4,
    "industry": 3,
    "education": 4,
    "language": 3,
    "general": 3,
}
TAG_CATEGORY_PRIORITY = {
    "tech": 0,
    "project": 1,
    "domain": 2,
    "industry": 3,
    "education": 4,
    "language": 5,
    "general": 6,
}
GENERIC_TAG_BLOCKLIST = {
    "engineer",
    "developer",
    "software",
    "job",
    "position",
    "experience",
    "responsibility",
    "responsibilities",
    "requirement",
    "requirements",
    "fulltime",
    "full-time",
    "intern",
    "internship",
    "campus",
    "remote",
    "onsite",
    "hybrid",
}


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.lower() in PLACEHOLDER_TEXTS:
        return None
    return text


def _dedupe(values: list[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = clean_text(value)
        if not text:
            continue
        marker = text.lower()
        if marker in seen:
            continue
        seen.add(marker)
        ordered.append(text)
    return ordered


def string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return _dedupe([str(item) for item in value])
    if isinstance(value, tuple):
        return _dedupe([str(item) for item in value])
    text = clean_text(value)
    return [text] if text else []


def first_present(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not clean_text(value):
            continue
        if isinstance(value, list) and not value:
            continue
        return value
    return None


def build_job_context_text(payload: dict[str, Any]) -> str:
    basic_info = payload.get("basic_info") or {}
    jd_text = _extract_job_description_text(payload.get("jd"))
    skill_requirements = payload.get("skill_requirements") or {}
    experience_requirements = payload.get("experience_requirements") or {}
    education_constraints = payload.get("education_constraints") or {}
    parts: list[str] = []

    primary_text = first_present(
        payload.get("summary"),
        basic_info.get("summary"),
        payload.get("raw_text"),
        payload.get("description"),
        jd_text,
    )
    parts.extend(
        value
        for value in [
            payload.get("title"),
            payload.get("job_name"),
            basic_info.get("title"),
            primary_text,
            payload.get("salary"),
            payload.get("department"),
            basic_info.get("department"),
            payload.get("city"),
            payload.get("work_address"),
            payload.get("location"),
            basic_info.get("location"),
            payload.get("education"),
            payload.get("experience"),
            payload.get("job_keys"),
            payload.get("company_industry"),
        ]
        if clean_text(value)
    )
    parts.extend(string_list(payload.get("responsibilities")))
    parts.extend(string_list(basic_info.get("responsibilities")))
    parts.extend(string_list(payload.get("highlights")))
    parts.extend(string_list(basic_info.get("highlights")))
    for item in (skill_requirements.get("required") or []) + (skill_requirements.get("bonus") or []):
        if not isinstance(item, dict):
            continue
        parts.extend(value for value in [item.get("name"), item.get("description")] if clean_text(value))
    for group in skill_requirements.get("optional_groups") or []:
        if not isinstance(group, dict):
            continue
        parts.extend(value for value in [group.get("group_name"), group.get("description")] if clean_text(value))
        for item in group.get("skills") or []:
            if not isinstance(item, dict):
                continue
            parts.extend(value for value in [item.get("name"), item.get("description")] if clean_text(value))
    for item in (experience_requirements.get("core") or []) + (experience_requirements.get("bonus") or []):
        if not isinstance(item, dict):
            continue
        parts.extend(value for value in [item.get("name"), item.get("description")] if clean_text(value))
        parts.extend(string_list(item.get("keywords")))
    parts.extend(string_list(education_constraints.get("required_majors")))
    parts.extend(string_list(education_constraints.get("preferred_majors")))
    parts.extend(string_list(education_constraints.get("certifications")))
    for item in education_constraints.get("languages") or []:
        if not isinstance(item, dict):
            continue
        parts.extend(value for value in [item.get("language"), item.get("level")] if clean_text(value))
    for tag in payload.get("tags") or []:
        if not isinstance(tag, dict):
            continue
        name = clean_text(tag.get("name"))
        if name:
            parts.append(name)
    for tag in string_list(payload.get("skill_tags")):
        parts.append(tag)
    return "\n".join(_dedupe(parts))


def infer_skills(payload: dict[str, Any], text: str) -> list[str]:
    candidates: list[str] = []
    candidates.extend(string_list(payload.get("skills")))
    candidates.extend(string_list(payload.get("skill_tags")))
    candidates.extend(_split_delimited_values(payload.get("job_keys")))

    skill_requirements = payload.get("skill_requirements") or {}
    for item in skill_requirements.get("required") or []:
        if isinstance(item, dict):
            name = clean_text(item.get("name"))
            if name:
                candidates.append(name)
    for item in skill_requirements.get("bonus") or []:
        if isinstance(item, dict):
            name = clean_text(item.get("name"))
            if name:
                candidates.append(name)
    for group in skill_requirements.get("optional_groups") or []:
        if not isinstance(group, dict):
            continue
        for skill in group.get("skills") or []:
            if isinstance(skill, dict):
                name = clean_text(skill.get("name"))
                if name:
                    candidates.append(name)

    for tag in payload.get("tags") or []:
        if not isinstance(tag, dict):
            continue
        if (clean_text(tag.get("category")) or "").lower() == "tech":
            name = clean_text(tag.get("name"))
            if name:
                candidates.append(name)

    candidates.extend(_extract_skills(text))
    return _dedupe(candidates)


def _extract_job_description_text(value: Any) -> str | None:
    if isinstance(value, dict):
        return "\n".join(
            item
            for item in [
                clean_text(value.get("requirements")),
                clean_text(value.get("infos")),
                clean_text(value.get("jobStrength")),
                clean_text(value.get("text")),
            ]
            if item
        ) or None

    text = clean_text(value)
    if not text:
        return None
    if not text.startswith("{"):
        return text

    try:
        import json

        payload = json.loads(text)
    except Exception:
        return text
    if not isinstance(payload, dict):
        return text
    return "\n".join(
        item
        for item in [
            clean_text(payload.get("requirements")),
            clean_text(payload.get("infos")),
            clean_text(payload.get("jobStrength")),
            clean_text(payload.get("text")),
        ]
        if item
    ) or text


def _split_delimited_values(value: Any) -> list[str]:
    text = clean_text(value)
    if not text:
        return []
    return _dedupe(re.split(r"[,，/|、;；]+", text))


def infer_topics(payload: dict[str, Any], title: str | None, text: str) -> list[str]:
    del title
    candidates: list[str] = []
    candidates.extend(string_list(payload.get("project_keywords")))

    experience = payload.get("experience_requirements") or {}
    for item in (experience.get("core") or []) + (experience.get("bonus") or []):
        if isinstance(item, dict):
            name = clean_text(item.get("name"))
            if name:
                candidates.append(name)
            candidates.extend(string_list(item.get("keywords")))

    for tag in payload.get("tags") or []:
        if not isinstance(tag, dict):
            continue
        category = (clean_text(tag.get("category")) or "").lower()
        if category in {"project", "domain", "industry"}:
            name = clean_text(tag.get("name"))
            if name:
                candidates.append(name)

    return _dedupe(candidates)


def infer_job_tags(
    payload: dict[str, Any],
    *,
    skills: list[str],
    topics: list[str],
    education_constraints: dict[str, Any] | None = None,
    highlights: list[str] | None = None,
) -> list[dict[str, Any]]:
    builder = _JobTagBuilder()
    constraints = education_constraints or {}

    for item in payload.get("tags") or []:
        if not isinstance(item, dict):
            continue
        name = clean_text(item.get("name"))
        if not name:
            continue
        category = _coerce_tag_category(name, item.get("category"))
        weight = item.get("weight")
        builder.add(name, category, int(weight) if isinstance(weight, (int, float)) else None)

    for index, skill in enumerate(_dedupe(skills)[: TAG_CATEGORY_LIMITS["tech"]]):
        builder.add(skill, "tech", 5 if index < 3 else 4)

    domain_candidates = [
        item
        for item in _split_delimited_values(payload.get("job_keys"))
        if not _looks_like_skill_tag(item)
    ]
    for item in domain_candidates[: TAG_CATEGORY_LIMITS["domain"]]:
        builder.add(item, "domain", 3)

    for index, topic in enumerate(_dedupe(topics)[: TAG_CATEGORY_LIMITS["project"]]):
        builder.add(topic, "project", 4 if index < 2 else 3)

    for item in _split_delimited_values(payload.get("company_industry"))[: TAG_CATEGORY_LIMITS["industry"]]:
        builder.add(item, "industry", 3)

    for item in string_list(constraints.get("required_majors"))[:3]:
        builder.add(item, "education", 3)
    for item in string_list(constraints.get("preferred_majors"))[:2]:
        builder.add(item, "education", 2)
    for item in string_list(constraints.get("certifications"))[:2]:
        builder.add(item, "education", 2)

    for item in constraints.get("languages") or []:
        if not isinstance(item, dict):
            continue
        name = clean_text(item.get("language"))
        if not name:
            continue
        builder.add(name, "language", 3 if item.get("required") is not False else 2)

    for item in (highlights or [])[: TAG_CATEGORY_LIMITS["general"]]:
        if _looks_like_general_tag(item):
            builder.add(item, "general", 2)

    return builder.finalize()


def infer_responsibilities(payload: dict[str, Any], text: str) -> list[str]:
    basic_info = payload.get("basic_info") or {}
    existing = string_list(payload.get("responsibilities")) or string_list(basic_info.get("responsibilities"))
    if existing:
        return existing
    return _extract_section_items(text, RESPONSIBILITY_MARKERS, SECTION_END_MARKERS, max_items=8)


def infer_highlights(payload: dict[str, Any], text: str) -> list[str]:
    basic_info = payload.get("basic_info") or {}
    existing = string_list(payload.get("highlights")) or string_list(basic_info.get("highlights"))
    if existing:
        return existing

    highlights: list[str] = []
    for marker in HIGHLIGHT_SECTION_MARKERS:
        for item in _extract_section_items(text, [marker], SECTION_END_MARKERS, max_items=4):
            normalized = _normalize_highlight_candidate(item)
            if normalized:
                highlights.append(normalized)
    if highlights:
        return _dedupe(highlights)[:6]

    for sentence in _split_items(text):
        normalized = _normalize_highlight_candidate(sentence)
        if normalized and _looks_like_highlight(normalized):
            highlights.append(normalized)
    return _dedupe(highlights)[:6]


def infer_years_range(text: str) -> tuple[float | None, float | None]:
    range_match = re.search(
        r"(?P<min>\d+(?:\.\d+)?)\s*[-~～至到]\s*(?P<max>\d+(?:\.\d+)?)\s*(?:年|years?)",
        text,
        re.IGNORECASE,
    )
    if range_match:
        return float(range_match.group("min")), float(range_match.group("max"))

    min_match = re.search(
        r"(?P<min>\d+(?:\.\d+)?)\s*(?:年|years?)\s*(?:以上|及以上|或以上|起|\+)",
        text,
        re.IGNORECASE,
    )
    if min_match:
        return float(min_match.group("min")), None

    exact_match = re.search(
        r"(?:至少|不少于)?\s*(?P<min>\d+(?:\.\d+)?)\s*(?:年|years?)经验",
        text,
        re.IGNORECASE,
    )
    if exact_match:
        return float(exact_match.group("min")), None

    return None, None


def infer_salary(text: str) -> dict[str, Any]:
    lower = text.lower()
    result: dict[str, Any] = {
        "salary_negotiable": True if "面议" in text else None,
        "salary_min": None,
        "salary_max": None,
        "salary_months_min": None,
        "salary_months_max": None,
        "intern_salary_amount": None,
        "intern_salary_unit": None,
        "currency": "CNY",
    }

    months_range = re.search(r"(?P<min>\d{1,2})\s*[-~～至到]\s*(?P<max>\d{1,2})\s*薪", text)
    if months_range:
        result["salary_months_min"] = int(months_range.group("min"))
        result["salary_months_max"] = int(months_range.group("max"))
    else:
        months_single = re.search(r"(?P<months>\d{1,2})\s*薪", text)
        if months_single:
            months = int(months_single.group("months"))
            result["salary_months_min"] = months
            result["salary_months_max"] = months

    daily_match = re.search(
        r"(?P<min>\d+(?:\.\d+)?)\s*[-~～至到]\s*(?P<max>\d+(?:\.\d+)?)\s*元\s*/\s*天",
        text,
    )
    if daily_match:
        result["intern_salary_amount"] = int(round(float(daily_match.group("max"))))
        result["intern_salary_unit"] = "元/天"
        return result

    monthly_k = re.search(r"(?P<min>\d+(?:\.\d+)?)\s*[-~～至到]\s*(?P<max>\d+(?:\.\d+)?)\s*[kK千]", text)
    if monthly_k:
        result["salary_min"] = int(round(float(monthly_k.group("min")) * 1000))
        result["salary_max"] = int(round(float(monthly_k.group("max")) * 1000))
        result["salary_negotiable"] = False
        return result

    monthly_plain = re.search(
        r"(?P<min>\d{4,6})\s*[-~～至到]\s*(?P<max>\d{4,6})\s*(?:元/月|元|/月)?",
        text,
    )
    if monthly_plain:
        result["salary_min"] = int(monthly_plain.group("min"))
        result["salary_max"] = int(monthly_plain.group("max"))
        result["salary_negotiable"] = False
        return result

    yearly_wan = re.search(
        r"(?P<min>\d+(?:\.\d+)?)\s*[-~～至到]\s*(?P<max>\d+(?:\.\d+)?)\s*[万wW]\s*/\s*年",
        lower,
    )
    if yearly_wan:
        result["salary_min"] = int(round(float(yearly_wan.group("min")) * 10000 / 12))
        result["salary_max"] = int(round(float(yearly_wan.group("max")) * 10000 / 12))
        result["salary_negotiable"] = False
    return result


def infer_education(text: str) -> dict[str, Any]:
    min_degree = _infer_min_degree(text)
    prefer_degrees = _infer_prefer_degrees(text)
    required_majors = _infer_majors(text, preferred=False)
    preferred_majors = _infer_majors(text, preferred=True)
    languages = _infer_languages(text)
    certifications = _infer_certifications(text)
    age_range = _infer_age_range(text)
    other = _infer_other_constraints(text)
    return {
        "min_degree": min_degree,
        "prefer_degrees": prefer_degrees,
        "required_majors": required_majors,
        "preferred_majors": preferred_majors,
        "languages": languages,
        "certifications": certifications,
        "age_range": age_range,
        "other": other,
    }


class _JobTagBuilder:
    def __init__(self) -> None:
        self._items: dict[str, dict[str, Any]] = {}

    def add(self, name: str, category: str, weight: int | None = None) -> None:
        cleaned = clean_text(name)
        if not cleaned:
            return
        if category not in VALID_TAG_CATEGORIES:
            return
        if not _is_meaningful_tag_name(cleaned):
            return
        item = {
            "name": cleaned,
            "category": category,
            "weight": int(weight or _default_tag_weight(category)),
        }
        key = _tag_key(cleaned, category)
        current = self._items.get(key)
        if current is None or _prefer_tag(item, current):
            self._items[key] = item

    def finalize(self) -> list[dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = {category: [] for category in VALID_TAG_CATEGORIES}
        for item in self._items.values():
            grouped[item["category"]].append(item)

        results: list[dict[str, Any]] = []
        for category in sorted(TAG_CATEGORY_PRIORITY, key=lambda item: TAG_CATEGORY_PRIORITY[item]):
            items = sorted(
                grouped.get(category, []),
                key=lambda item: (-int(item["weight"]), item["name"].lower()),
            )
            results.extend(items[: TAG_CATEGORY_LIMITS.get(category, len(items))])
        return results


def _extract_section_items(text: str, start_markers: list[str], end_markers: list[str], max_items: int) -> list[str]:
    for marker in start_markers:
        section = _extract_section_text(text, marker, end_markers)
        if not section:
            continue
        items = _split_items(section)
        if items:
            return items[:max_items]
    return []


def _extract_section_text(text: str, start_marker: str, end_markers: list[str]) -> str | None:
    start = text.find(start_marker)
    if start == -1:
        return None

    section = text[start + len(start_marker) :]
    section = re.sub(r"^[：:\-\s]+", "", section, count=1)
    end_positions = [position for marker in end_markers if (position := section.find(marker)) != -1]
    if end_positions:
        section = section[: min(end_positions)]
    return clean_text(section)


def _default_tag_weight(category: str) -> int:
    if category == "tech":
        return 4
    if category == "project":
        return 4
    if category in {"domain", "industry", "education", "language"}:
        return 3
    return 2


def _coerce_tag_category(name: str, category: Any) -> str:
    category_text = (clean_text(category) or "").lower()
    if category_text in VALID_TAG_CATEGORIES:
        if category_text != "general" or not _looks_like_skill_tag(name):
            return category_text
    if _looks_like_skill_tag(name):
        return "tech"
    return "general"


def _tag_key(name: str, category: str) -> str:
    if category == "tech":
        return f"tech:{name.strip().lower()}"
    return clean_text(name).lower()


def _prefer_tag(candidate: dict[str, Any], current: dict[str, Any]) -> bool:
    candidate_priority = TAG_CATEGORY_PRIORITY[candidate["category"]]
    current_priority = TAG_CATEGORY_PRIORITY[current["category"]]
    if candidate_priority != current_priority:
        return candidate_priority < current_priority
    return int(candidate["weight"]) > int(current["weight"])


def _is_meaningful_tag_name(value: str) -> bool:
    text = clean_text(value)
    if not text:
        return False
    lowered = text.lower()
    if lowered in GENERIC_TAG_BLOCKLIST:
        return False
    if len(text) < 2 or len(text) > 32:
        return False
    if len(text.split()) > 6:
        return False
    return True


def _looks_like_skill_tag(value: str) -> bool:
    normalized = clean_text(value)
    if not normalized:
        return False
    if _extract_skills(normalized):
        return True
    lowered = normalized.lower()
    return lowered in {"mini program", "wechat mini program", "uniapp", "flutter", "webgl"}


def _normalize_topic_candidate(value: str) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    normalized = text
    for verb in TOPIC_LEADING_VERBS:
        if normalized.startswith(verb):
            normalized = normalized[len(verb) :].strip("，,、；;。 ")
            break
    normalized = re.sub(r"(等工作|等相关工作|相关工作)$", "", normalized).strip("，,、；;。 ")
    if not normalized or len(normalized) < 4 or len(normalized) > 24:
        return None
    return normalized


def _normalize_highlight_candidate(value: str) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    normalized = re.sub(r"^(?:\u9879|\u52a0\u5206\u9879|\u798f\u5229\u5f85\u9047|\u4f18\u9009\u6761\u4ef6|\u4f18\u5148\u6761\u4ef6)[?:\s-]*", "", text).strip()
    normalized = re.sub(r"^(?:\d+|[??????????]+)[)?.??:?]\s*", "", normalized)
    normalized = normalized.lstrip("?: ").strip("?,??; ")
    normalized = re.sub(r"^[^A-Za-z0-9\u4e00-\u9fa5]+", "", normalized)
    if not normalized:
        return None
    if re.fullmatch(r"[A-Za-z\u4e00-\u9fa5]+(?:/[A-Za-z\u4e00-\u9fa5]+)+", normalized):
        return None
    return normalized


def _looks_like_general_tag(value: str) -> bool:
    text = clean_text(value)
    if not text:
        return False
    if not _is_meaningful_tag_name(text):
        return False
    if _looks_like_skill_tag(text):
        return False
    if len(text) > 24:
        return False
    return True


def _looks_like_highlight(sentence: str) -> bool:
    if any(marker in sentence for marker in RESPONSIBILITY_MARKERS):
        return False
    if any(keyword in sentence for keyword in ["\u672c\u79d1", "\u7855\u58eb", "\u535a\u58eb", "\u7814\u7a76\u751f", "\u5b66\u5386", "\u4e13\u4e1a"]):
        return False
    return any(keyword in sentence for keyword in HIGHLIGHT_KEYWORDS)


def _split_items(text: str) -> list[str]:
    normalized = text.replace("\r", "\n")
    normalized = re.sub(r"[•●▪■◆◇]", "\n", normalized)
    normalized = re.sub(r"\s+(?:[-–—]|\|)\s+", "\n", normalized)
    normalized = re.sub(r"(?:^|\n)\s*(?:\d+|[一二三四五六七八九十]+)[、.．:：)]\s*", "\n", normalized)
    normalized = normalized.replace("；", "\n").replace(";", "\n")
    normalized = re.sub(r"(?<=[。！？])\s*", "\n", normalized)

    items: list[str] = []
    for line in normalized.splitlines():
        cleaned = re.sub(r"^[\-\d、.．:：()（）\s]+", "", line).strip()
        cleaned = re.sub(
            r"^(?:岗位职责|工作职责|职责描述|职位职责|工作内容|岗位要求|任职要求|任职资格|职位要求|福利待遇|加分项|优选条件|优先条件|优选项|其他要求)[：:\s-]*",
            "",
            cleaned,
        )
        cleaned = cleaned.strip("，,。；; ")
        if len(cleaned) < 6:
            continue
        if any(marker in cleaned for marker in RESPONSIBILITY_MARKERS + SECTION_END_MARKERS):
            continue
        items.append(cleaned)
    return _dedupe(items)


def _infer_min_degree(text: str) -> str | None:
    patterns = [
        ("doctor", [r"博士及以上", r"博士研究生", r"phd", r"doctor"]),
        ("master", [r"硕士及以上", r"硕士研究生", r"研究生及以上", r"master"]),
        ("bachelor", [r"本科及以上", r"本科或以上", r"本科学历", r"学士", r"bachelor", r"统招本科"]),
        ("associate", [r"大专及以上", r"专科及以上", r"associate", r"college"]),
        ("high_school", [r"高中及以上", r"high school"]),
    ]
    for degree, regexes in patterns:
        if any(re.search(regex, text, re.IGNORECASE) for regex in regexes):
            return degree
    return None


def _infer_prefer_degrees(text: str) -> list[str]:
    preferences: list[str] = []
    patterns = [
        ("doctor", [r"博士(?:学历)?优先", r"phd.+优先", r"doctor.+优先"]),
        ("master", [r"硕士(?:学历)?优先", r"研究生优先", r"master.+优先"]),
        ("bachelor", [r"本科(?:学历)?优先", r"学士优先", r"bachelor.+优先"]),
    ]
    for degree, regexes in patterns:
        if any(re.search(regex, text, re.IGNORECASE) for regex in regexes):
            preferences.append(degree)
    return _dedupe(preferences)


def _infer_majors(text: str, preferred: bool) -> list[str]:
    regexes = [
        r"(?P<majors>[\u4e00-\u9fa5A-Za-z/、，,\s]{2,80}?)(?:等)?相关专业(?:优先|者优先)?",
        r"(?P<majors>[\u4e00-\u9fa5A-Za-z/、，,\s]{2,80}?)(?:等)?专业(?:优先|者优先)",
    ]
    results: list[str] = []
    for regex in regexes:
        for match in re.finditer(regex, text, re.IGNORECASE):
            majors_text = clean_text(match.group("majors"))
            if not majors_text:
                continue
            is_preferred = "优先" in match.group(0)
            if is_preferred != preferred:
                continue
            majors_text = re.sub(r".*学历", "", majors_text)
            majors_text = re.sub(r"\d{4}届|海内外|统招|学历|及以上|或研究生|或以上|以上", "", majors_text)
            for major in re.split(r"[、,/，]\s*|\s+", majors_text):
                token = _normalize_major_token(major)
                if token:
                    results.append(token)
    return _dedupe(results)


def _normalize_major_token(value: str) -> str | None:
    token = clean_text(value)
    if not token:
        return None
    token = re.sub(r"(相关专业|相关)$", "", token)
    token = re.sub(r"(专业|类)$", "", token)
    token = token.strip()
    if not token or token in MAJOR_STOPWORDS or len(token) < 2:
        return None
    return token


def _infer_languages(text: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for language, patterns in LANGUAGE_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if not match:
                continue
            window_start = max(0, match.start() - 24)
            window_end = min(len(text), match.end() + 24)
            context = text[window_start:window_end]
            level = None
            if any(token in context.lower() for token in ["流利", "熟练", "可作为工作语言", "business"]):
                level = "fluent"
            elif any(token in context.lower() for token in ["cet-6", "cet6", "六级", "n1"]):
                level = "advanced"
            elif any(token in context.lower() for token in ["cet-4", "cet4", "四级", "n2"]):
                level = "intermediate"
            required = "优先" not in context and "加分" not in context
            results.append({"language": language, "level": level, "required": required})
            break
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in results:
        key = item["language"].lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _infer_certifications(text: str) -> list[str]:
    found: list[str] = []
    lower = text.lower()
    for name in CERTIFICATION_PATTERNS:
        if name.lower() in lower:
            found.append(name)
    return _dedupe(found)


def _infer_age_range(text: str) -> str | None:
    range_match = re.search(r"(?P<min>\d{2})\s*[-~～至到]\s*(?P<max>\d{2})\s*岁", text)
    if range_match:
        return f"{range_match.group('min')}-{range_match.group('max')}岁"
    upper_match = re.search(r"(?P<max>\d{2})\s*岁(?:以下|以内)", text)
    if upper_match:
        return f"{upper_match.group('max')}岁以下"
    lower_match = re.search(r"(?P<min>\d{2})\s*岁(?:以上|及以上)", text)
    if lower_match:
        return f"{lower_match.group('min')}岁以上"
    return None


def _infer_other_constraints(text: str) -> list[str]:
    results: list[str] = []
    for sentence in _split_items(text):
        if any(
            keyword in sentence
            for keyword in ["每周", "到岗", "连续", "出差", "轮班", "驻场", "现场", "实习4", "实习5", "实习6", "个月以上"]
        ):
            results.append(sentence)
    return _dedupe(results)[:6]
