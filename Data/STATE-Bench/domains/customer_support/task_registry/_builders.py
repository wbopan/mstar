"""Shared builders for customer-support task generation, replay traces, and task environments."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from domains.customer_support.schemas import (
    CSEnvironmentData,
    Customer,
    Order,
    OrderItem,
    Product,
    Warranty,
)
from domains.customer_support.task_registry._task_summaries import TASK_SUMMARIES
from domains.customer_support.task_registry._user_sim_contexts import USER_SIM_CONTEXTS
from domains.customer_support.user_attributes import CUSTOMER_ATTRIBUTES

# ---------------------------------------------------------------------------
# ID generators
# ---------------------------------------------------------------------------

_product_counter = 1000
_order_counter = 5000
_item_counter = 8000
_warranty_counter = 3000


def _next_product_id() -> str:
    global _product_counter
    _product_counter += 1
    return f"PROD-{_product_counter}"


def _next_order_id() -> str:
    global _order_counter
    _order_counter += 1
    return f"ORD-{_order_counter}"


def _next_item_id() -> str:
    global _item_counter
    _item_counter += 1
    return f"ITEM-{_item_counter}"


def _next_warranty_id() -> str:
    global _warranty_counter
    _warranty_counter += 1
    return f"WRT-{_warranty_counter}"


def reset_counters() -> None:
    """Reset ID counters for deterministic generation."""
    global _product_counter, _order_counter, _item_counter, _warranty_counter
    _product_counter = 1000
    _order_counter = 5000
    _item_counter = 8000
    _warranty_counter = 3000


# ---------------------------------------------------------------------------
# Product catalog (reusable)
# ---------------------------------------------------------------------------

PRODUCT_CATALOG: dict[str, dict[str, Any]] = {
    "laptop_pro": {
        "name": "ProBook Laptop 15-inch",
        "category": "electronics",
        "subcategory": "laptop",
        "price": 1299,
        "warranty_months": 12,
        "return_window_days": 15,
        "restocking_fee_pct": 15,
        "weight_lbs": 4.5,
        "is_fragile": True,
    },
    "wireless_headphones": {
        "name": "SoundMax Wireless Headphones",
        "category": "electronics",
        "subcategory": "headphones",
        "price": 249,
        "warranty_months": 12,
        "return_window_days": 15,
        "restocking_fee_pct": 15,
        "weight_lbs": 0.6,
        "is_fragile": False,
    },
    "phone_case": {
        "name": "UltraShield Phone Case",
        "category": "accessories",
        "subcategory": "phone_case",
        "price": 35,
        "warranty_months": 3,
        "return_window_days": 30,
        "restocking_fee_pct": 0,
        "weight_lbs": 0.2,
        "is_fragile": False,
    },
    "cotton_shirt": {
        "name": "Premium Cotton Shirt",
        "category": "clothing",
        "subcategory": "shirt",
        "price": 59,
        "warranty_months": 0,
        "return_window_days": 30,
        "restocking_fee_pct": 0,
        "weight_lbs": 0.4,
        "is_fragile": False,
    },
    "blender": {
        "name": "PowerBlend Pro Blender",
        "category": "kitchen",
        "subcategory": "blender",
        "price": 89,
        "warranty_months": 6,
        "return_window_days": 30,
        "restocking_fee_pct": 0,
        "weight_lbs": 5.0,
        "is_fragile": True,
    },
    "novel": {
        "name": "The Great Algorithm (Hardcover)",
        "category": "books",
        "subcategory": "novel",
        "price": 24,
        "warranty_months": 0,
        "return_window_days": 14,
        "restocking_fee_pct": 0,
        "weight_lbs": 0.8,
        "is_fragile": False,
    },
    "usb_hub": {
        "name": "7-Port USB-C Hub",
        "category": "electronics",
        "subcategory": "accessory",
        "price": 45,
        "warranty_months": 12,
        "return_window_days": 15,
        "restocking_fee_pct": 15,
        "weight_lbs": 0.3,
        "is_fragile": False,
    },
    "smartphone": {
        "name": "TechPhone Pro 16",
        "category": "electronics",
        "subcategory": "phone",
        "price": 999,
        "warranty_months": 12,
        "return_window_days": 15,
        "restocking_fee_pct": 15,
        "weight_lbs": 0.4,
        "is_fragile": True,
    },
    "wireless_headphones_premium": {
        "name": "SoundMax Elite Wireless Headphones",
        "category": "electronics",
        "subcategory": "headphones_premium",
        "price": 349,
        "warranty_months": 12,
        "return_window_days": 15,
        "restocking_fee_pct": 15,
        "weight_lbs": 0.7,
        "is_fragile": False,
    },
    "kitchen_scale": {
        "name": "PrecisionScale Digital Kitchen Scale",
        "category": "kitchen",
        "subcategory": "scale",
        "price": 32,
        "warranty_months": 6,
        "return_window_days": 30,
        "restocking_fee_pct": 0,
        "weight_lbs": 1.2,
        "is_fragile": True,
    },
    "cotton_shirt_large": {
        "name": "Premium Cotton Shirt (Large)",
        "category": "clothing",
        "subcategory": "shirt",
        "price": 59,
        "warranty_months": 0,
        "return_window_days": 30,
        "restocking_fee_pct": 0,
        "weight_lbs": 0.4,
        "is_fragile": False,
    },
    "running_shoes": {
        "name": "SprintMax Running Shoes",
        "category": "clothing",
        "subcategory": "shoes",
        "price": 129,
        "warranty_months": 0,
        "return_window_days": 30,
        "restocking_fee_pct": 0,
        "weight_lbs": 1.5,
        "is_fragile": False,
    },
    "glass_vase": {
        "name": "Artisan Crystal Vase",
        "category": "kitchen",
        "subcategory": "vase",
        "price": 85,
        "warranty_months": 0,
        "return_window_days": 30,
        "restocking_fee_pct": 0,
        "weight_lbs": 3.0,
        "is_fragile": True,
    },
    "tablet": {
        "name": "SlateTab Pro 11-inch",
        "category": "electronics",
        "subcategory": "tablet",
        "price": 599,
        "warranty_months": 12,
        "return_window_days": 15,
        "restocking_fee_pct": 15,
        "weight_lbs": 1.1,
        "is_fragile": True,
    },
    "laptop_refurb": {
        "name": "ProBook Laptop 15-inch (Refurbished)",
        "category": "electronics",
        "subcategory": "laptop",
        "price": 799,
        "warranty_months": 3,
        "return_window_days": 15,
        "restocking_fee_pct": 15,
        "weight_lbs": 4.5,
        "is_fragile": True,
    },
    "budget_headphones": {
        "name": "SoundMax Basic Headphones",
        "category": "electronics",
        "subcategory": "headphones_budget",
        "price": 149,
        "warranty_months": 12,
        "return_window_days": 15,
        "restocking_fee_pct": 15,
        "weight_lbs": 0.5,
        "is_fragile": False,
    },
    "coffee_maker": {
        "name": "BrewPerfect Coffee Maker",
        "category": "kitchen",
        "subcategory": "coffee_maker",
        "price": 149,
        "warranty_months": 12,
        "return_window_days": 30,
        "restocking_fee_pct": 0,
        "weight_lbs": 6.0,
        "is_fragile": True,
    },
}


def build_product(catalog_key: str, product_id: str | None = None, **overrides: Any) -> Product:
    """Build a Product from the catalog, with optional overrides."""
    template = PRODUCT_CATALOG[catalog_key].copy()
    template.update(overrides)
    return Product(
        product_id=product_id or _next_product_id(),
        in_stock=template.pop("in_stock", True),
        current_price=template.pop("current_price", None),
        **template,
    )


# ---------------------------------------------------------------------------
# Order / Item builders
# ---------------------------------------------------------------------------


def build_order(
    customer_id: str,
    order_id: str | None = None,
    order_date: str = "2026-06-01T10:00:00",
    status: str = "delivered",
    shipping_status: str = "delivered",
    delivery_date: str | None = "2026-06-05T14:00:00",
    delivery_promised_date: str = "2026-06-05T18:00:00",
    shipping_cost: int = 8,
    discount_code: str | None = None,
    discount_amount: int = 0,
    payment_method: str = "credit_card",
    payment_details: dict[str, int] | None = None,
    is_gift: bool = False,
    gift_sender: str | None = None,
    signature_required: bool = False,
    signature_on_file: str | None = None,
    shipping_method: str = "standard",
) -> Order:
    """Build an Order with computed subtotal/total (items added later)."""
    return Order(
        order_id=order_id or _next_order_id(),
        customer_id=customer_id,
        order_date=order_date,
        status=status,
        shipping_status=shipping_status,
        shipping_method=shipping_method,
        shipping_cost=shipping_cost,
        tracking_number=f"TRK{int(hashlib.sha256((order_id or customer_id).encode('utf-8')).hexdigest()[:8], 16) % 10**8:08d}",
        delivery_date=delivery_date,
        delivery_promised_date=delivery_promised_date,
        signature_required=signature_required,
        signature_on_file=signature_on_file,
        payment_method=payment_method,
        payment_details=payment_details or ({payment_method: 0}),  # total filled later
        discount_code=discount_code,
        discount_amount=discount_amount,
        is_gift=is_gift,
        gift_sender=gift_sender,
    )


def build_order_item(
    order_id: str,
    product: Product,
    item_id: str | None = None,
    quantity: int = 1,
    unit_price: int | None = None,
    item_status: str = "delivered",
) -> OrderItem:
    """Build an OrderItem from a Product."""
    return OrderItem(
        item_id=item_id or _next_item_id(),
        order_id=order_id,
        product_id=product.product_id,
        quantity=quantity,
        unit_price=unit_price if unit_price is not None else product.price,
        item_status=item_status,
    )


def finalize_order(order: Order, items: list[OrderItem]) -> None:
    """Compute subtotal, total_paid, and payment_details from items."""
    order.subtotal = sum(i.unit_price * i.quantity for i in items)
    order.total_paid = order.subtotal - order.discount_amount + order.shipping_cost
    # Update payment_details with actual total
    if order.payment_method != "split":
        order.payment_details = {order.payment_method: order.total_paid}


def build_warranty(
    order_id: str,
    item_id: str,
    product: Product,
    warranty_id: str | None = None,
    warranty_type: str = "manufacturer",
    start_date: str = "2026-06-05",
    claim_count: int = 0,
    max_claims: int = 3,
    months_override: int | None = None,
) -> Warranty:
    """Build a Warranty from a Product."""
    from datetime import datetime, timedelta

    months = months_override if months_override is not None else product.warranty_months
    start_dt = datetime.fromisoformat(start_date)
    end_dt = start_dt + timedelta(days=months * 30)

    return Warranty(
        warranty_id=warranty_id or _next_warranty_id(),
        order_id=order_id,
        item_id=item_id,
        product_id=product.product_id,
        warranty_type=warranty_type,
        start_date=start_date,
        end_date=end_dt.strftime("%Y-%m-%d"),
        status="active" if months > 0 else "expired",
        claim_count=claim_count,
        max_claims=max_claims,
        coverage="repair_or_replace" if product.price >= 100 else "full_replacement",
    )


ScenarioResult = tuple[list[Product], list[Order], list[OrderItem], list[Warranty], dict[str, Any]]


# ---------------------------------------------------------------------------
# Ground truth trace builder
# ---------------------------------------------------------------------------


def _canonical_scenario_template(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize scenario-template aliases into a stable internal shape."""
    scenario = dict(raw or {})

    def _first_str(*keys: str) -> str | None:
        for key in keys:
            value = scenario.get(key)
            if isinstance(value, str) and value:
                return value
        return None

    def _list_of_str(*keys: str) -> list[str]:
        for key in keys:
            value = scenario.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, str) and item]
        return []

    primary_order_id = _first_str("primary_order_id", "order_id")
    secondary_order_id = _first_str("secondary_order_id", "order_id_2")
    primary_item_id = _first_str("primary_item_id", "item_id", "return_item_id")
    target_product_id = _first_str("target_product_id", "new_product_id")
    target_item_ids = _list_of_str("target_item_ids", "return_item_ids")

    if primary_order_id is not None:
        scenario["primary_order_id"] = primary_order_id
        scenario.setdefault("order_id", primary_order_id)
    if secondary_order_id is not None:
        scenario["secondary_order_id"] = secondary_order_id
        scenario.setdefault("order_id_2", secondary_order_id)
    if primary_item_id is not None:
        scenario["primary_item_id"] = primary_item_id
        scenario.setdefault("item_id", primary_item_id)
        scenario.setdefault("return_item_id", primary_item_id)
    if target_product_id is not None:
        scenario["target_product_id"] = target_product_id
        scenario.setdefault("new_product_id", target_product_id)
    if target_item_ids:
        scenario["target_item_ids"] = target_item_ids
        scenario.setdefault("return_item_ids", list(target_item_ids))

    return scenario


def _parse_replay_step_string(raw_step: Any) -> tuple[str, str | None, bool | None] | None:
    if not isinstance(raw_step, str):
        return None
    text = raw_step.strip()
    if not text:
        return None

    match = re.fullmatch(r"([A-Za-z_]+)(?:\((.*)\))?", text)
    if not match:
        return None
    name = match.group(1)
    arg_blob = match.group(2)
    label: str | None = None
    confirm: bool | None = None
    if arg_blob:
        tokens = [token.strip() for token in arg_blob.split(",") if token.strip()]
        non_control: list[str] = []
        for token in tokens:
            lowered = token.lower()
            if lowered == "preview":
                confirm = False
            elif lowered == "confirm":
                confirm = True
            else:
                non_control.append(token)
        if non_control:
            label = ", ".join(non_control)
    return name, label, confirm


def _normalize_replay_steps(raw_steps: list[Any]) -> list[dict[str, Any]]:
    """Normalize replay steps into structured dicts for canonical task traces."""
    normalized: list[dict[str, Any]] = []
    for raw_step in raw_steps:
        if isinstance(raw_step, dict):
            name = raw_step.get("name")
            if isinstance(name, str) and name:
                normalized.append(
                    {
                        "name": name,
                        "label": raw_step.get("label") if isinstance(raw_step.get("label"), str) else None,
                        "confirm": raw_step.get("confirm") if isinstance(raw_step.get("confirm"), bool) else None,
                    }
                )
            continue
        parsed = _parse_replay_step_string(raw_step)
        if parsed is None:
            continue
        name, label, confirm = parsed
        normalized.append({"name": name, "label": label, "confirm": confirm})
    return normalized


def build_expected_outcome(task_type: str, policy_results: dict[str, Any], scenario: dict[str, Any]) -> str:
    """Generate expected outcome text from policy computation results.

    This is a rubric for the satisfaction judge — structured checklist of
    what the agent should communicate to the customer.
    """
    parts: list[str] = []

    if task_type == "return_item":
        parts.append("Item returned.")
        parts.append(
            f"Refund of ${policy_results['refund_amount']} to {policy_results['refund_method'].replace('_', ' ')}."
        )
        if policy_results.get("restocking_fee", 0) > 0:
            parts.append(f"Agent must communicate ${policy_results['restocking_fee']} restocking fee deduction.")
        if policy_results.get("restocking_fee", 0) == 0 and policy_results.get("restocking_waived"):
            parts.append("Agent must mention restocking fee is waived due to membership tier.")
        if policy_results.get("discount_adjustment", 0) > 0:
            parts.append(
                f"Agent must explain promo discount redistribution (${policy_results['discount_adjustment']} deducted from refund)."
            )
        if policy_results.get("shipping_refund"):
            parts.append("Free return shipping label provided.")
        if policy_results.get("store_credit_only"):
            parts.append("Agent must explain refund is store credit only (outside return window).")
        if policy_results.get("is_gift_return"):
            parts.append("Agent must explain gift return refund is at current product price as store credit.")

    elif task_type == "price_match_refund":
        refund = policy_results.get("refund_amount")
        if refund is not None:
            parts.append(f"Price-match refund of ${refund} issued.")
        else:
            parts.append("Price-match refund issued.")
        parts.append("Order remains active; no cancellation or return is performed.")
        parts.append("No fees are charged.")

    elif task_type == "cancel_order":
        cancel = policy_results
        if cancel.get("cancellation_fee", 0) > 0:
            parts.append(f"Order cancelled with ${cancel['cancellation_fee']} intercept fee.")
            parts.append("Agent must communicate the intercept fee before confirming.")
        else:
            parts.append("Order cancelled. Full refund, no fees.")
        if cancel.get("split_refund"):
            parts.append("Agent must explain refund is split across original payment methods.")
        refund = cancel.get("refund_amount")
        if refund is not None:
            parts.append(f"Total refund: ${refund}.")

    elif task_type == "shipping_claim":
        claim = policy_results
        if claim.get("resolution") == "investigation_required":
            parts.append("Agent must explain investigation is required (3-5 business days) before resolution.")
            parts.append("Agent must NOT issue immediate refund or replacement.")
        elif claim.get("resolution") == "denied":
            parts.append(f"Claim denied. Reason: {claim.get('reason', 'policy violation')}.")
            parts.append("Agent must explain why the claim was denied.")
        elif claim.get("resolution") == "refund":
            parts.append(f"Refund of ${claim.get('refund_amount', 0)} issued.")
        elif claim.get("resolution") == "compensation":
            parts.append(f"Compensation of ${claim.get('compensation_amount', 0)} issued.")
            if claim.get("tier_multiplier", 1.0) > 1.0:
                parts.append(f"Agent must mention {claim['tier_multiplier']}x tier multiplier applied.")
        if claim.get("goodwill_credit", 0) > 0:
            if claim.get("resolution") == "compensation":
                parts.append(f"Agent should mention ${claim['goodwill_credit']} goodwill credit.")
            else:
                parts.append(f"Agent should mention ${claim['goodwill_credit']} goodwill credit for fragile item.")

    elif task_type == "warranty_claim":
        warranty = policy_results
        resolution = warranty.get("resolution", "repair")
        parts.append(f"Warranty claim processed. Resolution: {resolution.replace('_', ' ')}.")
        if warranty.get("cost", 0) > 0:
            parts.append(f"Agent must communicate cost of ${warranty['cost']} to customer.")
        if "replacement" in resolution:
            parts.append("Replacement item will be shipped.")
        if warranty.get("recurring"):
            parts.append("Agent should acknowledge this is a recurring issue and explain automatic replacement policy.")

    elif task_type == "exchange_item":
        exchange = policy_results
        if exchange.get("denied"):
            parts.append(f"Exchange denied. Reason: {exchange.get('reason', 'outside window')}.")
        elif exchange.get("out_of_stock"):
            parts.append("Requested item out of stock. Agent must offer store credit or waitlist.")
        else:
            if exchange.get("customer_pays", 0) > 0:
                parts.append(f"Exchange processed. Customer pays ${exchange['customer_pays']} price difference.")
            elif exchange.get("store_credit_refund", 0) > 0:
                parts.append(
                    f"Exchange processed. ${exchange['store_credit_refund']} difference refunded as store credit (not cash)."
                )
                parts.append("Agent must explain difference goes to store credit, not original payment.")
            else:
                parts.append("Exchange processed. Free same-variant swap.")

    elif task_type == "compound":
        # Compound tasks have custom outcomes — use the phases list
        for phase in policy_results.get("phases", []):
            parts.append(phase)

    elif task_type == "edge_case":
        edge = policy_results
        if edge.get("no_action"):
            parts.append("No state change expected.")
        parts.append(edge.get('agent_must', 'Handle the case gracefully.').rstrip('.') + '.')

    # Universal override: if policy_results has a "phases" key, use it for any task type
    if policy_results.get("phases") and task_type != "compound":
        parts.extend(policy_results["phases"])

    if not parts:
        parts.append("Task completed.")

    return " ".join(parts)


def build_ground_truth_trace(
    task_type: str,
    replay_steps: list[Any],
    policy_results: dict[str, Any],
    scenario: dict[str, Any],
) -> dict[str, Any]:
    """Build the canonical ground-truth trace for a task."""
    return {
        "replay_steps": _normalize_replay_steps(replay_steps),
        "policy_results": policy_results,
        "expected_outcome": build_expected_outcome(task_type, policy_results, scenario),
    }


def build_replay_trace(
    task_data: dict[str, Any],
    env_data: CSEnvironmentData,
) -> list[dict[str, Any]]:
    """Build canonical customer-support scenario intent into an executable replay trace.

    This is a shared generation helper. It reuses the checked-in scenario's
    structured ``ground_truth_trace.replay_steps`` and scenario data to synthesize
    deterministic tool calls that can be executed against the task-local
    environment snapshot to derive state requirements.
    """
    ground_truth = task_data.get("ground_truth_trace", {})
    replay_steps = ground_truth.get("replay_steps")
    if not isinstance(replay_steps, list):
        return []

    scenario = _canonical_scenario_template(task_data.get("scenario_template", {}))
    db_assertions = task_data.get("db_assertions", [])
    policy_results = ground_truth.get("policy_results", {})
    context = _ReplayBridgeContext(
        env_data,
        scenario,
        db_assertions,
        policy_results,
        description=task_data.get("description", ""),
        opening_message=task_data.get("opening_message", ""),
    )

    replay: list[dict[str, Any]] = []
    for step_data in replay_steps:
        step = _parse_replay_step(step_data)
        if step is None:
            continue
        built = _build_replay_step(step, context, task_data.get("task_type", ""))
        if built is None:
            continue
        if isinstance(built, list):
            replay.extend(built)
        else:
            replay.append(built)
    return replay


class _ReplayBridgeContext:
    def __init__(
        self,
        env_data: CSEnvironmentData,
        scenario: dict[str, Any],
        db_assertions: list[dict[str, Any]],
        policy_results: dict[str, Any],
        description: str = "",
        opening_message: str = "",
    ) -> None:
        self.env_data = env_data
        self.scenario = scenario
        self.db_assertions = db_assertions
        self.policy_results = policy_results
        self.description = description if isinstance(description, str) else ""
        self.opening_message = opening_message if isinstance(opening_message, str) else ""

        self.orders = {order.order_id: order for order in env_data.orders}
        self.items = {item.item_id: item for item in env_data.order_items}
        self.products = {product.product_id: product for product in env_data.products}
        self.warranties = {warranty.warranty_id: warranty for warranty in env_data.warranties}

        self.items_by_order: dict[str, list[OrderItem]] = {}
        for item in env_data.order_items:
            self.items_by_order.setdefault(item.order_id, []).append(item)

        self.item_assertions: dict[str, dict[str, Any]] = {}
        for assertion in db_assertions:
            if not isinstance(assertion, dict):
                continue
            booking_id = assertion.get("booking_id")
            if not isinstance(booking_id, str) or booking_id.startswith("{{"):
                continue
            if booking_id not in self.items:
                continue
            self.item_assertions.setdefault(booking_id, {})[assertion.get("field")] = assertion.get("expected")

        self.explicit_return_ids = [
            item_id for item_id in self._scenario_list("target_item_ids", "return_item_ids") if item_id in self.items
        ]
        if not self.explicit_return_ids:
            single_return = self.scenario.get("return_item_id")
            if isinstance(single_return, str) and single_return in self.items:
                self.explicit_return_ids = [single_return]

        self.cancel_item_ids = sorted(
            item_id
            for item_id, fields in self.item_assertions.items()
            if fields.get("item_status") == "cancelled"
        )

        self.return_queue = list(self.explicit_return_ids)
        if not self.return_queue and self.scenario.get("order_id") in self.items_by_order:
            order_items = self.items_by_order[self.scenario["order_id"]]
            return_targets = [
                item.item_id
                for item in order_items
                if self.item_assertions.get(item.item_id, {}).get("item_status") == "returned"
            ]
            self.return_queue = return_targets
        if not self.return_queue and self.scenario.get("order_id") in self.items_by_order:
            self.return_queue = [item.item_id for item in self.items_by_order[self.scenario["order_id"]]]

        self.refund_queue = self._build_refund_queue()
        self.seen_returns: list[str] = []
        self.seen_refunds: list[tuple[str, int]] = []
        self.used_item_ids: set[str] = set()
        self.pending_return_item_id: str | None = None
        self.pending_return_reason: str | None = None
        self.pending_refund_entry: dict[str, Any] | None = None
        self.pending_cancel_item_ids: list[str] | None = None
        self.pending_exchange_item_id: str | None = None
        self.pending_warranty_item_id: str | None = None

    def _scenario_list(self, *keys: str) -> list[str]:
        for key in keys:
            value = self.scenario.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, str)]
        return []

    def _build_refund_queue(self) -> list[dict[str, Any]]:
        refund_queue: list[dict[str, Any]] = []

        for item_id, fields in self.item_assertions.items():
            amount = fields.get("refund_amount")
            if amount is None or not isinstance(amount, int):
                continue
            refund_queue.append(
                {
                    "item_id": item_id,
                    "amount": amount,
                    "refund_method": fields.get("refund_method") or "original_payment",
                    "kind": "refund",
                }
            )

        # Preserve declaration order and dedupe by (item, amount, method).
        seen: set[tuple[str, int, str]] = set()
        deduped: list[dict[str, Any]] = []
        for entry in refund_queue:
            key = (entry["item_id"], entry["amount"], entry["refund_method"])
            if key in seen:
                continue
            seen.add(key)
            deduped.append(entry)
        return deduped

    def resolve_order_id(self, hint: str | None = None) -> str:
        if hint and hint in self.orders:
            return hint
        order_id = self.scenario.get("primary_order_id") or self.scenario.get("order_id")
        if isinstance(order_id, str) and order_id in self.orders:
            return order_id
        if len(self.orders) == 1:
            return next(iter(self.orders))
        raise ValueError("Unable to resolve order_id for replay step")

    def resolve_customer_id(self) -> str:
        customer_id = self.scenario.get("customer_id")
        if isinstance(customer_id, str) and customer_id:
            return customer_id
        raise ValueError("Unable to resolve customer_id for replay step")

    def resolve_goodwill_item_id(self, label: str | None = None) -> str:
        if label:
            resolved = self._match_item_label(label)
            if resolved is not None:
                return resolved

        policy_phases = self.policy_results.get("phases", [])
        fragile_hint = " ".join(phase for phase in policy_phases if isinstance(phase, str)).lower()
        for item_id, item in self.items.items():
            product = self.products.get(item.product_id)
            reason = self.item_assertions.get(item_id, {}).get("return_reason")
            if not isinstance(reason, str):
                reason = self._reason_from_item_context(item_id, label) or self._reason_from_item_context(item_id, "goodwill")
            if reason == "damaged_in_transit" and product is not None and getattr(product, "is_fragile", False):
                return item_id
            if reason == "damaged_in_transit" and "fragile" in fragile_hint:
                return item_id

        if self.seen_returns:
            return self.seen_returns[-1]
        return self.resolve_item_id(label, "refund")

    def resolve_item_id(self, label: str | None, action: str) -> str:
        if label and label in self.items:
            return label

        if action == "return":
            if self.pending_return_item_id is not None:
                return self.pending_return_item_id
            if label:
                resolved = self._match_item_label(label)
                if resolved is not None:
                    if resolved in self.return_queue:
                        self.return_queue = [item_id for item_id in self.return_queue if item_id != resolved]
                    return resolved
            if self.return_queue:
                item_id = self.return_queue.pop(0)
                return item_id
            order_id = self.scenario.get("primary_order_id") or self.scenario.get("order_id")
            if isinstance(order_id, str) and order_id in self.items_by_order:
                remaining = [item.item_id for item in self.items_by_order[order_id] if item.item_id not in self.used_item_ids]
                if remaining:
                    return remaining[0]

        if action == "refund":
            if self.pending_refund_entry is not None:
                return self.pending_refund_entry["item_id"]
            if label:
                resolved = self._match_item_label(label)
                if resolved is not None:
                    return resolved
            for key in ("primary_item_id", "return_item_id", "item_id"):
                value = self.scenario.get(key)
                if isinstance(value, str) and value in self.items:
                    return value
            if self.seen_returns:
                return self.seen_returns[-1]
            if len(self.items) == 1:
                return next(iter(self.items))

        if action in {"exchange", "warranty"}:
            if action == "exchange" and self.pending_exchange_item_id is not None:
                return self.pending_exchange_item_id
            if action == "warranty" and self.pending_warranty_item_id is not None:
                return self.pending_warranty_item_id
            for key in ("primary_item_id", "item_id", "return_item_id"):
                value = self.scenario.get(key)
                if isinstance(value, str) and value in self.items:
                    return value

        if len(self.items) == 1:
            return next(iter(self.items))
        raise ValueError(f"Unable to resolve item_id for replay step {action!r} label={label!r}")

    def resolve_product_id(self, label: str | None = None) -> str:
        new_product_id = self.scenario.get("target_product_id") or self.scenario.get("new_product_id")
        if isinstance(new_product_id, str) and new_product_id in self.products:
            return new_product_id
        target_item_id = None
        for item_key in ("primary_item_id", "item_id", "return_item_id"):
            item_id = self.scenario.get(item_key)
            if isinstance(item_id, str) and item_id in self.items:
                target_item_id = item_id
                break
        if target_item_id is None:
            order_id = self.scenario.get("primary_order_id") or self.scenario.get("order_id")
            if isinstance(order_id, str) and order_id in self.items_by_order and len(self.items_by_order[order_id]) == 1:
                target_item_id = self.items_by_order[order_id][0].item_id
        if len(self.products) == 2:
            if target_item_id is not None:
                current_product_id = self.items[target_item_id].product_id
                other_products = [pid for pid in self.products if pid != current_product_id]
                if other_products:
                    return other_products[0]
        if target_item_id is not None:
            product_id = self.items[target_item_id].product_id
            if product_id in self.products:
                return product_id
        if label:
            lowered = label.lower().replace("_", " ")
            for product_id, product in self.products.items():
                haystacks = {product_id.lower(), product.name.lower(), product.category.lower(), product.subcategory.lower()}
                if any(lowered in hay for hay in haystacks):
                    return product_id
        if len(self.products) == 1:
            return next(iter(self.products))
        raise ValueError(f"Unable to resolve product_id for replay step label={label!r}")

    def resolve_warranty_id(self) -> str:
        warranty_id = self.scenario.get("warranty_id")
        if isinstance(warranty_id, str) and warranty_id in self.warranties:
            return warranty_id
        if len(self.warranties) == 1:
            return next(iter(self.warranties))
        raise ValueError("Unable to resolve warranty_id for replay step")

    def resolve_return_reason(self, item_id: str, label: str | None = None) -> str:
        explicit = self._reason_from_text(label)
        if explicit is not None:
            return explicit

        explicit_task_reason = self._explicit_reason_from_task_text()
        if explicit_task_reason is not None:
            return explicit_task_reason

        contextual = self._reason_from_item_context(item_id, label)
        if contextual is not None:
            return contextual

        inferred = self._reason_from_task_text()
        if inferred is not None:
            return inferred

        expected = self.item_assertions.get(item_id, {}).get("return_reason")
        if isinstance(expected, str):
            return expected
        return "changed_mind"

    def _reason_from_text(self, text: str | None) -> str | None:
        if not text:
            return None
        lowered = text.lower()
        if "defective" in lowered or "defect" in lowered:
            return "defective"
        if "wrong" in lowered:
            return "wrong_item"
        if "damaged" in lowered or "shattered" in lowered or "cracked" in lowered:
            return "damaged_in_transit"
        if "missing" in lowered or "not received" in lowered or "never got" in lowered:
            return "missing"
        if "changed_mind" in lowered or "changed mind" in lowered or "buyer's remorse" in lowered:
            return "changed_mind"
        return None

    def _reason_from_item_context(self, item_id: str, label: str | None) -> str | None:
        item = self.items.get(item_id)
        product = self.products.get(item.product_id) if item is not None else None
        search_terms: list[str] = []
        if label:
            search_terms.append(label.lower().replace("_", " "))
        if product is not None:
            search_terms.extend(
                [
                    product.name.lower(),
                    product.category.lower(),
                    product.subcategory.lower(),
                ]
            )
            search_terms.extend(token for token in re.split(r"[^a-z0-9]+", product.name.lower()) if len(token) >= 4)

        phase_hits = self.policy_results.get("phases", [])
        if isinstance(phase_hits, list):
            for phase in phase_hits:
                if not isinstance(phase, str):
                    continue
                lowered_phase = phase.lower()
                for term in search_terms:
                    if term and term in lowered_phase:
                        reason = self._reason_from_text(lowered_phase)
                        if reason is not None:
                            return reason

        haystack = f"{self.description}\n{self.opening_message}".lower()
        for term in search_terms:
            if not term or len(term) < 4:
                continue
            for match in re.finditer(re.escape(term), haystack):
                start = max(0, match.start() - 80)
                end = min(len(haystack), match.end() + 80)
                reason = self._reason_from_text(haystack[start:end])
                if reason is not None:
                    return reason
        return None

    def _explicit_reason_from_task_text(self) -> str | None:
        if isinstance(self.policy_results.get("return_reason"), str):
            return self.policy_results["return_reason"]

        desc = self.description.lower()
        for phrase in ("classify as ", "correct classification: ", "must classify as ", "agent must classify as " ):
            idx = desc.find(phrase)
            if idx == -1:
                continue
            prefix = desc[max(0, idx - 4):idx].strip()
            if prefix.endswith("not"):
                continue
            after = desc[idx + len(phrase):].strip().split(",")[0].split(".")[0].split(" ")[0]
            if after in {"changed_mind", "defective", "wrong_item", "damaged_in_transit", "missing"}:
                return after

        if "not defective" in desc or "not a defect" in desc or "user error" in desc:
            return "changed_mind"
        if "not damaged" in desc or "not classify as damaged" in desc:
            return "changed_mind"
        return None

    def _reason_from_task_text(self) -> str | None:
        explicit = self._explicit_reason_from_task_text()
        if explicit is not None:
            return explicit

        desc = self.description.lower()
        opening = self.opening_message.lower()
        for text in (desc, opening):
            reason = self._reason_from_text(text)
            if reason is not None:
                return reason
        return None

    def resolve_refund_entry(self, label: str | None, task_type: str) -> dict[str, Any] | None:
        normalized_label = (label or "").strip().lower()
        if normalized_label and any(token in normalized_label for token in ("shipping", "bulk", "repeat", "clawback", "fee")):
            return None

        if normalized_label and "goodwill" in normalized_label:
            amount = self._extract_amount_from_policy_text("goodwill")
            if amount is not None:
                item_id = self.resolve_goodwill_item_id(label)
                entry = {
                    "item_id": item_id,
                    "amount": amount,
                    "refund_method": self.item_assertions.get(item_id, {}).get("refund_method") or "original_payment",
                    "kind": "goodwill",
                }
                self.pending_refund_entry = dict(entry)
                return entry

        if normalized_label and "comp" in normalized_label:
            amount = self._policy_amount("total_compensation", "compensation_amount", "refund_amount")
            if amount is not None:
                item_id = self.resolve_item_id(label, "refund")
                entry = {
                    "item_id": item_id,
                    "amount": amount,
                    "refund_method": self.item_assertions.get(item_id, {}).get("refund_method") or "original_payment",
                    "kind": "compensation",
                }
                self.pending_refund_entry = dict(entry)
                return entry

        if task_type == "price_match_refund":
            amount = self._policy_amount("refund_amount")
            if amount is not None:
                item_id = self.resolve_item_id(label, "refund")
                return {
                    "item_id": item_id,
                    "amount": amount,
                    "refund_method": self.item_assertions.get(item_id, {}).get("refund_method") or "original_payment",
                    "kind": "refund",
                }

        if task_type == "shipping_claim":
            amount = self._policy_amount("total_compensation", "refund_amount", "compensation_amount")
            if amount is not None:
                item_id = self.resolve_item_id(label, "refund")
                return {
                    "item_id": item_id,
                    "amount": amount,
                    "refund_method": self.item_assertions.get(item_id, {}).get("refund_method") or "original_payment",
                    "kind": "refund",
                }

        if not normalized_label and self.seen_returns:
            goodwill_amount = self._extract_amount_from_policy_text("goodwill")
            if goodwill_amount is not None:
                item_id = self.resolve_item_id(label, "refund")
                entry = {
                    "item_id": item_id,
                    "amount": goodwill_amount,
                    "refund_method": self.item_assertions.get(item_id, {}).get("refund_method") or "original_payment",
                    "kind": "goodwill",
                }
                self.pending_refund_entry = dict(entry)
                return entry

        if self.refund_queue:
            entry = self.refund_queue.pop(0)
            self.pending_refund_entry = dict(entry)
            return entry

        if self._policy_amount("goodwill_credit") is not None:
            amount = self._policy_amount("goodwill_credit")
            item_id = self.resolve_item_id(label, "refund")
            entry = {
                "item_id": item_id,
                "amount": amount,
                "refund_method": self.item_assertions.get(item_id, {}).get("refund_method") or "original_payment",
                "kind": "goodwill",
            }
            self.pending_refund_entry = dict(entry)
            return entry

        generic_amount = self._policy_amount("refund_amount")
        if generic_amount is not None:
            item_id = self.resolve_item_id(label, "refund")
            entry = {
                "item_id": item_id,
                "amount": generic_amount,
                "refund_method": self.item_assertions.get(item_id, {}).get("refund_method") or "original_payment",
                "kind": "refund",
            }
            self.pending_refund_entry = dict(entry)
            return entry
        return None

    def _match_item_label(self, label: str) -> str | None:
        lowered = label.lower().replace("_", " ")
        normalized_label = re.sub(r"[^a-z0-9]+", " ", lowered).strip()
        exact_candidates: list[str] = []
        fuzzy_candidates: list[str] = []
        for item_id, item in self.items.items():
            if item_id in self.used_item_ids:
                continue
            product = self.products.get(item.product_id)
            if product is None:
                continue
            name = product.name.lower()
            subcategory = product.subcategory.lower()
            normalized_name = re.sub(r"[^a-z0-9]+", " ", name).strip()
            normalized_subcategory = re.sub(r"[^a-z0-9]+", " ", subcategory).strip()
            normalized_category = re.sub(r"[^a-z0-9]+", " ", product.category.lower()).strip()
            if lowered in {item_id.lower(), product.product_id.lower(), subcategory}:
                exact_candidates.append(item_id)
                continue
            if normalized_label and normalized_label in {
                item_id.lower(),
                product.product_id.lower(),
                normalized_subcategory,
                normalized_name,
            }:
                exact_candidates.append(item_id)
                continue
            if lowered and (lowered in name or lowered in subcategory or lowered in product.category.lower()):
                fuzzy_candidates.append(item_id)
                continue
            if normalized_label and (
                normalized_label in normalized_name
                or normalized_label in normalized_subcategory
                or normalized_label in normalized_category
            ):
                fuzzy_candidates.append(item_id)
        if exact_candidates:
            return exact_candidates[0]
        if fuzzy_candidates:
            return fuzzy_candidates[0]
        return None

    def _policy_amount(self, *keys: str) -> int | None:
        for key in keys:
            value = self.policy_results.get(key)
            if isinstance(value, int):
                return value
        return None

    def _extract_amount_from_policy_text(self, keyword: str) -> int | None:
        phases = self.policy_results.get("phases", [])
        if not isinstance(phases, list):
            return None
        keyword_lower = keyword.lower()
        for phase in phases:
            if not isinstance(phase, str) or keyword_lower not in phase.lower():
                continue
            match = re.search(r"\$(\d+)", phase)
            if match:
                return int(match.group(1))
        return None


def _parse_replay_step(raw_step: Any) -> tuple[str, str | None, bool | None] | None:
    if isinstance(raw_step, dict):
        name = raw_step.get("name")
        if not isinstance(name, str) or not name:
            return None
        label = raw_step.get("label") if isinstance(raw_step.get("label"), str) else None
        confirm = raw_step.get("confirm") if isinstance(raw_step.get("confirm"), bool) else None
        return name, label, confirm
    return _parse_replay_step_string(raw_step)


def _build_replay_step(
    parsed: tuple[str, str | None, bool | None],
    context: _ReplayBridgeContext,
    task_type: str,
) -> dict[str, Any] | list[dict[str, Any]] | None:
    name, label, confirm = parsed
    if name == "get_order":
        order_hint = label if label and label.startswith("ORD-") else None
        return {"name": "get_order", "arguments": {"order_id": context.resolve_order_id(order_hint)}}
    if name == "get_customer":
        return {"name": "get_customer", "arguments": {"customer_id": context.resolve_customer_id()}}
    if name == "get_product":
        product_id = context.resolve_product_id(label)
        return {"name": "get_product", "arguments": {"product_id": product_id}}
    if name == "get_warranty_status":
        item_id = context.resolve_item_id(label, "warranty")
        return {"name": "get_warranty_status", "arguments": {"item_id": item_id}}
    if name == "get_policies":
        if not label:
            return None
        return {"name": "get_policies", "arguments": {"topic": label}}
    if name == "process_return":
        item_id = context.resolve_item_id(label, "return")
        if context.pending_return_item_id == item_id and context.pending_return_reason is not None and not label:
            reason = context.pending_return_reason
        else:
            reason = context.resolve_return_reason(item_id, label)
        context.pending_return_item_id = item_id
        context.pending_return_reason = reason
        if confirm:
            context.seen_returns.append(item_id)
            context.used_item_ids.add(item_id)
            context.pending_return_item_id = None
            context.pending_return_reason = None
        return {"name": "process_return", "arguments": {"item_id": item_id, "reason": reason, "confirm": bool(confirm)}}
    if name == "process_refund":
        refund = context.pending_refund_entry if context.pending_refund_entry is not None else context.resolve_refund_entry(label, task_type)
        if refund is None:
            return None
        if confirm:
            context.seen_refunds.append((refund["item_id"], refund["amount"]))
            context.pending_refund_entry = None
        return {
            "name": "process_refund",
            "arguments": {
                "item_id": refund["item_id"],
                "amount": refund["amount"],
                "refund_method": refund["refund_method"],
                "confirm": bool(confirm),
            },
        }
    if name == "cancel_order":
        arguments: dict[str, Any] = {"order_id": context.resolve_order_id(), "confirm": bool(confirm)}
        label_lower = (label or "").lower()
        if "item_ids" in label_lower and context.cancel_item_ids:
            context.pending_cancel_item_ids = list(context.cancel_item_ids)
        if context.pending_cancel_item_ids:
            arguments["item_ids"] = list(context.pending_cancel_item_ids)
        if confirm:
            context.pending_cancel_item_ids = None
        return {"name": "cancel_order", "arguments": arguments}
    if name == "process_exchange":
        item_id = context.resolve_item_id(label, "exchange")
        context.pending_exchange_item_id = item_id
        if confirm:
            context.pending_exchange_item_id = None
        return {
            "name": "process_exchange",
            "arguments": {
                "item_id": item_id,
                "new_product_id": context.resolve_product_id(label),
                "confirm": bool(confirm),
            },
        }
    if name == "process_warranty_claim":
        item_id = context.resolve_item_id(label, "warranty")
        context.pending_warranty_item_id = item_id
        if confirm:
            context.pending_warranty_item_id = None
        return {
            "name": "process_warranty_claim",
            "arguments": {
                "warranty_id": context.resolve_warranty_id(),
                "item_id": item_id,
                "issue_description": "Warranty issue",
                "confirm": bool(confirm),
            },
        }
    return None


# ---------------------------------------------------------------------------
# Filler data for environment realism
# ---------------------------------------------------------------------------


def build_task_environment(
    products: list[Product],
    orders: list[Order],
    items: list[OrderItem],
    warranties: list[Warranty],
    _task_data: dict[str, Any],
) -> CSEnvironmentData:
    """Build an isolated per-task environment snapshot from one scenario result."""
    customers = [
        Customer(
            customer_id=cid,
            name=attrs["name"],
            email=attrs["email"],
            membership_tier=attrs["membership_tier"],
            account_created=attrs["account_created"],
            total_orders=attrs["total_orders"],
            preferred_refund_method=attrs["preferred_refund_method"],
            store_credit_balance=attrs["store_credit_balance"],
            has_prime_shipping=attrs["has_prime_shipping"],
        )
        for cid, attrs in CUSTOMER_ATTRIBUTES.items()
    ]
    return CSEnvironmentData(
        products=list(products),
        orders=list(orders),
        order_items=list(items),
        customers=customers,
        warranties=list(warranties),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------




def _build_expected_outcome_from_state_requirements(task_data: dict[str, Any]) -> str | None:
    requirements = task_data.get("state_requirements")
    if not isinstance(requirements, list) or not requirements:
        return None

    item_fields: dict[str, dict[str, Any]] = {}
    order_fields: dict[str, dict[str, Any]] = {}
    for requirement in requirements:
        if not isinstance(requirement, dict):
            continue
        entity_type = requirement.get("entity_type")
        record_key = requirement.get("record_key")
        field = requirement.get("field")
        if not isinstance(record_key, str) or not isinstance(field, str):
            continue
        if entity_type == "order_items":
            item_fields.setdefault(record_key, {})[field] = requirement.get("expected_value")
        elif entity_type == "orders":
            order_fields.setdefault(record_key, {})[field] = requirement.get("expected_value")

    parts: list[str] = []
    task_type = task_data.get("task_type")

    if task_type == "price_match_refund":
        refund_entries = [
            fields
            for _item_id, fields in sorted(item_fields.items())
            if isinstance(fields.get("refund_amount"), int)
        ]
        if refund_entries:
            refund = refund_entries[0]
            amount = refund.get("refund_amount")
            method = refund.get("refund_method")
            if isinstance(amount, int) and isinstance(method, str):
                parts.append(f"Price-match refund of ${amount} to {method.replace('_', ' ')} recorded.")
            elif isinstance(amount, int):
                parts.append(f"Price-match refund of ${amount} recorded.")
            else:
                parts.append("Price-match refund recorded.")
            parts.append("Order remains active; no cancellation or return is performed.")
            parts.append("No fees are charged.")

    if task_type in {"return_item", "compound", "shipping_claim", "edge_case"}:
        returned_items = [
            (item_id, fields)
            for item_id, fields in sorted(item_fields.items())
            if fields.get("item_status") == "returned"
        ]
        if returned_items:
            single = len(returned_items) == 1
            for item_id, fields in returned_items:
                reason = fields.get("return_reason")
                refund_amount = fields.get("refund_amount")
                refund_method = fields.get("refund_method")
                restocking_fee = fields.get("restocking_fee")
                goodwill = fields.get("goodwill_credit")
                goodwill_method = fields.get("goodwill_credit_method")

                subject = "Item" if single else f"Item {item_id}"
                sentence = f"{subject} returned"
                if isinstance(reason, str):
                    sentence += f" ({reason.replace('_', ' ')})"
                if isinstance(refund_amount, int) and isinstance(refund_method, str):
                    sentence += f" with refund of ${refund_amount} to {refund_method.replace('_', ' ')}"
                sentence += "."
                parts.append(sentence)

                if isinstance(restocking_fee, int) and restocking_fee > 0:
                    parts.append(f"Restocking fee deduction: ${restocking_fee}.")
                if isinstance(goodwill, int) and goodwill > 0:
                    base_refund = refund_amount if isinstance(refund_amount, int) else 0
                    additive_goodwill = goodwill - base_refund if goodwill > base_refund and base_refund > 0 else goodwill
                    if isinstance(goodwill_method, str):
                        method = goodwill_method.replace('_', ' ')
                        parts.append(f"Additional goodwill credit of ${additive_goodwill} issued to {method}.")
                    else:
                        parts.append(f"Additional goodwill credit of ${additive_goodwill} issued.")

        standalone_refunds = [
            (item_id, fields)
            for item_id, fields in sorted(item_fields.items())
            if fields.get("item_status") != "returned"
            and isinstance(fields.get("refund_amount"), int)
            and isinstance(fields.get("refund_method"), str)
        ]
        for item_id, fields in standalone_refunds:
            subject = "Item" if len(standalone_refunds) == 1 and not returned_items else f"Item {item_id}"
            parts.append(
                f"{subject} refund of ${fields['refund_amount']} to {fields['refund_method'].replace('_', ' ')} recorded."
            )

    if task_type in {"cancel_order", "compound"}:
        cancelled_items = [
            (item_id, fields)
            for item_id, fields in sorted(item_fields.items())
            if fields.get("item_status") == "cancelled"
        ]
        if cancelled_items:
            total = sum(fields.get("refund_amount", 0) for _item_id, fields in cancelled_items if isinstance(fields.get("refund_amount"), int))
            if task_type == "cancel_order" and total:
                parts.append(f"Cancellation completed. Total recorded refund: ${total}.")
            else:
                for item_id, fields in cancelled_items:
                    refund_amount = fields.get("refund_amount")
                    sentence = f"Item {item_id} cancelled"
                    if isinstance(refund_amount, int):
                        sentence += f" with refund of ${refund_amount}"
                    sentence += "."
                    parts.append(sentence)

    if not parts:
        return None

    seen: set[str] = set()
    deduped = [part for part in parts if not (part in seen or seen.add(part))]
    return " ".join(deduped)


def _normalize_requirement_text(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text.strip())
    normalized = normalized.lstrip("- ")
    normalized = re.sub(r"\s+([,.;:])", r"\1", normalized)
    normalized = re.sub(r",([.!?])", r"\1", normalized)
    normalized = re.sub(r",$", "", normalized)
    return normalized.rstrip(".") + "."


def _requirement_evidence(text: str) -> str:
    lowered = text.lower()
    action_markers = (
        "process ",
        "issue ",
        "refund",
        "reship",
        "replacement",
        "return",
        "cancel",
        "exchange",
    )
    return "conversation_or_tool_calls" if any(marker in lowered for marker in action_markers) else "conversation"


def _append_requirement(requirements: list[dict[str, Any]], seen: set[tuple[str, str]], task_id: str, kind: str, text: str) -> None:
    normalized = _normalize_requirement_text(text)
    key = (kind, normalized)
    if key in seen:
        return
    seen.add(key)
    slug_tokens = re.findall(r"[a-z0-9]+", normalized.lower())[:6]
    slug = "_".join(slug_tokens) or f"req_{len(requirements) + 1}"
    requirements.append(
        {
            "id": f"{task_id.replace('-', '_')}_{slug}",
            "kind": kind,
            "requirement": normalized,
            "evidence": _requirement_evidence(normalized),
        }
    )


def _extract_requirements_from_text(task_id: str, text: str, requirements: list[dict[str, Any]], seen: set[tuple[str, str]]) -> None:
    if not isinstance(text, str) or not text.strip():
        return

    lowered_full = text.lower()

    if "two separate actions required:" in lowered_full:
        tail = text.split(":", 1)[1]
        for clause in re.split(r"\(\d+\)\s*", tail):
            clause = clause.strip(" .;")
            if not clause:
                continue
            for part in re.split(r"(?=Agent must not\b)", clause, flags=re.IGNORECASE):
                part = part.strip(" .;")
                if not part:
                    continue
                if re.match(r"agent must not\b", part, flags=re.IGNORECASE):
                    normalized = re.sub(r".*?(agent must not\b)", "Agent must not ", part, flags=re.IGNORECASE)
                    _append_requirement(requirements, seen, task_id, "must_not", normalized)
                    continue
                normalized_clause = part[0].lower() + part[1:] if part[:1].isupper() else part
                _append_requirement(requirements, seen, task_id, "must", f"Agent must {normalized_clause}")

    if re.search(r"agent must:\s*\(1\)", text, flags=re.IGNORECASE):
        tail = text.split(":", 1)[1]
        for clause in re.split(r"\(\d+\)\s*", tail):
            clause = clause.strip(" .;")
            if not clause:
                continue
            normalized_clause = clause[0].lower() + clause[1:] if clause[:1].isupper() else clause
            _append_requirement(requirements, seen, task_id, "must", f"Agent must {normalized_clause}")

    sentences = [segment.strip() for segment in re.split(r"(?<=[.!?])\s+", text.strip()) if segment.strip()]
    for sentence in sentences:
        lowered = sentence.lower()

        if lowered.startswith("no state change expected. agent must:"):
            tail = sentence.split(":", 1)[1]
            for clause in re.split(r";\s*", tail):
                clause = clause.strip()
                if not clause:
                    continue
                if clause.lower().startswith("and "):
                    clause = clause[4:]
                _append_requirement(requirements, seen, task_id, "must", f"Agent must {clause}")
            continue

        if re.search(r"agent must not\b", sentence, flags=re.IGNORECASE):
            normalized = re.sub(r".*?(agent must not\b)", "Agent must not ", sentence, flags=re.IGNORECASE)
            _append_requirement(requirements, seen, task_id, "must_not", normalized)
            continue

        if re.search(r"agent must\b", sentence, flags=re.IGNORECASE):
            normalized = re.sub(r".*?(agent must\b)", "Agent must ", sentence, flags=re.IGNORECASE)
            _append_requirement(requirements, seen, task_id, "must", normalized)
            continue

        if lowered.startswith("must "):
            _append_requirement(requirements, seen, task_id, "must", f"Agent must {sentence[5:]}")
            continue

        if re.search(r"agent should\b", sentence, flags=re.IGNORECASE):
            normalized = re.sub(r".*?(agent should\b)", "Agent must ", sentence, flags=re.IGNORECASE)
            _append_requirement(requirements, seen, task_id, "must", normalized)
            continue

        if lowered.startswith("exchange denied. reason:"):
            reason = sentence.split(":", 1)[1].strip()
            _append_requirement(
                requirements,
                seen,
                task_id,
                "must",
                f"Agent must deny the exchange request and explain the reason: {reason}",
            )
            continue

        if lowered.startswith("reason:"):
            reason = sentence.split(":", 1)[1].strip()
            _append_requirement(
                requirements,
                seen,
                task_id,
                "must",
                f"Agent must explain the reason: {reason}",
            )


def _translate_challenge_trap(trap: str) -> tuple[str, str] | None:
    lowered = trap.lower().strip()

    if lowered in {
        "denies (no seasonal)",
        "agent denies return (no seasonal)",
        "agent denies return (doesn't know seasonal extension)",
    }:
        return "must_not", "Agent must not deny the request for ignoring the seasonal extension."
    if lowered.startswith("misses silver disc $"):
        amount = trap.split("$", 1)[1]
        return "must", f"Agent must include the Silver restocking discount of ${amount}."
    if lowered.startswith("misses gold disc $"):
        amount = trap.split("$", 1)[1]
        return "must", f"Agent must include the Gold restocking discount of ${amount}."
    if lowered.startswith("misses gold $") and "disc" in lowered:
        amount = trap.split("$", 1)[1].split()[0]
        return "must", f"Agent must include the Gold restocking discount of ${amount}."
    if lowered == "misses gold restocking discounts":
        return "must", "Agent must include the Gold restocking discounts for both eligible returned items."
    if lowered.startswith("misses shipping $"):
        amount = trap.split("$", 1)[1]
        return "must", f"Agent must include the shipping adjustment of ${amount}."
    if lowered.startswith("misses repeat $"):
        amount = trap.split("$", 1)[1]
        return "must", f"Agent must include the repeat-return surcharge of ${amount}."
    if lowered.startswith("misses $") and "disc" in lowered:
        amount = trap.split("$", 1)[1].split()[0]
        return "must", f"Agent must include the stated discount of ${amount}."
    if lowered.startswith("misses $") and "clawback" in lowered:
        amount = trap.split("$", 1)[1].split()[0]
        return "must", f"Agent must include the clawback of ${amount}."
    return None


def _build_task_requirements(task_data: dict[str, Any], expected_outcome: str) -> list[dict[str, Any]]:
    existing = task_data.get("task_requirements")
    if isinstance(existing, list) and existing:
        return existing

    task_id = str(task_data.get("task_id", "task"))
    description = str(task_data.get("description", ""))
    desc_lower = description.lower()
    requirements: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    _extract_requirements_from_text(task_id, description, requirements, seen)
    _extract_requirements_from_text(task_id, expected_outcome, requirements, seen)

    for trap in task_data.get("_failure_traps", []):
        if not isinstance(trap, str):
            continue
        trap = trap.strip()
        translated = _translate_challenge_trap(trap)
        if translated is not None:
            kind, requirement = translated
            _append_requirement(requirements, seen, task_id, kind, requirement)
            continue
        lowered = trap.lower()
        if lowered.startswith("agent doesn't "):
            remainder = trap[len("Agent doesn't "):]
            _append_requirement(requirements, seen, task_id, "must", f"Agent must {remainder}")
        elif lowered.startswith("agent does not "):
            remainder = trap[len("Agent does not "):]
            _append_requirement(requirements, seen, task_id, "must", f"Agent must {remainder}")
        elif lowered.startswith("agent forgets one of "):
            _append_requirement(
                requirements,
                seen,
                task_id,
                "must",
                "Agent must include all required components of the resolution.",
            )
        elif lowered.startswith("agent forgets "):
            remainder = trap[len("Agent forgets "):]
            if remainder.lower().startswith("to "):
                phrasing = f"Agent must {remainder}"
            else:
                phrasing = f"Agent must include {remainder}"
            _append_requirement(requirements, seen, task_id, "must", phrasing)
        elif lowered.startswith("agent misses "):
            remainder = trap[len("Agent misses "):]
            _append_requirement(requirements, seen, task_id, "must", f"Agent must include {remainder}")
        elif lowered.startswith("misses "):
            remainder = trap[7:]
            _append_requirement(requirements, seen, task_id, "must", f"Agent must include {remainder}")
        elif lowered.startswith("agent denies "):
            remainder = trap[len("Agent denies "):]
            _append_requirement(requirements, seen, task_id, "must_not", f"Agent must not deny {remainder}")
        elif lowered.startswith("denies "):
            remainder = trap[7:]
            _append_requirement(requirements, seen, task_id, "must_not", f"Agent must not deny {remainder}")
        elif "instead of" in lowered:
            phrasing = trap if lowered.startswith("agent ") else f"Agent {trap[0].lower() + trap[1:]}"
            replacements = {
                "Agent applies ": "Agent must not apply ",
                "Agent adds ": "Agent must not add ",
                "Agent offers ": "Agent must not offer ",
                "Agent combines ": "Agent must not combine ",
                "Agent issues ": "Agent must not issue ",
                "Agent computes ": "Agent must not compute ",
            }
            for source, target in replacements.items():
                if phrasing.startswith(source):
                    phrasing = target + phrasing[len(source):]
                    break
            _append_requirement(requirements, seen, task_id, "must_not", phrasing)

    if "store credit only" in desc_lower:
        _append_requirement(requirements, seen, task_id, "must", "Agent must explain that the refund is store credit only.")
    if "gift return" in desc_lower:
        _append_requirement(requirements, seen, task_id, "must", "Agent must explain that a gift return refunds to store credit at the current product price.")
    if "same product variant" in desc_lower:
        _append_requirement(requirements, seen, task_id, "must", "Agent must explain that the same-variant exchange is free and has no restocking fee.")
    if "backordered" in desc_lower and "cancel only" in desc_lower:
        _append_requirement(requirements, seen, task_id, "must", "Agent must cancel only the backordered item and leave the other item active.")
    if "cancel 1 of" in desc_lower:
        _append_requirement(requirements, seen, task_id, "must", "Agent must cancel only the requested item and leave the other items active.")
    if "both tier extension" in desc_lower and "stack" in desc_lower:
        _append_requirement(requirements, seen, task_id, "must", "Agent must explain that the Gold and Prime extensions stack to a 45-day effective return window.")
    if "seasonal extension" in desc_lower or "seasonal extends to jan 31" in desc_lower or "within seasonal extension" in desc_lower:
        _append_requirement(requirements, seen, task_id, "must", "Agent must explain that the seasonal extension keeps this return eligible.")
    if "each independently processed" in desc_lower:
        _append_requirement(requirements, seen, task_id, "must", "Agent must process both returns independently rather than handling only one order.")
    if "two operations on same order" in desc_lower:
        _append_requirement(requirements, seen, task_id, "must", "Agent must handle both operations on the same order.")
    if "fragile-item goodwill credit" in desc_lower:
        _append_requirement(requirements, seen, task_id, "must", "Agent must include the $10 fragile goodwill credit in the final resolution.")
        _append_requirement(requirements, seen, task_id, "must_not", "Agent must not combine the goodwill credit into the item return refund.")
    if "two different processes required" in desc_lower:
        _append_requirement(requirements, seen, task_id, "must", "Agent must use the correct process for each item rather than the same process for both.")
    if "changes mind and wants a full return instead" in desc_lower:
        _append_requirement(requirements, seen, task_id, "must", "Agent must pivot from the original exchange request to the customer's final return request.")
    if "three actions:" in desc_lower:
        _append_requirement(requirements, seen, task_id, "must", "Agent must complete all three actions required by the scenario.")
    if "refund as store credit at current" in desc_lower:
        _append_requirement(requirements, seen, task_id, "must", "Agent must use the current product price for the gift return refund.")
        _append_requirement(requirements, seen, task_id, "must", "Agent must issue the gift return refund to store credit rather than the original payment method.")
    if "warranty claim on phone" in desc_lower and "return phone case" in desc_lower:
        _append_requirement(requirements, seen, task_id, "must", "Agent must handle both the warranty claim and the return in the same conversation.")
    if "gift return" in desc_lower and "exchange/apply credit" in desc_lower:
        _append_requirement(requirements, seen, task_id, "must", "Agent must apply the gift-return store credit toward the exchange rather than refunding to the original card.")
    if "gold, 7 days late, 3 issues" in desc_lower:
        _append_requirement(requirements, seen, task_id, "must", "Agent must include all three compensation components in the $59 resolution.")
        _append_requirement(requirements, seen, task_id, "must_not", "Agent must not apply the Gold multiplier to the goodwill or shipping refund components.")
    if "refurbished laptop with 90-day warranty" in desc_lower:
        _append_requirement(requirements, seen, task_id, "must", "Agent must explain that the refurbished item uses the 90-day warranty and is still covered.")

    expected_lower = expected_outcome.lower()
    if expected_lower.startswith("exchange denied"):
        _append_requirement(requirements, seen, task_id, "must", "Agent must deny the exchange request.")
    if "no state change expected" in expected_lower and not requirements:
        _append_requirement(requirements, seen, task_id, "must", "Agent must leave the order state unchanged.")

    return requirements


def _build_user_sim_context(task_data: dict[str, Any], known_info_list: list[str], scenario: dict[str, Any]) -> str:
    inline_context = task_data.get("user_sim_context")
    if isinstance(inline_context, str) and inline_context.strip():
        return inline_context.strip()

    task_slug = str(task_data.get("task_id", ""))
    if "-" in task_slug:
        task_slug = task_slug.split("-", 1)[1]
    authored_context = USER_SIM_CONTEXTS.get(task_slug)
    if not authored_context or not authored_context.strip():
        raise ValueError(f"{task_data['task_id']} is missing authored user_sim_context")
    return authored_context.strip()


def build_public_task_json(task_data: dict[str, Any]) -> dict[str, Any]:
    """Build the saved task JSON payload for generated customer-support tasks."""
    gt = task_data.get("ground_truth_trace", {})
    sim_raw = task_data.get("user_simulator", {})
    known_info_dict = sim_raw.get("_known_info", {})
    known_info_list = [f"{k}: {v}" for k, v in known_info_dict.items()] if isinstance(known_info_dict, dict) else []

    scenario = _canonical_scenario_template(task_data.get("scenario_template", {}))
    customer_id = scenario.get("customer_id", "")
    expected_outcome = _build_expected_outcome_from_state_requirements(task_data) or gt.get("expected_outcome", "")
    task_requirements = task_data.get("task_requirements") or _build_task_requirements(task_data, expected_outcome)
    task_slug = str(task_data.get("task_id", ""))
    if "-" in task_slug:
        task_slug = task_slug.split("-", 1)[1]
    task_summary = task_data.get("task_summary") or TASK_SUMMARIES.get(task_slug)
    if not isinstance(task_summary, str) or not task_summary.strip():
        raise ValueError(f"{task_data['task_id']} is missing authored task_summary")

    user_sim_context = _build_user_sim_context(task_data, known_info_list, scenario)

    output = {
        "task_id": task_data["task_id"],
        "task_summary": task_summary,
        "task_type": task_data["task_type"],
        "task_requirements": task_requirements,
        "user_id": customer_id,
        "now": scenario.get("now", "2026-06-12T10:00:00"),
        "opening_message": task_data.get("opening_message", ""),
        "user_simulator": {
            "personality": CUSTOMER_ATTRIBUTES.get(customer_id, {}).get("communication_style", "polite"),
            "user_sim_context": user_sim_context,
            "known_info": known_info_list,
            "unknown_info": sim_raw.get("_unknown_info", []),
            "task_rules": _extract_rules_from_prompt(sim_raw.get("prompt", "")),
        },
    }
    if "task_env_path" in task_data:
        output["task_env_path"] = task_data["task_env_path"]
    output["task_requirements"] = task_requirements
    if "state_requirements" in task_data:
        output["state_requirements"] = task_data["state_requirements"]
    if "replay_trace_hash" in task_data:
        output["replay_trace_hash"] = task_data["replay_trace_hash"]
    return output


def _build_task_json(task_data: dict[str, Any]) -> dict[str, Any]:
    """Backward-compatible alias for older customer-support generation tests."""
    return build_public_task_json(task_data)


def save_task(task_data: dict[str, Any], tasks_dir: Path) -> None:
    """Save a task definition to JSON in TaskDefinition-compatible format."""
    tasks_dir.mkdir(parents=True, exist_ok=True)
    output = build_public_task_json(task_data)

    path = tasks_dir / f"{task_data['task_id']}.json"
    with open(path, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)


def _extract_rules_from_prompt(prompt: str) -> list[str]:
    """Extract numbered rules from a CS simulator prompt."""
    rules = []
    for line in prompt.split("\n"):
        line = line.strip()
        if line and line[0].isdigit() and ". " in line:
            rule = line.split(". ", 1)[1]
            rules.append(rule)
    return rules
