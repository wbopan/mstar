"""Distribution checks: family coverage."""

from __future__ import annotations

from typing import Any

from state_bench.audits._types import CheckResult, DomainAuditConfig


def check_family_coverage(tasks: list[dict[str, Any]], cfg: DomainAuditConfig) -> CheckResult:
    """No-op: task-family metadata is no longer part of the task schema."""
    return CheckResult(check_name="Family coverage")


def check_category_distribution(tasks: list[dict[str, Any]], cfg: DomainAuditConfig) -> CheckResult:
    """No-op: legacy category metadata is no longer part of the task schema."""
    return CheckResult(check_name="Category distribution")
