"""Hard shopping extension task 146: hard_edge_no_policy_topic_fabrication."""

from __future__ import annotations

from domains.shopping_assistant.task_registry.hard_extension import env_for, task_json_for

TASK_ID = "146-hard_edge_no_policy_topic_fabrication"
TASK_JSON = task_json_for("hard_edge_no_policy_topic_fabrication")


def _build_seeded_env():
    return env_for("hard_edge_no_policy_topic_fabrication")
