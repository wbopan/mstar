"""Hard shopping extension task 123: hard_promo_category_wrong_item."""

from __future__ import annotations

from domains.shopping_assistant.task_registry.hard_extension import env_for, task_json_for

TASK_ID = "123-hard_promo_category_wrong_item"
TASK_JSON = task_json_for("hard_promo_category_wrong_item")


def _build_seeded_env():
    return env_for("hard_promo_category_wrong_item")
