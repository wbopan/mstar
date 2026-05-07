"""OracleAgent — oracle-style exact-task brief injection.

This agent intentionally cheats for experimental purposes:
- It looks up prior baseline trajectories for the exact same task_id.
- It gives the LLM the ground-truth task summary and requirements.
- It distills one structured oracle brief and injects it back only for that same task.

There is no cross-task reuse.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agents.base import AgentRuntimeContext
from agents.vanilla import VanillaAgent

_LEARNING_SYSTEM_PROMPT = (
    "You are producing a compact oracle learning brief for one exact benchmark task. "
    "Return valid JSON only with exactly these keys: failure_summary, root_cause, correct_procedure, learning_type, transferable_lesson. "
    "Do not return any other keys. Keep failure_summary under 160 characters, root_cause under 120 characters, correct_procedure as 2 to 4 short imperative steps, learning_type as a short label, and transferable_lesson under 160 characters. "
    "Use the ground-truth task summary and requirements as the source of truth, and use baseline evidence only as supporting context. "
    "Do not restate the task, do not quote schemas, and do not include long explanations."
)


class OracleMemoryStore:
    """Build and cache one exact-task oracle brief."""

    def __init__(
        self,
        client: Any,
        runtime_context: AgentRuntimeContext | None,
        usage_recorder: Any | None = None,
    ):
        self.client = client
        self.runtime_context = runtime_context
        self.usage_recorder = usage_recorder
        self.task_id = runtime_context.task_id if runtime_context else ""
        self.domain = runtime_context.domain if runtime_context else ""
        self.config = runtime_context.config if runtime_context else {}
        self.task_summary = runtime_context.task_summary if runtime_context else ""
        self.state_requirements = runtime_context.state_requirements if runtime_context else []
        self.task_requirements = runtime_context.task_requirements if runtime_context else []
        self.reasoning_effort = self.config.get("reasoning_effort", "medium")
        self.max_trajectories = int(self.config.get("max_trajectories_per_task", 2))
        self.max_messages_per_trajectory = int(self.config.get("max_messages_per_trajectory", 6))
        self.baseline_outputs_dir = self._resolve_baseline_dir()
        self.learning_dir = self._resolve_learning_dir()
        self.learning_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_baseline_dir(self) -> Path | None:
        raw = self.config.get("baseline_outputs_dir")
        if raw:
            return Path(raw)

        if not self.runtime_context or not self.runtime_context.output_dir:
            return None

        current_output_dir = Path(self.runtime_context.output_dir)
        parent = current_output_dir.parent
        if parent.name == self.domain:
            return parent
        return current_output_dir

    def _resolve_learning_dir(self) -> Path:
        raw = self.config.get("learning_dir")
        if raw:
            return Path(raw)

        if self.baseline_outputs_dir is not None:
            return self.baseline_outputs_dir / "learning_opportunities"

        if self.runtime_context and self.runtime_context.output_dir:
            output_dir = Path(self.runtime_context.output_dir)
            parent = output_dir.parent
            if parent.name == self.domain:
                return parent / "learning_opportunities"
            return output_dir / "learning_opportunities"

        return Path("outputs") / self.domain / "learning_opportunities"

    def _brief_path(self) -> Path:
        return self.learning_dir / f"{self.task_id}.json"

    def retrieve(self) -> str:
        if not self.task_id:
            return ""

        brief_path = self._brief_path()
        if brief_path.exists():
            data = json.loads(brief_path.read_text())
            if data.get("task_id") != self.task_id:
                return ""
            return self._format_brief(data)

        brief = self._generate_brief_from_baselines()
        if brief:
            brief_path.write_text(json.dumps(brief, indent=2, ensure_ascii=False))
            return self._format_brief(brief)
        return ""

    def has_brief(self) -> bool:
        return self._brief_path().exists()

    def ensure_brief(self) -> bool:
        if self.has_brief():
            return True
        brief = self._generate_brief_from_baselines()
        if not brief:
            return False
        self._brief_path().write_text(json.dumps(brief, indent=2, ensure_ascii=False))
        return True

    def _generate_brief_from_baselines(self) -> dict[str, Any] | None:
        trajectories = self._load_candidate_trajectories()
        if not trajectories:
            return None

        prompt = self._build_learning_prompt(trajectories)
        response = self.client.complete_json_response(
            prompt=prompt,
            system_prompt=_LEARNING_SYSTEM_PROMPT,
            max_tokens=320,
            reasoning_effort=self.reasoning_effort,
        )
        if self.usage_recorder is not None and getattr(response, "usage", None) is not None:
            self.usage_recorder(response.usage, category="memory_ingestion")
        result = json.loads(response.output_text)
        failure_summary = str(result.get("failure_summary", "")).strip()
        root_cause = str(result.get("root_cause", "")).strip()
        correct_procedure = [str(step).strip() for step in result.get("correct_procedure", []) if str(step).strip()]
        transferable_lesson = str(result.get("transferable_lesson", "")).strip()
        if not correct_procedure and not transferable_lesson:
            return None
        return {
            "task_id": self.task_id,
            "domain": self.domain,
            "failure_summary": failure_summary[:300],
            "root_cause": root_cause[:240],
            "correct_procedure": [step[:240] for step in correct_procedure[:6]],
            "learning_type": str(result.get("learning_type", "oracle_exact_task"))[:80],
            "transferable_lesson": transferable_lesson[:300],
        }

    def _build_learning_prompt(self, trajectories: list[dict[str, Any]]) -> str:
        state_lines = self._format_requirements(self.state_requirements, limit=4, value_limit=140)
        task_lines = self._format_requirements(self.task_requirements, limit=4, value_limit=140)
        trajectory_lines: list[str] = []
        for idx, traj in enumerate(trajectories, 1):
            trajectory_lines.append(
                f"Run {idx}: completion={traj.get('task_completion_pass')} state={traj.get('state_requirements_met')} task={traj.get('task_requirements_met')} ux={traj.get('ux_score')}"
            )
            reasoning = str(traj.get("task_requirements_reasoning", "")).strip()
            if reasoning:
                trajectory_lines.append(f"Reasoning: {reasoning[:220]}")
            for msg in traj.get("conversation", [])[:3]:
                role = str(msg.get("role", "?")).upper()
                content = str(msg.get("content", "")).replace("\n", " ").strip()
                if content:
                    trajectory_lines.append(f"{role}: {content[:180]}")
                tool_calls = [name for name in (msg.get("tool_calls") or []) if name]
                if tool_calls:
                    trajectory_lines.append(f"TOOLS: {', '.join(tool_calls[:4])}")
            trajectory_lines.append("")

        state_block = "\n".join(state_lines) if state_lines else "- none"
        task_block = "\n".join(task_lines) if task_lines else "- none"
        trajectory_block = "\n".join(trajectory_lines).strip()
        return (
            f"TASK ID: {self.task_id}\n"
            f"DOMAIN: {self.domain}\n"
            f"TASK SUMMARY: {self.task_summary[:300]}\n\n"
            f"STATE REQUIREMENTS:\n{state_block}\n\n"
            f"TASK REQUIREMENTS:\n{task_block}\n\n"
            f"BASELINE EVIDENCE:\n{trajectory_block}\n\n"
            "Return exactly this JSON shape and nothing else:\n"
            '{"failure_summary":"...","root_cause":"...","correct_procedure":["...","..."],"learning_type":"...","transferable_lesson":"..."}'
        )

    def _format_requirements(self, requirements: list[dict[str, Any]], *, limit: int, value_limit: int) -> list[str]:
        lines: list[str] = []
        for req in requirements[:limit]:
            compact = json.dumps(req, ensure_ascii=False, sort_keys=True)
            lines.append(f"- {compact[:value_limit]}")
        if len(requirements) > limit:
            lines.append(f"- ... {len(requirements) - limit} more")
        return lines

    def _format_brief(self, brief: dict[str, Any]) -> str:
        lines = ["## LEARNING FROM PAST EXPERIENCE", "", "You previously failed this exact task. Use these lessons:", ""]
        if brief.get("failure_summary"):
            lines.append(f"Failure: {brief['failure_summary']}")
        if brief.get("root_cause"):
            lines.append(f"Root cause: {brief['root_cause']}")
        if brief.get("correct_procedure"):
            lines.append("Correct procedure:")
            for idx, step in enumerate(brief["correct_procedure"], 1):
                lines.append(f"  {idx}. {step}")
        if brief.get("transferable_lesson"):
            lines.append("")
            lines.append(f"Key lesson: {brief['transferable_lesson']}")
        return "\n".join(lines)

    def _load_candidate_trajectories(self) -> list[dict[str, Any]]:
        if self.baseline_outputs_dir is None or not self.baseline_outputs_dir.exists() or not self.task_id:
            return []

        candidates: list[tuple[tuple[int, int, float, str], dict[str, Any]]] = []
        for path in sorted(self.baseline_outputs_dir.glob(f"run*/{self.task_id}.json")):
            data = json.loads(path.read_text())
            key = (
                int(data.get("task_completion_pass") or 0),
                int(data.get("task_requirements_met") or 0) + int(data.get("state_requirements_met") or 0),
                float(data.get("ux_score") or 0),
                path.parent.name,
            )
            candidates.append((key, self._trim_trajectory(data, path)))

        candidates.sort(reverse=True, key=lambda item: item[0])
        return [item[1] for item in candidates[: self.max_trajectories]]

    def _trim_trajectory(self, data: dict[str, Any], path: Path) -> dict[str, Any]:
        conversation = data.get("conversation", [])[: min(self.max_messages_per_trajectory, 3)]
        brief_conversation = []
        for msg in conversation:
            brief_conversation.append(
                {
                    "role": msg.get("role"),
                    "content": str(msg.get("content", ""))[:180],
                    "tool_calls": [tc.get("name") for tc in (msg.get("tool_calls") or [])],
                }
            )

        return {
            "source_path": str(path),
            "task_completion_pass": data.get("task_completion_pass"),
            "task_requirements_reasoning": str(data.get("task_requirements_reasoning", ""))[:220],
            "state_requirements_met": data.get("state_requirements_met"),
            "task_requirements_met": data.get("task_requirements_met"),
            "ux_score": data.get("ux_score"),
            "conversation": brief_conversation,
        }


class OracleAgent(VanillaAgent):
    """Oracle-style agent that injects exact-task briefs only."""

    def __init__(
        self,
        client: Any,
        system_prompt: str,
        tools: list[dict[str, Any]],
        tool_handlers: dict[str, Any],
        runtime_context: AgentRuntimeContext | None = None,
    ):
        super().__init__(client, system_prompt, tools, tool_handlers, runtime_context=runtime_context)
        self.memory_store = OracleMemoryStore(client, runtime_context, usage_recorder=self.add_response_usage)
        self.cached_learning = self.memory_store.retrieve()

    def prepare_conversation(self, conversation: list[Any]) -> list[Any]:
        if not self.cached_learning:
            return conversation

        system_content = (
            "Oracle learning for this exact task only. Do not generalize it to other tasks.\n"
            f"{self.cached_learning}"
        )
        return self.inject_system_message(conversation, system_content, before_last_user=True)
