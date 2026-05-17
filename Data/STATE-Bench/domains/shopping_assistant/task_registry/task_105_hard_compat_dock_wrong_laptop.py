"""Hard shopping extension task 105: hard_compat_dock_wrong_laptop."""

from __future__ import annotations

from domains.shopping_assistant.task_registry.hard_extension import env_for, task_json_for

TASK_ID = "105-hard_compat_dock_wrong_laptop"
TASK_JSON = task_json_for("hard_compat_dock_wrong_laptop")


def _build_seeded_env():
    return env_for("hard_compat_dock_wrong_laptop")
