"""Hard shopping extension task 136: hard_cart_remove_one_of_two_similar."""

from __future__ import annotations

from domains.shopping_assistant.task_registry.hard_extension import env_for, task_json_for

TASK_ID = "136-hard_cart_remove_one_of_two_similar"
TASK_JSON = task_json_for("hard_cart_remove_one_of_two_similar")


def _build_seeded_env():
    return env_for("hard_cart_remove_one_of_two_similar")
