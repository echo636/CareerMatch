from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import shutil
from typing import Any

TEST_DIR = Path(__file__).resolve().parent
REPORTS_DIR = TEST_DIR / "reports"


@dataclass(frozen=True, slots=True)
class ReportPaths:
    category: str
    markdown_path: Path
    json_path: Path
    latest_markdown_path: Path
    latest_json_path: Path


def resolve_report_paths(
    *,
    category: str,
    output_arg: str,
    started_at: datetime,
    default_stem: str,
) -> ReportPaths:
    category_dir = REPORTS_DIR / category
    if output_arg:
        markdown_path = Path(output_arg)
        if not markdown_path.is_absolute():
            markdown_path = TEST_DIR / markdown_path
    else:
        day_dir = category_dir / started_at.strftime("%Y-%m-%d")
        stamp = started_at.strftime("%Y%m%d_%H%M%S")
        markdown_path = day_dir / f"{default_stem}_{stamp}.md"

    if markdown_path.suffix.lower() != ".md":
        markdown_path = markdown_path.with_suffix(".md")
    json_path = markdown_path.with_suffix(".json")
    latest_markdown_path = category_dir / "latest.md"
    latest_json_path = category_dir / "latest.json"
    return ReportPaths(
        category=category,
        markdown_path=markdown_path,
        json_path=json_path,
        latest_markdown_path=latest_markdown_path,
        latest_json_path=latest_json_path,
    )


def write_report_files(paths: ReportPaths, markdown_text: str, report_payload: dict[str, Any]) -> None:
    paths.markdown_path.parent.mkdir(parents=True, exist_ok=True)
    paths.markdown_path.write_text(markdown_text, encoding="utf-8")
    paths.json_path.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    paths.latest_markdown_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(paths.markdown_path, paths.latest_markdown_path)
    shutil.copyfile(paths.json_path, paths.latest_json_path)
