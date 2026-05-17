"""Hard shopping extension task 128: hard_promo_two_codes_validate_before_apply."""

from __future__ import annotations

from domains.shopping_assistant.task_registry.hard_extension import env_for, task_json_for

TASK_ID = "128-hard_promo_two_codes_validate_before_apply"
TASK_JSON = task_json_for("hard_promo_two_codes_validate_before_apply")


def _build_seeded_env():
    return env_for("hard_promo_two_codes_validate_before_apply")
