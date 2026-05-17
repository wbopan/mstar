"""Hard shopping extension task 112: hard_shipping_platinum_nextday_without_promo."""

from __future__ import annotations

from domains.shopping_assistant.task_registry.hard_extension import env_for, task_json_for

TASK_ID = "112-hard_shipping_platinum_nextday_without_promo"
TASK_JSON = task_json_for("hard_shipping_platinum_nextday_without_promo")


def _build_seeded_env():
    return env_for("hard_shipping_platinum_nextday_without_promo")
