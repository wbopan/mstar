"""Hard shopping extension task 137: hard_cart_quantity_cap_existing_line."""

from __future__ import annotations

from domains.shopping_assistant.task_registry.hard_extension import env_for, task_json_for

TASK_ID = "137-hard_cart_quantity_cap_existing_line"
TASK_JSON = task_json_for("hard_cart_quantity_cap_existing_line")


def _build_seeded_env():
    return env_for("hard_cart_quantity_cap_existing_line")
