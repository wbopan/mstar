"""Hard shopping extension task 121: hard_loyalty_points_earned_post_promo."""

from __future__ import annotations

from domains.shopping_assistant.task_registry.hard_extension import env_for, task_json_for

TASK_ID = "121-hard_loyalty_points_earned_post_promo"
TASK_JSON = task_json_for("hard_loyalty_points_earned_post_promo")


def _build_seeded_env():
    return env_for("hard_loyalty_points_earned_post_promo")
