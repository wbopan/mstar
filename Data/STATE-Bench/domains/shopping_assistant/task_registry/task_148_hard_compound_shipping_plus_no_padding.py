"""Hard shopping extension task 148: hard_compound_shipping_plus_no_padding."""

from __future__ import annotations

from domains.shopping_assistant.task_registry.hard_extension import env_for, task_json_for

TASK_ID = "148-hard_compound_shipping_plus_no_padding"
TASK_JSON = task_json_for("hard_compound_shipping_plus_no_padding")


def _build_seeded_env():
    return env_for("hard_compound_shipping_plus_no_padding")
