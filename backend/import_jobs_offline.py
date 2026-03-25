from __future__ import annotations

import argparse
import json
from math import ceil
from pathlib import Path
import sys
import time

import psycopg

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    def load_dotenv(*_args, **_kwargs):
        return False

load_dotenv(BASE_DIR / ".env")

from app.bootstrap import _build_embedding_client, _build_llm_client
from app.clients.qdrant_store import QdrantVectorStore
from app.core.config import get_settings
from app.core.logging_utils import configure_logging, get_logger, to_log_json
from app.job_seed_loader import load_job_seed_records
from app.repositories.postgres import PostgresJobRepository, PostgresResumeRepository
from app.services.job_pipeline import JobPipelineService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Offline import jobs into the persistent CareerMatch store using real Qwen APIs."
    )
    parser.add_argument(
        "--input",
        default="",
        help="Source job file path. Supports .json and .sql. Defaults to JOB_DATA_PATH.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional max number of jobs to import.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Number of jobs to process per batch.",
    )
    parser.add_argument(
        "--replace-jobs",
        action="store_true",
        help="Clear persisted jobs and job vectors before importing.",
    )
    return parser.parse_args()


def resolve_path(value: str, default: Path) -> Path:
    if not value:
        return default
    path = Path(value)
    if path.is_absolute():
        return path.resolve()
    if path.exists() or path.parent.exists():
        return path.resolve()
    return (BASE_DIR / path).resolve()


def clear_jobs(dsn: str, vector_store: QdrantVectorStore) -> None:
    with psycopg.connect(dsn) as conn:
        conn.execute("DELETE FROM jobs")
        conn.commit()
    vector_store.delete_all("jobs")


def count_state(dsn: str) -> dict[str, int]:
    with psycopg.connect(dsn) as conn:
        jobs = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        resumes = conn.execute("SELECT COUNT(*) FROM resumes").fetchone()[0]
    return {"jobs": int(jobs), "resumes": int(resumes)}


def print_status(message: str) -> None:
    print(f"[offline-import] {message}", flush=True)


def main() -> int:
    args = parse_args()
    settings = get_settings()
    configure_logging(settings.app_log_dir, settings.app_log_level)
    logger = get_logger("scripts.import_jobs_offline")

    input_path = resolve_path(args.input, settings.job_seed_path)
    batch_size = max(args.batch_size, 1)

    logger.info(
        "offline_import.start input=%s postgres=%s qdrant=%s llm=%s embedding=%s batch_size=%s limit=%s replace_jobs=%s",
        input_path,
        settings.postgres_dsn,
        settings.qdrant_url,
        settings.llm_provider,
        settings.embedding_provider,
        batch_size,
        args.limit,
        args.replace_jobs,
    )
    print_status(
        f"input={input_path}, postgres={settings.postgres_dsn}, qdrant={settings.qdrant_url}"
    )

    records = load_job_seed_records(input_path, limit=args.limit)
    print_status(f"loaded {len(records)} job records from source file.")
    logger.info("offline_import.loaded_records count=%s", len(records))

    llm_client = _build_llm_client(settings)
    embedding_client = _build_embedding_client(settings)
    PostgresResumeRepository(settings.postgres_dsn)
    repository = PostgresJobRepository(settings.postgres_dsn)
    vector_store = QdrantVectorStore(settings.qdrant_url, settings.qwen_embedding_dimensions)

    if args.replace_jobs:
        print_status("clearing persisted jobs and job vectors before import.")
        clear_jobs(settings.postgres_dsn, vector_store)
        logger.info("offline_import.cleared_existing_jobs")

    pipeline = JobPipelineService(
        repository=repository,
        llm_client=llm_client,
        embedding_client=embedding_client,
        vector_store=vector_store,
    )

    total = len(records)
    total_batches = ceil(total / batch_size) if total else 0
    imported = 0
    started_at = time.monotonic()

    for index in range(0, total, batch_size):
        batch = records[index : index + batch_size]
        batch_no = (index // batch_size) + 1
        batch_started_at = time.monotonic()
        try:
            pipeline.import_jobs(batch)
        except Exception:
            logger.exception(
                "offline_import.batch_failed batch_no=%s total_batches=%s imported=%s batch_size=%s",
                batch_no,
                total_batches,
                imported,
                len(batch),
            )
            raise
        imported += len(batch)
        batch_elapsed = time.monotonic() - batch_started_at
        print_status(
            f"batch {batch_no}/{total_batches} imported {len(batch)} jobs in {batch_elapsed:.1f}s; total={imported}/{total}."
        )
        logger.info(
            "offline_import.batch_completed batch_no=%s total_batches=%s batch_size=%s imported=%s elapsed_sec=%.2f",
            batch_no,
            total_batches,
            len(batch),
            imported,
            batch_elapsed,
        )

    state = count_state(settings.postgres_dsn)
    payload = {
        "input": str(input_path),
        "postgres": settings.postgres_dsn,
        "imported": imported,
        "elapsedSec": round(time.monotonic() - started_at, 2),
        "dbCounts": state,
    }
    logger.info("offline_import.completed %s", to_log_json(payload))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
