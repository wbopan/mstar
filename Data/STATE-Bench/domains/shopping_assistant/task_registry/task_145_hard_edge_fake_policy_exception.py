"""Hard shopping extension task 145: hard_edge_fake_policy_exception."""

from __future__ import annotations

from domains.shopping_assistant.task_registry.hard_extension import env_for, task_json_for

TASK_ID = "145-hard_edge_fake_policy_exception"
TASK_JSON = task_json_for("hard_edge_fake_policy_exception")


def _build_seeded_env():
    return env_for("hard_edge_fake_policy_exception")
