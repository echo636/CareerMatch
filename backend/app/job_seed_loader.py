from __future__ import annotations

from pathlib import Path
import json
import re
from typing import Any

COPY_HEADER_PATTERN = re.compile(
    r"^COPY\s+talent_pool\.jobs\s+\((?P<columns>.+)\)\s+FROM\s+stdin;$"
)
TIMESTAMP_SUFFIX_PATTERN = re.compile(
    r"^(?P<prefix>.*?)(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.\d+)?[+-]\d{2})$"
)
JOB_TYPE_VALUES = {
    "fulltime",
    "parttime",
    "intern",
    "contract",
    "temporary",
    "全职",
    "兼职",
    "实习",
}

SKILL_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("Python", (r"\bpython\b",)),
    ("Java", (r"\bjava\b(?!script)",)),
    ("Golang", (r"\bgolang\b",)),
    ("C++", (r"\bc\+\+\b",)),
    ("C#", (r"\bc#\b", r"\bcsharp\b")),
    ("JavaScript", (r"\bjavascript\b",)),
    ("TypeScript", (r"\btypescript\b",)),
    ("Node.js", (r"\bnode\.?js\b",)),
    ("React", (r"\breact\b",)),
    ("Vue", (r"\bvue(?:\.js)?\b",)),
    ("Angular", (r"\bangular\b",)),
    ("HTML5", (r"\bhtml5\b",)),
    ("CSS3", (r"\bcss3\b",)),
    ("Flask", (r"\bflask\b",)),
    ("FastAPI", (r"\bfastapi\b",)),
    ("Django", (r"\bdjango\b",)),
    ("Spring", (r"\bspring\b",)),
    ("Spring Boot", (r"\bspring\s*boot\b",)),
    ("MySQL", (r"\bmysql\b",)),
    ("PostgreSQL", (r"\bpostgres(?:ql)?\b",)),
    ("Redis", (r"\bredis\b",)),
    ("MongoDB", (r"\bmongodb\b",)),
    ("Oracle", (r"\boracle\b",)),
    ("SQL", (r"\bsql\b",)),
    ("Kafka", (r"\bkafka\b",)),
    ("RabbitMQ", (r"\brabbitmq\b",)),
    ("Elasticsearch", (r"\belasticsearch\b",)),
    ("Docker", (r"\bdocker\b",)),
    ("Kubernetes", (r"\bkubernetes\b", r"\bk8s\b")),
    ("Linux", (r"\blinux\b",)),
    ("Git", (r"\bgit\b",)),
    ("Jenkins", (r"\bjenkins\b",)),
    ("AWS", (r"\baws\b",)),
    ("Azure", (r"\bazure\b",)),
    ("GCP", (r"\bgcp\b", r"\bgoogle cloud\b")),
    ("TensorFlow", (r"\btensorflow\b",)),
    ("PyTorch", (r"\bpytorch\b",)),
    ("LLM", (r"\bllm\b", r"大模型")),
    ("Embedding", (r"\bembedding\b",)),
    ("RAG", (r"\brag\b",)),
    ("Prompt Design", (r"\bprompt\b", r"提示词")),
    ("Qdrant", (r"\bqdrant\b",)),
    ("pgvector", (r"\bpgvector\b",)),
    ("ETL", (r"\betl\b",)),
    ("Selenium", (r"\bselenium\b",)),
    ("Appium", (r"\bappium\b",)),
    ("Playwright", (r"\bplaywright\b",)),
    ("Cypress", (r"\bcypress\b",)),
    ("JMeter", (r"\bjmeter\b",)),
    ("LoadRunner", (r"\bloadrunner\b",)),
    ("自动化测试", (r"自动化测试",)),
    ("接口测试", (r"接口测试",)),
    ("功能测试", (r"功能测试",)),
    ("性能测试", (r"性能测试",)),
    ("白盒测试", (r"白盒测试",)),
    ("黑盒测试", (r"黑盒测试",)),
    ("测试开发", (r"测试开发",)),
    ("数据分析", (r"数据分析",)),
]
TITLE_SPLIT_MARKERS = [
    "岗位职责",
    "岗位要求",
    "职位描述",
    "职位详情页",
    "Job description",
    "Job description and responsibilities",
    "Position:",
]
DESCRIPTION_HINTS = [
    "岗位职责",
    "岗位要求",
    "职位描述",
    "1、",
    "2、",
    "负责",
    "参与",
    "熟悉",
]


def load_job_seed_records(path: str | Path, limit: int | None = None) -> list[dict[str, Any]]:
    source_path = Path(path)
    if not source_path.exists():
        raise FileNotFoundError(f"Job seed file does not exist: {source_path}")

    normalized_limit = limit if limit and limit > 0 else None
    suffix = source_path.suffix.lower()
    if suffix == ".json":
        return _load_json_records(source_path, normalized_limit)
    if suffix == ".sql":
        return list(_iter_pageflux_sql_records(source_path, normalized_limit))
    raise ValueError(f"Unsupported job seed format '{suffix}'. Expected .json or .sql")


def _load_json_records(path: Path, limit: int | None) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        records = payload.get("jobs")
    else:
        records = payload
    if not isinstance(records, list):
        raise ValueError(f"JSON job seed must be a list or an object with 'jobs': {path}")
    normalized_records = [
        _normalize_json_job_record(item) if isinstance(item, dict) else item
        for item in records
    ]
    if limit is None:
        return normalized_records
    return normalized_records[:limit]


def _normalize_json_job_record(record: dict[str, Any]) -> dict[str, Any]:
    if _looks_like_standard_job_record(record):
        return record
    if _looks_like_zhaopin_job_record(record):
        return _map_zhaopin_json_record(record)
    if _looks_like_niuke_job_record(record):
        return _map_niuke_job_record(record)
    return record


def _looks_like_standard_job_record(record: dict[str, Any]) -> bool:
    return any(
        key in record
        for key in ("title", "description", "summary", "skill_requirements", "education_constraints")
    )


def _looks_like_niuke_job_record(record: dict[str, Any]) -> bool:
    return "job_name" in record and "jd" in record and "job_keys" in record


def _looks_like_zhaopin_job_record(record: dict[str, Any]) -> bool:
    return "job_name" in record and "jd" in record and any(
        key in record for key in ("skill_tags", "education", "experience", "work_address")
    )


def _map_niuke_job_record(record: dict[str, Any]) -> dict[str, Any]:
    title = _clean_text(record.get("job_name")) or _clean_text(record.get("career_job")) or "Untitled Role"
    jd_payload = _parse_embedded_jd(record.get("jd"))
    requirements = _clean_text(jd_payload.get("requirements"))
    infos = _clean_text(jd_payload.get("infos"))
    job_strength = _clean_text(jd_payload.get("jobStrength"))
    salary_text = _clean_text(record.get("salary"))
    location = _clean_text(record.get("city"))
    company = _clean_text(record.get("company")) or "Company Pending"
    topic_tags = _split_delimited_text(record.get("job_keys"))
    context_text = _build_text_blob(
        [
            title,
            salary_text,
            location,
            requirements,
            infos,
            job_strength,
            record.get("job_keys"),
        ]
    )
    skills = _extract_skills(context_text)
    salary_fields = _parse_salary_text(salary_text)
    min_years, max_years = _parse_experience_text(context_text)
    min_degree = _extract_min_degree_from_text(context_text)

    return {
        "id": _extract_job_id(record) or _clean_text(record.get("_detail_url")),
        "job_name": record.get("job_name"),
        "title": title,
        "company": company,
        "location": location,
        "salary": salary_text,
        "salary_currency": salary_fields["currency"],
        "salary_negotiable": salary_fields["salary_negotiable"],
        "salary_min": salary_fields["salary_min"],
        "salary_max": salary_fields["salary_max"],
        "salary_months_min": salary_fields["salary_months_min"],
        "salary_months_max": salary_fields["salary_months_max"],
        "summary": infos or requirements or title,
        "description": _build_text_blob([requirements, infos, job_strength]),
        "raw_text": context_text,
        "responsibilities": _string_list([infos] if infos else []),
        "highlights": _string_list([job_strength] if job_strength else []),
        "skills": skills,
        "skill_requirements": {
            "required": [{"name": skill} for skill in skills[:3]],
            "optional_groups": [],
            "bonus": [
                {"name": skill, "weight": max(5 - index, 1)}
                for index, skill in enumerate(skills[3:8])
            ],
        },
        "experience_years": min_years,
        "experience_requirements": {
            "core": [],
            "bonus": [],
            "min_total_years": min_years,
            "max_total_years": max_years,
        },
        "min_degree": min_degree,
        "education_constraints": {
            "min_degree": min_degree,
            "prefer_degrees": [],
            "required_majors": [],
            "preferred_majors": [],
            "languages": [],
            "certifications": [],
            "age_range": None,
            "other": [],
        },
        "tags": _build_standard_tags(skills, general_tags=topic_tags),
        "source": "niuke",
        "_detail_url": record.get("_detail_url"),
        "_category": record.get("_category"),
        "_has_salary": record.get("_has_salary"),
        "_has_valid_jd": record.get("_has_valid_jd"),
    }


def _map_zhaopin_json_record(record: dict[str, Any]) -> dict[str, Any]:
    title = _clean_text(record.get("job_name")) or "Untitled Role"
    description = _clean_text(record.get("jd"))
    salary_text = _clean_text(record.get("salary"))
    city = _clean_text(record.get("city"))
    work_address = _clean_text(record.get("work_address"))
    location = work_address or city
    company = _clean_text(record.get("company")) or "Company Pending"
    skill_tags = _string_list(record.get("skill_tags") or [])
    industry_tags = _split_delimited_text(record.get("company_industry"))
    context_text = _build_text_blob(
        [
            title,
            salary_text,
            city,
            work_address,
            record.get("education"),
            record.get("experience"),
            description,
            record.get("company_industry"),
            *skill_tags,
        ]
    )
    extracted_skills = _extract_skills(context_text)
    tagged_skills = [tag for tag in skill_tags if _looks_like_skill_label(tag)]
    skills = _string_list([*extracted_skills, *tagged_skills])
    general_tags = [tag for tag in skill_tags if tag not in skills]
    salary_fields = _parse_salary_text(salary_text)
    min_years, max_years = _parse_experience_text(record.get("experience"))
    min_degree = _normalize_degree(record.get("education")) or _extract_min_degree_from_text(context_text)

    return {
        "id": _extract_job_id(record) or _clean_text(record.get("_detail_url")),
        "job_name": record.get("job_name"),
        "title": title,
        "company": company,
        "location": location,
        "salary": salary_text,
        "salary_currency": salary_fields["currency"],
        "salary_negotiable": salary_fields["salary_negotiable"],
        "salary_min": salary_fields["salary_min"],
        "salary_max": salary_fields["salary_max"],
        "salary_months_min": salary_fields["salary_months_min"],
        "salary_months_max": salary_fields["salary_months_max"],
        "summary": description or title,
        "description": description,
        "raw_text": context_text,
        "responsibilities": [],
        "highlights": [],
        "skills": skills,
        "skill_requirements": {
            "required": [{"name": skill} for skill in skills[:3]],
            "optional_groups": [],
            "bonus": [
                {"name": skill, "weight": max(5 - index, 1)}
                for index, skill in enumerate(skills[3:8])
            ],
        },
        "experience_years": min_years,
        "experience_requirements": {
            "core": [],
            "bonus": [],
            "min_total_years": min_years,
            "max_total_years": max_years,
        },
        "min_degree": min_degree,
        "education_constraints": {
            "min_degree": min_degree,
            "prefer_degrees": [],
            "required_majors": [],
            "preferred_majors": [],
            "languages": [],
            "certifications": [],
            "age_range": None,
            "other": [],
        },
        "tags": _build_standard_tags(skills, general_tags=general_tags, industry_tags=industry_tags),
        "source": "zhaopin",
        "company_type": record.get("company_type"),
        "company_size": record.get("company_size"),
        "company_industry": record.get("company_industry"),
        "_detail_url": record.get("_detail_url"),
        "_category": record.get("_category"),
        "_has_salary": record.get("_has_salary"),
        "_has_valid_jd": record.get("_has_valid_jd"),
    }


def _iter_pageflux_sql_records(path: Path, limit: int | None):
    in_copy_block = False
    yielded = 0

    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for raw_line in handle:
            line = raw_line.rstrip("\r\n")
            if not in_copy_block:
                if COPY_HEADER_PATTERN.match(line):
                    in_copy_block = True
                continue

            if line == r"\.":
                break

            if not line:
                continue

            values = line.split("\t")
            yield _map_pageflux_row_to_job_payload(_parse_pageflux_copy_row(values))
            yielded += 1
            if limit is not None and yielded >= limit:
                break

    if not in_copy_block:
        raise ValueError(f"Could not find COPY talent_pool.jobs block in SQL dump: {path}")


def _parse_pageflux_copy_row(values: list[str]) -> dict[str, Any]:
    if len(values) < 20:
        raise ValueError(f"Unexpected SQL dump row with only {len(values)} fields.")

    jd_quality_passed = _bool_or_none(values[-1])
    source = _clean_copy_field(values[-2])
    updated_at = _clean_copy_field(values[-3])
    created_at, attached_degree = _extract_timestamp_suffix(values[-4])

    cursor = len(values) - 5
    min_degree = attached_degree
    if min_degree is None:
        min_degree = _clean_copy_field(values[cursor])
        cursor -= 1

    min_total_years = _float_or_none(values[cursor])
    cursor -= 1

    vector_project = _clean_copy_field(values[cursor])
    cursor -= 1
    vector_skill = _clean_copy_field(values[cursor])
    cursor -= 1
    vector_balanced = _clean_copy_field(values[cursor])
    cursor -= 1

    job_type_index = _find_job_type_index(values, cursor)
    currency_index = job_type_index + 8
    summary, responsibilities, highlights = _parse_summary_section(values[currency_index + 1 : cursor + 1])
    title, description, department, company_name, location = _parse_pre_job_type_block(values[3:job_type_index])

    return {
        "id": _clean_copy_field(values[0]),
        "job_id": _clean_copy_field(values[1]),
        "owner_org_id": _clean_copy_field(values[2]),
        "title": title,
        "description": description,
        "department": department,
        "company_name": company_name,
        "location": location,
        "job_type": _clean_copy_field(values[job_type_index]),
        "salary_negotiable": _bool_or_none(values[job_type_index + 1]),
        "salary_min": _int_or_none(values[job_type_index + 2]),
        "salary_max": _int_or_none(values[job_type_index + 3]),
        "salary_months_min": _int_or_none(values[job_type_index + 4]),
        "salary_months_max": _int_or_none(values[job_type_index + 5]),
        "intern_salary_amount": _int_or_none(values[job_type_index + 6]),
        "intern_salary_unit": _clean_copy_field(values[job_type_index + 7]),
        "currency": _clean_copy_field(values[currency_index]),
        "summary": summary,
        "responsibilities": responsibilities,
        "highlights": highlights,
        "query_embedding_balanced": vector_balanced,
        "query_embedding_skill": vector_skill,
        "query_embedding_project": vector_project,
        "min_total_years": min_total_years,
        "min_degree": min_degree,
        "created_at": created_at,
        "updated_at": updated_at,
        "source": source,
        "jd_quality_passed": jd_quality_passed,
    }


def _find_job_type_index(values: list[str], end_index: int) -> int:
    for index in range(end_index, -1, -1):
        text = (_clean_copy_field(values[index]) or "").lower()
        if text in JOB_TYPE_VALUES:
            return index
    raise ValueError("Could not locate job_type column in SQL dump row.")


def _parse_summary_section(values: list[str]) -> tuple[str | None, list[str], list[str]]:
    parts = [_clean_copy_field(value) for value in values]
    parts = [part for part in parts if part is not None]
    if not parts:
        return None, [], []
    if len(parts) == 1:
        return parts[0], [], []
    if len(parts) == 2:
        return parts[0], [], _parse_json_string_list(parts[1])

    summary = "\n\n".join(parts[:-2]) if len(parts) > 3 else parts[0]
    responsibilities = _parse_json_string_list(parts[-2])
    highlights = _parse_json_string_list(parts[-1])
    return summary, responsibilities, highlights


def _parse_pre_job_type_block(values: list[str]) -> tuple[str, str | None, str | None, str | None, str | None]:
    parts = [_clean_copy_field(value) for value in values]
    parts = [part for part in parts if part is not None]
    if not parts:
        return "Untitled Role", None, None, None, None

    if len(parts) >= 4:
        title = _clean_text(parts[0]) or "Untitled Role"
        description_parts = [part for part in parts[1:-2] if part]
        description = "\n\n".join(description_parts) if description_parts else None
        company_name = _clean_text(parts[-2])
        location = _clean_text(parts[-1])
        return title, description, None, company_name, location

    if len(parts) == 3:
        first, second, third = parts
        if _looks_like_description(first):
            title, description, _ = _split_title_and_description(first)
            return title, description, None, _clean_text(second), _clean_text(third)
        if _looks_like_description(second):
            title = _clean_text(first) or "Untitled Role"
            description = _clean_text(second)
            return title, description, None, None, _clean_text(third)
        title = _clean_text(first) or "Untitled Role"
        return title, None, None, _clean_text(second), _clean_text(third)

    if len(parts) == 2:
        first, second = parts
        if _looks_like_description(first):
            title, description, _ = _split_title_and_description(first)
            return title, description, None, _clean_text(second), None
        title = _clean_text(first) or "Untitled Role"
        return title, None, None, _clean_text(second), None

    title, description, _ = _split_title_and_description(parts[0])
    return title, description, None, None, None


def _looks_like_description(value: str) -> bool:
    if len(value) >= 80:
        return True
    return any(marker in value for marker in DESCRIPTION_HINTS)


def _split_title_and_description(value: str) -> tuple[str, str | None, str | None]:
    for marker in TITLE_SPLIT_MARKERS:
        position = value.find(marker)
        if position <= 0:
            continue
        title = value[:position].strip(" -/|") or "Untitled Role"
        description = value[position:].strip() or None
        return title, description, None
    return _clean_text(value) or "Untitled Role", None, None


def _map_pageflux_row_to_job_payload(row: dict[str, Any]) -> dict[str, Any]:
    title = str(row.get("title") or "Untitled Role").strip()
    summary = _compose_summary(row.get("summary"), row.get("description"), title)
    skills = _extract_skills(summary)
    required_skills = [{"name": skill} for skill in skills[:3]]
    bonus_skills = [
        {"name": skill, "weight": max(5 - index, 1)}
        for index, skill in enumerate(skills[3:8])
    ]
    tags = [
        {"name": skill, "category": "tech", "weight": 5 if index < 3 else 4}
        for index, skill in enumerate(skills[:8])
    ]

    return {
        "id": row.get("id") or row.get("job_id"),
        "job_id": row.get("job_id"),
        "company": row.get("company_name") or "Company Pending",
        "title": title,
        "department": row.get("department"),
        "location": row.get("location"),
        "job_type": row.get("job_type") or "fulltime",
        "salary_negotiable": row.get("salary_negotiable"),
        "salary_min": row.get("salary_min"),
        "salary_max": row.get("salary_max"),
        "salary_months_min": row.get("salary_months_min"),
        "salary_months_max": row.get("salary_months_max"),
        "intern_salary_amount": row.get("intern_salary_amount"),
        "intern_salary_unit": row.get("intern_salary_unit"),
        "salary_currency": row.get("currency") or "CNY",
        "summary": summary,
        "description": row.get("description"),
        "responsibilities": _string_list(row.get("responsibilities")),
        "highlights": _string_list(row.get("highlights")),
        "skills": skills,
        "skill_requirements": {
            "required": required_skills,
            "optional_groups": [],
            "bonus": bonus_skills,
        },
        "experience_years": row.get("min_total_years"),
        "experience_requirements": {
            "core": [],
            "bonus": [],
            "min_total_years": row.get("min_total_years"),
            "max_total_years": None,
        },
        "education_constraints": {
            "min_degree": _normalize_degree(row.get("min_degree")),
            "prefer_degrees": [],
            "required_majors": [],
            "preferred_majors": [],
            "languages": [],
            "certifications": [],
            "age_range": None,
            "other": [],
        },
        "tags": tags,
        "source": row.get("source"),
    }


def _extract_job_id(record: dict[str, Any]) -> str | None:
    explicit_id = _clean_text(record.get("id")) or _clean_text(record.get("job_id"))
    if explicit_id:
        return explicit_id
    detail_url = _clean_text(record.get("_detail_url"))
    if not detail_url:
        return None
    match = re.search(r"/(\d+)(?:\D*$|$)", detail_url)
    if match:
        return match.group(1)
    return detail_url


def _parse_embedded_jd(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    text = _clean_text(value)
    if not text:
        return {}
    if not text.startswith("{"):
        return {"text": text}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {"text": text}
    return payload if isinstance(payload, dict) else {"text": text}


def _build_text_blob(values: list[Any]) -> str:
    parts: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _clean_text(value)
        if not text:
            continue
        marker = text.lower()
        if marker in seen:
            continue
        seen.add(marker)
        parts.append(text)
    return "\n".join(parts)


def _split_delimited_text(value: Any) -> list[str]:
    text = _clean_text(value)
    if not text:
        return []
    items = re.split(r"[,，/|、;；]+", text)
    return _string_list(items)


def _build_standard_tags(
    skills: list[str],
    *,
    general_tags: list[str] | None = None,
    industry_tags: list[str] | None = None,
) -> list[dict[str, Any]]:
    tags: list[dict[str, Any]] = [
        {"name": skill, "category": "tech", "weight": 5 if index < 3 else 4}
        for index, skill in enumerate(skills[:8])
    ]
    tags.extend(
        {"name": tag, "category": "general", "weight": 3}
        for tag in (general_tags or [])[:6]
        if _clean_text(tag)
    )
    tags.extend(
        {"name": tag, "category": "industry", "weight": 3}
        for tag in (industry_tags or [])[:6]
        if _clean_text(tag)
    )
    return tags


def _looks_like_skill_label(value: str) -> bool:
    normalized = value.strip()
    if not normalized:
        return False
    if _extract_skills(normalized):
        return True
    lowered = normalized.lower()
    return lowered in {
        "小程序",
        "微信小程序",
        "uniapp",
        "flutter",
        "webgl",
    }


def _parse_experience_text(value: Any) -> tuple[float | None, float | None]:
    text = _clean_text(value)
    if not text:
        return None, None

    range_match = re.search(r"(\d+(?:\.\d+)?)\s*[-~～至到]\s*(\d+(?:\.\d+)?)\s*年", text)
    if range_match:
        return float(range_match.group(1)), float(range_match.group(2))

    min_match = re.search(r"(\d+(?:\.\d+)?)\s*年\s*(?:以上|及以上|\+|起)", text)
    if min_match:
        return float(min_match.group(1)), None

    exact_match = re.search(r"(\d+(?:\.\d+)?)\s*年", text)
    if exact_match:
        value = float(exact_match.group(1))
        return value, value

    if "应届" in text or "经验不限" in text:
        return 0.0, None
    return None, None


def _parse_salary_text(value: Any) -> dict[str, Any]:
    text = _clean_text(value)
    result = {
        "salary_negotiable": True if text and "面议" in text else None,
        "salary_min": None,
        "salary_max": None,
        "salary_months_min": None,
        "salary_months_max": None,
        "currency": "CNY",
    }
    if not text:
        return result

    months_match = re.search(r"(\d{1,2})(?:\s*[-~～至到]\s*(\d{1,2}))?\s*薪", text)
    if months_match:
        left = int(months_match.group(1))
        right = int(months_match.group(2) or months_match.group(1))
        result["salary_months_min"] = left
        result["salary_months_max"] = right

    monthly_k = re.search(
        r"(\d+(?:\.\d+)?)\s*[kK千]?\s*[-~～至到]\s*(\d+(?:\.\d+)?)\s*[kK千]",
        text,
    )
    if monthly_k:
        result["salary_min"] = int(round(float(monthly_k.group(1)) * 1000))
        result["salary_max"] = int(round(float(monthly_k.group(2)) * 1000))
        result["salary_negotiable"] = False
        return result

    monthly_plain = re.search(r"(\d{4,6})\s*[-~～至到]\s*(\d{4,6})\s*(?:元/月|元|/月)?", text)
    if monthly_plain:
        result["salary_min"] = int(monthly_plain.group(1))
        result["salary_max"] = int(monthly_plain.group(2))
        result["salary_negotiable"] = False
        return result

    monthly_wan = re.search(r"(\d+(?:\.\d+)?)\s*[-~～至到]\s*(\d+(?:\.\d+)?)\s*万", text)
    if monthly_wan:
        result["salary_min"] = int(round(float(monthly_wan.group(1)) * 10000))
        result["salary_max"] = int(round(float(monthly_wan.group(2)) * 10000))
        result["salary_negotiable"] = False
        return result

    yearly_wan = re.search(r"(\d+(?:\.\d+)?)\s*[-~～至到]\s*(\d+(?:\.\d+)?)\s*[万wW]\s*/?\s*年", text)
    if yearly_wan:
        result["salary_min"] = int(round(float(yearly_wan.group(1)) * 10000 / 12))
        result["salary_max"] = int(round(float(yearly_wan.group(2)) * 10000 / 12))
        result["salary_negotiable"] = False
    return result


def _extract_min_degree_from_text(text: Any) -> str | None:
    normalized = _clean_text(text)
    if not normalized:
        return None
    for token in ("博士", "phd", "doctor", "硕士", "master", "mba", "本科", "学士", "大专", "专科", "高中"):
        if token.lower() in normalized.lower() or token in normalized:
            return _normalize_degree(token)
    return None


def _compose_summary(summary: Any, description: Any, title: str) -> str:
    parts: list[str] = []
    for item in (summary, description):
        text = _clean_text(item)
        if not text:
            continue
        if text in parts:
            continue
        parts.append(text)
    if parts:
        return "\n\n".join(parts)
    return title or "Job description pending."


def _extract_skills(text: str) -> list[str]:
    matches: list[tuple[int, str]] = []
    for name, patterns in SKILL_PATTERNS:
        for pattern in patterns:
            result = re.search(pattern, text, re.IGNORECASE)
            if not result:
                continue
            matches.append((result.start(), name))
            break
    matches.sort(key=lambda item: item[0])

    ordered: list[str] = []
    seen: set[str] = set()
    for _, name in matches:
        marker = name.lower()
        if marker in seen:
            continue
        seen.add(marker)
        ordered.append(name)
    return ordered


def _parse_json_string_list(value: str | None) -> list[str]:
    text = _clean_text(value)
    if text is None:
        return []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return [text] if text.strip() else []
    if isinstance(payload, list):
        return _string_list(payload)
    normalized = _clean_text(payload)
    return [normalized] if normalized else []


def _string_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []

    results: list[str] = []
    seen: set[str] = set()
    for item in values:
        text = _clean_text(item)
        if not text:
            continue
        marker = text.lower()
        if marker in seen:
            continue
        seen.add(marker)
        results.append(text)
    return results


def _normalize_degree(value: Any) -> str | None:
    text = _clean_text(value)
    if not text:
        return None

    lowered = text.lower()
    if "本科" in text or "学士" in text or "bachelor" in lowered:
        return "bachelor"
    if "硕士" in text or "master" in lowered:
        return "master"
    if "mba" in lowered:
        return "mba"
    if "博士" in text or "phd" in lowered or "doctor" in lowered:
        return "phd"
    if "大专" in text or "专科" in text or "associate" in lowered or "college" in lowered:
        return "associate"
    if "高中" in text or "high school" in lowered:
        return "high_school"
    return lowered


def _extract_timestamp_suffix(value: str) -> tuple[str | None, str | None]:
    text = _clean_copy_field(value)
    if text is None:
        return None, None
    match = TIMESTAMP_SUFFIX_PATTERN.match(text)
    if match is None:
        return text, None
    prefix = match.group("prefix").strip() or None
    timestamp = match.group("timestamp")
    return timestamp, prefix


def _clean_copy_field(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    if text == r"\N":
        return None
    return _unescape_postgres_copy_text(text).strip() or None


def _unescape_postgres_copy_text(value: str) -> str:
    result: list[str] = []
    index = 0
    while index < len(value):
        char = value[index]
        if char != "\\":
            result.append(char)
            index += 1
            continue

        index += 1
        if index >= len(value):
            result.append("\\")
            break

        escaped = value[index]
        if escaped in "01234567":
            octal_digits = [escaped]
            for offset in range(1, 3):
                if index + offset >= len(value):
                    break
                candidate = value[index + offset]
                if candidate not in "01234567":
                    break
                octal_digits.append(candidate)
            result.append(chr(int("".join(octal_digits), 8)))
            index += len(octal_digits)
            continue

        mapping = {
            "b": "\b",
            "f": "\f",
            "n": "\n",
            "r": "\r",
            "t": "\t",
            "v": "\v",
            "\\": "\\",
        }
        result.append(mapping.get(escaped, escaped))
        index += 1
    return "".join(result)


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int_or_none(value: Any) -> int | None:
    text = _clean_copy_field(value)
    if text is None:
        return None
    try:
        return int(round(float(text)))
    except (TypeError, ValueError):
        return None


def _float_or_none(value: Any) -> float | None:
    text = _clean_copy_field(value)
    if text is None:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _bool_or_none(value: Any) -> bool | None:
    text = _clean_copy_field(value)
    if text is None:
        return None

    lowered = text.lower()
    if lowered in {"t", "true", "1", "yes"}:
        return True
    if lowered in {"f", "false", "0", "no"}:
        return False
    return None
