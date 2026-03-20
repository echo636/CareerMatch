from __future__ import annotations

import hashlib


class SimpleEmbeddingClient:
    def embed_text(self, text: str, dimensions: int = 16) -> list[float]:
        payload = hashlib.sha256(text.encode("utf-8")).digest()
        values = []
        for index in range(dimensions):
            source = payload[index % len(payload)]
            values.append(round(source / 255, 6))
        return values
