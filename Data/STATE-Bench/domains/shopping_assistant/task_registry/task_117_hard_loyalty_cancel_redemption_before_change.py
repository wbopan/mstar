"""Hard shopping extension task 117: hard_loyalty_cancel_redemption_before_change."""

from __future__ import annotations

from domains.shopping_assistant.task_registry.hard_extension import env_for, task_json_for

TASK_ID = "117-hard_loyalty_cancel_redemption_before_change"
TASK_JSON = task_json_for("hard_loyalty_cancel_redemption_before_change")


def _build_seeded_env():
    return env_for("hard_loyalty_cancel_redemption_before_change")
