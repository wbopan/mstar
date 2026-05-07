"""Hard shopping extension task 114: hard_inventory_backorder_deposit_disclosure."""

from __future__ import annotations

from domains.shopping_assistant.task_registry.hard_extension import env_for, task_json_for

TASK_ID = "114-hard_inventory_backorder_deposit_disclosure"
TASK_JSON = task_json_for("hard_inventory_backorder_deposit_disclosure")


def _build_seeded_env():
    return env_for("hard_inventory_backorder_deposit_disclosure")
