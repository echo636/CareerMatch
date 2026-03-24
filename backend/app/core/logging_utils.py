from __future__ import annotations

from collections.abc import Mapping
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys
from typing import Any

_CONFIGURED = False


def configure_logging(log_dir: Path, log_level: str = "INFO") -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    log_dir.mkdir(parents=True, exist_ok=True)
    app_level = getattr(logging, log_level.upper(), logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")

    app_logger = logging.getLogger("careermatch")
    app_logger.handlers.clear()
    app_logger.setLevel(app_level)
    app_logger.propagate = False

    backend_file_handler = RotatingFileHandler(
        log_dir / "backend.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    backend_file_handler.setLevel(app_level)
    backend_file_handler.setFormatter(formatter)
    app_logger.addHandler(backend_file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(app_level)
    console_handler.setFormatter(formatter)
    app_logger.addHandler(console_handler)

    score_logger = logging.getLogger("careermatch.match_scores")
    score_logger.handlers.clear()
    score_logger.setLevel(logging.INFO)
    score_logger.propagate = False

    score_file_handler = RotatingFileHandler(
        log_dir / "match_scores.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    score_file_handler.setLevel(logging.INFO)
    score_file_handler.setFormatter(formatter)
    score_logger.addHandler(score_file_handler)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"careermatch.{name}")


def get_score_logger() -> logging.Logger:
    return logging.getLogger("careermatch.match_scores")


def to_log_json(payload: Mapping[str, Any] | dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str, separators=(",", ":"))
