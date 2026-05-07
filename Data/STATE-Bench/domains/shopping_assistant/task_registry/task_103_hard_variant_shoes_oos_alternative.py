"""Hard shopping extension task 103: hard_variant_shoes_oos_alternative."""

from __future__ import annotations

from domains.shopping_assistant.task_registry.hard_extension import env_for, task_json_for

TASK_ID = "103-hard_variant_shoes_oos_alternative"
TASK_JSON = task_json_for("hard_variant_shoes_oos_alternative")


def _build_seeded_env():
    return env_for("hard_variant_shoes_oos_alternative")
