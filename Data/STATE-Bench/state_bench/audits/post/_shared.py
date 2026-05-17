"""Shared helpers for post-run audit heuristics."""

from __future__ import annotations

from typing import Any

NO_ACTION_PHRASES = [
    "no changes",
    "remains unchanged",
    "no compensation",
    "no action",
    "do not",
    "does not",
    "correctly denies",
    "correctly refuses",
    "correctly identifies that",
    "no modifications",
    "unchanged",
    "recommends keeping",
    "advise against",
    "should not",
    "denied.",
    "exchange denied",
    "claim denied",
    "outside exchange window",
    "outside return window",
]


def completion_pass(traj: dict[str, Any]) -> bool | None:
    """Return canonical pass/fail from task_completion_pass only."""
    task_completion = traj.get("task_completion_pass")
    if task_completion is None:
        return None
    return task_completion == 1


def is_info_task(task_id: str, task_summary: str = "") -> bool:
    tid = task_id.lower()
    summary = task_summary.lower()
    return (
        "-info_" in tid
        or "-policy_" in tid
        or "information-only" in summary
        or "policy-only" in summary
        or "informational only" in summary
    )


def expects_no_action(task_summary: str) -> bool:
    lowered = task_summary.lower()
    return any(phrase in lowered for phrase in NO_ACTION_PHRASES)
