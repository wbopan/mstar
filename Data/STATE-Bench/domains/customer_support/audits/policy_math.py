"""Audit policy math for the customer-support task catalog.

For each scenario, this script:
1. Calls the scenario builder to get the raw ScenarioResult
2. Extracts policy_results from ground_truth_trace
3. For return_item and cancel_order tasks, independently re-invokes the
   policy functions and compares key fields
4. Reports PASS/FAIL per task with details of any mismatch

Exit code 1 if any mismatches found.
"""

from __future__ import annotations

import argparse
import re
import sys
from typing import Any

from domains.customer_support import policies
from domains.customer_support.task_registry import ALL_SCENARIOS, reset_counters
from domains.customer_support.user_attributes import CUSTOMER_ATTRIBUTES

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def get_product_by_id(products: list, product_id: str):
    """Find a product by ID in the products list."""
    for p in products:
        if p.product_id == product_id:
            return p
    return None


def get_order_by_id(orders: list, order_id: str):
    """Find an order by ID."""
    for o in orders:
        if o.order_id == order_id:
            return o
    return None


def get_items_for_order(items: list, order_id: str) -> list:
    """Get all items belonging to an order."""
    return [i for i in items if i.order_id == order_id]


def get_item_by_id(items: list, item_id: str):
    """Find an item by ID."""
    for i in items:
        if i.item_id == item_id:
            return i
    return None


def get_warranty_by_id(warranties: list, warranty_id: str):
    """Find a warranty by ID."""
    for w in warranties:
        if w.warranty_id == warranty_id:
            return w
    return None


def parse_dollar_amounts(text: str) -> list[int]:
    """Extract positive whole-dollar amounts like ``$25`` from free text."""
    return [int(match) for match in re.findall(r"\$(\d+)", text)]


# ---------------------------------------------------------------------------
# Verify: return_item tasks
# ---------------------------------------------------------------------------


def verify_return_item(
    products: list,
    orders: list,
    items: list,
    warranties: list,
    task_data: dict[str, Any],
) -> list[str]:
    """Re-invoke calculate_refund and compare against stored policy_results."""
    errors: list[str] = []
    gt = task_data["ground_truth_trace"]
    stored = gt["policy_results"]
    scenario = task_data["scenario_template"]

    order_id = scenario.get("order_id")
    return_item_id = scenario.get("return_item_id")

    if not order_id or not return_item_id:
        # Some return_item tasks (full_order) may have different structure
        # Try to get from opening_message or just check amounts
        return errors

    order = get_order_by_id(orders, order_id)
    item = get_item_by_id(items, return_item_id)
    if not order or not item:
        errors.append(f"Could not find order {order_id} or item {return_item_id} in scenario data")
        return errors

    product = get_product_by_id(products, item.product_id)
    if not product:
        errors.append(f"Could not find product {item.product_id}")
        return errors

    customer_id = scenario.get("customer_id", order.customer_id)
    customer_attrs = CUSTOMER_ATTRIBUTES.get(customer_id, {})
    membership_tier = customer_attrs.get("membership_tier", "standard")

    # Determine return reason from task context
    # For return_item tasks, the return reason is typically in the description or opening message
    # We infer it from the stored policy_results and task description
    return_reason = _infer_return_reason(task_data, stored)

    is_gift = order.is_gift
    store_credit_only = stored.get("store_credit_only", False)

    recomputed = policies.calculate_refund(
        item_price=item.unit_price,
        return_reason=return_reason,
        category=product.category,
        discount_code=order.discount_code,
        discount_amount=order.discount_amount,
        order_subtotal=order.subtotal,
        membership_tier=membership_tier,
        is_gift_return=is_gift,
        current_product_price=product.current_price,
        store_credit_only=store_credit_only,
    )

    # Compare key fields
    # For shipping_claim tasks where the scenario builder manually constructs policy_results
    # (e.g. shipping_missing_item sets shipping_refund=True as a policy override), skip
    # fields that the scenario builder may have intentionally overridden.
    is_shipping_task = task_data["task_type"] == "shipping_claim"
    compare_keys = ["refund_amount", "restocking_fee", "discount_adjustment", "refund_method"]
    if not is_shipping_task:
        compare_keys.append("shipping_refund")

    for key in compare_keys:
        if key in stored and key in recomputed:
            if stored[key] != recomputed[key]:
                errors.append(
                    f"  return policy mismatch on '{key}': stored={stored[key]}, recomputed={recomputed[key]}"
                )

    return errors


def _infer_return_reason(task_data: dict, policy_results: dict) -> str:
    """Infer the return reason from task context.

    For challenge tasks where the user lies about the reason, the description
    states the correct classification (e.g., "classify as changed_mind, not defective").
    We must use the CORRECT reason, not what the user claims.
    """
    desc = task_data.get("description", "").lower()
    opening = task_data.get("opening_message", "").lower()

    # Check if policy_results explicitly stores the reason
    if "return_reason" in policy_results:
        return policy_results["return_reason"]

    # Challenge tasks: description says "classify as X" or "must classify as X" or "correct classification: X"
    # These override the user's claimed reason
    # IMPORTANT: skip matches preceded by "not" (e.g., "must NOT classify as damaged_in_transit")
    for phrase in ["classify as ", "correct classification: ", "must classify as ", "agent must classify as "]:
        idx = desc.find(phrase)
        if idx != -1:
            # Check this isn't a negation ("not classify as")
            prefix = desc[max(0, idx - 4) : idx].strip()
            if prefix.endswith("not"):
                continue
            after = desc[idx + len(phrase) :].strip().split(",")[0].split(".")[0].split(" ")[0]
            if after in ("changed_mind", "defective", "wrong_item", "damaged_in_transit", "missing"):
                return after

    # Check for explicit "not defective" / "not damaged" overrides
    if "not defective" in desc or "not a defect" in desc:
        return "changed_mind"
    if "not damaged" in desc or "not classify as damaged" in desc:
        return "changed_mind"

    if "defective" in desc or "defective" in opening or "defect" in opening:
        return "defective"
    if "wrong item" in desc or "wrong item" in opening or "received a blender" in opening:
        return "wrong_item"
    if "damaged" in desc or "shattered" in opening or "damaged" in opening:
        return "damaged_in_transit"
    if "missing" in desc or "missing" in opening:
        return "missing"
    if "didn't receive" in desc or "not received" in desc or "never got" in opening or "never received" in opening:
        return "missing"
    if "gift" in desc and "gift return" in desc:
        return "changed_mind"
    # Default
    return "changed_mind"


# ---------------------------------------------------------------------------
# Verify: cancel_order tasks
# ---------------------------------------------------------------------------


def verify_cancel_order(
    products: list,
    orders: list,
    items: list,
    warranties: list,
    task_data: dict[str, Any],
) -> list[str]:
    """Re-invoke check_cancellation_eligibility and compare stored policy_results."""
    errors: list[str] = []
    gt = task_data["ground_truth_trace"]
    stored = gt["policy_results"]
    scenario = task_data["scenario_template"]

    order_id = scenario.get("order_id")
    if not order_id:
        return errors

    order = get_order_by_id(orders, order_id)
    if not order:
        errors.append(f"Could not find order {order_id}")
        return errors

    order_items = get_items_for_order(items, order_id)
    if not order_items:
        errors.append(f"No items found for order {order_id}")
        return errors

    # Skip tasks with no_action (already cancelled, delivered, price_match)
    if stored.get("no_action"):
        return errors

    # Skip price_match tasks — they don't use check_cancellation_eligibility
    if "refund_amount" in stored and "cancellation_fee" not in stored:
        return errors

    # For cancellation tasks that do have a fee, verify
    if "cancellation_fee" in stored:
        item_statuses = [i.item_status for i in order_items]

        # Detect partial cancellation from task description/opening
        desc = task_data.get("description", "").lower()
        opening = task_data.get("opening_message", "").lower()
        is_partial = (
            "cancel 1 of" in desc
            or "cancel only" in desc
            or "cancel just" in desc
            or "cancel the backordered" in desc
            or "cancel just" in opening
            or "cancel only" in opening
        )

        if is_partial:
            # For partial cancels, assume 1 item unless we can infer more
            cancel_count = 1
            # Re-compute fee directly: in_transit → $10 per item
            if order.shipping_status == "in_transit":
                expected_fee = 10 * cancel_count
            else:
                expected_fee = 0

            if expected_fee != stored["cancellation_fee"]:
                errors.append(
                    f"  cancellation_fee mismatch (partial cancel, {cancel_count} items): "
                    f"stored={stored['cancellation_fee']}, expected={expected_fee}"
                )
        else:
            recomputed = policies.check_cancellation_eligibility(
                order_status=order.status,
                shipping_status=order.shipping_status,
                item_statuses=item_statuses,
                item_ids_to_cancel=None,  # full cancel
                total_items=len(order_items),
            )

            if recomputed.get("cancellation_fee") is not None and stored.get("cancellation_fee") is not None:
                if recomputed["cancellation_fee"] != stored["cancellation_fee"]:
                    errors.append(
                        f"  cancellation_fee mismatch: stored={stored['cancellation_fee']}, "
                        f"recomputed={recomputed['cancellation_fee']}"
                    )

    return errors


# ---------------------------------------------------------------------------
# Verify: warranty_claim tasks
# ---------------------------------------------------------------------------


def verify_warranty_claim(
    products: list,
    orders: list,
    items: list,
    warranties: list,
    task_data: dict[str, Any],
) -> list[str]:
    """Re-invoke check_warranty_claim and compare stored policy_results."""
    errors: list[str] = []
    gt = task_data["ground_truth_trace"]
    stored = gt["policy_results"]
    scenario = task_data["scenario_template"]

    warranty_id = scenario.get("warranty_id")
    if not warranty_id:
        return errors

    warranty = get_warranty_by_id(warranties, warranty_id)
    if not warranty:
        errors.append(f"Could not find warranty {warranty_id}")
        return errors

    product = get_product_by_id(products, warranty.product_id)
    if not product:
        errors.append(f"Could not find product {warranty.product_id}")
        return errors

    now = scenario.get("now", "2026-06-12T10:00:00")

    recomputed = policies.check_warranty_claim(
        warranty_type=warranty.warranty_type,
        warranty_start=warranty.start_date,
        warranty_end=warranty.end_date,
        now=now,
        claim_count=warranty.claim_count,
        max_claims=warranty.max_claims,
        item_price=product.price,
    )

    # Compare resolution
    if "resolution" in stored and "resolution" in recomputed:
        if stored["resolution"] != recomputed["resolution"]:
            errors.append(
                f"  warranty resolution mismatch: stored={stored['resolution']}, recomputed={recomputed['resolution']}"
            )

    # Compare cost
    if "cost" in stored and "cost" in recomputed:
        if stored["cost"] != recomputed["cost"]:
            errors.append(f"  warranty cost mismatch: stored={stored['cost']}, recomputed={recomputed['cost']}")

    return errors


# ---------------------------------------------------------------------------
# Verify: exchange_item tasks
# ---------------------------------------------------------------------------


def verify_exchange_item(
    products: list,
    orders: list,
    items: list,
    warranties: list,
    task_data: dict[str, Any],
) -> list[str]:
    """Re-invoke calculate_exchange and compare stored policy_results."""
    errors: list[str] = []
    gt = task_data["ground_truth_trace"]
    stored = gt["policy_results"]
    scenario = task_data["scenario_template"]

    # Skip denied or no_action exchanges
    if stored.get("denied") or stored.get("no_action") or stored.get("out_of_stock"):
        return errors

    order_id = scenario.get("order_id")
    item_id = scenario.get("item_id")
    new_product_id = scenario.get("new_product_id")

    if not order_id or not item_id or not new_product_id:
        return errors

    order = get_order_by_id(orders, order_id)
    item = get_item_by_id(items, item_id)
    if not order or not item:
        return errors

    original_product = get_product_by_id(products, item.product_id)
    new_product = get_product_by_id(products, new_product_id)
    if not original_product or not new_product:
        return errors

    customer_id = scenario.get("customer_id", order.customer_id)
    customer_attrs = CUSTOMER_ATTRIBUTES.get(customer_id, {})
    membership_tier = customer_attrs.get("membership_tier", "standard")
    has_prime = customer_attrs.get("has_prime_shipping", False)

    # Determine if same variant from task description
    desc = task_data.get("description", "").lower()
    same_variant = "same product variant" in desc or "size swap" in desc or "same-variant" in desc

    now = scenario.get("now", "2026-06-12T10:00:00")

    recomputed = policies.calculate_exchange(
        original_item_price=original_product.price,
        new_product_price=new_product.price,
        new_product_in_stock=new_product.in_stock,
        category=original_product.category,
        delivery_date=order.delivery_date,
        now=now,
        return_window_days=original_product.return_window_days,
        same_product_variant=same_variant,
        membership_tier=membership_tier,
        has_prime_shipping=has_prime,
    )

    # Compare key fields
    for key in ("customer_pays", "store_credit_refund"):
        if key in stored and key in recomputed:
            if stored[key] != recomputed[key]:
                errors.append(f"  exchange mismatch on '{key}': stored={stored[key]}, recomputed={recomputed[key]}")

    return errors


# ---------------------------------------------------------------------------
# Verify: expected_outcome dollar amounts vs policy_results
# ---------------------------------------------------------------------------


def verify_dollar_amounts(task_data: dict[str, Any]) -> list[str]:
    """Parse dollar amounts from expected_outcome and cross-check against policy_results."""
    errors: list[str] = []
    gt = task_data["ground_truth_trace"]
    stored = gt["policy_results"]
    expected_outcome = gt.get("expected_outcome", "")

    outcome_amounts = parse_dollar_amounts(expected_outcome)
    if not outcome_amounts:
        return errors

    # Collect all dollar amounts from policy_results (flat + nested)
    policy_amounts = _extract_policy_amounts(stored)

    # Check that every dollar amount in expected_outcome appears somewhere in policy_results
    for amt in outcome_amounts:
        if amt not in policy_amounts:
            errors.append(
                f"  expected_outcome mentions ${amt} but not found in policy_results values {sorted(set(policy_amounts))}"
            )

    return errors


def _extract_policy_amounts(d: dict | list | Any, depth: int = 0) -> list[int]:
    """Recursively extract integer values from policy_results that could be dollar amounts."""
    amounts: list[int] = []
    if depth > 5:
        return amounts
    if isinstance(d, dict):
        for v in d.values():
            amounts.extend(_extract_policy_amounts(v, depth + 1))
    elif isinstance(d, list):
        for item in d:
            if isinstance(item, str):
                amounts.extend(parse_dollar_amounts(item))
            else:
                amounts.extend(_extract_policy_amounts(item, depth + 1))
    elif isinstance(d, int) and d > 0:
        amounts.append(d)
    elif isinstance(d, float) and d > 0:
        amounts.append(int(d))
    elif isinstance(d, str):
        amounts.extend(parse_dollar_amounts(d))
    return amounts


# ---------------------------------------------------------------------------
# Verify: shipping_claim tasks with compensation
# ---------------------------------------------------------------------------


def verify_shipping_compensation(
    products: list,
    orders: list,
    items: list,
    warranties: list,
    task_data: dict[str, Any],
) -> list[str]:
    """For shipping_claim tasks with resolution=compensation, re-invoke calculate_compensation."""
    errors: list[str] = []
    gt = task_data["ground_truth_trace"]
    stored = gt["policy_results"]

    if stored.get("resolution") != "compensation":
        return errors

    # Skip manual multi-step computations (e.g., return + shipping fee tasks)
    # that store resolution=compensation but aren't calculate_compensation() results
    if "phases" in stored:
        return errors

    scenario = task_data["scenario_template"]
    order_id = scenario.get("order_id")
    if not order_id:
        return errors

    order = get_order_by_id(orders, order_id)
    if not order:
        return errors

    customer_id = scenario.get("customer_id", order.customer_id)
    customer_attrs = CUSTOMER_ATTRIBUTES.get(customer_id, {})
    membership_tier = customer_attrs.get("membership_tier", "standard")

    now = scenario.get("now", "2026-06-12T10:00:00")

    recomputed = policies.calculate_compensation(
        delivery_date=order.delivery_date,
        delivery_promised_date=order.delivery_promised_date,
        now=now,
        order_total=order.total_paid,
        shipping_cost=order.shipping_cost,
        membership_tier=membership_tier,
        previous_issues_count=scenario.get("previous_issues_count", 0),
    )

    if "compensation_amount" in stored and "total_compensation" in recomputed:
        if stored["compensation_amount"] != recomputed["total_compensation"]:
            errors.append(
                f"  compensation mismatch: stored={stored['compensation_amount']}, "
                f"recomputed={recomputed['total_compensation']}"
            )

    if "tier_multiplier" in stored and "tier_multiplier" in recomputed:
        if stored["tier_multiplier"] != recomputed["tier_multiplier"]:
            errors.append(
                f"  tier_multiplier mismatch: stored={stored['tier_multiplier']}, "
                f"recomputed={recomputed['tier_multiplier']}"
            )

    return errors


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

# Map ground_truth_trace task_type to verification function
# Note: the gt may use a different task_type than the task_data task_type.
# We use the task_data task_type as primary, but also check gt task_type
# for things like shipping_claim tasks that store refund results under return_item.
VERIFIERS = {
    "return_item": verify_return_item,
    "cancel_order": verify_cancel_order,
    "warranty_claim": verify_warranty_claim,
    "exchange_item": verify_exchange_item,
    "shipping_claim": verify_shipping_compensation,
}


def audit_single(
    idx: int,
    scenario_fn,
    verbose: bool = False,
) -> tuple[str, str, bool, list[str]]:
    """Audit a single scenario. Returns (task_id, task_type, passed, errors)."""
    products, orders, items, warranties, task_data = scenario_fn()

    task_id = task_data["task_id"]
    task_type = task_data["task_type"]
    gt = task_data.get("ground_truth_trace", {})
    gt_task_type = None

    # Determine the effective task_type for policy verification
    # Some shipping_claim tasks store results as return_item in gt
    replay_steps = gt.get("replay_steps")
    if isinstance(replay_steps, list):
        for step in replay_steps:
            if not isinstance(step, dict):
                continue
            name = step.get("name")
            if name == "process_return":
                gt_task_type = "return_item"
                break
            if name == "cancel_order":
                gt_task_type = "cancel_order"
                break
            if name == "process_warranty_claim":
                gt_task_type = "warranty_claim"
                break
            if name == "process_exchange":
                gt_task_type = "exchange_item"
                break

    all_errors: list[str] = []

    # 1. Run task_type verifier
    verifier = VERIFIERS.get(task_type)
    if verifier:
        all_errors.extend(verifier(products, orders, items, warranties, task_data))

    # 2. If gt implies a different task_type, run that verifier too
    if gt_task_type and gt_task_type != task_type:
        verifier2 = VERIFIERS.get(gt_task_type)
        if verifier2:
            all_errors.extend(verifier2(products, orders, items, warranties, task_data))

    passed = len(all_errors) == 0
    return task_id, task_type, passed, all_errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit policy math for CS tasks")
    parser.add_argument("--task", type=str, help="Run a single task by task_id (substring match)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print details for passing tasks too")
    args = parser.parse_args()

    # Reset counters and build all scenarios in order
    reset_counters()

    results: list[tuple[str, str, bool, list[str]]] = []
    pass_count = 0
    fail_count = 0

    for idx, scenario_fn in enumerate(ALL_SCENARIOS):
        task_id, task_type, passed, errors = audit_single(idx, scenario_fn, args.verbose)

        if args.task and args.task not in task_id:
            continue

        results.append((task_id, task_type, passed, errors))

        status = "PASS" if passed else "FAIL"
        if passed:
            pass_count += 1
        else:
            fail_count += 1

        if passed and not args.verbose:
            print(f"  [{status}] {idx + 1:02d}. {task_id} ({task_type})")
        else:
            print(f"  [{status}] {idx + 1:02d}. {task_id} ({task_type})")
            for err in errors:
                print(f"        {err}")

    # Summary
    total = pass_count + fail_count
    print(f"\n{'=' * 60}")
    print(f"  Policy Math Audit: {pass_count}/{total} passed, {fail_count} failed")
    print(f"{'=' * 60}")

    if fail_count > 0:
        print("\nFailed tasks:")
        for task_id, task_type, passed, errors in results:
            if not passed:
                print(f"  - {task_id} ({task_type})")
                for err in errors:
                    print(f"      {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
