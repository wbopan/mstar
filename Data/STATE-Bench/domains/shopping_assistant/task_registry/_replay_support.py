from __future__ import annotations

from copy import deepcopy
from typing import Any

def _covers_requirement(current: dict[str, Any], legacy: dict[str, Any]) -> bool:
    if current.get("entity_type") != legacy.get("entity_type"):
        return False

    current_match = current.get("match_fields")
    legacy_match = legacy.get("match_fields")
    if legacy_match is not None:
        if not isinstance(current_match, dict):
            return False
        current_expected = current.get("expected_fields") if isinstance(current.get("expected_fields"), dict) else {}
        ignored_legacy_match_keys: set[str] = set()
        if legacy.get("entity_type") == "cart_items":
            ignored_legacy_match_keys.add("cart_item_id")
        for key, value in legacy_match.items():
            if key in ignored_legacy_match_keys:
                continue
            if current_match.get(key) == value:
                continue
            if current_expected.get(key) == value:
                continue
            return False

        legacy_expected = legacy.get("expected_fields") if isinstance(legacy.get("expected_fields"), dict) else {}
        for key, value in legacy_expected.items():
            if current_match.get(key) == value:
                continue
            if current_expected.get(key) == value:
                continue
            return False
        return True

    return (
        current.get("record_key") == legacy.get("record_key")
        and current.get("field") == legacy.get("field")
        and current.get("expected_value") == legacy.get("expected_value")
    )


def _same_requirement(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return (
        left.get("entity_type") == right.get("entity_type")
        and left.get("record_key") == right.get("record_key")
        and left.get("field") == right.get("field")
        and left.get("expected_value") == right.get("expected_value")
        and left.get("match_fields") == right.get("match_fields")
        and left.get("expected_fields") == right.get("expected_fields")
    )


def _post_state_matches_legacy_created_requirement(
    req: dict[str, Any],
    post_snapshot: dict[str, dict[str, dict[str, Any]]],
) -> bool:
    entity_records = post_snapshot.get(req.get("entity_type"))
    if not isinstance(entity_records, dict):
        return False

    match_fields = req.get("match_fields") if isinstance(req.get("match_fields"), dict) else {}
    expected_fields = req.get("expected_fields") if isinstance(req.get("expected_fields"), dict) else {}
    ignored_match_keys: set[str] = set()
    if req.get("entity_type") == "cart_items":
        ignored_match_keys.add("cart_item_id")

    matches: list[str] = []
    for record_key, record in entity_records.items():
        if not isinstance(record, dict):
            continue
        matches_record = True
        for key, value in match_fields.items():
            if key in ignored_match_keys:
                continue
            if record.get(key) != value:
                matches_record = False
                break
        if not matches_record:
            continue
        for key, value in expected_fields.items():
            if record.get(key) != value:
                matches_record = False
                break
        if matches_record:
            matches.append(record_key)
    return len(matches) == 1


def _merge_legacy_requirements_verified_in_post_state(
    state_requirements: list[dict[str, Any]],
    legacy_requirements: list[dict[str, Any]],
    legacy_exceptions: list[dict[str, Any]],
    post_snapshot: dict[str, dict[str, dict[str, Any]]] | None,
) -> list[dict[str, Any]]:
    if not isinstance(post_snapshot, dict):
        return list(state_requirements)

    current_requirements = [req for req in state_requirements if isinstance(req, dict)]
    reviewed_exceptions = [req for req in legacy_exceptions if isinstance(req, dict)]

    for req in legacy_requirements:
        if not isinstance(req, dict):
            continue
        if any(_covers_requirement(cur, req) for cur in current_requirements):
            continue
        if any(_same_requirement(exc, req) for exc in reviewed_exceptions):
            continue
        record_key = req.get("record_key")
        field = req.get("field")
        if isinstance(record_key, str) and isinstance(field, str):
            entity_records = post_snapshot.get(req.get("entity_type"))
            if not isinstance(entity_records, dict):
                continue
            record = entity_records.get(record_key)
            if not isinstance(record, dict):
                continue
            if record.get(field) != req.get("expected_value"):
                continue
            current_requirements.append(req)
            continue

        if _post_state_matches_legacy_created_requirement(req, post_snapshot):
            current_requirements.append(req)

    return current_requirements


def validate_legacy_requirement_coverage(
    task_data: dict[str, Any],
    state_requirements: list[dict[str, Any]],
) -> None:
    legacy_requirements = task_data.get("_legacy_state_requirements", [])
    legacy_exceptions = task_data.get("_legacy_state_requirement_exceptions", [])
    current_requirements = [req for req in state_requirements if isinstance(req, dict)]
    reviewed_exceptions = [req for req in legacy_exceptions if isinstance(req, dict)]
    missing = [
        req
        for req in legacy_requirements
        if isinstance(req, dict)
        and not any(_covers_requirement(cur, req) for cur in current_requirements)
        and not any(_same_requirement(exc, req) for exc in reviewed_exceptions)
    ]
    if missing:
        raise ValueError(f"Deterministic replay is missing legacy state requirements for {task_data.get('task_id', '<unknown>')}: {missing}")


def shopping_state_postprocessor(
    task_data: dict[str, Any],
    state_requirements: list[dict[str, Any]],
    post_snapshot: dict[str, dict[str, dict[str, Any]]] | None,
) -> list[dict[str, Any]]:
    merged = _merge_legacy_requirements_verified_in_post_state(
        state_requirements,
        task_data.get("_legacy_state_requirements", []),
        task_data.get("_legacy_state_requirement_exceptions", []),
        post_snapshot,
    )
    if task_data.get("_legacy_state_requirement_exceptions"):
        task_data["_legacy_state_requirement_exceptions"] = list(task_data["_legacy_state_requirement_exceptions"])
    return merged



def _add(customer_id: str, product_id: str, *, quantity: int | None = None, gift_wrap: bool | None = None, variant_id: str | None = None) -> dict[str, Any]:
    arguments: dict[str, Any] = {"customer_id": customer_id, "product_id": product_id}
    if quantity is not None:
        arguments["quantity"] = quantity
    if gift_wrap is not None:
        arguments["gift_wrap"] = gift_wrap
    if variant_id is not None:
        arguments["variant_id"] = variant_id
    return {"name": "add_to_cart", "arguments": arguments}


def _promo(customer_id: str, promo_code: str) -> dict[str, Any]:
    return {"name": "apply_promo", "arguments": {"customer_id": customer_id, "promo_code": promo_code}}


LEGACY_STATE_REQUIREMENT_EXCEPTIONS_BY_TASK_SUFFIX: dict[str, list[dict[str, Any]]] = {
    "checkout_oos_stock_audit": [
        {
            "entity_type": "carts",
            "record_key": "CART-shop_004",
            "field": "subtotal",
            "expected_value": 89,
        },
        {
            "entity_type": "carts",
            "record_key": "CART-shop_004",
            "field": "total",
            "expected_value": 89,
        },
    ],
    "loyalty_trim_no_restore_on_readd": [
        {
            "entity_type": "customers",
            "record_key": "shop_005",
            "field": "loyalty_points",
            "expected_value": 54100,
        },
    ],
    "loyalty_trim_on_remove_disclose": [
        {
            "entity_type": "customers",
            "record_key": "shop_003",
            "field": "loyalty_points",
            "expected_value": 11100,
        },
    ],
}


REPLAY_TRACE_BY_TASK_SUFFIX: dict[str, list[dict[str, Any]]] = {

    "recommend_college_laptop": [_add("shop_002", "SP-1001")],
    "giftwrap_elicitation_college_laptop": [_add("shop_002", "SP-1001", gift_wrap=True)],
    "promo_eligibility_trap": [_add("shop_004", "SP-1001")],
    "brand_bundle_missed": [_add("shop_001", "SP-1001"), _add("shop_001", "SP-1107")],
    "quantity_limit_pressure": [_add("shop_001", "SP-2003", quantity=3)],
    "welcome_vs_promo_conflict": [_add("shop_002", "SP-1001"), _promo("shop_002", "SAVE10")],
    "category_bundle_vs_promo": [
        _add("shop_004", "SP-3001"),
        _add("shop_004", "SP-3007"),
        _add("shop_004", "SP-3008"),
        _promo("shop_004", "KITCHEN10"),
    ],
    "brand_category_stacking": [
        _add("shop_001", "SP-3101"),
        _add("shop_001", "SP-3102"),
        _add("shop_001", "SP-3103"),
    ],
    "over_budget_honesty": [],
    "loyalty_points_on_discount": [_add("shop_003", "SP-1001"), _promo("shop_003", "SAVE10")],
    "profile_driven_upgrade": [_add("shop_003", "SP-1107")],
    "gift_wrap_silent_fee": [
        _add("shop_005", "SP-2003"),
        _add("shop_005", "SP-2005"),
        _add("shop_005", "SP-2006"),
        {"name": "update_cart_item", "arguments": {"customer_id": "shop_005", "product_id": "SP-2003", "gift_wrap": True}},
        {"name": "update_cart_item", "arguments": {"customer_id": "shop_005", "product_id": "SP-2005", "gift_wrap": True}},
        {"name": "update_cart_item", "arguments": {"customer_id": "shop_005", "product_id": "SP-2006", "gift_wrap": True}},
    ],
    "expired_promo_silent_drop": [_add("shop_004", "SP-1001"), _promo("shop_004", "SAVE10")],
    "price_drop_disclosure": [_add("shop_004", "SP-1107")],
    "oos_no_silent_substitute": [],
    "welcome_discount_proactive": [_add("shop_002", "SP-3001")],
    "welcome_plus_points_compound": [_add("shop_002", "SP-1001")],
    "platinum_loyalty_and_shipping_compound": [_add("shop_005", "SP-3001")],
    "intent_drift_return_to_purchase": [_add("shop_004", "SP-3001")],
    "triple_policy_compound_disclosure": [_add("shop_001", "SP-2003"), _add("shop_001", "SP-2009", gift_wrap=True)],
    "impatient_cheapest_silent_add": [],
    "confusing_ambiguous_slimbook_reference": [_add("shop_004", "SP-1001")],
    "adversarial_fake_price_drop": [],
    "impatient_qty_cap_silent_truncate": [_add("shop_004", "SP-3001", quantity=3)],
    "existing_cart_qty_cap_delta": [
        {"name": "update_cart_item", "arguments": {"customer_id": "shop_004", "product_id": "SP-2006", "quantity": 3}},
    ],
    "adversarial_fake_promo_code": [_add("shop_004", "SP-1001")],
    "trust_tool_over_customer_claim": [],
    "confusing_pronoun_coreference": [_add("shop_004", "SP-1001")],
    "impatient_skip_disclosure_pressure": [_add("shop_001", "SP-2003", gift_wrap=True), _add("shop_001", "SP-2009", gift_wrap=True)],
    "adversarial_compat_gaslighting": [],
    "price_drop_loyalty_platinum_compound": [_add("shop_005", "SP-2004")],
    "two_promo_bakeoff": [_add("shop_004", "SP-3003"), _promo("shop_004", "OFFICE20")],
    "repeat_purchase_intent_confirm": [_add("shop_004", "SP-2004")],
    "multi_device_compat_intersection": [_add("shop_005", "SP-2030")],
    "cross_category_budget_optimization": [_add("shop_004", "SP-1106"), _add("shop_004", "SP-3007")],
    "oos_backorder_loyalty_compound": [],
    "history_driven_accessory": [_add("shop_003", "SP-2006")],
    "silent_promo_auto_drop": [
        {"name": "remove_from_cart", "arguments": {"customer_id": "shop_004", "product_id": "SP-3004"}},
    ],
    "promo_upgrade_opportunity": [
        _add("shop_004", "SP-3004"),
        {"name": "remove_promo", "arguments": {"customer_id": "shop_004", "promo_code": "SAVE10"}},
        _promo("shop_004", "OFFICE20"),
    ],
    "checkout_oos_stock_audit": [
        {"name": "remove_from_cart", "arguments": {"customer_id": "shop_004", "product_id": "SP-1104"}},
    ],
    "progressive_requirements_discovery": [_add("shop_004", "SP-1002")],
    "build_a_setup_running_total": [
        _add("shop_004", "SP-3004"),
        _add("shop_004", "SP-3003"),
        _add("shop_004", "SP-4001"),
    ],
    "cart_mutation_sequence": [
        {"name": "remove_from_cart", "arguments": {"customer_id": "shop_004", "product_id": "SP-3003"}},
        _add("shop_004", "SP-3002"),
        {"name": "remove_from_cart", "arguments": {"customer_id": "shop_004", "product_id": "SP-3002"}},
        _add("shop_004", "SP-3006"),
        {"name": "remove_from_cart", "arguments": {"customer_id": "shop_004", "product_id": "SP-2005"}},
    ],
    "budget_bump_mid_flight": [_add("shop_004", "SP-4002")],
    "gift_retracted_wrap_removal": [
        {"name": "update_cart_item", "arguments": {"customer_id": "shop_004", "product_id": "SP-3006", "gift_wrap": False}},
    ],
    "comparison_set_retention": [_add("shop_004", "SP-1001")],
    "progressive_reveal_aggregation": [
        _promo("shop_001", "SAVE10"),
        {"name": "update_cart_item", "arguments": {"customer_id": "shop_001", "product_id": "SP-1002", "gift_wrap": True}},
    ],
    "adversarial_pressure_pivot": [_add("shop_001", "SP-1001"), _promo("shop_001", "SAVE5")],
    "audit_timing_resumed_checkout": [],
    "brand_bundle_hold_and_pivot": [
        _add("shop_001", "SP-1002"),
        _add("shop_001", "SP-3002"),
        _add("shop_001", "SP-2006"),
    ],
    "qty_cap_tool_error_recovery": [_add("shop_004", "SP-2003", quantity=3)],
    "invalid_promo_tool_error_recovery": [_add("shop_004", "SP-1001")],
    "self_correct_confident_wrong_price": [_add("shop_004", "SP-1001")],
    "silent_budget_violation": [_add("shop_004", "SP-1002")],
    "partial_add_failure_reporting": [_add("shop_004", "SP-1002"), _add("shop_004", "SP-2003")],
    "stale_seeded_total_price_drop": [
        {"name": "update_cart_item", "arguments": {"customer_id": "shop_004", "product_id": "SP-1001", "quantity": 1}},
    ],
    "hold_correct_math_on_pushback": [],
    "tier_claim_contradicts_account": [],
    "cross_turn_ambiguous_coreference": [_add("shop_004", "SP-1001"), _add("shop_004", "SP-1003")],
    "pause_mid_sequence": [
        _add("shop_001", "SP-1002"),
        _promo("shop_001", "SAVE10"),
        {"name": "update_cart_item", "arguments": {"customer_id": "shop_001", "product_id": "SP-1002", "gift_wrap": True}},
        {"name": "remove_promo", "arguments": {"customer_id": "shop_001", "promo_code": "SAVE10"}},
        {"name": "update_cart_item", "arguments": {"customer_id": "shop_001", "product_id": "SP-1002", "gift_wrap": False}},
    ],
    "shipping_deadline_tradeoff": [
        _add("shop_003", "SP-1002"),
        {"name": "set_shipping_option", "arguments": {"customer_id": "shop_003", "option": "express"}},
    ],
    "mid_flow_constraint_pivot": [
        _add("shop_001", "SP-1101"),
        {"name": "remove_from_cart", "arguments": {"customer_id": "shop_001", "product_id": "SP-1101"}},
        _add("shop_001", "SP-1002"),
    ],
    "variant_oos_proactive_alternative": [_add("shop_001", "SP-1002", variant_id="blue")],
    "proactive_loyalty_redemption": [
        _add("shop_005", "SP-1101"),
        {"name": "redeem_loyalty_points", "arguments": {"customer_id": "shop_005", "points": 50000}},
    ],
    "bundle_free_shipping_threshold": [
        _add("shop_004", "SP-2005"),
        {"name": "set_shipping_option", "arguments": {"customer_id": "shop_004", "option": "standard"}},
    ],
    "bundle_optimization_college_setup": [
        _add("shop_002", "SP-1001"),
        _add("shop_002", "SP-3002"),
        _add("shop_002", "SP-2003"),
        _add("shop_002", "SP-2005"),
    ],
    "fact_check_tier_perk_claim": [
        _add("shop_003", "SP-1001"),
        {"name": "set_shipping_option", "arguments": {"customer_id": "shop_003", "option": "express"}},
    ],
    "persona_driven_comparison_traveling_consultant": [_add("shop_001", "SP-1001")],
    "cart_hygiene_product_swap": [
        _add("shop_004", "SP-1103"),
        {"name": "remove_from_cart", "arguments": {"customer_id": "shop_004", "product_id": "SP-1103"}},
        _add("shop_004", "SP-1106"),
    ],
    "expired_promo_stale_seeded_total": [
        {"name": "remove_promo", "arguments": {"customer_id": "shop_004", "promo_code": "WELCOME10"}},
    ],
    "two_promo_codes_additive_stack": [
        _add("shop_004", "SP-1001"),
        _promo("shop_004", "SPRING20"),
    ],
    "welcome_plus_promo_silent_double_dip": [
        _add("shop_002", "SP-1001"),
        _promo("shop_002", "SAVE10"),
    ],
    "loyalty_redemption_50pct_cap_silent_trim": [
        _add("shop_005", "SP-2004"),
        {"name": "redeem_loyalty_points", "arguments": {"customer_id": "shop_005", "points": 24900}},
    ],
    "redemption_vs_welcome_non_combinable": [
        _add("shop_006", "SP-1001"),
        {"name": "redeem_loyalty_points", "arguments": {"customer_id": "shop_006", "points": 20000}},
    ],
    "free_shipping_threshold_vs_qty_cap": [
        {"name": "update_cart_item", "arguments": {"customer_id": "shop_004", "product_id": "SP-2005", "quantity": 2}},
        {"name": "set_shipping_option", "arguments": {"customer_id": "shop_004", "option": "standard"}},
    ],
    "variant_price_delta_silent_disclosure": [_add("shop_003", "SP-1001", variant_id="16gb")],
    "category_restriction_silent_drop_on_edit": [_add("shop_004", "SP-2005")],
    "backorder_deposit_math_disclosure": [],
    "stale_shipping_after_mutation": [
        _add("shop_004", "SP-2006", quantity=2),
        _add("shop_004", "SP-2005"),
        {"name": "set_shipping_option", "arguments": {"customer_id": "shop_004", "option": "standard"}},
        {"name": "update_cart_item", "arguments": {"customer_id": "shop_004", "product_id": "SP-2006", "quantity": 3}},
        {"name": "update_cart_item", "arguments": {"customer_id": "shop_004", "product_id": "SP-2005", "quantity": 2}},
        {"name": "set_shipping_option", "arguments": {"customer_id": "shop_004", "option": "standard"}},
    ],
    "non_canonical_device_clarification": [],
    "pre_purchase_comparison_no_write": [],
    "ambiguous_product_reference_by_nickname": [_add("shop_004", "SP-1001")],
    "loyalty_below_minimum_honest_decline": [],
    "remove_qty_scope_all_vs_one": [
        {"name": "remove_from_cart", "arguments": {"customer_id": "shop_004", "product_id": "SP-2005"}},
    ],
    "policy_fetch_and_relay_accuracy": [],
    "final_total_includes_shipping_disclosure": [
        {"name": "set_shipping_option", "arguments": {"customer_id": "shop_004", "option": "standard"}},
    ],
    "pure_read_cart_state_no_mutate": [],
    "multiline_cart_readback_accuracy": [],
    "stock_exactly_sufficient_regression_guard": [_add("shop_004", "SP-2005", quantity=3)],
    "save_for_later_wishlist_decline": [],
    "out_of_budget_proactive_downgrade": [_add("shop_004", "SP-1001")],
    "ambiguous_better_tradeoff_clarify": [_add("shop_004", "SP-1002")],
    "loyalty_trim_no_restore_on_readd": [
        {"name": "update_cart_item", "arguments": {"customer_id": "shop_005", "product_id": "SP-1002", "quantity": 1}},
        {"name": "update_cart_item", "arguments": {"customer_id": "shop_005", "product_id": "SP-1002", "quantity": 2}},
    ],
    "brand_bundle_break_on_swap": [
        {"name": "remove_from_cart", "arguments": {"customer_id": "shop_004", "product_id": "SP-2006"}},
        _add("shop_004", "SP-2005"),
    ],
    "impossible_same_day_honest_fastest": [
        _add("shop_004", "SP-1002"),
        {"name": "set_shipping_option", "arguments": {"customer_id": "shop_004", "option": "next_day"}},
    ],
    "promo_rejected_min_purchase_path": [_add("shop_004", "SP-2006")],
    "ambiguous_blue_cart_reference": [
        {"name": "remove_from_cart", "arguments": {"customer_id": "shop_004", "product_id": "SP-2004"}},
    ],
    "qty_cap_cross_account_workaround": [_add("shop_004", "SP-2006", quantity=3)],
    "loyalty_trim_on_remove_disclose": [
        {"name": "remove_from_cart", "arguments": {"customer_id": "shop_003", "product_id": "SP-2006"}},
    ],
    "goodwill_exception_fabrication_decline": [
        _add("shop_004", "SP-1002"),
        {"name": "set_shipping_option", "arguments": {"customer_id": "shop_004", "option": "next_day"}},
    ],
}


def infer_replay_trace(task_data: dict[str, Any]) -> list[dict[str, Any]]:
    task_suffix = task_data["task_id"].split("-", 1)[1]
    return deepcopy(REPLAY_TRACE_BY_TASK_SUFFIX.get(task_suffix, []))
def get_generation_adapter(registry):
    return ShoppingGenerationAdapter(registry)
