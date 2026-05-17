"""Hard shopping extension task 138: hard_cart_swap_preserve_promo_disclosure."""

from __future__ import annotations

from domains.shopping_assistant.task_registry.hard_extension import env_for, task_json_for

TASK_ID = "138-hard_cart_swap_preserve_promo_disclosure"
TASK_JSON = task_json_for("hard_cart_swap_preserve_promo_disclosure")


def _build_seeded_env():
    return env_for("hard_cart_swap_preserve_promo_disclosure")
