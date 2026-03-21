from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
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
    "提示词工程",
]

CURRENT_YEAR = datetime.now().year


class MockLLMClient:
    def extract_resume(self, raw_text: str, file_name: str, resume_id: str) -> dict[str, Any]:
        skills = self._extract_terms(raw_text, KNOWN_SKILLS) or ["Python", "LLM"]
        projects = self._extract_terms(raw_text, KNOWN_PROJECT_TERMS) or ["简历解析", "岗位匹配"]
        years = self._extract_years(raw_text, default=5)
        salary_min, salary_max = self._extract_salary(raw_text, default_min=25000, default_max=35000)
        candidate_name = Path(file_name).stem.replace("_", " ") or "待命名候选人"
        summary = raw_text.strip()[:200] or "候选人简历摘要待补充。"

        return {
            "id": resume_id,
            "is_resume": True,
            "basic_info": {
                "name": candidate_name,
                "work_years": years,
                "current_title": self._infer_resume_title(raw_text),
                "summary": summary,
                "self_evaluation": summary,
            },
            "educations": [],
            "work_experiences": [
                {
                    "company_name": "待补充公司",
                    "title": self._infer_resume_title(raw_text),
                    "responsibilities": [
                        f"负责{projects[0]}相关方案设计与交付。",
                    ],
                    "achievements": [
                        "具备从需求抽象到系统实现的落地经验。",
                    ],
                    "tech_stack": skills[:5],
                }
            ],
            "projects": [
                {
                    "name": project,
                    "role": "核心开发",
                    "domain": "智能招聘",
                    "description": f"围绕{project}场景完成产品或系统落地。",
                    "responsibilities": [f"负责{project}相关模块设计与开发。"],
                    "achievements": [f"形成{project}方向的可复用经验。"],
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
                {"name": "智能招聘", "category": "domain"},
            ],
            "expected_salary": {
                "min": salary_min,
                "max": salary_max,
                "currency": "CNY",
            },
        }

    def extract_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        raw_text = payload.get("summary") or payload.get("raw_text") or payload.get("description") or ""
        structured_basic_info = payload.get("basic_info") or {}
        structured_skills = payload.get("skill_requirements") or {}
        structured_experience = payload.get("experience_requirements") or {}
        structured_education = payload.get("education_constraints") or {}
        structured_tags = payload.get("tags") or []

        skills = payload.get("skills") or self._extract_terms(raw_text, KNOWN_SKILLS) or ["Python"]
        projects = payload.get("project_keywords") or self._extract_terms(raw_text, KNOWN_PROJECT_TERMS) or ["推荐系统"]
        experience_years = int(payload.get("experience_years") or self._extract_years(raw_text, default=3))
        salary = payload.get("salary_range") or {}

        required_names = self._normalize_skill_names(
            structured_skills.get("required"),
            payload.get("hard_requirements") or skills[:2],
        )
        required_skills = [
            {
                "name": item.get("name") if isinstance(item, dict) else str(item),
                "level": item.get("level") if isinstance(item, dict) else None,
                "min_years": item.get("min_years") if isinstance(item, dict) else None,
                "description": item.get("description") if isinstance(item, dict) else None,
            }
            for item in (structured_skills.get("required") or [{"name": name} for name in required_names])
        ]
        optional_groups = structured_skills.get("optional_groups") or self._build_optional_skill_groups(skills, required_names)
        bonus_skills = structured_skills.get("bonus") or self._build_bonus_skills(skills, required_names)
        core_experiences = structured_experience.get("core") or [
            {
                "type": "project",
                "name": project,
                "min_years": max(experience_years - 1, 1),
                "keywords": [project],
            }
            for project in projects[:2]
        ]
        bonus_experiences = structured_experience.get("bonus") or [
            {
                "type": "project",
                "name": project,
                "weight": 5,
                "keywords": [project],
            }
            for project in projects[2:4]
        ]
        tags = structured_tags or self._build_job_tags(skills, projects)

        basic_info = {
            "title": structured_basic_info.get("title") or payload.get("title", "未命名岗位"),
            "department": structured_basic_info.get("department") or payload.get("department"),
            "location": structured_basic_info.get("location") or payload.get("location", "远程"),
            "job_type": structured_basic_info.get("job_type") or payload.get("job_type", "fulltime"),
            "salary_negotiable": structured_basic_info.get("salary_negotiable"),
            "salary_min": structured_basic_info.get("salary_min", salary.get("min", payload.get("salary_min", 20000))),
            "salary_max": structured_basic_info.get("salary_max", salary.get("max", payload.get("salary_max", 30000))),
            "salary_months_min": structured_basic_info.get("salary_months_min"),
            "salary_months_max": structured_basic_info.get("salary_months_max"),
            "intern_salary_amount": structured_basic_info.get("intern_salary_amount"),
            "intern_salary_unit": structured_basic_info.get("intern_salary_unit"),
            "currency": structured_basic_info.get("currency", salary.get("currency", payload.get("salary_currency", "CNY"))),
            "summary": structured_basic_info.get("summary") or raw_text or "岗位说明待补充。",
            "responsibilities": structured_basic_info.get("responsibilities") or payload.get("responsibilities") or [],
            "highlights": structured_basic_info.get("highlights") or payload.get("highlights") or [],
        }

        return {
            "id": payload.get("id") or payload.get("job_id") or f"job-{abs(hash(raw_text or basic_info['title'])) % 100000}",
            "company": payload.get("company", "待补充公司"),
            "basic_info": basic_info,
            "skill_requirements": {
                "required": required_skills,
                "optional_groups": optional_groups,
                "bonus": bonus_skills,
            },
            "experience_requirements": {
                "core": core_experiences,
                "bonus": bonus_experiences,
                "min_total_years": structured_experience.get("min_total_years", experience_years),
                "max_total_years": structured_experience.get("max_total_years"),
            },
            "education_constraints": {
                "min_degree": structured_education.get("min_degree"),
                "prefer_degrees": structured_education.get("prefer_degrees") or [],
                "required_majors": structured_education.get("required_majors") or [],
                "preferred_majors": structured_education.get("preferred_majors") or [],
                "languages": structured_education.get("languages") or [],
                "certifications": structured_education.get("certifications") or [],
                "age_range": structured_education.get("age_range"),
                "other": structured_education.get("other") or [],
            },
            "tags": tags,
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

    def _infer_resume_title(self, raw_text: str) -> str:
        lowered = raw_text.lower()
        if "agent" in lowered or "llm" in lowered:
            return "AI 应用工程师"
        if "flask" in lowered or "fastapi" in lowered:
            return "后端工程师"
        return "候选人"

    def _normalize_skill_names(self, structured_required: Any, fallback: list[str]) -> list[str]:
        if structured_required:
            values = []
            for item in structured_required:
                if isinstance(item, dict):
                    values.append(str(item.get("name", "")).strip())
                else:
                    values.append(str(item).strip())
            normalized = [value for value in values if value]
            if normalized:
                return normalized
        return [value for value in fallback if value]

    def _build_optional_skill_groups(self, skills: list[str], required_names: list[str]) -> list[dict[str, Any]]:
        optional_skills = [skill for skill in skills if skill not in required_names]
        if len(optional_skills) < 2:
            return []
        return [
            {
                "group_name": "相关技术栈",
                "description": "满足其中部分技术会提升岗位适配度。",
                "min_required": 1,
                "skills": [{"name": skill} for skill in optional_skills[:3]],
            }
        ]

    def _build_bonus_skills(self, skills: list[str], required_names: list[str]) -> list[dict[str, Any]]:
        return [
            {
                "name": skill,
                "weight": max(3, 8 - index),
            }
            for index, skill in enumerate(skills)
            if skill not in required_names
        ][:3]

    def _build_job_tags(self, skills: list[str], projects: list[str]) -> list[dict[str, Any]]:
        return [
            *[{"name": skill, "category": "tech", "weight": 5} for skill in skills[:4]],
            *[{"name": project, "category": "project", "weight": 4} for project in projects[:3]],
            {"name": "智能招聘", "category": "domain", "weight": 5},
        ]

