from __future__ import annotations

from abc import ABC, abstractmethod
import hashlib
import json
import urllib.error
import urllib.request


class BaseEmbeddingClient(ABC):
    @abstractmethod
    def embed_text(self, text: str, dimensions: int | None = None) -> list[float]:
        raise NotImplementedError


class SimpleEmbeddingClient(BaseEmbeddingClient):
    def embed_text(self, text: str, dimensions: int | None = 16) -> list[float]:
        size = dimensions or 16
        payload = hashlib.sha256(text.encode("utf-8")).digest()
        values = []
        for index in range(size):
            source = payload[index % len(payload)]
            values.append(round(source / 255, 6))
        return values


class QwenEmbeddingClient(BaseEmbeddingClient):
    def __init__(
        self,
        *,
        api_key: str,
        model: str = "text-embedding-v4",
        base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1",
        dimensions: int = 1024,
        timeout_sec: int = 60,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.dimensions = dimensions
        self.timeout_sec = timeout_sec

    def embed_text(self, text: str, dimensions: int | None = None) -> list[float]:
        payload = {
            "model": self.model,
            "input": text,
            "encoding_format": "float",
        }
        target_dimensions = dimensions or self.dimensions
        if target_dimensions > 0:
            payload["dimensions"] = target_dimensions

        response = self._post_json("/embeddings", payload)
        data = response.get("data") or []
        if not data:
            raise RuntimeError("Qwen embedding response did not include data.")
        embedding = data[0].get("embedding")
        if not isinstance(embedding, list):
            raise RuntimeError("Qwen embedding response did not include a valid embedding vector.")
        return [float(value) for value in embedding]

    def _post_json(self, path: str, payload: dict) -> dict:
        request = urllib.request.Request(
            url=f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_sec) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Qwen embedding request failed with status {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Qwen embedding request failed: {exc.reason}") from exc
