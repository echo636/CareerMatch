from __future__ import annotations

from abc import ABC, abstractmethod
import hashlib
import json
import urllib.error
import urllib.request

from app.core.logging_utils import get_logger

logger = get_logger("clients.embedding")


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
        logger.debug("embedding.simple.generated dimensions=%s text_length=%s", size, len(text))
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

        logger.debug(
            "embedding.qwen.request_start model=%s dimensions=%s text_length=%s",
            self.model,
            target_dimensions,
            len(text),
        )
        response = self._post_json("/embeddings", payload)
        data = response.get("data") or []
        if not data:
            logger.error("embedding.qwen.invalid_response missing_data model=%s", self.model)
            raise RuntimeError("Qwen embedding response did not include data.")
        embedding = data[0].get("embedding")
        if not isinstance(embedding, list):
            logger.error("embedding.qwen.invalid_response missing_embedding model=%s", self.model)
            raise RuntimeError("Qwen embedding response did not include a valid embedding vector.")
        logger.debug(
            "embedding.qwen.request_success model=%s dimensions=%s returned_dimensions=%s",
            self.model,
            target_dimensions,
            len(embedding),
        )
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
        except TimeoutError as exc:
            logger.warning(
                "embedding.qwen.timeout model=%s timeout_sec=%s",
                self.model,
                self.timeout_sec,
            )
            raise RuntimeError(
                f"Qwen embedding request timed out after {self.timeout_sec} seconds."
            ) from exc
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            logger.error(
                "embedding.qwen.http_error model=%s status=%s detail=%s",
                self.model,
                exc.code,
                detail,
            )
            raise RuntimeError(f"Qwen embedding request failed with status {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                logger.warning(
                    "embedding.qwen.timeout model=%s timeout_sec=%s",
                    self.model,
                    self.timeout_sec,
                )
                raise RuntimeError(
                    f"Qwen embedding request timed out after {self.timeout_sec} seconds."
                ) from exc
            logger.error(
                "embedding.qwen.url_error model=%s reason=%s",
                self.model,
                exc.reason,
            )
            raise RuntimeError(f"Qwen embedding request failed: {exc.reason}") from exc
