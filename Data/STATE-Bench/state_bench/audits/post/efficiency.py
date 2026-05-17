"""Post-run efficiency checks: optimal vs actual turns/tools."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from state_bench.audits._types import AuditFinding, CheckResult, DomainAuditConfig, Severity
from state_bench.audits.post._shared import completion_pass


def check_efficiency(trajectories: list[dict[str, Any]], cfg: DomainAuditConfig) -> CheckResult:
    """For tasks passing all N runs, compute waste vs optimal baselines."""
    result = CheckResult(check_name="Efficiency")

    if not cfg.optimal_baselines:
        return result

    # Group trajectories by task_id
    by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for traj in trajectories:
        tid = traj.get("task_id", "<unknown>")
        by_task[tid].append(traj)

    for tid, runs in sorted(by_task.items()):
        if tid not in cfg.optimal_baselines:
            continue

        # Only evaluate tasks that pass all runs
        if not all(completion_pass(r) is True for r in runs):
            continue

        opt_turns, opt_tools = cfg.optimal_baselines[tid]
        avg_turns = sum(r.get("turns", 0) for r in runs) / len(runs)
        avg_tools = sum(r.get("tool_calls", 0) for r in runs) / len(runs)

        turn_waste = avg_turns - opt_turns
        tool_waste = avg_tools - opt_tools

        if turn_waste > 2 or tool_waste > 4:
            result.findings.append(
                AuditFinding(
                    Severity.INFO,
                    result.check_name,
                    tid,
                    f"waste: +{turn_waste:.1f} turns, +{tool_waste:.1f} tools "
                    f"(avg={avg_turns:.1f}/{avg_tools:.1f}, optimal={opt_turns}/{opt_tools})",
                )
            )

    return result
