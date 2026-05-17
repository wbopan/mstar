"""Cross-reference checks: user IDs, entity existence, ownership."""

from __future__ import annotations

import re
from typing import Any

from state_bench.audits._types import AuditFinding, CheckResult, DomainAuditConfig, Severity


def _extract_entity_ids(task: dict[str, Any], cfg: DomainAuditConfig) -> set[str]:
    """Extract all entity IDs from relevant text fields using domain patterns."""
    texts = [
        task.get("opening_message", ""),
        task.get("task_summary", ""),
        task.get("user_simulator", {}).get("user_sim_context", ""),
    ]
    for item in task.get("user_simulator", {}).get("known_info", []):
        texts.append(str(item))
    combined = " ".join(texts)

    ids: set[str] = set()
    for pattern in cfg.entity_patterns:
        ids.update(pattern.regex.findall(combined))
    return ids


def _env_index_for_task(task: dict[str, Any], env_indexes_by_task: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return env_indexes_by_task.get(task.get("task_id", ""), {})


def check_user_ids(
    tasks: list[dict[str, Any]],
    env_indexes_by_task: dict[str, dict[str, Any]],
    cfg: DomainAuditConfig,
) -> CheckResult:
    """Verify user_id exists in the task-local environment and CUSTOMER_ATTRIBUTES."""
    result = CheckResult(check_name="User ID validity")
    for task in tasks:
        tid = task.get("task_id", "<unknown>")
        env_index = _env_index_for_task(task, env_indexes_by_task)
        customer_ids = env_index.get("customer_ids", set())
        uid = task.get("user_id", "")
        if uid and uid not in customer_ids:
            result.findings.append(
                AuditFinding(Severity.CRITICAL, result.check_name, tid, f"user_id '{uid}' not in task environment")
            )
        if uid and uid not in cfg.customer_attributes:
            result.findings.append(
                AuditFinding(Severity.CRITICAL, result.check_name, tid, f"user_id '{uid}' not in CUSTOMER_ATTRIBUTES")
            )
    return result


def check_entity_crossrefs(
    tasks: list[dict[str, Any]],
    env_indexes_by_task: dict[str, dict[str, Any]],
    cfg: DomainAuditConfig,
) -> CheckResult:
    """Verify entity IDs referenced in tasks exist in the task-local environment."""
    result = CheckResult(check_name="Entity cross-refs")
    for task in tasks:
        tid = task.get("task_id", "<unknown>")
        env_index = _env_index_for_task(task, env_indexes_by_task)
        if "-edge_" in tid.lower():
            continue

        entities = _extract_entity_ids(task, cfg)
        for eid in sorted(entities):
            if eid in cfg.known_invalid_entities:
                continue
            if any(eid.startswith(dp) for dp in cfg.dynamic_entity_prefixes):
                continue

            for pattern in cfg.entity_patterns:
                if re.match(pattern.regex.pattern.replace(r"\b", ""), eid):
                    valid_set = env_index.get(pattern.env_lookup_key, set())
                    if isinstance(valid_set, dict):
                        valid_set = set(valid_set.keys())
                    if eid not in valid_set:
                        result.findings.append(
                            AuditFinding(
                                Severity.CRITICAL,
                                result.check_name,
                                tid,
                                f"entity '{eid}' not found in task environment ({pattern.env_lookup_key})",
                            )
                        )
                    break
    return result


def check_entity_ownership(
    tasks: list[dict[str, Any]],
    env_indexes_by_task: dict[str, dict[str, Any]],
    cfg: DomainAuditConfig,
) -> CheckResult:
    """Verify entities with ownership fields belong to the task's user."""
    result = CheckResult(check_name="Entity ownership")
    for task in tasks:
        tid = task.get("task_id", "<unknown>")
        uid = task.get("user_id", "")
        env_index = _env_index_for_task(task, env_indexes_by_task)
        entities = _extract_entity_ids(task, cfg)

        for eid in sorted(entities):
            for pattern in cfg.entity_patterns:
                if pattern.ownership_lookup_key and pattern.regex.search(eid):
                    ownership_map = env_index.get(pattern.ownership_lookup_key, {})
                    owner = ownership_map.get(eid)
                    if owner is not None and owner != uid:
                        result.findings.append(
                            AuditFinding(
                                Severity.CRITICAL,
                                result.check_name,
                                tid,
                                f"entity '{eid}' belongs to '{owner}', not task user '{uid}'",
                            )
                        )
                    break
    return result
