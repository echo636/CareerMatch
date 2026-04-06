from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
import json
from pathlib import Path
import re
import time
from typing import Any
import urllib.error
import urllib.request

from app.core.logging_utils import get_logger
from app.domain.models import GapInsight
from app.job_enrichment import (
    build_job_context_text,
    clean_text,
    first_present,
    infer_education,
    infer_highlights,
    infer_responsibilities,
    infer_salary,
    infer_skills,
    infer_topics,
    infer_years_range,
)


CURRENT_YEAR = datetime.now().year
DEFAULT_QWEN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_RESUME_SUMMARY = "Resume summary pending."
DEFAULT_JOB_SUMMARY = "Job description pending."
LLM_PLACEHOLDER_TEXTS = {
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
RESUME_DATE_RANGE_PATTERN = re.compile(
    r"(?P<start>\d{4}[./-]\d{1,2})\s*(?:[-~～—–至到]+\s*)(?P<end>至今|\d{4}[./-]\d{1,2})"
)
RESUME_SECTION_MARKERS = ("工作经历", "工作经验")
RESUME_SECTION_END_MARKERS = ("项目经历", "项目经验", "教育经历", "教育背景", "技能", "自我评价")
RESUME_COMPANY_SUFFIXES = (
    "股份有限公司",
    "有限责任公司",
    "有限公司",
    "集团",
    "公司",
    "工作室",
    "研究院",
    "银行",
    "医院",
    "学校",
    "中心",
    "机构",
)
RESUME_TITLE_KEYWORDS = (
    "工程师",
    "开发",
    "主管",
    "经理",
    "负责人",
    "合伙人",
    "架构师",
    "总监",
    "leader",
    "leader",
    "director",
    "manager",
    "developer",
    "engineer",
    "architect",
    "顾问",
    "程序员",
)

logger = get_logger("clients.llm")


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

    @abstractmethod
    def score_job_match(self, resume_text: str, job_context: str) -> dict[str, Any]:
        raise NotImplementedError



class QwenLLMClient(BaseLLMClient):
    def __init__(
        self,
        *,
        api_key: str,
        model: str = "qwen-plus-latest",
        base_url: str = DEFAULT_QWEN_BASE_URL,
        timeout_sec: int = 120,
        retry_count: int = 2,
        retry_backoff_sec: float = 2.0,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_sec = timeout_sec
        self.retry_count = max(retry_count, 0)
        self.retry_backoff_sec = max(retry_backoff_sec, 0.0)
    def extract_resume(self, raw_text: str, file_name: str, resume_id: str) -> dict[str, Any]:
        payload = self._chat_json(self._resume_messages(raw_text, file_name, resume_id))
        return self._normalize_resume(payload, raw_text, file_name, resume_id)

    def extract_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self._is_standardized_job_payload(payload):
            logger.info(
                "llm.qwen.extract_job.fast_path title=%s company=%s",
                self._clean_text(payload.get("title")) or self._clean_text((payload.get("basic_info") or {}).get("title")),
                self._clean_text(payload.get("company")) or self._clean_text(payload.get("company_name")),
            )
            return self._normalize_job({}, payload)
        model_payload = self._chat_json(self._job_messages(payload))
        return self._normalize_job(model_payload, payload)

    def generate_gap_insights(
        self,
        missing_skills: list[str],
        salary_gap: int,
        experience_gap_years: int,
    ) -> list[GapInsight]:
        payload = self._chat_json(self._gap_messages(missing_skills, salary_gap, experience_gap_years))
        raw_items = payload.get("insights") if isinstance(payload, dict) else None
        if not isinstance(raw_items, list):
            raise RuntimeError("Qwen gap insights response did not include an insights list.")

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

        if len(insights) != 3:
            raise RuntimeError(
                f"Qwen gap insights response returned {len(insights)} valid insights; expected 3."
            )
        return insights

    def score_job_match(self, resume_text: str, job_context: str) -> dict[str, Any]:
        messages = self._match_score_messages(resume_text, job_context)
        payload = self._chat_json(messages)
        score = payload.get("score")
        if score is None:
            score = payload.get("overall_score")
        if not isinstance(score, (int, float)) or not (0 <= score <= 100):
            raise RuntimeError(f"LLM match score out of range or missing: {payload}")
        subscores = payload.get("subscores")
        normalized_subscores: dict[str, float] = {}
        if isinstance(subscores, dict):
            for key, value in subscores.items():
                if isinstance(value, (int, float)) and 0 <= float(value) <= 100:
                    normalized_subscores[str(key)] = round(float(value), 1)
        return {
            "score": round(float(score), 1),
            "reasoning": str(payload.get("reasoning") or ""),
            "subscores": normalized_subscores,
        }

    def _match_score_messages(self, resume_text: str, job_context: str) -> list[dict[str, str]]:
        return [
            {
                "role": "system",
                "content": (
                    "你是一位资深招聘评估专家。你的任务是评估一份简历与一个岗位的匹配程度。"
                    "返回合法 JSON，不要 markdown 代码块，不要多余文字。"
                    "你必须使用完整评分区间并尽量拉开相近岗位的分差，避免大量岗位出现同分。"
                ),
            },
            {
                "role": "user",
                "content": (
                    "请根据以下简历和岗位信息，综合评估匹配度并打分。\n"
                    "评分维度：技能匹配度、工作经验相关性、学历契合度、薪资合理性、业务/领域相似性、地点匹配度、转岗成本。\n"
                    "请特别注意：\n"
                    "1. 如果岗位是强专精岗位（例如高级Java、核心自研、大模型平台、银行/保险/交易等），而候选人缺少核心技术栈或领域经验，应显著降低分数。\n"
                    "2. 如果候选人的项目/业务域与岗位场景高度相似，即使主技术栈不完全一致，也可以适度上调分数。\n"
                    "3. 如果候选人的期望城市与岗位城市明显不一致，且岗位不是远程/混合办公，应明确扣分。\n"
                    "4. 评分必须拉开差距：若两个岗位匹配程度存在实际差异，overall_score 不要给出相同分数。\n"
                    "5. overall_score 使用 0-100 的一位小数，不要只给 42/62/80 这种整齐分段。\n"
                    "返回一个 JSON 对象，包含三个字段：\n"
                    '- score: 数值，0-100，保留 1 位小数，表示综合匹配度\n'
                    '- reasoning: 字符串，用中文简要说明打分依据（2-4句话）\n'
                    '- subscores: 对象，包含 skill, experience, education, salary, domain, location, transition_cost 七个字段，均为 0-100 的数值\n'
                    "评分参考：\n"
                    "- 85-100：高度匹配，主技术栈、业务场景、经验层级都明显贴合\n"
                    "- 70-84：较强匹配，有少量技术栈或地点偏差，但整体可转化\n"
                    "- 50-69：中等匹配，存在明显技术栈/领域缺口，但仍有迁移空间\n"
                    "- 30-49：弱匹配，核心技能或专精领域差距明显\n"
                    "- 0-29：基本不匹配，主技能、行业方向和岗位层级均明显错位\n"
                    "\n"
                    f"简历全文：\n{resume_text}\n"
                    "\n"
                    f"岗位信息：\n{job_context}"
                ),
            },
        ]

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
                    "- basic_info.current_company must be the candidate's MOST RECENT employer determined by date range, not by company prominence or order of appearance.\n"
                    "- basic_info.current_title must be the candidate's MOST RECENT job title determined by date range.\n"
                    "- work_experiences MUST be ordered by start_date DESCENDING (most recent experience first).\n"
                    "- basic_info.summary should be a concise but COMPLETE professional summary (2-4 sentences). Do NOT truncate mid-sentence. If the resume contains a self-evaluation section, use it as-is.\n"
                    "- basic_info.self_evaluation should contain the candidate's full self-evaluation text if present in the resume.\n"
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
                    "- When fields are null or empty but inferable from the provided context, fill them instead of leaving them empty.\n"
                    "- Especially try to infer responsibilities, highlights, experience years, degree, majors, languages, certifications, and salary-related fields when the text makes them clear.\n"
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
                    "The three dimensions must be \u6280\u80fd, \u85aa\u8d44, \u7ecf\u9a8c.\n"
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
        request_body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        max_attempts = self.retry_count + 1
        last_error: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            request = urllib.request.Request(
                url=f"{self.base_url}/chat/completions",
                data=request_body,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            try:
                logger.info(
                    "llm.qwen.request_start model=%s attempt=%s/%s timeout_sec=%s",
                    self.model,
                    attempt,
                    max_attempts,
                    self.timeout_sec,
                )
                with urllib.request.urlopen(request, timeout=self.timeout_sec) as response:
                    result = json.loads(response.read().decode("utf-8"))
                logger.info(
                    "llm.qwen.request_success model=%s attempt=%s/%s",
                    self.model,
                    attempt,
                    max_attempts,
                )
                return result
            except TimeoutError as exc:
                last_error = exc
                logger.warning(
                    "llm.qwen.timeout model=%s attempt=%s/%s timeout_sec=%s",
                    self.model,
                    attempt,
                    max_attempts,
                    self.timeout_sec,
                )
                if attempt >= max_attempts:
                    raise RuntimeError(
                        f"Qwen chat request timed out after {self.timeout_sec} seconds."
                    ) from exc
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                last_error = exc
                retryable = exc.code in {408, 429, 500, 502, 503, 504}
                logger.warning(
                    "llm.qwen.http_error model=%s attempt=%s/%s status=%s retryable=%s detail=%s",
                    self.model,
                    attempt,
                    max_attempts,
                    exc.code,
                    retryable,
                    detail,
                )
                if not retryable or attempt >= max_attempts:
                    raise RuntimeError(f"Qwen chat request failed with status {exc.code}: {detail}") from exc
            except urllib.error.URLError as exc:
                last_error = exc
                timeout_reason = isinstance(exc.reason, TimeoutError)
                retryable = timeout_reason or isinstance(exc.reason, ConnectionResetError) or isinstance(exc.reason, OSError)
                logger.warning(
                    "llm.qwen.url_error model=%s attempt=%s/%s retryable=%s reason=%s",
                    self.model,
                    attempt,
                    max_attempts,
                    retryable,
                    exc.reason,
                )
                if not retryable or attempt >= max_attempts:
                    if timeout_reason:
                        raise RuntimeError(
                            f"Qwen chat request timed out after {self.timeout_sec} seconds."
                        ) from exc
                    raise RuntimeError(f"Qwen chat request failed: {exc.reason}") from exc

            sleep_sec = self.retry_backoff_sec * attempt
            if sleep_sec > 0:
                logger.info(
                    "llm.qwen.retry_sleep model=%s next_attempt=%s sleep_sec=%.1f",
                    self.model,
                    attempt + 1,
                    sleep_sec,
                )
                time.sleep(sleep_sec)

        raise RuntimeError("Qwen chat request failed after retries.") from last_error
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
        summary = self._clean_text(basic_info.get("summary")) or self._clean_text(basic_info.get("self_evaluation")) or raw_text.strip()[:500] or DEFAULT_RESUME_SUMMARY
        salary_min, salary_max = self._ordered_int_pair(expected_salary.get("min"), expected_salary.get("max"), 0, 0)
        normalized_work_items = [
            self._normalize_resume_work(item) for item in self._as_list(data.get("work_experiences"))
        ]
        work_experiences = self._merge_resume_work_experiences(
            self._fill_resume_work_experiences_from_raw_text(normalized_work_items, raw_text),
            self._infer_resume_work_experiences(raw_text),
        )
        latest_experience = work_experiences[0] if work_experiences else {}
        return {
            "id": resume_id,
            "is_resume": True,
            "basic_info": {
                "name": name,
                "gender": self._clean_text(basic_info.get("gender")),
                "age": self._int_or_none(basic_info.get("age")),
                "work_years": self._int_or_none(basic_info.get("work_years")),
                "current_city": self._clean_text(basic_info.get("current_city")),
                "current_title": self._clean_text(basic_info.get("current_title")) or self._clean_text(latest_experience.get("title")),
                "current_company": self._clean_text(basic_info.get("current_company")) or self._clean_text(latest_experience.get("company_name")),
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
            "work_experiences": work_experiences,
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
        source_basic_info = self._as_dict(original_payload.get("basic_info"))
        source_skill_requirements = self._as_dict(original_payload.get("skill_requirements"))
        source_experience_requirements = self._as_dict(original_payload.get("experience_requirements"))
        source_education_constraints = self._as_dict(original_payload.get("education_constraints"))
        context_text = build_job_context_text(original_payload)

        title = self._clean_text(data.get("title")) or self._clean_text(basic_info.get("title")) or self._clean_text(original_payload.get("title")) or self._clean_text(source_basic_info.get("title")) or "Untitled Role"
        inferred_skills = infer_skills(original_payload, context_text)
        inferred_topics = infer_topics(original_payload, title, context_text)
        inferred_responsibilities = infer_responsibilities(original_payload, context_text)
        inferred_highlights = infer_highlights(original_payload, context_text)
        inferred_min_years, inferred_max_years = infer_years_range(context_text)
        inferred_salary = infer_salary(context_text)
        inferred_education = infer_education(context_text)
        source_salary = self._as_dict(original_payload.get("salary_range"))

        salary_min, salary_max = self._normalize_optional_salary_range(
            basic_info.get("salary_min"),
            basic_info.get("salary_max"),
            source_basic_info.get("salary_min"),
            source_basic_info.get("salary_max"),
            original_payload.get("salary_min"),
            original_payload.get("salary_max"),
            source_salary.get("min"),
            source_salary.get("max"),
            inferred_salary.get("salary_min"),
            inferred_salary.get("salary_max"),
        )

        responsibilities = self._string_list(basic_info.get("responsibilities"))
        if not responsibilities:
            responsibilities = self._string_list(original_payload.get("responsibilities"))
        if not responsibilities:
            responsibilities = self._string_list(source_basic_info.get("responsibilities"))
        if not responsibilities:
            responsibilities = inferred_responsibilities

        highlights = self._string_list(basic_info.get("highlights"))
        if not highlights:
            highlights = self._string_list(original_payload.get("highlights"))
        if not highlights:
            highlights = self._string_list(source_basic_info.get("highlights"))
        if not highlights:
            highlights = inferred_highlights

        required_items = [self._normalize_required_skill(item) for item in self._as_list(skill_requirements.get("required"))]
        if not required_items:
            required_items = [self._normalize_required_skill(item) for item in self._as_list(source_skill_requirements.get("required"))]
        if not required_items:
            required_items = [self._normalize_required_skill({"name": name}) for name in inferred_skills[:3]]

        optional_groups = [self._normalize_optional_group(item) for item in self._as_list(skill_requirements.get("optional_groups"))]
        if not optional_groups:
            optional_groups = [self._normalize_optional_group(item) for item in self._as_list(source_skill_requirements.get("optional_groups"))]

        bonus_items = [self._normalize_bonus_skill(item) for item in self._as_list(skill_requirements.get("bonus"))]
        if not bonus_items:
            bonus_items = [self._normalize_bonus_skill(item) for item in self._as_list(source_skill_requirements.get("bonus"))]
        if not bonus_items:
            bonus_items = [
                self._normalize_bonus_skill({"name": skill, "weight": max(5 - index, 1)})
                for index, skill in enumerate(inferred_skills[3:8])
            ]

        core_items = [self._normalize_experience_item(item) for item in self._as_list(experience_requirements.get("core"))]
        if not core_items:
            core_items = [self._normalize_experience_item(item) for item in self._as_list(source_experience_requirements.get("core"))]
        if not core_items:
            core_items = [
                self._normalize_experience_item({"type": "project", "name": topic, "keywords": [topic]})
                for topic in inferred_topics[:2]
            ]

        bonus_experience_items = [self._normalize_bonus_experience_item(item) for item in self._as_list(experience_requirements.get("bonus"))]
        if not bonus_experience_items:
            bonus_experience_items = [self._normalize_bonus_experience_item(item) for item in self._as_list(source_experience_requirements.get("bonus"))]

        languages = [self._normalize_language(item) for item in self._as_list(education_constraints.get("languages"))]
        if not languages:
            languages = [self._normalize_language(item) for item in self._as_list(source_education_constraints.get("languages"))]
        if not languages:
            languages = [self._normalize_language(item) for item in inferred_education.get("languages") or []]

        tags = [self._normalize_job_tag(item) for item in self._as_list(data.get("tags"))]
        if not tags:
            tags = [self._normalize_job_tag(item) for item in self._as_list(original_payload.get("tags"))]
        if not tags:
            tags = [
                *[
                    self._normalize_job_tag({"name": skill, "category": "tech", "weight": 5 if index < 3 else 4})
                    for index, skill in enumerate(inferred_skills[:8])
                ],
                *[
                    self._normalize_job_tag({"name": topic, "category": "project", "weight": 4})
                    for topic in inferred_topics[:3]
                ],
            ]

        salary_negotiable = first_present(
            self._bool_or_none(basic_info.get("salary_negotiable")),
            self._bool_or_none(source_basic_info.get("salary_negotiable")),
            self._bool_or_none(original_payload.get("salary_negotiable")),
            inferred_salary.get("salary_negotiable"),
        )
        salary_months_min = first_present(
            self._int_or_none(basic_info.get("salary_months_min")),
            self._int_or_none(source_basic_info.get("salary_months_min")),
            self._int_or_none(original_payload.get("salary_months_min")),
            inferred_salary.get("salary_months_min"),
        )
        salary_months_max = first_present(
            self._int_or_none(basic_info.get("salary_months_max")),
            self._int_or_none(source_basic_info.get("salary_months_max")),
            self._int_or_none(original_payload.get("salary_months_max")),
            inferred_salary.get("salary_months_max"),
        )
        intern_salary_amount = first_present(
            self._int_or_none(basic_info.get("intern_salary_amount")),
            self._int_or_none(source_basic_info.get("intern_salary_amount")),
            self._int_or_none(original_payload.get("intern_salary_amount")),
            inferred_salary.get("intern_salary_amount"),
        )
        intern_salary_unit = first_present(
            self._clean_text(basic_info.get("intern_salary_unit")),
            self._clean_text(source_basic_info.get("intern_salary_unit")),
            self._clean_text(original_payload.get("intern_salary_unit")),
            inferred_salary.get("intern_salary_unit"),
        )

        return {
            "id": self._clean_text(data.get("id")) or self._clean_text(original_payload.get("id")) or self._clean_text(original_payload.get("job_id")) or f"job-{abs(hash(context_text or title)) % 100000}",
            "company": self._clean_text(data.get("company")) or self._clean_text(original_payload.get("company")) or self._clean_text(original_payload.get("company_name")) or "Company Pending",
            "basic_info": {
                "title": title,
                "department": self._clean_text(basic_info.get("department")) or self._clean_text(source_basic_info.get("department")) or self._clean_text(original_payload.get("department")),
                "location": self._clean_text(basic_info.get("location")) or self._clean_text(source_basic_info.get("location")) or self._clean_text(original_payload.get("location")) or "Remote",
                "job_type": self._clean_text(basic_info.get("job_type")) or self._clean_text(source_basic_info.get("job_type")) or self._clean_text(original_payload.get("job_type")) or "fulltime",
                "salary_negotiable": salary_negotiable,
                "salary_min": salary_min,
                "salary_max": salary_max,
                "salary_months_min": salary_months_min,
                "salary_months_max": salary_months_max,
                "intern_salary_amount": intern_salary_amount,
                "intern_salary_unit": intern_salary_unit,
                "currency": self._clean_text(basic_info.get("currency")) or self._clean_text(source_basic_info.get("currency")) or self._clean_text(original_payload.get("salary_currency")) or self._clean_text(source_salary.get("currency")) or self._clean_text(inferred_salary.get("currency")) or "CNY",
                "summary": self._clean_text(basic_info.get("summary")) or self._clean_text(source_basic_info.get("summary")) or self._clean_text(original_payload.get("summary")) or self._clean_text(original_payload.get("raw_text")) or self._clean_text(original_payload.get("description")) or context_text or DEFAULT_JOB_SUMMARY,
                "responsibilities": responsibilities,
                "highlights": highlights,
            },
            "skill_requirements": {
                "required": required_items,
                "optional_groups": optional_groups,
                "bonus": bonus_items,
            },
            "experience_requirements": {
                "core": core_items,
                "bonus": bonus_experience_items,
                "min_total_years": first_present(
                    self._positive_float_or_none(experience_requirements.get("min_total_years")),
                    self._positive_float_or_none(source_experience_requirements.get("min_total_years")),
                    self._positive_float_or_none(original_payload.get("experience_years")),
                    inferred_min_years,
                ),
                "max_total_years": first_present(
                    self._positive_float_or_none(experience_requirements.get("max_total_years")),
                    self._positive_float_or_none(source_experience_requirements.get("max_total_years")),
                    inferred_max_years,
                ),
            },
            "education_constraints": {
                "min_degree": self._clean_text(education_constraints.get("min_degree")) or self._clean_text(source_education_constraints.get("min_degree")) or self._clean_text(inferred_education.get("min_degree")),
                "prefer_degrees": self._string_list(education_constraints.get("prefer_degrees")) or self._string_list(source_education_constraints.get("prefer_degrees")) or list(inferred_education.get("prefer_degrees") or []),
                "required_majors": self._string_list(education_constraints.get("required_majors")) or self._string_list(source_education_constraints.get("required_majors")) or list(inferred_education.get("required_majors") or []),
                "preferred_majors": self._string_list(education_constraints.get("preferred_majors")) or self._string_list(source_education_constraints.get("preferred_majors")) or list(inferred_education.get("preferred_majors") or []),
                "languages": languages,
                "certifications": self._string_list(education_constraints.get("certifications")) or self._string_list(source_education_constraints.get("certifications")) or list(inferred_education.get("certifications") or []),
                "age_range": self._clean_text(education_constraints.get("age_range")) or self._clean_text(source_education_constraints.get("age_range")) or self._clean_text(inferred_education.get("age_range")),
                "other": self._string_list(education_constraints.get("other")) or self._string_list(source_education_constraints.get("other")) or list(inferred_education.get("other") or []),
            },
            "tags": tags,
        }

    def _is_standardized_job_payload(self, payload: dict[str, Any]) -> bool:
        title = self._clean_text(payload.get("title")) or self._clean_text((payload.get("basic_info") or {}).get("title"))
        company = self._clean_text(payload.get("company")) or self._clean_text(payload.get("company_name"))
        has_structured_text = any(
            self._clean_text(payload.get(key))
            for key in ("summary", "description", "raw_text", "location", "salary")
        )
        has_skills = bool(payload.get("skill_requirements") or payload.get("skills") or payload.get("skill_tags"))
        return bool(title and company and has_structured_text and has_skills)
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
            "company_name": self._clean_text(payload.get("company_name")) or "",
            "industry": self._clean_text(payload.get("industry")),
            "title": self._clean_text(payload.get("title")) or "",
            "level": self._clean_text(payload.get("level")),
            "location": self._clean_text(payload.get("location")),
            "start_date": self._clean_text(payload.get("start_date")),
            "end_date": self._clean_text(payload.get("end_date")),
            "responsibilities": self._string_list(payload.get("responsibilities")),
            "achievements": self._string_list(payload.get("achievements")),
            "tech_stack": self._string_list(payload.get("tech_stack")),
        }

    def _merge_resume_work_experiences(
        self,
        extracted_items: list[dict[str, Any]],
        inferred_items: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not extracted_items:
            return self._dedupe_resume_work_experiences(inferred_items)
        if not inferred_items:
            return self._dedupe_resume_work_experiences(extracted_items)

        inferred_by_key = {
            key: item for item in inferred_items if (key := self._resume_work_key(item))
        }
        merged: list[dict[str, Any]] = []

        for index, item in enumerate(extracted_items):
            key = self._resume_work_key(item)
            fallback = inferred_by_key.get(key) if key else None
            if (
                fallback is None
                and key is None
                and not self._clean_text(item.get("title"))
                and not self._clean_text(item.get("company_name"))
                and index < len(inferred_items)
            ):
                fallback = inferred_items[index]

            merged.append(self._merge_resume_work_item(item, fallback))

        merged_keys = {self._resume_work_key(item) for item in merged if self._resume_work_key(item)}
        for inferred in inferred_items:
            inferred_key = self._resume_work_key(inferred)
            if inferred_key and inferred_key in merged_keys:
                continue
            merged.append(inferred)

        return self._dedupe_resume_work_experiences(merged)

    def _fill_resume_work_experiences_from_raw_text(
        self,
        items: list[dict[str, Any]],
        raw_text: str,
    ) -> list[dict[str, Any]]:
        if not items or not raw_text.strip():
            return items

        normalized_lines = [line.strip() for line in raw_text.replace("\r\n", "\n").splitlines() if line.strip()]
        filled: list[dict[str, Any]] = []
        for item in items:
            allow_start_only = not self._clean_text(item.get("title")) and not self._clean_text(item.get("company_name"))
            fallback = self._find_resume_work_item_from_lines(
                normalized_lines,
                self._clean_text(item.get("start_date")),
                self._clean_text(item.get("end_date")),
                allow_start_only=allow_start_only,
            )
            filled.append(self._merge_resume_work_item(item, fallback))
        return self._dedupe_resume_work_experiences(filled)

    def _merge_resume_work_item(
        self,
        primary: dict[str, Any],
        fallback: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if fallback is None:
            return primary
        has_primary_identity = bool(
            self._clean_text(primary.get("title")) or self._clean_text(primary.get("company_name"))
        )
        return {
            "company_name": self._clean_text(primary.get("company_name")) or self._clean_text(fallback.get("company_name")) or "",
            "industry": self._clean_text(primary.get("industry")) or self._clean_text(fallback.get("industry")),
            "title": self._clean_text(primary.get("title")) or self._clean_text(fallback.get("title")) or "",
            "level": self._clean_text(primary.get("level")) or self._clean_text(fallback.get("level")),
            "location": self._clean_text(primary.get("location")) or self._clean_text(fallback.get("location")),
            "start_date": (
                self._clean_text(primary.get("start_date"))
                if has_primary_identity
                else None
            ) or self._clean_text(fallback.get("start_date")) or self._clean_text(primary.get("start_date")),
            "end_date": (
                self._clean_text(primary.get("end_date"))
                if has_primary_identity
                else None
            ) or self._clean_text(fallback.get("end_date")) or self._clean_text(primary.get("end_date")),
            "responsibilities": self._string_list(primary.get("responsibilities")) or self._string_list(fallback.get("responsibilities")),
            "achievements": self._string_list(primary.get("achievements")) or self._string_list(fallback.get("achievements")),
            "tech_stack": self._string_list(primary.get("tech_stack")) or self._string_list(fallback.get("tech_stack")),
        }

    def _resume_work_key(self, item: dict[str, Any]) -> str | None:
        start = self._normalize_resume_date_token(self._clean_text(item.get("start_date")))
        end = self._normalize_resume_date_token(self._clean_text(item.get("end_date")))
        if start or end:
            return f"{start or ''}|{end or ''}"
        return None

    def _infer_resume_work_experiences(self, raw_text: str) -> list[dict[str, Any]]:
        section_text = self._resume_work_section(raw_text)
        if not section_text:
            return []

        inferred: list[dict[str, Any]] = []
        for raw_line in section_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            match = RESUME_DATE_RANGE_PATTERN.search(line)
            if match is None:
                continue

            start_date = self._normalize_resume_date(match.group("start"))
            end_date = self._normalize_resume_date(match.group("end"))
            company_name, title = self._split_resume_company_title_from_line(line, match)
            if not company_name and not title:
                continue

            inferred.append(
                {
                    "company_name": company_name or "",
                    "industry": None,
                    "title": title or "",
                    "level": None,
                    "location": None,
                    "start_date": start_date,
                    "end_date": end_date,
                    "responsibilities": [],
                    "achievements": [],
                    "tech_stack": [],
                }
            )

        return inferred

    def _find_resume_work_item_from_lines(
        self,
        lines: list[str],
        start_date: str | None,
        end_date: str | None,
        allow_start_only: bool = False,
    ) -> dict[str, Any] | None:
        normalized_start = self._normalize_resume_date_token(start_date)
        normalized_end = self._normalize_resume_date_token(end_date)
        if not normalized_start:
            return None

        for line in lines:
            match = RESUME_DATE_RANGE_PATTERN.search(line)
            if match is None:
                continue
            matched_start = self._normalize_resume_date_token(match.group("start"))
            matched_end = self._normalize_resume_date_token(match.group("end"))
            if matched_start != normalized_start:
                continue
            if normalized_end and matched_end and normalized_end != matched_end:
                if allow_start_only:
                    pass
                else:
                    continue
            if normalized_end and not matched_end and not allow_start_only:
                continue

            parsed_start = self._normalize_resume_date(match.group("start"))
            parsed_end = self._normalize_resume_date(match.group("end"))
            company_name, title = self._split_resume_company_title_from_line(line, match)
            if not company_name and not title:
                continue
            return {
                "company_name": company_name or "",
                "industry": None,
                "title": title or "",
                "level": None,
                "location": None,
                "start_date": parsed_start,
                "end_date": parsed_end,
                "responsibilities": [],
                "achievements": [],
                "tech_stack": [],
            }

        return None

    def _dedupe_resume_work_experiences(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ordered_keys: list[str | None] = []
        best_by_key: dict[str, dict[str, Any]] = {}
        keyless_items: list[dict[str, Any]] = []

        for item in items:
            key = self._resume_work_key(item)
            if key is None:
                keyless_items.append(item)
                continue
            if key not in best_by_key:
                ordered_keys.append(key)
                best_by_key[key] = item
                continue
            if self._resume_work_item_score(item) > self._resume_work_item_score(best_by_key[key]):
                best_by_key[key] = item

        deduped = [best_by_key[key] for key in ordered_keys]
        deduped.extend(keyless_items)
        return self._sort_resume_work_by_date_desc(deduped)

    def _sort_resume_work_by_date_desc(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Sort work experiences by date descending (most recent first).

        Ordering priority:
        - end_date '至今' (present) comes first
        - Then by end_date descending
        - Then by start_date descending
        - Items without any parseable date go last
        """
        def sort_key(item: dict[str, Any]) -> tuple[int, str, str]:
            end = self._normalize_resume_date_token(self._clean_text(item.get("end_date")))
            start = self._normalize_resume_date_token(self._clean_text(item.get("start_date")))
            if end == "至今":
                return (0, "9999.99", start or "9999.99")
            if end:
                return (1, end, start or "0000.00")
            if start:
                return (2, start, "0000.00")
            return (3, "0000.00", "0000.00")

        return sorted(items, key=sort_key, reverse=True)

    def _resume_work_item_score(self, item: dict[str, Any]) -> int:
        score = 0
        if self._clean_text(item.get("company_name")):
            score += 2
        if self._clean_text(item.get("title")):
            score += 2
        if self._clean_text(item.get("industry")):
            score += 1
        if self._clean_text(item.get("location")):
            score += 1
        if self._string_list(item.get("responsibilities")):
            score += 1
        if self._string_list(item.get("achievements")):
            score += 1
        if self._string_list(item.get("tech_stack")):
            score += 1
        return score

    def _resume_work_section(self, raw_text: str) -> str:
        normalized_text = raw_text.replace("\r\n", "\n")
        start_index = -1
        for marker in RESUME_SECTION_MARKERS:
            marker_index = normalized_text.find(marker)
            if marker_index != -1:
                start_index = marker_index + len(marker)
                break
        if start_index == -1:
            return normalized_text

        section = normalized_text[start_index:]
        end_positions = [
            position for marker in RESUME_SECTION_END_MARKERS if (position := section.find(marker)) != -1
        ]
        if end_positions:
            section = section[: min(end_positions)]
        return section.strip()

    def _normalize_resume_date(self, value: str) -> str:
        if value == "至今":
            return value
        match = re.match(r"(?P<year>\d{4})[./-](?P<month>\d{1,2})", value)
        if match is None:
            return value
        year = match.group("year")
        month = int(match.group("month"))
        return f"{year}.{month:02d}"

    def _normalize_resume_date_token(self, value: str | None) -> str | None:
        cleaned = self._clean_text(value)
        if not cleaned:
            return None
        if cleaned == "至今":
            return cleaned
        match = re.match(r"(?P<year>\d{4})[./-](?P<month>\d{1,2})", cleaned)
        if match is None:
            return cleaned
        return f"{match.group('year')}.{int(match.group('month')):02d}"

    def _split_resume_company_title_from_line(
        self,
        line: str,
        match: re.Match[str],
    ) -> tuple[str | None, str | None]:
        before = line[: match.start()].strip(" ：:|/\\-—–")
        after = line[match.end() :].strip(" ：:|/\\-—–")
        if after:
            company_name, title = self._split_resume_company_title(after)
            if company_name or title:
                return company_name, title
        if before:
            company_name, title = self._split_resume_company_title(before)
            if company_name or title:
                return company_name, title
        combined = " ".join(part for part in [before, after] if part).strip()
        if combined:
            return self._split_resume_company_title(combined)
        return None, None

    def _split_resume_company_title(self, text: str) -> tuple[str | None, str | None]:
        normalized = re.sub(r"\s+", " ", text).strip()
        if not normalized:
            return None, None

        for suffix in RESUME_COMPANY_SUFFIXES:
            pattern = re.compile(rf"^(?P<company>.+?{re.escape(suffix)})(?:\s+(?P<title>.+))?$")
            match = pattern.match(normalized)
            if match is None:
                continue
            company_name = self._clean_text(match.group("company"))
            title = self._clean_text(match.group("title"))
            return company_name, title

        parts = normalized.split(" ")
        if len(parts) >= 2:
            trailing = parts[-1]
            if self._looks_like_resume_title(trailing):
                return self._clean_text(" ".join(parts[:-1])), self._clean_text(trailing)

        if self._looks_like_resume_title(normalized):
            return None, normalized
        return normalized, None

    def _looks_like_resume_title(self, value: str) -> bool:
        lowered = value.lower()
        return any(keyword in lowered for keyword in RESUME_TITLE_KEYWORDS)

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
        description = self._clean_text(payload.get("description"))
        keywords = self._string_list(payload.get("keywords"))
        name = self._clean_text(payload.get("name")) or description or (keywords[0] if keywords else None) or "Experience Pending"
        return {
            "type": self._clean_text(payload.get("type")) or "project",
            "name": name,
            "min_years": self._positive_float_or_none(payload.get("min_years")),
            "description": description,
            "keywords": keywords,
        }

    def _normalize_bonus_experience_item(self, item: Any) -> dict[str, Any]:
        payload = self._as_dict(item)
        description = self._clean_text(payload.get("description"))
        keywords = self._string_list(payload.get("keywords"))
        name = self._clean_text(payload.get("name")) or description or (keywords[0] if keywords else None) or "Experience Pending"
        return {
            "type": self._clean_text(payload.get("type")) or "project",
            "name": name,
            "weight": self._int_or_none(payload.get("weight")),
            "description": description,
            "keywords": keywords,
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
            "skill": "\u6280\u80fd",
            "skills": "\u6280\u80fd",
            "\u6280\u80fd": "\u6280\u80fd",
            "salary": "\u85aa\u8d44",
            "compensation": "\u85aa\u8d44",
            "\u85aa\u8d44": "\u85aa\u8d44",
            "\u7ecf\u9a8c": "\u7ecf\u9a8c",
            "experience": "\u7ecf\u9a8c",
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
        if text.lower() in LLM_PLACEHOLDER_TEXTS:
            return None
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

    def _positive_float_or_none(self, value: Any) -> float | None:
        parsed = self._float_or_none(value)
        if parsed is None or parsed <= 0:
            return None
        return parsed

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
        salary_min = next((ints[index] for index in range(0, len(ints), 2) if ints[index] is not None), None)
        salary_max = next((ints[index] for index in range(1, len(ints), 2) if ints[index] is not None), None)
        if salary_min is None and salary_max is None:
            return None, None
        if salary_min is None:
            salary_min = salary_max
        if salary_max is None:
            salary_max = salary_min
        if salary_min is not None and salary_max is not None and salary_min > salary_max:
            salary_min, salary_max = salary_max, salary_min
        return salary_min, salary_max
