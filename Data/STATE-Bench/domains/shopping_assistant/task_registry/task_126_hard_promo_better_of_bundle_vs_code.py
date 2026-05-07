"""Hard shopping extension task 126: hard_promo_better_of_bundle_vs_code."""

from __future__ import annotations

from domains.shopping_assistant.task_registry.hard_extension import env_for, task_json_for

TASK_ID = "126-hard_promo_better_of_bundle_vs_code"
TASK_JSON = task_json_for("hard_promo_better_of_bundle_vs_code")


def _build_seeded_env():
    return env_for("hard_promo_better_of_bundle_vs_code")
