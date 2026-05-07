"""Hard shopping extension task 140: hard_cart_cancel_points_before_remove."""

from __future__ import annotations

from domains.shopping_assistant.task_registry.hard_extension import env_for, task_json_for

TASK_ID = "140-hard_cart_cancel_points_before_remove"
TASK_JSON = task_json_for("hard_cart_cancel_points_before_remove")


def _build_seeded_env():
    return env_for("hard_cart_cancel_points_before_remove")
