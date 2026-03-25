from __future__ import annotations

import logging
from uuid import UUID, uuid5

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from app.clients.vector_store import BaseVectorStore, StoredVector

logger = logging.getLogger(__name__)

QDRANT_UUID_NAMESPACE = UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")


def _deterministic_uuid(item_id: str) -> str:
    return str(uuid5(QDRANT_UUID_NAMESPACE, item_id))


class QdrantVectorStore(BaseVectorStore):
    def __init__(self, url: str, embedding_dimensions: int) -> None:
        self._client = QdrantClient(url=url)
        self._dimensions = embedding_dimensions
        self._ensured_collections: set[str] = set()

    def _ensure_collection(self, namespace: str) -> None:
        if namespace in self._ensured_collections:
            return
        if not self._client.collection_exists(namespace):
            self._client.create_collection(
                collection_name=namespace,
                vectors_config=VectorParams(
                    size=self._dimensions,
                    distance=Distance.COSINE,
                ),
            )
            logger.info("Created Qdrant collection '%s' (dim=%d)", namespace, self._dimensions)
        self._ensured_collections.add(namespace)

    def get(self, namespace: str, item_id: str) -> StoredVector | None:
        self._ensure_collection(namespace)
        point_id = _deterministic_uuid(item_id)
        results = self._client.retrieve(
            collection_name=namespace,
            ids=[point_id],
            with_vectors=True,
            with_payload=True,
        )
        if not results:
            return None
        point = results[0]
        return StoredVector(
            vector=list(point.vector),
            payload_hash=str(point.payload.get("payload_hash", "")),
        )

    def upsert(self, namespace: str, item_id: str, vector: list[float], payload_hash: str) -> None:
        self._ensure_collection(namespace)
        point_id = _deterministic_uuid(item_id)
        self._client.upsert(
            collection_name=namespace,
            points=[
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "item_id": item_id,
                        "payload_hash": payload_hash,
                    },
                )
            ],
        )

    def query(self, namespace: str, vector: list[float], top_k: int) -> list[dict[str, float | str]]:
        self._ensure_collection(namespace)
        results = self._client.query_points(
            collection_name=namespace,
            query=vector,
            limit=top_k,
            with_payload=True,
        ).points
        return [
            {
                "id": str(point.payload.get("item_id", point.id)),
                "score": round(point.score, 6),
            }
            for point in results
        ]

    def delete(self, namespace: str, item_id: str) -> None:
        self._ensure_collection(namespace)
        point_id = _deterministic_uuid(item_id)
        self._client.delete(
            collection_name=namespace,
            points_selector=[point_id],
        )

    def delete_all(self, namespace: str) -> None:
        if self._client.collection_exists(namespace):
            self._client.delete_collection(namespace)
            self._ensured_collections.discard(namespace)
