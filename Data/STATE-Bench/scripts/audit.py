#!/usr/bin/env python3
"""Unified audit runner for all benchmark domains.

Usage:
    uv run python scripts/audit.py --domain travel --phase pre
    uv run python scripts/audit.py --domain customer_support --phase post --num-runs 5
    uv run python scripts/audit.py --domain travel --phase all
    uv run python scripts/audit.py --domain travel --phase pre --task 1-cancel_economy_domestic
    uv run python scripts/audit.py --domain travel --phase pre --format json
    uv run python scripts/audit.py --domain travel --phase post --runs-dir outputs/travel_v2 --llm-review
    uv run python scripts/audit.py --domain travel --phase post --llm-review --max-llm-tasks 10
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from state_bench.audits import run_post_audit, run_pre_audit
from state_bench.audits._report import print_json_report, print_text_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Unified benchmark audit")
    parser.add_argument(
        "--domain",
        required=True,
        choices=["travel", "customer_support", "shopping_assistant"],
        help="Domain to audit",
    )
    parser.add_argument(
        "--phase",
        required=True,
        choices=["pre", "post", "all"],
        help="Audit phase: pre (task definitions), post (trajectories), or all",
    )
    parser.add_argument("--task", type=str, default=None, help="Audit a single task (task_id substring match)")
    parser.add_argument("--num-runs", type=int, default=3, help="Number of runs for post-run audit (default: 3)")
    parser.add_argument("--runs-dir", type=str, default=None, help="Override outputs directory for post-run audit")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format (default: text)")
    parser.add_argument(
        "--llm-review",
        action="store_true",
        help="Enable LLM-based trajectory review (requires Azure OpenAI credentials, expensive)",
    )
    parser.add_argument(
        "--max-llm-tasks",
        type=int,
        default=None,
        help="Max trajectories for LLM review (for cost control). Default: all.",
    )
    parser.add_argument(
        "--failure-attribution",
        action="store_true",
        help="Write customer_support harness attribution reports for saved trajectories.",
    )
    args = parser.parse_args()

    runs_dir = Path(args.runs_dir) if args.runs_dir else None
    reports = []

    if args.phase in ("pre", "all"):
        reports.append(run_pre_audit(args.domain, single_task=args.task))

    if args.phase in ("post", "all"):
        reports.append(
            run_post_audit(
                args.domain,
                num_runs=args.num_runs,
                single_task=args.task,
                runs_dir=runs_dir,
                llm_review=args.llm_review,
                max_llm_tasks=args.max_llm_tasks,
                failure_attribution=args.failure_attribution,
            )
        )

    exit_code = 0
    for report in reports:
        if args.format == "json":
            print_json_report(report)
        else:
            print_text_report(report)
        if not report.passed:
            exit_code = 1

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
