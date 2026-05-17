"""Hard shopping extension task 147: hard_compound_valid_promo_invalid_points."""

from __future__ import annotations

from domains.shopping_assistant.task_registry.hard_extension import env_for, task_json_for

TASK_ID = "147-hard_compound_valid_promo_invalid_points"
TASK_JSON = task_json_for("hard_compound_valid_promo_invalid_points")


def _build_seeded_env():
    return env_for("hard_compound_valid_promo_invalid_points")
