"""Hard shopping extension task 132: hard_discovery_accessory_for_purchase_history."""

from __future__ import annotations

from domains.shopping_assistant.task_registry.hard_extension import env_for, task_json_for

TASK_ID = "132-hard_discovery_accessory_for_purchase_history"
TASK_JSON = task_json_for("hard_discovery_accessory_for_purchase_history")


def _build_seeded_env():
    return env_for("hard_discovery_accessory_for_purchase_history")
