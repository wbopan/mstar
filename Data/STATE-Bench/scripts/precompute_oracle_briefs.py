"""Precompute oracle-style per-task briefs for OracleAgent.

Generates `outputs/<domain>/learning_opportunities/<task_id>.json` only when missing.
This mirrors the older oracle setup, but uses the v0.3 exact-task oracle brief format.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from agents.base import AgentRuntimeContext
from agents.oracle import OracleMemoryStore
from state_bench.client import PooledLLMClient
from state_bench.schemas import TaskDefinition

DOMAINS = ["travel", "customer_support", "shopping_assistant"]


def _load_agent_config(path: str | None) -> dict:
    if path is None:
        return {}
    return json.loads(Path(path).read_text())


def main() -> None:
    parser = argparse.ArgumentParser(description="Precompute missing oracle briefs for OracleAgent")
    parser.add_argument("--domain", required=True, choices=DOMAINS + ["all"])
    parser.add_argument("--agent-config", type=str, default=None, help="Optional oracle config JSON")
    parser.add_argument("--tasks", type=str, default=None, help="Comma-separated task IDs")
    args = parser.parse_args()

    domains = DOMAINS if args.domain == "all" else [args.domain]
    agent_config = _load_agent_config(args.agent_config)
    client = PooledLLMClient()

    for domain in domains:
        task_dir = Path("domains") / domain / "tasks"
        output_dir = Path("outputs") / domain
        learning_dir = Path(agent_config.get("learning_dir", output_dir / "learning_opportunities"))
        selected = None
        if args.tasks:
            selected = {task_id.strip() for task_id in args.tasks.split(",") if task_id.strip()}

        generated = 0
        skipped = 0
        for task_path in sorted(task_dir.glob("*.json")):
            task = TaskDefinition.load(task_path)
            if selected is not None and task.task_id not in selected:
                continue

            context = AgentRuntimeContext(
                task_id=task.task_id,
                user_id=task.user_id,
                domain=domain,
                now=task.now,
                output_dir=str(output_dir / "run1"),
                task_summary=task.task_summary,
                state_requirements=task.state_requirements,
                task_requirements=task.task_requirements,
                config={**agent_config, "learning_dir": str(learning_dir), "baseline_outputs_dir": str(output_dir)},
            )
            store = OracleMemoryStore(client, context)
            if store.has_brief():
                skipped += 1
                continue
            if store.ensure_brief():
                generated += 1

        print(f"{domain}: generated {generated}, skipped {skipped} existing briefs → {learning_dir}")


if __name__ == "__main__":
    main()
