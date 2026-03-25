from .in_memory import JobRepository, ResumeRepository
from .postgres import PostgresJobRepository, PostgresResumeRepository
from .sqlite import SqliteJobRepository, SqliteResumeRepository

__all__ = [
    "JobRepository",
    "ResumeRepository",
    "PostgresJobRepository",
    "PostgresResumeRepository",
    "SqliteJobRepository",
    "SqliteResumeRepository",
]
