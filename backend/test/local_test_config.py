from __future__ import annotations

from dataclasses import dataclass, field
import os
from typing import Any, Mapping

"""
Single local config file for manual backend test scripts.

Edit this file when you want to:
- choose default resume files / ids for local testing
- switch the rerank model used by test_resume_algorithm_llm_compare.py

CLI arguments still take precedence over values defined here.
"""


@dataclass(slots=True)
class ResumeSelectionConfig:
    """
    Defaults for resume-selection related test scripts.

    Notes:
    - default_resume_id / default_resume_file are used by single-resume scripts.
    - default_resume_ids is used by multi-resume scripts.
    - If both default_resume_id and default_resume_file are set, single-resume
      scripts prefer default_resume_file.
    """

    default_resume_id: str = ""
    default_resume_file: str = r"D:\constructing_projects\CareerMatch\backend\uploads\resumes\resume-393061ce\e31efb4b_15-24K_10.pdf"
    default_resume_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RerankModelProfile:
    """
    Saved rerank profile for manual LLM comparison tests.

    source:
    - "backend_client": reuse the backend llm client created by backend/.env
    - "openai_compatible": call an external OpenAI-compatible chat endpoint
    """

    display_name: str = ""
    notes: str = ""
    source: str = "openai_compatible"
    provider: str = "qwen"
    model: str = ""
    chat_url: str = ""
    api_key: str = ""
    api_key_env_var: str = ""
    api_key_env_vars: list[str] = field(default_factory=list)
    timeout_sec: int = 180
    retry_count: int = 2
    retry_backoff_sec: float = 2.0
    temperature: float = 0.1
    auth_header_name: str = "Authorization"
    auth_prefix: str = "Bearer "
    request_headers: dict[str, str] = field(default_factory=dict)
    extra_body: dict[str, Any] = field(
        default_factory=lambda: {
            "response_format": {"type": "json_object"},
        }
    )


def _default_rerank_profiles() -> dict[str, RerankModelProfile]:
    dashscope_chat_url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    json_object_body = {"response_format": {"type": "json_object"}}

    return {
        "backend_default": RerankModelProfile(
            display_name="Backend .env Default",
            notes="Reuse backend/.env and the backend-created llm client.",
            source="backend_client",
            provider="backend",
            model="qwen-plus-latest",
        ),
        "dashscope_qwen_plus_latest": RerankModelProfile(
            display_name="DashScope Qwen Plus Latest",
            notes="Direct OpenAI-compatible call to DashScope using qwen-plus-latest.",
            source="openai_compatible",
            provider="qwen",
            model="qwen-plus-latest",
            chat_url=dashscope_chat_url,
            api_key_env_var="RERANK_DASHSCOPE_QWEN_PLUS_LATEST_API_KEY",
            timeout_sec=180,
            retry_count=2,
            retry_backoff_sec=2.0,
            temperature=0.1,
            extra_body=dict(json_object_body),
        ),
        "dashscope_qwen36_plus": RerankModelProfile(
            display_name="DashScope Qwen 3.6 Plus",
            notes="Direct OpenAI-compatible call to DashScope using qwen3.6-plus.",
            source="openai_compatible",
            provider="qwen",
            model="qwen3.6-plus",
            chat_url=dashscope_chat_url,
            api_key_env_var="RERANK_DASHSCOPE_QWEN36_PLUS_API_KEY",
            timeout_sec=180,
            retry_count=2,
            retry_backoff_sec=2.0,
            temperature=0.1,
            extra_body=dict(json_object_body),
        ),
        "minimax_text_01_example": RerankModelProfile(
            display_name="MiniMax Text 01 Example",
            notes="Example profile. Fill in the real chat_url and provide MINIMAX_API_KEY.",
            source="openai_compatible",
            provider="minimax",
            model="MiniMax-Text-01",
            chat_url="https://your-endpoint/chat/completions",
            api_key_env_var="RERANK_MINIMAX_TEXT_01_API_KEY",
            timeout_sec=180,
            retry_count=2,
            retry_backoff_sec=2.0,
            temperature=0.1,
            extra_body=dict(json_object_body),
        ),
    }


@dataclass(slots=True)
class RerankConfig:
    """
    Rerank profile selector.

    Usage:
    - set active_profile to the profile name you want
    - store each model's complete params under profiles

    Example:
    - LOCAL_TEST_CONFIG.rerank.active_profile = "backend_default"
    - LOCAL_TEST_CONFIG.rerank.active_profile = "dashscope_qwen36_plus"
    """

    active_profile: str = "dashscope_qwen_plus_latest"
    profiles: dict[str, RerankModelProfile] = field(default_factory=_default_rerank_profiles)

    def profile_names(self) -> list[str]:
        return list(self.profiles.keys())

    def active(self) -> RerankModelProfile:
        profile = self.profiles.get(self.active_profile)
        if profile is None:
            available = ", ".join(self.profile_names()) or "<none>"
            raise KeyError(
                f"Unknown LOCAL_TEST_CONFIG.rerank.active_profile={self.active_profile!r}. "
                f"Available profiles: {available}."
            )
        return profile

    @property
    def source(self) -> str:
        return self.active().source

    @property
    def provider(self) -> str:
        return self.active().provider

    @property
    def model(self) -> str:
        return self.active().model

    @property
    def chat_url(self) -> str:
        return self.active().chat_url

    @property
    def api_key(self) -> str:
        return self.active().api_key

    @property
    def api_key_env_vars(self) -> list[str]:
        return list(self.active().api_key_env_vars)

    @property
    def timeout_sec(self) -> int:
        return self.active().timeout_sec

    @property
    def retry_count(self) -> int:
        return self.active().retry_count

    @property
    def retry_backoff_sec(self) -> float:
        return self.active().retry_backoff_sec

    @property
    def temperature(self) -> float:
        return self.active().temperature

    @property
    def auth_header_name(self) -> str:
        return self.active().auth_header_name

    @property
    def auth_prefix(self) -> str:
        return self.active().auth_prefix

    @property
    def request_headers(self) -> dict[str, str]:
        return dict(self.active().request_headers)

    @property
    def extra_body(self) -> dict[str, Any]:
        return dict(self.active().extra_body)


def get_active_rerank_profile() -> tuple[str, RerankModelProfile]:
    return LOCAL_TEST_CONFIG.rerank.active_profile, LOCAL_TEST_CONFIG.rerank.active()


def list_rerank_profile_names() -> list[str]:
    return LOCAL_TEST_CONFIG.rerank.profile_names()


def configured_rerank_api_key_env_names(profile: RerankModelProfile) -> list[str]:
    names: list[str] = []
    primary = (profile.api_key_env_var or "").strip()
    if primary:
        names.append(primary)
    for name in profile.api_key_env_vars:
        cleaned = (name or "").strip()
        if cleaned and cleaned not in names:
            names.append(cleaned)
    return names


def resolve_rerank_api_key(
    profile: RerankModelProfile,
    *,
    environ: Mapping[str, str] | None = None,
) -> tuple[str, str]:
    env = environ or os.environ
    inline_key = (profile.api_key or "").strip()
    if inline_key:
        return inline_key, "inline"

    for env_name in configured_rerank_api_key_env_names(profile):
        value = (env.get(env_name, "") or "").strip()
        if value:
            return value, f"env:{env_name}"

    return "", ""


@dataclass(slots=True)
class LocalTestConfig:
    """
    Top-level local config.

    Read this object if you want the grouped, more readable structure.
    Compatibility aliases are also exported below for older scripts.
    """

    resume: ResumeSelectionConfig = field(default_factory=ResumeSelectionConfig)
    rerank: RerankConfig = field(default_factory=RerankConfig)


LOCAL_TEST_CONFIG = LocalTestConfig()


# Compatibility aliases for scripts that still import the old flat names.
DEFAULT_RESUME_ID = LOCAL_TEST_CONFIG.resume.default_resume_id
DEFAULT_RESUME_FILE = LOCAL_TEST_CONFIG.resume.default_resume_file
DEFAULT_RESUME_IDS = LOCAL_TEST_CONFIG.resume.default_resume_ids


# Switch rerank profile by changing only one line:
#
# LOCAL_TEST_CONFIG.rerank.active_profile = "backend_default"
# LOCAL_TEST_CONFIG.rerank.active_profile = "dashscope_qwen_plus_latest"
# LOCAL_TEST_CONFIG.rerank.active_profile = "dashscope_qwen36_plus"
# LOCAL_TEST_CONFIG.rerank.active_profile = "minimax_text_01_example"
#
# Per-profile API key env vars:
# - dashscope_qwen_plus_latest -> RERANK_DASHSCOPE_QWEN_PLUS_LATEST_API_KEY
# - dashscope_qwen36_plus -> RERANK_DASHSCOPE_QWEN36_PLUS_API_KEY
# - minimax_text_01_example -> RERANK_MINIMAX_TEXT_01_API_KEY
# - backend_default -> backend/.env DASHSCOPE_API_KEY
#
# Add a new model by copying one profile under LOCAL_TEST_CONFIG.rerank.profiles
# and then pointing active_profile to the new key.
