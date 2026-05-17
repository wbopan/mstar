"""Hard shopping extension task 131: hard_discovery_no_result_relax_filters."""

from __future__ import annotations

from domains.shopping_assistant.task_registry.hard_extension import env_for, task_json_for

TASK_ID = "131-hard_discovery_no_result_relax_filters"
TASK_JSON = task_json_for("hard_discovery_no_result_relax_filters")


def _build_seeded_env():
    return env_for("hard_discovery_no_result_relax_filters")
