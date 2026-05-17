"""Hard shopping extension task 150: hard_compound_invalid_compat_valid_readback."""

from __future__ import annotations

from domains.shopping_assistant.task_registry.hard_extension import env_for, task_json_for

TASK_ID = "150-hard_compound_invalid_compat_valid_readback"
TASK_JSON = task_json_for("hard_compound_invalid_compat_valid_readback")


def _build_seeded_env():
    return env_for("hard_compound_invalid_compat_valid_readback")
