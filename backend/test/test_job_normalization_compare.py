from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
TEST_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    def load_dotenv(*_args, **_kwargs):
        return False

load_dotenv(BASE_DIR / ".env")

from app.bootstrap import _build_embedding_client, _build_llm_client
from app.clients.vector_store import InMemoryVectorStore
from app.core.config import get_settings
from app.core.logging_utils import configure_logging
from app.domain.models import serialize
from app.job_enrichment import build_job_context_text
from app.job_seed_loader import load_job_seed_records
from app.repositories.in_memory import JobRepository
from app.services.job_pipeline import JobPipelineService
from report_manager import resolve_report_paths, write_report_files


FIELD_COMPARISONS: list[tuple[list[str], str]] = [
    (["department", "basic_info.department"], "basicInfo.department"),
    (["location", "basic_info.location"], "basicInfo.location"),
    (["job_type", "basic_info.job_type"], "basicInfo.jobType"),
    (["salary_negotiable", "basic_info.salary_negotiable"], "basicInfo.salaryNegotiable"),
    (["salary_min", "basic_info.salary_min", "salary_range.min"], "basicInfo.salaryMin"),
    (["salary_max", "basic_info.salary_max", "salary_range.max"], "basicInfo.salaryMax"),
    (["salary_months_min", "basic_info.salary_months_min"], "basicInfo.salaryMonthsMin"),
    (["salary_months_max", "basic_info.salary_months_max"], "basicInfo.salaryMonthsMax"),
    (["intern_salary_amount", "basic_info.intern_salary_amount"], "basicInfo.internSalaryAmount"),
    (["intern_salary_unit", "basic_info.intern_salary_unit"], "basicInfo.internSalaryUnit"),
    (["responsibilities", "basic_info.responsibilities"], "basicInfo.responsibilities"),
    (["highlights", "basic_info.highlights"], "basicInfo.highlights"),
    (["skill_requirements.required"], "skillRequirements.required"),
    (["skill_requirements.bonus"], "skillRequirements.bonus"),
    (["experience_requirements.core"], "experienceRequirements.core"),
    (["experience_requirements.min_total_years", "experience_years", "min_total_years"], "experienceRequirements.minTotalYears"),
    (["experience_requirements.max_total_years", "max_total_years"], "experienceRequirements.maxTotalYears"),
    (["education_constraints.min_degree", "min_degree"], "educationConstraints.minDegree"),
    (["education_constraints.prefer_degrees"], "educationConstraints.preferDegrees"),
    (["education_constraints.required_majors"], "educationConstraints.requiredMajors"),
    (["education_constraints.preferred_majors"], "educationConstraints.preferredMajors"),
    (["education_constraints.languages"], "educationConstraints.languages"),
    (["education_constraints.certifications"], "educationConstraints.certifications"),
    (["education_constraints.age_range"], "educationConstraints.ageRange"),
    (["education_constraints.other"], "educationConstraints.other"),
    (["tags"], "tags"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the real Qwen job normalization and embedding APIs, and compare input vs processed JSON."
    )
    parser.add_argument("--input", default="", help="Path to source jobs file. Defaults to JOB_DATA_PATH.")
    parser.add_argument("--limit", type=int, default=1, help="How many records to process when --index is not provided.")
    parser.add_argument(
        "--index",
        dest="indices",
        action="append",
        type=int,
        default=[],
        help="Specific 0-based record index to inspect. Repeat for multiple records.",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Optional markdown output path. Relative paths are resolved under backend/test; default output goes to backend/test/reports/job_normalization/.",
    )
    return parser.parse_args()


def now_local() -> datetime:
    return datetime.now().astimezone()


def is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def get_nested(payload: Any, path: str) -> Any:
    current = payload
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def first_non_empty(values: list[Any]) -> Any:
    for value in values:
        if not is_empty(value):
            return value
    return None


def truncate_text(value: Any, limit: int = 220) -> str:
    text = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3] + "..."


def make_jsonable(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def collect_filled_fields(source: dict[str, Any], processed: dict[str, Any]) -> list[dict[str, Any]]:
    filled: list[dict[str, Any]] = []
    for source_paths, processed_path in FIELD_COMPARISONS:
        source_values = [get_nested(source, path) for path in source_paths]
        if first_non_empty(source_values) is not None:
            continue
        processed_value = get_nested(processed, processed_path)
        if is_empty(processed_value):
            continue
        filled.append(
            {
                "source_paths": source_paths,
                "processed_path": processed_path,
                "processed_value": processed_value,
            }
        )
    return filled


def embedding_preview(vector: list[float], limit: int = 8) -> list[float]:
    return [round(float(value), 6) for value in vector[:limit]]


def render_report(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Real Job Normalization Compare Report")
    lines.append("")
    lines.append(f"- Run At: {report['run_at']}")
    lines.append(f"- Input: {report['input_path']}")
    lines.append(f"- LLM Provider: {report['llm_provider']}")
    lines.append(f"- LLM Model: {report['llm_model']}")
    lines.append(f"- Embedding Provider: {report['embedding_provider']}")
    lines.append(f"- Embedding Model: {report['embedding_model']}")
    lines.append(f"- Processed: {len(report['results'])}")
    lines.append("")

    if report["errors"]:
        lines.append("## Errors")
        lines.append("")
        for item in report["errors"]:
            lines.append(f"- index={item['index']} title={item.get('title') or '-'} error={item['error']}")
        lines.append("")

    for result in report["results"]:
        lines.append(f"## Record {result['index']} - {result['processed_json']['basicInfo']['title']}")
        lines.append("")
        lines.append(f"- Company: {result['processed_json']['company']}")
        lines.append(f"- Filled Fields Count: {len(result['filled_fields'])}")
        lines.append(f"- Context Preview: {truncate_text(result['context_text'], 260)}")
        lines.append(f"- Embedding Payload Preview: {truncate_text(result['embedding_payload'], 260)}")
        lines.append(f"- Embedding Dimensions: {result['embedding_dimensions']}")
        lines.append(f"- Embedding Preview: {truncate_text(result['embedding_preview'], 200)}")
        lines.append("")
        lines.append("### Input JSON")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(result["input_json"], ensure_ascii=False, indent=2))
        lines.append("```")
        lines.append("")
        lines.append("### Filled Fields")
        lines.append("")
        if result["filled_fields"]:
            for item in result["filled_fields"]:
                lines.append(
                    f"- {' | '.join(item['source_paths'])} -> {item['processed_path']}: {truncate_text(item['processed_value'])}"
                )
        else:
            lines.append("- No empty source fields were backfilled in the tracked paths.")
        lines.append("")
        lines.append("### Processed JSON")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(result["processed_json"], ensure_ascii=False, indent=2))
        lines.append("```")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    settings = get_settings()
    configure_logging(settings.app_log_dir, settings.app_log_level)

    if settings.llm_provider != "qwen" or settings.embedding_provider != "qwen":
        raise SystemExit("This script requires LLM_PROVIDER=qwen and EMBEDDING_PROVIDER=qwen.")

    input_path = Path(args.input).resolve() if args.input else settings.job_seed_path
    records = load_job_seed_records(input_path)
    indices = args.indices or list(range(min(max(args.limit, 0), len(records))))

    llm_client = _build_llm_client(settings)
    embedding_client = _build_embedding_client(settings)
    pipeline = JobPipelineService(
        repository=JobRepository(),
        llm_client=llm_client,
        embedding_client=embedding_client,
        vector_store=InMemoryVectorStore(),
    )

    started_at = now_local()
    report_paths = resolve_report_paths(
        category="job_normalization",
        output_arg=args.output,
        started_at=started_at,
        default_stem="job_normalization_compare",
    )

    report: dict[str, Any] = {
        "run_at": started_at.isoformat(timespec="seconds"),
        "input_path": str(input_path),
        "llm_provider": settings.llm_provider,
        "llm_model": settings.qwen_llm_model,
        "embedding_provider": settings.embedding_provider,
        "embedding_model": settings.qwen_embedding_model,
        "results": [],
        "errors": [],
    }

    for index in indices:
        if index < 0 or index >= len(records):
            report["errors"].append({"index": index, "title": None, "error": "index_out_of_range"})
            continue
        record = records[index]
        try:
            job = pipeline.normalize_record(record)
            processed_json = serialize(job)
            context_text = build_job_context_text(record)
            vector_payload = pipeline.vector_payload_for(job)
            vector = embedding_client.embed_text(vector_payload)
            report["results"].append(
                {
                    "index": index,
                    "input_json": make_jsonable(record),
                    "processed_json": processed_json,
                    "context_text": context_text,
                    "embedding_payload": vector_payload,
                    "embedding_dimensions": len(vector),
                    "embedding_preview": embedding_preview(vector),
                    "filled_fields": collect_filled_fields(record, processed_json),
                }
            )
        except Exception as exc:  # pragma: no cover - real network/provider path
            report["errors"].append(
                {
                    "index": index,
                    "title": record.get("title") or record.get("job_id"),
                    "error": repr(exc),
                }
            )

    markdown = render_report(report)
    write_report_files(report_paths, markdown, report)

    print(markdown)
    print(f"[report] markdown={report_paths.markdown_path}")
    print(f"[report] json={report_paths.json_path}")
    print(f"[report] latest_markdown={report_paths.latest_markdown_path}")
    print(f"[report] latest_json={report_paths.latest_json_path}")
    return 0 if report["results"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
