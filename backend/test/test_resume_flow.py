from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

DEFAULT_API_BASE_URL = "http://127.0.0.1:5000/api"
DEFAULT_SAMPLE_RESUME = ROOT_DIR / "test" / "sample_resume.txt"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke test the real Qwen resume extraction and upload flow."
    )
    parser.add_argument(
        "--mode",
        choices=("direct", "upload", "both"),
        default="both",
        help="direct: call QwenLLMClient directly; upload: call local backend upload/match/gap APIs.",
    )
    parser.add_argument(
        "--api-base-url",
        default=DEFAULT_API_BASE_URL,
        help="Local backend API base URL for upload mode.",
    )
    parser.add_argument(
        "--file",
        dest="file_path",
        default=str(DEFAULT_SAMPLE_RESUME),
        help="Resume text file used for both direct and upload modes.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=3,
        help="Number of matches to request from /matches/recommend and /gap/report.",
    )
    return parser.parse_args()


def request_json(
    url: str,
    *,
    method: str = "GET",
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> dict:
    request = urllib.request.Request(url=url, data=data, method=method)
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    with urllib.request.urlopen(request, timeout=90) as response:
        return json.loads(response.read().decode("utf-8"))


def build_multipart_form(file_path: Path, *, resume_id: str) -> tuple[bytes, str]:
    boundary = f"----CareerMatchBoundary{uuid.uuid4().hex}"
    parts: list[bytes] = []

    def add_field(name: str, value: str) -> None:
        parts.append(f"--{boundary}\r\n".encode("utf-8"))
        parts.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
        parts.append(value.encode("utf-8"))
        parts.append(b"\r\n")

    def add_file(name: str, path: Path) -> None:
        content_type = "text/plain; charset=utf-8"
        parts.append(f"--{boundary}\r\n".encode("utf-8"))
        parts.append(
            (
                f'Content-Disposition: form-data; name="{name}"; filename="{path.name}"\r\n'
                f"Content-Type: {content_type}\r\n\r\n"
            ).encode("utf-8")
        )
        parts.append(path.read_bytes())
        parts.append(b"\r\n")

    add_field("resume_id", resume_id)
    add_file("file", file_path)
    parts.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(parts), boundary


def print_json(title: str, payload: dict) -> None:
    print(f"\n[{title}]")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def print_status(message: str) -> None:
    print(f"[resume-flow] {message}", flush=True)


def run_direct_llm(file_path: Path) -> None:
    from app.clients.llm import QwenLLMClient
    from app.core.config import get_settings

    settings = get_settings()
    if settings.llm_provider != "qwen":
        raise RuntimeError(
            f"LLM_PROVIDER is '{settings.llm_provider}', expected 'qwen' for a real LLM smoke test."
        )
    if not settings.dashscope_api_key:
        raise RuntimeError("DASHSCOPE_API_KEY is missing.")

    raw_text = file_path.read_text(encoding="utf-8")
    client = QwenLLMClient(
        api_key=settings.dashscope_api_key,
        model=settings.qwen_llm_model,
        base_url=settings.dashscope_base_url,
        timeout_sec=settings.dashscope_timeout_sec,
    )
    resume_id = f"llm-smoke-{uuid.uuid4().hex[:8]}"
    print_status(
        "direct mode is sending a full resume extraction request to DashScope "
        f"with model '{settings.qwen_llm_model}' and timeout {settings.dashscope_timeout_sec}s."
    )
    started_at = time.monotonic()
    payload = client.extract_resume(raw_text, file_path.name, resume_id)
    print_status(f"direct mode completed in {time.monotonic() - started_at:.1f}s.")
    print_json(
        "direct-llm",
        {
            "resumeId": payload.get("id"),
            "name": ((payload.get("basic_info") or {}).get("name")),
            "currentTitle": ((payload.get("basic_info") or {}).get("current_title")),
            "skillCount": len(payload.get("skills") or []),
            "projectCount": len(payload.get("projects") or []),
            "summary": ((payload.get("basic_info") or {}).get("summary")),
        },
    )


def run_upload_flow(api_base_url: str, file_path: Path, top_k: int) -> None:
    print_status(f"upload mode is checking backend health at {api_base_url}/health.")
    health = request_json(f"{api_base_url}/health")
    print_json("health", health)

    resume_id = f"upload-smoke-{uuid.uuid4().hex[:8]}"
    body, boundary = build_multipart_form(file_path, resume_id=resume_id)
    print_status(f"upload mode is posting {file_path.name} to {api_base_url}/resumes/upload.")
    upload_payload = request_json(
        f"{api_base_url}/resumes/upload",
        method="POST",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    print_json(
        "upload",
        {
            "resumeId": upload_payload.get("resumeId"),
            "name": ((upload_payload.get("resume") or {}).get("basicInfo") or {}).get("name"),
            "skillCount": len(((upload_payload.get("resume") or {}).get("skills") or [])),
            "projectCount": len(((upload_payload.get("resume") or {}).get("projects") or [])),
        },
    )

    request_body = json.dumps({"resume_id": upload_payload["resumeId"], "top_k": top_k}).encode("utf-8")
    print_status(f"upload mode is requesting top {top_k} matches.")
    matches_payload = request_json(
        f"{api_base_url}/matches/recommend",
        method="POST",
        data=request_body,
        headers={"Content-Type": "application/json"},
    )
    print_json(
        "matches",
        {
            "count": len(matches_payload.get("matches") or []),
            "topJob": (((matches_payload.get("matches") or [{}])[0].get("job") or {}).get("basicInfo") or {}).get(
                "title"
            )
            if matches_payload.get("matches")
            else None,
        },
    )

    print_status("upload mode is requesting the gap report.")
    gap_payload = request_json(
        f"{api_base_url}/gap/report",
        method="POST",
        data=request_body,
        headers={"Content-Type": "application/json"},
    )
    print_json(
        "gap",
        {
            "baselineRoles": (gap_payload.get("report") or {}).get("baselineRoles"),
            "missingSkills": (gap_payload.get("report") or {}).get("missingSkills"),
            "insightCount": len(((gap_payload.get("report") or {}).get("insights") or [])),
        },
    )


def main() -> int:
    args = parse_args()
    file_path = Path(args.file_path).resolve()
    if not file_path.exists():
        print(f"Resume file not found: {file_path}", file=sys.stderr)
        return 2

    print_status(f"mode={args.mode}, file={file_path}")
    try:
        if args.mode in {"direct", "both"}:
            run_direct_llm(file_path)
        if args.mode in {"upload", "both"}:
            run_upload_flow(args.api_base_url.rstrip("/"), file_path, args.top_k)
    except KeyboardInterrupt:
        print(
            "Interrupted while waiting for an external response. "
            "The direct LLM extraction can take tens of seconds because it requests a full JSON resume.",
            file=sys.stderr,
        )
        return 130
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        print(f"HTTPError {exc.code}: {detail}", file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"URLError: {exc.reason}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
