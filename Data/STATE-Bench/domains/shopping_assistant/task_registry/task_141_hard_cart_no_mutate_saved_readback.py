"""Hard shopping extension task 141: hard_cart_no_mutate_saved_readback."""

from __future__ import annotations

from domains.shopping_assistant.task_registry.hard_extension import env_for, task_json_for

TASK_ID = "141-hard_cart_no_mutate_saved_readback"
TASK_JSON = task_json_for("hard_cart_no_mutate_saved_readback")


def _build_seeded_env():
    return env_for("hard_cart_no_mutate_saved_readback")
