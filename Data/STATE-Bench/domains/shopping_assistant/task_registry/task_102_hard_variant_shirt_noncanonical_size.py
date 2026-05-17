"""Hard shopping extension task 102: hard_variant_shirt_noncanonical_size."""

from __future__ import annotations

from domains.shopping_assistant.task_registry.hard_extension import env_for, task_json_for

TASK_ID = "102-hard_variant_shirt_noncanonical_size"
TASK_JSON = task_json_for("hard_variant_shirt_noncanonical_size")


def _build_seeded_env():
    return env_for("hard_variant_shirt_noncanonical_size")
