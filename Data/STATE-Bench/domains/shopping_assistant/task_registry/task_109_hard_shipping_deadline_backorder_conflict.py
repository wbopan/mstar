"""Hard shopping extension task 109: hard_shipping_deadline_backorder_conflict."""

from __future__ import annotations

from domains.shopping_assistant.task_registry.hard_extension import env_for, task_json_for

TASK_ID = "109-hard_shipping_deadline_backorder_conflict"
TASK_JSON = task_json_for("hard_shipping_deadline_backorder_conflict")


def _build_seeded_env():
    return env_for("hard_shipping_deadline_backorder_conflict")
