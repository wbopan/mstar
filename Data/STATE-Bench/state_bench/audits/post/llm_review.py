"""LLM-based post-run trajectory review.

Uses an LLM to walk through each trajectory and verify:
1. Task is well-posed (task summary is complete, not missing anything)
2. State_diff is complete and matches task summary
3. Classification: true-pass / true-fail / false-pass / false-fail

Requires Azure OpenAI credentials (same as the benchmark runner).
Runs LLM calls in parallel using ThreadPoolExecutor for speed.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from state_bench.audits._types import AuditFinding, CheckResult, DomainAuditConfig, Severity

LLM_REVIEW_PROMPT = """\
You are an expert benchmark auditor. Your job is to verify that a benchmark task and its trajectory result are correct. \
You are NOT judging the agent — you are auditing the **benchmark harness** for bugs.

## Task Definition
**Task ID:** {task_id}
**Task Summary:** {task_summary}

## Conversation
{conversation}

## Database Changes (state_diff)
{state_diff}

## Agent Result
- **Passed:** {passed}
- **Task Completion Pass:** {task_completion_pass}
- **State Requirements Met:** {state_requirements_met}
- **Task Requirements Met:** {task_requirements_met}
- **Completion Reasoning:** {completion_reasoning}

## Your Audit

Answer each question carefully:

### 1. Is the task summary complete?
Does the task summary specify everything the agent needs to do? Are there dollar amounts, \
status changes, or actions that are implied but not stated? If missing, the judge may score \
incorrectly.

### 2. Is the state_diff consistent with the conversation?
Look at what the agent actually did (tool calls, their results) and compare with the \
state_diff. Does the state_diff accurately reflect all database changes? Are there tool calls \
that should have changed state but didn't (environment bug)?

### 3. Is the pass/fail classification correct?
- If the agent passed: Did the agent actually achieve the expected outcome? Or did the judge \
score too generously (false pass)?
- If the agent failed: Did the agent actually fail? Or was there a harness issue — impossible \
task, broken tool, incomplete task_summary, simulator blocking valid path (false fail)?

### 4. Classification
Based on your analysis, classify this result:
- **true_pass**: Agent correctly achieved the expected outcome. Score is deserved.
- **true_fail**: Agent genuinely failed. Score is deserved.
- **false_pass**: Agent passed but shouldn't have (harness bug inflated score).
- **false_fail**: Agent failed but shouldn't have (harness bug deflated score).

Respond with ONLY a JSON object:
{{
    "task_summary_complete": true/false,
    "task_summary_issues": "description of any issues or 'none'",
    "state_diff_consistent": true/false,
    "state_diff_issues": "description of any issues or 'none'",
    "classification": "true_pass|true_fail|false_pass|false_fail",
    "reasoning": "2-3 sentences explaining your classification",
    "severity": "none|minor|moderate|critical"
}}
"""


def _format_conversation_for_audit(conversation: list[dict[str, Any]]) -> str:
    """Format conversation into a readable text for the LLM auditor."""
    lines: list[str] = []
    for msg in conversation:
        role = msg.get("role", "unknown").upper()
        content = msg.get("content", "")
        tool_calls = msg.get("tool_calls", [])

        if role == "ASSISTANT":
            label = "AGENT"
        elif role == "USER":
            label = "USER"
        elif role == "TOOL":
            label = "TOOL_RESULT"
        else:
            label = role

        if tool_calls:
            tc_strs = []
            for tc in tool_calls:
                name = tc.get("name", tc.get("function", {}).get("name", "unknown"))
                args = tc.get("arguments", tc.get("function", {}).get("arguments", {}))
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        pass
                args_str = json.dumps(args, default=str) if isinstance(args, dict) else str(args)
                if len(args_str) > 200:
                    args_str = args_str[:197] + "..."
                tc_strs.append(f"  [{name}({args_str})]")
            tc_text = "\n".join(tc_strs)
            if content:
                lines.append(f"{label}: {content}\n{tc_text}")
            else:
                lines.append(f"{label}:\n{tc_text}")
        elif content:
            # Truncate very long messages
            display = content if len(content) <= 500 else content[:497] + "..."
            lines.append(f"{label}: {display}")

    return "\n\n".join(lines)


def _format_state_diff_for_audit(state_diff: dict[str, Any] | None) -> str:
    """Format state_diff dict into readable text."""
    if not state_diff:
        return "No database changes were made."

    lines: list[str] = []
    created = state_diff.get("created", {})
    modified = state_diff.get("modified", {})
    deleted = state_diff.get("deleted", {})

    if not created and not modified and not deleted:
        return "No database changes were made."

    if created:
        lines.append("### Created")
        for entity_type, entities in created.items():
            for eid, record in entities.items():
                record_str = json.dumps(record, default=str)
                if len(record_str) > 300:
                    record_str = record_str[:297] + "..."
                lines.append(f"- {entity_type} {eid}: {record_str}")

    if modified:
        lines.append("### Modified")
        for entity_type, entities in modified.items():
            for eid, changes in entities.items():
                change_strs = [f"{k}: {v.get('old')} → {v.get('new')}" for k, v in changes.items()]
                lines.append(f"- {entity_type} {eid}: {', '.join(change_strs)}")

    if deleted:
        lines.append("### Deleted")
        for entity_type, entities in deleted.items():
            for eid in entities:
                lines.append(f"- {entity_type} {eid}")

    return "\n".join(lines)


def check_llm_review(
    trajectories: list[dict[str, Any]],
    task_jsons: dict[str, dict[str, Any]],
    cfg: DomainAuditConfig,
    client: Any | None = None,
    max_tasks: int | None = None,
    deterministic_flags: dict[str, list[str]] | None = None,
) -> CheckResult:
    """Use an LLM to audit each trajectory for harness bugs.

    Args:
        trajectories: Loaded trajectory dicts.
        task_jsons: Task definition dicts keyed by task_id.
        cfg: Domain audit config.
        client: LLM client (PooledLLMClient or LLMClient). If None, builds one.
        max_tasks: Maximum number of trajectories to audit (for cost control).
        deterministic_flags: Per-task flags from deterministic checks that need LLM classification.
            Keyed by "task_id/run", values are list of mismatch descriptions.
    """
    result = CheckResult(check_name="LLM trajectory review")

    if client is None:
        try:
            from state_bench.client import PooledLLMClient

            client = PooledLLMClient()
        except Exception as e:
            result.findings.append(
                AuditFinding(Severity.MINOR, result.check_name, None, f"Could not build LLM client: {e}")
            )
            return result

    # Collect best trajectory per task — prefer runs where the judge scored successfully
    traj_by_task: dict[str, list[tuple[str, dict]]] = {}  # tid -> [(run, traj), ...]
    for traj in trajectories:
        tid = traj.get("task_id", "<unknown>")
        run = traj.get("_run", "?")
        traj_by_task.setdefault(tid, []).append((run, traj))

    tasks_to_review: list[tuple[str, str, dict, dict]] = []  # (tid, run, traj, task_json)
    for tid, runs in traj_by_task.items():
        if max_tasks is not None and len(tasks_to_review) >= max_tasks:
            break
        task_json = task_jsons.get(tid, {})
        if not task_json:
            continue
        # Prefer trajectory with canonical completion scoring, then first run
        scored = [(run, t) for run, t in runs if t.get("task_completion_pass") is not None]
        if scored:
            run, traj = scored[0]
        else:
            # All runs were unscored — skip this task for LLM review
            continue
        tasks_to_review.append((tid, run, traj, task_json))

    def _review_single(tid: str, run: str, traj: dict, task_json: dict) -> list[AuditFinding]:
        """Review a single trajectory. Returns list of findings."""
        findings: list[AuditFinding] = []
        conversation = traj.get("conversation", [])
        state_diff = traj.get("state_diff")
        task_completion = traj.get("task_completion_pass")
        passed = task_completion == 1
        task_completion_pass = traj.get("task_completion_pass", "N/A")
        state_requirements_met = traj.get("state_requirements_met", "N/A")
        task_requirements_met = traj.get("task_requirements_met", "N/A")
        completion_reasoning = traj.get("task_requirements_reasoning") or traj.get("state_requirements_reasoning", "N/A")

        prompt = LLM_REVIEW_PROMPT.format(
            task_id=tid,
            task_summary=task_json.get("task_summary", ""),
            conversation=_format_conversation_for_audit(conversation),
            state_diff=_format_state_diff_for_audit(state_diff),
            passed=passed,
            task_completion_pass=task_completion_pass,
            state_requirements_met=state_requirements_met,
            task_requirements_met=task_requirements_met,
            completion_reasoning=completion_reasoning,
        )

        task_key = f"{tid}/{run}"
        flags = (deterministic_flags or {}).get(task_key, [])
        if flags:
            flags_text = "\n".join(f"- {f}" for f in flags)
            prompt += (
                "\n\n## Deterministic Audit Flags\n"
                "The following mismatches were detected by automated checks. "
                "For each, classify whether this is an **agent error** (agent chose wrong flight/amount) "
                "or a **harness bug** (task_summary is wrong, environment bug, etc.):\n\n"
                f"{flags_text}"
            )

        try:
            response = client.complete_json(
                prompt=prompt,
                system_prompt="You are a benchmark quality auditor. Return valid JSON only.",
            )
        except Exception as e:
            findings.append(
                AuditFinding(Severity.MINOR, "LLM trajectory review", f"{tid}/{run}", f"LLM review failed: {e}")
            )
            return findings

        classification = response.get("classification", "unknown")
        severity_str = response.get("severity", "none")
        reasoning = response.get("reasoning", "")
        eo_complete = response.get("task_summary_complete", True)
        eo_issues = response.get("task_summary_issues", "none")
        sd_consistent = response.get("state_diff_consistent", True)
        sd_issues = response.get("state_diff_issues", "none")

        sev_map = {"critical": Severity.CRITICAL, "moderate": Severity.MODERATE, "minor": Severity.MINOR}
        severity = sev_map.get(severity_str, Severity.INFO)

        if classification in ("false_pass", "false_fail"):
            findings.append(
                AuditFinding(
                    severity,
                    "LLM trajectory review",
                    f"{tid}/{run}",
                    f"[{classification}] {reasoning}",
                    details={
                        "classification": classification,
                        "task_summary_complete": eo_complete,
                        "task_summary_issues": eo_issues,
                        "state_diff_consistent": sd_consistent,
                        "state_diff_issues": sd_issues,
                    },
                )
            )

        if not eo_complete and eo_issues != "none":
            findings.append(
                AuditFinding(
                    Severity.MODERATE,
                    "LLM trajectory review",
                    f"{tid}/{run}",
                    f"Incomplete task_summary: {eo_issues}",
                )
            )

        if not sd_consistent and sd_issues != "none":
            findings.append(
                AuditFinding(
                    Severity.MODERATE,
                    "LLM trajectory review",
                    f"{tid}/{run}",
                    f"State diff inconsistency: {sd_issues}",
                )
            )

        return findings

    # Run reviews in parallel
    print(f"  LLM review: {len(tasks_to_review)} tasks across parallel workers...")
    with ThreadPoolExecutor(max_workers=min(25, len(tasks_to_review))) as executor:
        futures = {
            executor.submit(_review_single, tid, run, traj, task_json): tid
            for tid, run, traj, task_json in tasks_to_review
        }
        for future in as_completed(futures):
            tid = futures[future]
            try:
                findings = future.result()
                result.findings.extend(findings)
            except Exception as e:
                result.findings.append(AuditFinding(Severity.MINOR, result.check_name, tid, f"LLM review error: {e}"))

    if not tasks_to_review:
        result.findings.append(
            AuditFinding(Severity.MINOR, result.check_name, None, "No trajectories reviewed (no matching tasks)")
        )

    return result
