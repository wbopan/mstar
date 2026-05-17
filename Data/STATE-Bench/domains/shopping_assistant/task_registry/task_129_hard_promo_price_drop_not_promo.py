"""Hard shopping extension task 129: hard_promo_price_drop_not_promo."""

from __future__ import annotations

from domains.shopping_assistant.task_registry.hard_extension import env_for, task_json_for

TASK_ID = "129-hard_promo_price_drop_not_promo"
TASK_JSON = task_json_for("hard_promo_price_drop_not_promo")


def _build_seeded_env():
    return env_for("hard_promo_price_drop_not_promo")
