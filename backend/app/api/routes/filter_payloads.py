from __future__ import annotations

from typing import Any

from app.domain.models import MatchFilters


def parse_match_filters(payload: dict[str, Any]) -> MatchFilters | None:
    raw_filters = payload.get("filters") or {}
    if not isinstance(raw_filters, dict):
        return None

    role_categories = _normalize_string_list(raw_filters.get("role_categories"))
    work_modes = _normalize_string_list(raw_filters.get("work_modes"))
    internship_preference = str(raw_filters.get("internship_preference") or "all").strip().lower()
    if internship_preference not in {"all", "intern", "fulltime"}:
        internship_preference = "all"

    filters = MatchFilters(
        role_categories=role_categories,
        work_modes=work_modes,
        internship_preference=internship_preference,
        posted_within_days=_coerce_positive_int(raw_filters.get("posted_within_days")),
        min_experience_years=_coerce_float(raw_filters.get("min_experience_years")),
        max_experience_years=_coerce_float(raw_filters.get("max_experience_years")),
    )
    return filters if filters.is_active else None


def _normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    ordered: list[str] = []
    seen: set[str] = set()
    for item in value:
        normalized = str(item or "").strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def _coerce_positive_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _coerce_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
