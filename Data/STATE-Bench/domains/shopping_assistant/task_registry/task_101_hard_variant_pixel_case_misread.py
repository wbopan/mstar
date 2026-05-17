"""Hard shopping extension task 101: hard_variant_pixel_case_misread."""

from __future__ import annotations

from domains.shopping_assistant.task_registry.hard_extension import env_for, task_json_for

TASK_ID = "101-hard_variant_pixel_case_misread"
TASK_JSON = task_json_for("hard_variant_pixel_case_misread")


def _build_seeded_env():
    return env_for("hard_variant_pixel_case_misread")
