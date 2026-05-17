"""Hard shopping extension task 125: hard_promo_expired_code_no_replacement."""

from __future__ import annotations

from domains.shopping_assistant.task_registry.hard_extension import env_for, task_json_for

TASK_ID = "125-hard_promo_expired_code_no_replacement"
TASK_JSON = task_json_for("hard_promo_expired_code_no_replacement")


def _build_seeded_env():
    return env_for("hard_promo_expired_code_no_replacement")
