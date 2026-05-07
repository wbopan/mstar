"""Audit configuration for the customer support domain."""

from __future__ import annotations

import re
from typing import Any

from state_bench.audits._types import AuditFinding, CheckResult, DomainAuditConfig, EntityPattern, Severity


def _build_env_index(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "product_ids": {p["product_id"] for p in raw.get("products", [])},
        "order_ids": {o["order_id"] for o in raw.get("orders", [])},
        "order_owner": {o["order_id"]: o["customer_id"] for o in raw.get("orders", [])},
        "item_ids": {i["item_id"] for i in raw.get("order_items", [])},
        "customer_ids": {c["customer_id"] for c in raw.get("customers", [])},
        "warranty_ids": {w["warranty_id"] for w in raw.get("warranties", [])},
    }


def _load_scenarios() -> dict[str, dict[str, Any]]:
    """Load scenario data from builders, keyed by numbered task_id."""
    from domains.customer_support.task_registry import ALL_SCENARIOS, reset_counters

    reset_counters()
    result: dict[str, dict[str, Any]] = {}
    for idx, scenario_fn in enumerate(ALL_SCENARIOS, start=1):
        products, orders, items, warranties, task_data = scenario_fn()
        tid = task_data["task_id"]
        numbered_id = f"{idx}-{tid}"
        task_data["_numbered_id"] = numbered_id
        task_data["_scenario_products"] = products
        task_data["_scenario_orders"] = orders
        task_data["_scenario_items"] = items
        task_data["_scenario_warranties"] = warranties
        result[numbered_id] = task_data
    return result


def _policy_math_verifier() -> CheckResult:
    """Run domain-specific policy math verification."""
    from domains.customer_support.audits.policy_math import (
        VERIFIERS,
        verify_dollar_amounts,
    )
    from domains.customer_support.task_registry import ALL_SCENARIOS, reset_counters

    result = CheckResult(check_name="Policy math")
    reset_counters()

    for idx, scenario_fn in enumerate(ALL_SCENARIOS, start=1):
        products, orders, items, warranties, task_data = scenario_fn()
        tid = task_data.get("task_id", f"unknown_{idx}")
        task_type = task_data.get("task_type", "unknown")
        numbered_id = f"{idx}-{tid}"

        all_errors: list[str] = []
        # Run type-specific verifier
        verifier = VERIFIERS.get(task_type)
        if verifier:
            all_errors.extend(verifier(products, orders, items, warranties, task_data))
        # Run dollar amount check
        all_errors.extend(verify_dollar_amounts(task_data))

        for err in all_errors:
            result.findings.append(AuditFinding(Severity.CRITICAL, result.check_name, numbered_id, err))

    return result


def get_audit_config() -> DomainAuditConfig:
    from domains.customer_support.user_attributes import CUSTOMER_ATTRIBUTES

    return DomainAuditConfig(
        name="customer_support",
        expected_task_count=150,
        entity_patterns=[
            EntityPattern(
                prefix="ORD",
                regex=re.compile(r"\bORD-\d+\b"),
                env_lookup_key="order_ids",
                ownership_field="customer_id",
                ownership_lookup_key="order_owner",
            ),
            EntityPattern(prefix="ITEM", regex=re.compile(r"\bITEM-\d+\b"), env_lookup_key="item_ids"),
            EntityPattern(prefix="PROD", regex=re.compile(r"\bPROD-\d+\b"), env_lookup_key="product_ids"),
            EntityPattern(prefix="WRT", regex=re.compile(r"\bWRT-\d+\b"), env_lookup_key="warranty_ids"),
        ],
        read_tools={"get_order", "get_customer", "get_product", "get_policies", "get_warranty_status"},
        write_tools={"process_return", "process_refund", "cancel_order", "process_exchange", "process_warranty_claim"},
        policy_gate_map={
            "process_return": ["return", "refund"],
            "process_refund": ["refund"],
            "cancel_order": ["cancellation"],
            "process_exchange": ["exchange"],
            "process_warranty_claim": ["warranty"],
        },
        build_env_index=_build_env_index,
        customer_attributes=CUSTOMER_ATTRIBUTES,
        load_scenarios=_load_scenarios,
        policy_math_verifier=_policy_math_verifier,
    )
