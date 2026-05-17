"""Hard shopping extension task 134: hard_discovery_compare_case_compatibility."""

from __future__ import annotations

from domains.shopping_assistant.task_registry.hard_extension import env_for, task_json_for

TASK_ID = "134-hard_discovery_compare_case_compatibility"
TASK_JSON = task_json_for("hard_discovery_compare_case_compatibility")


def _build_seeded_env():
    return env_for("hard_discovery_compare_case_compatibility")
