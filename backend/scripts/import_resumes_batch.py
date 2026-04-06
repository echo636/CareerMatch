from __future__ import annotations

import argparse
import hashlib
import mimetypes
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    def load_dotenv(*_args, **_kwargs):
        return False

from app.bootstrap import build_services
from app.core.config import get_settings
from app.core.logging_utils import configure_logging

SUPPORTED_SUFFIXES = {".pdf", ".docx", ".doc", ".txt", ".md"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch import resumes from local folders.")
    parser.add_argument(
        "--input-dir",
        action="append",
        required=True,
        help="Directory to scan recursively for resume files. Can be repeated.",
    )
    parser.add_argument("--limit", type=int, default=0, help="Maximum number of resumes to import.")
    parser.add_argument(
        "--prefix",
        type=str,
        default="batch-resume",
        help="Prefix used when generating resume ids.",
    )
    parser.add_argument(
        "--max-text-chars",
        type=int,
        default=12000,
        help="Trim extracted resume text to this many characters before sending to the LLM.",
    )
    return parser.parse_args()


def detect_content_type(file_path: Path) -> str:
    return mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"


def collect_candidate_files(input_dirs: list[Path]) -> list[Path]:
    files: list[Path] = []
    for input_dir in input_dirs:
        if not input_dir.exists():
            continue
        for path in sorted(input_dir.rglob("*")):
            if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES:
                files.append(path)
    return files


def main() -> int:
    load_dotenv(BACKEND_DIR / ".env")
    args = parse_args()
    settings = get_settings()
    configure_logging(settings.app_log_dir, settings.app_log_level)
    services = build_services(settings)

    input_dirs = [Path(value).expanduser().resolve() for value in args.input_dir]
    candidates = collect_candidate_files(input_dirs)

    existing_names = {resume.source_file_name for resume in services.resume_pipeline.repository.list() if resume.source_file_name}
    seen_hashes: set[str] = set()

    imported = 0
    skipped_existing = 0
    skipped_duplicate = 0
    skipped_empty = 0
    failures: list[tuple[str, str]] = []

    for file_path in candidates:
        if args.limit and imported >= args.limit:
            break
        if file_path.name in existing_names:
            skipped_existing += 1
            continue

        file_bytes = file_path.read_bytes()
        file_hash = hashlib.sha1(file_bytes).hexdigest()
        if file_hash in seen_hashes:
            skipped_duplicate += 1
            continue
        seen_hashes.add(file_hash)

        resume_id = f"{args.prefix}-{file_hash[:12]}"
        try:
            content_type = detect_content_type(file_path)
            raw_text = services.resume_pipeline.document_parser.extract_text(
                file_bytes=file_bytes,
                file_name=file_path.name,
                content_type=content_type,
            )
            normalized_text = raw_text.replace("\x00", " ").replace("\ufeff", " ").strip()
            if not normalized_text:
                skipped_empty += 1
                print(f"[skipped-empty] {file_path}")
                continue
            if args.max_text_chars and len(normalized_text) > args.max_text_chars:
                normalized_text = normalized_text[: args.max_text_chars]
            services.resume_pipeline.process_uploaded_resume(
                file_name=file_path.name,
                content_type=content_type,
                file_bytes=file_bytes,
                resume_id=resume_id,
                raw_text=normalized_text,
            )
            imported += 1
            print(f"[imported] {resume_id} <- {file_path}")
        except Exception as exc:  # pragma: no cover
            failures.append((str(file_path), str(exc)))
            print(f"[failed] {file_path}: {exc}")

    print(
        {
            "candidate_files": len(candidates),
            "imported": imported,
            "skipped_existing_name": skipped_existing,
            "skipped_duplicate_content": skipped_duplicate,
            "skipped_empty_text": skipped_empty,
            "failed": len(failures),
        }
    )
    if failures:
        for file_path, message in failures[:20]:
            print({"file": file_path, "error": message})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
