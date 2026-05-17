"""Hard shopping extension task 119: hard_loyalty_cross_account_no_read."""

from __future__ import annotations

from domains.shopping_assistant.task_registry.hard_extension import env_for, task_json_for

TASK_ID = "119-hard_loyalty_cross_account_no_read"
TASK_JSON = task_json_for("hard_loyalty_cross_account_no_read")


def _build_seeded_env():
    return env_for("hard_loyalty_cross_account_no_read")
