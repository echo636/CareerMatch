from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any
import urllib.error
import urllib.request

from app.domain.models import GapInsight


KNOWN_SKILLS = [
    "Python",
    "Flask",
    "FastAPI",
    "React",
    "Next.js",
    "TypeScript",
    "PostgreSQL",
    "Qdrant",
    "pgvector",
    "Docker",
    "LLM",
    "Embedding",
    "Prompt Design",
    "Redis",
]
KNOWN_PROJECT_TERMS = [
    "Resume Parsing",
    "Job Matching",
    "Semantic Search",
    "Scoring System",
    "Recommendation System",
    "Data Ingestion",
    "Service Orchestration",
    "Gap Analysis",
    "Agent",
    "Vector Search",
    "Prompt Engineering",
]
CURRENT_YEAR = datetime.now().year
DEFAULT_QWEN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_RESUME_SUMMARY = "Resume summary pending."
DEFAULT_JOB_SUMMARY = "Job description pending."


class BaseLLMClient(ABC):
    @abstractmethod
    def extract_resume(self, raw_text: str, file_name: str, resume_id: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def extract_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def generate_gap_insights(
        self,
        missing_skills: list[str],
        salary_gap: int,
        experience_gap_years: int,
    ) -> list[GapInsight]:
        raise NotImplementedError


class MockLLMClient(BaseLLMClient):
    def extract_resume(self, raw_text: str, file_name: str, resume_id: str) -> dict[str, Any]:
        skills = self._extract_terms(raw_text, KNOWN_SKILLS) or ["Python", "LLM"]
        projects = self._extract_terms(raw_text, KNOWN_PROJECT_TERMS) or ["Resume Parsing", "Job Matching"]
        years = self._extract_years(raw_text, default=5)
        salary_min, salary_max = self._extract_salary(raw_text, 25000, 35000)
        summary = raw_text.strip()[:200] or DEFAULT_RESUME_SUMMARY
        title = self._infer_resume_title(raw_text)
        return {
            "id": resume_id,
            "is_resume": True,
            "basic_info": {
                "name": Path(file_name).stem.replace("_", " ").strip() or "Unnamed Candidate",
                "work_years": years,
                "current_title": title,
                "summary": summary,
                "self_evaluation": summary,
            },
            "educations": [],
            "work_experiences": [
                {
                    "company_name": "Company Pending",
                    "title": title,
                    "responsibilities": [f"Led delivery of {projects[0]} related work."],
                    "achievements": ["Shipped features from requirement analysis to production."],
                    "tech_stack": skills[:5],
                }
            ],
            "projects": [
                {
                    "name": project,
                    "role": "Core Contributor",
                    "domain": "Intelligent Recruiting",
                    "description": f"Built a solution around {project}.",
                    "responsibilities": [f"Owned the {project} module."],
                    "achievements": [f"Accumulated reusable experience on {project}."],
                    "tech_stack": skills[:4],
                }
                for project in projects[:3]
            ],
            "skills": [
                {
                    "name": skill,
                    "level": "advanced" if index < 3 else "intermediate",
                    "years": years if index < 2 else max(years - 1, 1),
                    "last_used_year": CURRENT_YEAR,
                }
                for index, skill in enumerate(skills)
            ],
            "tags": [
                *[{"name": skill, "category": "tech"} for skill in skills],
                *[{"name": project, "category": "project"} for project in projects],
                {"name": "Intelligent Recruiting", "category": "domain"},
            ],
            "expected_salary": {"min": salary_min, "max": salary_max, "currency": "CNY"},
        }

    def extract_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        raw_text = payload.get("summary") or payload.get("raw_text") or payload.get("description") or ""
        basic_info = payload.get("basic_info") or {}
        skill_requirements = payload.get("skill_requirements") or {}
        experience_requirements = payload.get("experience_requirements") or {}
        skills = payload.get("skills") or self._extract_terms(raw_text, KNOWN_SKILLS) or ["Python"]
        projects = payload.get("project_keywords") or self._extract_terms(raw_text, KNOWN_PROJECT_TERMS) or ["Recommendation System"]
        years = int(payload.get("experience_years") or self._extract_years(raw_text, default=3))
        salary = payload.get("salary_range") or {}
        required = skill_requirements.get("required") or [{"name": name} for name in skills[:2]]
        return {
            "id": payload.get("id") or payload.get("job_id") or f"job-{abs(hash(raw_text or payload.get('title', 'job'))) % 100000}",
            "company": payload.get("company", "Company Pending"),
            "basic_info": {
                "title": payload.get("title") or basic_info.get("title") or "Untitled Role",
                "department": payload.get("department") or basic_info.get("department"),
                "location": payload.get("location") or basic_info.get("location") or "Remote",
                "job_type": payload.get("job_type") or basic_info.get("job_type") or "fulltime",
                "salary_negotiable": basic_info.get("salary_negotiable"),
                "salary_min": payload.get("salary_min") or basic_info.get("salary_min") or salary.get("min") or 20000,
                "salary_max": payload.get("salary_max") or basic_info.get("salary_max") or salary.get("max") or 30000,
                "currency": payload.get("salary_currency") or basic_info.get("currency") or salary.get("currency") or "CNY",
                "summary": raw_text or basic_info.get("summary") or DEFAULT_JOB_SUMMARY,
                "responsibilities": payload.get("responsibilities") or basic_info.get("responsibilities") or [],
                "highlights": payload.get("highlights") or basic_info.get("highlights") or [],
            },
            "skill_requirements": {
                "required": required,
                "optional_groups": skill_requirements.get("optional_groups") or [],
                "bonus": skill_requirements.get("bonus") or [{"name": skill, "weight": 5} for skill in skills[2:5]],
            },
            "experience_requirements": {
                "core": experience_requirements.get("core") or [
                    {"type": "project", "name": project, "min_years": max(years - 1, 1), "keywords": [project]}
                    for project in projects[:2]
                ],
                "bonus": experience_requirements.get("bonus") or [],
                "min_total_years": experience_requirements.get("min_total_years") or years,
                "max_total_years": experience_requirements.get("max_total_years"),
            },
            "education_constraints": payload.get("education_constraints") or {
                "min_degree": None,
                "prefer_degrees": [],
                "required_majors": [],
                "preferred_majors": [],
                "languages": [],
                "certifications": [],
                "age_range": None,
                "other": [],
            },
            "tags": payload.get("tags") or [
                *[{"name": skill, "category": "tech", "weight": 5} for skill in skills[:4]],
                *[{"name": project, "category": "project", "weight": 4} for project in projects[:3]],
            ],
        }

    def generate_gap_insights(
        self,
        missing_skills: list[str],
        salary_gap: int,
        experience_gap_years: int,
    ) -> list[GapInsight]:
        return [
            GapInsight("技能", "已具备一定的项目落地能力。", f"优先补齐这些核心短板：{' / '.join(missing_skills[:3]) or '暂无明显技能缺口'}。", "优先围绕岗位匹配、向量检索和数据调度补一条可量化项目案例。"),
            GapInsight("薪资", "当前预期与目标岗位存在一定差距。" if salary_gap > 0 else "当前预期与目标岗位基本重合。", f"通过量化项目结果，将薪资谈判差距控制在 {salary_gap} 元以内。", "补充匹配准确率、召回率和业务转化类指标，增强议价能力。"),
            GapInsight("经验", "现有经验已覆盖部分核心场景。", f"再补 {experience_gap_years} 年等价复杂度的系统设计与数据链路经验。", "围绕批量导入、异步任务和评估回放补一条完整工程案例。"),
        ]

    def _extract_terms(self, raw_text: str, dictionary: list[str]) -> list[str]:
        text = raw_text.lower()
        return [term for term in dictionary if term.lower() in text]

    def _extract_years(self, raw_text: str, default: int) -> int:
        match = re.search(r"(\d+)\s*(?:年|years?)", raw_text, re.IGNORECASE)
        return int(match.group(1)) if match else default

    def _extract_salary(self, raw_text: str, default_min: int, default_max: int) -> tuple[int, int]:
        matches = re.findall(r"(\d{4,5})", raw_text)
        if len(matches) >= 2:
            values = sorted(int(item) for item in matches[:2])
            return values[0], values[1]
        return default_min, default_max

    def _infer_resume_title(self, raw_text: str) -> str:
        lowered = raw_text.lower()
        if "agent" in lowered or "llm" in lowered:
            return "AI 应用工程师"
        if "flask" in lowered or "fastapi" in lowered:
            return "后端工程师"
        return "候选人"


class QwenLLMClient(BaseLLMClient):
    def __init__(
        self,
        *,
        api_key: str,
        model: str = "qwen-plus-latest",
        base_url: str = DEFAULT_QWEN_BASE_URL,
        timeout_sec: int = 60,
        fallback_client: BaseLLMClient | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_sec = timeout_sec
        self.fallback_client = fallback_client or MockLLMClient()
    def extract_resume(self, raw_text: str, file_name: str, resume_id: str) -> dict[str, Any]:
        fallback = self.fallback_client.extract_resume(raw_text, file_name, resume_id)
        payload = self._chat_json(self._resume_messages(raw_text, file_name, resume_id))
        merged = self._merge(fallback, payload)
        return self._normalize_resume(merged, raw_text, file_name, resume_id)

    def extract_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        fallback = self.fallback_client.extract_job(payload)
        model_payload = self._chat_json(self._job_messages(payload))
        merged = self._merge(fallback, model_payload)
        return self._normalize_job(merged, payload)

    def generate_gap_insights(
        self,
        missing_skills: list[str],
        salary_gap: int,
        experience_gap_years: int,
    ) -> list[GapInsight]:
        fallback = self.fallback_client.generate_gap_insights(
            missing_skills,
            salary_gap,
            experience_gap_years,
        )
        payload = self._chat_json(self._gap_messages(missing_skills, salary_gap, experience_gap_years))
        raw_items = payload.get("insights") if isinstance(payload, dict) else None
        if not isinstance(raw_items, list):
            return fallback

        insights: list[GapInsight] = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            dimension = self._normalize_dimension(item.get("dimension"))
            current_state = self._clean_text(item.get("current_state"))
            target_state = self._clean_text(item.get("target_state"))
            suggestion = self._clean_text(item.get("suggestion"))
            if not (dimension and current_state and target_state and suggestion):
                continue
            insights.append(GapInsight(dimension, current_state, target_state, suggestion))

        if not insights:
            return fallback

        seen = {item.dimension for item in insights}
        for item in fallback:
            if len(insights) >= 3:
                break
            if item.dimension in seen:
                continue
            insights.append(item)
        return insights[:3]

    def _resume_messages(self, raw_text: str, file_name: str, resume_id: str) -> list[dict[str, str]]:
        return [
            {
                "role": "system",
                "content": (
                    "You extract resumes into structured JSON for a recruiting system. "
                    "Return valid JSON only. No markdown fences. No commentary. "
                    "Keep field names in English exactly as requested. Preserve source language for text values."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Task: convert the following resume into structured JSON only.\n"
                    "Top-level keys: id, is_resume, basic_info, educations, work_experiences, projects, skills, tags, expected_salary.\n"
                    "Rules:\n"
                    "- id must equal the provided resume_id.\n"
                    "- is_resume must be true.\n"
                    "- Unknown scalar fields use null. Unknown collections use [].\n"
                    "- Keep only factual information grounded in the resume. Do not invent companies or projects.\n"
                    "- skill level should prefer: basic, intermediate, advanced, expert.\n"
                    "- tag category should prefer: tech, project, domain, industry, education, language, general.\n"
                    "- expected_salary should be monthly CNY when inferable.\n"
                    "- Return a single JSON object only.\n"
                    f"metadata={json.dumps({'resume_id': resume_id, 'file_name': file_name}, ensure_ascii=False)}\n"
                    f"resume_text={raw_text}"
                ),
            },
        ]

    def _job_messages(self, payload: dict[str, Any]) -> list[dict[str, str]]:
        return [
            {
                "role": "system",
                "content": (
                    "You normalize job descriptions into structured JSON for a recruiting system. "
                    "Return valid JSON only. No markdown fences. No commentary. "
                    "Preserve trustworthy structured input fields when they already exist."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Task: normalize the following job payload into JSON only.\n"
                    "Top-level keys: id, company, basic_info, skill_requirements, experience_requirements, education_constraints, tags.\n"
                    "Rules:\n"
                    "- Unknown scalar fields use null. Unknown collections use [].\n"
                    "- basic_info.title is required when inferable.\n"
                    "- required skills should contain hard requirements only. bonus skills are additive.\n"
                    "- experience type should prefer: project, domain, industry, tech, product, management.\n"
                    "- education min_degree should prefer: high_school, college, associate, bachelor, master, mba, phd, doctor.\n"
                    "- language items must contain language, level, required.\n"
                    "- salary should be monthly CNY when inferable.\n"
                    "- Return a single JSON object only.\n"
                    f"job_payload={json.dumps(payload, ensure_ascii=False)}"
                ),
            },
        ]

    def _gap_messages(
        self,
        missing_skills: list[str],
        salary_gap: int,
        experience_gap_years: int,
    ) -> list[dict[str, str]]:
        return [
            {
                "role": "system",
                "content": (
                    "You are a recruiting analyst. Return valid JSON only. No markdown fences. "
                    "Write concise Chinese recommendations."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Return exactly one JSON object with key insights. insights must be a list of exactly 3 items.\n"
                    "Each item must contain: dimension, current_state, target_state, suggestion.\n"
                    "The three dimensions must be 技能, 薪资, 经验.\n"
                    f"missing_skills={json.dumps(missing_skills, ensure_ascii=False)}\n"
                    f"salary_gap={salary_gap}\n"
                    f"experience_gap_years={experience_gap_years}"
                ),
            },
        ]

    def _chat_json(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        response = self._post_json(
            {
                "model": self.model,
                "messages": messages,
                "temperature": 0.1,
                "response_format": {"type": "json_object"},
            }
        )
        choices = response.get("choices") or []
        if not choices:
            raise RuntimeError("Qwen chat response did not include choices.")
        message = choices[0].get("message") or {}
        content = self._message_content_to_text(message.get("content"))
        if not content:
            raise RuntimeError("Qwen chat response did not include message content.")
        payload_text = self._extract_json_object(content)
        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Qwen chat response was not valid JSON: {content}") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("Qwen chat response root must be a JSON object.")
        return payload

    def _post_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            url=f"{self.base_url}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_sec) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Qwen chat request failed with status {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Qwen chat request failed: {exc.reason}") from exc
    def _message_content_to_text(self, content: Any) -> str:
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if not isinstance(item, dict):
                    continue
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
            return "\n".join(parts).strip()
        return ""

    def _extract_json_object(self, content: str) -> str:
        stripped = content.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            if len(lines) >= 3:
                stripped = "\n".join(lines[1:-1]).strip()
        try:
            json.loads(stripped)
            return stripped
        except json.JSONDecodeError:
            pass

        decoder = json.JSONDecoder()
        start = stripped.find("{")
        while start != -1:
            try:
                obj, end = decoder.raw_decode(stripped[start:])
                if isinstance(obj, dict):
                    return stripped[start : start + end]
            except json.JSONDecodeError:
                start = stripped.find("{", start + 1)
                continue
            start = stripped.find("{", start + 1)
        return stripped

    def _merge(self, base: Any, override: Any) -> Any:
        if override is None:
            return base
        if isinstance(base, dict) and isinstance(override, dict):
            merged = dict(base)
            for key, value in override.items():
                merged[key] = self._merge(base.get(key), value) if key in base else value
            return merged
        if isinstance(override, str) and not override.strip():
            return base
        return override

    def _normalize_resume(
        self,
        payload: Any,
        raw_text: str,
        file_name: str,
        resume_id: str,
    ) -> dict[str, Any]:
        data = payload if isinstance(payload, dict) else {}
        basic_info = self._as_dict(data.get("basic_info"))
        expected_salary = self._as_dict(data.get("expected_salary"))
        name = self._clean_text(basic_info.get("name")) or Path(file_name).stem.replace("_", " ").strip() or "Unnamed Candidate"
        summary = self._clean_text(basic_info.get("summary")) or self._clean_text(basic_info.get("self_evaluation")) or raw_text.strip()[:200] or DEFAULT_RESUME_SUMMARY
        salary_min, salary_max = self._ordered_int_pair(expected_salary.get("min"), expected_salary.get("max"), 25000, 35000)
        return {
            "id": resume_id,
            "is_resume": True,
            "basic_info": {
                "name": name,
                "gender": self._clean_text(basic_info.get("gender")),
                "age": self._int_or_none(basic_info.get("age")),
                "work_years": self._int_or_none(basic_info.get("work_years")),
                "current_city": self._clean_text(basic_info.get("current_city")),
                "current_title": self._clean_text(basic_info.get("current_title")),
                "current_company": self._clean_text(basic_info.get("current_company")),
                "status": self._clean_text(basic_info.get("status")),
                "email": self._clean_text(basic_info.get("email")),
                "phone": self._clean_text(basic_info.get("phone")),
                "wechat": self._clean_text(basic_info.get("wechat")),
                "ethnicity": self._clean_text(basic_info.get("ethnicity")),
                "birth_date": self._clean_text(basic_info.get("birth_date")),
                "native_place": self._clean_text(basic_info.get("native_place")),
                "residence": self._clean_text(basic_info.get("residence")),
                "political_status": self._clean_text(basic_info.get("political_status")),
                "id_number": self._clean_text(basic_info.get("id_number")),
                "marital_status": self._clean_text(basic_info.get("marital_status")),
                "summary": summary,
                "self_evaluation": self._clean_text(basic_info.get("self_evaluation")) or summary,
                "first_degree": self._clean_text(basic_info.get("first_degree")),
                "avatar": self._clean_text(basic_info.get("avatar")),
            },
            "educations": [self._normalize_resume_education(item) for item in self._as_list(data.get("educations"))],
            "work_experiences": [self._normalize_resume_work(item) for item in self._as_list(data.get("work_experiences"))],
            "projects": [self._normalize_resume_project(item) for item in self._as_list(data.get("projects"))],
            "skills": [self._normalize_resume_skill(item) for item in self._as_list(data.get("skills"))],
            "tags": [self._normalize_resume_tag(item) for item in self._as_list(data.get("tags"))],
            "expected_salary": {
                "min": salary_min,
                "max": salary_max,
                "currency": self._clean_text(expected_salary.get("currency")) or "CNY",
            },
        }

    def _normalize_job(self, payload: Any, original_payload: dict[str, Any]) -> dict[str, Any]:
        data = payload if isinstance(payload, dict) else {}
        basic_info = self._as_dict(data.get("basic_info"))
        skill_requirements = self._as_dict(data.get("skill_requirements"))
        experience_requirements = self._as_dict(data.get("experience_requirements"))
        education_constraints = self._as_dict(data.get("education_constraints"))
        fallback_text = self._clean_text(original_payload.get("summary")) or self._clean_text(original_payload.get("raw_text")) or self._clean_text(original_payload.get("description")) or ""
        title = self._clean_text(data.get("title")) or self._clean_text(basic_info.get("title")) or self._clean_text(original_payload.get("title")) or "Untitled Role"
        source_salary = self._as_dict(original_payload.get("salary_range"))
        salary_min, salary_max = self._normalize_optional_salary_range(
            basic_info.get("salary_min"),
            basic_info.get("salary_max"),
            original_payload.get("salary_min"),
            original_payload.get("salary_max"),
            source_salary.get("min"),
            source_salary.get("max"),
        )
        return {
            "id": self._clean_text(data.get("id")) or self._clean_text(original_payload.get("id")) or self._clean_text(original_payload.get("job_id")) or f"job-{abs(hash(fallback_text or title)) % 100000}",
            "company": self._clean_text(data.get("company")) or self._clean_text(original_payload.get("company")) or "Company Pending",
            "basic_info": {
                "title": title,
                "department": self._clean_text(basic_info.get("department")) or self._clean_text(original_payload.get("department")),
                "location": self._clean_text(basic_info.get("location")) or self._clean_text(original_payload.get("location")) or "Remote",
                "job_type": self._clean_text(basic_info.get("job_type")) or self._clean_text(original_payload.get("job_type")) or "fulltime",
                "salary_negotiable": self._bool_or_none(basic_info.get("salary_negotiable")),
                "salary_min": salary_min,
                "salary_max": salary_max,
                "salary_months_min": self._int_or_none(basic_info.get("salary_months_min")),
                "salary_months_max": self._int_or_none(basic_info.get("salary_months_max")),
                "intern_salary_amount": self._int_or_none(basic_info.get("intern_salary_amount")),
                "intern_salary_unit": self._clean_text(basic_info.get("intern_salary_unit")),
                "currency": self._clean_text(basic_info.get("currency")) or self._clean_text(original_payload.get("salary_currency")) or "CNY",
                "summary": self._clean_text(basic_info.get("summary")) or fallback_text or DEFAULT_JOB_SUMMARY,
                "responsibilities": self._string_list(basic_info.get("responsibilities")),
                "highlights": self._string_list(basic_info.get("highlights")),
            },
            "skill_requirements": {
                "required": [self._normalize_required_skill(item) for item in self._as_list(skill_requirements.get("required"))],
                "optional_groups": [self._normalize_optional_group(item) for item in self._as_list(skill_requirements.get("optional_groups"))],
                "bonus": [self._normalize_bonus_skill(item) for item in self._as_list(skill_requirements.get("bonus"))],
            },
            "experience_requirements": {
                "core": [self._normalize_experience_item(item) for item in self._as_list(experience_requirements.get("core"))],
                "bonus": [self._normalize_bonus_experience_item(item) for item in self._as_list(experience_requirements.get("bonus"))],
                "min_total_years": self._float_or_none(experience_requirements.get("min_total_years")),
                "max_total_years": self._float_or_none(experience_requirements.get("max_total_years")),
            },
            "education_constraints": {
                "min_degree": self._clean_text(education_constraints.get("min_degree")),
                "prefer_degrees": self._string_list(education_constraints.get("prefer_degrees")),
                "required_majors": self._string_list(education_constraints.get("required_majors")),
                "preferred_majors": self._string_list(education_constraints.get("preferred_majors")),
                "languages": [self._normalize_language(item) for item in self._as_list(education_constraints.get("languages"))],
                "certifications": self._string_list(education_constraints.get("certifications")),
                "age_range": self._clean_text(education_constraints.get("age_range")),
                "other": self._string_list(education_constraints.get("other")),
            },
            "tags": [self._normalize_job_tag(item) for item in self._as_list(data.get("tags"))],
        }
    def _normalize_resume_education(self, item: Any) -> dict[str, Any]:
        payload = self._as_dict(item)
        return {
            "school": self._clean_text(payload.get("school")) or "School Pending",
            "degree": self._clean_text(payload.get("degree")),
            "major": self._clean_text(payload.get("major")),
            "start_year": self._clean_text(payload.get("start_year")),
            "end_year": self._clean_text(payload.get("end_year")),
        }

    def _normalize_resume_work(self, item: Any) -> dict[str, Any]:
        payload = self._as_dict(item)
        return {
            "company_name": self._clean_text(payload.get("company_name")) or "Company Pending",
            "industry": self._clean_text(payload.get("industry")),
            "title": self._clean_text(payload.get("title")) or "Role Pending",
            "level": self._clean_text(payload.get("level")),
            "location": self._clean_text(payload.get("location")),
            "start_date": self._clean_text(payload.get("start_date")),
            "end_date": self._clean_text(payload.get("end_date")),
            "responsibilities": self._string_list(payload.get("responsibilities")),
            "achievements": self._string_list(payload.get("achievements")),
            "tech_stack": self._string_list(payload.get("tech_stack")),
        }

    def _normalize_resume_project(self, item: Any) -> dict[str, Any]:
        payload = self._as_dict(item)
        return {
            "name": self._clean_text(payload.get("name")) or "Project Pending",
            "role": self._clean_text(payload.get("role")),
            "domain": self._clean_text(payload.get("domain")),
            "description": self._clean_text(payload.get("description")),
            "responsibilities": self._string_list(payload.get("responsibilities")),
            "achievements": self._string_list(payload.get("achievements")),
            "tech_stack": self._string_list(payload.get("tech_stack")),
        }

    def _normalize_resume_skill(self, item: Any) -> dict[str, Any]:
        payload = self._as_dict(item)
        return {
            "name": self._clean_text(payload.get("name")) or "Skill Pending",
            "level": self._clean_text(payload.get("level")),
            "years": self._int_or_none(payload.get("years")),
            "last_used_year": self._int_or_none(payload.get("last_used_year")) or CURRENT_YEAR,
        }

    def _normalize_resume_tag(self, item: Any) -> dict[str, Any]:
        payload = self._as_dict(item)
        return {
            "name": self._clean_text(payload.get("name")) or "Tag Pending",
            "category": self._clean_text(payload.get("category")),
        }

    def _normalize_required_skill(self, item: Any) -> dict[str, Any]:
        payload = self._as_dict(item)
        return {
            "name": self._clean_text(payload.get("name")) or "Skill Pending",
            "level": self._clean_text(payload.get("level")),
            "min_years": self._float_or_none(payload.get("min_years")),
            "description": self._clean_text(payload.get("description")),
        }

    def _normalize_optional_group(self, item: Any) -> dict[str, Any]:
        payload = self._as_dict(item)
        return {
            "group_name": self._clean_text(payload.get("group_name")) or "Optional Skills",
            "description": self._clean_text(payload.get("description")),
            "min_required": self._int_or_none(payload.get("min_required")) or 1,
            "skills": [self._normalize_optional_skill(skill) for skill in self._as_list(payload.get("skills"))],
        }

    def _normalize_optional_skill(self, item: Any) -> dict[str, Any]:
        payload = self._as_dict(item)
        return {
            "name": self._clean_text(payload.get("name")) or "Skill Pending",
            "level": self._clean_text(payload.get("level")),
            "description": self._clean_text(payload.get("description")),
        }

    def _normalize_bonus_skill(self, item: Any) -> dict[str, Any]:
        payload = self._as_dict(item)
        return {
            "name": self._clean_text(payload.get("name")) or "Skill Pending",
            "weight": self._int_or_none(payload.get("weight")),
            "description": self._clean_text(payload.get("description")),
        }

    def _normalize_experience_item(self, item: Any) -> dict[str, Any]:
        payload = self._as_dict(item)
        return {
            "type": self._clean_text(payload.get("type")) or "project",
            "name": self._clean_text(payload.get("name")) or "Experience Pending",
            "min_years": self._float_or_none(payload.get("min_years")),
            "description": self._clean_text(payload.get("description")),
            "keywords": self._string_list(payload.get("keywords")),
        }

    def _normalize_bonus_experience_item(self, item: Any) -> dict[str, Any]:
        payload = self._as_dict(item)
        return {
            "type": self._clean_text(payload.get("type")) or "project",
            "name": self._clean_text(payload.get("name")) or "Experience Pending",
            "weight": self._int_or_none(payload.get("weight")),
            "description": self._clean_text(payload.get("description")),
            "keywords": self._string_list(payload.get("keywords")),
        }

    def _normalize_language(self, item: Any) -> dict[str, Any]:
        payload = self._as_dict(item)
        return {
            "language": self._clean_text(payload.get("language")) or "Language Pending",
            "level": self._clean_text(payload.get("level")),
            "required": self._bool_or_none(payload.get("required")),
        }

    def _normalize_job_tag(self, item: Any) -> dict[str, Any]:
        payload = self._as_dict(item)
        return {
            "name": self._clean_text(payload.get("name")) or "Tag Pending",
            "category": self._clean_text(payload.get("category")),
            "weight": self._int_or_none(payload.get("weight")),
        }

    def _normalize_dimension(self, value: Any) -> str | None:
        text = (self._clean_text(value) or "").lower()
        mapping = {
            "skill": "技能",
            "skills": "技能",
            "技能": "技能",
            "salary": "薪资",
            "compensation": "薪资",
            "薪资": "薪资",
            "经验": "经验",
            "experience": "经验",
        }
        return mapping.get(text, self._clean_text(value))

    def _as_dict(self, value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    def _as_list(self, value: Any) -> list[Any]:
        return value if isinstance(value, list) else []

    def _clean_text(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None
    def _string_list(self, value: Any) -> list[str]:
        source = value if isinstance(value, list) else []
        results: list[str] = []
        seen: set[str] = set()
        for item in source:
            text = self._clean_text(item)
            if not text:
                continue
            marker = text.lower()
            if marker in seen:
                continue
            seen.add(marker)
            results.append(text)
        return results

    def _int_or_none(self, value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(round(float(value)))
        except (TypeError, ValueError):
            return None

    def _float_or_none(self, value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _bool_or_none(self, value: Any) -> bool | None:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "1", "yes", "y"}:
                return True
            if normalized in {"false", "0", "no", "n"}:
                return False
        if isinstance(value, (int, float)):
            return bool(value)
        return None

    def _ordered_int_pair(self, left: Any, right: Any, default_left: int, default_right: int) -> tuple[int, int]:
        left_value = self._int_or_none(left)
        right_value = self._int_or_none(right)
        if left_value is None:
            left_value = default_left
        if right_value is None:
            right_value = default_right
        if left_value > right_value:
            left_value, right_value = right_value, left_value
        return left_value, right_value

    def _normalize_optional_salary_range(self, *values: Any) -> tuple[int | None, int | None]:
        ints = [self._int_or_none(value) for value in values]
        salary_min = next((ints[index] for index in (0, 2, 4) if ints[index] is not None), None)
        salary_max = next((ints[index] for index in (1, 3, 5) if ints[index] is not None), None)
        if salary_min is None and salary_max is None:
            return None, None
        if salary_min is None:
            salary_min = salary_max
        if salary_max is None:
            salary_max = salary_min
        if salary_min is not None and salary_max is not None and salary_min > salary_max:
            salary_min, salary_max = salary_max, salary_min
        return salary_min, salary_max

