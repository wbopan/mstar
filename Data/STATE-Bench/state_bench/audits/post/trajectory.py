"""Post-run trajectory structure checks."""

from __future__ import annotations

import re
from typing import Any

from state_bench.audits._types import AuditFinding, CheckResult, DomainAuditConfig, Severity
from state_bench.audits.post._shared import completion_pass, expects_no_action, is_info_task

REQUIRED_TRAJECTORY_FIELDS = ["task_id", "user_id", "task_summary", "conversation"]
DOLLAR_RE = re.compile(r"\$(\d+(?:\.\d{2})?)")
BARE_INT_RE = re.compile(r"(?<![a-zA-Z_\"-])(\d+)(?![a-zA-Z_\"])")
STATUS_KEYWORDS = {
    "cancelled",
    "returned",
    "refunded",
    "confirmed",
    "rejected",
    "denied",
    "exchanged",
    "replaced",
    "compensated",
}
def check_trajectory_structure(trajectories: list[dict[str, Any]], cfg: DomainAuditConfig) -> CheckResult:
    """Validate trajectory JSON structure."""
    result = CheckResult(check_name="Trajectory structure")
    for traj in trajectories:
        tid = traj.get("task_id", "<unknown>")
        run = traj.get("_run", "?")

        for field in REQUIRED_TRAJECTORY_FIELDS:
            if field not in traj:
                result.findings.append(
                    AuditFinding(Severity.CRITICAL, result.check_name, f"{tid}/{run}", f"missing field '{field}'")
                )

        # Conversation should be non-empty
        conv = traj.get("conversation", [])
        if not conv:
            result.findings.append(
                AuditFinding(Severity.CRITICAL, result.check_name, f"{tid}/{run}", "empty conversation")
            )

        # Canonical completion score check
        score = traj.get("task_completion_pass")
        if score is None and conv:
            result.findings.append(
                AuditFinding(
                    Severity.MODERATE,
                    result.check_name,
                    f"{tid}/{run}",
                    "task_completion_pass is null — completion scoring has not been run",
                    details={"completion_unscored": True},
                )
            )
        elif score is not None and score not in {0, 1}:
            result.findings.append(
                AuditFinding(
                    Severity.CRITICAL,
                    result.check_name,
                    f"{tid}/{run}",
                    f"task_completion_pass {score} out of range {{0,1}}",
                )
            )

    return result


def check_termination(trajectories: list[dict[str, Any]], cfg: DomainAuditConfig) -> CheckResult:
    """Verify all conversations terminated properly."""
    result = CheckResult(check_name="Termination")
    for traj in trajectories:
        tid = traj.get("task_id", "<unknown>")
        run = traj.get("_run", "?")
        conv = traj.get("conversation", [])

        if not conv:
            continue

        # Check if conversation has [TASK_DONE] marker or hit max turns
        has_task_done = False
        for msg in conv:
            content = msg.get("content", "")
            if isinstance(content, str) and "[TASK_DONE]" in content:
                has_task_done = True
                break

        if traj.get("error"):
            continue  # Error trajectories may not terminate normally

        if not has_task_done:
            # Not necessarily CRITICAL — could have hit max turns
            result.findings.append(
                AuditFinding(Severity.INFO, result.check_name, f"{tid}/{run}", "no [TASK_DONE] marker in conversation")
            )

    return result


def check_state_diff_consistency(
    trajectories: list[dict[str, Any]],
    task_jsons: dict[str, dict[str, Any]],
    cfg: DomainAuditConfig,
) -> CheckResult:
    """Check state_diff consistency with task expectations."""
    result = CheckResult(check_name="State diff consistency")

    for traj in trajectories:
        tid = traj.get("task_id", "<unknown>")
        run = traj.get("_run", "?")
        passed = completion_pass(traj)
        state_diff = traj.get("state_diff", {})

        task_json = task_jsons.get(tid, {})

        # Determine if this is an info-only or no-action task
        task_summary = task_json.get("task_summary", "").lower()
        info_task = is_info_task(tid, task_summary)
        no_action_expected = expects_no_action(task_summary)

        diff_is_empty = not state_diff or (
            not state_diff.get("created") and not state_diff.get("modified") and not state_diff.get("deleted")
        )

        if passed and not info_task and not no_action_expected and diff_is_empty:
            # Passed action task with no state changes — suspicious
            result.findings.append(
                AuditFinding(
                    Severity.MODERATE,
                    result.check_name,
                    f"{tid}/{run}",
                    "passed action task with empty state_diff",
                )
            )

    return result


def check_task_summary_vs_state_diff(
    trajectories: list[dict[str, Any]],
    task_jsons: dict[str, dict[str, Any]],
    cfg: DomainAuditConfig,
) -> CheckResult:
    """Cross-reference task_summary against state_diff for passing trajectories."""
    result = CheckResult(check_name="Task summary vs state_diff")

    for traj in trajectories:
        tid = traj.get("task_id", "<unknown>")
        run = traj.get("_run", "?")

        if completion_pass(traj) is not True:
            continue  # Only check passing trajectories

        task_json = task_jsons.get(tid, {})
        task_summary = task_json.get("task_summary", "")
        info_task = is_info_task(tid, task_summary)
        no_action_expected = expects_no_action(task_summary)
        if info_task or no_action_expected:
            continue

        state_diff = traj.get("state_diff", {})
        if not task_summary or not state_diff:
            continue

        diff_text = str(state_diff).lower()

        # Check dollar amounts from task_summary appear in state_diff
        # Filter out $0 — it means "no fee" and won't appear in state_diff
        expected_amounts = {int(float(m)) for m in DOLLAR_RE.findall(task_summary) if float(m) > 0}
        if expected_amounts:
            # State_diff stores amounts as bare ints (e.g. "cancellation_fee": 52)
            # so match both $-prefixed and bare numeric values
            diff_str = str(state_diff)
            diff_amounts = {int(float(m)) for m in DOLLAR_RE.findall(diff_str)}
            diff_amounts |= {int(m) for m in BARE_INT_RE.findall(diff_str) if int(m) > 0}
            missing = expected_amounts - diff_amounts
            if missing and len(missing) == len(expected_amounts):
                result.findings.append(
                    AuditFinding(
                        Severity.INFO,
                        result.check_name,
                        f"{tid}/{run}",
                        f"task_summary mentions ${sorted(expected_amounts)} but none found in state_diff"
                        " (needs LLM review to classify as agent error vs harness bug)",
                        details={"needs_llm_review": True, "mismatch_type": "summary_amounts_missing_from_diff"},
                    )
                )

        # Check status keywords from task_summary appear in state_diff
        expected_statuses = {kw for kw in STATUS_KEYWORDS if kw in task_summary.lower()}
        if expected_statuses:
            missing_statuses = {s for s in expected_statuses if s not in diff_text}
            if missing_statuses:
                result.findings.append(
                    AuditFinding(
                        Severity.INFO,
                        result.check_name,
                        f"{tid}/{run}",
                        f"task_summary mentions statuses {sorted(missing_statuses)} not found in state_diff",
                    )
                )

        # Reverse check: significant amounts in state_diff missing from task_summary.
        # If state_diff has concrete monetary changes (fees, refunds, prices) that
        # task_summary doesn't mention, the task definition may be incomplete.
        eo_amounts = {int(float(m)) for m in DOLLAR_RE.findall(task_summary)}
        # Also pick up bare numbers in task_summary (e.g. "50000 points")
        eo_amounts |= {int(m) for m in BARE_INT_RE.findall(task_summary) if int(m) > 0}
        diff_monetary = _extract_monetary_from_state_diff(state_diff)
        missing_from_eo = {v for v in diff_monetary.values() if v > 0} - eo_amounts
        if missing_from_eo:
            # Build detail: which fields have amounts not in task_summary
            details = []
            for field, val in sorted(diff_monetary.items()):
                if val > 0 and val not in eo_amounts:
                    details.append(f"{field}={val}")
            if details:
                result.findings.append(
                    AuditFinding(
                        Severity.INFO,
                        result.check_name,
                        f"{tid}/{run}",
                        f"state_diff has amounts not in task_summary: {', '.join(details)}"
                        " (needs LLM review to classify as agent error vs harness bug)",
                        details={"needs_llm_review": True, "mismatch_type": "diff_amounts_missing_from_summary"},
                    )
                )

        # Reverse check: preference fields in state_diff not mentioned in task_summary.
        # For booking/update tasks, preferences (seat_type, meal, cabin_class) may need
        # to be called out explicitly in the task definition.
        diff_prefs = _extract_preference_fields_from_state_diff(state_diff)
        if diff_prefs:
            eo_lower = task_summary.lower()
            missing_prefs = [
                f"{field}={value}" for field, value in diff_prefs.items() if str(value).lower() not in eo_lower
            ]
            if missing_prefs:
                result.findings.append(
                    AuditFinding(
                        Severity.INFO,
                        result.check_name,
                        f"{tid}/{run}",
                        f"state_diff has preferences not in task_summary: {', '.join(missing_prefs)}",
                    )
                )

    return result


# Monetary field names common across domains (fees, refunds, prices, compensation)
_MONETARY_FIELD_KEYWORDS = {
    "fee",
    "refund",
    "amount",
    "price",
    "paid",
    "cost",
    "compensation",
    "credit",
    "discount",
    "total",
    "subtotal",
    "shipping",
}


def _extract_monetary_from_state_diff(state_diff: dict[str, Any]) -> dict[str, int]:
    """Extract field_name -> amount for monetary fields in state_diff modifications.

    Looks at 'modified' entries where the new value is a positive number and the
    field name suggests it's a monetary amount (fee, refund, price, etc.).
    """
    amounts: dict[str, int] = {}
    modified = state_diff.get("modified", {})
    for _entity_type, entities in modified.items():
        for _eid, changes in entities.items():
            for field, change in changes.items():
                if not isinstance(change, dict):
                    continue
                new_val = change.get("new")
                if not isinstance(new_val, int | float) or new_val <= 0:
                    continue
                # Check if field name looks monetary
                field_lower = field.lower()
                if any(kw in field_lower for kw in _MONETARY_FIELD_KEYWORDS):
                    amounts[field] = int(new_val)
    return amounts


# Preference fields that appear in booking/order state_diff and should be reflected in task summaries.
_PREFERENCE_FIELDS = {"seat_type", "meal_preference", "cabin_class", "room_type", "car_class"}


def _extract_preference_fields_from_state_diff(state_diff: dict[str, Any]) -> dict[str, str]:
    """Extract preference fields from created or modified entries in state_diff."""
    prefs: dict[str, str] = {}
    for section in ("created", "modified"):
        data = state_diff.get(section, {})
        for _entity_type, entities in data.items():
            for _eid, record_or_changes in entities.items():
                if section == "created":
                    # record_or_changes is the full record
                    for field in _PREFERENCE_FIELDS:
                        if field in record_or_changes:
                            prefs[field] = str(record_or_changes[field])
                else:
                    # record_or_changes is {field: {old, new}}
                    for field in _PREFERENCE_FIELDS:
                        if field in record_or_changes:
                            change = record_or_changes[field]
                            if isinstance(change, dict):
                                prefs[field] = str(change.get("new", ""))
    return prefs
