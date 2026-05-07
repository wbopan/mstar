from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Protocol

from state_bench.replay import (
    ReplayError,
    ReplayMatcherConfig,
    compute_replay_trace_hash,
    derive_state_requirements_from_state_diff,
    execute_replay_trace,
)


class ReplayPolicy(str, Enum):
    STRICT_WRITE_REPLAY = "strict_write_replay"
    NO_STATE_CHANGE_OK = "no_state_change_ok"


StateRequirementsPostprocessor = Callable[
    [dict[str, Any], list[dict[str, Any]], dict[str, dict[str, dict[str, Any]]] | None],
    list[dict[str, Any]],
]
StateRequirementsValidator = Callable[[dict[str, Any], list[dict[str, Any]]], None]


@dataclass
class ScenarioBuildResult:
    task_data: dict[str, Any]
    task_env: Any
    now: str
    replay_policy: ReplayPolicy
    replay_trace: list[dict[str, Any]] = field(default_factory=list)
    audit_issues: list[str] = field(default_factory=list)
    matcher_config: ReplayMatcherConfig = field(default_factory=ReplayMatcherConfig)
    state_requirements_postprocessor: StateRequirementsPostprocessor | None = None
    state_requirements_validator: StateRequirementsValidator | None = None


class DomainGenerationAdapter(Protocol):
    def enumerate(self, task_id_filter: set[int] | None = None) -> list[tuple[int, Any]]: ...

    def build(self, idx: int, scenario: Any) -> ScenarioBuildResult: ...


def serialize_task_payload(task_data: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in task_data.items() if not key.startswith("_")}


def save_task_json(task_data: dict[str, Any], tasks_dir: Path) -> None:
    tasks_dir.mkdir(parents=True, exist_ok=True)
    path = tasks_dir / f"{task_data['task_id']}.json"
    with open(path, "w") as f:
        json.dump(serialize_task_payload(task_data), f, indent=2, ensure_ascii=False)


def _require_explicit_contract_fields(result: ScenarioBuildResult) -> None:
    if not isinstance(result.now, str) or not result.now:
        raise ValueError("ScenarioBuildResult.now must be an explicit non-empty string")
    if not isinstance(result.replay_policy, ReplayPolicy):
        raise ValueError(f"ScenarioBuildResult.replay_policy must be ReplayPolicy, got {result.replay_policy!r}")


def finalize_generated_task(domain_config: Any, result: ScenarioBuildResult) -> ScenarioBuildResult:
    _require_explicit_contract_fields(result)

    task_data = dict(result.task_data)
    replay_trace = list(result.replay_trace or [])
    task_data["_replay_trace"] = replay_trace
    task_data["now"] = result.now
    task_data.setdefault("state_requirements", [])

    env = domain_config.environment_class(result.task_env.deep_copy(), now=result.now)
    replay_error: ReplayError | None = None
    post_snapshot: dict[str, dict[str, dict[str, Any]]] | None = None

    if replay_trace:
        try:
            _executed, state_diff = execute_replay_trace(env, replay_trace)
        except ReplayError as exc:
            replay_error = exc
            if result.replay_policy is not ReplayPolicy.NO_STATE_CHANGE_OK:
                raise
            task_data["state_requirements"] = []
        else:
            post_snapshot = env.get_full_snapshot()
            task_data["state_requirements"] = derive_state_requirements_from_state_diff(
                state_diff,
                matcher_config=result.matcher_config,
            )
    elif result.replay_policy is ReplayPolicy.NO_STATE_CHANGE_OK:
        task_data["state_requirements"] = []

    if result.state_requirements_postprocessor is not None:
        task_data["state_requirements"] = result.state_requirements_postprocessor(
            task_data,
            list(task_data.get("state_requirements", [])),
            post_snapshot,
        )

    task_data["replay_trace_hash"] = compute_replay_trace_hash(
        task_id=task_data["task_id"],
        now=result.now,
        replay_trace=replay_trace,
        environment_snapshot=result.task_env.to_dict(),
    )

    if replay_error is not None:
        task_data["_replay_error"] = str(replay_error)

    if result.state_requirements_validator is not None:
        result.state_requirements_validator(task_data, list(task_data.get("state_requirements", [])))

    result.task_data = task_data
    return result
