from __future__ import annotations

import argparse
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
TEST_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*_args, **_kwargs):
        return False

from app.bootstrap import build_services
from app.core.config import get_settings
from app.core.logging_utils import configure_logging
from app.job_enrichment import build_job_context_text
from local_test_config import DEFAULT_RESUME_ID
from report_manager import resolve_report_paths, write_report_files


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare algorithmic matching ranking with LLM-based scoring. "
            "Computes Spearman rank correlation coefficient. "
            "When --resume-id is omitted, the script falls back to backend/test/local_test_config.py."
        )
    )
    parser.add_argument(
        "--resume-id",
        default=DEFAULT_RESUME_ID,
        help="Resume ID to test.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=10,
        help="Number of top matches to compare. Default: 10.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="",
        help="Optional custom report filename.",
    )
    return parser.parse_args()


def spearman_rho(algo_ids: list[str], llm_ids: list[str]) -> float:
    n = len(algo_ids)
    if n <= 1:
        return 1.0
    rank_b = {job_id: i for i, job_id in enumerate(llm_ids)}
    d_sq = sum((i - rank_b[jid]) ** 2 for i, jid in enumerate(algo_ids))
    return round(1.0 - (6 * d_sq) / (n * (n ** 2 - 1)), 4)


def llm_sort_key(item: dict[str, Any]) -> tuple[float, float, float, float, float, float, float, float]:
    subscores = item.get("llm_subscores") or {}
    return (
        float(item.get("llm_score") or 0.0),
        float(subscores.get("domain") or 0.0),
        float(subscores.get("skill") or 0.0),
        float(subscores.get("experience") or 0.0),
        float(subscores.get("location") or 0.0),
        float(subscores.get("education") or 0.0),
        float(subscores.get("salary") or 0.0),
        -float(subscores.get("transition_cost") or 0.0),
    )


def brief_text(text: str, limit: int = 120) -> str:
    normalized = " ".join((text or "").split())
    if len(normalized) <= limit:
        return normalized or "-"
    return normalized[: limit - 3] + "..."


def render_report(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# 排序相关性报告")
    lines.append("")
    lines.append(f"- 运行时间: {report['run_at']}")
    lines.append(f"- 简历ID: {report['resume_id']}")
    lines.append(f"- 候选人: {report['resume_name']}")
    lines.append(f"- 匹配岗位数: {report['match_count']}")
    lines.append(f"- Spearman ρ: **{report['spearman_rho']}**")
    lines.append(f"- 算法耗时: {report['algo_duration_ms']} ms")
    lines.append(f"- LLM打分耗时: {report['llm_duration_ms']} ms")
    lines.append("")

    rho = report["spearman_rho"]
    if rho >= 0.8:
        lines.append("> 强相关：算法排序与 LLM 语义理解高度一致。")
    elif rho >= 0.5:
        lines.append("> 中等相关：算法排序与 LLM 有一定一致性，部分岗位排序存在差异。")
    else:
        lines.append("> 弱相关：算法排序与 LLM 认知差距较大，建议分析差异原因。")
    lines.append("")

    lines.append("## 排序对比")
    lines.append("")
    lines.append("| # | 岗位 | 公司 | 算法排名 | 算法分 | LLM排名 | LLM分 | 名次差 |")
    lines.append("|---|------|------|---------|--------|---------|-------|--------|")

    for item in report["comparisons"]:
        lines.append(
            f"| {item['index']} "
            f"| {brief_text(item['job_title'], 20)} "
            f"| {brief_text(item['company'], 12)} "
            f"| {item['algo_rank']} "
            f"| {item['algo_score']:.4f} "
            f"| {item['llm_rank']} "
            f"| {item['llm_score']} "
            f"| {item['rank_diff']} |"
        )
    lines.append("")

    big_diffs = [c for c in report["comparisons"] if abs(c["rank_diff"]) >= 3]
    if big_diffs:
        lines.append("## 差异较大的岗位 (名次差 ≥ 3)")
        lines.append("")
        for item in big_diffs:
            direction = "LLM更看好" if item["rank_diff"] > 0 else "算法更看好"
            lines.append(f"### {item['job_title']} ({item['company']})")
            lines.append(f"- 算法排名: {item['algo_rank']}，LLM排名: {item['llm_rank']}（{direction}）")
            lines.append(f"- 算法分: {item['algo_score']:.4f}，LLM分: {item['llm_score']}")
            lines.append(f"- LLM说明: {item['llm_reasoning']}")
            lines.append("")

    lines.append("## LLM 打分详情")
    lines.append("")
    for item in report["comparisons"]:
        lines.append(f"**{item['index']}. {item['job_title']}** (LLM: {item['llm_score']}分)")
        lines.append(f"> {item['llm_reasoning']}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    args.resume_id = (args.resume_id or "").strip()
    if not args.resume_id:
        raise SystemExit(
            "resume id is required. Pass --resume-id or set DEFAULT_RESUME_ID in backend/test/local_test_config.py"
        )
    if args.top_k <= 0:
        raise SystemExit("--top-k must be greater than 0")

    load_dotenv(BACKEND_DIR / ".env")
    get_settings.cache_clear()
    settings = get_settings()
    configure_logging(settings.app_log_dir, settings.app_log_level)
    services = build_services(settings)

    started_at = datetime.now().astimezone()
    report_paths = resolve_report_paths(
        category="ranking_correlation",
        output_arg=args.output,
        started_at=started_at,
        default_stem="ranking_report",
    )

    # Step 1: Get resume
    resume = services.resume_pipeline.get_resume(args.resume_id)
    if resume is None:
        print(f"[error] Resume '{args.resume_id}' not found.")
        return 1

    print(f"[info] 简历: {resume.basic_info.name} ({resume.id})")
    print(f"[info] 开始算法匹配 (top_k={args.top_k})...")

    # Step 2: Algorithm matching
    algo_start = perf_counter()
    matches = services.matching_service.recommend(resume.id, args.top_k)
    algo_duration = round((perf_counter() - algo_start) * 1000, 2)

    if not matches:
        print("[error] 算法未返回匹配结果，请确保岗位库已导入。")
        return 1

    print(f"[info] 算法返回 {len(matches)} 个结果 ({algo_duration} ms)")

    # Step 3: LLM scoring for each match
    llm_client = services.resume_pipeline.llm_client
    llm_results: list[dict[str, Any]] = []
    llm_start = perf_counter()

    for i, match in enumerate(matches):
        job_payload = asdict(match.job)
        job_context = build_job_context_text(job_payload)
        print(f"[info] LLM 打分 {i + 1}/{len(matches)}: {match.job.title} ({match.job.company})...", end=" ", flush=True)
        try:
            score_start = perf_counter()
            result = llm_client.score_job_match(resume.raw_text, job_context)
            score_ms = round((perf_counter() - score_start) * 1000, 2)
            print(f"→ {result['score']}分 ({score_ms} ms)")
        except Exception as exc:
            print(f"→ 失败: {exc}")
            result = {"score": 0, "reasoning": f"LLM调用失败: {exc}", "subscores": {}}

        llm_results.append({
            "job_id": match.job.id,
            "job_title": match.job.title,
            "company": match.job.company,
            "algo_score": match.breakdown.total,
            "llm_score": result["score"],
            "llm_reasoning": result["reasoning"],
            "llm_subscores": result.get("subscores") or {},
        })

    llm_duration = round((perf_counter() - llm_start) * 1000, 2)
    print(f"[info] LLM 打分完成 ({llm_duration} ms)")

    # Step 4: Build rankings
    algo_order = [r["job_id"] for r in llm_results]
    llm_sorted = sorted(llm_results, key=llm_sort_key, reverse=True)
    llm_order = [r["job_id"] for r in llm_sorted]

    llm_rank_map = {job_id: rank + 1 for rank, job_id in enumerate(llm_order)}

    # Step 5: Compute Spearman
    rho = spearman_rho(algo_order, llm_order)
    print(f"[result] Spearman ρ = {rho}")

    # Step 6: Build comparison table
    comparisons: list[dict[str, Any]] = []
    for algo_rank, item in enumerate(llm_results, start=1):
        llm_rank = llm_rank_map[item["job_id"]]
        comparisons.append({
            "index": algo_rank,
            "job_id": item["job_id"],
            "job_title": item["job_title"],
            "company": item["company"],
            "algo_rank": algo_rank,
            "algo_score": item["algo_score"],
            "llm_rank": llm_rank,
            "llm_score": item["llm_score"],
            "rank_diff": algo_rank - llm_rank,
            "llm_reasoning": item["llm_reasoning"],
        })

    # Step 7: Build report
    report: dict[str, Any] = {
        "run_at": started_at.isoformat(timespec="seconds"),
        "resume_id": resume.id,
        "resume_name": resume.basic_info.name,
        "match_count": len(matches),
        "spearman_rho": rho,
        "algo_duration_ms": algo_duration,
        "llm_duration_ms": llm_duration,
        "algo_order": algo_order,
        "llm_order": llm_order,
        "comparisons": comparisons,
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
