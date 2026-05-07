"""Hard shopping extension task 135: hard_discovery_price_ladder_with_no_mutation."""

from __future__ import annotations

from domains.shopping_assistant.task_registry.hard_extension import env_for, task_json_for

TASK_ID = "135-hard_discovery_price_ladder_with_no_mutation"
TASK_JSON = task_json_for("hard_discovery_price_ladder_with_no_mutation")


def _build_seeded_env():
    return env_for("hard_discovery_price_ladder_with_no_mutation")
