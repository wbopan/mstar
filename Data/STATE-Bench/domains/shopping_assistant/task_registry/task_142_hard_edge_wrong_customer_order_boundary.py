"""Hard shopping extension task 142: hard_edge_wrong_customer_order_boundary."""

from __future__ import annotations

from domains.shopping_assistant.task_registry.hard_extension import env_for, task_json_for

TASK_ID = "142-hard_edge_wrong_customer_order_boundary"
TASK_JSON = task_json_for("hard_edge_wrong_customer_order_boundary")


def _build_seeded_env():
    return env_for("hard_edge_wrong_customer_order_boundary")
