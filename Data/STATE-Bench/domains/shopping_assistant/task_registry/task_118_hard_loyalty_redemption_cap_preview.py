"""Hard shopping extension task 118: hard_loyalty_redemption_cap_preview."""

from __future__ import annotations

from domains.shopping_assistant.task_registry.hard_extension import env_for, task_json_for

TASK_ID = "118-hard_loyalty_redemption_cap_preview"
TASK_JSON = task_json_for("hard_loyalty_redemption_cap_preview")


def _build_seeded_env():
    return env_for("hard_loyalty_redemption_cap_preview")
