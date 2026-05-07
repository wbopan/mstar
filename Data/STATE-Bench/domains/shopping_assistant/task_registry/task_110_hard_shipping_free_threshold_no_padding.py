"""Hard shopping extension task 110: hard_shipping_free_threshold_no_padding."""

from __future__ import annotations

from domains.shopping_assistant.task_registry.hard_extension import env_for, task_json_for

TASK_ID = "110-hard_shipping_free_threshold_no_padding"
TASK_JSON = task_json_for("hard_shipping_free_threshold_no_padding")


def _build_seeded_env():
    return env_for("hard_shipping_free_threshold_no_padding")
