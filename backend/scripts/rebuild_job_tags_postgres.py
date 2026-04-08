from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
import sys
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
TEST_DIR = BASE_DIR / "test"
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
if str(TEST_DIR) not in sys.path:
    sys.path.insert(0, str(TEST_DIR))

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    def load_dotenv(*_args, **_kwargs):
        return False

load_dotenv(BASE_DIR / ".env")

from app.clients.embedding import BaseEmbeddingClient
from app.clients.llm import QwenLLMClient
from app.clients.qdrant_store import QdrantVectorStore
from app.clients.vector_store import InMemoryVectorStore
from app.core.config import get_settings
from app.core.logging_utils import configure_logging, get_logger
from app.domain.models import JobProfile, serialize
from app.repositories.postgres import PostgresJobRepository
from app.services.job_pipeline import JobPipelineService
from report_manager import resolve_report_paths, write_report_files


class NoopEmbeddingClient(BaseEmbeddingClient):
    def embed_text(self, text: str, dimensions: int | None = None) -> list[float]:
        del text, dimensions
        return [0.0]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Rebuild job tags for existing Postgres jobs using the local normalization fast path, "
            "and optionally refresh Qdrant vectors when the vector payload changes."
        )
    )
    parser.add_argument(
        "--job-id",
        dest="job_ids",
        action="append",
        default=[],
        help="Specific job id to rebuild. Repeat for multiple jobs.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional max number of jobs to process when --job-id is not provided. 0 means all jobs.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute diffs and write the report without saving Postgres payloads or vectors.",
    )
    parser.add_argument(
        "--skip-vectors",
        action="store_true",
        help="Only update Postgres job payloads. Do not refresh Qdrant vectors.",
    )
    parser.add_argument(
        "--output",
        default="",
        help=(
            "Optional markdown output path. Relative paths are resolved under backend/test; "
            "default output goes to backend/test/reports/job_tag_refresh/."
        ),
    )
    return parser.parse_args()


def now_local() -> datetime:
    return datetime.now().astimezone()


def select_jobs(repository: PostgresJobRepository, job_ids: list[str], limit: int) -> list[JobProfile]:
    selected_ids = {job_id.strip() for job_id in job_ids if job_id.strip()}
    jobs = repository.list()
    if selected_ids:
        return [job for job in jobs if job.id in selected_ids]
    if limit > 0:
        return jobs[:limit]
    return jobs


def tag_summary(tags: list[dict[str, Any]], limit: int = 8) -> str:
    if not tags:
        return "-"
    items = [f"{item.get('name')}<{item.get('category')}>" for item in tags[:limit]]
    if len(tags) > limit:
        items.append(f"... (+{len(tags) - limit})")
    return ", ".join(items)


def category_counts(tags: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in tags:
        category = str(item.get("category") or "unknown")
        counts[category] = counts.get(category, 0) + 1
    return counts


def merge_counts(target: dict[str, int], values: dict[str, int]) -> None:
    for key, value in values.items():
        target[key] = target.get(key, 0) + int(value)


def render_report(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Job Tag Refresh Report")
    lines.append("")
    lines.append(f"- Run At: {report['run_at']}")
    lines.append(f"- Dry Run: {report['dry_run']}")
    lines.append(f"- Skip Vectors: {report['skip_vectors']}")
    lines.append(f"- Selected Jobs: {report['selected_jobs']}")
    lines.append(f"- Changed Jobs: {report['changed_jobs']}")
    lines.append(f"- Saved Jobs: {report['saved_jobs']}")
    lines.append(f"- Vector Refresh Count: {report['vector_refresh_count']}")
    lines.append(f"- Missing Requested Jobs: {', '.join(report['missing_job_ids']) if report['missing_job_ids'] else '-'}")
    lines.append(f"- Category Counts Before: {report['category_counts_before']}")
    lines.append(f"- Category Counts After: {report['category_counts_after']}")
    lines.append("")
    lines.append("## Changed Jobs")
    lines.append("")
    if not report["changed_items"]:
        lines.append("- No jobs changed.")
    else:
        for item in report["changed_items"]:
            lines.append(
                f"- {item['job_id']} | {item['title']} | tag_count {item['old_tag_count']} -> {item['new_tag_count']} "
                f"| roles {item['old_roles']} -> {item['new_roles']} | vector_payload_changed={item['vector_payload_changed']}"
            )
            lines.append(f"  old_tags: {tag_summary(item['old_tags'])}")
            lines.append(f"  new_tags: {tag_summary(item['new_tags'])}")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    settings = get_settings()
    configure_logging(settings.app_log_dir, settings.app_log_level)
    logger = get_logger("scripts.rebuild_job_tags_postgres")

    repository = PostgresJobRepository(settings.postgres_dsn)
    jobs = select_jobs(repository, args.job_ids, args.limit)
    selected_ids = {job.id for job in jobs}
    missing_job_ids = sorted({job_id.strip() for job_id in args.job_ids if job_id.strip()} - selected_ids)

    llm_client = QwenLLMClient(
        api_key=settings.dashscope_api_key or "local-offline",
        model=settings.qwen_llm_model,
        base_url=settings.dashscope_base_url,
        timeout_sec=settings.dashscope_timeout_sec,
        retry_count=0,
        retry_backoff_sec=0.0,
    )

    if args.skip_vectors:
        embedding_client: BaseEmbeddingClient = NoopEmbeddingClient()
        vector_store = InMemoryVectorStore()
    else:
        if not settings.dashscope_api_key:
            raise SystemExit("DASHSCOPE_API_KEY is required unless --skip-vectors is used.")
        from app.bootstrap import _build_embedding_client

        embedding_client = _build_embedding_client(settings)
        vector_store = QdrantVectorStore(settings.qdrant_url, settings.qwen_embedding_dimensions)

    pipeline = JobPipelineService(
        repository=repository,
        llm_client=llm_client,
        embedding_client=embedding_client,
        vector_store=vector_store,
    )

    changed_items: list[dict[str, Any]] = []
    jobs_to_save: list[JobProfile] = []
    vector_refresh_count = 0
    category_counts_before: dict[str, int] = {}
    category_counts_after: dict[str, int] = {}

    for job in jobs:
        original_payload = asdict(job)
        original_serialized = serialize(job)
        updated_job = pipeline.normalize_record(original_payload)
        updated_serialized = serialize(updated_job)

        old_tags = list(original_serialized.get("tags") or [])
        new_tags = list(updated_serialized.get("tags") or [])
        old_roles = list((original_serialized.get("filterFacets") or {}).get("roleCategories") or [])
        new_roles = list((updated_serialized.get("filterFacets") or {}).get("roleCategories") or [])
        old_vector_payload = pipeline.vector_payload_for(job)
        new_vector_payload = pipeline.vector_payload_for(updated_job)
        vector_payload_changed = old_vector_payload != new_vector_payload

        merge_counts(category_counts_before, category_counts(old_tags))
        merge_counts(category_counts_after, category_counts(new_tags))

        if old_tags == new_tags and old_roles == new_roles and not vector_payload_changed:
            continue

        changed_items.append(
            {
                "job_id": job.id,
                "title": updated_job.title,
                "old_tags": old_tags,
                "new_tags": new_tags,
                "old_tag_count": len(old_tags),
                "new_tag_count": len(new_tags),
                "old_roles": old_roles,
                "new_roles": new_roles,
                "vector_payload_changed": vector_payload_changed,
            }
        )
        jobs_to_save.append(updated_job)

        if not args.dry_run and not args.skip_vectors and vector_payload_changed:
            pipeline._ensure_vector("jobs", updated_job.id, new_vector_payload)
            vector_refresh_count += 1

    if not args.dry_run and jobs_to_save:
        repository.save_many(jobs_to_save)

    started_at = now_local()
    report_paths = resolve_report_paths(
        category="job_tag_refresh",
        output_arg=args.output,
        started_at=started_at,
        default_stem="job_tag_refresh",
    )
    report = {
        "run_at": started_at.isoformat(timespec="seconds"),
        "dry_run": bool(args.dry_run),
        "skip_vectors": bool(args.skip_vectors),
        "selected_jobs": len(jobs),
        "changed_jobs": len(changed_items),
        "saved_jobs": 0 if args.dry_run else len(jobs_to_save),
        "vector_refresh_count": 0 if args.dry_run else vector_refresh_count,
        "missing_job_ids": missing_job_ids,
        "category_counts_before": category_counts_before,
        "category_counts_after": category_counts_after,
        "changed_items": changed_items,
    }
    markdown = render_report(report)
    write_report_files(report_paths, markdown, report)

    print(markdown)
    print(f"[report] markdown={report_paths.markdown_path}")
    print(f"[report] json={report_paths.json_path}")
    print(f"[report] latest_markdown={report_paths.latest_markdown_path}")
    print(f"[report] latest_json={report_paths.latest_json_path}")
    logger.info(
        "job_tag_refresh.completed selected=%s changed=%s saved=%s dry_run=%s skip_vectors=%s",
        len(jobs),
        len(changed_items),
        0 if args.dry_run else len(jobs_to_save),
        args.dry_run,
        args.skip_vectors,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
