"""Hard shopping extension task 108: hard_variant_case_cross_device_privacy."""

from __future__ import annotations

from domains.shopping_assistant.task_registry.hard_extension import env_for, task_json_for

TASK_ID = "108-hard_variant_case_cross_device_privacy"
TASK_JSON = task_json_for("hard_variant_case_cross_device_privacy")


def _build_seeded_env():
    return env_for("hard_variant_case_cross_device_privacy")
