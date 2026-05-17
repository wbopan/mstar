"""Hard shopping extension task 104: hard_variant_laptop_ram_price_delta."""

from __future__ import annotations

from domains.shopping_assistant.task_registry.hard_extension import env_for, task_json_for

TASK_ID = "104-hard_variant_laptop_ram_price_delta"
TASK_JSON = task_json_for("hard_variant_laptop_ram_price_delta")


def _build_seeded_env():
    return env_for("hard_variant_laptop_ram_price_delta")
