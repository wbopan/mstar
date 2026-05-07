"""Hard shopping extension task 116: hard_loyalty_minimum_decline_no_topoff."""

from __future__ import annotations

from domains.shopping_assistant.task_registry.hard_extension import env_for, task_json_for

TASK_ID = "116-hard_loyalty_minimum_decline_no_topoff"
TASK_JSON = task_json_for("hard_loyalty_minimum_decline_no_topoff")


def _build_seeded_env():
    return env_for("hard_loyalty_minimum_decline_no_topoff")
