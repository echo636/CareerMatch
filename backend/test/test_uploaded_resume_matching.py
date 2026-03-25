from __future__ import annotations

import argparse
import json
import mimetypes
import sys
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
TEST_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional in bare environments
    def load_dotenv(*_args, **_kwargs):
        return False

from app.bootstrap import build_services
from app.core.config import get_settings
from app.core.logging_utils import configure_logging
from report_manager import resolve_report_paths, write_report_files


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Test matching flow for uploaded resumes. The script scans backend/uploads/resumes, "
            "reuses persisted resumes from SQLite when possible, and writes managed reports under backend/test/reports/resume_matching by default."
        )
    )
    parser.add_argument(
        "--resume-id",
        dest="resume_ids",
        action="append",
        default=[],
        help="Specific resume id to test. Repeat this flag to test multiple resumes.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of final matches to show for each resume. Default: 5.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limit upload directories when --resume-id is not provided. 0 means no limit.",
    )
    parser.add_argument(
        "--hydrate-missing",
        action="store_true",
        help=(
            "If a resume folder exists in uploads but the structured resume is missing from SQLite, "
            "re-parse the source file and persist the resume before matching."
        ),
    )
    parser.add_argument(
        "--output",
        type=str,
        default="",
        help="Optional custom markdown report filename. Relative paths are resolved under backend/test; default output goes to backend/test/reports/resume_matching/.",
    )
    return parser.parse_args()


def now_local() -> datetime:
    return datetime.now().astimezone()


def detect_content_type(file_path: Path) -> str:
    return mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"


def latest_resume_file(upload_dir: Path) -> Path | None:
    if not upload_dir.exists() or not upload_dir.is_dir():
        return None
    files = [item for item in upload_dir.iterdir() if item.is_file()]
    if not files:
        return None
    files.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    return files[0]


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


def brief_text(text: str, limit: int = 120) -> str:
    normalized = " ".join((text or "").split())
    if len(normalized) <= limit:
        return normalized or "-"
    return normalized[: limit - 3] + "..."


def build_breakdown_dict(breakdown: Any) -> dict[str, float]:
    return {
        "vector_similarity": float(breakdown.vector_similarity),
        "skill_match": float(breakdown.skill_match),
        "experience_match": float(breakdown.experience_match),
        "education_match": float(breakdown.education_match),
        "salary_match": float(breakdown.salary_match),
        "total": float(breakdown.total),
    }


def select_resume_ids(upload_root: Path, requested_ids: list[str], limit: int) -> list[str]:
    if requested_ids:
        return requested_ids

    directories = [item for item in upload_root.iterdir() if item.is_dir()] if upload_root.exists() else []
    directories.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    selected = [item.name for item in directories]
    if limit > 0:
        selected = selected[:limit]
    return selected


def ensure_resume(services: Any, settings: Any, resume_id: str, hydrate_missing: bool) -> tuple[Any | None, dict[str, Any] | None]:
    resume = services.resume_pipeline.get_resume(resume_id)
    upload_dir = settings.object_storage_root / "resumes" / resume_id
    file_path = latest_resume_file(upload_dir)

    if resume is not None:
        return resume, {
            "status": "persisted",
            "resume_id": resume_id,
            "file_path": str(file_path) if file_path else None,
        }

    if not hydrate_missing:
        return None, {
            "status": "skipped",
            "resume_id": resume_id,
            "reason": "resume_not_found_in_sqlite",
            "file_path": str(file_path) if file_path else None,
            "hint": "Run with --hydrate-missing to rebuild this resume from uploads.",
        }

    if file_path is None:
        return None, {
            "status": "skipped",
            "resume_id": resume_id,
            "reason": "resume_file_missing",
            "file_path": None,
            "hint": "No file found under backend/uploads/resumes/<resume_id>.",
        }

    try:
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
        return resume, {
            "status": "hydrated_from_upload",
            "resume_id": resume_id,
            "file_path": str(file_path),
        }
    except Exception as exc:  # pragma: no cover - depends on file/provider state
        return None, {
            "status": "error",
            "resume_id": resume_id,
            "reason": "hydrate_failed",
            "file_path": str(file_path),
            "error": repr(exc),
        }


def trace_matching(services: Any, resume: Any, top_k: int) -> dict[str, Any]:
    matching = services.matching_service
    started_at = perf_counter()

    resume_vector = matching._ensure_resume_vector(resume)
    recall_size = max(top_k * 3, top_k)
    recalled = matching.vector_store.query("jobs", resume_vector, recall_size)
    candidate_skill_index = matching._build_candidate_skill_index(resume)
    candidate_terms = matching._build_candidate_terms(resume)

    filtered_out = 0
    traced_candidates: list[dict[str, Any]] = []
    traced_matches: list[dict[str, Any]] = []

    for rank, candidate in enumerate(recalled, start=1):
        candidate_score = float(candidate["score"])
        job = matching.job_repository.get(str(candidate["id"]))
        if job is None:
            traced_candidates.append(
                {
                    "rank": rank,
                    "job_id": str(candidate["id"]),
                    "job_title": None,
                    "company": None,
                    "status": "job_missing",
                    "filter_reason": None,
                    "vector_similarity": round(candidate_score, 4),
                    "breakdown": None,
                    "matched_skills": [],
                    "missing_skills": [],
                    "reasoning": None,
                }
            )
            continue

        passed_filters, filter_reason = matching._filter_decision(resume, job)
        if not passed_filters:
            filtered_out += 1
            traced_candidates.append(
                {
                    "rank": rank,
                    "job_id": job.id,
                    "job_title": job.title,
                    "company": job.company,
                    "status": "filtered",
                    "filter_reason": filter_reason,
                    "vector_similarity": round(candidate_score, 4),
                    "breakdown": None,
                    "matched_skills": [],
                    "missing_skills": [],
                    "reasoning": None,
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
        matched_skills = [skill for skill in job.skills if skill.lower() in candidate_skill_index]
        missing_skills = [skill for skill in job.skills if skill.lower() not in candidate_skill_index]
        reasoning = matching._build_reasoning(job, matched_skills, missing_skills, breakdown)
        breakdown_dict = build_breakdown_dict(breakdown)
        traced_item = {
            "rank": rank,
            "job_id": job.id,
            "job_title": job.title,
            "company": job.company,
            "status": "matched",
            "filter_reason": filter_reason,
            "vector_similarity": round(candidate_score, 4),
            "breakdown": breakdown_dict,
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
            "reasoning": reasoning,
        }
        traced_candidates.append(traced_item)
        traced_matches.append(traced_item)

    traced_matches.sort(key=lambda item: item["breakdown"]["total"], reverse=True)
    top_results = traced_matches[:top_k]
    public_results = matching.recommend(resume.id, top_k)
    public_ids = [item.job.id for item in public_results]
    traced_ids = [item["job_id"] for item in top_results]
    duration_ms = round((perf_counter() - started_at) * 1000, 2)

    return {
        "recall_size": recall_size,
        "recalled_count": len(recalled),
        "filtered_out": filtered_out,
        "matched_count": len(traced_matches),
        "returned_count": len(top_results),
        "duration_ms": duration_ms,
        "public_result_ids": public_ids,
        "traced_result_ids": traced_ids,
        "public_consistent": public_ids == traced_ids,
        "candidates": traced_candidates,
        "top_results": top_results,
    }


def build_resume_snapshot(resume: Any, file_path: str | None) -> dict[str, Any]:
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
        "skill_count": len(resume.skills),
        "project_count": len(resume.projects),
        "work_experience_count": len(resume.work_experiences),
        "skills_sample": resume.skill_names[:8],
        "project_keywords_sample": resume.project_keywords[:8],
        "summary_excerpt": brief_text(resume.summary, 160),
        "source_file_name": resume.source_file_name,
        "source_object_key": resume.source_object_key,
        "upload_file_path": file_path,
    }


def render_report(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Uploaded Resume Matching Test Report")
    lines.append("")
    lines.append(f"- Run At: {report['run_at']}")
    lines.append(f"- State DB: {report['settings']['state_db']}")
    lines.append(f"- Upload Root: {report['settings']['upload_root']}")
    lines.append(f"- LLM Provider: {report['settings']['llm_provider']}")
    lines.append(f"- Embedding Provider: {report['settings']['embedding_provider']}")
    lines.append(f"- Jobs In Store: {report['settings']['job_count']}")
    lines.append(f"- Persisted Resumes In Store: {report['settings']['persisted_resume_count']}")
    lines.append(f"- Selected Resume IDs: {', '.join(report['selection']['selected_resume_ids']) or '-'}")
    lines.append(f"- Processed Count: {len(report['processed'])}")
    lines.append(f"- Skipped Count: {len(report['skipped'])}")
    lines.append("")

    if report["skipped"]:
        lines.append("## Skipped Resume IDs")
        lines.append("")
        for item in report["skipped"]:
            reason = item.get("reason") or item.get("status")
            lines.append(f"- {item['resume_id']}: {reason}")
            if item.get("hint"):
                lines.append(f"  hint: {item['hint']}")
            if item.get("file_path"):
                lines.append(f"  file: {item['file_path']}")
            if item.get("error"):
                lines.append(f"  error: {item['error']}")
        lines.append("")

    for item in report["processed"]:
        snapshot = item["resume_snapshot"]
        process = item["matching_process"]
        lines.append(f"## Resume {snapshot['resume_id']}")
        lines.append("")
        lines.append(f"- Source: {item['resume_source']}")
        lines.append(f"- File: {snapshot['upload_file_path'] or '-'}")
        lines.append(f"- Name: {snapshot['name']}")
        lines.append(f"- Current Title: {snapshot['current_title'] or '-'}")
        lines.append(f"- Work Years: {snapshot['work_years'] if snapshot['work_years'] is not None else '-'}")
        lines.append(f"- First Degree: {snapshot['first_degree'] or '-'}")
        lines.append(
            f"- Expected Salary: {format_salary(snapshot['expected_salary']['min'], snapshot['expected_salary']['max'], snapshot['expected_salary']['currency'])}"
        )
        lines.append(f"- Skill Sample: {format_values(snapshot['skills_sample'], limit=8)}")
        lines.append(f"- Project Keyword Sample: {format_values(snapshot['project_keywords_sample'], limit=8)}")
        lines.append(f"- Summary Excerpt: {snapshot['summary_excerpt']}")
        lines.append("")
        lines.append("### Matching Summary")
        lines.append("")
        lines.append(f"- Recall Size: {process['recall_size']}")
        lines.append(f"- Recalled Candidates: {process['recalled_count']}")
        lines.append(f"- Filtered Out: {process['filtered_out']}")
        lines.append(f"- Matched Before Top-K: {process['matched_count']}")
        lines.append(f"- Returned Top-K: {process['returned_count']}")
        lines.append(f"- Duration: {process['duration_ms']} ms")
        lines.append(f"- Public Recommend Consistent With Trace: {process['public_consistent']}")
        lines.append("")
        lines.append("### Candidate Trace")
        lines.append("")
        if not process["candidates"]:
            lines.append("- No recalled candidates.")
        else:
            for candidate in process["candidates"]:
                line = (
                    f"{candidate['rank']:02d}. [{candidate['status']}] "
                    f"{candidate['job_title'] or candidate['job_id']}"
                    f" | company={candidate['company'] or '-'}"
                    f" | vec={candidate['vector_similarity']:.4f}"
                )
                if candidate["breakdown"]:
                    breakdown = candidate["breakdown"]
                    line += (
                        f" | total={breakdown['total']:.4f}"
                        f" | skill={breakdown['skill_match']:.4f}"
                        f" | exp={breakdown['experience_match']:.4f}"
                        f" | edu={breakdown['education_match']:.4f}"
                        f" | salary={breakdown['salary_match']:.4f}"
                    )
                if candidate.get("filter_reason"):
                    line += f" | reason={candidate['filter_reason']}"
                lines.append(line)
                if candidate["status"] == "matched":
                    lines.append(f"    matched_skills: {format_values(candidate['matched_skills'])}")
                    lines.append(f"    missing_skills: {format_values(candidate['missing_skills'])}")
        lines.append("")
        lines.append("### Presented Top Results")
        lines.append("")
        if not process["top_results"]:
            lines.append("- No final matches returned.")
        else:
            for index, result in enumerate(process["top_results"], start=1):
                breakdown = result["breakdown"]
                lines.append(
                    f"{index}. {result['job_title']} | company={result['company']} | total={breakdown['total']:.4f}"
                )
                lines.append(
                    f"   vector={breakdown['vector_similarity']:.4f}, skill={breakdown['skill_match']:.4f}, "
                    f"exp={breakdown['experience_match']:.4f}, edu={breakdown['education_match']:.4f}, "
                    f"salary={breakdown['salary_match']:.4f}"
                )
                lines.append(f"   matched_skills: {format_values(result['matched_skills'], limit=8)}")
                lines.append(f"   missing_skills: {format_values(result['missing_skills'], limit=8)}")
                lines.append(f"   reasoning: {result['reasoning']}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    if args.top_k <= 0:
        raise SystemExit("--top-k must be greater than 0")
    if args.limit < 0:
        raise SystemExit("--limit must be greater than or equal to 0")

    load_dotenv(BACKEND_DIR / ".env")
    get_settings.cache_clear()
    settings = get_settings()
    configure_logging(settings.app_log_dir, settings.app_log_level)
    services = build_services(settings)

    upload_root = settings.object_storage_root / "resumes"
    selected_resume_ids = select_resume_ids(upload_root, args.resume_ids, args.limit)
    started_at = now_local()
    report_paths = resolve_report_paths(
        category="resume_matching",
        output_arg=args.output,
        started_at=started_at,
        default_stem="matching_report",
    )

    report: dict[str, Any] = {
        "run_at": started_at.isoformat(timespec="seconds"),
        "settings": {
            "state_db": str(settings.app_state_db_path),
            "upload_root": str(upload_root),
            "llm_provider": settings.llm_provider,
            "embedding_provider": settings.embedding_provider,
            "job_count": len(services.matching_service.job_repository.list()),
            "persisted_resume_count": len(services.resume_pipeline.repository.list()),
        },
        "selection": {
            "selected_resume_ids": selected_resume_ids,
            "hydrate_missing": bool(args.hydrate_missing),
            "top_k": args.top_k,
            "limit": args.limit,
        },
        "processed": [],
        "skipped": [],
    }

    for resume_id in selected_resume_ids:
        resume, status = ensure_resume(services, settings, resume_id, args.hydrate_missing)
        if resume is None:
            report["skipped"].append(status or {"resume_id": resume_id, "reason": "unknown"})
            continue

        snapshot = build_resume_snapshot(resume, status.get("file_path") if status else None)
        matching_process = trace_matching(services, resume, args.top_k)
        report["processed"].append(
            {
                "resume_id": resume.id,
                "resume_source": status.get("status") if status else "persisted",
                "resume_snapshot": snapshot,
                "matching_process": matching_process,
            }
        )

    report_text = render_report(report)
    write_report_files(report_paths, report_text, report)

    print(report_text)
    print(f"[report] markdown={report_paths.markdown_path}")
    print(f"[report] json={report_paths.json_path}")
    print(f"[report] latest_markdown={report_paths.latest_markdown_path}")
    print(f"[report] latest_json={report_paths.latest_json_path}")

    return 0 if report["processed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
