from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import sqlite3
from typing import Iterable

from app.domain.models import JobProfile, ResumeProfile
from app.repositories.payload_codec import job_from_payload, resume_from_payload


class _SqliteJsonRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS resumes (
                    id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.commit()


class SqliteResumeRepository(_SqliteJsonRepository):
    def count(self) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) FROM resumes").fetchone()
        return int(row[0]) if row is not None else 0

    def save(self, resume: ResumeProfile) -> ResumeProfile:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO resumes (id, payload_json)
                VALUES (?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (resume.id, json.dumps(asdict(resume), ensure_ascii=False, separators=(",", ":"))),
            )
            connection.commit()
        return resume

    def get(self, resume_id: str) -> ResumeProfile | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM resumes WHERE id = ?",
                (resume_id,),
            ).fetchone()
        if row is None:
            return None
        return resume_from_payload(json.loads(row[0]))

    def list(self) -> list[ResumeProfile]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload_json FROM resumes ORDER BY updated_at DESC, id ASC"
            ).fetchall()
        return [resume_from_payload(json.loads(row[0])) for row in rows]


class SqliteJobRepository(_SqliteJsonRepository):
    def count(self) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) FROM jobs").fetchone()
        return int(row[0]) if row is not None else 0

    def save(self, job: JobProfile) -> JobProfile:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO jobs (id, payload_json)
                VALUES (?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (job.id, json.dumps(asdict(job), ensure_ascii=False, separators=(",", ":"))),
            )
            connection.commit()
        return job

    def save_many(self, jobs: Iterable[JobProfile]) -> list[JobProfile]:
        values = list(jobs)
        if not values:
            return []
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO jobs (id, payload_json)
                VALUES (?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                [
                    (job.id, json.dumps(asdict(job), ensure_ascii=False, separators=(",", ":")))
                    for job in values
                ],
            )
            connection.commit()
        return values

    def get(self, job_id: str) -> JobProfile | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        if row is None:
            return None
        return job_from_payload(json.loads(row[0]))

    def list(self) -> list[JobProfile]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload_json FROM jobs ORDER BY updated_at DESC, id ASC"
            ).fetchall()
        return [job_from_payload(json.loads(row[0])) for row in rows]


