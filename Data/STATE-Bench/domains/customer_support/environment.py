"""Stateful customer support environment with tool handlers.

The CustomerSupportEnvironment holds the in-memory database and provides tool handler
methods as bound functions. Each evaluation run gets a fresh deep copy.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from domains.customer_support import policies
from domains.customer_support.schemas import (
    CSEnvironmentData,
    Customer,
    Order,
    OrderItem,
    Product,
    Warranty,
)
from state_bench.environment import BaseEnvironment


class CustomerSupportEnvironment(BaseEnvironment):
    """Stateful environment wrapping products, orders, items, customers, warranties and policy engine."""

    def __init__(self, env_data: CSEnvironmentData, now: str):
        super().__init__(env_data, now)
        self.products: dict[str, Product] = {p.product_id: p for p in env_data.products}
        self.orders: dict[str, Order] = {o.order_id: o for o in env_data.orders}
        self.order_items: dict[str, OrderItem] = {i.item_id: i for i in env_data.order_items}
        self.customers: dict[str, Customer] = {c.customer_id: c for c in env_data.customers}
        self.warranties: dict[str, Warranty] = {w.warranty_id: w for w in env_data.warranties}

        # Policy gate: track which policy topics have been looked up
        self._policies_checked: set[str] = set()

        # Two-step enforcement: track previewed operations per tool
        self._previewed: dict[str, set[str]] = {
            "return": set(),
            "refund": set(),
            "cancel": set(),
            "exchange": set(),
            "warranty_claim": set(),
        }
        self._previewed_refunds: dict[str, set[tuple[str, int | float]]] = {}

    def get_orders_snapshot(self) -> dict[str, dict[str, Any]]:
        """Return a snapshot for assertion checking.

        Keys include order_ids, item_ids, AND warranty_ids so that
        DBAssertion.booking_id (used as generic entity_id) can reference
        any entity type.
        """
        snapshot: dict[str, dict[str, Any]] = {}
        for oid, order in self.orders.items():
            snapshot[oid] = order.to_dict()
        for iid, item in self.order_items.items():
            snapshot[iid] = item.to_dict()
        for wid, warranty in self.warranties.items():
            snapshot[wid] = warranty.to_dict()
        return snapshot

    def get_full_snapshot(self) -> dict[str, dict[str, dict[str, Any]]]:
        """Return all mutable entities indexed by type and ID for StateDiff."""
        return {
            "orders": {oid: o.to_dict() for oid, o in self.orders.items()},
            "order_items": {iid: i.to_dict() for iid, i in self.order_items.items()},
            "customers": {cid: c.to_dict() for cid, c in self.customers.items()},
            "warranties": {wid: w.to_dict() for wid, w in self.warranties.items()},
        }

    def _get_items_for_order(self, order_id: str) -> list[OrderItem]:
        """Get all OrderItems belonging to an order."""
        return [item for item in self.order_items.values() if item.order_id == order_id]

    def _get_warranty_for_item(self, item_id: str) -> Warranty | None:
        """Get warranty for an item, if any."""
        for w in self.warranties.values():
            if w.item_id == item_id:
                return w
        return None

    # -------------------------------------------------------------------
    # READ tools
    # -------------------------------------------------------------------

    def get_order(self, params: dict[str, Any]) -> dict[str, Any]:
        """Retrieve full order details including all items and product info."""
        order_id = params.get("order_id", "")
        order = self.orders.get(order_id)
        if not order:
            return {"error": f"Order {order_id} not found."}

        items = self._get_items_for_order(order_id)
        items_data = []
        for item in items:
            product = self.products.get(item.product_id)
            item_dict = item.to_dict()
            if product:
                item_dict["product"] = {
                    "product_id": product.product_id,
                    "name": product.name,
                    "category": product.category,
                    "price": product.price,
                    "current_price": product.current_price,
                    "return_window_days": product.return_window_days,
                    "warranty_months": product.warranty_months,
                    "in_stock": product.in_stock,
                }
            items_data.append(item_dict)

        result = order.to_dict()
        result["items"] = items_data
        return result

    def get_customer(self, params: dict[str, Any]) -> dict[str, Any]:
        """Retrieve customer profile."""
        customer_id = params.get("customer_id", "")
        customer = self.customers.get(customer_id)
        if not customer:
            return {"error": f"Customer {customer_id} not found."}
        result = customer.to_dict()
        # Add membership benefit summary
        tier = customer.membership_tier
        result["benefits"] = {
            "return_window_extension": f"+{policies.TIER_RETURN_EXTENSION.get(tier, 0)} days",
            "compensation_multiplier": f"{policies.TIER_COMPENSATION_MULTIPLIER.get(tier, 1.0)}x",
            "restocking_fee_waiver": tier == "platinum",
            "prime_shipping": customer.has_prime_shipping,
        }
        return result

    def get_product(self, params: dict[str, Any]) -> dict[str, Any]:
        """Retrieve product details. Supports lookup by product_id or product name."""
        product_id = params.get("product_id", "")
        product = self.products.get(product_id)
        if not product:
            # Try name-based lookup (case-insensitive)
            pid_lower = product_id.lower().strip()
            for p in self.products.values():
                if p.name.lower() == pid_lower:
                    return p.to_dict()
            # Try partial name match
            for p in self.products.values():
                if pid_lower in p.name.lower() or p.name.lower() in pid_lower:
                    return p.to_dict()
            return {"error": f"Product {product_id} not found."}
        return product.to_dict()

    def get_policies(self, params: dict[str, Any]) -> dict[str, Any]:
        """Look up company policies for a given topic. Must be called before any write tool."""
        topic = params.get("topic", "")
        self._policies_checked.add(topic)

        if topic == "return":
            return {
                "topic": "return",
                "rules": {
                    "electronics": "15-day return window",
                    "clothing": "30-day return window",
                    "kitchen": "30-day return window",
                    "books": "14-day return window",
                    "accessories": "30-day return window",
                    "membership_extension": "Gold/Platinum members get +15 days",
                    "prime_extension": "Prime shipping members get +15 additional days",
                    "defective_items": "No window restriction for defective, wrong item, or damaged in transit",
                    "already_returned": "Items already returned/exchanged/cancelled are ineligible",
                    "store_credit_window": "Up to 15 days past return window: store credit only",
                    "seasonal_extension": "Nov/Dec holiday orders qualify for an extended return window through Jan 31 of the following year — see get_policies(topic='seasonal') for full rules",
                },
            }
        elif topic == "refund":
            return {
                "topic": "refund",
                "rules": {
                    "full_refund": "Full refund for defective, wrong item, or damaged in transit",
                    "restocking_fee": "15% restocking fee for opened electronics (changed_mind)",
                    "platinum_waiver": "Platinum members: restocking fee waived",
                    "promo_redistribution": "If promo/coupon was used: discount allocated proportionally by item price. Refund = item_price - (discount * item_price / subtotal)",
                    "gift_return": "Returns on gift-flagged orders: store credit at current product price",
                    "outside_window": "Outside return window (within store credit window): store credit only",
                    "shipping_refund": "Shipping refunded for defective/wrong item, NOT for buyer's remorse",
                    "price_match": "If product price dropped within 7 days of delivery, refund the difference via process_refund",
                    "goodwill_credit": "Goodwill credits (e.g., fragile item damaged) are issued via process_refund with the credit amount",
                },
            }
        elif topic == "cancellation":
            return {
                "topic": "cancellation",
                "rules": {
                    "pre_shipment": "Free cancellation before shipment (pending/processing status)",
                    "in_transit": "$10 intercept fee per item for in-transit orders",
                    "delivered": "Cannot cancel delivered orders — must use return process",
                    "partial": "Partial cancellation allowed if items not yet delivered",
                    "split_payment": "Refund distributed proportionally to original payment methods",
                    "already_cancelled": "Already cancelled orders cannot be cancelled again",
                },
            }
        elif topic == "exchange":
            return {
                "topic": "exchange",
                "rules": {
                    "same_variant": "Same product, different size/color: free exchange, no restocking fee",
                    "more_expensive": "Exchange for more expensive item: customer pays price difference",
                    "cheaper": "Exchange for cheaper item: difference refunded as store credit (not original payment)",
                    "out_of_stock": "If requested item is out of stock: offer store credit or waitlist",
                    "return_window": "Must be within return window (same rules as returns)",
                    "no_price_protection": "No price protection on exchanges (item price at time of purchase applies)",
                },
            }
        elif topic == "warranty":
            return {
                "topic": "warranty",
                "rules": {
                    "active": "Active warranty: eligible for claim",
                    "expired_recent": "Expired <30 days: 50% off repair",
                    "expired_old": "Expired >30 days: full-price repair or 25% off replacement",
                    "claim_limit": "Max claims reached: paid repair only (40% of item price)",
                    "repair_vs_replace": "Items <$100: replacement. Items >=$100: repair first",
                    "recurring_defect": "2+ prior claims for same issue: automatic replacement",
                    "manufacturer": "Manufacturer warranty covers first 12 months",
                    "extended": "Extended warranty covers after manufacturer period",
                },
            }
        elif topic == "shipping":
            return {
                "topic": "shipping",
                "rules": {
                    "not_received_under_500": "Delivered but not received (<$500): reship or refund",
                    "not_received_over_500": "Delivered but not received (>=$500): mandatory investigation (3-5 business days)",
                    "signature": "Delivery with signature on file: claim denied",
                    "lost_under_500": "Lost in transit (<$500): immediate reship or refund",
                    "lost_over_500": "Lost in transit (>=$500): carrier claim required first",
                    "damaged": "Damaged in transit: full refund or replacement",
                    "fragile_bonus": "Fragile items damaged: +$10 goodwill credit",
                    "stuck_7_days": "No tracking update 7+ days: treat as lost",
                },
            }
        elif topic == "compensation":
            return {
                "topic": "compensation",
                "rules": {
                    "late_1_2_days": "$5 credit",
                    "late_3_5_days": "$15 credit",
                    "late_6_plus_days": "Full shipping refund + $15 credit",
                    "repeated_issues": "3+ PRIOR issues in 6 months (not counting current incident): additional $25 goodwill credit",
                    "fragile_damaged_item": "Fragile items damaged in transit qualify for a separate $10 goodwill credit; check shipping policy details and issue it via process_refund in addition to the return refund.",
                    "gold_multiplier": "Gold members: 1.5x multiplier — applies ONLY to the base late-delivery credit, NOT to shipping refund or goodwill. Result is rounded down to the nearest dollar (e.g. int(15*1.5) = 22).",
                    "platinum_multiplier": "Platinum members: 2x multiplier — applies ONLY to the base late-delivery credit, NOT to shipping refund or goodwill. Result is rounded down.",
                    "max_cap": "Maximum compensation: 50% of order total (rounded down)",
                    "loyalty_bonus": "Platinum members with 50+ orders: one-time $50 loyalty bonus on next compensation claim",
                    "calculation_order": "1) Compute base credit by days-late tier. 2) Apply tier multiplier to base credit only. 3) Add shipping refund (if 6+ days late). 4) Add goodwill (if 3+ prior issues). 5) Apply 50%-of-order cap on the sum.",
                },
            }
        elif topic == "loyalty":
            return {
                "topic": "loyalty",
                "rules": {
                    "eligibility": "Platinum tier + 50 or more total orders",
                    "bonus": "$50 one-time loyalty bonus",
                    "when_applied": "Applied as additional credit on next compensation or refund claim",
                    "one_time": "Can only be used once — check with customer if already redeemed",
                },
            }
        elif topic == "bulk_discount":
            return {
                "topic": "bulk_discount",
                "rules": {
                    "threshold": "Bulk discounts apply to orders with 3+ items",
                    "clawback": "If returning items drops remaining count below 3, clawback $5 per remaining item",
                    "deduction": "Clawback amount is deducted from the return refund",
                    "no_discount": "If order had no discount code, no clawback applies",
                },
            }
        elif topic == "seasonal":
            return {
                "topic": "seasonal",
                "rules": {
                    "holiday_orders": "Orders placed in November or December qualify for seasonal extension",
                    "extended_window": "Return window extends to January 31 of the following year",
                    "stacking": "Seasonal extension applies if it gives more time than tier/prime extensions",
                    "after_deadline": "After January 31, normal return window rules apply",
                },
            }
        elif topic == "free_shipping":
            return {
                "topic": "free_shipping",
                "rules": {
                    "threshold": "Orders with subtotal >= $100 qualify for free shipping",
                    "clawback": "If a return drops remaining subtotal below $100, original shipping cost is deducted from the return refund",
                    "deduction": "Shipping clawback is deducted from the return refund, not charged separately",
                    "no_clawback": "If order originally paid for shipping (subtotal < $100), no clawback applies",
                },
            }
        elif topic == "repeat_return":
            return {
                "topic": "repeat_return",
                "rules": {
                    "same_category": "If returning 2+ items from the same product category in one order, $5 surcharge per additional return",
                    "first_free": "First return in each category has no surcharge",
                    "deduction": "Surcharge is deducted from the return refund",
                    "different_categories": "Returns from different categories do not trigger the surcharge",
                },
            }
        elif topic == "restocking_discount":
            return {
                "topic": "restocking_discount",
                "rules": {
                    "gold": "Gold members: 50% off the 15% restocking fee on electronics",
                    "silver": "Silver members: 25% off the 15% restocking fee on electronics",
                    "standard": "Standard members: no discount on restocking fee",
                    "platinum": "Platinum members: restocking fee is already fully waived",
                    "how_applied": "Discount is automatically folded into the process_return refund amount (no separate process_refund call needed). The process_return result also reports the discount amount under the 'restocking_discount' field for transparency.",
                },
            }
        elif topic == "return_shipping":
            return {
                "topic": "return_shipping",
                "rules": {
                    "low_value": "Orders with subtotal < $50: customer pays $8 return shipping fee",
                    "free_threshold": "Orders >= $50: free return label provided",
                    "defective_free": "Defective, wrong item, or damaged: always free return shipping",
                    "fee_deduction": "Return shipping fee is deducted from the return refund",
                },
            }
        else:
            return {
                "error": f"Unknown policy topic: {topic}. Valid: return, refund, cancellation, exchange, warranty, shipping, compensation, loyalty, bulk_discount, seasonal, free_shipping, repeat_return, restocking_discount, return_shipping"
            }

    def get_warranty_status(self, params: dict[str, Any]) -> dict[str, Any]:
        """Check warranty status for an item."""
        item_id = params.get("item_id", "")
        item = self.order_items.get(item_id)
        if not item:
            return {"error": f"Item {item_id} not found."}

        warranty = self._get_warranty_for_item(item_id)
        if not warranty:
            return {"item_id": item_id, "has_warranty": False, "message": "No warranty found for this item."}

        now_dt = datetime.fromisoformat(self.now)
        end_dt = datetime.fromisoformat(warranty.end_date)
        is_active = now_dt <= end_dt

        result = warranty.to_dict()
        result["is_active"] = is_active
        result["days_until_expiry"] = (end_dt - now_dt).days if is_active else 0
        result["days_past_expiry"] = (now_dt - end_dt).days if not is_active else 0
        result["has_warranty"] = True
        return result

    # -------------------------------------------------------------------
    # WRITE tools (all two-step: preview → confirm)
    # -------------------------------------------------------------------

    def process_return(self, params: dict[str, Any]) -> dict[str, Any]:
        """Process a return for an order item. Two-step: preview then confirm."""
        item_id = params.get("item_id", "")
        reason = params.get("reason", "changed_mind")
        confirm = self.parse_bool(params.get("confirm"))

        # Policy gate
        if "return" not in self._policies_checked:
            return {"error": "Policy review required. Call get_policies(topic='return') first."}

        item = self.order_items.get(item_id)
        if not item:
            return {"error": f"Item {item_id} not found."}

        order = self.orders.get(item.order_id)
        if not order:
            return {"error": f"Order {item.order_id} not found."}

        product = self.products.get(item.product_id)
        if not product:
            return {"error": f"Product {item.product_id} not found."}

        customer = self.customers.get(order.customer_id)
        if not customer:
            return {"error": f"Customer {order.customer_id} not found."}

        # Check eligibility
        eligibility = policies.check_return_eligibility(
            category=product.category,
            delivery_date=order.delivery_date,
            now=self.now,
            item_status=item.item_status,
            return_reason=reason,
            membership_tier=customer.membership_tier,
            has_prime_shipping=customer.has_prime_shipping,
            order_date=order.order_date,
        )

        if not eligibility["eligible"]:
            return {"status": "rejected", "item_id": item_id, "reason": eligibility["reason"]}

        # Calculate refund
        store_credit_only = eligibility.get("store_credit_only", False)
        refund = policies.calculate_refund(
            item_price=item.unit_price,
            return_reason=reason,
            category=product.category,
            discount_code=order.discount_code,
            discount_amount=order.discount_amount,
            order_subtotal=order.subtotal,
            membership_tier=customer.membership_tier,
            is_gift_return=order.is_gift and reason == "changed_mind",
            current_product_price=product.current_price,
            store_credit_only=store_credit_only,
        )

        # Clawbacks: bulk applies universally (policy text: "deducted from return refund"
        # with no reason carveout). Shipping clawback skipped on product-fault returns
        # since those already get shipping refunded — clawing back simultaneously is
        # contradictory.
        is_product_fault = reason in ("defective", "damaged_in_transit", "wrong_item", "missing")

        # Free-shipping clawback: if this return drops remaining subtotal below the
        # free-shipping threshold, deduct the would-be standard shipping cost from
        # the refund. "Remaining" counts items not yet returned/cancelled/exchanged
        # EXCLUDING the current item.
        original_free_shipping = order.subtotal >= policies.FREE_SHIPPING_THRESHOLD
        all_items = self._get_items_for_order(order.order_id)
        remaining_items_after = [
            i for i in all_items
            if i.item_id != item_id and i.item_status not in ("returned", "cancelled", "exchanged")
        ]
        remaining_subtotal_after = sum(i.unit_price for i in remaining_items_after)
        clawback_amount = 0
        if not is_product_fault and original_free_shipping and remaining_subtotal_after < policies.FREE_SHIPPING_THRESHOLD:
            clawback_amount = policies.STANDARD_SHIPPING_COST

        # Bulk-discount clawback: if this return drops remaining item count
        # below the bulk threshold (3), claw back $5 per remaining item.
        bulk = policies.calculate_bulk_clawback(
            original_item_count=len(all_items),
            items_being_returned=1,
            remaining_item_count=len(remaining_items_after),
            discount_code=order.discount_code,
            discount_amount=order.discount_amount,
        )
        bulk_clawback_amount = bulk.get("clawback_amount", 0) if bulk.get("applies") else 0

        # Repeat-category surcharge: $5 on 2nd+ return in same category within this order.
        already_returned_categories: list[str] = []
        for i in all_items:
            if i.item_id == item_id:
                continue
            if i.item_status == "returned":
                p = self.products.get(i.product_id)
                if p:
                    already_returned_categories.append(p.category)
        repeat = policies.calculate_repeat_return_surcharge(
            return_category=product.category,
            already_returned_categories=already_returned_categories,
        )
        repeat_surcharge_amount = repeat.get("surcharge", 0) if repeat.get("applies") else 0

        # Paid return shipping: low-value orders (<$50) pay $8 return shipping
        # on customer-fault returns. Product-fault returns always get free shipping.
        paid_ship = policies.calculate_paid_return_shipping(
            order_subtotal=order.subtotal,
            return_reason=reason,
        )
        paid_return_shipping_fee = paid_ship.get("fee", 0) if paid_ship.get("applies") else 0

        # Tier-based restocking-fee discount (Gold 50%, Silver 25%). Added back
        # to the refund so agents don't need a separate process_refund call.
        restocking_discount = policies.calculate_restocking_discount(
            restocking_fee=refund["restocking_fee"],
            membership_tier=customer.membership_tier,
        )
        restocking_discount_amount = restocking_discount.get("discount", 0) if restocking_discount.get("applies") else 0

        refund_after_clawback = max(
            0,
            refund["refund_amount"] - clawback_amount - bulk_clawback_amount - repeat_surcharge_amount - paid_return_shipping_fee + restocking_discount_amount,
        )

        if not confirm:
            self._previewed["return"].add(item_id)
            return {
                "status": "preview",
                "item_id": item_id,
                "return_eligible": True,
                "reason": reason,
                "refund_amount": refund_after_clawback,
                "refund_method": refund["refund_method"],
                "restocking_fee": refund["restocking_fee"],
                "discount_adjustment": refund["discount_adjustment"],
                "free_return_shipping": eligibility.get("free_return_shipping", False),
                "shipping_refund": refund["shipping_refund"],
                "shipping_clawback": clawback_amount,
                "bulk_clawback": bulk_clawback_amount,
                "repeat_surcharge": repeat_surcharge_amount,
                "paid_return_shipping_fee": paid_return_shipping_fee,
                "restocking_discount": restocking_discount_amount,
            }

        # Enforce two-step
        if item_id not in self._previewed["return"]:
            return {"error": "Must preview return before confirming. Call without confirm first."}

        # Execute return
        item.item_status = "returned"
        item.return_reason = reason
        item.refund_amount = refund_after_clawback
        item.refund_method = refund["refund_method"]
        item.restocking_fee = refund["restocking_fee"]
        item.return_label_issued = eligibility.get("free_return_shipping", False)
        self._previewed["return"].discard(item_id)

        # Update order status. Mixed return+cancellation outcomes should stay
        # partial rather than collapsing to fully_returned.
        order_items = self._get_items_for_order(order.order_id)
        all_terminal = all(i.item_status in ("returned", "cancelled", "exchanged") for i in order_items)
        if all_terminal:
            statuses = {i.item_status for i in order_items}
            if statuses == {"cancelled"}:
                order.status = "cancelled"
            elif statuses <= {"returned", "exchanged"}:
                order.status = "fully_returned"
            else:
                order.status = "partially_cancelled"
        else:
            any_terminal = any(i.item_status in ("returned", "cancelled", "exchanged") for i in order_items)
            any_cancelled = any(i.item_status == "cancelled" for i in order_items)
            if any_terminal:
                order.status = "partially_cancelled" if any_cancelled else "partially_returned"

        return {
            "status": "returned",
            "item_id": item_id,
            "refund_amount": refund_after_clawback,
            "refund_method": refund["refund_method"],
            "restocking_fee": refund["restocking_fee"],
            "return_label_issued": item.return_label_issued,
            "shipping_clawback": clawback_amount,
            "bulk_clawback": bulk_clawback_amount,
            "repeat_surcharge": repeat_surcharge_amount,
            "paid_return_shipping_fee": paid_return_shipping_fee,
            "restocking_discount": restocking_discount_amount,
        }

    def process_refund(self, params: dict[str, Any]) -> dict[str, Any]:
        """Process a refund for an order item. Two-step: preview then confirm."""
        item_id = params.get("item_id", "")
        refund_method = params.get("refund_method", "original_payment")
        amount = params.get("amount", 0)
        confirm = self.parse_bool(params.get("confirm"))

        # Policy gate
        if "refund" not in self._policies_checked:
            return {"error": "Policy review required. Call get_policies(topic='refund') first."}

        item = self.order_items.get(item_id)
        if not item:
            return {"error": f"Item {item_id} not found."}

        order = self.orders.get(item.order_id)
        if not order:
            return {"error": f"Order {item.order_id} not found."}

        preview_key = (refund_method, amount)
        if not confirm:
            self._previewed_refunds.setdefault(item_id, set()).add(preview_key)
            self._previewed["refund"].add(item_id)
            return {
                "status": "preview",
                "item_id": item_id,
                "refund_amount": amount,
                "refund_method": refund_method,
            }

        if preview_key not in self._previewed_refunds.get(item_id, set()):
            return {"error": "Must preview refund before confirming. Call without confirm first."}

        # If a return/cancel already created the base refund, allow the agent to
        # either reissue that same refund to a different method or top it up with
        # a same-method supplemental refund (for example, a separate shipping refund)
        # without misclassifying the extra amount as goodwill.
        if item.refund_amount is not None and amount == item.refund_amount:
            item.refund_method = refund_method
            effective_amount = item.refund_amount
            mode = "refund_method_update"
        elif item.refund_amount is not None and refund_method == item.refund_method:
            effective_amount = amount
            mode = "supplemental_refund"
        elif item.refund_amount is not None:
            item.goodwill_credit = (item.goodwill_credit or 0) + amount
            item.goodwill_credit_method = refund_method
            effective_amount = amount
            mode = "goodwill_credit"
        else:
            item.refund_amount = amount
            item.refund_method = refund_method
            effective_amount = amount
            mode = "refund"
        item_previews = self._previewed_refunds.get(item_id)
        if item_previews is not None:
            item_previews.discard(preview_key)
            if not item_previews:
                self._previewed_refunds.pop(item_id, None)
                self._previewed["refund"].discard(item_id)
        if order.payment_method == "split" and refund_method == "original_payment":
            split_refund = policies.calculate_split_refund(order.payment_details, effective_amount)
            return {
                "status": "refunded",
                "item_id": item_id,
                "mode": mode,
                "refund_amount": effective_amount,
                "refund_method": "split",
                "split_details": split_refund,
                "total_goodwill_credit": item.goodwill_credit,
            }

        return {
            "status": "refunded",
            "item_id": item_id,
            "mode": mode,
            "refund_amount": effective_amount,
            "refund_method": refund_method,
            "total_goodwill_credit": item.goodwill_credit,
        }

    def cancel_order(self, params: dict[str, Any]) -> dict[str, Any]:
        """Cancel an order or specific items. Two-step: preview then confirm."""
        order_id = params.get("order_id", "")
        item_ids = params.get("item_ids")
        confirm = self.parse_bool(params.get("confirm"))

        # Policy gate
        if "cancellation" not in self._policies_checked:
            return {"error": "Policy review required. Call get_policies(topic='cancellation') first."}

        order = self.orders.get(order_id)
        if not order:
            return {"error": f"Order {order_id} not found."}

        order_items = self._get_items_for_order(order_id)
        if not order_items:
            return {"error": f"No items found for order {order_id}."}

        # Determine which items to cancel
        if item_ids:
            target_items = [i for i in order_items if i.item_id in item_ids]
            if len(target_items) != len(item_ids):
                found = {i.item_id for i in target_items}
                missing = [iid for iid in item_ids if iid not in found]
                return {"error": f"Items not found in order: {missing}"}
            item_statuses = [i.item_status for i in target_items]
        else:
            target_items = order_items
            item_statuses = [i.item_status for i in order_items]
            item_ids = [i.item_id for i in order_items]

        eligibility = policies.check_cancellation_eligibility(
            order_status=order.status,
            shipping_status=order.shipping_status,
            item_statuses=item_statuses,
            item_ids_to_cancel=item_ids,
            total_items=len(order_items),
        )

        if not eligibility["eligible"]:
            return {"status": "rejected", "order_id": order_id, "reason": eligibility["reason"]}

        cancel_fee = eligibility["cancellation_fee"]
        # Compute refund: sum of item prices minus fee
        items_total = sum(i.unit_price for i in target_items)
        refund_amount = items_total - cancel_fee

        if not confirm:
            self._previewed["cancel"].add(order_id)
            return {
                "status": "preview",
                "order_id": order_id,
                "items_to_cancel": [i.item_id for i in target_items],
                "cancellation_fee": cancel_fee,
                "refund_amount": refund_amount,
                "reason": eligibility["reason"],
            }

        if order_id not in self._previewed["cancel"]:
            return {"error": "Must preview cancellation before confirming. Call without confirm first."}

        # Execute cancellation. Prorate the cancellation fee across items
        # so per-item refund_amount fields reflect the post-fee payout.
        self._previewed["cancel"].discard(order_id)
        n = len(target_items)
        per_item_fee = cancel_fee // n if n else 0
        fee_remainder = cancel_fee - per_item_fee * n
        for idx, item in enumerate(target_items):
            item.item_status = "cancelled"
            item_fee = per_item_fee + (1 if idx < fee_remainder else 0)
            item.refund_amount = item.unit_price - item_fee

        # Update order status
        all_items = self._get_items_for_order(order_id)
        all_cancelled = all(i.item_status == "cancelled" for i in all_items)
        if all_cancelled:
            order.status = "cancelled"
        else:
            any_cancelled = any(i.item_status == "cancelled" for i in all_items)
            if any_cancelled:
                order.status = "partially_cancelled"

        # Handle split payment refund
        refund_details: dict[str, Any] = {
            "refund_amount": refund_amount,
            "refund_method": order.payment_method,
        }
        if order.payment_method == "split":
            refund_details["split_details"] = policies.calculate_split_refund(order.payment_details, refund_amount)

        return {
            "status": "cancelled",
            "order_id": order_id,
            "items_cancelled": [i.item_id for i in target_items],
            "cancellation_fee": cancel_fee,
            **refund_details,
        }

    def process_exchange(self, params: dict[str, Any]) -> dict[str, Any]:
        """Exchange an item for a different product/variant. Two-step: preview then confirm."""
        item_id = params.get("item_id", "")
        new_product_id = params.get("new_product_id", "")
        confirm = self.parse_bool(params.get("confirm"))

        # Policy gate
        if "exchange" not in self._policies_checked:
            return {"error": "Policy review required. Call get_policies(topic='exchange') first."}

        item = self.order_items.get(item_id)
        if not item:
            return {"error": f"Item {item_id} not found."}

        order = self.orders.get(item.order_id)
        if not order:
            return {"error": f"Order {item.order_id} not found."}

        old_product = self.products.get(item.product_id)
        new_product = self.products.get(new_product_id)
        if not new_product:
            # Try name-based lookup
            pid_lower = new_product_id.lower().strip()
            for p in self.products.values():
                if p.name.lower() == pid_lower or pid_lower in p.name.lower() or p.name.lower() in pid_lower:
                    new_product = p
                    new_product_id = p.product_id
                    break
        if not old_product:
            return {"error": f"Original product {item.product_id} not found."}
        if not new_product:
            return {"error": f"New product {new_product_id} not found."}

        customer = self.customers.get(order.customer_id)
        if not customer:
            return {"error": f"Customer {order.customer_id} not found."}

        # Determine if same product variant
        same_variant = (
            old_product.category == new_product.category and old_product.subcategory == new_product.subcategory
        )

        exchange = policies.calculate_exchange(
            original_item_price=item.unit_price,
            new_product_price=new_product.price,
            new_product_in_stock=new_product.in_stock,
            category=old_product.category,
            delivery_date=order.delivery_date,
            now=self.now,
            return_window_days=old_product.return_window_days,
            same_product_variant=same_variant,
            membership_tier=customer.membership_tier,
            has_prime_shipping=customer.has_prime_shipping,
        )

        if not exchange["eligible"]:
            return {"status": "rejected", "item_id": item_id, "reason": exchange["reason"]}

        if exchange.get("out_of_stock"):
            return {
                "status": "out_of_stock",
                "item_id": item_id,
                "new_product_id": new_product_id,
                "store_credit_amount": exchange["store_credit_amount"],
                "reason": exchange["reason"],
            }

        if not confirm:
            self._previewed["exchange"].add(item_id)
            return {
                "status": "preview",
                "item_id": item_id,
                "new_product_id": new_product_id,
                "price_difference": exchange["price_difference"],
                "customer_pays": exchange.get("customer_pays", 0),
                "store_credit_refund": exchange.get("store_credit_refund", 0),
                "reason": exchange["reason"],
            }

        if item_id not in self._previewed["exchange"]:
            return {"error": "Must preview exchange before confirming. Call without confirm first."}

        # Execute exchange
        self._previewed["exchange"].discard(item_id)
        item.item_status = "exchanged"

        # Create replacement item
        new_item_id = _next_item_id(self.order_items)
        new_item = OrderItem(
            item_id=new_item_id,
            order_id=order.order_id,
            product_id=new_product_id,
            quantity=item.quantity,
            unit_price=new_product.price,
            item_status="confirmed",
        )
        self.order_items[new_item_id] = new_item
        item.replacement_item_id = new_item_id

        return {
            "status": "exchanged",
            "item_id": item_id,
            "new_item_id": new_item_id,
            "new_product_id": new_product_id,
            "price_difference": exchange["price_difference"],
            "customer_pays": exchange.get("customer_pays", 0),
            "store_credit_refund": exchange.get("store_credit_refund", 0),
        }

    def process_warranty_claim(self, params: dict[str, Any]) -> dict[str, Any]:
        """File a warranty claim. Two-step: preview then confirm."""
        warranty_id = params.get("warranty_id", "")
        item_id = params.get("item_id", "")
        _issue_desc = params.get("issue_description", "")  # logged but not used in policy logic
        confirm = self.parse_bool(params.get("confirm"))

        # Policy gate
        if "warranty" not in self._policies_checked:
            return {"error": "Policy review required. Call get_policies(topic='warranty') first."}

        warranty = self.warranties.get(warranty_id)
        if not warranty:
            return {"error": f"Warranty {warranty_id} not found."}

        item = self.order_items.get(item_id)
        if not item:
            return {"error": f"Item {item_id} not found."}

        claim = policies.check_warranty_claim(
            warranty_type=warranty.warranty_type,
            warranty_start=warranty.start_date,
            warranty_end=warranty.end_date,
            now=self.now,
            claim_count=warranty.claim_count,
            max_claims=warranty.max_claims,
            item_price=item.unit_price,
        )

        if not confirm:
            self._previewed["warranty_claim"].add(warranty_id)
            return {
                "status": "preview",
                "warranty_id": warranty_id,
                "item_id": item_id,
                "eligible": claim["eligible"],
                "resolution": claim.get("resolution"),
                "cost": claim.get("cost", 0),
                "reason": claim["reason"],
            }

        if warranty_id not in self._previewed["warranty_claim"]:
            return {"error": "Must preview warranty claim before confirming. Call without confirm first."}

        if not claim["eligible"] and claim.get("resolution") != "paid_repair":
            return {"status": "rejected", "reason": claim["reason"]}

        # Execute claim
        self._previewed["warranty_claim"].discard(warranty_id)
        warranty.claim_count += 1
        warranty.status = "claimed"

        resolution = claim.get("resolution", "repair")
        warranty.resolution = resolution

        # Create replacement item if resolution is replacement
        replacement_id = None
        if "replacement" in resolution:
            new_item_id = _next_item_id(self.order_items)
            new_item = OrderItem(
                item_id=new_item_id,
                order_id=item.order_id,
                product_id=item.product_id,
                quantity=item.quantity,
                unit_price=item.unit_price,
                item_status="confirmed",
            )
            self.order_items[new_item_id] = new_item
            item.replacement_item_id = new_item_id
            replacement_id = new_item_id

        return {
            "status": "claimed",
            "warranty_id": warranty_id,
            "item_id": item_id,
            "resolution": resolution,
            "cost": claim.get("cost", 0),
            "replacement_item_id": replacement_id,
            "claim_count": warranty.claim_count,
        }

    # -------------------------------------------------------------------
    # Tool handler registry
    # -------------------------------------------------------------------

    @property
    def tool_handlers(self) -> dict[str, Any]:
        return {
            "get_order": self.get_order,
            "get_customer": self.get_customer,
            "get_product": self.get_product,
            "get_policies": self.get_policies,
            "get_warranty_status": self.get_warranty_status,
            "process_return": self.process_return,
            "process_refund": self.process_refund,
            "cancel_order": self.cancel_order,
            "process_exchange": self.process_exchange,
            "process_warranty_claim": self.process_warranty_claim,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _next_item_id(order_items: dict[str, OrderItem]) -> str:
    """Generate next sequential item ID."""
    existing_nums = []
    for iid in order_items:
        if iid.startswith("ITEM-"):
            try:
                existing_nums.append(int(iid.split("-")[1]))
            except (ValueError, IndexError):
                pass
    next_num = max(existing_nums, default=8000) + 1
    return f"ITEM-{next_num}"
