"""Audit configuration for the shopping assistant domain."""

from __future__ import annotations

import importlib
import re
from typing import Any

from state_bench.audits._types import DomainAuditConfig, EntityPattern


def _build_env_index(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "product_ids": {p["product_id"] for p in raw.get("products", [])},
        "customer_ids": {c["customer_id"] for c in raw.get("customers", [])},
        "cart_ids": {c["cart_id"] for c in raw.get("carts", [])},
        "cart_owner": {c["cart_id"]: c["customer_id"] for c in raw.get("carts", [])},
    }


def _load_scenarios() -> dict[str, dict[str, Any]]:
    from domains.shopping_assistant.task_registry import ALL_SCENARIOS

    result: dict[str, dict[str, Any]] = {}
    for idx, module_path in enumerate(ALL_SCENARIOS, start=1):
        mod = importlib.import_module(module_path)
        task_json = getattr(mod, 'TASK_JSON', None)
        if not isinstance(task_json, dict):
            continue
        task_data = dict(task_json)
        task_data["task_id"] = f"{idx}-{task_data['task_id'].split('-', 1)[1]}"
        result[task_data['task_id']] = task_data
    return result


def get_audit_config() -> DomainAuditConfig:
    from domains.shopping_assistant.config import get_config
    from domains.shopping_assistant.user_attributes import CUSTOMER_ATTRIBUTES

    domain = get_config()

    return DomainAuditConfig(
        name="shopping_assistant",
        expected_task_count=150,
        entity_patterns=[
            EntityPattern(
                prefix="SP",
                regex=re.compile(r"\bSP-\d+\b"),
                env_lookup_key="product_ids",
            ),
            EntityPattern(
                prefix="CART",
                regex=re.compile(r"\bCART-shop_\d+\b"),
                env_lookup_key="cart_ids",
                ownership_field="customer_id",
                ownership_lookup_key="cart_owner",
            ),
        ],
        read_tools={
            "search_products",
            "get_product_details",
            "get_variants",
            "get_customer_account",
            "get_cart",
            "check_compatibility",
            "get_promotions",
            "get_policies",
            "validate_promo",
            "get_shipping_options",
        },
        write_tools=set(domain.write_tool_names),
        build_env_index=_build_env_index,
        customer_attributes=CUSTOMER_ATTRIBUTES,
        load_scenarios=_load_scenarios,
        policy_math_verifier=None,
    )
