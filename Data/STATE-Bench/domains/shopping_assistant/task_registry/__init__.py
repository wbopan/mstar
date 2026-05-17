"""Shopping assistant task registry with semantic family discovery."""

from __future__ import annotations

import importlib
import re

from domains.shopping_assistant.task_registry._replay_support import (
    LEGACY_STATE_REQUIREMENT_EXCEPTIONS_BY_TASK_SUFFIX,
    infer_replay_trace,
    shopping_state_postprocessor,
    validate_legacy_requirement_coverage,
)

_TASK_PATTERN = re.compile(r"task_(\d+)_")
_FAMILY_MODULES = [
    "domains.shopping_assistant.task_registry.scenarios.product_search_discovery_a",
    "domains.shopping_assistant.task_registry.scenarios.product_search_discovery_b",
    "domains.shopping_assistant.task_registry.scenarios.comparison_recommendation_a",
    "domains.shopping_assistant.task_registry.scenarios.comparison_recommendation_b",
    "domains.shopping_assistant.task_registry.scenarios.cart_management_a",
    "domains.shopping_assistant.task_registry.scenarios.cart_management_b",
    "domains.shopping_assistant.task_registry.scenarios.promotions_discounts_a",
    "domains.shopping_assistant.task_registry.scenarios.promotions_discounts_b",
    "domains.shopping_assistant.task_registry.scenarios.loyalty_account_a",
    "domains.shopping_assistant.task_registry.scenarios.loyalty_account_b",
    "domains.shopping_assistant.task_registry.scenarios.compatibility_variants_a",
    "domains.shopping_assistant.task_registry.scenarios.inventory_shipping_a",
    "domains.shopping_assistant.task_registry.scenarios.inventory_shipping_b",
    "domains.shopping_assistant.task_registry.scenarios.edge_cases_a",
    "domains.shopping_assistant.task_registry.scenarios.hard_extension",
]


def _discover_task_modules() -> list[str]:
    discovered: list[tuple[int, str]] = []
    for family_module in _FAMILY_MODULES:
        mod = importlib.import_module(family_module)
        for module_path in getattr(mod, "TASK_MODULES", []):
            stem = module_path.rsplit(".", 1)[-1]
            match = _TASK_PATTERN.match(stem)
            if not match:
                raise ValueError(f"Shopping family module listed non-task module: {module_path}")
            discovered.append((int(match.group(1)), module_path))

    discovered.sort(key=lambda item: item[0])
    task_numbers = [number for number, _ in discovered]
    if task_numbers != list(range(1, len(discovered) + 1)):
        raise ValueError(f"Shopping task registry numbering drifted: {task_numbers}")
    return [module_path for _, module_path in discovered]


ALL_SCENARIOS: list[str] = _discover_task_modules()
