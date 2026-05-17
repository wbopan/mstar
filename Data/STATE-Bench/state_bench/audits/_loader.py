"""Load tasks, task-local environments, trajectories, and finalized generation state."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

from state_bench.domain import get_domain_config
from state_bench.env_loader import resolve_task_env_path
from state_bench.generation import finalize_generated_task
from state_bench.schemas import TaskDefinition

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _domain_dir(domain: str) -> Path:
    return REPO_ROOT / "domains" / domain


def load_tasks(domain: str, single_task: str | None = None) -> list[dict[str, Any]]:
    """Load task JSONs for a domain. If single_task given, filter to matches."""
    tasks_dir = _domain_dir(domain) / "tasks"
    if not tasks_dir.exists():
        print(f"ERROR: tasks directory not found: {tasks_dir}")
        sys.exit(1)

    tasks: list[dict[str, Any]] = []
    for f in sorted(tasks_dir.glob("*.json")):
        if single_task and single_task not in f.stem:
            continue
        tasks.append(json.loads(f.read_text()))

    if single_task and not tasks:
        print(f"ERROR: no task matching '{single_task}' in {tasks_dir}")
        sys.exit(1)

    return tasks


def load_task_environment_jsons(tasks: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Load raw task-local environments keyed by task_id."""
    task_envs: dict[str, dict[str, Any]] = {}
    for task_raw in tasks:
        task = TaskDefinition.from_dict(task_raw)
        try:
            env_path = resolve_task_env_path(task)
        except FileNotFoundError as exc:
            print(f"ERROR: {exc}")
            sys.exit(1)
        if not env_path.exists():
            print(f"ERROR: task environment not found for {task.task_id}: {env_path}")
            sys.exit(1)
        task_envs[task.task_id] = json.loads(env_path.read_text())
    return task_envs


def load_finalized_generation_results(domain: str, single_task: str | None = None) -> dict[str, dict[str, Any]]:
    registry = importlib.import_module(f"domains.{domain}.task_registry")
    hooks = importlib.import_module(f"domains.{domain}.generate_tasks")
    adapter = hooks.get_generation_adapter(registry)
    domain_config = get_domain_config(domain)

    results: dict[str, dict[str, Any]] = {}
    for idx, scenario in adapter.enumerate():
        built = adapter.build(idx, scenario)
        finalized = finalize_generated_task(domain_config, built)
        task_id = finalized.task_data["task_id"]
        if single_task and single_task not in task_id:
            continue
        results[task_id] = {
            "task": finalized.task_data,
            "task_env": finalized.task_env.to_dict(),
            "replay_trace": list(finalized.replay_trace),
            "audit_issues": list(finalized.audit_issues),
        }
    return results


def load_trajectories(
    domain: str,
    runs_dir: Path | None = None,
    num_runs: int = 3,
    single_task: str | None = None,
) -> list[dict[str, Any]]:
    """Load trajectory JSONs from output runs."""
    if runs_dir is None:
        runs_dir = REPO_ROOT / "outputs" / domain

    trajectories: list[dict[str, Any]] = []
    for run_idx in range(1, num_runs + 1):
        run_dir = runs_dir / f"run{run_idx}"
        if not run_dir.exists():
            continue
        for f in sorted(run_dir.glob("*.json")):
            if single_task and single_task not in f.stem:
                continue
            data = json.loads(f.read_text())
            data["_run"] = f"run{run_idx}"
            data["_source_file"] = str(f)
            trajectories.append(data)

    return trajectories


def load_task_jsons_by_id(domain: str, single_task: str | None = None) -> dict[str, dict[str, Any]]:
    """Load task JSONs keyed by task_id."""
    tasks = load_tasks(domain, single_task)
    return {t["task_id"]: t for t in tasks}
