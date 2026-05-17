"""Hard shopping extension task 127: hard_promo_remove_item_breaks_discount."""

from __future__ import annotations

from domains.shopping_assistant.task_registry.hard_extension import env_for, task_json_for

TASK_ID = "127-hard_promo_remove_item_breaks_discount"
TASK_JSON = task_json_for("hard_promo_remove_item_breaks_discount")


def _build_seeded_env():
    return env_for("hard_promo_remove_item_breaks_discount")
