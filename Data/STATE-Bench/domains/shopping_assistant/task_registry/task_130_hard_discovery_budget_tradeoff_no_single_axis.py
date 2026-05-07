"""Hard shopping extension task 130: hard_discovery_budget_tradeoff_no_single_axis."""

from __future__ import annotations

from domains.shopping_assistant.task_registry.hard_extension import env_for, task_json_for

TASK_ID = "130-hard_discovery_budget_tradeoff_no_single_axis"
TASK_JSON = task_json_for("hard_discovery_budget_tradeoff_no_single_axis")


def _build_seeded_env():
    return env_for("hard_discovery_budget_tradeoff_no_single_axis")
