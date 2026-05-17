"""Customer-support harness attribution audit.

This module is intentionally mostly deterministic. It does not attempt to
replace the task-requirements LLM judge; instead it checks the harness surfaces
that can be mechanically verified and then attributes saved pass/fail outcomes
to agent behavior or a concrete non-agent defect.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from state_bench.audits._loader import (
    REPO_ROOT,
    load_finalized_generation_results,
    load_task_environment_jsons,
)
from state_bench.audits._types import AuditFinding, CheckResult, DomainAuditConfig, Severity
from state_bench.domain import get_domain_config
from state_bench.replay import ReplayError, execute_replay_trace
from state_bench.schemas import StateDiff, TaskDefinition
from state_bench.scoring import evaluate_state_requirements

ATTRIBUTION_LABELS = {
    "PASS",
    "AGENT_ERROR",
    "TASK_BUG",
    "HARNESS_BUG",
    "JUDGE_BUG",
    "FALSE_PASS",
    "BLOCKED_AMBIGUOUS",
}


@dataclass
class TaskAudit:
    task_id: str
    valid: bool = True
    issues: list[dict[str, Any]] = field(default_factory=list)
    canonical_replay_state_pass: int | None = None
    canonical_replay_reasoning: str | None = None
    canonical_replay_error: str | None = None

    def add_issue(self, surface: str, message: str, fix: str, label: str = "TASK_BUG") -> None:
        self.valid = False
        self.issues.append({"label": label, "surface": surface, "message": message, "fix": fix})

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "valid": self.valid,
            "issues": self.issues,
            "canonical_replay_state_pass": self.canonical_replay_state_pass,
            "canonical_replay_reasoning": self.canonical_replay_reasoning,
            "canonical_replay_error": self.canonical_replay_error,
        }


@dataclass
class TrajectoryAttribution:
    task_id: str
    run: str
    label: str
    passed: bool | None
    state_requirements_met: int | None
    task_requirements_met: int | None
    reasons: list[str] = field(default_factory=list)
    fix_recommendation: str | None = None
    deterministic_checks: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "run": self.run,
            "label": self.label,
            "passed": self.passed,
            "state_requirements_met": self.state_requirements_met,
            "task_requirements_met": self.task_requirements_met,
            "reasons": self.reasons,
            "fix_recommendation": self.fix_recommendation,
            "deterministic_checks": self.deterministic_checks,
        }


def run_failure_attribution_audit(
    *,
    domain: str,
    cfg: DomainAuditConfig,
    trajectories: list[dict[str, Any]],
    task_jsons: dict[str, dict[str, Any]],
    runs_dir: Path | None = None,
    attribution_date: str | None = None,
) -> CheckResult:
    """Run deterministic harness attribution and write JSON/Markdown reports."""
    result = CheckResult(check_name="Harness failure attribution")
    if domain != "customer_support":
        result.findings.append(
            AuditFinding(
                Severity.MINOR,
                result.check_name,
                None,
                "failure attribution is currently implemented for customer_support only",
            )
        )
        return result

    date_slug = attribution_date or _date_slug()
    output_dir = runs_dir if runs_dir is not None else REPO_ROOT / "outputs" / domain
    output_dir.mkdir(parents=True, exist_ok=True)

    tasks = list(task_jsons.values())
    task_envs = load_task_environment_jsons(tasks)
    generated = load_finalized_generation_results(domain)
    task_audits = _audit_tasks(domain, cfg, task_jsons, task_envs, generated)
    policy_math_issues = _audit_policy_math(cfg, task_audits)

    attributions = [
        _attribute_trajectory(domain, cfg, traj, task_jsons, task_audits)
        for traj in trajectories
    ]

    summary = _build_summary(task_audits, attributions, policy_math_issues)
    payload = {
        "domain": domain,
        "date": date_slug,
        "summary": summary,
        "policy_math_issues": policy_math_issues,
        "task_audits": {task_id: audit.to_dict() for task_id, audit in sorted(task_audits.items())},
        "trajectory_attributions": [item.to_dict() for item in attributions],
    }

    json_path = output_dir / f"harness_audit_{date_slug}.json"
    md_path = output_dir / f"harness_audit_{date_slug}.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    md_path.write_text(_render_markdown_report(payload))

    non_agent_counts = {
        label: summary["trajectory_labels"].get(label, 0)
        for label in ("TASK_BUG", "HARNESS_BUG", "JUDGE_BUG", "FALSE_PASS", "BLOCKED_AMBIGUOUS")
    }
    non_agent_total = sum(non_agent_counts.values()) + summary["invalid_task_count"] + len(policy_math_issues)

    result.findings.append(
        AuditFinding(
            Severity.INFO,
            result.check_name,
            None,
            f"wrote harness attribution reports: {json_path} and {md_path}",
            details={"json_path": str(json_path), "markdown_path": str(md_path), "summary": summary},
        )
    )
    if non_agent_total:
        result.findings.append(
            AuditFinding(
                Severity.CRITICAL,
                result.check_name,
                None,
                f"found {non_agent_total} non-agent harness/task/judge concern(s); see {md_path}",
                details={"non_agent_counts": non_agent_counts, "invalid_task_count": summary["invalid_task_count"]},
            )
        )

    return result


def _date_slug() -> str:
    now = datetime.now()
    return f"{now.month}_{now.day}_{now.year}"


def _audit_tasks(
    domain: str,
    cfg: DomainAuditConfig,
    task_jsons: dict[str, dict[str, Any]],
    task_envs: dict[str, dict[str, Any]],
    generated: dict[str, dict[str, Any]],
) -> dict[str, TaskAudit]:
    audits = {task_id: TaskAudit(task_id=task_id) for task_id in task_jsons}
    domain_config = get_domain_config(domain)

    for task_id, task_raw in task_jsons.items():
        audit = audits[task_id]
        generated_entry = generated.get(task_id)
        if generated_entry is None:
            audit.add_issue(
                "scenario registry",
                "checked-in task is not produced by the current scenario registry",
                "Add the scenario to ALL_SCENARIOS or remove the stale checked-in task.",
            )
            continue

        generated_task = _public_task_payload(generated_entry["task"])
        if task_raw != generated_task:
            audit.add_issue(
                "task json",
                "checked-in task JSON differs from current generated task payload",
                "Regenerate the task after confirming the generated payload is intended, or fix the scenario builder.",
            )

        generated_env = generated_entry.get("task_env")
        if task_envs.get(task_id) != generated_env:
            audit.add_issue(
                "task environment",
                "checked-in task environment differs from current generated task environment",
                "Regenerate task_envs after confirming scenario data is intended, or fix the scenario builder.",
            )

        task = TaskDefinition.from_dict(task_raw)
        replay_trace = generated_entry.get("replay_trace") or []
        replay_created_records: dict[str, set[str]] = {}
        if replay_trace:
            env = domain_config.environment_class(domain_config.env_data_class.from_dict(generated_env), now=task.now)
            try:
                _executed, replay_diff = _execute_canonical_replay(env, replay_trace, allow_terminal_rejected=not bool(task.state_requirements))
            except ReplayError as exc:
                audit.canonical_replay_error = str(exc)
                audit.add_issue(
                    "canonical replay",
                    f"canonical replay cannot execute: {exc}",
                    "Fix replay_trace generation or the environment tool behavior so the authored solution is executable.",
                    label="HARNESS_BUG",
                )
            else:
                replay_created_records = {
                    entity_type: set(records)
                    for entity_type, records in replay_diff.created.items()
                }
                score = evaluate_state_requirements(task, replay_diff)
                audit.canonical_replay_state_pass = score.score if score else None
                audit.canonical_replay_reasoning = score.reasoning if score else None
                if score and score.score != 1:
                    audit.add_issue(
                        "state requirements",
                        f"canonical replay does not satisfy checked-in state requirements: {score.reasoning}",
                        "Update state_requirements to match the canonical solution, or fix replay/tool behavior if the replay is wrong.",
                    )
        elif task.state_requirements:
            audit.add_issue(
                "canonical replay",
                "task has state requirements but no canonical replay trace",
                "Add replay steps for the authored solution or remove impossible state requirements.",
            )

        _audit_state_requirement_references(task_raw, task_envs.get(task_id, {}), audit, replay_created_records)

    for task_id in generated:
        if task_id not in audits:
            audits[task_id] = TaskAudit(task_id=task_id, valid=False)
            audits[task_id].add_issue(
                "task json",
                "scenario registry generates a task that is not checked in",
                "Run task generation or remove the scenario from the registry.",
            )
    return audits


def _public_task_payload(task_data: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in task_data.items() if not key.startswith("_")}


def _execute_canonical_replay(
    environment: Any,
    replay_trace: list[dict[str, Any]],
    *,
    allow_terminal_rejected: bool = False,
) -> tuple[list[dict[str, Any]], StateDiff]:
    """Execute a canonical replay, allowing expected no-op denials.

    Denial/restraint customer-support tasks sometimes prove the correct answer by
    previewing a write tool and receiving a rejected response. For tasks with no
    state requirements, a terminal rejection is valid evidence that no mutation is
    reachable or desired.
    """
    if not allow_terminal_rejected:
        return execute_replay_trace(environment, replay_trace)

    before = environment.get_full_snapshot()
    executed: list[dict[str, Any]] = []
    for index, step in enumerate(replay_trace):
        if not isinstance(step, dict):
            raise ReplayError(f"Replay step {index} must be a dict, got {type(step).__name__}.")
        name = step.get("name")
        arguments = step.get("arguments", {})
        if not name or not isinstance(name, str):
            raise ReplayError(f"Replay step {index} is missing a valid tool name.")
        if not isinstance(arguments, dict):
            raise ReplayError(f"Replay step {index} arguments for {name} must be a dict.")
        handler = getattr(environment, name, None)
        if not callable(handler):
            raise ReplayError(f"Replay step {index} references unknown tool handler {name!r}.")
        try:
            result = handler(arguments)
        except Exception as exc:  # pragma: no cover - defensive
            raise ReplayError(f"Replay step {index} {name} raised {exc!r}.") from exc
        executed.append({"index": index, "name": name, "arguments": arguments, "result": result})
        if isinstance(result, dict) and "error" in result:
            raise ReplayError(f"Replay step {index} {name} returned error: {result['error']}")
        if isinstance(result, dict) and result.get("status") == "rejected":
            if index == len(replay_trace) - 1:
                break
            raise ReplayError(f"Replay step {index} {name} was rejected before the final step: {result}")

    after = environment.get_full_snapshot()
    return executed, StateDiff.compute(before, after)


def _audit_state_requirement_references(
    task_raw: dict[str, Any],
    env_raw: dict[str, Any],
    audit: TaskAudit,
    replay_created_records: dict[str, set[str]] | None = None,
) -> None:
    env_index = {
        "products": {row.get("product_id") for row in env_raw.get("products", [])},
        "orders": {row.get("order_id") for row in env_raw.get("orders", [])},
        "order_items": {row.get("item_id") for row in env_raw.get("order_items", [])},
        "customers": {row.get("customer_id") for row in env_raw.get("customers", [])},
        "warranties": {row.get("warranty_id") for row in env_raw.get("warranties", [])},
    }
    allowed_created_match = {"match_fields", "expected_fields"}
    for idx, req in enumerate(task_raw.get("state_requirements", []), start=1):
        if not isinstance(req, dict):
            audit.add_issue("state requirements", f"state requirement {idx} is not an object", "Rewrite it as a structured state requirement.")
            continue
        if allowed_created_match & set(req):
            continue
        entity_type = req.get("entity_type")
        record_key = req.get("record_key")
        field = req.get("field")
        if not entity_type or record_key is None or not field:
            audit.add_issue("state requirements", f"state requirement {idx} is malformed", "Include entity_type, record_key, field, and expected_value.")
            continue
        known_records = env_index.get(str(entity_type))
        if known_records is not None and record_key not in known_records:
            if record_key in (replay_created_records or {}).get(str(entity_type), set()):
                continue
            audit.add_issue(
                "state requirements",
                f"state requirement {idx} references unknown {entity_type} record {record_key}",
                "Fix the record_key or convert the requirement to match_fields for records created during the task.",
            )


def _audit_policy_math(cfg: DomainAuditConfig, task_audits: dict[str, TaskAudit]) -> list[dict[str, Any]]:
    if cfg.policy_math_verifier is None:
        return []
    result = cfg.policy_math_verifier()
    issues: list[dict[str, Any]] = []
    for finding in result.findings:
        issue = {
            "task_id": finding.task_id,
            "severity": finding.severity.value,
            "message": finding.message,
            "fix": "Fix the scenario policy calculation or expected dollar amount so independent policy recomputation agrees.",
        }
        issues.append(issue)
        if finding.task_id and finding.task_id in task_audits:
            task_audits[finding.task_id].add_issue("policy math", finding.message, issue["fix"])
    return issues


def _attribute_trajectory(
    domain: str,
    cfg: DomainAuditConfig,
    traj: dict[str, Any],
    task_jsons: dict[str, dict[str, Any]],
    task_audits: dict[str, TaskAudit],
) -> TrajectoryAttribution:
    task_id = traj.get("task_id", "<unknown>")
    run = str(traj.get("_run", "?"))
    passed = _as_bool(traj.get("task_completion_pass"))
    state_saved = _as_int(traj.get("state_requirements_met"))
    task_saved = _as_int(traj.get("task_requirements_met"))
    reasons: list[str] = []
    deterministic: dict[str, Any] = {}

    task_raw = task_jsons.get(task_id)
    task_audit = task_audits.get(task_id)
    if task_audit and not task_audit.valid:
        reasons.append("task-level audit found non-agent defects before trajectory attribution")
        return TrajectoryAttribution(
            task_id=task_id,
            run=run,
            label=_first_task_issue_label(task_audit),
            passed=passed,
            state_requirements_met=state_saved,
            task_requirements_met=task_saved,
            reasons=reasons + [issue["message"] for issue in task_audit.issues[:3]],
            fix_recommendation=_first_fix(task_audit),
            deterministic_checks={"task_valid": False},
        )

    if task_raw is None:
        return TrajectoryAttribution(
            task_id=task_id,
            run=run,
            label="HARNESS_BUG",
            passed=passed,
            state_requirements_met=state_saved,
            task_requirements_met=task_saved,
            reasons=["trajectory references a task_id that is not checked in"],
            fix_recommendation="Remove the trajectory or restore the missing task JSON.",
        )

    task = TaskDefinition.from_dict(task_raw)
    saved_diff = _state_diff_from_dict(traj.get("state_diff") or {})
    recomputed_state = evaluate_state_requirements(task, saved_diff)
    deterministic["recomputed_state_score"] = recomputed_state.score if recomputed_state else None
    deterministic["recomputed_state_reasoning"] = recomputed_state.reasoning if recomputed_state else None
    if recomputed_state and state_saved is not None and recomputed_state.score != state_saved:
        reasons.append(
            f"saved state score {state_saved} disagrees with deterministic recomputation {recomputed_state.score}: {recomputed_state.reasoning}"
        )
        return TrajectoryAttribution(
            task_id=task_id,
            run=run,
            label="HARNESS_BUG",
            passed=passed,
            state_requirements_met=state_saved,
            task_requirements_met=task_saved,
            reasons=reasons,
            fix_recommendation="Recompute/rescore this trajectory; investigate saved state_diff or state scoring serialization.",
            deterministic_checks=deterministic,
        )

    tool_calls = _extract_tool_calls(traj.get("conversation", []))
    deterministic["tool_call_count"] = len(tool_calls)
    deterministic["write_tool_calls"] = [call["name"] for call in tool_calls if call["name"] in cfg.write_tools]
    gate_issues = _check_policy_and_preview_sequence(tool_calls, cfg)
    deterministic["tool_sequence_issues"] = gate_issues

    replayed = _replay_agent_tool_calls(domain, task, tool_calls)
    deterministic["agent_tool_replay"] = replayed
    if replayed.get("status") == "ok" and replayed.get("state_diff") != saved_diff.to_dict():
        reasons.append("replaying saved tool calls from a fresh task environment does not match saved state_diff")
        return TrajectoryAttribution(
            task_id=task_id,
            run=run,
            label="HARNESS_BUG",
            passed=passed,
            state_requirements_met=state_saved,
            task_requirements_met=task_saved,
            reasons=reasons,
            fix_recommendation="Investigate trajectory state_diff capture or environment nondeterminism for this run.",
            deterministic_checks=deterministic,
        )

    action_expected = _action_expected(task_raw)
    no_state_expected = not task.state_requirements

    if passed is True:
        false_pass_reasons: list[str] = []
        if recomputed_state and recomputed_state.score != 1:
            false_pass_reasons.append("trajectory passed even though deterministic state requirements fail")
        if action_expected and not deterministic["write_tool_calls"]:
            false_pass_reasons.append("action task passed without any write tool calls")
        if no_state_expected and not saved_diff.is_empty():
            false_pass_reasons.append("no-state task passed despite non-empty state_diff")
        if false_pass_reasons:
            return TrajectoryAttribution(
                task_id=task_id,
                run=run,
                label="FALSE_PASS",
                passed=passed,
                state_requirements_met=state_saved,
                task_requirements_met=task_saved,
                reasons=false_pass_reasons,
                fix_recommendation="Rescore trajectory and tighten the judge/state gate so this pass cannot be awarded without satisfying required evidence.",
                deterministic_checks=deterministic,
            )
        return TrajectoryAttribution(
            task_id=task_id,
            run=run,
            label="PASS",
            passed=passed,
            state_requirements_met=state_saved,
            task_requirements_met=task_saved,
            reasons=["trajectory passed deterministic harness checks; no failure attribution needed"],
            deterministic_checks=deterministic,
        )

    if recomputed_state and recomputed_state.score == 1 and task_saved == 0:
        judge_bug_reason = _maybe_judge_bug(traj)
        if judge_bug_reason:
            return TrajectoryAttribution(
                task_id=task_id,
                run=run,
                label="JUDGE_BUG",
                passed=passed,
                state_requirements_met=state_saved,
                task_requirements_met=task_saved,
                reasons=[judge_bug_reason],
                fix_recommendation="Review task requirement judgment and update judge prompt or rescore this trajectory.",
                deterministic_checks=deterministic,
            )

    if gate_issues:
        reasons.extend(gate_issues[:3])
    if state_saved == 0 and recomputed_state:
        reasons.append(f"agent final state does not satisfy requirements: {recomputed_state.reasoning}")
    if task_saved == 0:
        task_reason = str(traj.get("task_requirements_reasoning") or "").strip()
        reasons.append(task_reason or "task-requirements judge marked the trajectory as failing")
    if not deterministic["write_tool_calls"] and action_expected:
        reasons.append("agent did not call any write tool for an action task")

    return TrajectoryAttribution(
        task_id=task_id,
        run=run,
        label="AGENT_ERROR",
        passed=passed,
        state_requirements_met=state_saved,
        task_requirements_met=task_saved,
        reasons=_dedupe(reasons) or ["saved trajectory failed and deterministic task/harness checks did not identify a non-agent defect"],
        deterministic_checks=deterministic,
    )


def _state_diff_from_dict(raw: dict[str, Any]) -> StateDiff:
    return StateDiff(
        created=raw.get("created") or {},
        modified=raw.get("modified") or {},
        deleted=raw.get("deleted") or {},
    )


def _extract_tool_calls(conversation: list[dict[str, Any]]) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for message in conversation:
        if message.get("role") != "assistant":
            continue
        for raw_call in message.get("tool_calls") or []:
            if not isinstance(raw_call, dict):
                continue
            name = raw_call.get("name") or raw_call.get("function", {}).get("name")
            args = raw_call.get("arguments") or raw_call.get("function", {}).get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {"_raw_arguments": args}
            if not isinstance(args, dict):
                args = {}
            calls.append({"name": name, "arguments": args, "result": raw_call.get("result")})
    return [call for call in calls if isinstance(call.get("name"), str)]


def _check_policy_and_preview_sequence(tool_calls: list[dict[str, Any]], cfg: DomainAuditConfig) -> list[str]:
    issues: list[str] = []
    policies_seen: set[str] = set()
    previewed: dict[str, set[str]] = defaultdict(set)
    for call in tool_calls:
        name = call["name"]
        args = call.get("arguments") or {}
        if name == "get_policies":
            topic = args.get("topic")
            if isinstance(topic, str):
                policies_seen.add(topic)
            continue
        if name not in cfg.write_tools:
            continue
        required_topics = cfg.policy_gate_map.get(name, [])
        if required_topics and not any(topic in policies_seen for topic in required_topics):
            issues.append(f"{name} called before required policy lookup ({'/'.join(required_topics)})")
        key = _preview_key(name, args)
        confirm = args.get("confirm") is True
        if confirm:
            if key not in previewed[name]:
                issues.append(f"{name} confirm=true called before preview for {key}")
        elif key:
            previewed[name].add(key)
        result = call.get("result")
        if isinstance(result, dict) and ("error" in result or result.get("status") == "rejected"):
            issues.append(f"{name} returned error/rejected result: {str(result)[:160]}")
    return _dedupe(issues)


def _preview_key(name: str, args: dict[str, Any]) -> str:
    if name in {"process_return", "process_refund", "process_exchange"}:
        return str(args.get("item_id", ""))
    if name == "cancel_order":
        return str(args.get("order_id", ""))
    if name == "process_warranty_claim":
        return str(args.get("warranty_id", ""))
    return json.dumps(args, sort_keys=True, default=str)


def _replay_agent_tool_calls(domain: str, task: TaskDefinition, tool_calls: list[dict[str, Any]]) -> dict[str, Any]:
    domain_config = get_domain_config(domain)
    try:
        from state_bench.env_loader import load_task_environment

        env_data, _ = load_task_environment(domain_config, task)
        env = domain_config.environment_class(env_data.deep_copy(), now=task.now)
    except Exception as exc:  # pragma: no cover - defensive
        return {"status": "error", "error": f"could not load task env: {exc}"}

    before = env.get_full_snapshot()
    executed: list[dict[str, Any]] = []
    for call in tool_calls:
        handler = getattr(env, call["name"], None)
        if not callable(handler):
            executed.append({"name": call["name"], "arguments": call.get("arguments", {}), "error": "unknown tool"})
            continue
        try:
            result = handler(call.get("arguments") or {})
        except Exception as exc:  # pragma: no cover - defensive
            return {"status": "error", "error": f"{call['name']} raised {exc!r}", "executed": executed}
        executed.append({"name": call["name"], "arguments": call.get("arguments", {}), "result": result})
    after = env.get_full_snapshot()
    return {"status": "ok", "state_diff": StateDiff.compute(before, after).to_dict(), "executed_count": len(executed)}


def _action_expected(task_raw: dict[str, Any]) -> bool:
    if task_raw.get("state_requirements"):
        return True
    text = " ".join(
        [
            str(task_raw.get("task_summary", "")),
            json.dumps(task_raw.get("task_requirements", []), ensure_ascii=False),
        ]
    ).lower()
    action_terms = (
        "process",
        "issue",
        "refund",
        "cancel",
        "exchange",
        "return",
        "warranty claim",
        "replacement",
        "compensation",
    )
    denial_terms = (
        "deny",
        "denied",
        "must not",
        "no state change",
        "no action needed",
        "avoid",
        "ask for",
        "invalid order",
        "investigation",
        "waitlist",
        "outside",
        "not eligible",
    )
    return any(term in text for term in action_terms) and not any(term in text for term in denial_terms)


def _maybe_judge_bug(traj: dict[str, Any]) -> str | None:
    details = traj.get("task_requirements_details")
    if isinstance(details, list) and details:
        passed_values = [item.get("passed") for item in details if isinstance(item, dict)]
        if passed_values and all(value is True or value == 1 for value in passed_values):
            return "task_requirements_met=0 but all detailed task requirements are marked passed"
    reasoning = str(traj.get("task_requirements_reasoning") or "").lower()
    positive = ("all required" in reasoning or "satisfied" in reasoning or "requirements are met" in reasoning)
    negative = ("not" in reasoning or "missing" in reasoning or "failed" in reasoning or "never" in reasoning)
    if positive and not negative:
        return "task_requirements_met=0 but task-requirements reasoning appears positive"
    return None


def _as_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if value in {0, 1, False, True}:
        return bool(value)
    return None


def _as_int(value: Any) -> int | None:
    if value in {0, 1, False, True}:
        return int(value)
    return None


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _first_task_issue_label(task_audit: TaskAudit) -> str:
    for issue in task_audit.issues:
        label = issue.get("label")
        if label in ATTRIBUTION_LABELS:
            return label
    return "TASK_BUG"


def _first_fix(task_audit: TaskAudit) -> str | None:
    for issue in task_audit.issues:
        fix = issue.get("fix")
        if fix:
            return str(fix)
    return None


def _build_summary(
    task_audits: dict[str, TaskAudit],
    attributions: list[TrajectoryAttribution],
    policy_math_issues: list[dict[str, Any]],
) -> dict[str, Any]:
    labels = Counter(item.label for item in attributions)
    failed = [item for item in attributions if item.passed is False]
    passed = [item for item in attributions if item.passed is True]
    return {
        "task_count": len(task_audits),
        "invalid_task_count": sum(1 for audit in task_audits.values() if not audit.valid),
        "trajectory_count": len(attributions),
        "failed_trajectory_count": len(failed),
        "passed_trajectory_count": len(passed),
        "trajectory_labels": dict(sorted(labels.items())),
        "policy_math_issue_count": len(policy_math_issues),
        "blocked_ambiguous_count": labels.get("BLOCKED_AMBIGUOUS", 0),
    }


def _render_markdown_report(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        f"# Customer Support Harness Attribution Audit - {payload['date']}",
        "",
        "## Summary",
        "",
        f"- Tasks audited: `{summary['task_count']}`",
        f"- Invalid tasks: `{summary['invalid_task_count']}`",
        f"- Trajectories audited: `{summary['trajectory_count']}`",
        f"- Failed trajectories: `{summary['failed_trajectory_count']}`",
        f"- Passed trajectories: `{summary['passed_trajectory_count']}`",
        f"- Policy math issues: `{summary['policy_math_issue_count']}`",
        f"- Blocked ambiguous: `{summary['blocked_ambiguous_count']}`",
        "",
        "## Labels",
        "",
        "| Label | Count |",
        "|---|---:|",
    ]
    for label, count in sorted(summary["trajectory_labels"].items()):
        lines.append(f"| `{label}` | {count} |")

    task_issues = [audit for audit in payload["task_audits"].values() if not audit["valid"]]
    lines.extend(["", "## Task-Level Findings", ""])
    if not task_issues:
        lines.append("No task-level harness defects were detected by deterministic checks.")
    else:
        for audit in task_issues:
            lines.append(f"### `{audit['task_id']}`")
            for issue in audit["issues"]:
                lines.append(f"- `{issue['label']}` / {issue['surface']}: {issue['message']}")
                lines.append(f"  Fix: {issue['fix']}")

    non_agent = [
        item
        for item in payload["trajectory_attributions"]
        if item["label"] in {"TASK_BUG", "HARNESS_BUG", "JUDGE_BUG", "FALSE_PASS", "BLOCKED_AMBIGUOUS"}
    ]
    lines.extend(["", "## Non-Agent Trajectory Findings", ""])
    if not non_agent:
        lines.append("No non-agent trajectory findings were detected by deterministic checks.")
    else:
        for item in non_agent[:200]:
            lines.append(f"### `{item['task_id']}` / `{item['run']}` - `{item['label']}`")
            for reason in item["reasons"][:4]:
                lines.append(f"- {reason}")
            if item.get("fix_recommendation"):
                lines.append(f"- Fix: {item['fix_recommendation']}")
        if len(non_agent) > 200:
            lines.append(f"\n... {len(non_agent) - 200} additional non-agent findings omitted from Markdown; see JSON.")

    failed_agent = [item for item in payload["trajectory_attributions"] if item["passed"] is False and item["label"] == "AGENT_ERROR"]
    lines.extend(["", "## Agent Error Failures", "", f"Deterministically attributed agent-error failures: `{len(failed_agent)}`."])
    for item in failed_agent[:50]:
        lines.append(f"- `{item['task_id']}` / `{item['run']}`: {item['reasons'][0] if item['reasons'] else 'agent failed task requirements or state requirements'}")
    if len(failed_agent) > 50:
        lines.append(f"- ... {len(failed_agent) - 50} more in JSON.")
    lines.append("")
    return "\n".join(lines)
