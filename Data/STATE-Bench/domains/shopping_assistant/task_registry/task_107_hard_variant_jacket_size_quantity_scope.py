"""Hard shopping extension task 107: hard_variant_jacket_size_quantity_scope."""

from __future__ import annotations

from domains.shopping_assistant.task_registry.hard_extension import env_for, task_json_for

TASK_ID = "107-hard_variant_jacket_size_quantity_scope"
TASK_JSON = task_json_for("hard_variant_jacket_size_quantity_scope")


def _build_seeded_env():
    return env_for("hard_variant_jacket_size_quantity_scope")
