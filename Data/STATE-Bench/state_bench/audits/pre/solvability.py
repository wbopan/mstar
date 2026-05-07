"""Solvability checks: info path, replay sequence, policy gate, simulator info."""

from __future__ import annotations

import re
from typing import Any

from state_bench.audits._types import AuditFinding, CheckResult, DomainAuditConfig, Severity


def _extract_ids_from_text(text: str, patterns: list[re.Pattern[str]]) -> set[str]:
    ids: set[str] = set()
    for pat in patterns:
        ids.update(pat.findall(text))
    return ids


def _scenario_replay_steps(scenario: dict[str, Any]) -> list[dict[str, Any]]:
    replay_steps = scenario.get("replay_trace")
    if not isinstance(replay_steps, list):
        return []
    return [step for step in replay_steps if isinstance(step, dict) and isinstance(step.get("name"), str)]


def _step_argument_text(step: dict[str, Any]) -> str | None:
    arguments = step.get("arguments")
    if isinstance(arguments, dict) and arguments:
        pieces = [f"{key}:{value}" for key, value in sorted(arguments.items())]
        return " ".join(pieces)
    arg_text = step.get("arguments_text")
    if isinstance(arg_text, str) and arg_text:
        return arg_text
    label = step.get("label")
    if isinstance(label, str) and label:
        return label
    return None


def _policy_topic(step: dict[str, Any]) -> str | None:
    arguments = step.get("arguments")
    if isinstance(arguments, dict) and isinstance(arguments.get("topic"), str):
        return arguments["topic"]
    text = _step_argument_text(step)
    if not text:
        return None
    match = re.search(r"(?:^|\b)topic:([^\s,)]+)", text)
    if match:
        return match.group(1)
    return text.strip()


def _task_scope_ids(task: dict[str, Any], patterns: list[re.Pattern[str]]) -> set[str]:
    opening = task.get("opening_message", "")
    known_info = task.get("user_simulator", {}).get("known_info", [])
    known_text = " ".join(str(k) for k in known_info) if isinstance(known_info, list) else str(known_info)
    return _extract_ids_from_text(opening + " " + known_text, patterns)


def check_info_path(
    tasks: list[dict[str, Any]],
    scenarios: dict[str, dict[str, Any]],
    env_index: dict[str, Any],
    cfg: DomainAuditConfig,
) -> CheckResult:
    result = CheckResult(check_name="Info path")
    id_patterns = [p.regex for p in cfg.entity_patterns]

    for task in tasks:
        tid = task.get("task_id", "<unknown>")
        scenario = scenarios.get(tid)
        if not scenario:
            continue

        replay_steps = _scenario_replay_steps(scenario)
        discoverable = _task_scope_ids(task, id_patterns)

        missing_entities: set[str] = set()
        for step in replay_steps:
            arg_text = _step_argument_text(step)
            if not arg_text:
                continue
            ids_in_arg = _extract_ids_from_text(arg_text, id_patterns)
            for eid in ids_in_arg:
                if eid in discoverable or eid in missing_entities:
                    continue
                if "-edge_" in tid.lower():
                    continue
                if eid.startswith("ITEM-") and any(scope_id.startswith("ORD-") for scope_id in discoverable):
                    continue
                missing_entities.add(eid)
                result.findings.append(
                    AuditFinding(
                        Severity.MINOR,
                        result.check_name,
                        tid,
                        f"entity {eid} in replay steps not in opening/known_info (may be discoverable via tool chain)",
                    )
                )

    return result


def check_replay_sequence(
    tasks: list[dict[str, Any]],
    scenarios: dict[str, dict[str, Any]],
    cfg: DomainAuditConfig,
) -> CheckResult:
    result = CheckResult(check_name="Replay sequence")

    for task in tasks:
        tid = task.get("task_id", "<unknown>")
        scenario = scenarios.get(tid)
        if not scenario:
            continue

        replay_steps = _scenario_replay_steps(scenario)

        if not replay_steps:
            result.findings.append(AuditFinding(Severity.MINOR, result.check_name, tid, "empty replay trace"))
            continue

        first_tool = replay_steps[0]["name"]
        if first_tool not in cfg.read_tools and first_tool in cfg.write_tools:
            result.findings.append(
                AuditFinding(Severity.MINOR, result.check_name, tid, f"sequence starts with write tool '{first_tool}'")
            )

        if cfg.policy_gate_map:
            policies_seen = False
            for step in replay_steps:
                base = step["name"]
                if base == "get_policies":
                    policies_seen = True
                if base in cfg.write_tools and not policies_seen:
                    result.findings.append(
                        AuditFinding(
                            Severity.CRITICAL,
                            result.check_name,
                            tid,
                            f"write tool '{base}' before any get_policies call",
                        )
                    )
                    break

    return result


def check_policy_gate(
    tasks: list[dict[str, Any]],
    scenarios: dict[str, dict[str, Any]],
    cfg: DomainAuditConfig,
) -> CheckResult:
    result = CheckResult(check_name="Policy gate")
    if not cfg.policy_gate_map:
        return result

    for task in tasks:
        tid = task.get("task_id", "<unknown>")
        scenario = scenarios.get(tid)
        if not scenario:
            continue

        replay_steps = _scenario_replay_steps(scenario)

        policies_seen: set[str] = set()
        for step in replay_steps:
            base = step["name"]
            topic = _policy_topic(step)

            if base == "get_policies" and topic:
                policies_seen.add(topic)

            if base in cfg.policy_gate_map:
                required_topics = cfg.policy_gate_map[base]
                if not any(t in policies_seen for t in required_topics):
                    result.findings.append(
                        AuditFinding(
                            Severity.CRITICAL,
                            result.check_name,
                            tid,
                            f"{base} requires get_policies({'/'.join(required_topics)}) but only seen: {sorted(policies_seen) if policies_seen else 'none'}",
                        )
                    )

    return result


def check_simulator_info(
    tasks: list[dict[str, Any]],
    scenarios: dict[str, dict[str, Any]],
    cfg: DomainAuditConfig,
) -> CheckResult:
    result = CheckResult(check_name="Simulator info")
    for task in tasks:
        tid = task.get("task_id", "<unknown>")
        sim = task.get("user_simulator", {})
        known = sim.get("known_info", [])
        unknown = sim.get("unknown_info", [])

        if not known:
            result.findings.append(
                AuditFinding(Severity.MINOR, result.check_name, tid, "empty known_info in user_simulator")
            )
        if not unknown:
            result.findings.append(
                AuditFinding(Severity.MINOR, result.check_name, tid, "empty unknown_info in user_simulator")
            )
    return result
