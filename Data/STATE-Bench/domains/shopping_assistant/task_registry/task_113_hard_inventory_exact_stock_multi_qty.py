"""Hard shopping extension task 113: hard_inventory_exact_stock_multi_qty."""

from __future__ import annotations

from domains.shopping_assistant.task_registry.hard_extension import env_for, task_json_for

TASK_ID = "113-hard_inventory_exact_stock_multi_qty"
TASK_JSON = task_json_for("hard_inventory_exact_stock_multi_qty")


def _build_seeded_env():
    return env_for("hard_inventory_exact_stock_multi_qty")
