from __future__ import annotations

import argparse
import json
from math import ceil
from pathlib import Path
import sqlite3
import sys
import time

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    def load_dotenv(*_args, **_kwargs):
        return False

load_dotenv(BASE_DIR / '.env')

from app.bootstrap import _build_embedding_client, _build_llm_client
from app.clients.llm import MockLLMClient
from app.clients.vector_store import SqliteVectorStore
from app.core.config import get_settings
from app.job_seed_loader import load_job_seed_records
from app.repositories.sqlite import SqliteJobRepository, SqliteResumeRepository
from app.services.job_pipeline import JobPipelineService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Offline import jobs into the persistent CareerMatch store.'
    )
    parser.add_argument(
        '--input',
        default='',
        help='Source job file path. Supports .json and .sql. Defaults to JOB_DATA_PATH.',
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Optional max number of jobs to import.',
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=50,
        help='Number of jobs to process per batch.',
    )
    parser.add_argument(
        '--replace-jobs',
        action='store_true',
        help='Clear persisted jobs and job vectors before importing.',
    )
    parser.add_argument(
        '--state-db',
        default='',
        help='Optional override for APP_STATE_DB_PATH.',
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


def clear_jobs(db_path: Path) -> None:
    with sqlite3.connect(db_path) as connection:
        connection.execute('DELETE FROM jobs')
        connection.execute("DELETE FROM vectors WHERE namespace = 'jobs'")
        connection.commit()


def count_state(db_path: Path) -> dict[str, int]:
    with sqlite3.connect(db_path) as connection:
        jobs = int(connection.execute('SELECT COUNT(*) FROM jobs').fetchone()[0])
        resumes = int(connection.execute('SELECT COUNT(*) FROM resumes').fetchone()[0])
        vectors = int(connection.execute('SELECT COUNT(*) FROM vectors').fetchone()[0])
    return {'jobs': jobs, 'resumes': resumes, 'vectors': vectors}


def print_status(message: str) -> None:
    print(f'[offline-import] {message}', flush=True)


def main() -> int:
    args = parse_args()
    settings = get_settings()
    input_path = resolve_path(args.input, settings.job_seed_path)
    state_db_path = resolve_path(args.state_db, settings.app_state_db_path)
    batch_size = max(args.batch_size, 1)

    print_status(
        f"input={input_path}, db={state_db_path}, llm={settings.llm_provider}, embedding={settings.embedding_provider}"
    )
    records = load_job_seed_records(input_path, limit=args.limit)
    print_status(f'loaded {len(records)} job records from source file.')

    llm_client = _build_llm_client(settings, MockLLMClient())
    embedding_client = _build_embedding_client(settings)
    SqliteResumeRepository(state_db_path)
    repository = SqliteJobRepository(state_db_path)
    vector_store = SqliteVectorStore(state_db_path)

    if args.replace_jobs:
        print_status('clearing persisted jobs and job vectors before import.')
        clear_jobs(state_db_path)

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
        batch = records[index:index + batch_size]
        batch_no = (index // batch_size) + 1
        batch_started_at = time.monotonic()
        pipeline.import_jobs(batch)
        imported += len(batch)
        print_status(
            f'batch {batch_no}/{total_batches} imported {len(batch)} jobs in '
            f'{time.monotonic() - batch_started_at:.1f}s; total={imported}/{total}.'
        )

    state = count_state(state_db_path)
    payload = {
        'input': str(input_path),
        'stateDb': str(state_db_path),
        'imported': imported,
        'elapsedSec': round(time.monotonic() - started_at, 2),
        'dbCounts': state,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
