"""Hard shopping extension task 139: hard_cart_gift_wrap_remove_only_one."""

from __future__ import annotations

from domains.shopping_assistant.task_registry.hard_extension import env_for, task_json_for

TASK_ID = "139-hard_cart_gift_wrap_remove_only_one"
TASK_JSON = task_json_for("hard_cart_gift_wrap_remove_only_one")


def _build_seeded_env():
    return env_for("hard_cart_gift_wrap_remove_only_one")
