"""Hard shopping extension task 143: hard_edge_invalid_product_id_recover."""

from __future__ import annotations

from domains.shopping_assistant.task_registry.hard_extension import env_for, task_json_for

TASK_ID = "143-hard_edge_invalid_product_id_recover"
TASK_JSON = task_json_for("hard_edge_invalid_product_id_recover")


def _build_seeded_env():
    return env_for("hard_edge_invalid_product_id_recover")
