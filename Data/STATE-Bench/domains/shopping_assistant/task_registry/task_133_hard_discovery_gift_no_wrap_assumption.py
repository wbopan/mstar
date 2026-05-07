"""Hard shopping extension task 133: hard_discovery_gift_no_wrap_assumption."""

from __future__ import annotations

from domains.shopping_assistant.task_registry.hard_extension import env_for, task_json_for

TASK_ID = "133-hard_discovery_gift_no_wrap_assumption"
TASK_JSON = task_json_for("hard_discovery_gift_no_wrap_assumption")


def _build_seeded_env():
    return env_for("hard_discovery_gift_no_wrap_assumption")
