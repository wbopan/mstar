"""Hard shopping extension task 144: hard_edge_already_empty_remove."""

from __future__ import annotations

from domains.shopping_assistant.task_registry.hard_extension import env_for, task_json_for

TASK_ID = "144-hard_edge_already_empty_remove"
TASK_JSON = task_json_for("hard_edge_already_empty_remove")


def _build_seeded_env():
    return env_for("hard_edge_already_empty_remove")
