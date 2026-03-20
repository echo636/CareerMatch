from __future__ import annotations

import re
from typing import Any

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
    "简历解析",
    "岗位匹配",
    "语义检索",
    "评分系统",
    "推荐系统",
    "数据入库",
    "服务编排",
    "Gap 分析",
    "Agent",
    "向量检索",
]


class MockLLMClient:
    def extract_resume(self, raw_text: str, file_name: str, resume_id: str) -> dict[str, Any]:
        skills = self._extract_terms(raw_text, KNOWN_SKILLS)
        projects = self._extract_terms(raw_text, KNOWN_PROJECT_TERMS)
        years = self._extract_years(raw_text, default=5)
        salary_min, salary_max = self._extract_salary(raw_text, default_min=25000, default_max=35000)

        return {
            "id": resume_id,
            "candidate_name": file_name.replace(".pdf", "").replace(".docx", "").replace("_", " "),
            "summary": raw_text.strip()[:200] or "候选人简历摘要待补充。",
            "skills": skills or ["Python", "LLM"],
            "project_keywords": projects or ["简历解析", "岗位匹配"],
            "years_experience": years,
            "salary_min": salary_min,
            "salary_max": salary_max,
        }

    def extract_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        raw_text = payload.get("summary") or payload.get("raw_text") or ""
        skills = payload.get("skills") or self._extract_terms(raw_text, KNOWN_SKILLS)
        projects = payload.get("project_keywords") or self._extract_terms(raw_text, KNOWN_PROJECT_TERMS)
        experience_years = int(payload.get("experience_years") or self._extract_years(raw_text, default=3))
        salary = payload.get("salary_range") or {}

        return {
            "id": payload.get("id") or payload.get("job_id") or f"job-{abs(hash(raw_text)) % 100000}",
            "title": payload.get("title", "未命名岗位"),
            "company": payload.get("company", "待补充公司"),
            "location": payload.get("location", "远程"),
            "summary": raw_text or payload.get("description", "岗位说明待补充。"),
            "skills": skills or ["Python"],
            "project_keywords": projects or ["推荐系统"],
            "hard_requirements": payload.get("hard_requirements") or skills[:2],
            "salary_min": int(salary.get("min", payload.get("salary_min", 20000))),
            "salary_max": int(salary.get("max", payload.get("salary_max", 30000))),
            "salary_currency": salary.get("currency", payload.get("salary_currency", "CNY")),
            "experience_years": experience_years,
        }

    def generate_gap_insights(
        self,
        missing_skills: list[str],
        salary_gap: int,
        experience_gap_years: int,
    ) -> list[GapInsight]:
        return [
            GapInsight(
                dimension="技能",
                current_state="已具备项目落地的基础能力。",
                target_state=f"补齐核心差距技能：{' / '.join(missing_skills[:3]) or '暂无明显缺口'}。",
                suggestion="优先围绕岗位匹配、向量检索和数据调度补一条可量化案例。",
            ),
            GapInsight(
                dimension="薪资",
                current_state="当前期望与目标岗位存在一定差距。" if salary_gap > 0 else "当前期望与目标岗位基本重合。",
                target_state=f"将项目成果量化后争取 {salary_gap} 元以内的谈薪空间。",
                suggestion="补充匹配准确率、召回率和业务转化指标。",
            ),
            GapInsight(
                dimension="经验",
                current_state="现有经验已覆盖部分核心场景。",
                target_state=f"再补 {experience_gap_years} 年等价复杂度的系统设计与数据链路经验。",
                suggestion="围绕批量导入、异步任务和评估回放补一条完整工程案例。",
            ),
        ]

    def _extract_terms(self, raw_text: str, dictionary: list[str]) -> list[str]:
        normalized = raw_text.lower()
        return [term for term in dictionary if term.lower() in normalized]

    def _extract_years(self, raw_text: str, default: int) -> int:
        match = re.search(r"(\d+)\s*(?:年|years?)", raw_text, re.IGNORECASE)
        return int(match.group(1)) if match else default

    def _extract_salary(self, raw_text: str, default_min: int, default_max: int) -> tuple[int, int]:
        matches = re.findall(r"(\d{4,5})", raw_text)
        if len(matches) >= 2:
            values = sorted(int(item) for item in matches[:2])
            return values[0], values[1]
        return default_min, default_max
