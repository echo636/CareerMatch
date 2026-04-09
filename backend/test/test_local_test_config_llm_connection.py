from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any
import urllib.error
import urllib.request
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parents[1]
TEST_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    def load_dotenv(*_args, **_kwargs):
        return False

from app.core.config import get_settings
from local_test_config import (
    configured_rerank_api_key_env_names,
    get_active_rerank_profile,
    list_rerank_profile_names,
    resolve_rerank_api_key,
)
from report_manager import resolve_report_paths, write_report_files


PASS = "pass"
WARN = "warn"
FAIL = "fail"
SKIP = "skip"

MASKED_VALUE = "***masked***"


def load_local_env() -> bool:
    loaded = bool(load_dotenv(ENV_PATH))
    if not ENV_PATH.exists():
        return loaded

    content = ENV_PATH.read_text(encoding="utf-8")
    for raw_line in content.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not value:
            parsed = ""
        elif value[0] in {"'", '"'} and value[-1] == value[0]:
            parsed = value[1:-1]
        else:
            parsed = re.sub(r"\s+#.*$", "", value).strip()
        os.environ.setdefault(key, parsed)
    return True


def mask_secret(value: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        return "-"
    if len(cleaned) <= 8:
        return "*" * len(cleaned)
    return f"{cleaned[:4]}...{cleaned[-4:]} (len={len(cleaned)})"


def shorten_text(value: Any, limit: int = 260) -> str:
    text = "" if value is None else str(value)
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3]}..."


def add_check(
    checks: list[dict[str, str]],
    *,
    status: str,
    name: str,
    detail: str,
    suggestion: str = "",
) -> None:
    checks.append(
        {
            "status": status,
            "name": name,
            "detail": detail,
            "suggestion": suggestion,
        }
    )


def parse_message_content(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())
        return "\n".join(parts).strip()
    return ""


def resolve_effective_source(source_override: str) -> str:
    if source_override != "auto":
        return source_override
    _, profile = get_active_rerank_profile()
    return (profile.source or "backend_client").strip().lower()


def diagnose_openai_compatible() -> tuple[dict[str, Any], list[dict[str, str]]]:
    profile_name, rerank = get_active_rerank_profile()
    checks: list[dict[str, str]] = []

    raw_chat_url = rerank.chat_url or ""
    effective_chat_url = raw_chat_url.strip()
    raw_model = rerank.model or ""
    effective_model = raw_model.strip()
    effective_api_key, api_key_source = resolve_rerank_api_key(rerank, environ=os.environ)

    add_check(
        checks,
        status=PASS,
        name="selected profile",
        detail=f"active_profile={profile_name!r}, display_name={rerank.display_name or profile_name!r}.",
    )
    if rerank.notes:
        add_check(
            checks,
            status=PASS,
            name="profile notes",
            detail=rerank.notes,
        )

    if raw_chat_url != effective_chat_url:
        add_check(
            checks,
            status=WARN,
            name="chat_url contains surrounding whitespace",
            detail=f"raw chat_url contains leading or trailing spaces: {raw_chat_url!r}",
            suggestion="Remove surrounding spaces to reduce ambiguity in manual inspection and copy/paste.",
        )
    else:
        add_check(
            checks,
            status=PASS,
            name="chat_url whitespace",
            detail="chat_url has no leading or trailing whitespace after inspection.",
        )

    if not effective_model:
        add_check(
            checks,
            status=FAIL,
            name="model is missing",
            detail="LOCAL_TEST_CONFIG.rerank.model is empty.",
            suggestion="Set rerank.model to a valid model name for the provider.",
        )
    else:
        add_check(
            checks,
            status=PASS,
            name="model is configured",
            detail=f"effective model is {effective_model!r}.",
        )

    if not effective_api_key:
        env_names = ", ".join(configured_rerank_api_key_env_names(rerank)) or "<none>"
        add_check(
            checks,
            status=FAIL,
            name="api_key is missing",
            detail=(
                "The selected profile did not resolve any api key from inline config or env vars. "
                f"api_key_env_vars={env_names}."
            ),
            suggestion="Provide an API key inline or set one of the configured env vars before running the test.",
        )
    else:
        add_check(
            checks,
            status=PASS,
            name="api_key is configured",
            detail=f"api key is present: {mask_secret(effective_api_key)} from {api_key_source or 'unknown source'}.",
        )
        if api_key_source == "inline":
            add_check(
                checks,
                status=WARN,
                name="api_key is hardcoded in local_test_config.py",
                detail="The current rerank API key is stored directly in backend/test/local_test_config.py.",
                suggestion="Prefer loading it from an environment variable to avoid accidental leak and report pollution.",
            )

    if not effective_chat_url:
        add_check(
            checks,
            status=FAIL,
            name="chat_url is missing",
            detail="LOCAL_TEST_CONFIG.rerank.chat_url is empty.",
            suggestion="Set rerank.chat_url to the provider's full chat completions endpoint.",
        )
    else:
        parsed = urlparse(effective_chat_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            add_check(
                checks,
                status=FAIL,
                name="chat_url is invalid",
                detail=f"chat_url could not be parsed as an absolute http(s) URL: {effective_chat_url!r}.",
                suggestion="Use a full URL such as https://host/path/chat/completions.",
            )
        else:
            add_check(
                checks,
                status=PASS,
                name="chat_url basic format",
                detail=f"chat_url scheme={parsed.scheme}, host={parsed.netloc}, path={parsed.path or '/'}",
            )
            normalized_path = parsed.path.rstrip("/")
            if normalized_path.endswith("/chat/completions"):
                add_check(
                    checks,
                    status=PASS,
                    name="chat_url endpoint path",
                    detail="chat_url already points to a chat completions endpoint.",
                )
            else:
                add_check(
                    checks,
                    status=FAIL,
                    name="chat_url endpoint path",
                    detail=(
                        "The compare script sends requests directly to rerank.chat_url, but the current path "
                        f"is {parsed.path or '/'} instead of a /chat/completions endpoint."
                    ),
                    suggestion="Change rerank.chat_url to https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions.",
                )

    effective_config = {
        "profile_name": profile_name,
        "profile_display_name": rerank.display_name or profile_name,
        "profile_notes": rerank.notes,
        "source": "openai_compatible",
        "provider": (rerank.provider or "openai_compatible").strip() or "openai_compatible",
        "model": effective_model,
        "api_key_masked": mask_secret(effective_api_key),
        "api_key_source": api_key_source or "missing",
        "api_key_env_names": configured_rerank_api_key_env_names(rerank),
        "chat_url": effective_chat_url,
        "timeout_sec": max(int(rerank.timeout_sec), 1),
        "retry_count": max(int(rerank.retry_count), 0),
        "retry_backoff_sec": max(float(rerank.retry_backoff_sec), 0.0),
        "temperature": float(rerank.temperature),
        "auth_header_name": (rerank.auth_header_name or "Authorization").strip() or "Authorization",
        "auth_prefix": rerank.auth_prefix or "",
        "request_headers": dict(rerank.request_headers or {}),
        "extra_body": dict(rerank.extra_body or {}),
    }
    return effective_config, checks


def diagnose_backend_client(env_loaded: bool) -> tuple[dict[str, Any], list[dict[str, str]]]:
    checks: list[dict[str, str]] = []
    get_settings.cache_clear()
    settings = get_settings()
    profile_name, rerank = get_active_rerank_profile()

    add_check(
        checks,
        status=PASS,
        name="selected profile",
        detail=f"active_profile={profile_name!r}, display_name={rerank.display_name or profile_name!r}.",
    )
    if rerank.notes:
        add_check(
            checks,
            status=PASS,
            name="profile notes",
            detail=rerank.notes,
        )

    if env_loaded:
        add_check(
            checks,
            status=PASS,
            name=".env load",
            detail=f"Loaded backend environment from {ENV_PATH}.",
        )
    else:
        add_check(
            checks,
            status=WARN,
            name=".env load",
            detail=f"{ENV_PATH} was not loaded, so only process environment variables are in effect.",
            suggestion="Ensure backend/.env exists or export the required variables before running the script.",
        )

    if settings.llm_provider != "qwen":
        add_check(
            checks,
            status=FAIL,
            name="LLM_PROVIDER",
            detail=f"Expected qwen, got {settings.llm_provider!r}.",
            suggestion="Set LLM_PROVIDER=qwen for the current backend implementation.",
        )
    else:
        add_check(
            checks,
            status=PASS,
            name="LLM_PROVIDER",
            detail=f"LLM_PROVIDER is {settings.llm_provider!r}.",
        )

    if not settings.dashscope_api_key:
        add_check(
            checks,
            status=FAIL,
            name="DASHSCOPE_API_KEY",
            detail="DASHSCOPE_API_KEY is empty after loading environment.",
            suggestion="Set DASHSCOPE_API_KEY in backend/.env or shell environment.",
        )
    else:
        add_check(
            checks,
            status=PASS,
            name="DASHSCOPE_API_KEY",
            detail=f"DASHSCOPE_API_KEY is present: {mask_secret(settings.dashscope_api_key)}.",
        )

    parsed = urlparse(settings.dashscope_base_url or "")
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        add_check(
            checks,
            status=FAIL,
            name="DASHSCOPE_BASE_URL",
            detail=f"dashscope base URL is invalid: {settings.dashscope_base_url!r}.",
            suggestion="Set DASHSCOPE_BASE_URL to a valid base URL such as https://dashscope.aliyuncs.com/compatible-mode/v1.",
        )
    else:
        add_check(
            checks,
            status=PASS,
            name="DASHSCOPE_BASE_URL",
            detail=f"base URL scheme={parsed.scheme}, host={parsed.netloc}, path={parsed.path or '/'}",
        )

    if not settings.qwen_llm_model:
        add_check(
            checks,
            status=FAIL,
            name="QWEN_LLM_MODEL",
            detail="QWEN_LLM_MODEL is empty after environment resolution.",
            suggestion="Set QWEN_LLM_MODEL to a valid model name.",
        )
    else:
        add_check(
            checks,
            status=PASS,
            name="QWEN_LLM_MODEL",
            detail=f"effective backend model is {settings.qwen_llm_model!r}.",
        )

    effective_config = {
        "profile_name": profile_name,
        "profile_display_name": rerank.display_name or profile_name,
        "profile_notes": rerank.notes,
        "source": "backend_client",
        "provider": settings.llm_provider,
        "model": settings.qwen_llm_model,
        "api_key_masked": mask_secret(settings.dashscope_api_key),
        "api_key_source": "env:DASHSCOPE_API_KEY",
        "chat_url": f"{settings.dashscope_base_url.rstrip('/')}/chat/completions",
        "timeout_sec": settings.dashscope_timeout_sec,
        "retry_count": settings.dashscope_llm_retry_count,
        "retry_backoff_sec": settings.dashscope_llm_retry_backoff_sec,
        "temperature": 0.1,
        "auth_header_name": "Authorization",
        "auth_prefix": "Bearer ",
        "request_headers": {},
        "extra_body": {"response_format": {"type": "json_object"}},
    }
    return effective_config, checks


def should_attempt_network_probe(config: dict[str, Any]) -> tuple[bool, str]:
    chat_url = (config.get("chat_url") or "").strip()
    model = (config.get("model") or "").strip()
    api_key = (config.get("api_key") or "").strip()

    if not chat_url:
        return False, "chat_url is empty."
    if not model:
        return False, "model is empty."
    if not api_key or api_key == "-":
        return False, "api key is empty."

    parsed = urlparse(chat_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False, "chat_url is not a valid absolute http(s) URL."
    return True, ""


def probe_chat_completion(config: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    payload: dict[str, Any] = {
        "model": config["model"],
        "messages": [
            {
                "role": "system",
                "content": "You are a connectivity check assistant. Reply with compact JSON only.",
            },
            {
                "role": "user",
                "content": 'Return this JSON object exactly: {"status":"ok","message":"llm connection works"}',
            },
        ],
        "temperature": config["temperature"],
    }
    payload.update(dict(config.get("extra_body") or {}))

    headers = {"Content-Type": "application/json"}
    headers.update(dict(config.get("request_headers") or {}))
    headers[config["auth_header_name"]] = f"{config['auth_prefix']}{config['api_key']}"

    request_body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url=config["chat_url"],
        data=request_body,
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=int(config["timeout_sec"])) as response:
            response_bytes = response.read()
            response_text = response_bytes.decode("utf-8", errors="replace")
            response_json = json.loads(response_text)
        duration_ms = round((time.perf_counter() - started) * 1000, 1)
        choices = response_json.get("choices") if isinstance(response_json, dict) else None
        content = ""
        if isinstance(choices, list) and choices:
            message = choices[0].get("message") if isinstance(choices[0], dict) else None
            if isinstance(message, dict):
                content = parse_message_content(message.get("content"))
        return {
            "status": PASS,
            "duration_ms": duration_ms,
            "http_status": 200,
            "request_url": config["chat_url"],
            "response_content_preview": shorten_text(content, 200),
            "response_preview": shorten_text(response_text, 500),
        }
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        duration_ms = round((time.perf_counter() - started) * 1000, 1)
        return {
            "status": FAIL,
            "duration_ms": duration_ms,
            "http_status": exc.code,
            "request_url": config["chat_url"],
            "error_type": "HTTPError",
            "error_detail": shorten_text(detail or f"HTTP {exc.code} with empty response body.", 500),
        }
    except urllib.error.URLError as exc:
        duration_ms = round((time.perf_counter() - started) * 1000, 1)
        return {
            "status": FAIL,
            "duration_ms": duration_ms,
            "request_url": config["chat_url"],
            "error_type": "URLError",
            "error_detail": shorten_text(exc.reason, 500),
        }
    except TimeoutError as exc:
        duration_ms = round((time.perf_counter() - started) * 1000, 1)
        return {
            "status": FAIL,
            "duration_ms": duration_ms,
            "request_url": config["chat_url"],
            "error_type": "TimeoutError",
            "error_detail": shorten_text(exc, 500),
        }
    except json.JSONDecodeError as exc:
        duration_ms = round((time.perf_counter() - started) * 1000, 1)
        return {
            "status": FAIL,
            "duration_ms": duration_ms,
            "request_url": config["chat_url"],
            "error_type": "JSONDecodeError",
            "error_detail": shorten_text(exc, 500),
        }
    except Exception as exc:  # pragma: no cover
        duration_ms = round((time.perf_counter() - started) * 1000, 1)
        return {
            "status": FAIL,
            "duration_ms": duration_ms,
            "request_url": config["chat_url"],
            "error_type": type(exc).__name__,
            "error_detail": shorten_text(exc, 500),
        }


def build_markdown_report(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Local Test Config LLM Connection Report")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- Overall Result: {report['overall_status'].upper()}")
    lines.append(f"- Checked At: {report['started_at']}")
    lines.append(f"- Effective Source: {report['effective_source']}")
    lines.append(f"- Network Probe Enabled: {report['network_probe_enabled']}")
    lines.append(f"- Report Version: {report['report_version']}")
    lines.append("")
    lines.append("## Scope")
    lines.append("- `backend/test/local_test_config.py` only controls local manual test scripts.")
    lines.append("- It does not replace the backend app's main LLM config in `backend/.env` unless the script uses `backend_client` mode.")
    lines.append("")
    lines.append("## Effective Config")
    for key, value in report["effective_config"].items():
        rendered = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
        if key == "api_key":
            rendered = MASKED_VALUE
        lines.append(f"- {key}: {rendered}")
    lines.append("")
    lines.append("## Checks")
    for item in report["checks"]:
        lines.append(f"- [{item['status'].upper()}] {item['name']}: {item['detail']}")
        if item.get("suggestion"):
            lines.append(f"  Suggestion: {item['suggestion']}")
    lines.append("")
    lines.append("## Network Probe")
    probe = report["network_probe"]
    if not probe:
        lines.append("- No network probe result.")
    else:
        for key, value in probe.items():
            rendered = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
            lines.append(f"- {key}: {rendered}")
    lines.append("")
    if report["summary_findings"]:
        lines.append("## Key Findings")
        for finding in report["summary_findings"]:
            lines.append(f"- {finding}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def summarize_findings(report: dict[str, Any]) -> list[str]:
    summary: list[str] = []
    failed_checks = [item for item in report["checks"] if item["status"] == FAIL]
    warn_checks = [item for item in report["checks"] if item["status"] == WARN]

    if failed_checks:
        summary.append(f"{len(failed_checks)} static configuration checks failed before or alongside the live probe.")
    if warn_checks:
        summary.append(f"{len(warn_checks)} configuration warnings were found.")

    probe = report["network_probe"]
    if probe:
        if probe.get("status") == PASS:
            summary.append(
                f"Live probe succeeded in {probe.get('duration_ms', '-')} ms against {report['effective_config'].get('chat_url', '-')}"
            )
        elif probe.get("status") == FAIL:
            status_text = probe.get("http_status") or probe.get("error_type") or "unknown error"
            summary.append(f"Live probe failed with {status_text}: {probe.get('error_detail', '-')}")
    return summary


def determine_overall_status(checks: list[dict[str, str]], network_probe: dict[str, Any] | None) -> str:
    if any(item["status"] == FAIL for item in checks):
        return FAIL
    if network_probe and network_probe.get("status") == FAIL:
        return FAIL
    if any(item["status"] == WARN for item in checks):
        return WARN
    return PASS


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Diagnose whether backend/test/local_test_config.py can connect to the configured LLM, "
            "show the exact misconfiguration points, and write a Markdown/JSON report."
        )
    )
    parser.add_argument("--output", default="", help="Optional markdown report path.")
    parser.add_argument(
        "--source",
        choices=("auto", "openai_compatible", "backend_client"),
        default="auto",
        help="Override the source to diagnose. Default: use LOCAL_TEST_CONFIG.rerank.source.",
    )
    parser.add_argument(
        "--skip-network",
        action="store_true",
        help="Only perform static configuration checks without sending a live request.",
    )
    args = parser.parse_args()

    started_at = datetime.now()
    env_loaded = load_local_env()
    effective_source = resolve_effective_source(args.source)

    if effective_source == "openai_compatible":
        effective_config, checks = diagnose_openai_compatible()
        _, active_profile = get_active_rerank_profile()
        effective_config["api_key"] = resolve_rerank_api_key(active_profile, environ=os.environ)[0]
    elif effective_source == "backend_client":
        effective_config, checks = diagnose_backend_client(env_loaded)
        get_settings.cache_clear()
        settings = get_settings()
        effective_config["api_key"] = settings.dashscope_api_key
    else:
        effective_config = {"source": effective_source}
        checks = []
        available = ", ".join(list_rerank_profile_names())
        add_check(
            checks,
            status=FAIL,
            name="source value",
            detail=f"Unsupported source value {effective_source!r}.",
            suggestion=f"Use backend_client or openai_compatible. Available profiles: {available}.",
        )

    network_probe: dict[str, Any] | None = None
    probe_allowed, probe_reason = should_attempt_network_probe(effective_config)
    if args.skip_network:
        network_probe = {
            "status": SKIP,
            "reason": "Skipped by --skip-network.",
        }
    elif not probe_allowed:
        network_probe = {
            "status": SKIP,
            "reason": probe_reason,
        }
    else:
        network_probe = probe_chat_completion(effective_config)

    report = {
        "report_version": 1,
        "started_at": started_at.isoformat(timespec="seconds"),
        "effective_source": effective_source,
        "network_probe_enabled": not args.skip_network,
        "checks": checks,
        "effective_config": {
            key: (MASKED_VALUE if key == "api_key" else value)
            for key, value in effective_config.items()
        },
        "network_probe": network_probe,
        "overall_status": "",
        "summary_findings": [],
    }
    report["overall_status"] = determine_overall_status(checks, network_probe)
    report["summary_findings"] = summarize_findings(report)

    markdown_text = build_markdown_report(report)
    report_paths = resolve_report_paths(
        category=f"llm_connectivity/{effective_source}",
        output_arg=args.output,
        started_at=started_at,
        default_stem=f"local_test_config_llm_connection_{effective_source}",
    )
    write_report_files(report_paths, markdown_text, report)

    print(f"[info] overall_status={report['overall_status']}")
    print(f"[info] source={effective_source}")
    print(f"[info] markdown_report={report_paths.markdown_path}")
    print(f"[info] json_report={report_paths.json_path}")
    for item in checks:
        print(f"[{item['status']}] {item['name']}: {item['detail']}")
    if network_probe:
        probe_status = network_probe.get("status", "-")
        probe_detail = network_probe.get("error_detail") or network_probe.get("response_content_preview") or network_probe.get("reason") or "-"
        print(f"[{probe_status}] network_probe: {probe_detail}")

    return 1 if report["overall_status"] == FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
