from __future__ import annotations

import argparse
from dataclasses import asdict
import statistics
import sys
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
TEST_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(TEST_DIR) not in sys.path:
    sys.path.insert(0, str(TEST_DIR))

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    def load_dotenv(*_args, **_kwargs):
        return False

from app.bootstrap import build_services
from app.core.config import get_settings
from app.core.logging_utils import configure_logging
from app.job_enrichment import build_job_context_text
from report_manager import resolve_report_paths, write_report_files
from test_ranking_correlation import llm_sort_key, spearman_rho
from test_resume_algorithm_llm_compare import collect_candidate_pool, compute_spearman_metrics, llm_rank_candidates


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run pointwise/listwise evaluation across multiple resumes and report average metrics."
    )
    parser.add_argument(
        "--resume-id",
        dest="resume_ids",
        action="append",
        default=[],
        help="Specific resume id to evaluate. Repeat to provide multiple ids.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="When --resume-id is omitted, evaluate the latest N resumes. Default: 5.",
    )
    parser.add_argument(
        "--mode",
        choices=("pointwise", "listwise", "both"),
        default="both",
        help="Evaluation mode. Default: both.",
    )
    parser.add_argument(
        "--pointwise-top-k",
        type=int,
        default=10,
        help="Top-k used by pointwise evaluation. Default: 10.",
    )
    parser.add_argument(
        "--listwise-top-k",
        type=int,
        default=10,
        help="Top-k overlap shown by listwise evaluation. Default: 10.",
    )
    parser.add_argument(
        "--candidate-limit",
        type=int,
        default=30,
        help="Candidate pool size for listwise evaluation. Default: 30.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="",
        help="Optional custom markdown output path.",
    )
    return parser.parse_args()


def now_local() -> datetime:
    return datetime.now().astimezone()


def brief_text(text: str | None, limit: int = 120) -> str:
    normalized = " ".join((text or "").split())
    if not normalized:
        return "-"
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3] + "..."


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    return round(float(statistics.median(values)), 4)


def _min(values: list[float]) -> float | None:
    return round(min(values), 4) if values else None


def _max(values: list[float]) -> float | None:
    return round(max(values), 4) if values else None


def resolve_resume_ids(services: Any, requested_ids: list[str], limit: int) -> list[str]:
    if requested_ids:
        ordered: list[str] = []
        seen: set[str] = set()
        for resume_id in requested_ids:
            normalized = resume_id.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            ordered.append(normalized)
        return ordered

    resumes = services.resume_pipeline.repository.list()
    if limit > 0:
        resumes = resumes[:limit]
    return [resume.id for resume in resumes]


def run_pointwise_for_resume(services: Any, resume: Any, top_k: int) -> dict[str, Any]:
    matches = services.matching_service.recommend(resume.id, top_k)
    if not matches:
        raise RuntimeError("algorithm returned no matches")

    llm_client = services.resume_pipeline.llm_client
    algo_order: list[str] = []
    llm_results: list[dict[str, Any]] = []

    algo_duration_ms = None
    if hasattr(matches[0], "breakdown"):
        algo_duration_ms = None

    llm_started = perf_counter()
    for match in matches:
        algo_order.append(match.job.id)
        job_context = build_job_context_text(asdict(match.job))
        result = llm_client.score_job_match(resume.raw_text, job_context)
        llm_results.append(
            {
                "job_id": match.job.id,
                "job_title": match.job.title,
                "company": match.job.company,
                "algo_score": match.breakdown.total,
                "llm_score": result["score"],
                "llm_reasoning": result["reasoning"],
                "llm_subscores": result.get("subscores") or {},
            }
        )
    llm_duration_ms = round((perf_counter() - llm_started) * 1000, 2)

    llm_sorted = sorted(llm_results, key=llm_sort_key, reverse=True)
    llm_order = [item["job_id"] for item in llm_sorted]
    rho = spearman_rho(algo_order, llm_order)

    return {
        "resume_id": resume.id,
        "resume_name": resume.basic_info.name,
        "current_title": resume.basic_info.current_title,
        "rho": rho,
        "match_count": len(matches),
        "llm_duration_ms": llm_duration_ms,
        "algorithm_top_job": matches[0].job.title if matches else None,
        "algorithm_top_company": matches[0].job.company if matches else None,
        "llm_top_job": llm_sorted[0]["job_title"] if llm_sorted else None,
        "llm_top_company": llm_sorted[0]["company"] if llm_sorted else None,
        "comparisons": [
            {
                "algo_rank": index + 1,
                "llm_rank": llm_order.index(item["job_id"]) + 1,
                "job_title": item["job_title"],
                "company": item["company"],
                "algo_score": item["algo_score"],
                "llm_score": item["llm_score"],
            }
            for index, item in enumerate(llm_results)
        ],
    }


def run_listwise_for_resume(services: Any, resume: Any, candidate_limit: int, top_k: int) -> dict[str, Any]:
    candidate_pool = collect_candidate_pool(services, resume, candidate_limit)
    if candidate_pool["compared_candidate_count"] == 0:
        raise RuntimeError("no compared candidates after recall/filter")

    llm_result = llm_rank_candidates(services, resume, candidate_pool["compared_candidates"])
    metrics = compute_spearman_metrics(candidate_pool["algorithm_order"], llm_result["order"])
    overlap = len(set(candidate_pool["algorithm_order"][:top_k]) & set(llm_result["order"][:top_k]))

    return {
        "resume_id": resume.id,
        "resume_name": resume.basic_info.name,
        "current_title": resume.basic_info.current_title,
        "rho": metrics["rho"],
        "top_k_overlap": overlap,
        "candidate_count": candidate_pool["compared_candidate_count"],
        "candidate_pool_duration_ms": candidate_pool["duration_ms"],
        "llm_duration_ms": llm_result["duration_ms"],
        "algorithm_top_job": candidate_pool["algorithm_ranked"][0]["job_title"] if candidate_pool["algorithm_ranked"] else None,
        "algorithm_top_company": candidate_pool["algorithm_ranked"][0]["company"] if candidate_pool["algorithm_ranked"] else None,
        "llm_top_job": next(
            (
                item["job_title"]
                for item in candidate_pool["compared_candidates"]
                if item["job_id"] == llm_result["order"][0]
            ),
            None,
        )
        if llm_result["order"]
        else None,
        "llm_top_company": next(
            (
                item["company"]
                for item in candidate_pool["compared_candidates"]
                if item["job_id"] == llm_result["order"][0]
            ),
            None,
        )
        if llm_result["order"]
        else None,
    }


def summarize_mode(results: list[dict[str, Any]], *, extra_numeric_keys: list[str] | None = None) -> dict[str, Any]:
    extra_numeric_keys = extra_numeric_keys or []
    rho_values = [float(item["rho"]) for item in results if item.get("rho") is not None]
    summary: dict[str, Any] = {
        "count": len(results),
        "avg_rho": _mean(rho_values),
        "median_rho": _median(rho_values),
        "min_rho": _min(rho_values),
        "max_rho": _max(rho_values),
    }
    for key in extra_numeric_keys:
        values = [float(item[key]) for item in results if item.get(key) is not None]
        summary[f"avg_{key}"] = _mean(values)
        summary[f"median_{key}"] = _median(values)
    return summary


def render_report(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Multi-Resume Average Evaluation")
    lines.append("")
    lines.append(f"- Run At: {report['run_at']}")
    lines.append(f"- Jobs In Store: {report['dataset']['job_count']}")
    lines.append(f"- Resumes In Store: {report['dataset']['resume_count']}")
    lines.append(f"- Evaluated Resume Count: {report['selection']['evaluated_resume_count']}")
    lines.append(f"- Mode: {report['selection']['mode']}")
    lines.append(f"- Resume IDs: {', '.join(report['selection']['resume_ids'])}")
    lines.append("")

    if report.get("pointwise"):
        pointwise = report["pointwise"]
        lines.append("## Pointwise Summary")
        lines.append("")
        lines.append(f"- Resume Count: {pointwise['summary']['count']}")
        lines.append(f"- Avg Spearman ρ: {pointwise['summary']['avg_rho']}")
        lines.append(f"- Median Spearman ρ: {pointwise['summary']['median_rho']}")
        lines.append(f"- Min Spearman ρ: {pointwise['summary']['min_rho']}")
        lines.append(f"- Max Spearman ρ: {pointwise['summary']['max_rho']}")
        lines.append(f"- Avg LLM Duration: {pointwise['summary'].get('avg_llm_duration_ms')} ms")
        lines.append("")
        lines.append("| Resume | Name | Current Title | ρ | Algo Top | LLM Top |")
        lines.append("|---|---|---|---:|---|---|")
        for item in pointwise["results"]:
            lines.append(
                f"| {item['resume_id']} | {item['resume_name']} | {item['current_title'] or '-'} | {item['rho']} | "
                f"{brief_text(item['algorithm_top_job'], 24)} | {brief_text(item['llm_top_job'], 24)} |"
            )
        lines.append("")

    if report.get("listwise"):
        listwise = report["listwise"]
        lines.append("## Listwise Summary")
        lines.append("")
        lines.append(f"- Resume Count: {listwise['summary']['count']}")
        lines.append(f"- Avg Spearman ρ: {listwise['summary']['avg_rho']}")
        lines.append(f"- Median Spearman ρ: {listwise['summary']['median_rho']}")
        lines.append(f"- Avg Top-{report['selection']['listwise_top_k']} Overlap: {listwise['summary'].get('avg_top_k_overlap')}")
        lines.append(f"- Avg Candidate Count: {listwise['summary'].get('avg_candidate_count')}")
        lines.append(f"- Avg Candidate Pool Duration: {listwise['summary'].get('avg_candidate_pool_duration_ms')} ms")
        lines.append(f"- Avg LLM Duration: {listwise['summary'].get('avg_llm_duration_ms')} ms")
        lines.append("")
        lines.append("| Resume | Name | Current Title | ρ | Top-K Overlap | Algo Top | LLM Top |")
        lines.append("|---|---|---|---:|---:|---|---|")
        for item in listwise["results"]:
            lines.append(
                f"| {item['resume_id']} | {item['resume_name']} | {item['current_title'] or '-'} | {item['rho']} | {item['top_k_overlap']} | "
                f"{brief_text(item['algorithm_top_job'], 24)} | {brief_text(item['llm_top_job'], 24)} |"
            )
        lines.append("")

    if report["failures"]:
        lines.append("## Failures")
        lines.append("")
        for item in report["failures"]:
            lines.append(f"- {item['mode']} | {item['resume_id']} | {item['error']}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    load_dotenv(BACKEND_DIR / ".env")
    get_settings.cache_clear()
    settings = get_settings()
    configure_logging(settings.app_log_dir, settings.app_log_level)
    services = build_services(settings)

    resume_ids = resolve_resume_ids(services, args.resume_ids, args.limit)
    if not resume_ids:
        raise SystemExit("no resumes selected for evaluation")

    started_at = now_local()
    report_paths = resolve_report_paths(
        category="multi_resume_average_eval",
        output_arg=args.output,
        started_at=started_at,
        default_stem="multi_resume_average_eval",
    )

    pointwise_results: list[dict[str, Any]] = []
    listwise_results: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []

    selected_mode = args.mode
    for resume_id in resume_ids:
        resume = services.resume_pipeline.get_resume(resume_id)
        if resume is None:
            failures.append({"mode": "load", "resume_id": resume_id, "error": "resume not found"})
            continue

        if selected_mode in {"pointwise", "both"}:
            print(f"[batch] pointwise -> {resume_id} ({resume.basic_info.name})")
            try:
                pointwise_results.append(run_pointwise_for_resume(services, resume, args.pointwise_top_k))
            except Exception as exc:
                failures.append({"mode": "pointwise", "resume_id": resume_id, "error": str(exc)})

        if selected_mode in {"listwise", "both"}:
            print(f"[batch] listwise -> {resume_id} ({resume.basic_info.name})")
            try:
                listwise_results.append(
                    run_listwise_for_resume(services, resume, args.candidate_limit, args.listwise_top_k)
                )
            except Exception as exc:
                failures.append({"mode": "listwise", "resume_id": resume_id, "error": str(exc)})

    report: dict[str, Any] = {
        "run_at": started_at.isoformat(timespec="seconds"),
        "dataset": {
            "job_count": len(services.matching_service.job_repository.list()),
            "resume_count": len(services.resume_pipeline.repository.list()),
        },
        "selection": {
            "mode": selected_mode,
            "resume_ids": resume_ids,
            "evaluated_resume_count": len(resume_ids),
            "pointwise_top_k": args.pointwise_top_k,
            "listwise_top_k": args.listwise_top_k,
            "candidate_limit": args.candidate_limit,
        },
        "pointwise": None,
        "listwise": None,
        "failures": failures,
    }

    if pointwise_results:
        report["pointwise"] = {
            "summary": summarize_mode(pointwise_results, extra_numeric_keys=["llm_duration_ms"]),
            "results": pointwise_results,
        }
    if listwise_results:
        report["listwise"] = {
            "summary": summarize_mode(
                listwise_results,
                extra_numeric_keys=["top_k_overlap", "candidate_count", "candidate_pool_duration_ms", "llm_duration_ms"],
            ),
            "results": listwise_results,
        }

    report_text = render_report(report)
    write_report_files(report_paths, report_text, report)

    print("")
    print(report_text)
    print(f"[report] markdown={report_paths.markdown_path}")
    print(f"[report] json={report_paths.json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
