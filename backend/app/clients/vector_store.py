from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import json
from math import sqrt
from pathlib import Path
import sqlite3


@dataclass(frozen=True, slots=True)
class StoredVector:
    vector: list[float]
    payload_hash: str


class BaseVectorStore(ABC):
    @abstractmethod
    def get(self, namespace: str, item_id: str) -> StoredVector | None:
        raise NotImplementedError

    @abstractmethod
    def upsert(self, namespace: str, item_id: str, vector: list[float], payload_hash: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def query(self, namespace: str, vector: list[float], top_k: int) -> list[dict[str, float | str]]:
        raise NotImplementedError


class InMemoryVectorStore(BaseVectorStore):
    def __init__(self) -> None:
        self._namespaces: dict[str, dict[str, StoredVector]] = {}

    def get(self, namespace: str, item_id: str) -> StoredVector | None:
        return self._namespaces.get(namespace, {}).get(item_id)

    def upsert(self, namespace: str, item_id: str, vector: list[float], payload_hash: str) -> None:
        self._namespaces.setdefault(namespace, {})[item_id] = StoredVector(vector=list(vector), payload_hash=payload_hash)

    def query(self, namespace: str, vector: list[float], top_k: int) -> list[dict[str, float | str]]:
        namespace_values = self._namespaces.get(namespace, {})
        scored = [
            {"id": item_id, "score": self._cosine_similarity(vector, stored.vector)}
            for item_id, stored in namespace_values.items()
        ]
        scored.sort(key=lambda item: float(item["score"]), reverse=True)
        return scored[:top_k]

    def _cosine_similarity(self, left: list[float], right: list[float]) -> float:
        dot_product = sum(a * b for a, b in zip(left, right))
        left_norm = sqrt(sum(a * a for a in left))
        right_norm = sqrt(sum(b * b for b in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return round(dot_product / (left_norm * right_norm), 6)


class SqliteVectorStore(BaseVectorStore):
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def get(self, namespace: str, item_id: str) -> StoredVector | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT vector_json, payload_hash FROM vectors WHERE namespace = ? AND item_id = ?",
                (namespace, item_id),
            ).fetchone()
        if row is None:
            return None
        return StoredVector(vector=self._decode_vector(row[0]), payload_hash=str(row[1]))

    def upsert(self, namespace: str, item_id: str, vector: list[float], payload_hash: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO vectors (namespace, item_id, payload_hash, vector_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(namespace, item_id) DO UPDATE SET
                    payload_hash = excluded.payload_hash,
                    vector_json = excluded.vector_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (namespace, item_id, payload_hash, self._encode_vector(vector)),
            )
            connection.commit()

    def query(self, namespace: str, vector: list[float], top_k: int) -> list[dict[str, float | str]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT item_id, vector_json FROM vectors WHERE namespace = ?",
                (namespace,),
            ).fetchall()
        scored = [
            {"id": str(row[0]), "score": self._cosine_similarity(vector, self._decode_vector(row[1]))}
            for row in rows
        ]
        scored.sort(key=lambda item: float(item["score"]), reverse=True)
        return scored[:top_k]

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS vectors (
                    namespace TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    vector_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (namespace, item_id)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_vectors_namespace ON vectors(namespace)"
            )
            connection.commit()

    def _encode_vector(self, vector: list[float]) -> str:
        return json.dumps(vector, separators=(",", ":"))

    def _decode_vector(self, payload: str) -> list[float]:
        values = json.loads(payload)
        return [float(value) for value in values]

    def _cosine_similarity(self, left: list[float], right: list[float]) -> float:
        dot_product = sum(a * b for a, b in zip(left, right))
        left_norm = sqrt(sum(a * a for a in left))
        right_norm = sqrt(sum(b * b for b in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return round(dot_product / (left_norm * right_norm), 6)
