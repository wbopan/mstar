"""Hard shopping extension task 122: hard_loyalty_first_time_vs_points_noncombine."""

from __future__ import annotations

from domains.shopping_assistant.task_registry.hard_extension import env_for, task_json_for

TASK_ID = "122-hard_loyalty_first_time_vs_points_noncombine"
TASK_JSON = task_json_for("hard_loyalty_first_time_vs_points_noncombine")


def _build_seeded_env():
    return env_for("hard_loyalty_first_time_vs_points_noncombine")
