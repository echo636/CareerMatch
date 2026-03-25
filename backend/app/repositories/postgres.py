from __future__ import annotations

from dataclasses import asdict
from typing import Iterable

import psycopg
from psycopg.rows import dict_row

from app.domain.models import JobProfile, ResumeProfile
from app.repositories.payload_codec import job_from_payload, resume_from_payload


class _PostgresJsonRepository:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._ensure_schema()

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self._dsn, row_factory=dict_row)

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS resumes (
                    id TEXT PRIMARY KEY,
                    payload JSONB NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    payload JSONB NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            conn.commit()


class PostgresResumeRepository(_PostgresJsonRepository):
    def count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS cnt FROM resumes").fetchone()
        return int(row["cnt"]) if row else 0

    def save(self, resume: ResumeProfile) -> ResumeProfile:
        payload = asdict(resume)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO resumes (id, payload)
                VALUES (%s, %b)
                ON CONFLICT (id) DO UPDATE SET
                    payload = EXCLUDED.payload,
                    updated_at = now()
                """,
                (resume.id, psycopg.types.json.Jsonb(payload)),
            )
            conn.commit()
        return resume

    def get(self, resume_id: str) -> ResumeProfile | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM resumes WHERE id = %s",
                (resume_id,),
            ).fetchone()
        if row is None:
            return None
        return resume_from_payload(row["payload"])

    def list(self) -> list[ResumeProfile]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT payload FROM resumes ORDER BY updated_at DESC, id ASC"
            ).fetchall()
        return [resume_from_payload(row["payload"]) for row in rows]

    def delete(self, resume_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM resumes WHERE id = %s", (resume_id,))
            conn.commit()


class PostgresJobRepository(_PostgresJsonRepository):
    def count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS cnt FROM jobs").fetchone()
        return int(row["cnt"]) if row else 0

    def save(self, job: JobProfile) -> JobProfile:
        payload = asdict(job)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO jobs (id, payload)
                VALUES (%s, %b)
                ON CONFLICT (id) DO UPDATE SET
                    payload = EXCLUDED.payload,
                    updated_at = now()
                """,
                (job.id, psycopg.types.json.Jsonb(payload)),
            )
            conn.commit()
        return job

    def save_many(self, jobs: Iterable[JobProfile]) -> list[JobProfile]:
        values = list(jobs)
        if not values:
            return []
        with self._connect() as conn:
            with conn.cursor() as cur:
                for job in values:
                    cur.execute(
                        """
                        INSERT INTO jobs (id, payload)
                        VALUES (%s, %b)
                        ON CONFLICT (id) DO UPDATE SET
                            payload = EXCLUDED.payload,
                            updated_at = now()
                        """,
                        (job.id, psycopg.types.json.Jsonb(asdict(job))),
                    )
            conn.commit()
        return values

    def get(self, job_id: str) -> JobProfile | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM jobs WHERE id = %s",
                (job_id,),
            ).fetchone()
        if row is None:
            return None
        return job_from_payload(row["payload"])

    def list(self) -> list[JobProfile]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT payload FROM jobs ORDER BY updated_at DESC, id ASC"
            ).fetchall()
        return [job_from_payload(row["payload"]) for row in rows]

    def delete_all(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM jobs")
            conn.commit()
