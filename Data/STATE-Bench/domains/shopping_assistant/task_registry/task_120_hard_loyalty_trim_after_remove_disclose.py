"""Hard shopping extension task 120: hard_loyalty_trim_after_remove_disclose."""

from __future__ import annotations

from domains.shopping_assistant.task_registry.hard_extension import env_for, task_json_for

TASK_ID = "120-hard_loyalty_trim_after_remove_disclose"
TASK_JSON = task_json_for("hard_loyalty_trim_after_remove_disclose")


def _build_seeded_env():
    return env_for("hard_loyalty_trim_after_remove_disclose")
