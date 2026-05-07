"""Post-run classification: detect false passes and false fails."""

from __future__ import annotations

from typing import Any

from state_bench.audits._types import AuditFinding, CheckResult, DomainAuditConfig, Severity
from state_bench.audits.post._shared import completion_pass, expects_no_action, is_info_task


def _extract_tool_calls(conversation: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract all tool calls from assistant messages."""
    calls: list[dict[str, Any]] = []
    for msg in conversation:
        if msg.get("role") != "assistant":
            continue
        for tc in msg.get("tool_calls") or []:
            if isinstance(tc, dict):
                calls.append(tc)
    return calls


def _has_write_tool_call(conversation: list[dict[str, Any]], write_tools: set[str]) -> bool:
    """Check if any write tool was called."""
    for tc in _extract_tool_calls(conversation):
        name = tc.get("name", tc.get("function", {}).get("name", ""))
        if name in write_tools:
            return True
    return False


def _count_tool_errors(conversation: list[dict[str, Any]]) -> int:
    """Count tool calls whose recorded result contains an error."""
    count = 0
    for tc in _extract_tool_calls(conversation):
        result = tc.get("result")
        if isinstance(result, dict) and ("error" in result or result.get("status") == "rejected"):
            count += 1
    return count


def check_false_passes(
    trajectories: list[dict[str, Any]],
    task_jsons: dict[str, dict[str, Any]],
    cfg: DomainAuditConfig,
) -> CheckResult:
    """Detect harness bugs that may have inflated scores (false passes).

    Checks:
    - Agent passed but never called write tools on an action task
    - Multiple tool errors occurred but the trajectory still passed
    """
    result = CheckResult(check_name="False pass detection")

    for traj in trajectories:
        tid = traj.get("task_id", "<unknown>")
        run = traj.get("_run", "?")

        passed = completion_pass(traj)
        if passed is not True:
            continue  # Only check passing trajectories

        task_json = task_jsons.get(tid, {})
        task_summary = task_json.get("task_summary", "")
        info_task = is_info_task(tid, task_summary)
        no_action_expected = expects_no_action(task_summary)

        conv = traj.get("conversation", [])

        # FP-1: Passed action task with no write tool calls.
        if not info_task and not no_action_expected and not _has_write_tool_call(conv, cfg.write_tools):
            result.findings.append(
                AuditFinding(
                    Severity.MODERATE,
                    result.check_name,
                    f"{tid}/{run}",
                    "passed action task without any write tool calls — possible harness issue",
                )
            )

        # FP-2: Multiple tool errors but still passed
        error_count = _count_tool_errors(conv)
        if error_count >= 3:
            result.findings.append(
                AuditFinding(
                    Severity.MODERATE,
                    result.check_name,
                    f"{tid}/{run}",
                    f"passed with {error_count} tool errors — possible harness issue",
                )
            )

    return result


def check_false_fails(
    trajectories: list[dict[str, Any]],
    task_jsons: dict[str, dict[str, Any]],
    cfg: DomainAuditConfig,
) -> CheckResult:
    """Detect harness bugs that may have deflated scores (false fails).

    Checks:
    - Tool handler returned error for seemingly valid parameters (env bug)
    - Task references entities not in environment (task def bug)
    - Completion result seems inconsistent with observed behavior
    """
    result = CheckResult(check_name="False fail detection")

    for traj in trajectories:
        tid = traj.get("task_id", "<unknown>")
        run = traj.get("_run", "?")

        passed = completion_pass(traj)
        if passed is not False:
            continue  # Only check failing trajectories

        conv = traj.get("conversation", [])
        score = traj.get("task_completion_pass")

        # FF-1: Failed completion despite meaningful state changes = possible harness issue
        state_diff = traj.get("state_diff", {})
        has_changes = state_diff and (
            state_diff.get("created") or state_diff.get("modified") or state_diff.get("deleted")
        )
        if score == 0 and has_changes:
            result.findings.append(
                AuditFinding(
                    Severity.INFO,
                    result.check_name,
                    f"{tid}/{run}",
                    "task_completion_pass=0 with non-empty state_diff — may warrant manual review",
                )
            )

        # FF-2: Error in trajectory (not tool error, but harness error)
        error = traj.get("error")
        if error:
            result.findings.append(
                AuditFinding(
                    Severity.MODERATE,
                    result.check_name,
                    f"{tid}/{run}",
                    f"trajectory has error: {error[:200]}",
                )
            )

        # FF-3: Tool errors that look like environment bugs (not user-facing validation failures)
        for tc in _extract_tool_calls(conv):
            tool_result = tc.get("result")
            if not isinstance(tool_result, dict):
                continue
            error_text = str(tool_result.get("error", ""))
            if "internal error" in error_text.lower() or "traceback" in error_text.lower():
                result.findings.append(
                    AuditFinding(
                        Severity.CRITICAL,
                        result.check_name,
                        f"{tid}/{run}",
                        f"tool returned internal error: {error_text[:200]}",
                    )
                )

    return result
