from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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
class RerankModelConfig:
    """
    Only affects backend/test/test_resume_algorithm_llm_compare.py.

    source:
    - "backend_client": reuse the backend llm client created by backend/.env
    - "openai_compatible": call an external OpenAI-compatible chat endpoint

    provider / model are shown in the generated markdown/json report.
    """

    source: str = "openai_compatible"
    provider: str = "minimax"
    model: str = ""

    # Used only when source == "openai_compatible".
    chat_url: str = "https://ai.deepplumen.cn"
    api_key: str = "sk-f6bdb3643dbabb86169de19abd2ac3452c320b0e8091e2f6929ef1ec0afcbb21"
    timeout_sec: int = 120
    retry_count: int = 2
    retry_backoff_sec: float = 2.0
    temperature: float = 0.1

    # Override these only if the provider does not use standard Bearer auth.
    auth_header_name: str = "Authorization"
    auth_prefix: str = "Bearer "

    # Optional provider-specific extensions.
    request_headers: dict[str, str] = field(default_factory=dict)
    extra_body: dict[str, Any] = field(
        default_factory=lambda: {
            "response_format": {"type": "json_object"},
        }
    )


@dataclass(slots=True)
class LocalTestConfig:
    """
    Top-level local config.

    Read this object if you want the grouped, more readable structure.
    Compatibility aliases are also exported below for older scripts.
    """

    resume: ResumeSelectionConfig = field(default_factory=ResumeSelectionConfig)
    rerank: RerankModelConfig = field(default_factory=RerankModelConfig)


LOCAL_TEST_CONFIG = LocalTestConfig()


# Compatibility aliases for scripts that still import the old flat names.
DEFAULT_RESUME_ID = LOCAL_TEST_CONFIG.resume.default_resume_id
DEFAULT_RESUME_FILE = LOCAL_TEST_CONFIG.resume.default_resume_file
DEFAULT_RESUME_IDS = LOCAL_TEST_CONFIG.resume.default_resume_ids


# MiniMax example for test_resume_algorithm_llm_compare.py:
#
# LOCAL_TEST_CONFIG.rerank.source = "openai_compatible"
# LOCAL_TEST_CONFIG.rerank.provider = "minimax"
# LOCAL_TEST_CONFIG.rerank.model = "MiniMax-Text-01"
# LOCAL_TEST_CONFIG.rerank.chat_url = "https://your-endpoint/chat/completions"
# LOCAL_TEST_CONFIG.rerank.api_key = "your_api_key"
#
# If you want to switch back to the backend model:
#
# LOCAL_TEST_CONFIG.rerank.source = "backend_client"
# LOCAL_TEST_CONFIG.rerank.provider = "backend"
# LOCAL_TEST_CONFIG.rerank.model = ""
