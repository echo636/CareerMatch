from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import sys
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
TEST_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional in bare environments
    def load_dotenv(*_args, **_kwargs):
        return False

from report_manager import resolve_report_paths, write_report_files

BOOTSTRAP_IMPORT_ERROR: Exception | None = None
try:
    from app.bootstrap import build_services
    from app.clients.llm import QwenLLMClient
    from app.core.config import get_settings
    from app.core.logging_utils import configure_logging
except Exception as exc:  # pragma: no cover - depends on local runtime environment
    BOOTSTRAP_IMPORT_ERROR = exc
    build_services = None  # type: ignore[assignment]
    QwenLLMClient = object  # type: ignore[assignment]
    get_settings = None  # type: ignore[assignment]
    configure_logging = None  # type: ignore[assignment]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare the built-in matching algorithm with an LLM rerank over the same uploaded-resume candidate pool."
        )
    )
    parser.add_argument("--resume-id", type=str, default="")
    parser.add_argument("--resume-file", type=str, default="")
    parser.add_argument("--candidate-limit", type=int, default=12)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--force-reparse", action="store_true")
    parser.add_argument("--output", type=str, default="")
    return parser.parse_args()


def now_local() -> datetime:
    return datetime.now().astimezone()


def detect_content_type(file_path: Path) -> str:
    return mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"


def brief_text(text: str | None, limit: int = 160) -> str:
    normalized = " ".join((text or "").split())
    if not normalized:
        return "-"
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3] + "..."


def format_salary(min_value: int | None, max_value: int | None, currency: str | None = None) -> str:
    if min_value is None and max_value is None:
        return "-"
    left = "-" if min_value is None else str(min_value)
    right = "-" if max_value is None else str(max_value)
    suffix = f" {currency}" if currency else ""
    return f"{left}-{right}{suffix}"


def format_values(values: list[str], limit: int = 6) -> str:
    if not values:
        return "-"
    clipped = values[:limit]
    text = ", ".join(clipped)
    if len(values) > limit:
        text += f" ... (+{len(values) - limit})"
    return text


def build_breakdown_dict(breakdown: Any) -> dict[str, float]:
    return {
        "vector_similarity": float(breakdown.vector_similarity),
        "skill_match": float(breakdown.skill_match),
        "experience_match": float(breakdown.experience_match),
        "education_match": float(breakdown.education_match),
        "salary_match": float(breakdown.salary_match),
        "total": float(breakdown.total),
    }


def upload_root_candidates(settings: Any) -> list[Path]:
    candidates = [
        settings.object_storage_root / "resumes",
        settings.object_storage_root,
        BACKEND_DIR / "uploads" / "resumes",
        BACKEND_DIR / "app" / "uploads" / "resumes",
        BACKEND_DIR / "app" / "uploads",
    ]
    existing: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        resolved = path.resolve()
        marker = str(resolved).lower()
        if marker in seen:
            continue
        seen.add(marker)
        if resolved.exists():
            existing.append(resolved)
    return existing


def latest_resume_dir(upload_roots: list[Path]) -> Path | None:
    directories: list[Path] = []
    for root in upload_roots:
        if not root.exists() or not root.is_dir():
            continue
        directories.extend(item for item in root.iterdir() if item.is_dir())
    if not directories:
        return None
    directories.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    return directories[0]


def latest_resume_file(upload_dir: Path) -> Path | None:
    if not upload_dir.exists() or not upload_dir.is_dir():
        return None
    files = [item for item in upload_dir.iterdir() if item.is_file()]
    if not files:
        return None
    files.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    return files[0]


def resolve_resume_selection(settings: Any, requested_resume_id: str, requested_resume_file: str) -> tuple[str, Path]:
    if requested_resume_file:
        file_path = Path(requested_resume_file)
        if not file_path.is_absolute():
            file_path = (PROJECT_DIR / file_path).resolve()
        else:
            file_path = file_path.resolve()
        if not file_path.exists() or not file_path.is_file():
            raise SystemExit(f"resume file does not exist: {file_path}")
        resume_id = requested_resume_id.strip() or file_path.parent.name.strip()
        if not resume_id:
            marker = hashlib.sha1(str(file_path).encode("utf-8")).hexdigest()[:8]
            resume_id = f"resume-compare-{marker}"
        return resume_id, file_path

    upload_roots = upload_root_candidates(settings)
    if not upload_roots:
        raise SystemExit("no upload root found")
    if requested_resume_id.strip():
        resume_id = requested_resume_id.strip()
        for root in upload_roots:
            file_path = latest_resume_file(root / resume_id)
            if file_path is not None:
                return resume_id, file_path
        raise SystemExit(f"resume id not found under uploads: {resume_id}")

    upload_dir = latest_resume_dir(upload_roots)
    if upload_dir is None:
        raise SystemExit("no uploaded resume directory found")
    file_path = latest_resume_file(upload_dir)
    if file_path is None:
        raise SystemExit(f"no resume file found in {upload_dir}")
    return upload_dir.name, file_path


def ensure_resume(services: Any, resume_id: str, file_path: Path, force_reparse: bool) -> tuple[Any, dict[str, Any]]:
    if not force_reparse:
        resume = services.resume_pipeline.get_resume(resume_id)
        if resume is not None:
            return resume, {"status": "persisted", "resume_id": resume_id, "file_path": str(file_path)}

    file_bytes = file_path.read_bytes()
    content_type = detect_content_type(file_path)
    raw_text = services.resume_pipeline.document_parser.extract_text(
        file_bytes=file_bytes,
        file_name=file_path.name,
        content_type=content_type,
    )
    object_key = (Path("resumes") / resume_id / file_path.name).as_posix()
    resume = services.resume_pipeline.process_resume(
        file_name=file_path.name,
        raw_text=raw_text,
        resume_id=resume_id,
        source_content_type=content_type,
        source_object_key=object_key,
    )
    status = "reparsed_from_upload" if force_reparse else "hydrated_from_upload"
    return resume, {"status": status, "resume_id": resume_id, "file_path": str(file_path)}


def build_resume_snapshot(resume: Any, file_path: Path) -> dict[str, Any]:
    return {
        "resume_id": resume.id,
        "name": resume.basic_info.name,
        "current_title": resume.basic_info.current_title,
        "current_company": resume.basic_info.current_company,
        "work_years": resume.basic_info.work_years,
        "first_degree": resume.basic_info.first_degree,
        "expected_salary": {
            "min": resume.expected_salary.min,
            "max": resume.expected_salary.max,
            "currency": resume.expected_salary.currency,
        },
        "skills_sample": resume.skill_names[:10],
        "project_keywords_sample": resume.project_keywords[:10],
        "summary_excerpt": brief_text(resume.summary, 220),
        "upload_file_path": str(file_path),
    }


def collect_candidate_pool(services: Any, resume: Any, candidate_limit: int) -> dict[str, Any]:
    matching = services.matching_service
    desired = max(candidate_limit, 1)
    started_at = perf_counter()

    job_count = len(matching.job_repository.list())
    resume_vector = matching._ensure_resume_vector(resume)
    candidate_skill_index = matching._build_candidate_skill_index(resume)
    candidate_terms = matching._build_candidate_terms(resume)

    recall_size = min(max(matching._dynamic_recall_size(desired, job_count), desired), max(job_count, desired))
    filtered_candidates: list[dict[str, Any]] = []
    filtered_out: list[dict[str, Any]] = []
    recalled_count = 0

    while True:
        recalled = matching.vector_store.query("jobs", resume_vector, recall_size)
        recalled_count = len(recalled)
        filtered_candidates = []
        filtered_out = []

        for rank, candidate in enumerate(recalled, start=1):
            candidate_score = float(candidate["score"])
            job = matching.job_repository.get(str(candidate["id"]))
            if job is None:
                continue

            passed_filters, filter_reason = matching._filter_decision(resume, job)
            if not passed_filters:
                filtered_out.append(
                    {
                        "vector_rank": rank,
                        "job_id": job.id,
                        "job_title": job.title,
                        "company": job.company,
                        "vector_similarity": round(candidate_score, 4),
                        "filter_reason": filter_reason,
                    }
                )
                continue

            breakdown = matching._build_breakdown(
                resume,
                job,
                candidate_score,
                candidate_skill_index,
                candidate_terms,
            )
            matched_skills = [skill for skill in job.skills if matching._normalize_skill(skill) in candidate_skill_index]
            missing_skills = [skill for skill in job.skills if matching._normalize_skill(skill) not in candidate_skill_index]
            filtered_candidates.append(
                {
                    "vector_rank": rank,
                    "job_id": job.id,
                    "job_title": job.title,
                    "company": job.company,
                    "location": job.location,
                    "summary": job.summary,
                    "vector_similarity": round(candidate_score, 4),
                    "breakdown": build_breakdown_dict(breakdown),
                    "matched_skills": matched_skills,
                    "missing_skills": missing_skills,
                    "job": job,
                }
            )

        if len(filtered_candidates) >= desired or recalled_count >= job_count or recall_size >= job_count:
            break
        next_recall = max(recall_size * 2, desired)
        if next_recall == recall_size:
            break
        recall_size = min(next_recall, job_count)

    compared_candidates = filtered_candidates[:desired]
    algorithm_ranked = sorted(
        compared_candidates,
        key=lambda item: (
            -float(item["breakdown"]["total"]),
            -float(item["breakdown"]["vector_similarity"]),
            str(item["job_id"]),
        ),
    )
    duration_ms = round((perf_counter() - started_at) * 1000, 2)
    return {
        "job_count": job_count,
        "recall_size": recall_size,
        "recalled_count": recalled_count,
        "filtered_out_count": len(filtered_out),
        "filtered_candidate_count": len(filtered_candidates),
        "compared_candidate_count": len(compared_candidates),
        "duration_ms": duration_ms,
        "filtered_out": filtered_out,
        "compared_candidates": compared_candidates,
        "algorithm_ranked": algorithm_ranked,
        "algorithm_order": [item["job_id"] for item in algorithm_ranked],
    }


def build_resume_prompt_payload(resume: Any) -> dict[str, Any]:
    latest_work = []
    for item in resume.work_experiences[:3]:
        latest_work.append(
            {
                "company": item.company_name,
                "title": item.title,
                "industry": item.industry,
                "start_date": item.start_date,
                "end_date": item.end_date,
                "tech_stack": list(item.tech_stack or [])[:8],
            }
        )

    latest_projects = []
    for item in resume.projects[:3]:
        latest_projects.append(
            {
                "name": item.name,
                "role": item.role,
                "domain": item.domain,
                "tech_stack": list(item.tech_stack or [])[:8],
                "description": brief_text(item.description, 140),
            }
        )

    return {
        "resume_id": resume.id,
        "name": resume.basic_info.name,
        "current_title": resume.basic_info.current_title,
        "current_company": resume.basic_info.current_company,
        "current_city": resume.basic_info.current_city,
        "work_years": resume.years_experience,
        "first_degree": resume.basic_info.first_degree,
        "expected_salary": {
            "min": resume.expected_salary.min,
            "max": resume.expected_salary.max,
            "currency": resume.expected_salary.currency,
        },
        "skills": resume.skill_names[:18],
        "project_keywords": resume.project_keywords[:18],
        "summary": brief_text(resume.summary, 280),
        "latest_work_experiences": latest_work,
        "latest_projects": latest_projects,
    }


def build_job_prompt_payload(job: Any) -> dict[str, Any]:
    core_experiences = []
    for item in job.experience_requirements.core[:5]:
        core_experiences.append(
            {
                "type": item.type,
                "name": item.name,
                "min_years": item.min_years,
                "keywords": list(item.keywords or [])[:5],
                "description": brief_text(item.description, 100),
            }
        )

    return {
        "job_id": job.id,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "summary": brief_text(job.summary, 220),
        "salary": {
            "min": job.salary_range.min if job.has_salary_reference else None,
            "max": job.salary_range.max if job.has_salary_reference else None,
            "currency": job.salary_range.currency if job.has_salary_reference else None,
        },
        "required_skills": job.hard_requirements[:10],
        "all_skills": job.skills[:14],
        "project_keywords": job.project_keywords[:10],
        "core_experiences": core_experiences,
        "min_total_years": job.experience_requirements.min_total_years,
        "max_total_years": job.experience_requirements.max_total_years,
        "education": {
            "min_degree": job.education_constraints.min_degree,
            "prefer_degrees": list(job.education_constraints.prefer_degrees or [])[:5],
            "required_majors": list(job.education_constraints.required_majors or [])[:5],
            "preferred_majors": list(job.education_constraints.preferred_majors or [])[:5],
        },
        "tags": [tag.name for tag in job.tags[:10]],
    }


def llm_rank_candidates(services: Any, resume: Any, compared_candidates: list[dict[str, Any]]) -> dict[str, Any]:
    llm_client = services.resume_pipeline.llm_client
    if not isinstance(llm_client, QwenLLMClient):
        raise RuntimeError("This script currently supports QwenLLMClient only.")
    chat_json = getattr(llm_client, "_chat_json", None)
    if not callable(chat_json):
        raise RuntimeError("Current llm client does not expose a JSON chat helper.")

    prompt_jobs = [build_job_prompt_payload(item["job"]) for item in compared_candidates]
    prompt_jobs.sort(key=lambda item: str(item["job_id"]))
    candidate_ids = [str(item["job_id"]) for item in compared_candidates]
    candidate_id_set = set(candidate_ids)

    messages = [
        {
            "role": "system",
            "content": (
                "You are a senior recruiting analyst. Rank jobs for a candidate by real hiring fit. "
                "Return JSON only. Do not output markdown."
            ),
        },
        {
            "role": "user",
            "content": (
                "Task: rank the given jobs for the candidate from best fit to worst fit.\n"
                "- The jobs list order is arbitrary and does not imply priority.\n"
                "- You must rank every job_id exactly once.\n"
                "- Consider skills, project and domain experience, years, role direction, education, and salary expectation.\n"
                "- Treat missing information as neutral and do not invent facts.\n"
                "- Return JSON in this shape: "
                '{"ranked_job_ids":["job1","job2"],"assessments":[{"job_id":"job1","fit_score":88,"reason":"...","risk":"..."}],"summary":"..."}\n'
                f"candidate={json.dumps(build_resume_prompt_payload(resume), ensure_ascii=False)}\n"
                f"jobs={json.dumps(prompt_jobs, ensure_ascii=False)}"
            ),
        },
    ]

    started_at = perf_counter()
    payload = chat_json(messages)
    duration_ms = round((perf_counter() - started_at) * 1000, 2)

    raw_ranked_ids = payload.get("ranked_job_ids")
    ranked_ids: list[str] = []
    duplicates_removed: list[str] = []
    missing_ids: list[str] = []
    seen: set[str] = set()
    if isinstance(raw_ranked_ids, list):
        for value in raw_ranked_ids:
            job_id = str(value).strip()
            if not job_id or job_id not in candidate_id_set:
                continue
            if job_id in seen:
                duplicates_removed.append(job_id)
                continue
            seen.add(job_id)
            ranked_ids.append(job_id)
    for job_id in candidate_ids:
        if job_id in seen:
            continue
        missing_ids.append(job_id)
        ranked_ids.append(job_id)

    assessment_index: dict[str, dict[str, Any]] = {}
    if isinstance(payload.get("assessments"), list):
        for item in payload["assessments"]:
            if not isinstance(item, dict):
                continue
            job_id = str(item.get("job_id") or "").strip()
            if not job_id or job_id not in candidate_id_set:
                continue
            assessment_index[job_id] = {
                "fit_score": item.get("fit_score"),
                "reason": brief_text(str(item.get("reason") or ""), 180),
                "risk": brief_text(str(item.get("risk") or ""), 160),
            }

    return {
        "duration_ms": duration_ms,
        "prompt_job_count": len(prompt_jobs),
        "order": ranked_ids,
        "summary": brief_text(str(payload.get("summary") or ""), 260),
        "duplicates_removed": duplicates_removed,
        "missing_ids_appended": missing_ids,
        "assessment_index": assessment_index,
        "raw_payload": payload,
    }


def compute_spearman_metrics(algorithm_order: list[str], llm_order: list[str]) -> dict[str, Any]:
    if set(algorithm_order) != set(llm_order):
        raise ValueError("algorithm and llm orders must contain the same job ids")
    count = len(algorithm_order)
    if count == 0:
        return {"count": 0, "rho": None, "distance": None, "normalized_distance": None, "sum_squared_rank_diff": None}
    if count == 1:
        return {"count": 1, "rho": 1.0, "distance": 0.0, "normalized_distance": 0.0, "sum_squared_rank_diff": 0}

    algorithm_ranks = {job_id: index + 1 for index, job_id in enumerate(algorithm_order)}
    llm_ranks = {job_id: index + 1 for index, job_id in enumerate(llm_order)}
    sum_squared_rank_diff = sum((algorithm_ranks[job_id] - llm_ranks[job_id]) ** 2 for job_id in algorithm_order)
    denominator = count * (count**2 - 1)
    rho = 1 - (6 * sum_squared_rank_diff / denominator)
    return {
        "count": count,
        "rho": round(rho, 6),
        "distance": round(1 - rho, 6),
        "normalized_distance": round((1 - rho) / 2, 6),
        "sum_squared_rank_diff": int(sum_squared_rank_diff),
    }


def build_disagreements(
    compared_candidates: list[dict[str, Any]],
    algorithm_order: list[str],
    llm_order: list[str],
    llm_assessment_index: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    candidate_index = {str(item["job_id"]): item for item in compared_candidates}
    algorithm_ranks = {job_id: index + 1 for index, job_id in enumerate(algorithm_order)}
    llm_ranks = {job_id: index + 1 for index, job_id in enumerate(llm_order)}
    disagreements: list[dict[str, Any]] = []
    for job_id in algorithm_order:
        item = candidate_index[job_id]
        llm_assessment = llm_assessment_index.get(job_id, {})
        disagreements.append(
            {
                "job_id": job_id,
                "job_title": item["job_title"],
                "company": item["company"],
                "algorithm_rank": algorithm_ranks[job_id],
                "llm_rank": llm_ranks[job_id],
                "rank_shift": llm_ranks[job_id] - algorithm_ranks[job_id],
                "algorithm_score": item["breakdown"]["total"],
                "vector_similarity": item["breakdown"]["vector_similarity"],
                "llm_fit_score": llm_assessment.get("fit_score"),
                "llm_reason": llm_assessment.get("reason"),
                "llm_risk": llm_assessment.get("risk"),
            }
        )
    disagreements.sort(key=lambda item: (-abs(int(item["rank_shift"])), int(item["algorithm_rank"]), str(item["job_id"])))
    return disagreements


def render_report(report: dict[str, Any]) -> str:
    snapshot = report["resume_snapshot"]
    pool = report["candidate_pool"]
    metrics = report["metrics"]
    llm_result = report["llm_result"]
    lines: list[str] = []
    lines.append("# Resume Matching Algorithm vs LLM Compare Report")
    lines.append("")
    lines.append(f"- Run At: {report['run_at']}")
    lines.append(f"- Resume Source: {report['resume_source']}")
    lines.append(f"- Resume File: {snapshot['upload_file_path']}")
    lines.append(f"- State DB: {report['settings']['state_db']}")
    lines.append(f"- Upload Root: {report['settings']['upload_root']}")
    lines.append(f"- LLM Provider: {report['settings']['llm_provider']}")
    lines.append(f"- LLM Model: {report['settings']['llm_model']}")
    lines.append(f"- Jobs In Store: {report['settings']['job_count']}")
    lines.append("")
    lines.append("## Resume Snapshot")
    lines.append("")
    lines.append(f"- Resume ID: {snapshot['resume_id']}")
    lines.append(f"- Name: {snapshot['name']}")
    lines.append(f"- Current Title: {snapshot['current_title'] or '-'}")
    lines.append(f"- Current Company: {snapshot['current_company'] or '-'}")
    lines.append(f"- Work Years: {snapshot['work_years'] if snapshot['work_years'] is not None else '-'}")
    lines.append(f"- First Degree: {snapshot['first_degree'] or '-'}")
    lines.append(
        f"- Expected Salary: {format_salary(snapshot['expected_salary']['min'], snapshot['expected_salary']['max'], snapshot['expected_salary']['currency'])}"
    )
    lines.append(f"- Skills: {format_values(snapshot['skills_sample'], limit=10)}")
    lines.append(f"- Project Keywords: {format_values(snapshot['project_keywords_sample'], limit=10)}")
    lines.append(f"- Summary: {snapshot['summary_excerpt']}")
    lines.append("")
    lines.append("## Compare Metrics")
    lines.append("")
    lines.append(f"- Candidate Limit: {report['selection']['candidate_limit']}")
    lines.append(f"- Compared Candidates: {pool['compared_candidate_count']}")
    lines.append(f"- Recall Size: {pool['recall_size']}")
    lines.append(f"- Recalled Count: {pool['recalled_count']}")
    lines.append(f"- Filtered Candidate Count: {pool['filtered_candidate_count']}")
    lines.append(f"- Filtered Out Count: {pool['filtered_out_count']}")
    lines.append(f"- Candidate Pool Build Duration: {pool['duration_ms']} ms")
    lines.append(f"- LLM Ranking Duration: {llm_result['duration_ms']} ms")
    lines.append(f"- Spearman Rho: {metrics['rho']}")
    lines.append(f"- Spearman Distance (1-rho): {metrics['distance']}")
    lines.append(f"- Normalized Distance ((1-rho)/2): {metrics['normalized_distance']}")
    lines.append(f"- Sum Squared Rank Diff: {metrics['sum_squared_rank_diff']}")
    lines.append(f"- Top-{report['selection']['top_k']} Overlap: {report['top_k_overlap']}")
    if llm_result["summary"] != "-":
        lines.append(f"- LLM Summary: {llm_result['summary']}")
    if llm_result["duplicates_removed"]:
        lines.append(f"- LLM Duplicate IDs Removed: {', '.join(llm_result['duplicates_removed'])}")
    if llm_result["missing_ids_appended"]:
        lines.append(f"- LLM Missing IDs Appended: {', '.join(llm_result['missing_ids_appended'])}")
    lines.append("")
    lines.append("## Algorithm Top Results")
    lines.append("")
    for index, item in enumerate(report["algorithm_top_results"], start=1):
        breakdown = item["breakdown"]
        lines.append(
            f"{index}. {item['job_title']} | company={item['company']} | total={breakdown['total']:.4f} | vec={breakdown['vector_similarity']:.4f}"
        )
        lines.append(
            f"   skill={breakdown['skill_match']:.4f}, exp={breakdown['experience_match']:.4f}, edu={breakdown['education_match']:.4f}, salary={breakdown['salary_match']:.4f}"
        )
        lines.append(f"   matched_skills: {format_values(item['matched_skills'], limit=8)}")
        lines.append(f"   missing_skills: {format_values(item['missing_skills'], limit=8)}")
    lines.append("")
    lines.append("## LLM Top Results")
    lines.append("")
    for index, item in enumerate(report["llm_top_results"], start=1):
        lines.append(f"{index}. {item['job_title']} | company={item['company']} | llm_fit_score={item.get('llm_fit_score')}")
        lines.append(f"   reason: {item.get('llm_reason') or '-'}")
        lines.append(f"   risk: {item.get('llm_risk') or '-'}")
        lines.append(
            f"   algorithm_rank={item['algorithm_rank']}, algorithm_score={item['algorithm_score']:.4f}, vector_similarity={item['vector_similarity']:.4f}"
        )
    lines.append("")
    lines.append("## Largest Rank Gaps")
    lines.append("")
    for item in report["disagreements"][: max(report["selection"]["top_k"], 8)]:
        lines.append(
            f"- {item['job_title']} | company={item['company']} | algorithm_rank={item['algorithm_rank']} | llm_rank={item['llm_rank']} | shift={item['rank_shift']:+d} | algorithm_score={item['algorithm_score']:.4f} | llm_fit_score={item.get('llm_fit_score')}"
        )
        lines.append(f"  llm_reason: {item.get('llm_reason') or '-'}")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    if args.candidate_limit <= 0:
        raise SystemExit("--candidate-limit must be greater than 0")
    if args.top_k <= 0:
        raise SystemExit("--top-k must be greater than 0")
    if BOOTSTRAP_IMPORT_ERROR is not None:
        raise SystemExit(
            "failed to import backend runtime dependencies. "
            f"current_python={sys.version.split()[0]}. "
            "Run this script with a Python 3.11/3.12 environment that has the backend dependencies installed. "
            f"original_error={BOOTSTRAP_IMPORT_ERROR!r}"
        )

    load_dotenv(BACKEND_DIR / ".env")
    get_settings.cache_clear()
    settings = get_settings()
    configure_logging(settings.app_log_dir, settings.app_log_level)
    services = build_services(settings)

    resume_id, file_path = resolve_resume_selection(settings, args.resume_id, args.resume_file)
    resume, status = ensure_resume(services, resume_id, file_path, bool(args.force_reparse))
    candidate_pool = collect_candidate_pool(services, resume, args.candidate_limit)
    if candidate_pool["compared_candidate_count"] == 0:
        raise SystemExit("no candidates available for comparison after recall and filtering")

    llm_result = llm_rank_candidates(services, resume, candidate_pool["compared_candidates"])
    metrics = compute_spearman_metrics(candidate_pool["algorithm_order"], llm_result["order"])
    disagreements = build_disagreements(
        candidate_pool["compared_candidates"],
        candidate_pool["algorithm_order"],
        llm_result["order"],
        llm_result["assessment_index"],
    )

    disagreement_index = {item["job_id"]: item for item in disagreements}
    top_k_overlap = len(set(candidate_pool["algorithm_order"][: args.top_k]) & set(llm_result["order"][: args.top_k]))
    algorithm_top_results = candidate_pool["algorithm_ranked"][: args.top_k]
    llm_top_results = [disagreement_index[job_id] for job_id in llm_result["order"][: args.top_k] if job_id in disagreement_index]

    started_at = now_local()
    report_paths = resolve_report_paths(
        category="resume_algorithm_llm_compare",
        output_arg=args.output,
        started_at=started_at,
        default_stem="resume_algorithm_llm_compare",
    )

    upload_roots = upload_root_candidates(settings)
    report: dict[str, Any] = {
        "run_at": started_at.isoformat(timespec="seconds"),
        "settings": {
            "state_db": str(settings.app_state_db_path),
            "upload_root": str(upload_roots[0]) if upload_roots else str(settings.object_storage_root),
            "llm_provider": settings.llm_provider,
            "llm_model": settings.qwen_llm_model,
            "job_count": len(services.matching_service.job_repository.list()),
        },
        "selection": {
            "resume_id": resume.id,
            "resume_file": str(file_path),
            "candidate_limit": args.candidate_limit,
            "top_k": args.top_k,
            "force_reparse": bool(args.force_reparse),
        },
        "resume_source": status.get("status") if status else "unknown",
        "resume_snapshot": build_resume_snapshot(resume, file_path),
        "candidate_pool": {
            "job_count": candidate_pool["job_count"],
            "recall_size": candidate_pool["recall_size"],
            "recalled_count": candidate_pool["recalled_count"],
            "filtered_out_count": candidate_pool["filtered_out_count"],
            "filtered_candidate_count": candidate_pool["filtered_candidate_count"],
            "compared_candidate_count": candidate_pool["compared_candidate_count"],
            "duration_ms": candidate_pool["duration_ms"],
            "filtered_out": candidate_pool["filtered_out"],
            "compared_candidates": [
                {
                    "vector_rank": item["vector_rank"],
                    "job_id": item["job_id"],
                    "job_title": item["job_title"],
                    "company": item["company"],
                    "location": item["location"],
                    "summary": brief_text(item["summary"], 180),
                    "vector_similarity": item["vector_similarity"],
                    "breakdown": item["breakdown"],
                    "matched_skills": item["matched_skills"],
                    "missing_skills": item["missing_skills"],
                }
                for item in candidate_pool["compared_candidates"]
            ],
            "algorithm_order": candidate_pool["algorithm_order"],
        },
        "llm_result": {
            "duration_ms": llm_result["duration_ms"],
            "prompt_job_count": llm_result["prompt_job_count"],
            "order": llm_result["order"],
            "summary": llm_result["summary"],
            "duplicates_removed": llm_result["duplicates_removed"],
            "missing_ids_appended": llm_result["missing_ids_appended"],
            "assessment_index": llm_result["assessment_index"],
            "raw_payload": llm_result["raw_payload"],
        },
        "metrics": metrics,
        "top_k_overlap": top_k_overlap,
        "algorithm_top_results": [
            {
                "job_id": item["job_id"],
                "job_title": item["job_title"],
                "company": item["company"],
                "breakdown": item["breakdown"],
                "matched_skills": item["matched_skills"],
                "missing_skills": item["missing_skills"],
            }
            for item in algorithm_top_results
        ],
        "llm_top_results": llm_top_results,
        "disagreements": disagreements,
    }

    report_text = render_report(report)
    write_report_files(report_paths, report_text, report)
    print(report_text)
    print(f"[report] markdown={report_paths.markdown_path}")
    print(f"[report] json={report_paths.json_path}")
    print(f"[report] latest_markdown={report_paths.latest_markdown_path}")
    print(f"[report] latest_json={report_paths.latest_json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
