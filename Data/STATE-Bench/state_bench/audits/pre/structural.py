"""Structural checks: schema, duplicates, placeholders, TASK_DONE, file count, task summary."""

from __future__ import annotations

import re
from typing import Any

from state_bench.audits._types import AuditFinding, CheckResult, DomainAuditConfig, Severity

PLACEHOLDER_RE = re.compile(r"\{\{[^}]+\}\}|\{[a-zA-Z_][a-zA-Z0-9_]*\}")
DOLLAR_RE = re.compile(r"\$\d+(?:\.\d{2})?")
STATUS_KEYWORDS = {
    "cancelled",
    "returned",
    "refunded",
    "confirmed",
    "rejected",
    "denied",
    "approved",
    "exchanged",
    "exchange processed",
    "replacement",
    "replaced",
    "repair",
    "processed",
    "compensated",
    "investigation",
    "delivered",
    "shipped",
}


NO_ACTION_PHRASES = [
    "no state change expected",
    "agent must:",
    "deny",
    "denied",
    "handle invalid",
    "gracefully",
    "out of stock",
    "waitlist",
    "store credit",
    "suggest return+rebuy",
    "explain",
]


def check_file_count(tasks: list[dict[str, Any]], cfg: DomainAuditConfig) -> CheckResult:
    """Verify task count matches expected."""
    result = CheckResult(check_name="File count")
    if cfg.expected_task_count is not None and len(tasks) != cfg.expected_task_count:
        result.findings.append(
            AuditFinding(
                severity=Severity.CRITICAL,
                check_name=result.check_name,
                task_id=None,
                message=f"Expected {cfg.expected_task_count} tasks, found {len(tasks)}",
            )
        )
    return result


def check_schema(tasks: list[dict[str, Any]], cfg: DomainAuditConfig) -> CheckResult:
    """Verify all required fields present in every task."""
    result = CheckResult(check_name="Schema compliance")
    for task in tasks:
        tid = task.get("task_id", "<unknown>")
        for f in cfg.required_top_fields:
            if f not in task:
                result.findings.append(
                    AuditFinding(Severity.CRITICAL, result.check_name, tid, f"missing top-level field '{f}'")
                )
        if "task_info" in task:
            result.findings.append(
                AuditFinding(Severity.CRITICAL, result.check_name, tid, "legacy task_info field is not allowed")
            )
        summary = task.get("task_summary", "")
        if not isinstance(summary, str) or not summary.strip():
            result.findings.append(
                AuditFinding(Severity.CRITICAL, result.check_name, tid, "missing or empty task_summary")
            )
        sim = task.get("user_simulator", {})
        for f in cfg.required_simulator_fields:
            if f not in sim:
                result.findings.append(
                    AuditFinding(Severity.CRITICAL, result.check_name, tid, f"missing user_simulator.{f}")
                )
    return result


def check_duplicate_ids(tasks: list[dict[str, Any]], cfg: DomainAuditConfig) -> CheckResult:
    """Verify no duplicate task_ids."""
    result = CheckResult(check_name="No duplicate task_ids")
    seen: dict[str, int] = {}
    for task in tasks:
        tid = task.get("task_id", "<unknown>")
        seen[tid] = seen.get(tid, 0) + 1
    for tid, count in seen.items():
        if count > 1:
            result.findings.append(
                AuditFinding(Severity.CRITICAL, result.check_name, tid, f"duplicate task_id (appears {count} times)")
            )
    return result


def _scan_placeholders(value: object, path: str, found: list[str]) -> None:
    """Recursively scan for unresolved placeholders."""
    if isinstance(value, str):
        for m in PLACEHOLDER_RE.finditer(value):
            found.append(f"{path}: {m.group()}")
    elif isinstance(value, list):
        for i, item in enumerate(value):
            _scan_placeholders(item, f"{path}[{i}]", found)
    elif isinstance(value, dict):
        for k, v in value.items():
            _scan_placeholders(v, f"{path}.{k}", found)


def check_placeholders(tasks: list[dict[str, Any]], cfg: DomainAuditConfig) -> CheckResult:
    """Verify no unresolved {{...}} or {var_name} placeholders."""
    result = CheckResult(check_name="No unresolved placeholders")
    for task in tasks:
        tid = task.get("task_id", "<unknown>")
        found: list[str] = []
        _scan_placeholders(task, "root", found)
        for placeholder in found:
            # Check exemptions
            if any(exempt in placeholder for exempt in cfg.placeholder_exemptions):
                continue
            result.findings.append(
                AuditFinding(Severity.CRITICAL, result.check_name, tid, f"unresolved placeholder: {placeholder}")
            )
    return result


def check_task_done(tasks: list[dict[str, Any]], cfg: DomainAuditConfig) -> CheckResult:
    """Verify task_rules contain conversation-ending guidance."""
    result = CheckResult(check_name="TASK_DONE path")
    done_keywords = [
        "task_done",
        "[task_done]",
        "done",
        "end",
        "confirm",
        "accept",
        "say goodbye",
        "end the conversation",
        "keep responses",
        "never mind",
        "no worries",
        "go ahead",
    ]
    for task in tasks:
        tid = task.get("task_id", "<unknown>")
        rules = task.get("user_simulator", {}).get("task_rules", [])
        rules_text = " ".join(rules).lower()
        if not any(kw in rules_text for kw in done_keywords):
            result.findings.append(
                AuditFinding(Severity.MINOR, result.check_name, tid, "no TASK_DONE or conversation-ending guidance")
            )
    return result


def check_task_summary_completeness(tasks: list[dict[str, Any]], cfg: DomainAuditConfig) -> CheckResult:
    """Verify task_summary contains concrete, verifiable claims."""
    result = CheckResult(check_name="Task summary completeness")

    for task in tasks:
        tid = task.get("task_id", "<unknown>")
        eo = task.get("task_summary", "")
        tid_lower = tid.lower()
        eo_lower = eo.lower()
        is_info_task = (
            "-info_" in tid_lower
            or "-policy_" in tid_lower
            or "information-only" in eo_lower
            or "policy-only" in eo_lower
            or "informational only" in eo_lower
        )

        if not eo:
            result.findings.append(AuditFinding(Severity.CRITICAL, result.check_name, tid, "empty task_summary"))
            continue

        if len(eo) < 20:
            result.findings.append(
                AuditFinding(
                    Severity.MODERATE, result.check_name, tid, f"task_summary too short ({len(eo)} chars): '{eo}'"
                )
            )

        # For action tasks (not info-only), task_summary should contain
        # at least one concrete indicator: dollar amount OR action/result keyword.
        if not is_info_task:
            has_dollar = bool(DOLLAR_RE.search(eo))
            has_status = any(kw in eo_lower for kw in STATUS_KEYWORDS)
            explicit_no_action = any(phrase in eo_lower for phrase in NO_ACTION_PHRASES)
            if not has_dollar and not has_status and not explicit_no_action:
                result.findings.append(
                    AuditFinding(
                        Severity.MINOR,
                        result.check_name,
                        tid,
                        "task_summary lacks concrete verifiable claims (no dollar amounts or action/status keywords)",
                    )
                )

    return result
