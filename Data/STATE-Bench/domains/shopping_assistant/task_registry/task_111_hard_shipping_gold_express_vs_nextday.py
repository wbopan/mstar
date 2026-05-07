"""Hard shopping extension task 111: hard_shipping_gold_express_vs_nextday."""

from __future__ import annotations

from domains.shopping_assistant.task_registry.hard_extension import env_for, task_json_for

TASK_ID = "111-hard_shipping_gold_express_vs_nextday"
TASK_JSON = task_json_for("hard_shipping_gold_express_vs_nextday")


def _build_seeded_env():
    return env_for("hard_shipping_gold_express_vs_nextday")
