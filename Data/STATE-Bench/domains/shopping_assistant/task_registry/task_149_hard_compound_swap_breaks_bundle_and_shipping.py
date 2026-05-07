"""Hard shopping extension task 149: hard_compound_swap_breaks_bundle_and_shipping."""

from __future__ import annotations

from domains.shopping_assistant.task_registry.hard_extension import env_for, task_json_for

TASK_ID = "149-hard_compound_swap_breaks_bundle_and_shipping"
TASK_JSON = task_json_for("hard_compound_swap_breaks_bundle_and_shipping")


def _build_seeded_env():
    return env_for("hard_compound_swap_breaks_bundle_and_shipping")
