"""Core types for the unified audit framework."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class Severity(Enum):
    CRITICAL = "CRITICAL"
    MODERATE = "MODERATE"
    MINOR = "MINOR"
    INFO = "INFO"


@dataclass
class AuditFinding:
    """A single issue found by an audit check."""

    severity: Severity
    check_name: str
    task_id: str | None  # None for global checks
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class CheckResult:
    """Result of a single check function."""

    check_name: str
    findings: list[AuditFinding] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not any(f.severity == Severity.CRITICAL for f in self.findings)


@dataclass
class AuditReport:
    """Aggregate report across all checks in a phase (pre or post)."""

    domain: str
    phase: str  # "pre" or "post"
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def all_findings(self) -> list[AuditFinding]:
        return [f for c in self.checks for f in c.findings]

    @property
    def passed(self) -> bool:
        return not any(f.severity == Severity.CRITICAL for f in self.all_findings)

    def count_by_severity(self) -> dict[Severity, int]:
        counts = {s: 0 for s in Severity}
        for f in self.all_findings:
            counts[f.severity] += 1
        return counts

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "phase": self.phase,
            "passed": self.passed,
            "counts": {s.value: c for s, c in self.count_by_severity().items()},
            "checks": [
                {
                    "name": cr.check_name,
                    "passed": cr.passed,
                    "findings": [
                        {"severity": f.severity.value, "task_id": f.task_id, "message": f.message} for f in cr.findings
                    ],
                }
                for cr in self.checks
            ],
        }


@dataclass
class EntityPattern:
    """A domain-specific entity ID pattern for cross-reference checks."""

    prefix: str  # "BK", "ORD", "SP"
    regex: re.Pattern[str]  # compiled pattern like re.compile(r"\bBK-\d+\b")
    env_lookup_key: str  # key in the env index dict, e.g. "booking_ids"
    ownership_field: str | None = None  # field name on the entity that holds the owner user_id
    ownership_lookup_key: str | None = None  # key in env_index for ownership mapping, e.g. "order_owner"


DEFAULT_REQUIRED_TOP_FIELDS = ["task_id", "task_summary", "user_id", "now", "opening_message", "user_simulator"]
DEFAULT_REQUIRED_SIMULATOR_FIELDS = ["personality", "user_sim_context", "known_info", "unknown_info", "task_rules"]

@dataclass(kw_only=True)
class DomainAuditConfig:
    """Domain-specific configuration plugged into the audit framework."""

    name: str

    # Structural
    expected_task_count: int | None  # None = skip count check
    required_top_fields: list[str] = field(default_factory=lambda: list(DEFAULT_REQUIRED_TOP_FIELDS))
    required_simulator_fields: list[str] = field(default_factory=lambda: list(DEFAULT_REQUIRED_SIMULATOR_FIELDS))
    # Entity patterns for cross-ref checks
    entity_patterns: list[EntityPattern] = field(default_factory=list)
    known_invalid_entities: set[str] = field(default_factory=set)


    # Solvability
    read_tools: set[str] = field(default_factory=set)
    write_tools: set[str] = field(default_factory=set)
    policy_gate_map: dict[str, list[str]] = field(default_factory=dict)

    # Task-environment loader — builds env_index from a task-local environment JSON
    build_env_index: Callable[[dict[str, Any]], dict[str, Any]] = field(default=lambda raw: {})

    # Customer attributes
    customer_attributes: dict[str, dict[str, Any]] = field(default_factory=dict)

    # Placeholder exemptions (patterns to ignore in placeholder check)
    placeholder_exemptions: set[str] = field(default_factory=set)

    # Dynamic entity prefixes (exempt from cross-ref, e.g. CART- with task prefix)
    dynamic_entity_prefixes: list[str] = field(default_factory=list)

    # Scenario loader (for solvability + policy math) — returns {task_id: scenario_data}
    load_scenarios: Callable[[], dict[str, dict[str, Any]]] | None = None

    # Policy math verifier (domain-specific, returns CheckResult)
    policy_math_verifier: Callable[[], CheckResult] | None = None

    # Efficiency baselines — task_id -> (optimal_turns, optimal_tools)
    optimal_baselines: dict[str, tuple[int, int]] | None = None
