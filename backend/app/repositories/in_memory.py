from __future__ import annotations

from typing import Dict, Iterable

from app.domain.models import JobProfile, ResumeProfile


class ResumeRepository:
    def __init__(self) -> None:
        self._items: Dict[str, ResumeProfile] = {}

    def save(self, resume: ResumeProfile) -> ResumeProfile:
        self._items[resume.id] = resume
        return resume

    def get(self, resume_id: str) -> ResumeProfile | None:
        return self._items.get(resume_id)

    def list(self) -> list[ResumeProfile]:
        return list(self._items.values())


class JobRepository:
    def __init__(self) -> None:
        self._items: Dict[str, JobProfile] = {}

    def save(self, job: JobProfile) -> JobProfile:
        self._items[job.id] = job
        return job

    def save_many(self, jobs: Iterable[JobProfile]) -> list[JobProfile]:
        return [self.save(job) for job in jobs]

    def get(self, job_id: str) -> JobProfile | None:
        return self._items.get(job_id)

    def list(self) -> list[JobProfile]:
        return list(self._items.values())
