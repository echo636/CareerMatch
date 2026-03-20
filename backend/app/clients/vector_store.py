from __future__ import annotations

from math import sqrt


class InMemoryVectorStore:
    def __init__(self) -> None:
        self._namespaces: dict[str, dict[str, list[float]]] = {}

    def upsert(self, namespace: str, item_id: str, vector: list[float]) -> None:
        self._namespaces.setdefault(namespace, {})[item_id] = vector

    def query(self, namespace: str, vector: list[float], top_k: int) -> list[dict[str, float | str]]:
        namespace_values = self._namespaces.get(namespace, {})
        scored = [
            {"id": item_id, "score": self._cosine_similarity(vector, stored_vector)}
            for item_id, stored_vector in namespace_values.items()
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
