"""Shopping assistant generation hooks."""

from __future__ import annotations

import importlib
from copy import deepcopy
from pathlib import Path
from typing import Any

from domains.shopping_assistant.schemas import SAEnvironmentData
from domains.shopping_assistant.task_registry._replay_support import (
    infer_replay_trace,
    shopping_state_postprocessor,
    validate_legacy_requirement_coverage,
    LEGACY_STATE_REQUIREMENT_EXCEPTIONS_BY_TASK_SUFFIX,
)
from state_bench.generation import ReplayPolicy, ScenarioBuildResult
from state_bench.replay import ReplayMatcherConfig


_MATCHER_CONFIG = ReplayMatcherConfig(
    created_record_match_priority_by_entity={
        "cart_items": ("customer_id", "product_id", "variant_id", "gift_wrap", "quantity"),
    },
    created_record_ignored_fields_by_entity={
        "cart_items": {"cart_item_id", "customer_id", "product_id", "variant_id", "gift_wrap", "quantity"},
    },
)

SCENARIO_FAMILY_TO_TASK_TYPE = {
    "cart_management_a": "cart_management",
    "cart_management_b": "cart_management",
    "comparison_recommendation_a": "comparison_recommendation",
    "comparison_recommendation_b": "comparison_recommendation",
    "compatibility_variants_a": "compatibility_variants",
    "edge_cases_a": "edge_case_or_restraint",
    "inventory_shipping_a": "inventory_shipping",
    "inventory_shipping_b": "inventory_shipping",
    "loyalty_account_a": "loyalty_account",
    "loyalty_account_b": "loyalty_account",
    "product_search_discovery_a": "product_search_discovery",
    "product_search_discovery_b": "product_search_discovery",
    "promotions_discounts_a": "promotions_discounts",
    "promotions_discounts_b": "promotions_discounts",
}

HARD_EXTENSION_PREFIX_TO_TASK_TYPE = {
    "hard_cart_": "cart_management",
    "hard_compat_": "compatibility_variants",
    "hard_compound_": "compound_multi_policy",
    "hard_discovery_": "product_search_discovery",
    "hard_edge_": "edge_case_or_restraint",
    "hard_inventory_": "inventory_shipping",
    "hard_loyalty_": "loyalty_account",
    "hard_promo_": "promotions_discounts",
    "hard_shipping_": "inventory_shipping",
    "hard_variant_": "compatibility_variants",
}

SHOPPING_TASK_TYPES = frozenset(
    {
        "cart_management",
        "comparison_recommendation",
        "compatibility_variants",
        "compound_multi_policy",
        "edge_case_or_restraint",
        "inventory_shipping",
        "loyalty_account",
        "product_search_discovery",
        "promotions_discounts",
    }
)


def _scenario_family_for_module(registry, module_path: str) -> str:
    for family_module_path in registry._FAMILY_MODULES:
        family_module = importlib.import_module(family_module_path)
        if module_path in getattr(family_module, "TASK_MODULES", []):
            return family_module_path.rsplit(".", 1)[-1]
    raise ValueError(f"Shopping task module is not listed in a scenario family: {module_path}")


def _task_type_for_module(registry, module_path: str, task_id: str) -> str:
    family = _scenario_family_for_module(registry, module_path)
    if family == "hard_extension":
        slug = task_id.split("-", 1)[1]
        for prefix, task_type in HARD_EXTENSION_PREFIX_TO_TASK_TYPE.items():
            if slug.startswith(prefix):
                return task_type
        raise ValueError(f"Unmapped shopping hard-extension task slug for task_type: {slug}")
    try:
        return SCENARIO_FAMILY_TO_TASK_TYPE[family]
    except KeyError as exc:
        raise ValueError(f"Unmapped shopping scenario family for task_type: {family}") from exc


class ShoppingGenerationAdapter:
    def __init__(self, registry) -> None:
        self.registry = registry

    def enumerate(self, task_id_filter: set[int] | None = None) -> list[tuple[int, str]]:
        modules = list(self.registry.ALL_SCENARIOS)
        indexed = list(enumerate(modules, start=1))
        if task_id_filter is None:
            return indexed
        return [(idx, module_path) for idx, module_path in indexed if idx in task_id_filter]

    def build(self, idx: int, module_path: str) -> ScenarioBuildResult:
        mod = importlib.import_module(module_path)
        task_data = deepcopy(getattr(mod, "TASK_JSON"))
        task_data["task_id"] = f"{idx}-{task_data['task_id'].split('-', 1)[1]}"
        task_data["task_type"] = _task_type_for_module(self.registry, module_path, task_data["task_id"])
        task_data["task_env_path"] = f"domains/shopping_assistant/task_envs/{task_data['task_id']}.json"
        task_env = _load_task_env_or_module_seed(task_data["task_id"], mod)
        replay_trace = deepcopy(task_data.pop("_replay_trace", None)) or infer_replay_trace(task_data)
        task_data["_legacy_state_requirements"] = deepcopy(getattr(mod, "TASK_JSON").get("state_requirements", []))
        task_data["_legacy_state_requirement_exceptions"] = deepcopy(
            LEGACY_STATE_REQUIREMENT_EXCEPTIONS_BY_TASK_SUFFIX.get(task_data["task_id"].split("-", 1)[1], [])
        )
        return ScenarioBuildResult(
            task_data=task_data,
            task_env=task_env,
            now=task_data["now"],
            replay_policy=ReplayPolicy.STRICT_WRITE_REPLAY,
            replay_trace=replay_trace,
            matcher_config=_MATCHER_CONFIG,
            state_requirements_postprocessor=shopping_state_postprocessor,
            state_requirements_validator=validate_legacy_requirement_coverage,
        )


def _load_task_env_or_module_seed(task_id: str, mod: Any):
    seeded_builder = getattr(mod, "_build_seeded_env", None)
    if callable(seeded_builder):
        return seeded_builder()
    checked_in_env_path = Path(f"domains/shopping_assistant/task_envs/{task_id}.json")
    if not checked_in_env_path.exists():
        raise ValueError(f"Missing checked-in shopping task env: {checked_in_env_path}")
    return SAEnvironmentData.load(checked_in_env_path)


def get_generation_adapter(registry):
    return ShoppingGenerationAdapter(registry)
