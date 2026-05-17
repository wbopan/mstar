"""Hard shopping extension task 115: hard_shipping_remove_breaks_free_standard."""

from __future__ import annotations

from domains.shopping_assistant.task_registry.hard_extension import env_for, task_json_for

TASK_ID = "115-hard_shipping_remove_breaks_free_standard"
TASK_JSON = task_json_for("hard_shipping_remove_breaks_free_standard")


def _build_seeded_env():
    return env_for("hard_shipping_remove_breaks_free_standard")
