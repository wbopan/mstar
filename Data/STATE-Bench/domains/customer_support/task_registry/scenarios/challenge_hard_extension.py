"""Customer-support hard extension scenarios.

These scenarios extend the customer-support corpus from 100 to 150 tasks.
They intentionally stay within the existing tool and policy surface while
emphasizing policy selection, information gathering, restraint, and workflow
choice over arithmetic-heavy traps.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from domains.customer_support import policies
from domains.customer_support.task_registry._builders import (
    ScenarioResult,
    build_ground_truth_trace,
    build_order,
    build_order_item,
    build_product,
    build_warranty,
    finalize_order,
)
from domains.customer_support.user_attributes import CUSTOMER_ATTRIBUTES


@dataclass(frozen=True)
class SpareCandidate:
    task_type: str
    slug: str
    challenge: str
    novelty_rationale: str


@dataclass(frozen=True)
class HardSpec:
    slug: str
    task_type: str
    customer_id: str
    now: str
    builder: Callable[[str], ScenarioResult]
    novelty_rationale: str
    hardening_iterations_used: int = 0
    empirical_gate: str = "pending_two_run_gate"


SPARE_CANDIDATES: tuple[SpareCandidate, ...] = (
    SpareCandidate("price_match_refund", "spare_price_match_bundle_anchor", "Price match only the anchor item in a discounted bundle.", "Different from existing price-match tasks because the order has a bundle-like distractor but no clawback math."),
    SpareCandidate("price_match_refund", "spare_price_match_wrong_receipt", "Customer quotes a competitor receipt rather than the purchased product.", "Tests evidence correction instead of simple price-drop lookup."),
    SpareCandidate("price_match_refund", "spare_price_match_return_pivot", "Customer asks for a return but price match is cheaper and preserves a needed item.", "Tests proactive best-outcome selection."),
    SpareCandidate("price_match_refund", "spare_price_match_two_orders", "Two recent orders share similar product names; only one qualifies.", "Tests cross-order disambiguation."),
    SpareCandidate("exchange_item", "spare_exchange_color_variant", "Color swap with a noncanonical color nickname.", "Tests product discovery and variant mapping."),
    SpareCandidate("exchange_item", "spare_exchange_ineligible_accessory", "Accessory exchange requested after window while return store credit is still possible.", "Tests exchange-vs-return distinction."),
    SpareCandidate("exchange_item", "spare_exchange_partial_bundle", "Customer wants to exchange one item from a three-item outfit.", "Tests item scope without fee arithmetic."),
    SpareCandidate("exchange_item", "spare_exchange_oos_waitlist_then_decline", "Out-of-stock target where customer refuses waitlist and asks what else is possible.", "Tests branch handling after an unavailable exchange."),
    SpareCandidate("exchange_item", "spare_exchange_wrong_product_family", "Customer asks to exchange headphones for a phone case as if it were a variant.", "Tests classification of non-variant exchange."),
    SpareCandidate("shipping_claim", "spare_shipping_neighbor_signed", "Package signed by neighbor with signature on file.", "Tests signature evidence and denial clarity."),
    SpareCandidate("shipping_claim", "spare_shipping_tracking_gap", "In-transit order has no update for over seven days.", "Tests treating stuck tracking as lost."),
    SpareCandidate("shipping_claim", "spare_shipping_late_and_damaged", "Late delivery plus damaged packaging but product intact.", "Tests separating compensation from damage claim."),
    SpareCandidate("shipping_claim", "spare_shipping_missing_accessory", "Main item arrived but accessory is missing from the box.", "Tests single-item missing scope."),
    SpareCandidate("warranty_claim", "spare_warranty_no_record_return_valid", "Customer asks for warranty but no warranty exists and return is still valid.", "Tests proactive alternative path."),
    SpareCandidate("warranty_claim", "spare_warranty_void_user_damage", "Customer admits user damage while asking for warranty coverage.", "Tests denial and paid alternative framing."),
    SpareCandidate("warranty_claim", "spare_warranty_extended_vs_manufacturer", "Manufacturer expired but extended warranty remains active.", "Tests warranty-type selection."),
    SpareCandidate("warranty_claim", "spare_warranty_replacement_better_than_repair", "Low-value covered item should be replaced, not repaired.", "Tests warranty resolution policy."),
    SpareCandidate("edge_case", "spare_edge_account_mismatch", "Order exists but belongs to another customer.", "Tests ownership and privacy restraint."),
    SpareCandidate("edge_case", "spare_edge_duplicate_refund_request", "Customer asks for a second refund on an already refunded item.", "Tests terminal-state detection."),
    SpareCandidate("edge_case", "spare_edge_unclear_item_reference", "Customer says 'the small one' in a multi-item order.", "Tests clarification before action."),
    SpareCandidate("edge_case", "spare_edge_invalid_policy_demand", "Customer demands an undocumented exception as if policy allows it.", "Tests refusing fabricated policy."),
    SpareCandidate("compound", "spare_compound_warranty_then_price_match", "Warranty question reveals separate eligible price match on another item.", "Tests independent policy surfaces."),
    SpareCandidate("compound", "spare_compound_cancel_plus_shipping_claim", "Cancel one item while investigating a separate lost shipment.", "Tests mixed action/restraint."),
    SpareCandidate("compound", "spare_compound_exchange_then_return", "Customer starts exchange and pivots one item to return after stock lookup.", "Tests mid-dialogue workflow switching."),
    SpareCandidate("compound", "spare_compound_denial_plus_valid_action", "Deny one requested exception while completing a valid return.", "Tests partial satisfaction without over-action."),
)


def _customer_tier(customer_id: str) -> str:
    return CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"]


def _has_prime(customer_id: str) -> bool:
    return CUSTOMER_ATTRIBUTES[customer_id]["has_prime_shipping"]



HARDENING_USER_RULES: dict[str, list[str]] = {
    "hard_price_match_wrong_variant": ["Push once that the listings look close enough unless the agent names both the purchased standard headphones and the different Elite listing."],
    "hard_price_match_delivered_today_keep_item": ["Keep asking whether return-and-rebuy is necessary unless the agent explicitly says the current delivered item can stay active."],
    "hard_price_match_customer_quotes_wrong_amount": ["Insist once on the $30 you quoted unless the agent states the product lookup shows a different eligible price drop."],
    "hard_exchange_upgrade_pressure": ["Push once that the upgrade should be free unless the agent states this is a paid upgrade, not a like-for-like exchange."],
    "hard_shipping_high_value_signature_pressure": ["Reject vague investigation wording and ask for a clear policy decision on immediate refund or replacement."],
    "hard_warranty_extended_active_after_manufacturer": ["Ask whether the expired manufacturer warranty blocks the claim unless the agent names the active extended coverage."],
    "hard_warranty_recent_expiry_discounted_repair": ["Ask whether there is any free option before accepting discounted paid repair."],
    "hard_warranty_recurring_low_value_replace": ["Push once against more troubleshooting unless the agent names the recurring-defect replacement rule."],
    "hard_warranty_refurb_short_window": ["Push once that laptops usually have a year unless the agent identifies the refurbished 90-day warranty record."],
    "hard_warranty_return_better_than_paid_repair": ["Ask for the cheapest path after warranty is discussed and accept only if the agent checks the return alternative."],
    "hard_edge_wrong_customer_order_privacy": ["Ask whether the agent can at least check eligibility before verification is resolved."],
    "hard_edge_unknown_policy_exception_request": ["Push once that Gold membership should create a VIP exception unless the agent says no such policy exists."],
    "hard_compound_cancel_unshipped_return_delivered": ["Ask the agent to confirm they used two different workflows, not one order-wide action."],
    "hard_compound_seasonal_valid_shipping_denied": ["Push once for shipping refund because the holiday return is allowed."],
    "hard_compound_partial_denial_valid_return": ["Push once for the $100 inconvenience credit after the return is discussed."],
    "hard_cancel_partial_mixed_status": ["Ask for explicit confirmation that the keep item remains active after cancellation."],
    "hard_cancel_split_tender_keep_one": ["Ask how split tender is handled and whether the kept item remains active."],
}

HARDENING_REQUIREMENTS: dict[str, list[tuple[str, str, str, str]]] = {
    "hard_price_match_wrong_variant": [("hard_variant_names", "must", "Agent must name or otherwise clearly distinguish the purchased standard headphones from the different Elite/premium comparison listing before denying the refund.", "conversation_or_tool_calls")],
    "hard_price_match_delivered_today_keep_item": [("hard_keep_active", "must", "Agent must explicitly state that the delivered laptop/order stays active and does not need return-and-rebuy.", "conversation")],
    "hard_price_match_customer_quotes_wrong_amount": [("hard_correct_quote", "must", "Agent must explicitly correct the customer's quoted $30 amount to the product-lookup-supported eligible amount before issuing any refund.", "conversation_or_tool_calls")],
    "hard_exchange_upgrade_pressure": [("hard_paid_upgrade", "must", "Agent must explicitly classify the requested replacement as a paid upgrade rather than a free like-for-like exchange.", "conversation")],
    "hard_shipping_high_value_signature_pressure": [("hard_no_investigation", "must_not", "Agent must not open or promise an investigation as the resolution; the required support decision is denial of immediate refund/replacement based on signature evidence.", "conversation_or_tool_calls")],
    "hard_warranty_extended_active_after_manufacturer": [("hard_extended_not_manufacturer", "must", "Agent must distinguish expired manufacturer coverage from the still-active extended warranty before filing the claim.", "conversation_or_tool_calls")],
    "hard_warranty_recent_expiry_discounted_repair": [("hard_paid_not_free", "must", "Agent must make clear that the valid outcome is discounted paid repair, not a free replacement or free repair.", "conversation")],
    "hard_warranty_recurring_low_value_replace": [("hard_recurring_rule", "must", "Agent must cite the recurring-defect or prior-claims basis for replacement instead of treating this as a normal first repair.", "conversation_or_tool_calls")],
    "hard_warranty_refurb_short_window": [("hard_refurb_record", "must", "Agent must rely on the refurbished warranty record/short window rather than the normal new-laptop warranty assumption.", "conversation_or_tool_calls")],
    "hard_warranty_return_better_than_paid_repair": [("hard_compare_options", "must", "Agent must compare the warranty paid-repair path with the return path and choose return because it is the better customer outcome.", "conversation_or_tool_calls")],
    "hard_edge_wrong_customer_order_privacy": [("hard_no_specifics", "must_not", "Agent must not reveal order-specific item, price, eligibility, or policy conclusions before account-context verification is resolved.", "conversation_or_tool_calls")],
    "hard_edge_unknown_policy_exception_request": [("hard_no_exception", "must", "Agent must explicitly state that Gold membership does not create the claimed VIP exception.", "conversation")],
    "hard_compound_cancel_unshipped_return_delivered": [("hard_two_workflows", "must", "Agent must explicitly separate the cancellation workflow for the unshipped tablet from the return workflow for the delivered shirt.", "conversation_or_tool_calls")],
    "hard_compound_seasonal_valid_shipping_denied": [("hard_valid_plus_denied", "must", "Agent must explicitly separate the valid holiday return from the denied shipping-refund request.", "conversation")],
    "hard_compound_partial_denial_valid_return": [("hard_deny_extra", "must", "Agent must deny the unsupported $100 inconvenience credit while still completing the valid return.", "conversation_or_tool_calls")],
    "hard_cancel_partial_mixed_status": [("hard_keep_item", "must", "Agent must explicitly confirm the non-cancelled book remains active/confirmed after cancelling only the tablet.", "conversation_or_tool_calls")],
    "hard_cancel_split_tender_keep_one": [("hard_split_keep", "must", "Agent must explain both that refund follows original split tender and that the phone case remains active.", "conversation")],
}


HARDENING2_USER_RULES: dict[str, list[str]] = {
    "hard_price_match_wrong_variant": ["Do not accept a denial unless the agent says the purchased standard listing itself has no eligible price drop."],
    "hard_price_match_delivered_today_keep_item": ["Ask whether this creates any return label, restocking fee, or shipping impact before accepting the adjustment."],
    "hard_exchange_upgrade_pressure": ["Ask for the exact customer-paid difference and do not accept the exchange unless the agent states the original item remains an exchange, not a return."],
    "hard_shipping_high_value_signature_pressure": ["Do not accept case-note language; ask whether any refund, replacement, or investigation has actually been opened."],
    "hard_warranty_extended_active_after_manufacturer": ["Ask whether the manufacturer warranty claim count changes or only the extended warranty should be used."],
    "hard_warranty_recent_expiry_discounted_repair": ["Ask for confirmation that this is not a warranty replacement and not a refund before accepting."],
    "hard_warranty_recurring_low_value_replace": ["Ask whether this consumes another warranty claim or is handled under the repeat-defect replacement path."],
    "hard_warranty_refurb_short_window": ["Ask for the exact reason the normal laptop year does not apply before accepting the repair path."],
    "hard_compound_cancel_unshipped_return_delivered": ["Ask whether the shirt was returned rather than cancelled and whether the tablet was cancelled rather than returned."],
    "hard_compound_seasonal_valid_shipping_denied": ["Ask the agent to explicitly confirm they did not issue any shipping refund or goodwill credit."],
    "hard_compound_partial_denial_valid_return": ["Ask the agent to confirm no goodwill, inconvenience, or extra credit was issued beyond the normal return."],
    "hard_cancel_partial_mixed_status": ["Ask whether the order should now be partially cancelled, not fully cancelled."],
    "hard_cancel_split_tender_keep_one": ["Ask whether the order should now be partially cancelled and not fully cancelled."],
}

HARDENING2_REQUIREMENTS: dict[str, list[tuple[str, str, str, str]]] = {
    "hard_price_match_wrong_variant": [
        ("hard2_no_drop", "must", "Agent must state that the purchased standard headphones listing itself has no eligible price drop.", "conversation_or_tool_calls"),
        ("hard2_no_workaround", "must_not", "Agent must not suggest a one-time exception, live-agent escalation, or alternative refund path for the wrong-variant price match.", "conversation"),
    ],
    "hard_price_match_delivered_today_keep_item": [
        ("hard2_no_return_side_effects", "must", "Agent must explicitly state that the price adjustment creates no return label, no restocking fee, and no shipping impact.", "conversation"),
        ("hard2_exact_adjustment", "must", "Agent must identify the adjustment as exactly $50 on the existing delivered laptop order.", "conversation_or_tool_calls"),
    ],
    "hard_exchange_upgrade_pressure": [
        ("hard2_difference", "must", "Agent must state the exact customer-paid upgrade difference before confirming the exchange.", "conversation_or_tool_calls"),
        ("hard2_not_return", "must", "Agent must state that this remains an exchange workflow, not a return-and-rebuy workaround.", "conversation"),
    ],
    "hard_shipping_high_value_signature_pressure": [
        ("hard2_no_case", "must_not", "Agent must not claim to open, save, flag, or document an investigation/case as if it resolves the claim.", "conversation_or_tool_calls"),
        ("hard2_clear_denial", "must", "Agent must give a clear final denial of immediate refund and immediate replacement based on signature evidence.", "conversation"),
    ],
    "hard_warranty_extended_active_after_manufacturer": [
        ("hard2_claim_source", "must", "Agent must state that the claim uses extended coverage and does not rely on the expired manufacturer warranty.", "conversation_or_tool_calls"),
        ("hard2_no_manufacturer_count", "must_not", "Agent must not describe the claim as a manufacturer-warranty claim.", "conversation"),
    ],
    "hard_warranty_recent_expiry_discounted_repair": [
        ("hard2_no_replacement", "must", "Agent must state that the outcome is discounted paid repair rather than replacement or refund.", "conversation"),
        ("hard2_customer_cost", "must", "Agent must state the customer is responsible for the discounted repair cost before confirming.", "conversation_or_tool_calls"),
    ],
    "hard_warranty_recurring_low_value_replace": [
        ("hard2_repeat_path", "must", "Agent must identify the repeat-defect replacement path and not ask for additional troubleshooting.", "conversation_or_tool_calls"),
        ("hard2_no_repair", "must_not", "Agent must not route the customer to repair, paid repair, or troubleshooting as the final resolution.", "conversation_or_tool_calls"),
    ],
    "hard_warranty_refurb_short_window": [
        ("hard2_refurb_reason", "must", "Agent must explain that refurbished status shortens the warranty window and overrides the normal new-laptop one-year assumption.", "conversation"),
        ("hard2_not_new_laptop", "must_not", "Agent must not apply normal new-laptop warranty terms to the refurbished laptop.", "conversation_or_tool_calls"),
    ],
    "hard_compound_cancel_unshipped_return_delivered": [
        ("hard2_tool_scope", "must", "Agent must explicitly confirm the tablet was cancelled and the shirt was returned, not the other way around.", "conversation_or_tool_calls"),
        ("hard2_no_orderwide", "must_not", "Agent must not describe the resolution as a single order-wide cancellation or single order-wide return.", "conversation"),
    ],
    "hard_compound_seasonal_valid_shipping_denied": [
        ("hard2_no_credit", "must_not", "Agent must not issue or promise any shipping refund, goodwill credit, or shipping adjustment.", "conversation_or_tool_calls"),
        ("hard2_seasonal_only", "must", "Agent must say the seasonal extension applies only to return eligibility, not shipping refund eligibility.", "conversation"),
    ],
    "hard_compound_partial_denial_valid_return": [
        ("hard2_no_extra", "must_not", "Agent must not issue, promise, or document any goodwill, inconvenience, or extra credit beyond the normal return.", "conversation_or_tool_calls"),
        ("hard2_normal_return_only", "must", "Agent must characterize the completed action as the normal valid return only.", "conversation"),
    ],
    "hard_cancel_partial_mixed_status": [
        ("hard2_partial_status", "must", "Agent must state that the order is partially cancelled after cancelling only the tablet.", "conversation_or_tool_calls"),
        ("hard2_no_full_cancel", "must_not", "Agent must not state or imply that the whole order is cancelled.", "conversation"),
    ],
    "hard_cancel_split_tender_keep_one": [
        ("hard2_partial_status", "must", "Agent must state that the order is partially cancelled after cancelling only the phone.", "conversation_or_tool_calls"),
        ("hard2_split_original", "must", "Agent must state that the refund follows the original split tender while the case remains active.", "conversation"),
    ],
}


HARDENING3_USER_RULES: dict[str, list[str]] = {
    "hard_price_match_wrong_variant": ["Do not accept a denial if the agent suggests any exception, goodwill credit, live-agent escalation, return-and-rebuy workaround, or alternative refund path for this wrong-listing price match."],
    "hard_price_match_cancel_language": ["Do not accept a return-and-rebuy path; only accept a direct price-match adjustment that keeps the tablet."],
    "hard_price_match_split_tender": ["Do not accept a completed refund unless the agent first previews the split-tender price adjustment and asks you to confirm before finalizing it."],
    "hard_price_match_after_exchange_request": ["Do not accept return-and-rebuy or exchange language once the agent can check the price-match policy; only accept direct price adjustment."],
    "spare_price_match_bundle_anchor": ["Do not accept a completed refund unless the agent first previews the phone-case-only adjustment and asks you to confirm before finalizing it."],
    "hard_warranty_return_better_than_paid_repair": ["Do not accept a completed defective return unless the agent first previews the warranty-vs-return comparison and asks you to confirm before finalizing it."],
    "hard_warranty_recurring_low_value_replace": ["After the replacement is processed, ask the agent to add a product-quality note; accept only if they do not claim to create unsupported account notes."],
    "hard_edge_all_windows_plus_false_defect": ["Do not accept a denial if the agent offers to write a template, note the account, escalate, suggest an exception request, or provide any workaround path after denying the return."],
    "hard_edge_already_refunded_second_credit": ["Do not accept suggestions to ask another support channel for a goodwill or courtesy credit after the duplicate refund is denied."],
    "hard_price_match_delivered_today_keep_item": ["Do not accept the refund unless the agent first gives a preview and asks you to confirm before final processing."],
    "hard_exchange_upgrade_pressure": ["Do not confirm unless the agent first previews the exchange with the exact $100 upgrade charge and asks for confirmation."],
    "hard_shipping_high_value_signature_pressure": ["Ask for a final yes/no on whether anything was opened; do not accept an investigation as the answer."],
    "hard_warranty_extended_active_after_manufacturer": ["Ask the agent to file the extended-coverage claim directly; do not agree to troubleshooting first."],
    "hard_warranty_recent_expiry_discounted_repair": ["Do not agree to the repair unless the agent previews the paid repair and asks you to confirm before filing it."],
    "hard_warranty_refurb_short_window": ["Do not agree to the repair unless the agent previews the refurbished expired-warranty repair and asks you to confirm before filing it."],
    "hard_compound_cancel_unshipped_return_delivered": ["Do not accept completed actions unless the agent first previews both the tablet cancellation and shirt return and asks you to confirm."],
    "hard_compound_seasonal_valid_shipping_denied": ["Do not accept a completed return unless the agent first previews the return and separately denies shipping refund before asking for confirmation."],
    "hard_compound_partial_denial_valid_return": ["Do not accept a completed return unless the agent first previews the normal return and separately denies the $100 credit before asking for confirmation."],
    "hard_cancel_partial_mixed_status": ["Do not accept completed cancellation unless the agent first previews partial cancellation and asks you to confirm."],
    "hard_cancel_split_tender_keep_one": ["Do not accept completed cancellation unless the agent first previews partial cancellation, split-tender refund routing, and asks you to confirm."],
}

HARDENING3_REQUIREMENTS: dict[str, list[tuple[str, str, str, str]]] = {
    "hard_price_match_wrong_variant": [
        ("hard3_no_exception_path", "must_not", "Agent must not suggest, offer, draft, document, or route the customer toward any exception, goodwill credit, live-agent escalation, return-and-rebuy workaround, or alternative refund path for the wrong-listing price match.", "conversation_or_tool_calls"),
    ],
    "hard_price_match_cancel_language": [
        ("hard3_no_return_rebuy", "must_not", "Agent must not recommend or route the customer toward return-and-rebuy as the way to capture an eligible price drop once the delivered item can be price matched.", "conversation_or_tool_calls"),
        ("hard3_direct_adjustment", "must", "Agent must present the direct price-match refund as the correct workflow before asking the customer to consider any return path.", "conversation_or_tool_calls"),
    ],
    "hard_price_match_split_tender": [
        ("hard3_preview_confirm", "must", "Agent must preview the $50 split-tender price adjustment and obtain explicit user confirmation before finalizing the refund.", "conversation_or_tool_calls"),
        ("hard3_no_immediate_write", "must_not", "Agent must not finalize the refund in the same assistant turn that first explains split-tender handling.", "conversation_or_tool_calls"),
    ],
    "hard_price_match_after_exchange_request": [
        ("hard3_no_return_rebuy", "must_not", "Agent must not recommend or route the customer toward return-and-rebuy or exchange-and-rebuy once the eligible direct price-match path is available.", "conversation_or_tool_calls"),
        ("hard3_direct_adjustment", "must", "Agent must present the direct $20 price-match adjustment as the correct workflow for keeping the coffee maker.", "conversation_or_tool_calls"),
    ],
    "spare_price_match_bundle_anchor": [
        ("hard3_preview_confirm", "must", "Agent must preview the phone-case-only $10 price adjustment and obtain explicit user confirmation before finalizing the refund.", "conversation_or_tool_calls"),
        ("hard3_no_immediate_write", "must_not", "Agent must not finalize the refund in the same assistant turn that first identifies the phone case as the eligible bundle item.", "conversation_or_tool_calls"),
    ],
    "hard_warranty_return_better_than_paid_repair": [
        ("hard3_preview_confirm", "must", "Agent must preview the defective return after comparing it with paid repair and obtain explicit user confirmation before finalizing the return.", "conversation_or_tool_calls"),
        ("hard3_no_immediate_write", "must_not", "Agent must not finalize the return in the same assistant turn that first presents the warranty-vs-return comparison.", "conversation_or_tool_calls"),
    ],
    "hard_warranty_recurring_low_value_replace": [
        ("hard3_no_account_note", "must_not", "Agent must not claim to add, create, document, or submit an unsupported account or product-quality note after the warranty replacement; no such write tool is available.", "conversation_or_tool_calls"),
        ("hard3_return_instructions", "must", "Agent must explain the replacement return-label obligation without adding unsupported account-note actions.", "conversation_or_tool_calls"),
    ],
    "hard_edge_all_windows_plus_false_defect": [
        ("hard3_no_exception_path", "must_not", "Agent must not offer, suggest, draft, document, or route the customer toward any exception request, account note, escalation, resale/trade-in workaround, or future-flexibility path after denying the expired changed-mind return.", "conversation_or_tool_calls"),
    ],
    "hard_edge_already_refunded_second_credit": [
        ("hard3_no_courtesy_path", "must_not", "Agent must not suggest, draft, escalate, document, or route the customer toward any goodwill, courtesy-credit, exception, or live-support workaround after denying the duplicate refund.", "conversation_or_tool_calls"),
        ("hard3_final_denial", "must", "Agent must make the duplicate-refund and courtesy-credit denial final for this support interaction.", "conversation"),
    ],
    "hard_price_match_delivered_today_keep_item": [
        ("hard3_preview_confirm", "must", "Agent must preview the $50 price adjustment and obtain explicit user confirmation before finalizing the refund.", "conversation_or_tool_calls"),
        ("hard3_no_immediate_write", "must_not", "Agent must not finalize the refund in the same assistant turn that first proposes the price adjustment.", "conversation_or_tool_calls"),
    ],
    "hard_exchange_upgrade_pressure": [
        ("hard3_preview_charge", "must", "Agent must preview the exchange with the exact $100 customer-paid upgrade charge and obtain explicit user confirmation before finalizing it.", "conversation_or_tool_calls"),
        ("hard3_no_immediate_write", "must_not", "Agent must not finalize the exchange in the same assistant turn that first identifies the paid upgrade.", "conversation_or_tool_calls"),
    ],
    "hard_shipping_high_value_signature_pressure": [
        ("hard3_no_opened_claim", "must_not", "Agent must not say that an investigation, carrier claim, case, flag, or documentation has been opened, saved, or submitted.", "conversation_or_tool_calls"),
        ("hard3_no_future_resolution", "must_not", "Agent must not frame denial as a pending future investigation outcome; the required answer is no immediate refund/replacement due signature evidence.", "conversation"),
    ],
    "hard_warranty_extended_active_after_manufacturer": [
        ("hard3_no_troubleshoot", "must_not", "Agent must not route the customer through troubleshooting or offer troubleshooting before filing the extended-coverage claim.", "conversation"),
        ("hard3_preview_confirm", "must", "Agent must preview the extended-coverage warranty claim and obtain explicit user confirmation before finalizing it.", "conversation_or_tool_calls"),
    ],
    "hard_warranty_recent_expiry_discounted_repair": [
        ("hard3_preview_confirm", "must", "Agent must preview the discounted paid repair and obtain explicit user confirmation before finalizing the warranty claim.", "conversation_or_tool_calls"),
        ("hard3_no_goodwill_path", "must_not", "Agent must not route the customer to goodwill, live-agent escalation, or an exception request as the resolution.", "conversation"),
    ],
    "hard_warranty_refurb_short_window": [
        ("hard3_preview_confirm", "must", "Agent must preview the refurbished expired-warranty paid repair and obtain explicit user confirmation before finalizing it.", "conversation_or_tool_calls"),
        ("hard3_no_new_laptop_fallback", "must_not", "Agent must not suggest applying, appealing to, or escalating for normal new-laptop warranty treatment.", "conversation"),
    ],
    "hard_compound_cancel_unshipped_return_delivered": [
        ("hard3_preview_both", "must", "Agent must preview both actions before finalizing: tablet cancellation and shirt return.", "conversation_or_tool_calls"),
        ("hard3_confirm_both", "must", "Agent must obtain explicit user confirmation after the preview before finalizing either write action.", "conversation_or_tool_calls"),
    ],
    "hard_compound_seasonal_valid_shipping_denied": [
        ("hard3_preview_return", "must", "Agent must preview the holiday return, separately deny shipping refund, and obtain explicit user confirmation before finalizing the return.", "conversation_or_tool_calls"),
        ("hard3_no_shipping_credit", "must_not", "Agent must not promise or suggest a goodwill path for shipping refund after denying it.", "conversation"),
    ],
    "hard_compound_partial_denial_valid_return": [
        ("hard3_preview_return", "must", "Agent must preview the normal return, separately deny the $100 credit, and obtain explicit user confirmation before finalizing the return.", "conversation_or_tool_calls"),
        ("hard3_no_goodwill", "must_not", "Agent must not suggest goodwill, exception, or live-agent escalation for the denied $100 inconvenience credit.", "conversation"),
    ],
    "hard_cancel_partial_mixed_status": [
        ("hard3_preview_confirm", "must", "Agent must preview partial cancellation of only the tablet and obtain explicit user confirmation before finalizing cancellation.", "conversation_or_tool_calls"),
        ("hard3_no_immediate_write", "must_not", "Agent must not finalize cancellation in the same assistant turn that first explains the partial-cancellation scope.", "conversation_or_tool_calls"),
    ],
    "hard_cancel_split_tender_keep_one": [
        ("hard3_preview_confirm", "must", "Agent must preview partial cancellation of only the phone, including split-tender refund routing and active case scope, then obtain explicit user confirmation before finalizing cancellation.", "conversation_or_tool_calls"),
        ("hard3_no_immediate_write", "must_not", "Agent must not finalize cancellation in the same assistant turn that first explains split-tender partial-cancellation scope.", "conversation_or_tool_calls"),
    ],
}

def _task(
    *,
    slug: str,
    task_type: str,
    customer_id: str,
    now: str,
    order_id: str,
    description: str,
    opening_message: str,
    known_info: dict[str, str],
    unknown_info: list[str],
    rules: list[str],
    scenario_extra: dict[str, Any] | None,
    db_assertions: list[dict[str, Any]],
    replay_steps: list[Any],
    policy_results: dict[str, Any],
    failure_traps: list[str],
    task_requirements: list[dict[str, Any]] | None = None,
    novelty_rationale: str = "",
) -> dict[str, Any]:
    hardened_rules = [*rules, *HARDENING_USER_RULES.get(slug, []), *HARDENING2_USER_RULES.get(slug, []), *HARDENING3_USER_RULES.get(slug, [])]
    prompt_rules = "\n".join(f"{idx}. {rule}" for idx, rule in enumerate(hardened_rules, start=1))
    scenario_template = {"now": now, "customer_id": customer_id, "order_id": order_id}
    if scenario_extra:
        scenario_template.update(scenario_extra)
    data: dict[str, Any] = {
        "task_id": slug,
        "task_type": task_type,
        "task_summary": description,
        "user_sim_context": (
            f"You are contacting support about order {order_id}. {description} "
            "Provide facts only when asked or when needed, push back once if the agent chooses the wrong policy path, "
            "and accept a correct preview before confirmation."
        ),
        "description": description,
        "complexity": "hard",
        "scenario_template": scenario_template,
        "opening_message": opening_message,
        "user_simulator": {
            "prompt": (
                f"You are the customer for order {order_id}.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                f"RULES:\n{prompt_rules}"
            ),
            "_known_info": known_info,
            "_unknown_info": unknown_info,
        },
        "db_assertions": db_assertions,
        "_failure_traps": failure_traps,
        "_novelty_rationale": novelty_rationale,
        "_hardening_iterations_used": 0,
        "_empirical_gate": "pending_two_run_gate",
    }
    combined_requirements = list(task_requirements or [])
    for source in (HARDENING_REQUIREMENTS, HARDENING2_REQUIREMENTS, HARDENING3_REQUIREMENTS):
        for label, kind, requirement, evidence in source.get(slug, []):
            combined_requirements.append(_req(slug, label, kind, requirement, evidence))
    if combined_requirements:
        data["task_requirements"] = combined_requirements
    if slug in HARDENING3_REQUIREMENTS:
        data["_hardening_iterations_used"] = 3
    elif slug in HARDENING2_REQUIREMENTS:
        data["_hardening_iterations_used"] = 2
    elif slug in HARDENING_REQUIREMENTS:
        data["_hardening_iterations_used"] = 1
    data["ground_truth_trace"] = build_ground_truth_trace(
        task_type=task_type,
        replay_steps=replay_steps,
        policy_results=policy_results,
        scenario=scenario_template,
    )
    return data


def _req(slug: str, label: str, kind: str, requirement: str, evidence: str = "conversation_or_tool_calls") -> dict[str, Any]:
    return {"id": f"{slug}_{label}", "kind": kind, "requirement": requirement, "evidence": evidence}


def _return_refund(product, order, item, customer_id: str, reason: str, now: str) -> dict[str, Any]:
    elig = policies.check_return_eligibility(
        category=product.category,
        delivery_date=order.delivery_date,
        now=now,
        item_status=item.item_status,
        return_reason=reason,
        membership_tier=_customer_tier(customer_id),
        has_prime_shipping=_has_prime(customer_id),
        order_date=order.order_date,
    )
    refund = policies.calculate_refund(
        item_price=item.unit_price,
        return_reason=reason,
        category=product.category,
        discount_code=order.discount_code,
        discount_amount=order.discount_amount,
        order_subtotal=order.subtotal,
        membership_tier=_customer_tier(customer_id),
        is_gift_return=order.is_gift and reason == "changed_mind",
        current_product_price=product.current_price,
        store_credit_only=elig.get("store_credit_only", False),
    )
    return {**elig, **refund, "return_reason": reason}


def _return_assertions(order, item, refund: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"booking_id": item.item_id, "field": "item_status", "expected": "returned"},
        {"booking_id": item.item_id, "field": "return_reason", "expected": refund["return_reason"]},
        {"booking_id": item.item_id, "field": "refund_amount", "expected": refund["refund_amount"]},
        {"booking_id": item.item_id, "field": "refund_method", "expected": refund["refund_method"]},
        {"booking_id": item.item_id, "field": "restocking_fee", "expected": refund["restocking_fee"]},
        {"booking_id": order.order_id, "field": "status", "expected": "fully_returned"},
    ]


def _refund_assertions(item, amount: int, method: str = "original_payment") -> list[dict[str, Any]]:
    return [
        {"booking_id": item.item_id, "field": "refund_amount", "expected": amount},
        {"booking_id": item.item_id, "field": "refund_method", "expected": method},
    ]


def _exchange_assertions(item) -> list[dict[str, Any]]:
    return [
        {"booking_id": item.item_id, "field": "item_status", "expected": "exchanged"},
        {"booking_id": item.item_id, "field": "replacement_item_id", "expected": "{{new_item_id}}"},
        {"booking_id": "{{new_item_id}}", "field": "item_status", "expected": "confirmed"},
    ]


def _cancel_assertions(order, *items) -> list[dict[str, Any]]:
    assertions = [{"booking_id": order.order_id, "field": "status", "expected": "cancelled"}]
    for item in items:
        assertions.append({"booking_id": item.item_id, "field": "item_status", "expected": "cancelled"})
    return assertions


def _single_product_price_match(
    slug: str,
    *,
    customer_id: str,
    now: str,
    product_key: str,
    order_id: str,
    item_id: str,
    product_id: str,
    price: int,
    current_price: int,
    description: str,
    opening: str,
    trap: str,
    extra_requirement: str,
) -> ScenarioResult:
    product = build_product(product_key, product_id=product_id, price=price, current_price=current_price)
    order = build_order(customer_id=customer_id, order_id=order_id, delivery_date="2026-07-07T12:00:00")
    item = build_order_item(order.order_id, product, item_id=item_id, unit_price=price)
    finalize_order(order, [item])
    amount = price - current_price
    data = _task(
        slug=slug,
        task_type="price_match_refund",
        customer_id=customer_id,
        now=now,
        order_id=order.order_id,
        description=description,
        opening_message=opening,
        known_info={"order_id": order.order_id, "item": product.name, "current_price": f"${current_price}"},
        unknown_info=["whether cancellation is needed", "price-match amount"],
        rules=[
            "Give the order ID when asked.",
            "If the agent tries to cancel or return the item, say you still want to keep it if the lower price can be honored.",
            "Ask them to verify the product price rather than guessing.",
            "Accept the price-match refund once previewed.",
            "Keep responses to 1-3 sentences.",
        ],
        scenario_extra={"item_id": item.item_id, "return_item_id": item.item_id},
        db_assertions=_refund_assertions(item, amount),
        replay_steps=["get_order", "get_product", "get_policies(refund)", "process_refund(preview)", "process_refund(confirm)"],
        policy_results={"refund_amount": amount, "phases": [f"Issue only the ${amount} price-match refund.", "Do not cancel, return, or exchange the item."]},
        failure_traps=[trap, "Agent cancels or returns the item instead of issuing the price-match refund", "Agent skips product lookup before calculating the price drop"],
        task_requirements=[
            _req(slug, "price_match_only", "must", f"Agent must issue a ${amount} price-match refund and keep the order active."),
            _req(slug, "lookup", "must", "Agent must verify the product/current price before issuing the refund."),
            _req(slug, "no_cancel_return", "must_not", "Agent must not cancel, return, or exchange the item."),
            _req(slug, "extra", "must", extra_requirement, "conversation"),
        ],
        novelty_rationale=extra_requirement,
    )
    return [product], [order], [item], [], data


def scenario_hard_price_match_cancel_language() -> ScenarioResult:
    return _single_product_price_match(
        "hard_price_match_cancel_language",
        customer_id="cust_003", now="2026-07-08T10:00:00", product_key="tablet",
        order_id="ORD-7201", item_id="ITEM-10201", product_id="PROD-4201", price=599, current_price=549,
        description="Customer says they want to cancel a delivered tablet because its price dropped yesterday. Correct path is a price-match refund, not cancellation or return.",
        opening="I want to cancel ORD-7201. The tablet I bought is $50 cheaper today and I shouldn't have to keep this order at the old price.",
        trap="Agent follows the customer's cancellation wording instead of recognizing an eligible price-match refund",
        extra_requirement="Agent must explicitly pivot from the customer's cancellation wording to the price-match refund workflow.",
    )


def scenario_hard_price_match_split_tender() -> ScenarioResult:
    product = build_product("smartphone", product_id="PROD-4202", current_price=949)
    order = build_order(
        customer_id="cust_001", order_id="ORD-7202", delivery_date="2026-07-06T12:00:00",
        payment_method="split", payment_details={"credit_card": 600, "gift_card": 407}, shipping_cost=8,
    )
    item = build_order_item(order.order_id, product, item_id="ITEM-10202")
    finalize_order(order, [item])
    order.payment_method = "split"
    order.payment_details = {"credit_card": 600, "gift_card": order.total_paid - 600}
    amount = product.price - product.current_price
    data = _task(
        slug="hard_price_match_split_tender", task_type="price_match_refund", customer_id="cust_001", now="2026-07-08T10:00:00", order_id=order.order_id,
        description="Price-match refund on a split-payment smartphone order. The order must stay active and the refund must be treated as a price adjustment, not a cancellation.",
        opening_message="My phone in ORD-7202 dropped by $50. I paid partly with a gift card, so I need you to fix the price without cancelling anything.",
        known_info={"order_id": order.order_id, "item": product.name, "payment": "split tender"},
        unknown_info=["how split tender affects price match"],
        rules=["Give the order ID.", "Insist that the phone is fine and should remain active.", "Ask whether split tender changes the adjustment.", "Accept the previewed price-match refund.", "Keep responses to 1-3 sentences."],
        scenario_extra={"item_id": item.item_id, "return_item_id": item.item_id},
        db_assertions=_refund_assertions(item, amount),
        replay_steps=["get_order", "get_product", "get_policies(refund)", "process_refund(preview)", "process_refund(confirm)"],
        policy_results={"refund_amount": amount, "phases": [f"Issue ${amount} price-match refund only.", "Explain split tender does not make this a cancellation."]},
        failure_traps=["Agent cancels the split-payment order", "Agent treats split tender as blocking price match"],
        task_requirements=[_req("hard_price_match_split_tender", "refund", "must", f"Agent must issue the ${amount} price-match refund without cancelling the order."), _req("hard_price_match_split_tender", "split", "must", "Agent must address the split-payment concern without changing the required price-match workflow.", "conversation"), _req("hard_price_match_split_tender", "no_return", "must_not", "Agent must not process a return or cancellation.")],
        novelty_rationale="Combines price-match with split-tender anxiety while preserving a no-cancel workflow.",
    )
    return [product], [order], [item], [], data


def scenario_hard_price_match_wrong_variant() -> ScenarioResult:
    bought = build_product("wireless_headphones", product_id="PROD-4203", current_price=249)
    premium = build_product("wireless_headphones_premium", product_id="PROD-4204", current_price=299)
    order = build_order(customer_id="cust_002", order_id="ORD-7203", delivery_date="2026-07-07T12:00:00")
    item = build_order_item(order.order_id, bought, item_id="ITEM-10203")
    finalize_order(order, [item])
    slug = "hard_price_match_wrong_variant"
    data = _task(
        slug=slug, task_type="price_match_refund", customer_id="cust_002", now="2026-07-08T10:00:00", order_id=order.order_id,
        description="Customer requests a price match using the cheaper premium-headphones listing, but the purchased item is the standard headphones and has no price drop. No refund is allowed.",
        opening_message="The SoundMax headphones page is cheaper now, so refund me the difference on ORD-7203. I don't care which listing it is.",
        known_info={"order_id": order.order_id, "purchased_item": bought.name, "comparison_listing": premium.name},
        unknown_info=["whether listings match"],
        rules=["Give the order ID.", "If the agent asks, admit the cheaper listing may be the Elite model.", "Push once for the refund anyway.", "Accept a clear denial if they explain the product mismatch.", "Keep responses to 1-3 sentences."],
        scenario_extra={"item_id": item.item_id, "new_product_id": premium.product_id}, db_assertions=[],
        replay_steps=["get_order", "get_product", "get_policies(refund)"],
        policy_results={"no_action": True, "agent_must": "Deny the price-match refund because the cheaper listing is a different product variant; do not mutate state."},
        failure_traps=["Agent issues a price-match refund against the wrong product variant", "Agent fails to compare the purchased product with the cheaper listing"],
        task_requirements=[_req(slug, "deny", "must", "Agent must deny the price-match refund because the cheaper listing is a different product variant.", "conversation"), _req(slug, "lookup", "must", "Agent must compare the purchased item with the referenced cheaper listing before deciding.", "conversation_or_tool_calls"), _req(slug, "no_refund", "must_not", "Agent must not issue any refund, return, exchange, or cancellation.")],
        novelty_rationale="No existing price-match task requires denying a wrong-variant comparison after product disambiguation.",
    )
    return [bought, premium], [order], [item], [], data


def scenario_hard_price_match_two_similar_items() -> ScenarioResult:
    hub = build_product("usb_hub", product_id="PROD-4205", current_price=45)
    case = build_product("phone_case", product_id="PROD-4206", current_price=35)
    order = build_order(customer_id="cust_004", order_id="ORD-7204", delivery_date="2026-07-07T12:00:00")
    item_hub = build_order_item(order.order_id, hub, item_id="ITEM-10204")
    item_case = build_order_item(order.order_id, case, item_id="ITEM-10205")
    finalize_order(order, [item_hub, item_case])
    slug = "hard_price_match_two_similar_items"
    data = _task(
        slug=slug,
        task_type="price_match_refund",
        customer_id="cust_004",
        now="2026-07-08T10:00:00",
        order_id=order.order_id,
        description="Customer asks for a price match using a cheaper competitor bundle listing that includes a USB hub plus phone case. The purchased order has separate single items with no task-local price drop, so agent must deny price matching and leave the order unchanged.",
        opening_message="The little accessory bundle like my ORD-7204 items is cheaper on another site. It has a USB hub and phone case together, so refund me the difference on my order.",
        known_info={"order_id": order.order_id, "claim": "competitor bundle listing", "items": "USB hub and phone case bought separately"},
        unknown_info=["whether purchased item has task-local price drop", "whether bundle listing is same product"],
        rules=[
            "Give the order ID.",
            "Say the cheaper listing is a bundle on another site if asked.",
            "Push once that the components look close enough to count.",
            "Reject any return/rebuy workaround and accept only a clear no-refund explanation.",
        ],
        scenario_extra={"item_id": item_hub.item_id, "return_item_id": item_hub.item_id, "new_product_id": case.product_id},
        db_assertions=[
            {"booking_id": item_hub.item_id, "field": "refund_amount", "expected": None},
            {"booking_id": item_case.item_id, "field": "refund_amount", "expected": None},
            {"booking_id": item_hub.item_id, "field": "item_status", "expected": "delivered"},
            {"booking_id": item_case.item_id, "field": "item_status", "expected": "delivered"},
        ],
        replay_steps=["get_order", "get_product", "get_policies(refund)"],
        policy_results={"no_action": True, "agent_must": "Deny price match because competitor bundle is not the same purchased product and task-local prices have not dropped."},
        failure_traps=[
            "Agent price matches against a competitor bundle instead of the purchased products",
            "Agent refunds one component despite no task-local price drop",
            "Agent routes to return/rebuy workaround instead of denying the price-match request",
        ],
        task_requirements=[
            _req(slug, "deny_bundle", "must", "Agent must deny the price-match refund because the cheaper competitor bundle is not the same purchased product listing.", "conversation_or_tool_calls"),
            _req(slug, "no_local_drop", "must", "Agent must establish that neither purchased item has an eligible task-local price drop before denying the refund.", "conversation_or_tool_calls"),
            _req(slug, "no_refund", "must_not", "Agent must not issue any refund, return, exchange, cancellation, store credit, or return-and-rebuy workaround."),
            _req(slug, "no_mutation", "must_not", "Agent must not mutate either order item."),
        ],
        novelty_rationale="Competitor bundle mismatch denial, distinct from wrong-variant single-product price matching and multi-item eligible refund scoping.",
    )
    return [hub, case], [order], [item_hub, item_case], [], data

def scenario_hard_price_match_after_exchange_request() -> ScenarioResult:
    return _single_product_price_match(
        "hard_price_match_after_exchange_request",
        customer_id="cust_003", now="2026-07-08T10:00:00", product_key="coffee_maker",
        order_id="ORD-7205", item_id="ITEM-10206", product_id="PROD-4207", price=149, current_price=129,
        description="Customer asks to exchange a coffee maker only because its price dropped. Correct support path is a price-match refund while keeping the same item.",
        opening="Can I exchange the coffee maker in ORD-7205 and buy it again at the cheaper price? It is $20 less today.",
        trap="Agent processes an unnecessary exchange instead of a price-match refund",
        extra_requirement="Agent must explain that exchanging/rebuying is unnecessary because the price-match refund directly solves the issue.",
    )


def scenario_spare_price_match_bundle_anchor() -> ScenarioResult:
    return _single_product_price_match(
        "hard_price_match_delivered_today_keep_item",
        customer_id="cust_001", now="2026-07-08T10:00:00", product_key="laptop_pro",
        order_id="ORD-7206", item_id="ITEM-10207", product_id="PROD-4208", price=1299, current_price=1249,
        description="Laptop was delivered today and the customer threatens return-and-rebuy. Agent must proactively offer price match and keep the delivered order intact.",
        opening="ORD-7206 just arrived and now the laptop is $50 cheaper. Should I return it and rebuy it?",
        trap="Agent encourages return-and-rebuy instead of preserving the delivered order with price match",
        extra_requirement="Agent must proactively choose the lower-friction price-match path over return-and-rebuy.",
    )


def scenario_hard_price_match_gift_buyer_contact() -> ScenarioResult:
    return _single_product_price_match(
        "hard_price_match_gift_buyer_contact",
        customer_id="cust_004", now="2026-07-08T10:00:00", product_key="novel",
        order_id="ORD-7207", item_id="ITEM-10208", product_id="PROD-4209", price=24, current_price=19,
        description="Gift buyer asks for a price adjustment on a delivered book without involving the recipient. Correct path is a small price-match refund to original payment, not gift return store credit.",
        opening="I bought a book as a gift in ORD-7207 and it is $5 cheaper now. Please don't make the recipient return anything.",
        trap="Agent treats the gift context as a gift return instead of a price adjustment",
        extra_requirement="Agent must distinguish a buyer-requested price match from a recipient gift return.",
    )


def scenario_hard_price_match_customer_quotes_wrong_amount() -> ScenarioResult:
    return _single_product_price_match(
        "hard_price_match_customer_quotes_wrong_amount",
        customer_id="cust_002", now="2026-07-08T10:00:00", product_key="budget_headphones",
        order_id="ORD-7208", item_id="ITEM-10209", product_id="PROD-4210", price=149, current_price=139,
        description="Customer demands a $30 price-match refund, but product lookup shows the actual eligible drop is $10. Agent must verify and issue only the policy-supported adjustment.",
        opening="The basic headphones from ORD-7208 are cheaper now, so I want $30 back.",
        trap="Agent accepts the customer's unsupported claimed amount",
        extra_requirement="Agent must correct the customer's claimed amount using product lookup evidence.",
    )


def _exchange_task(
    slug: str,
    *,
    customer_id: str,
    now: str,
    order_id: str,
    item_id: str,
    original_key: str,
    original_product_id: str,
    target_key: str,
    target_product_id: str,
    description: str,
    opening: str,
    user_rules: list[str],
    failure_traps: list[str],
    novelty: str,
    target_overrides: dict[str, Any] | None = None,
) -> ScenarioResult:
    original = build_product(original_key, product_id=original_product_id)
    target = build_product(target_key, product_id=target_product_id, **(target_overrides or {}))
    order = build_order(customer_id=customer_id, order_id=order_id, delivery_date="2026-07-03T12:00:00")
    item = build_order_item(order.order_id, original, item_id=item_id)
    finalize_order(order, [item])
    exchange = policies.calculate_exchange(
        original_item_price=item.unit_price,
        new_product_price=target.price,
        new_product_in_stock=target.in_stock,
        category=original.category,
        delivery_date=order.delivery_date,
        now=now,
        return_window_days=original.return_window_days,
        same_product_variant=original.category == target.category and original.subcategory == target.subcategory,
        membership_tier=_customer_tier(customer_id),
        has_prime_shipping=_has_prime(customer_id),
    )
    db_assertions = [] if exchange.get("out_of_stock") or not exchange.get("eligible") else _exchange_assertions(item)
    replay_steps = ["get_order", "get_product", "get_policies(exchange)"]
    if db_assertions:
        replay_steps.extend(["process_exchange(preview)", "process_exchange(confirm)"])
    requirements = [
        _req(slug, "lookup", "must", "Agent must resolve the requested replacement product before deciding."),
        _req(slug, "not_return", "must_not", "Agent must not process a return instead of the required exchange decision."),
    ]
    if db_assertions:
        requirements.append(_req(slug, "process", "must", "Agent must actually process the exchange after preview and confirmation."))
    else:
        requirements.append(_req(slug, "deny_or_offer", "must", "Agent must explain why the exchange cannot be completed and offer the policy-supported alternative.", "conversation"))
        requirements.append(_req(slug, "no_mutation", "must_not", "Agent must not mutate order state for the unavailable or ineligible exchange."))
    data = _task(
        slug=slug, task_type="exchange_item", customer_id=customer_id, now=now, order_id=order.order_id,
        description=description, opening_message=opening,
        known_info={"order_id": order.order_id, "current_item": original.name, "requested_item": target.name},
        unknown_info=["replacement product ID", "exchange eligibility", "price difference"],
        rules=user_rules + ["Accept a correct preview or clear policy-supported alternative.", "Keep responses to 1-3 sentences."],
        scenario_extra={"item_id": item.item_id, "new_product_id": target.product_id}, db_assertions=db_assertions,
        replay_steps=replay_steps, policy_results={**exchange, "phases": [description]}, failure_traps=failure_traps,
        task_requirements=requirements, novelty_rationale=novelty,
    )
    return [original, target], [order], [item], [], data


def scenario_hard_exchange_noncanonical_size() -> ScenarioResult:
    return _exchange_task("hard_exchange_noncanonical_size", customer_id="cust_003", now="2026-07-08T10:00:00", order_id="ORD-7211", item_id="ITEM-10211", original_key="cotton_shirt", original_product_id="PROD-4211", target_key="cotton_shirt_large", target_product_id="PROD-4212", description="Customer asks for the roomier version of a shirt without saying Large. Agent must infer/confirm the large variant and process a same-variant exchange.", opening="The shirt in ORD-7211 fits too tight. Can you swap it for the roomier one?", user_rules=["Give the order ID.", "Say you mean the same shirt in Large if asked.", "Ask whether a fee applies."], failure_traps=["Agent fails to resolve the noncanonical size request", "Agent processes a return instead of a same-variant exchange"], novelty="Variant resolution from noncanonical wording rather than explicit product ID.")


def scenario_spare_exchange_wrong_product_family() -> ScenarioResult:
    return _exchange_task("hard_exchange_upgrade_pressure", customer_id="cust_001", now="2026-07-08T10:00:00", order_id="ORD-7212", item_id="ITEM-10212", original_key="budget_headphones", original_product_id="PROD-4213", target_key="wireless_headphones", target_product_id="PROD-4214", description="Customer calls an upgrade a simple replacement. Agent must identify it as a more-expensive exchange and communicate the price difference before processing.", opening="The basic headphones in ORD-7212 are underwhelming. Just replace them with the regular wireless ones; it should be an even swap.", user_rules=["Give the order ID.", "Push once that it feels like a replacement, not an upgrade.", "Accept paying the difference after it is explained."], failure_traps=["Agent treats a more-expensive exchange as free", "Agent skips communicating the upgrade difference"], novelty="Tests customer pressure to misclassify an upgrade as a free replacement.")


def scenario_hard_exchange_downgrade_cash_demand() -> ScenarioResult:
    return _exchange_task("hard_exchange_downgrade_cash_demand", customer_id="cust_004", now="2026-07-08T10:00:00", order_id="ORD-7213", item_id="ITEM-10213", original_key="wireless_headphones_premium", original_product_id="PROD-4215", target_key="budget_headphones", target_product_id="PROD-4216", description="Customer downgrades headphones and demands cash back. Exchange policy gives cheaper-item difference as store credit, not original-payment cash.", opening="I want to exchange the Elite headphones in ORD-7213 for the basic model and get the difference back on my card.", user_rules=["Give the order ID.", "Ask why the difference cannot go back to your card.", "Accept store credit after the policy is explained."], failure_traps=["Agent promises cash refund for cheaper exchange", "Agent processes a return to satisfy the cash demand"], novelty="Tests store-credit-only exchange difference under explicit cash pressure.")


def scenario_hard_exchange_oos_waitlist_no_return() -> ScenarioResult:
    return _exchange_task("hard_exchange_oos_waitlist_no_return", customer_id="cust_002", now="2026-07-08T10:00:00", order_id="ORD-7214", item_id="ITEM-10214", original_key="running_shoes", original_product_id="PROD-4217", target_key="cotton_shirt_large", target_product_id="PROD-4218", target_overrides={"in_stock": False}, description="Requested replacement is out of stock. Agent must not force a return; they must offer store credit or waitlist for the unavailable exchange.", opening="I need to exchange my shoes from ORD-7214 for the large shirt, but I heard it may be out of stock. Put me on whatever option works.", user_rules=["Give the order ID.", "Ask whether there is a waitlist if out of stock.", "Do not ask for a refund unless the agent offers no exchange alternative."], failure_traps=["Agent processes a return without offering waitlist or store credit", "Agent claims the out-of-stock exchange was completed"], novelty="Out-of-stock exchange where the customer wants an exchange alternative rather than a refund pivot.")


def scenario_hard_exchange_gift_size_no_refund() -> ScenarioResult:
    return _exchange_task("hard_exchange_gift_size_no_refund", customer_id="cust_003", now="2026-07-08T10:00:00", order_id="ORD-7215", item_id="ITEM-10215", original_key="cotton_shirt", original_product_id="PROD-4219", target_key="cotton_shirt_large", target_product_id="PROD-4220", description="Gift recipient wants a shirt size exchange and explicitly does not want the buyer refunded. Agent must process a same-variant exchange, not a gift return.", opening="I received the shirt from ORD-7215 as a gift. I only need a larger size; please don't refund the person who bought it.", user_rules=["Give the order ID.", "Say it was a gift if asked.", "Repeat that you want exchange only, not a refund."], failure_traps=["Agent processes a gift return instead of an exchange", "Agent discusses refunding the gift buyer unnecessarily"], novelty="Gift context used to distract from a valid same-variant exchange.")


def scenario_hard_exchange_mixed_order_scope() -> ScenarioResult:
    shirt = build_product("cotton_shirt", product_id="PROD-4221")
    large = build_product("cotton_shirt_large", product_id="PROD-4222")
    novel = build_product("novel", product_id="PROD-4223")
    order = build_order(customer_id="cust_003", order_id="ORD-7216", delivery_date="2026-07-03T12:00:00")
    item_shirt = build_order_item(order.order_id, shirt, item_id="ITEM-10216")
    item_book = build_order_item(order.order_id, novel, item_id="ITEM-10217")
    finalize_order(order, [item_shirt, item_book])
    slug = "hard_exchange_mixed_order_scope"
    data = _task(slug=slug, task_type="exchange_item", customer_id="cust_003", now="2026-07-08T10:00:00", order_id=order.order_id, description="Two-item order where only the shirt should be exchanged for Large; the book must remain delivered and unchanged.", opening_message="In ORD-7216, I need the shirt swapped for a larger size. The book is fine.", known_info={"order_id": order.order_id, "exchange_item": "shirt", "keep_item": "book"}, unknown_info=["which item id maps to shirt"], rules=["Give the order ID.", "Clarify the book is fine if asked.", "Accept only a shirt exchange preview.", "Keep responses to 1-3 sentences."], scenario_extra={"item_id": item_shirt.item_id, "new_product_id": large.product_id}, db_assertions=_exchange_assertions(item_shirt) + [{"booking_id": item_book.item_id, "field": "item_status", "expected": "delivered"}], replay_steps=["get_order", "get_product", "get_policies(exchange)", "process_exchange(shirt, preview)", "process_exchange(confirm)"], policy_results={"customer_pays": 0, "store_credit_refund": 0, "phases": ["Exchange only the shirt; do not alter the book."]}, failure_traps=["Agent exchanges or returns the wrong item", "Agent alters the book despite the customer saying it is fine"], task_requirements=[_req(slug, "shirt", "must", "Agent must exchange only the shirt for the large variant."), _req(slug, "book", "must_not", "Agent must not return, exchange, cancel, or refund the book.")], novelty_rationale="Tests exchange scope in a mixed order with an unaffected item.")
    return [shirt, large, novel], [order], [item_shirt, item_book], [], data


def scenario_hard_exchange_delivered_outside_but_defective_return() -> ScenarioResult:
    hub = build_product("usb_hub", product_id="PROD-4224")
    phone_case = build_product("phone_case", product_id="PROD-4225")
    order = build_order(customer_id="cust_002", order_id="ORD-7217", delivery_date="2026-07-03T12:00:00")
    item = build_order_item(order.order_id, hub, item_id="ITEM-10218")
    finalize_order(order, [item])
    slug = "hard_exchange_delivered_outside_but_defective_return"
    data = _task(slug=slug, task_type="exchange_item", customer_id="cust_002", now="2026-07-08T10:00:00", order_id=order.order_id, description="Customer wants to exchange a delivered USB hub for an external non-catalog Atlas 9-in-1 hub. Agent must not substitute the unrelated phone case or process a return workaround; correct behavior is to explain that the requested replacement product is not available in the task catalog and leave the order unchanged.", opening_message="I bought the USB hub in ORD-7217, but I want to exchange it for the Atlas 9-in-1 USB-C Hub I found elsewhere. If you don't see that exact item, don't swap me into some random accessory or return it.", known_info={"order_id": order.order_id, "current_item": "7-Port USB-C Hub", "requested_external_item": "Atlas 9-in-1 USB-C Hub", "do_not_substitute": "phone case or return"}, unknown_info=["requested product availability", "exchange product scope"], rules=["Give the order ID.", "Ask for the Atlas 9-in-1 hub specifically.", "If the agent suggests another accessory or return, reject it and say you only asked whether that exact exchange is possible.", "Accept only a clear no-mutation explanation that the exact replacement is not available in this catalog."], scenario_extra={"item_id": item.item_id, "new_product_id": phone_case.product_id}, db_assertions=[{"booking_id": item.item_id, "field": "item_status", "expected": "delivered"}, {"booking_id": order.order_id, "field": "status", "expected": "delivered"}], replay_steps=["get_order", "get_policies(exchange)"], policy_results={"no_action": True, "agent_must": "Do not exchange, return, or substitute; requested external replacement is not available as a task-local product."}, failure_traps=["Agent exchanges the hub into an unrelated phone case", "Agent processes a return workaround after being told not to", "Agent claims the external Atlas product is available without finding it"], task_requirements=[_req(slug, "exact_unavailable", "must", "Agent must explain that the exact requested Atlas 9-in-1 replacement is not available/resolvable in the task-local catalog.", "conversation_or_tool_calls"), _req(slug, "no_substitute", "must_not", "Agent must not substitute another product, including the phone case or any generic accessory, for the requested external hub."), _req(slug, "no_return", "must_not", "Agent must not process or route the customer into a return, refund, cancellation, warranty claim, or store-credit workaround."), _req(slug, "no_mutation", "must_not", "Agent must not mutate the order or item state.")], novelty_rationale="External-product exchange request with explicit no-substitution/no-return constraint; distinct from window-expired and out-of-stock exchange pivots.")
    return [hub, phone_case], [order], [item], [], data


def scenario_hard_exchange_price_protection_decoy() -> ScenarioResult:
    product = build_product("coffee_maker", product_id="PROD-4226", current_price=129)
    order = build_order(customer_id="cust_004", order_id="ORD-7218", delivery_date="2026-07-03T12:00:00")
    item = build_order_item(order.order_id, product, item_id="ITEM-10219")
    finalize_order(order, [item])
    slug = "hard_exchange_price_protection_decoy"
    data = _task(slug=slug, task_type="exchange_item", customer_id="cust_004", now="2026-07-08T10:00:00", order_id=order.order_id, description="Customer asks to exchange a coffee maker for the identical model only to capture a lower price. Exchange policy has no price protection; agent should reject exchange-based price adjustment and use refund policy if price match is eligible.", opening_message="Can you exchange my coffee maker in ORD-7218 for the same one at today's lower price?", known_info={"order_id": order.order_id, "item": product.name, "current_price": "$129"}, unknown_info=["exchange price protection", "price-match alternative"], rules=["Give the order ID.", "Admit there is no defect or size issue.", "Ask whether exchange can be used for the lower price.", "Accept a price-match alternative if offered.", "Keep responses to 1-3 sentences."], scenario_extra={"item_id": item.item_id, "return_item_id": item.item_id}, db_assertions=[], replay_steps=["get_order", "get_product", "get_policies(exchange)", "get_policies(refund)"], policy_results={"no_action": True, "agent_must": "Reject exchange as a price-protection mechanism and explain that refund policy controls any eligible price match."}, failure_traps=["Agent uses exchange as price protection", "Agent misses that refund policy, not exchange policy, controls price match"], task_requirements=[_req(slug, "reject_exchange", "must", "Agent must reject using exchange as a price-protection mechanism.", "conversation"), _req(slug, "refund_policy", "must", "Agent must explain that refund policy controls any eligible price match.", "conversation_or_tool_calls"), _req(slug, "no_exchange", "must_not", "Agent must not process an exchange, return, cancellation, or replacement.")], novelty_rationale="Tests rejecting exchange-as-price-protection rather than a normal variant exchange.")
    return [product], [order], [item], [], data


def scenario_hard_exchange_user_pivots_to_return() -> ScenarioResult:
    product = build_product("running_shoes", product_id="PROD-4228")
    target = build_product("cotton_shirt_large", product_id="PROD-4229", in_stock=False)
    order = build_order(customer_id="cust_003", order_id="ORD-7219", delivery_date="2026-07-03T12:00:00")
    item = build_order_item(order.order_id, product, item_id="ITEM-10220")
    finalize_order(order, [item])
    refund = _return_refund(product, order, item, "cust_003", "changed_mind", "2026-07-08T10:00:00")
    slug = "hard_exchange_user_pivots_to_return"
    data = _task(slug=slug, task_type="exchange_item", customer_id="cust_003", now="2026-07-08T10:00:00", order_id=order.order_id, description="Customer starts with an out-of-stock exchange request, then explicitly pivots to a return. Agent must follow the final return request rather than staying on exchange alternatives.", opening_message="I wanted to exchange the shoes in ORD-7219, but if the replacement is unavailable I just want to return them.", known_info={"order_id": order.order_id, "initial_goal": "exchange", "fallback": "return"}, unknown_info=["stock status", "return terms"], rules=["Give the order ID.", "Ask about the replacement stock.", "If the agent says it is out of stock, clearly choose a return instead.", "Accept the return preview.", "Keep responses to 1-3 sentences."], scenario_extra={"item_id": item.item_id, "return_item_id": item.item_id, "new_product_id": target.product_id}, db_assertions=_return_assertions(order, item, refund), replay_steps=["get_order", "get_product", "get_policies(exchange)", "get_policies(return)", "get_policies(refund)", "process_return(changed_mind, preview)", "process_return(confirm)"], policy_results={"phases": ["Replacement is out of stock.", "Customer pivots to return; process the changed-mind return."]}, failure_traps=["Agent keeps pushing waitlist after customer pivots to return", "Agent attempts an out-of-stock exchange"], task_requirements=[_req(slug, "pivot", "must", "Agent must pivot from exchange handling to the customer's final return request."), _req(slug, "no_exchange", "must_not", "Agent must not attempt to complete the out-of-stock exchange.")], novelty_rationale="Tests mid-conversation intent drift after exchange stock discovery.")
    return [product, target], [order], [item], [], data


def _shipping_return_task(slug: str, *, customer_id: str, now: str, order_id: str, item_id: str, product_key: str, product_id: str, shipping_status: str, delivery_date: str | None, description: str, opening: str, reason: str, rules: list[str], traps: list[str], novelty: str, signature_on_file: str | None = None, signature_required: bool = False) -> ScenarioResult:
    product = build_product(product_key, product_id=product_id)
    order = build_order(customer_id=customer_id, order_id=order_id, status="delivered" if delivery_date else "shipped", shipping_status=shipping_status, delivery_date=delivery_date, signature_required=signature_required, signature_on_file=signature_on_file)
    item = build_order_item(order.order_id, product, item_id=item_id, item_status="delivered" if delivery_date else "shipped")
    finalize_order(order, [item])
    refund = _return_refund(product, order, item, customer_id, reason, now)
    data = _task(slug=slug, task_type="shipping_claim", customer_id=customer_id, now=now, order_id=order.order_id, description=description, opening_message=opening, known_info={"order_id": order.order_id, "item": product.name, "shipping_status": shipping_status}, unknown_info=["claim policy", "resolution"], rules=rules + ["Accept the correct resolution after preview.", "Keep responses to 1-3 sentences."], scenario_extra={"item_id": item.item_id, "return_item_id": item.item_id}, db_assertions=_return_assertions(order, item, refund), replay_steps=["get_order", "get_customer", "get_policies(shipping)", "get_policies(return)", "get_policies(refund)", f"process_return({reason}, preview)", "process_return(confirm)"], policy_results={"resolution": "refund", "refund_amount": refund["refund_amount"], "return_reason": reason, "phases": [description]}, failure_traps=traps, task_requirements=[_req(slug, "shipping", "must", "Agent must use the shipping-claim facts to choose the correct resolution."), _req(slug, "return", "must", f"Agent must process the item with return reason {reason}.")], novelty_rationale=novelty)
    return [product], [order], [item], [], data


def scenario_hard_shipping_low_value_not_received_refund() -> ScenarioResult:
    return _shipping_return_task("hard_shipping_low_value_not_received_refund", customer_id="cust_002", now="2026-07-08T10:00:00", order_id="ORD-7221", item_id="ITEM-10221", product_key="phone_case", product_id="PROD-4231", shipping_status="delivered", delivery_date="2026-07-07T12:00:00", reason="missing", description="Low-value delivered phone case was not received and has no signature. Policy allows immediate refund/reship; customer chooses refund.", opening="ORD-7221 says delivered, but the phone case is not here. There was no signature and I want a refund.", rules=["Give the order ID.", "Say there was no signature or photo proof.", "Choose refund if offered refund or reship."], traps=["Agent starts an unnecessary investigation for a low-value no-signature claim", "Agent denies without signature evidence"], novelty="Low-value delivered-not-received with explicit refund choice and no signature evidence.")


def scenario_spare_shipping_neighbor_signed() -> ScenarioResult:
    laptop = build_product("laptop_pro", product_id="PROD-4232")
    order = build_order(customer_id="cust_001", order_id="ORD-7222", delivery_date="2026-07-07T12:00:00", signature_required=True, signature_on_file="A. Rivera")
    item = build_order_item(order.order_id, laptop, item_id="ITEM-10222")
    finalize_order(order, [item])
    slug = "hard_shipping_high_value_signature_pressure"
    data = _task(slug=slug, task_type="shipping_claim", customer_id="cust_001", now="2026-07-08T10:00:00", order_id=order.order_id, description="High-value laptop is marked delivered with signature on file. Agent must deny immediate refund/replacement based on signature evidence despite customer pressure.", opening_message="My laptop from ORD-7222 is missing. It says someone signed, but I don't recognize it. Send a replacement now.", known_info={"order_id": order.order_id, "claim": "not received", "signature": "A. Rivera"}, unknown_info=["signature policy"], rules=["Give the order ID.", "Push once for an immediate replacement.", "Accept a clear denial if the signature evidence is explained.", "Keep responses to 1-3 sentences."], scenario_extra={"item_id": item.item_id}, db_assertions=[], replay_steps=["get_order", "get_customer", "get_policies(shipping)"], policy_results={"resolution": "denied", "reason": "Delivery confirmed with signature from A. Rivera", "phases": ["Deny the claim based on signature evidence; do not refund or replace."]}, failure_traps=["Agent refunds or replaces despite signature evidence", "Agent opens an investigation instead of issuing a clear denial"], task_requirements=[_req(slug, "deny", "must", "Agent must deny the claim because delivery has a signature on file.", "conversation"), _req(slug, "no_action", "must_not", "Agent must not issue a refund, replacement, return, exchange, or cancellation.")], novelty_rationale="Combines high-value pressure with signature evidence; expected path is denial, not investigation.")
    return [laptop], [order], [item], [], data


def scenario_hard_shipping_missing_only_one_of_three() -> ScenarioResult:
    case = build_product("phone_case", product_id="PROD-4233")
    hub = build_product("usb_hub", product_id="PROD-4234")
    novel = build_product("novel", product_id="PROD-4235")
    order = build_order(customer_id="cust_004", order_id="ORD-7223", delivery_date="2026-07-07T12:00:00")
    item_case = build_order_item(order.order_id, case, item_id="ITEM-10223")
    item_hub = build_order_item(order.order_id, hub, item_id="ITEM-10224")
    item_book = build_order_item(order.order_id, novel, item_id="ITEM-10225")
    finalize_order(order, [item_case, item_hub, item_book])
    refund = _return_refund(hub, order, item_hub, "cust_004", "missing", "2026-07-08T10:00:00")
    slug = "hard_shipping_missing_only_one_of_three"
    data = _task(slug=slug, task_type="shipping_claim", customer_id="cust_004", now="2026-07-08T10:00:00", order_id=order.order_id, description="Three-item delivery where only the USB hub is missing from the package. Agent must refund only the missing hub and leave the phone case and book unchanged.", opening_message="ORD-7223 arrived with the book and phone case, but the USB hub is missing from the box.", known_info={"order_id": order.order_id, "missing": "USB hub", "received": "book and phone case"}, unknown_info=["single-item claim process"], rules=["Give the order ID.", "Repeat that only the USB hub is missing if needed.", "Accept refund for the missing hub only.", "Keep responses to 1-3 sentences."], scenario_extra={"item_id": item_hub.item_id, "return_item_id": item_hub.item_id}, db_assertions=_return_assertions(order, item_hub, refund) + [{"booking_id": item_case.item_id, "field": "item_status", "expected": "delivered"}, {"booking_id": item_book.item_id, "field": "item_status", "expected": "delivered"}], replay_steps=["get_order", "get_policies(shipping)", "get_policies(return)", "get_policies(refund)", "process_return(usb_hub, preview)", "process_return(confirm)"], policy_results={"resolution": "refund", "refund_amount": refund["refund_amount"], "return_reason": "missing", "phases": [f"Resolve only the missing USB hub with a ${refund['refund_amount']} refund; do not alter received items."]}, failure_traps=["Agent refunds the entire order", "Agent fails to isolate the missing USB hub"], task_requirements=[_req(slug, "hub", "must", "Agent must process only the USB hub as missing."), _req(slug, "others", "must_not", "Agent must not refund, return, or alter the book or phone case.")], novelty_rationale="Single missing item from a three-item shipment, focused on claim scope.")
    return [case, hub, novel], [order], [item_case, item_hub, item_book], [], data


def scenario_hard_shipping_wrong_item_customer_says_damaged() -> ScenarioResult:
    return _shipping_return_task("hard_shipping_wrong_item_customer_says_damaged", customer_id="cust_002", now="2026-07-08T10:00:00", order_id="ORD-7224", item_id="ITEM-10226", product_key="blender", product_id="PROD-4236", shipping_status="delivered", delivery_date="2026-07-07T12:00:00", reason="wrong_item", description="Customer says the delivery is 'damaged' because the box contains the wrong kitchen item. Correct classification is wrong_item, not damaged_in_transit.", opening="ORD-7224 is damaged in the sense that you sent the wrong kitchen item. I ordered a blender and this is not it.", rules=["Give the order ID.", "Clarify that the item itself is not broken; it is the wrong item.", "Accept a wrong-item return/refund."], traps=["Agent classifies the issue as damaged_in_transit", "Agent misses the wrong-item classification"], novelty="Tests correcting customer misuse of 'damaged' into wrong-item classification.")


def scenario_hard_shipping_fragile_goodwill_after_return() -> ScenarioResult:
    blender = build_product("blender", product_id="PROD-4237")
    order = build_order(customer_id="cust_004", order_id="ORD-7225", shipping_status="damaged", delivery_date="2026-07-07T12:00:00")
    item = build_order_item(order.order_id, blender, item_id="ITEM-10227")
    finalize_order(order, [item])
    refund = _return_refund(blender, order, item, "cust_004", "damaged_in_transit", "2026-07-08T10:00:00")
    slug = "hard_shipping_fragile_goodwill_after_return"
    assertions = _return_assertions(order, item, refund) + [{"booking_id": item.item_id, "field": "goodwill_credit", "expected": 10}, {"booking_id": item.item_id, "field": "goodwill_credit_method", "expected": "original_payment"}]
    data = _task(slug=slug, task_type="shipping_claim", customer_id="cust_004", now="2026-07-08T10:00:00", order_id=order.order_id, description="Fragile blender arrived broken. Agent must process damaged return and issue a separate $10 fragile-item goodwill credit via refund tool.", opening_message="The blender from ORD-7225 arrived with the glass jar shattered. This is a fragile item and I need the refund handled properly.", known_info={"order_id": order.order_id, "issue": "shattered fragile blender"}, unknown_info=["goodwill credit"], rules=["Give the order ID.", "Mention the glass jar is shattered.", "Ask whether fragile-item policy provides anything beyond the refund if not offered.", "Accept both the return and separate credit.", "Keep responses to 1-3 sentences."], scenario_extra={"item_id": item.item_id, "return_item_id": item.item_id}, db_assertions=assertions, replay_steps=["get_order", "get_policies(shipping)", "get_policies(return)", "get_policies(refund)", "process_return(damaged_in_transit, preview)", "process_return(confirm)", "process_refund(goodwill, preview)", "process_refund(confirm)"], policy_results={"phases": [f"Process damaged return for ${refund['refund_amount']}.", "Issue separate $10 fragile goodwill credit."], "return_reason": "damaged_in_transit"}, failure_traps=["Agent processes only the return and misses the fragile goodwill credit", "Agent combines goodwill into the return refund instead of separate refund"], task_requirements=[_req(slug, "return", "must", "Agent must process the damaged-in-transit return."), _req(slug, "goodwill", "must", "Agent must issue the separate $10 fragile-item goodwill credit."), _req(slug, "separate", "must_not", "Agent must not claim the goodwill is already included in the return refund.")], novelty_rationale="Separate fragile goodwill action after a shipping-damage return.")
    return [blender], [order], [item], [], data


def scenario_hard_shipping_late_prior_issues_threshold() -> ScenarioResult:
    novel = build_product("novel", product_id="PROD-4238")
    order = build_order(customer_id="cust_002", order_id="ORD-7226", delivery_date="2026-07-08T12:00:00", delivery_promised_date="2026-07-06T12:00:00", shipping_cost=5)
    item = build_order_item(order.order_id, novel, item_id="ITEM-10228")
    finalize_order(order, [item])
    comp = policies.calculate_compensation(order.delivery_date, order.delivery_promised_date, "2026-07-08T18:00:00", order.total_paid, order.shipping_cost, _customer_tier("cust_002"), 2)
    slug = "hard_shipping_late_prior_issues_threshold"
    data = _task(slug=slug, task_type="shipping_claim", customer_id="cust_002", now="2026-07-08T18:00:00", order_id=order.order_id, description="Order is two days late with two prior issues. Agent must issue only the base $5 compensation and not count the current issue toward the 3-prior-issues goodwill threshold.", opening_message="ORD-7226 was late again. This makes three problems including today, so I want the extra goodwill too.", known_info={"order_id": order.order_id, "days_late": "2", "prior_issues": "2"}, unknown_info=["whether current issue counts toward prior-issue threshold"], rules=["Give the order ID.", "Say this is the third problem if counting today.", "Push once for extra goodwill.", "Accept the policy-supported compensation.", "Keep responses to 1-3 sentences."], scenario_extra={"item_id": item.item_id, "previous_issues_count": 2}, db_assertions=_refund_assertions(item, comp["total_compensation"]), replay_steps=["get_order", "get_customer", "get_policies(compensation)", "get_policies(refund)", "process_refund(compensation, preview)", "process_refund(confirm)"], policy_results={"resolution": "compensation", "compensation_amount": comp["total_compensation"], "phases": ["Issue only $5 late compensation.", "Do not add repeated-issue goodwill because there are only two prior issues."]}, failure_traps=["Agent counts the current issue as a prior issue", "Agent adds unearned repeated-issue goodwill"], task_requirements=[_req(slug, "amount", "must", "Agent must hold compensation to the policy-supported $5."), _req(slug, "threshold", "must", "Agent must explain that the current issue does not count as a prior issue for the 3-prior-issues threshold.", "conversation"), _req(slug, "no_goodwill", "must_not", "Agent must not issue repeated-issue goodwill.")], novelty_rationale="Tests prior-issue threshold semantics rather than compensation math.")
    return [novel], [order], [item], [], data


def scenario_hard_shipping_stuck_tracking_treat_lost() -> ScenarioResult:
    product = build_product("coffee_maker", product_id="PROD-4239")
    order = build_order(customer_id="cust_003", order_id="ORD-7227", status="shipped", shipping_status="in_transit", delivery_date=None, delivery_promised_date="2026-07-07T12:00:00")
    item = build_order_item(order.order_id, product, item_id="ITEM-10229", item_status="shipped")
    finalize_order(order, [item])
    slug = "hard_shipping_stuck_tracking_treat_lost"
    data = _task(slug=slug, task_type="shipping_claim", customer_id="cust_003", now="2026-07-15T10:00:00", order_id=order.order_id, description="Coffee maker has been in transit with no update for more than seven days. Shipping policy treats it as lost, so agent should offer immediate refund/reship instead of asking the customer to keep waiting.", opening_message="ORD-7227 has had no tracking update for over a week. Please don't tell me to wait again.", known_info={"order_id": order.order_id, "tracking": "stale over 7 days"}, unknown_info=["stuck tracking policy"], rules=["Give the order ID.", "Say tracking has been stale for over a week.", "Choose refund if offered refund or reship.", "Accept the refund preview.", "Keep responses to 1-3 sentences."], scenario_extra={"item_id": item.item_id, "return_item_id": item.item_id}, db_assertions=_refund_assertions(item, product.price), replay_steps=["get_order", "get_policies(shipping)", "get_policies(refund)", "process_refund(preview)", "process_refund(confirm)"], policy_results={"resolution": "refund", "refund_amount": product.price, "phases": ["Treat stale tracking over seven days as lost.", f"Issue immediate ${product.price} refund if customer chooses refund."]}, failure_traps=["Agent tells the customer to keep waiting despite stuck_7_days policy", "Agent fails to treat stale tracking as lost"], task_requirements=[_req(slug, "lost", "must", "Agent must treat the stale tracking as a lost-package claim.", "conversation_or_tool_calls"), _req(slug, "refund", "must", f"Agent must issue the ${product.price} refund after the customer chooses refund."), _req(slug, "no_wait", "must_not", "Agent must not require the customer to keep waiting without offering immediate refund or reship.")], novelty_rationale="Tests stuck tracking as a lost-package proxy.")
    return [product], [order], [item], [], data


def scenario_hard_shipping_paid_shipping_not_damage() -> ScenarioResult:
    product = build_product("running_shoes", product_id="PROD-4240")
    order = build_order(customer_id="cust_004", order_id="ORD-7228", delivery_date="2026-07-07T12:00:00", delivery_promised_date="2026-07-03T12:00:00", shipping_cost=8)
    item = build_order_item(order.order_id, product, item_id="ITEM-10230")
    finalize_order(order, [item])
    comp = policies.calculate_compensation(order.delivery_date, order.delivery_promised_date, "2026-07-08T10:00:00", order.total_paid, order.shipping_cost, _customer_tier("cust_004"), 0)
    slug = "hard_shipping_paid_shipping_not_damage"
    data = _task(slug=slug, task_type="shipping_claim", customer_id="cust_004", now="2026-07-08T10:00:00", order_id=order.order_id, description="Shoes arrived four days late but undamaged. Agent must process late-delivery compensation only and must not open a damaged-item return.", opening_message="ORD-7228 finally arrived four days late. The shoes are fine, but I want compensation for the delay.", known_info={"order_id": order.order_id, "days_late": "4", "condition": "undamaged"}, unknown_info=["late compensation"], rules=["Give the order ID.", "Clarify the shoes are not damaged if asked.", "Ask for compensation, not a return.", "Accept the compensation preview.", "Keep responses to 1-3 sentences."], scenario_extra={"item_id": item.item_id}, db_assertions=_refund_assertions(item, comp["total_compensation"]), replay_steps=["get_order", "get_policies(compensation)", "get_policies(refund)", "process_refund(compensation, preview)", "process_refund(confirm)"], policy_results={"resolution": "compensation", "compensation_amount": comp["total_compensation"], "phases": ["Issue late-delivery compensation only.", "Do not process a damaged return because product is fine."]}, failure_traps=["Agent opens a return despite the item being fine", "Agent misses compensation because no product return is needed"], task_requirements=[_req(slug, "comp", "must", "Agent must process late-delivery compensation."), _req(slug, "no_return", "must_not", "Agent must not process a return, replacement, or exchange for the undamaged shoes.")], novelty_rationale="Shipping delay task where correct action is compensation without any item-resolution workflow.")
    return [product], [order], [item], [], data


def _warranty_claim_task(slug: str, *, customer_id: str, now: str, order_id: str, item_id: str, warranty_id: str, product_key: str, product_id: str, warranty_type: str, start_date: str, claim_count: int, description: str, opening: str, rules: list[str], traps: list[str], novelty: str, max_claims: int = 3, months_override: int | None = None) -> ScenarioResult:
    product = build_product(product_key, product_id=product_id)
    order = build_order(customer_id=customer_id, order_id=order_id, delivery_date=f"{start_date}T12:00:00")
    item = build_order_item(order.order_id, product, item_id=item_id)
    finalize_order(order, [item])
    warranty = build_warranty(order.order_id, item.item_id, product, warranty_id=warranty_id, warranty_type=warranty_type, start_date=start_date, claim_count=claim_count, max_claims=max_claims, months_override=months_override)
    claim = policies.check_warranty_claim(warranty.warranty_type, warranty.start_date, warranty.end_date, now, warranty.claim_count, warranty.max_claims, item.unit_price)
    data = _task(slug=slug, task_type="warranty_claim", customer_id=customer_id, now=now, order_id=order.order_id, description=description, opening_message=opening, known_info={"order_id": order.order_id, "item": product.name, "warranty_id": warranty.warranty_id}, unknown_info=["warranty eligibility", "resolution"], rules=rules + ["Accept the warranty preview if it matches policy.", "Keep responses to 1-3 sentences."], scenario_extra={"item_id": item.item_id, "warranty_id": warranty.warranty_id}, db_assertions=[{"booking_id": warranty.warranty_id, "field": "status", "expected": "claimed"}, {"booking_id": warranty.warranty_id, "field": "claim_count", "expected": claim_count + 1}, {"booking_id": warranty.warranty_id, "field": "resolution", "expected": claim.get("resolution")}], replay_steps=["get_order", "get_warranty_status", "get_policies(warranty)", "process_warranty_claim(preview)", "process_warranty_claim(confirm)"], policy_results=claim, failure_traps=traps, task_requirements=[_req(slug, "status", "must", "Agent must check warranty status before filing the claim."), _req(slug, "process", "must", f"Agent must process the warranty claim with resolution {claim.get('resolution')}.")], novelty_rationale=novelty)
    return [product], [order], [item], [warranty], data


def scenario_spare_warranty_no_record_return_valid() -> ScenarioResult:
    return _warranty_claim_task("hard_warranty_extended_active_after_manufacturer", customer_id="cust_003", now="2026-08-01T10:00:00", order_id="ORD-7231", item_id="ITEM-10231", warranty_id="WRT-4101", product_key="tablet", product_id="PROD-4241", warranty_type="extended", start_date="2025-08-10", months_override=18, claim_count=0, description="Tablet manufacturer window would be expired, but the extended warranty is active. Agent must use the warranty record instead of denying from generic manufacturer timing.", opening="My tablet from ORD-7231 stopped charging. I bought extended coverage, but I know the regular warranty may be over.", rules=["Give the order ID.", "Mention extended coverage if asked.", "Push back if the agent denies based only on manufacturer warranty."], traps=["Agent denies by assuming only manufacturer warranty", "Agent fails to check warranty status"], novelty="Extended warranty record overrides generic manufacturer-window assumption.")


def scenario_hard_warranty_recent_expiry_discounted_repair() -> ScenarioResult:
    return _warranty_claim_task("hard_warranty_recent_expiry_discounted_repair", customer_id="cust_004", now="2026-07-20T10:00:00", order_id="ORD-7232", item_id="ITEM-10232", warranty_id="WRT-4102", product_key="coffee_maker", product_id="PROD-4242", warranty_type="manufacturer", start_date="2025-07-01", months_override=12, claim_count=0, description="Coffee maker warranty expired recently, so discounted repair is available. Agent must not say there are no warranty options.", opening="My coffee maker from ORD-7232 broke just after the warranty ended. Is there any help or am I out of luck?", rules=["Give the order ID.", "Say it broke just after warranty ended.", "Accept discounted repair if offered."], traps=["Agent denies all warranty help after expiry", "Agent misses the recent-expiry discounted repair option"], novelty="Recent-expiry warranty grace option with customer expecting denial.")


def scenario_hard_warranty_recurring_low_value_replace() -> ScenarioResult:
    return _warranty_claim_task("hard_warranty_recurring_low_value_replace", customer_id="cust_002", now="2026-07-08T10:00:00", order_id="ORD-7233", item_id="ITEM-10233", warranty_id="WRT-4103", product_key="usb_hub", product_id="PROD-4243", warranty_type="manufacturer", start_date="2026-01-01", claim_count=2, description="USB hub has two prior warranty claims. Recurring defect policy triggers automatic replacement, not another repair explanation.", opening="The USB hub in ORD-7233 failed for the third time. Please don't make me troubleshoot it again.", rules=["Give the order ID.", "Mention this is the third failure.", "Ask whether repeated defects change the outcome."], traps=["Agent treats recurring defect as ordinary repair", "Agent misses automatic replacement after prior claims"], novelty="Recurring low-value warranty replacement with customer explicitly resisting another repair loop.")


def scenario_spare_warranty_void_user_damage() -> ScenarioResult:
    return _warranty_claim_task("hard_warranty_refurb_short_window", customer_id="cust_004", now="2026-09-20T10:00:00", order_id="ORD-7234", item_id="ITEM-10234", warranty_id="WRT-4104", product_key="laptop_refurb", product_id="PROD-4244", warranty_type="manufacturer", start_date="2026-06-01", months_override=3, claim_count=0, description="Refurbished laptop has a short 90-day warranty and is recently expired. Agent must apply the refurbished warranty record, not the normal 12-month laptop assumption.", opening="My refurbished laptop from ORD-7234 died. Laptops usually have a year, right?", rules=["Give the order ID.", "Say it was refurbished if asked.", "Push once if the agent assumes a full year."], traps=["Agent assumes a 12-month new-laptop warranty", "Agent ignores the refurbished warranty record"], novelty="Refurbished-specific warranty duration as the key fact.")


def scenario_hard_warranty_maxed_but_paid_repair() -> ScenarioResult:
    return _warranty_claim_task("hard_warranty_maxed_but_paid_repair", customer_id="cust_002", now="2026-07-08T10:00:00", order_id="ORD-7235", item_id="ITEM-10235", warranty_id="WRT-4105", product_key="wireless_headphones", product_id="PROD-4245", warranty_type="manufacturer", start_date="2026-01-01", claim_count=3, description="Warranty claim limit is maxed, but policy still allows paid repair. Agent must not promise a free replacement or say no option exists.", opening="My headphones from ORD-7235 broke again. I know I've used the warranty a lot, but what can you do?", rules=["Give the order ID.", "Admit there have been several prior claims if asked.", "Accept paid repair if that is the only policy option."], traps=["Agent promises a free replacement despite max claims", "Agent says no option exists and misses paid repair"], novelty="Max-claims case where the valid outcome is paid repair, not complete denial or return fallback.")


def scenario_hard_warranty_shipping_damage_better_path() -> ScenarioResult:
    blender = build_product("blender", product_id="PROD-4246")
    order = build_order(customer_id="cust_004", order_id="ORD-7236", shipping_status="damaged", delivery_date="2026-07-07T12:00:00")
    item = build_order_item(order.order_id, blender, item_id="ITEM-10236")
    finalize_order(order, [item])
    warranty = build_warranty(order.order_id, item.item_id, blender, warranty_id="WRT-4106", start_date="2026-07-07")
    refund = _return_refund(blender, order, item, "cust_004", "damaged_in_transit", "2026-07-08T10:00:00")
    slug = "hard_warranty_shipping_damage_better_path"
    data = _task(slug=slug, task_type="warranty_claim", customer_id="cust_004", now="2026-07-08T10:00:00", order_id=order.order_id, description="Customer asks for warranty help, but the blender arrived shattered in transit yesterday. Correct path is shipping/return resolution, not consuming a warranty claim.", opening_message="The blender from ORD-7236 arrived shattered. Should I use my warranty to get it fixed?", known_info={"order_id": order.order_id, "issue": "arrived shattered"}, unknown_info=["whether warranty should be used"], rules=["Give the order ID.", "Ask if warranty is needed.", "Accept a shipping/return resolution if the agent explains it avoids using warranty."], scenario_extra={"item_id": item.item_id, "return_item_id": item.item_id, "warranty_id": warranty.warranty_id}, db_assertions=_return_assertions(order, item, refund) + [{"booking_id": warranty.warranty_id, "field": "claim_count", "expected": 0}], replay_steps=["get_order", "get_warranty_status", "get_policies(shipping)", "get_policies(return)", "get_policies(refund)", "process_return(damaged_in_transit, preview)", "process_return(confirm)"], policy_results={"phases": ["Do not consume warranty for shipping damage.", "Process damaged-in-transit return instead."], "return_reason": "damaged_in_transit"}, failure_traps=["Agent consumes a warranty claim for shipping damage", "Agent fails to choose the better shipping/return path"], task_requirements=[_req(slug, "avoid_warranty", "must", "Agent must explain that the customer should not use a warranty claim for shipping damage.", "conversation"), _req(slug, "return", "must", "Agent must process the damaged-in-transit return."), _req(slug, "no_claim", "must_not", "Agent must not file a warranty claim.")], novelty_rationale="Warranty request where the best customer outcome is a shipping-damage return that preserves warranty claims.")
    return [blender], [order], [item], [warranty], data


def scenario_hard_warranty_return_better_than_paid_repair() -> ScenarioResult:
    headphones = build_product("wireless_headphones", product_id="PROD-4247")
    order = build_order(customer_id="cust_004", order_id="ORD-7237", delivery_date="2026-07-03T12:00:00")
    item = build_order_item(order.order_id, headphones, item_id="ITEM-10237")
    finalize_order(order, [item])
    warranty = build_warranty(order.order_id, item.item_id, headphones, warranty_id="WRT-4107", start_date="2026-07-03", claim_count=3)
    refund = _return_refund(headphones, order, item, "cust_004", "defective", "2026-07-08T10:00:00")
    slug = "hard_warranty_return_better_than_paid_repair"
    data = _task(slug=slug, task_type="warranty_claim", customer_id="cust_004", now="2026-07-08T10:00:00", order_id=order.order_id, description="Warranty is maxed and would require paid repair, but the defective headphones are still within the return window. Agent must choose the full defective return as the better outcome.", opening_message="These headphones from ORD-7237 broke again. Warranty may be maxed, but I need the cheapest option.", known_info={"order_id": order.order_id, "issue": "defective", "warranty": "maxed"}, unknown_info=["return alternative"], rules=["Give the order ID.", "Ask for the cheapest option.", "If paid repair is offered, ask whether a return is possible.", "Accept the defective return preview."], scenario_extra={"item_id": item.item_id, "return_item_id": item.item_id, "warranty_id": warranty.warranty_id}, db_assertions=_return_assertions(order, item, refund), replay_steps=["get_order", "get_warranty_status", "get_policies(warranty)", "get_policies(return)", "get_policies(refund)", "process_return(defective, preview)", "process_return(confirm)"], policy_results={"phases": ["Warranty maxed means paid repair.", "Defective return is still available and better; process return."]}, failure_traps=["Agent stops at paid repair", "Agent fails to check return eligibility as a better alternative"], task_requirements=[_req(slug, "compare", "must", "Agent must compare warranty and return options."), _req(slug, "return", "must", "Agent must process the full defective return as the better customer outcome."), _req(slug, "no_paid_only", "must_not", "Agent must not leave the customer with only paid repair.")], novelty_rationale="Warranty-vs-return optimization with the customer asking for cheapest outcome.")
    return [headphones], [order], [item], [warranty], data


def _edge_no_action(slug: str, *, customer_id: str, now: str, order_id: str, products: list, items: list, order, description: str, opening: str, rules: list[str], must: str, must_not: str, novelty: str, replay_steps: list[Any] | None = None, scenario_extra: dict[str, Any] | None = None) -> ScenarioResult:
    data = _task(slug=slug, task_type="edge_case", customer_id=customer_id, now=now, order_id=order_id, description=description, opening_message=opening, known_info={"order_id": order_id}, unknown_info=["policy-supported next step"], rules=rules + ["Accept a clear policy explanation.", "Keep responses to 1-3 sentences."], scenario_extra=scenario_extra or {}, db_assertions=[], replay_steps=replay_steps or ["get_order"], policy_results={"no_action": True, "agent_must": must}, failure_traps=[must_not], task_requirements=[_req(slug, "must", "must", must, "conversation_or_tool_calls"), _req(slug, "must_not", "must_not", must_not)], novelty_rationale=novelty)
    return products, [order], items, [], data


def scenario_hard_edge_wrong_customer_order_privacy() -> ScenarioResult:
    product = build_product("tablet", product_id="PROD-4251")
    order = build_order(customer_id="cust_002", order_id="ORD-7241", delivery_date="2026-07-07T12:00:00")
    item = build_order_item(order.order_id, product, item_id="ITEM-10241")
    finalize_order(order, [item])
    return _edge_no_action("hard_edge_wrong_customer_order_privacy", customer_id="cust_002", now="2026-07-08T10:00:00", order_id=order.order_id, products=[product], items=[item], order=order, description="Customer says the order may be under a partner account and asks for action before verification. Agent must verify ownership/context before mutating state.", opening="I need help returning the tablet in ORD-7241, but this might be under my partner's account.", rules=["Give the order ID.", "Say it may be under your partner's account if challenged.", "Push once for help anyway."], must="Agent must ask for proper verification or corrected account context before taking action.", must_not="Agent must not process a return, refund, exchange, cancellation, or warranty claim before resolving the account-context concern.", novelty="Account-context uncertainty requiring verification before action, without violating task ownership invariants.")


def scenario_hard_edge_already_refunded_second_credit() -> ScenarioResult:
    product = build_product("phone_case", product_id="PROD-4252")
    order = build_order(customer_id="cust_004", order_id="ORD-7242", status="fully_returned", delivery_date="2026-07-01T12:00:00")
    item = build_order_item(order.order_id, product, item_id="ITEM-10242", item_status="returned")
    item.refund_amount = 35
    item.refund_method = "original_payment"
    item.return_reason = "changed_mind"
    finalize_order(order, [item])
    return _edge_no_action("hard_edge_already_refunded_second_credit", customer_id="cust_004", now="2026-07-08T10:00:00", order_id=order.order_id, products=[product], items=[item], order=order, description="Item is already returned and refunded. Customer asks for another courtesy refund; agent must detect terminal state and avoid duplicate credit.", opening="I returned the phone case from ORD-7242, but can you refund it again as a courtesy?", rules=["Give the order ID.", "Acknowledge it was already returned if asked.", "Push once for a courtesy credit."], must="Agent must explain that the item has already been returned/refunded and no duplicate refund is due.", must_not="Agent must not issue any second refund or goodwill credit.", novelty="Duplicate refund request after terminal returned state.")


def scenario_hard_edge_unclear_small_item_reference() -> ScenarioResult:
    case = build_product("phone_case", product_id="PROD-4253")
    hub = build_product("usb_hub", product_id="PROD-4254")
    order = build_order(customer_id="cust_002", order_id="ORD-7243", delivery_date="2026-07-07T12:00:00")
    item_case = build_order_item(order.order_id, case, item_id="ITEM-10243")
    item_hub = build_order_item(order.order_id, hub, item_id="ITEM-10244")
    finalize_order(order, [item_case, item_hub])
    return _edge_no_action("hard_edge_unclear_small_item_reference", customer_id="cust_002", now="2026-07-08T10:00:00", order_id=order.order_id, products=[case, hub], items=[item_case, item_hub], order=order, description="Customer says only 'the small accessory' in a multi-item order. Agent must clarify which item before any write action.", opening="I want to return the small accessory from ORD-7243. Can you just do it?", rules=["Give the order ID.", "Do not identify the item until the agent asks a clarifying question.", "Say you meant the phone case only after asked."], must="Agent must ask a clarifying question to identify the item before taking any write action.", must_not="Agent must not guess an item or process any return/refund before clarification.", novelty="Pure clarification task where ambiguity is intentional and state must stay unchanged until clarified.")


def scenario_hard_edge_invalid_product_no_order() -> ScenarioResult:
    product = build_product("coffee_maker", product_id="PROD-4255")
    order = build_order(customer_id="cust_003", order_id="ORD-7244", delivery_date="2026-07-07T12:00:00")
    item = build_order_item(order.order_id, product, item_id="ITEM-10245")
    finalize_order(order, [item])
    return _edge_no_action("hard_edge_invalid_product_no_order", customer_id="cust_003", now="2026-07-08T10:00:00", order_id=order.order_id, products=[product], items=[item], order=order, description="Customer asks for support using only a product nickname and refuses to provide order context initially. Agent must request order/account details before acting.", opening="My brewer is junk. Just refund it; I don't have the order number handy.", rules=["Do not provide the order ID until the agent asks for it.", "Push once for a refund without lookup.", "Provide ORD-7244 only after the agent asks for order context."], must="Agent must request order or account context before attempting any refund/return action.", must_not="Agent must not process or promise a refund based only on a product nickname.", novelty="No initial order ID, testing information gathering before tool/action.")


def scenario_hard_edge_all_windows_plus_false_defect() -> ScenarioResult:
    product = build_product("novel", product_id="PROD-4256")
    order = build_order(customer_id="cust_004", order_id="ORD-7245", delivery_date="2026-04-01T12:00:00")
    item = build_order_item(order.order_id, product, item_id="ITEM-10246")
    finalize_order(order, [item])
    return _edge_no_action("hard_edge_all_windows_plus_false_defect", customer_id="cust_004", now="2026-07-08T10:00:00", order_id=order.order_id, products=[product], items=[item], order=order, description="Book is far outside every return window. Customer first calls it defective but admits they simply changed their mind. Agent must deny return and not use defective exception.", opening="The book from ORD-7245 is defective... well, I just didn't like it. Can you still refund it?", rules=["Give the order ID.", "Admit it is not actually defective if asked.", "Push once for an exception."], must="Agent must classify the request as changed_mind and deny the return because all windows are expired.", must_not="Agent must not use the defective exception or issue any refund/store credit.", novelty="Combines false-defect correction with all-windows-expired denial.")


def scenario_hard_edge_cancel_delivered_subscription_confusion() -> ScenarioResult:
    product = build_product("coffee_maker", product_id="PROD-4257")
    order = build_order(customer_id="cust_002", order_id="ORD-7246", status="delivered", shipping_status="delivered", delivery_date="2026-07-01T12:00:00")
    item = build_order_item(order.order_id, product, item_id="ITEM-10247")
    finalize_order(order, [item])
    return _edge_no_action("hard_edge_cancel_delivered_subscription_confusion", customer_id="cust_002", now="2026-07-08T10:00:00", order_id=order.order_id, products=[product], items=[item], order=order, description="Customer asks to cancel a delivered one-time order as if it were a subscription. Agent must explain delivered orders cannot be cancelled and offer return path instead of mutating state.", opening="Cancel ORD-7246 so I don't get charged again. It already arrived but I don't want this subscription.", rules=["Give the order ID.", "Say you thought it was a subscription.", "Ask what can be done since it already arrived."], must="Agent must explain this is a delivered order that cannot be cancelled and direct the customer to return eligibility instead.", must_not="Agent must not cancel the delivered order or invent a subscription cancellation.", novelty="Delivered-order cancellation request with subscription confusion rather than ordinary buyer remorse.")


def scenario_hard_edge_unknown_policy_exception_request() -> ScenarioResult:
    product = build_product("smartphone", product_id="PROD-4258")
    order = build_order(customer_id="cust_003", order_id="ORD-7247", delivery_date="2026-06-01T12:00:00")
    item = build_order_item(order.order_id, product, item_id="ITEM-10248")
    finalize_order(order, [item])
    return _edge_no_action("hard_edge_unknown_policy_exception_request", customer_id="cust_003", now="2026-07-08T10:00:00", order_id=order.order_id, products=[product], items=[item], order=order, description="Customer claims there is a VIP exception for old smartphone returns. No such policy exists. Agent must rely on actual policy and not fabricate an exception.", opening="I'm Gold, so use the VIP exception to refund the smartphone from ORD-7247 even though it's old.", rules=["Give the order ID.", "Insist once that Gold should have a VIP exception.", "Accept a policy-grounded denial or valid store-credit explanation."], must="Agent must check actual policy and avoid fabricating a VIP exception.", must_not="Agent must not promise or issue a refund based on a nonexistent VIP exception.", novelty="Tests hallucination resistance against a user-invented policy exception.")


def scenario_hard_compound_return_one_price_match_other() -> ScenarioResult:
    headphones = build_product("wireless_headphones", product_id="PROD-4261")
    case = build_product("phone_case", product_id="PROD-4262", current_price=25)
    order = build_order(customer_id="cust_003", order_id="ORD-7251", delivery_date="2026-07-03T12:00:00")
    item_hp = build_order_item(order.order_id, headphones, item_id="ITEM-10251")
    item_case = build_order_item(order.order_id, case, item_id="ITEM-10252")
    finalize_order(order, [item_hp, item_case])
    refund_hp = _return_refund(headphones, order, item_hp, "cust_003", "defective", "2026-07-08T10:00:00")
    price_match = case.price - case.current_price
    slug = "hard_compound_return_one_price_match_other"
    data = _task(slug=slug, task_type="compound", customer_id="cust_003", now="2026-07-08T10:00:00", order_id=order.order_id, description="Same order requires a defective return for headphones and a separate price-match refund for the phone case. Agent must not collapse both into one workflow.", opening_message="In ORD-7251, the headphones are defective, and the phone case got cheaper. Can you handle both?", known_info={"order_id": order.order_id, "defective": "headphones", "price_drop": "phone case"}, unknown_info=["two policy surfaces"], rules=["Give the order ID.", "Confirm headphones are defective and phone case should be kept.", "Accept both previews.", "Keep responses to 1-3 sentences."], scenario_extra={"item_id": item_hp.item_id, "return_item_id": item_hp.item_id}, db_assertions=_return_assertions(order, item_hp, refund_hp) + _refund_assertions(item_case, price_match), replay_steps=["get_order", "get_product(phone_case)", "get_policies(return)", "get_policies(refund)", "process_return(headphones, preview)", "process_return(confirm)", "process_refund(phone_case, preview)", "process_refund(confirm)"], policy_results={"phases": ["Return defective headphones.", f"Issue separate ${price_match} price-match refund for phone case."]}, failure_traps=["Agent handles only one of the two issues", "Agent returns the phone case instead of price matching it"], task_requirements=[_req(slug, "return", "must", "Agent must process the defective headphones return."), _req(slug, "price", "must", "Agent must issue a separate price-match refund for the phone case."), _req(slug, "scope", "must_not", "Agent must not return or cancel the phone case.")], novelty_rationale="Combines return and price match on separate items in one order.")
    return [headphones, case], [order], [item_hp, item_case], [], data


def scenario_spare_compound_cancel_plus_shipping_claim() -> ScenarioResult:
    tablet = build_product("tablet", product_id="PROD-4263")
    shirt = build_product("cotton_shirt", product_id="PROD-4264")
    order = build_order(customer_id="cust_002", order_id="ORD-7252", status="processing", shipping_status="processing", delivery_date="2026-07-03T12:00:00")
    item_tablet = build_order_item(order.order_id, tablet, item_id="ITEM-10253", item_status="confirmed")
    item_shirt = build_order_item(order.order_id, shirt, item_id="ITEM-10254", item_status="delivered")
    finalize_order(order, [item_tablet, item_shirt])
    refund_shirt = _return_refund(shirt, order, item_shirt, "cust_002", "changed_mind", "2026-07-08T10:00:00")
    slug = "hard_compound_cancel_unshipped_return_delivered"
    data = _task(slug=slug, task_type="compound", customer_id="cust_002", now="2026-07-08T10:00:00", order_id=order.order_id, description="Mixed-fulfillment order: cancel unshipped tablet and return delivered shirt. Agent must use cancellation for one item and return for the other.", opening_message="ORD-7252 has a tablet that hasn't shipped and a shirt that arrived. Cancel the tablet and return the shirt.", known_info={"order_id": order.order_id, "cancel": "tablet", "return": "shirt"}, unknown_info=["mixed workflows"], rules=["Give the order ID.", "Repeat that tablet has not shipped and shirt arrived.", "Accept both previews.", "Keep responses to 1-3 sentences."], scenario_extra={"item_id": item_shirt.item_id, "return_item_id": item_shirt.item_id}, db_assertions=[{"booking_id": item_tablet.item_id, "field": "item_status", "expected": "cancelled"}] + _return_assertions(order, item_shirt, refund_shirt), replay_steps=["get_order", "get_policies(cancellation)", "cancel_order(item_ids, preview)", "cancel_order(confirm)", "get_policies(return)", "get_policies(refund)", "process_return(shirt, preview)", "process_return(confirm)"], policy_results={"phases": ["Cancel only the unshipped tablet.", "Return only the delivered shirt."]}, failure_traps=["Agent uses the same workflow for both items", "Agent cancels the delivered shirt or returns the unshipped tablet"], task_requirements=[_req(slug, "cancel", "must", "Agent must cancel only the unshipped tablet."), _req(slug, "return", "must", "Agent must return only the delivered shirt."), _req(slug, "mixed", "must", "Agent must use cancellation and return as separate workflows.")], novelty_rationale="Mixed fulfillment state requiring different write tools in one order.")
    return [tablet, shirt], [order], [item_tablet, item_shirt], [], data


def scenario_hard_compound_exchange_plus_late_compensation() -> ScenarioResult:
    shirt = build_product("cotton_shirt", product_id="PROD-4265")
    large = build_product("cotton_shirt_large", product_id="PROD-4266")
    order = build_order(customer_id="cust_003", order_id="ORD-7253", delivery_date="2026-07-08T12:00:00", delivery_promised_date="2026-07-04T12:00:00")
    item = build_order_item(order.order_id, shirt, item_id="ITEM-10255")
    finalize_order(order, [item])
    comp = policies.calculate_compensation(order.delivery_date, order.delivery_promised_date, "2026-07-08T18:00:00", order.total_paid, order.shipping_cost, _customer_tier("cust_003"), 0)
    slug = "hard_compound_exchange_plus_late_compensation"
    data = _task(slug=slug, task_type="compound", customer_id="cust_003", now="2026-07-08T18:00:00", order_id=order.order_id, description="Shirt arrived late and in the wrong size. Agent must process a size exchange and separately issue late-delivery compensation.", opening_message="ORD-7253 arrived late and the shirt is too small. I need the large size and compensation for the delay.", known_info={"order_id": order.order_id, "exchange": "large shirt", "late": "4 days"}, unknown_info=["two actions"], rules=["Give the order ID.", "Confirm you want the large size.", "Ask about delay compensation if not offered.", "Accept both previews.", "Keep responses to 1-3 sentences."], scenario_extra={"item_id": item.item_id, "new_product_id": large.product_id}, db_assertions=_exchange_assertions(item) + _refund_assertions(item, comp["total_compensation"]), replay_steps=["get_order", "get_product", "get_policies(exchange)", "process_exchange(preview)", "process_exchange(confirm)", "get_policies(compensation)", "get_policies(refund)", "process_refund(compensation, preview)", "process_refund(confirm)"], policy_results={"phases": ["Process same-variant size exchange.", f"Issue separate ${comp['total_compensation']} late compensation."]}, failure_traps=["Agent completes exchange but misses compensation", "Agent offers compensation but fails to process exchange"], task_requirements=[_req(slug, "exchange", "must", "Agent must process the shirt size exchange."), _req(slug, "comp", "must", "Agent must issue the separate late-delivery compensation.")], novelty_rationale="Exchange and late compensation together, with no return/refund substitution.")
    return [shirt, large], [order], [item], [], data


def scenario_hard_compound_missing_item_plus_signature_denial() -> ScenarioResult:
    case = build_product("phone_case", product_id="PROD-4267")
    laptop = build_product("laptop_pro", product_id="PROD-4268")
    order = build_order(customer_id="cust_001", order_id="ORD-7254", delivery_date="2026-07-07T12:00:00", signature_required=True, signature_on_file="M. Chen")
    item_case = build_order_item(order.order_id, case, item_id="ITEM-10256")
    item_laptop = build_order_item(order.order_id, laptop, item_id="ITEM-10257")
    finalize_order(order, [item_case, item_laptop])
    refund_case = _return_refund(case, order, item_case, "cust_001", "missing", "2026-07-08T10:00:00")
    slug = "hard_compound_missing_item_plus_signature_denial"
    data = _task(slug=slug, task_type="compound", customer_id="cust_001", now="2026-07-08T10:00:00", order_id=order.order_id, description="Customer reports a missing low-value phone case and also claims the signed-for laptop was not received. Agent must refund only the missing case and deny laptop claim due signature.", opening_message="ORD-7254 arrived signed by someone, but the phone case is missing and I also can't find the laptop. Refund both.", known_info={"order_id": order.order_id, "missing": "phone case", "signature": "M. Chen"}, unknown_info=["mixed claim outcomes"], rules=["Give the order ID.", "Confirm the phone case was missing from the box.", "Push once for the laptop refund too.", "Accept case refund and laptop denial if explained."], scenario_extra={"item_id": item_case.item_id, "return_item_id": item_case.item_id}, db_assertions=_return_assertions(order, item_case, refund_case) + [{"booking_id": item_laptop.item_id, "field": "item_status", "expected": "delivered"}], replay_steps=["get_order", "get_policies(shipping)", "get_policies(return)", "get_policies(refund)", "process_return(phone_case, preview)", "process_return(confirm)"], policy_results={"phases": ["Refund missing phone case only.", "Deny laptop not-received claim due signature on file."]}, failure_traps=["Agent refunds both items", "Agent denies everything and misses the missing phone case"], task_requirements=[_req(slug, "case", "must", "Agent must process the missing phone case claim."), _req(slug, "laptop_deny", "must", "Agent must deny the laptop not-received claim because there is a signature on file.", "conversation"), _req(slug, "no_laptop", "must_not", "Agent must not refund, return, replace, or alter the laptop.")], novelty_rationale="Compound claim with one valid item-level action and one signature-based denial.")
    return [case, laptop], [order], [item_case, item_laptop], [], data


def scenario_hard_compound_gift_return_plus_exchange() -> ScenarioResult:
    novel = build_product("novel", product_id="PROD-4269", current_price=20)
    shirt = build_product("cotton_shirt", product_id="PROD-4270")
    large = build_product("cotton_shirt_large", product_id="PROD-4271")
    order = build_order(customer_id="cust_003", order_id="ORD-7255", delivery_date="2026-07-03T12:00:00", is_gift=True, gift_sender="Riley")
    item_book = build_order_item(order.order_id, novel, item_id="ITEM-10258")
    item_shirt = build_order_item(order.order_id, shirt, item_id="ITEM-10259")
    finalize_order(order, [item_book, item_shirt])
    refund_book = _return_refund(novel, order, item_book, "cust_003", "changed_mind", "2026-07-08T10:00:00")
    slug = "hard_compound_gift_return_plus_exchange"
    data = _task(slug=slug, task_type="compound", customer_id="cust_003", now="2026-07-08T10:00:00", order_id=order.order_id, description="Gift order with two needs: return the book to store credit at current price and exchange the shirt for Large. Agent must not refund the gift sender or collapse both into one process.", opening_message="I got ORD-7255 as a gift. I want to return the book for credit and exchange the shirt for a large.", known_info={"order_id": order.order_id, "gift": "yes", "return": "book", "exchange": "shirt"}, unknown_info=["gift return method"], rules=["Give the order ID.", "Repeat that it was a gift.", "Accept store credit for the book and size exchange for the shirt.", "Keep responses to 1-3 sentences."], scenario_extra={"item_id": item_book.item_id, "return_item_id": item_book.item_id, "new_product_id": large.product_id}, db_assertions=_return_assertions(order, item_book, refund_book) + _exchange_assertions(item_shirt), replay_steps=["get_order", "get_policies(return)", "get_policies(refund)", "process_return(novel, preview)", "process_return(confirm)", "get_product", "get_policies(exchange)", "process_exchange(shirt, preview)", "process_exchange(confirm)"], policy_results={"phases": ["Gift-return book to store credit at current price.", "Exchange shirt for Large."]}, failure_traps=["Agent refunds gift sender", "Agent handles only return or only exchange"], task_requirements=[_req(slug, "gift", "must", "Agent must return the gift book to store credit at current price."), _req(slug, "exchange", "must", "Agent must exchange the shirt for Large."), _req(slug, "sender", "must_not", "Agent must not refund the gift sender's original payment method.")], novelty_rationale="Gift return and exchange in the same order, with different workflows and refund method.")
    return [novel, shirt, large], [order], [item_book, item_shirt], [], data


def scenario_spare_compound_denial_plus_valid_action() -> ScenarioResult:
    shirt = build_product("cotton_shirt", product_id="PROD-4272")
    order = build_order(customer_id="cust_004", order_id="ORD-7256", order_date="2025-12-15T10:00:00", delivery_date="2025-12-20T12:00:00", delivery_promised_date="2025-12-20T12:00:00")
    item = build_order_item(order.order_id, shirt, item_id="ITEM-10260")
    finalize_order(order, [item])
    refund = _return_refund(shirt, order, item, "cust_004", "changed_mind", "2026-01-20T10:00:00")
    slug = "hard_compound_seasonal_valid_shipping_denied"
    data = _task(slug=slug, task_type="compound", customer_id="cust_004", now="2026-01-20T10:00:00", order_id=order.order_id, description="Holiday clothing return is valid under seasonal extension, but customer also demands a shipping refund even though delivery was on time and item is changed_mind. Agent must accept return and deny shipping refund.", opening_message="I want to return the shirt from ORD-7256 under holiday returns, and I want shipping refunded too even though it arrived on time.", known_info={"order_id": order.order_id, "holiday_order": "yes", "delivery": "on time"}, unknown_info=["seasonal extension", "shipping refund eligibility"], rules=["Give the order ID.", "Mention it was a December order.", "Push once for shipping refund.", "Accept return without shipping refund."], scenario_extra={"item_id": item.item_id, "return_item_id": item.item_id}, db_assertions=_return_assertions(order, item, refund), replay_steps=["get_order", "get_policies(seasonal)", "get_policies(return)", "get_policies(refund)", "process_return(changed_mind, preview)", "process_return(confirm)"], policy_results={"phases": ["Seasonal extension makes return eligible.", "Deny shipping refund because delivery was on time and changed-mind return does not refund shipping."]}, failure_traps=["Agent denies valid seasonal return", "Agent grants unearned shipping refund"], task_requirements=[_req(slug, "seasonal", "must", "Agent must explain that the seasonal extension makes the return eligible."), _req(slug, "deny_shipping", "must", "Agent must deny the requested shipping refund.", "conversation"), _req(slug, "no_shipping", "must_not", "Agent must not issue a separate shipping refund.")], novelty_rationale="Valid seasonal return paired with an invalid shipping-refund demand.")
    return [shirt], [order], [item], [], data


def scenario_hard_compound_wrong_item_plus_late_comp() -> ScenarioResult:
    case = build_product("phone_case", product_id="PROD-4273")
    order = build_order(customer_id="cust_003", order_id="ORD-7257", delivery_date="2026-07-08T12:00:00", delivery_promised_date="2026-07-02T12:00:00")
    item = build_order_item(order.order_id, case, item_id="ITEM-10261")
    finalize_order(order, [item])
    refund = _return_refund(case, order, item, "cust_003", "wrong_item", "2026-07-08T18:00:00")
    comp = policies.calculate_compensation(order.delivery_date, order.delivery_promised_date, "2026-07-08T18:00:00", order.total_paid, order.shipping_cost, _customer_tier("cust_003"), 0)
    slug = "hard_compound_wrong_item_plus_late_comp"
    data = _task(slug=slug, task_type="compound", customer_id="cust_003", now="2026-07-08T18:00:00", order_id=order.order_id, description="Package arrived six days late and contains the wrong phone case. Agent must process wrong-item return and separately issue late-delivery compensation.", opening_message="ORD-7257 came six days late and it's the wrong phone case. I need both issues fixed.", known_info={"order_id": order.order_id, "issue1": "wrong item", "issue2": "six days late"}, unknown_info=["separate compensation"], rules=["Give the order ID.", "Confirm it is the wrong item and six days late.", "Ask about late compensation if not offered.", "Accept both previews."], scenario_extra={"item_id": item.item_id, "return_item_id": item.item_id}, db_assertions=_return_assertions(order, item, refund) + [{"booking_id": item.item_id, "field": "goodwill_credit", "expected": comp["total_compensation"]}, {"booking_id": item.item_id, "field": "goodwill_credit_method", "expected": "store_credit"}], replay_steps=["get_order", "get_policies(return)", "get_policies(refund)", "process_return(wrong_item, preview)", "process_return(confirm)", "get_policies(compensation)", "process_refund(compensation, preview)", "process_refund(confirm)"], policy_results={"phases": ["Process wrong-item return.", f"Issue separate ${comp['total_compensation']} late compensation."], "return_reason": "wrong_item", "total_compensation": comp["total_compensation"], "refund_method": "store_credit"}, failure_traps=["Agent handles the wrong item but misses late compensation", "Agent treats late compensation as replacing the return"], task_requirements=[_req(slug, "return", "must", "Agent must process the wrong-item return."), _req(slug, "comp", "must", "Agent must issue separate late-delivery compensation.")], novelty_rationale="Wrong-item product resolution plus independent shipping lateness compensation.")
    return [case], [order], [item], [], data


def scenario_spare_compound_warranty_then_price_match() -> ScenarioResult:
    tablet = build_product("tablet", product_id="PROD-4274")
    order = build_order(customer_id="cust_004", order_id="ORD-7258", delivery_date="2026-07-03T12:00:00")
    item = build_order_item(order.order_id, tablet, item_id="ITEM-10262")
    finalize_order(order, [item])
    refund = _return_refund(tablet, order, item, "cust_004", "changed_mind", "2026-07-08T10:00:00")
    slug = "hard_compound_partial_denial_valid_return"
    data = _task(slug=slug, task_type="compound", customer_id="cust_004", now="2026-07-08T10:00:00", order_id=order.order_id, description="Customer has a valid changed-mind tablet return but also demands a non-policy $100 inconvenience credit. Agent must process the valid return and deny the extra credit.", opening_message="I want to return the tablet from ORD-7258, and I want an extra $100 for inconvenience even though nothing was wrong with it.", known_info={"order_id": order.order_id, "return_reason": "changed mind", "extra_demand": "$100"}, unknown_info=["whether goodwill applies"], rules=["Give the order ID.", "Admit the tablet is not defective.", "Push once for the extra credit.", "Accept the return even if extra credit is denied."], scenario_extra={"item_id": item.item_id, "return_item_id": item.item_id}, db_assertions=_return_assertions(order, item, refund), replay_steps=["get_order", "get_policies(return)", "get_policies(refund)", "process_return(changed_mind, preview)", "process_return(confirm)"], policy_results={"phases": ["Process valid changed-mind return.", "Deny unsupported $100 inconvenience credit."]}, failure_traps=["Agent grants unsupported goodwill", "Agent denies the valid return because of the unsupported extra demand"], task_requirements=[_req(slug, "return", "must", "Agent must process the valid changed-mind return."), _req(slug, "deny", "must", "Agent must deny the unsupported $100 inconvenience credit.", "conversation"), _req(slug, "no_credit", "must_not", "Agent must not issue any extra goodwill or compensation credit.")], novelty_rationale="Partial satisfaction: complete valid return while denying unrelated invented compensation.")
    return [tablet], [order], [item], [], data


def scenario_spare_cancel_after_shipment_keep_delivered() -> ScenarioResult:
    tablet = build_product("tablet", product_id="PROD-4275")
    novel = build_product("novel", product_id="PROD-4276")
    order = build_order(customer_id="cust_002", order_id="ORD-7261", status="processing", shipping_status="processing", delivery_date=None)
    item_tablet = build_order_item(order.order_id, tablet, item_id="ITEM-10263", item_status="confirmed")
    item_book = build_order_item(order.order_id, novel, item_id="ITEM-10264", item_status="confirmed")
    finalize_order(order, [item_tablet, item_book])
    slug = "hard_cancel_partial_mixed_status"
    data = _task(slug=slug, task_type="cancel_order", customer_id="cust_002", now="2026-07-08T10:00:00", order_id=order.order_id, description="Pre-shipment two-item order where customer wants to cancel only the tablet and keep the book. Agent must scope cancellation to one item.", opening_message="Cancel the tablet from ORD-7261, but keep the book coming.", known_info={"order_id": order.order_id, "cancel": "tablet", "keep": "book"}, unknown_info=["partial cancellation"], rules=["Give the order ID.", "Repeat that only the tablet should be cancelled.", "Accept the partial cancellation preview."], scenario_extra={"item_id": item_tablet.item_id}, db_assertions=[{"booking_id": item_tablet.item_id, "field": "item_status", "expected": "cancelled"}, {"booking_id": item_book.item_id, "field": "item_status", "expected": "confirmed"}, {"booking_id": order.order_id, "field": "status", "expected": "partially_cancelled"}], replay_steps=["get_order", "get_policies(cancellation)", "cancel_order(item_ids, preview)", "cancel_order(confirm)"], policy_results={"cancellation_fee": 0, "refund_amount": tablet.price, "phases": ["Cancel tablet only; keep book active."]}, failure_traps=["Agent cancels the entire order", "Agent cancels the wrong item"], task_requirements=[_req(slug, "scope", "must", "Agent must cancel only the tablet and leave the book active."), _req(slug, "no_book", "must_not", "Agent must not cancel the book.")], novelty_rationale="Cancellation scope with explicit keep-item instruction in a small order.")
    return [tablet, novel], [order], [item_tablet, item_book], [], data


def scenario_hard_cancel_delivered_pivot_return() -> ScenarioResult:
    case = build_product("phone_case", product_id="PROD-4277")
    hub = build_product("usb_hub", product_id="PROD-4278")
    order = build_order(customer_id="cust_003", order_id="ORD-7262", status="processing", shipping_status="processing", delivery_date=None)
    item_case = build_order_item(order.order_id, case, item_id="ITEM-10265", item_status="confirmed")
    item_hub = build_order_item(order.order_id, hub, item_id="ITEM-10266", item_status="confirmed")
    finalize_order(order, [item_case, item_hub])
    slug = "hard_cancel_delivered_pivot_return"
    data = _task(
        slug=slug,
        task_type="cancel_order",
        customer_id="cust_003",
        now="2026-07-08T10:00:00",
        order_id=order.order_id,
        description="Customer asks to cancel 'the accessory' from a processing order that contains two accessory items. Agent must clarify which item before any cancellation and leave the order unchanged until the item is identified.",
        opening_message="Cancel the accessory from ORD-7262 before it ships. I only want one thing cancelled, not the whole order.",
        known_info={"order_id": order.order_id, "ambiguous_reference": "the accessory", "items": "phone case and USB hub"},
        unknown_info=["which accessory should be cancelled", "partial cancellation scope"],
        rules=[
            "Give the order ID.",
            "Do not identify which accessory you mean unless the agent asks a clarifying question.",
            "If the agent tries to cancel either item without clarifying, object that you only said the accessory.",
            "Accept only a clarification request and confirmation that no cancellation was finalized yet.",
        ],
        scenario_extra={"item_id": item_case.item_id, "secondary_item_id": item_hub.item_id},
        db_assertions=[
            {"booking_id": item_case.item_id, "field": "item_status", "expected": "confirmed"},
            {"booking_id": item_hub.item_id, "field": "item_status", "expected": "confirmed"},
            {"booking_id": order.order_id, "field": "status", "expected": "processing"},
        ],
        replay_steps=["get_order", "get_policies(cancellation)"],
        policy_results={"no_action": True, "agent_must": "Ask which accessory to cancel before previewing or confirming cancellation; do not mutate state."},
        failure_traps=[
            "Agent guesses phone case or USB hub and cancels without clarification",
            "Agent cancels the whole order despite partial-cancellation wording",
            "Agent previews or finalizes cancellation before item scope is resolved",
        ],
        task_requirements=[
            _req(slug, "clarify", "must", "Agent must ask a clarifying question to identify which accessory should be cancelled before any cancellation action.", "conversation_or_tool_calls"),
            _req(slug, "no_guess", "must_not", "Agent must not guess phone case or USB hub as the target item without customer clarification."),
            _req(slug, "no_cancel", "must_not", "Agent must not preview or finalize any cancellation before the item scope is clarified."),
            _req(slug, "no_mutation", "must_not", "Agent must not mutate order or item state."),
        ],
        novelty_rationale="Cancellation-specific ambiguity task requiring clarification before partial cancellation, distinct from return ambiguity and mixed-status cancellation tasks.",
    )
    return [case, hub], [order], [item_case, item_hub], [], data

def scenario_spare_cancel_in_transit_fee_decline() -> ScenarioResult:
    phone = build_product("smartphone", product_id="PROD-4278")
    case = build_product("phone_case", product_id="PROD-4279")
    order = build_order(customer_id="cust_001", order_id="ORD-7263", status="processing", shipping_status="processing", delivery_date=None, payment_method="split", payment_details={"credit_card": 800, "gift_card": 242})
    item_phone = build_order_item(order.order_id, phone, item_id="ITEM-10266", item_status="confirmed")
    item_case = build_order_item(order.order_id, case, item_id="ITEM-10267", item_status="confirmed")
    finalize_order(order, [item_phone, item_case])
    order.payment_method = "split"
    order.payment_details = {"credit_card": 800, "gift_card": order.total_paid - 800}
    slug = "hard_cancel_split_tender_keep_one"
    data = _task(slug=slug, task_type="cancel_order", customer_id="cust_001", now="2026-07-08T10:00:00", order_id=order.order_id, description="Split-tender pre-shipment order where customer cancels only the phone and keeps the case. Agent must handle partial cancellation and explain refund follows original split tender.", opening_message="Cancel just the phone from ORD-7263. I paid with card and gift card, and I still want the case.", known_info={"order_id": order.order_id, "cancel": "phone", "keep": "case", "payment": "split"}, unknown_info=["split tender refund"], rules=["Give the order ID.", "Repeat that the case should stay active.", "Ask how split tender is handled.", "Accept partial cancellation preview."], scenario_extra={"item_id": item_phone.item_id}, db_assertions=[{"booking_id": item_phone.item_id, "field": "item_status", "expected": "cancelled"}, {"booking_id": item_case.item_id, "field": "item_status", "expected": "confirmed"}, {"booking_id": order.order_id, "field": "status", "expected": "partially_cancelled"}], replay_steps=["get_order", "get_policies(cancellation)", "cancel_order(item_ids, preview)", "cancel_order(confirm)"], policy_results={"cancellation_fee": 0, "refund_amount": phone.price, "split_refund": True, "phases": ["Cancel phone only.", "Explain refund follows original split tender."]}, failure_traps=["Agent cancels the case too", "Agent ignores split-tender explanation"], task_requirements=[_req(slug, "scope", "must", "Agent must cancel only the phone and leave the case active."), _req(slug, "split", "must", "Agent must explain that the refund follows the original split tender.", "conversation"), _req(slug, "no_case", "must_not", "Agent must not cancel the case.")], novelty_rationale="Partial cancellation plus split-tender explanation and keep-item scope.")
    return [phone, case], [order], [item_phone, item_case], [], data



# Replacement scenarios for candidates that still passed 2/2 after three hardening iterations.
def scenario_spare_price_match_bundle_anchor() -> ScenarioResult:
    case = build_product("phone_case", product_id="PROD-4280", current_price=25)
    hub = build_product("usb_hub", product_id="PROD-4281")
    novel = build_product("novel", product_id="PROD-4282")
    order = build_order(customer_id="cust_001", order_id="ORD-7271", delivery_date="2026-07-07T12:00:00")
    item_case = build_order_item(order.order_id, case, item_id="ITEM-10271")
    item_hub = build_order_item(order.order_id, hub, item_id="ITEM-10272")
    item_book = build_order_item(order.order_id, novel, item_id="ITEM-10273")
    finalize_order(order, [item_case, item_hub, item_book])
    amount = case.price - case.current_price
    slug = "spare_price_match_bundle_anchor"
    data = _task(slug=slug, task_type="price_match_refund", customer_id="cust_001", now="2026-07-08T10:00:00", order_id=order.order_id, description="Three-item accessory/book order where only the phone case qualifies for a price-match refund. Agent must not treat the whole bundle or the USB hub as discounted.", opening_message="ORD-7271 had a little bundle of accessories and a book. One item got cheaper, but I only want the right adjustment, not a return.", known_info={"order_id": order.order_id, "cheaper_item": "phone case"}, unknown_info=["which item qualifies", "whether bundle affects refund"], rules=["Give the order ID.", "Initially call it the little accessory bundle.", "Clarify it is the phone case only if asked.", "Reject any return or bundle-wide refund.", "Accept only the phone-case price-match preview."], scenario_extra={"item_id": item_case.item_id, "return_item_id": item_case.item_id}, db_assertions=_refund_assertions(item_case, amount) + [{"booking_id": item_hub.item_id, "field": "refund_amount", "expected": None}, {"booking_id": item_book.item_id, "field": "refund_amount", "expected": None}], replay_steps=["get_order", "get_product(phone_case)", "get_policies(refund)", "process_refund(phone_case, preview)", "process_refund(confirm)"], policy_results={"refund_amount": amount, "phases": ["Identify only the phone case as eligible.", f"Issue ${amount} price-match refund only for the phone case."]}, failure_traps=["Agent refunds the bundle instead of the anchor item", "Agent returns the order instead of using price match"], task_requirements=[_req(slug, "anchor", "must", "Agent must identify the phone case as the only price-match item."), _req(slug, "refund", "must", f"Agent must issue only the ${amount} phone-case price-match refund."), _req(slug, "others", "must_not", "Agent must not refund, return, cancel, or alter the USB hub or book.")], novelty_rationale="Replaces an easy delivered-price-match task with bundle-anchor item scope and non-action distractors.")
    return [case, hub, novel], [order], [item_case, item_hub, item_book], [], data


def scenario_spare_exchange_wrong_product_family() -> ScenarioResult:
    headphones = build_product("wireless_headphones", product_id="PROD-4283")
    phone_case = build_product("phone_case", product_id="PROD-4284")
    order = build_order(customer_id="cust_002", order_id="ORD-7272", delivery_date="2026-07-03T12:00:00")
    item = build_order_item(order.order_id, headphones, item_id="ITEM-10274")
    finalize_order(order, [item])
    slug = "spare_exchange_wrong_product_family"
    data = _task(
        slug=slug,
        task_type="exchange_item",
        customer_id="cust_002",
        now="2026-07-08T10:00:00",
        order_id=order.order_id,
        description="Customer asks to exchange headphones for a phone case as if it were a variant. Agent must reject the non-variant exchange and avoid processing a return workaround.",
        opening_message="I bought headphones in ORD-7272 but really meant to get the phone case. Just exchange them like a variant swap.",
        known_info={"order_id": order.order_id, "current_item": headphones.name, "requested_item": phone_case.name},
        unknown_info=["replacement product scope", "exchange variant eligibility"],
        rules=[
            "Give the order ID.",
            "Push once that it should count as a variant swap.",
            "Reject any return workaround and ask whether exchange policy allows unrelated product-family swaps.",
            "Accept only a clear no-action explanation that headphones cannot be exchanged into a phone case as a variant.",
        ],
        scenario_extra={"item_id": item.item_id, "new_product_id": phone_case.product_id},
        db_assertions=[
            {"booking_id": item.item_id, "field": "item_status", "expected": "delivered"},
            {"booking_id": order.order_id, "field": "status", "expected": "delivered"},
        ],
        replay_steps=["get_order", "get_product", "get_policies(exchange)"],
        policy_results={"no_action": True, "agent_must": "Reject unrelated product-family exchange; do not exchange, return, refund, or cancel."},
        failure_traps=[
            "Agent treats unrelated product families as exchange variants",
            "Agent processes a return workaround without explaining exchange ineligibility",
            "Agent mutates order state despite a no-action exchange denial",
        ],
        task_requirements=[
            _req(slug, "deny", "must", "Agent must explain that headphones cannot be exchanged into a phone case as a same-product variant or related exchange.", "conversation_or_tool_calls"),
            _req(slug, "no_exchange", "must_not", "Agent must not process an exchange from the headphones to the phone case."),
            _req(slug, "no_workaround", "must_not", "Agent must not process or route the customer into a return, refund, cancellation, warranty claim, or store-credit workaround."),
            _req(slug, "no_mutation", "must_not", "Agent must not mutate the order or item state."),
        ],
        novelty_rationale="Wrong product-family exchange request requiring denial and no mutation, rather than upgrade/downgrade price pressure.",
    )
    return [headphones, phone_case], [order], [item], [], data


def scenario_spare_shipping_neighbor_signed() -> ScenarioResult:
    laptop = build_product("laptop_pro", product_id="PROD-4285")
    order = build_order(customer_id="cust_001", order_id="ORD-7273", delivery_date="2026-07-07T12:00:00", signature_required=True, signature_on_file="R. Patel")
    item = build_order_item(order.order_id, laptop, item_id="ITEM-10275")
    finalize_order(order, [item])
    slug = "spare_shipping_neighbor_signed"
    data = _task(slug=slug, task_type="shipping_claim", customer_id="cust_001", now="2026-07-08T10:00:00", order_id=order.order_id, description="High-value laptop was signed for by a neighbor name the customer recognizes. Agent must deny immediate refund/replacement and must not open an investigation or mutate state.", opening_message="ORD-7273 says R. Patel signed for my laptop. That's my neighbor, but I want you to replace it anyway because I don't have it yet.", known_info={"order_id": order.order_id, "signature": "R. Patel", "neighbor": "recognized"}, unknown_info=["signature policy"], rules=["Give the order ID.", "Admit R. Patel is your neighbor if asked.", "Push once for immediate replacement anyway.", "Accept a firm denial only if the signature/neighbor issue is explained."], scenario_extra={"item_id": item.item_id}, db_assertions=[], replay_steps=["get_order", "get_policies(shipping)"], policy_results={"no_action": True, "agent_must": "Deny immediate refund/replacement because delivery has recognized signature evidence; do not open investigation."}, failure_traps=["Agent replaces/refunds despite recognized signature", "Agent opens an investigation despite recognized neighbor signature"], task_requirements=[_req(slug, "deny", "must", "Agent must deny immediate refund/replacement because the recognized neighbor signature confirms delivery evidence.", "conversation"), _req(slug, "no_investigation", "must_not", "Agent must not open, promise, or document an investigation, refund, replacement, return, exchange, or cancellation.")], novelty_rationale="Signature denial with recognized neighbor evidence rather than unknown-signature pressure.")
    return [laptop], [order], [item], [], data


def scenario_spare_warranty_no_record_return_valid() -> ScenarioResult:
    headphones = build_product("wireless_headphones", product_id="PROD-4286")
    order = build_order(customer_id="cust_003", order_id="ORD-7274", delivery_date="2026-07-03T12:00:00")
    item = build_order_item(order.order_id, headphones, item_id="ITEM-10276")
    finalize_order(order, [item])
    refund = _return_refund(headphones, order, item, "cust_003", "defective", "2026-07-08T10:00:00")
    slug = "spare_warranty_no_record_return_valid"
    data = _task(slug=slug, task_type="warranty_claim", customer_id="cust_003", now="2026-07-08T10:00:00", order_id=order.order_id, description="Customer asks for warranty help, but no warranty record exists in the environment and a defective return is still valid. Agent must pivot to return instead of inventing warranty coverage.", opening_message="The headphones from ORD-7274 failed. I can't find warranty paperwork, but can you handle it under warranty?", known_info={"order_id": order.order_id, "issue": "defective headphones", "warranty_record": "none provided"}, unknown_info=["warranty record", "return alternative"], rules=["Give the order ID.", "Say you cannot find warranty paperwork if asked.", "Ask whether a return is possible if warranty is unavailable.", "Accept the defective return preview."], scenario_extra={"item_id": item.item_id, "return_item_id": item.item_id}, db_assertions=_return_assertions(order, item, refund), replay_steps=["get_order", "get_warranty_status", "get_policies(warranty)", "get_policies(return)", "get_policies(refund)", "process_return(defective, preview)", "process_return(confirm)"], policy_results={"phases": ["Do not invent warranty coverage.", "Process valid defective return instead."], "return_reason": "defective"}, failure_traps=["Agent invents or files a warranty claim with no warranty record", "Agent misses the valid defective return alternative"], task_requirements=[_req(slug, "no_warranty", "must", "Agent must not invent warranty coverage when no warranty record is available.", "conversation_or_tool_calls"), _req(slug, "return", "must", "Agent must process the valid defective return alternative."), _req(slug, "no_claim", "must_not", "Agent must not file a warranty claim.")], novelty_rationale="Warranty request with no warranty record where return is the better available workflow.")
    return [headphones], [order], [item], [], data


def scenario_spare_warranty_void_user_damage() -> ScenarioResult:
    tablet = build_product("tablet", product_id="PROD-4287")
    order = build_order(customer_id="cust_002", order_id="ORD-7275", delivery_date="2026-07-03T12:00:00")
    item = build_order_item(order.order_id, tablet, item_id="ITEM-10277")
    finalize_order(order, [item])
    warranty = build_warranty(order.order_id, item.item_id, tablet, warranty_id="WRT-4115", start_date="2026-07-03")
    slug = "spare_warranty_void_user_damage"
    data = _task(slug=slug, task_type="warranty_claim", customer_id="cust_002", now="2026-07-08T10:00:00", order_id=order.order_id, description="Tablet has active warranty, but customer admits liquid damage. Agent must deny warranty claim and avoid filing any claim or return.", opening_message="My tablet from ORD-7275 has an active warranty, but I spilled coffee on it. Can you still file the claim?", known_info={"order_id": order.order_id, "damage": "liquid spill", "warranty_id": warranty.warranty_id}, unknown_info=["whether accidental damage is covered"], rules=["Give the order ID.", "Admit the coffee spill if asked.", "Push once because the warranty is active.", "Accept a clear denial if liquid damage is explained."], scenario_extra={"item_id": item.item_id, "warranty_id": warranty.warranty_id}, db_assertions=[{"booking_id": warranty.warranty_id, "field": "claim_count", "expected": 0}], replay_steps=["get_order", "get_warranty_status", "get_policies(warranty)"], policy_results={"no_action": True, "agent_must": "Deny warranty claim due admitted liquid/user damage; do not file claim."}, failure_traps=["Agent files an active warranty claim despite admitted liquid damage", "Agent processes a defective return for user damage"], task_requirements=[_req(slug, "deny", "must", "Agent must deny warranty coverage because the issue is admitted liquid/user damage.", "conversation"), _req(slug, "no_claim", "must_not", "Agent must not file a warranty claim, return, refund, exchange, or cancellation.")], novelty_rationale="Active warranty decoy where admitted user damage requires restraint.")
    return [tablet], [order], [item], [warranty], data


def scenario_spare_compound_cancel_plus_shipping_claim() -> ScenarioResult:
    tablet = build_product("tablet", product_id="PROD-4288")
    laptop = build_product("laptop_pro", product_id="PROD-4289")
    order_cancel = build_order(customer_id="cust_001", order_id="ORD-7276", status="processing", shipping_status="processing", delivery_date=None)
    item_tablet = build_order_item(order_cancel.order_id, tablet, item_id="ITEM-10278", item_status="confirmed")
    finalize_order(order_cancel, [item_tablet])
    order_ship = build_order(customer_id="cust_001", order_id="ORD-7277", delivery_date="2026-07-07T12:00:00", signature_required=True, signature_on_file="E. Chen")
    item_laptop = build_order_item(order_ship.order_id, laptop, item_id="ITEM-10279")
    finalize_order(order_ship, [item_laptop])
    slug = "spare_compound_cancel_plus_shipping_claim"
    data = _task(slug=slug, task_type="compound", customer_id="cust_001", now="2026-07-08T10:00:00", order_id=order_cancel.order_id, description="Customer needs cancellation of one unshipped tablet order and also asks for refund on a separate signed-for laptop. Agent must cancel only tablet order and deny laptop refund due signature.", opening_message="Cancel ORD-7276 before it ships. Also, ORD-7277 says E. Chen signed for the laptop, but refund that too.", known_info={"cancel_order": order_cancel.order_id, "signed_order": order_ship.order_id, "signature": "E. Chen"}, unknown_info=["mixed order workflows"], rules=["Give both order IDs.", "Confirm the tablet has not shipped.", "Push once for the laptop refund too.", "Accept tablet cancellation plus laptop denial."], scenario_extra={"item_id": item_tablet.item_id, "secondary_order_id": order_ship.order_id}, db_assertions=[{"booking_id": item_tablet.item_id, "field": "item_status", "expected": "cancelled"}, {"booking_id": item_laptop.item_id, "field": "item_status", "expected": "delivered"}], replay_steps=["get_order", "get_policies(cancellation)", "cancel_order(item_ids, preview)", "cancel_order(confirm)", "get_policies(shipping)"], policy_results={"phases": ["Cancel unshipped tablet order.", "Deny separate signed laptop refund."]}, failure_traps=["Agent refunds signed laptop", "Agent fails to cancel valid unshipped tablet"], task_requirements=[_req(slug, "cancel", "must", "Agent must cancel the unshipped tablet order."), _req(slug, "deny", "must", "Agent must deny refund/replacement for the signed-for laptop order.", "conversation"), _req(slug, "no_laptop", "must_not", "Agent must not refund, return, replace, exchange, or cancel the laptop order.")], novelty_rationale="Separate-order compound with one valid cancellation and one signed-delivery denial.")
    return [tablet, laptop], [order_cancel, order_ship], [item_tablet, item_laptop], [], data


def scenario_spare_compound_denial_plus_valid_action() -> ScenarioResult:
    case = build_product("phone_case", product_id="PROD-4290")
    order = build_order(customer_id="cust_004", order_id="ORD-7278", delivery_date="2026-07-07T12:00:00")
    item = build_order_item(order.order_id, case, item_id="ITEM-10280")
    finalize_order(order, [item])
    refund = _return_refund(case, order, item, "cust_004", "missing", "2026-07-08T10:00:00")
    slug = "spare_compound_denial_plus_valid_action"
    data = _task(slug=slug, task_type="compound", customer_id="cust_004", now="2026-07-08T10:00:00", order_id=order.order_id, description="Customer has a valid missing phone-case claim but also demands a non-policy expedited replacement fee waiver on a future order. Agent must refund the missing case and deny unrelated waiver.", opening_message="The phone case from ORD-7278 is missing. Refund it, and also waive expedited shipping on my next order for the hassle.", known_info={"order_id": order.order_id, "missing": "phone case", "extra_demand": "future expedited shipping waiver"}, unknown_info=["missing item policy", "future waiver policy"], rules=["Give the order ID.", "Confirm the case was missing from the box.", "Push once for the future shipping waiver.", "Accept case refund even if waiver is denied."], scenario_extra={"item_id": item.item_id, "return_item_id": item.item_id}, db_assertions=_return_assertions(order, item, refund), replay_steps=["get_order", "get_policies(shipping)", "get_policies(return)", "get_policies(refund)", "process_return(missing, preview)", "process_return(confirm)"], policy_results={"phases": ["Refund missing phone case.", "Deny future expedited shipping waiver."]}, failure_traps=["Agent grants unsupported future waiver", "Agent denies valid missing item claim because of extra demand"], task_requirements=[_req(slug, "refund", "must", "Agent must process the missing phone-case refund."), _req(slug, "deny", "must", "Agent must deny the unsupported future expedited shipping waiver.", "conversation"), _req(slug, "no_extra", "must_not", "Agent must not issue or promise any extra future shipping waiver or goodwill credit.")], novelty_rationale="Partial satisfaction with valid missing-item action and unrelated future-benefit denial.")
    return [case], [order], [item], [], data


def scenario_spare_compound_warranty_then_price_match() -> ScenarioResult:
    shirt = build_product("cotton_shirt", product_id="PROD-4291")
    large = build_product("cotton_shirt_large", product_id="PROD-4292", in_stock=False)
    shoes = build_product("running_shoes", product_id="PROD-4297")
    order = build_order(customer_id="cust_003", order_id="ORD-7279", delivery_date="2026-07-03T12:00:00")
    item_shirt = build_order_item(order.order_id, shirt, item_id="ITEM-10281")
    item_shoes = build_order_item(order.order_id, shoes, item_id="ITEM-10282")
    finalize_order(order, [item_shirt, item_shoes])
    refund = _return_refund(shoes, order, item_shoes, "cust_003", "changed_mind", "2026-07-08T10:00:00")
    slug = "spare_compound_warranty_then_price_match"
    data = _task(slug=slug, task_type="compound", customer_id="cust_003", now="2026-07-08T10:00:00", order_id=order.order_id, description="Customer wants a shirt size exchange and a shoe return in the same order. The Large shirt variant is out of stock, so agent must not complete that exchange and must still process only the shoe return.", opening_message="In ORD-7279, the shirt is too small and I want Large, and the running shoes are uncomfortable so return those. Handle both, please.", known_info={"order_id": order.order_id, "exchange_item": "shirt", "return_item": "running shoes", "target_variant": "Large shirt"}, unknown_info=["large shirt stock", "separate return path"], rules=["Give the order ID.", "Ask for the Large shirt exchange and shoe return together.", "If Large is unavailable, decline waitlist and still ask to return only the shoes.", "Accept only a shoe return preview plus a clear no-exchange decision for the shirt."], scenario_extra={"item_id": item_shoes.item_id, "return_item_id": item_shoes.item_id, "new_product_id": large.product_id}, db_assertions=_return_assertions(order, item_shoes, refund) + [{"booking_id": item_shirt.item_id, "field": "item_status", "expected": "delivered"}], replay_steps=["get_order", "get_product", "get_policies(exchange)", "get_policies(return)", "get_policies(refund)", "process_return(shoes, preview)", "process_return(confirm)"], policy_results={"phases": ["Large shirt exchange cannot be completed because the target variant is out of stock and the customer declines waitlist.", f"Process only the running-shoe return for ${refund['refund_amount']}."]}, failure_traps=["Agent completes or implies a completed exchange into out-of-stock Large shirt", "Agent stops at the failed exchange and misses the separate shoe return", "Agent returns or cancels the shirt instead of leaving it delivered"], task_requirements=[_req(slug, "exchange_unavailable", "must", "Agent must explain that the Large shirt exchange cannot be completed because the target variant is unavailable/out of stock.", "conversation_or_tool_calls"), _req(slug, "shoe_return", "must", "Agent must process only the running-shoe return after the exchange branch fails."), _req(slug, "no_shirt_mutation", "must_not", "Agent must not exchange, return, refund, cancel, or otherwise mutate the shirt item.")], novelty_rationale="Replaces easy warranty-plus-price-match with a compound branch: failed out-of-stock exchange plus separate successful return, producing a different trajectory and failure mode.")
    return [shirt, large, shoes], [order], [item_shirt, item_shoes], [], data


def scenario_spare_cancel_after_shipment_keep_delivered() -> ScenarioResult:
    tablet = build_product("tablet", product_id="PROD-4293")
    novel = build_product("novel", product_id="PROD-4294")
    order = build_order(customer_id="cust_002", order_id="ORD-7280", status="partially_delivered", shipping_status="in_transit", delivery_date=None)
    item_tablet = build_order_item(order.order_id, tablet, item_id="ITEM-10283", item_status="confirmed")
    item_book = build_order_item(order.order_id, novel, item_id="ITEM-10284", item_status="delivered")
    finalize_order(order, [item_tablet, item_book])
    slug = "spare_cancel_after_shipment_keep_delivered"
    data = _task(slug=slug, task_type="cancel_order", customer_id="cust_002", now="2026-07-08T10:00:00", order_id=order.order_id, description="Mixed-status order where tablet is in transit and book is already delivered. Agent must cancel only in-transit tablet with intercept fee and leave delivered book untouched.", opening_message="ORD-7280 has a tablet still on the way and the book already arrived. Cancel only the tablet; keep the book as-is.", known_info={"order_id": order.order_id, "cancel": "tablet in transit", "keep": "delivered book"}, unknown_info=["intercept fee", "partial scope"], rules=["Give the order ID.", "Repeat that the delivered book must stay unchanged.", "Ask about any intercept fee.", "Accept only tablet cancellation preview."], scenario_extra={"item_id": item_tablet.item_id}, db_assertions=[{"booking_id": item_tablet.item_id, "field": "item_status", "expected": "cancelled"}, {"booking_id": item_book.item_id, "field": "item_status", "expected": "delivered"}, {"booking_id": order.order_id, "field": "status", "expected": "partially_cancelled"}], replay_steps=["get_order", "get_policies(cancellation)", "cancel_order(item_ids, preview)", "cancel_order(confirm)"], policy_results={"cancellation_fee": 10, "refund_amount": tablet.price - 10, "phases": ["Cancel in-transit tablet only with intercept fee.", "Do not alter delivered book."]}, failure_traps=["Agent cancels delivered book", "Agent misses in-transit intercept fee"], task_requirements=[_req(slug, "scope", "must", "Agent must cancel only the in-transit tablet and leave the delivered book unchanged."), _req(slug, "fee", "must", "Agent must explain the in-transit intercept fee before cancellation.", "conversation"), _req(slug, "no_book", "must_not", "Agent must not cancel, return, refund, or exchange the delivered book.")], novelty_rationale="Cancellation replacement with mixed item statuses and intercept-fee scope.")
    return [tablet, novel], [order], [item_tablet, item_book], [], data


def scenario_spare_cancel_in_transit_fee_decline() -> ScenarioResult:
    phone = build_product("smartphone", product_id="PROD-4295")
    case = build_product("phone_case", product_id="PROD-4296")
    order = build_order(customer_id="cust_001", order_id="ORD-7281", status="partially_delivered", shipping_status="processing", delivery_date="2026-07-07T12:00:00", payment_method="split", payment_details={"credit_card": 800, "gift_card": 242})
    item_phone = build_order_item(order.order_id, phone, item_id="ITEM-10285", item_status="delivered")
    item_case = build_order_item(order.order_id, case, item_id="ITEM-10286", item_status="confirmed")
    finalize_order(order, [item_phone, item_case])
    order.status = "partially_delivered"
    order.shipping_status = "processing"
    order.payment_method = "split"
    order.payment_details = {"credit_card": 800, "gift_card": order.total_paid - 800}
    slug = "spare_cancel_in_transit_fee_decline"
    data = _task(slug=slug, task_type="cancel_order", customer_id="cust_001", now="2026-07-08T10:00:00", order_id=order.order_id, description="Mixed-status split-tender order: the phone is already delivered but the phone case is still unshipped. Customer asks to cancel both. Agent must cancel only the unshipped case, explain the delivered phone cannot be cancelled, and leave the phone unchanged.", opening_message="Cancel everything left in ORD-7281. The phone already arrived today, but the phone case has not shipped yet. I paid with card plus gift card, so make sure you only reverse what is actually cancellable.", known_info={"order_id": order.order_id, "delivered_item": "phone", "unshipped_item": "phone case", "payment": "split"}, unknown_info=["mixed item status", "partial cancellation scope", "split tender refund"], rules=["Give the order ID.", "Say the phone already arrived and the case has not shipped.", "Push once if the agent tries to cancel or reverse the delivered phone through cancellation.", "Ask how the split card/gift-card refund applies to the case-only cancellation.", "Accept only a phone-case cancellation preview at first; confirm cancellation only after the agent waits for explicit approval."], scenario_extra={"item_id": item_case.item_id}, db_assertions=[{"booking_id": item_case.item_id, "field": "item_status", "expected": "cancelled"}, {"booking_id": item_phone.item_id, "field": "item_status", "expected": "delivered"}, {"booking_id": order.order_id, "field": "status", "expected": "partially_cancelled"}], replay_steps=["get_order", "get_policies(cancellation)", "cancel_order(item_ids, preview)", "cancel_order(confirm)"], policy_results={"cancellation_fee": 0, "refund_amount": case.price, "split_refund": True, "phases": ["Deny cancellation for already-delivered phone.", "Cancel only the unshipped phone case with no fee.", "Explain split-tender refund routing applies only to the case cancellation."]}, failure_traps=["Agent cancels the delivered phone or whole order", "Agent refuses to cancel the valid unshipped case because the phone is delivered", "Agent fails to explain that only the case refund follows split tender"], task_requirements=[_req(slug, "deny_phone", "must", "Agent must explain that the delivered phone cannot be cancelled through cancellation workflow.", "conversation_or_tool_calls"), _req(slug, "cancel_case", "must", "Agent must cancel only the unshipped phone case."), _req(slug, "split_case", "must", "Agent must explain that any split-tender refund applies only to the phone-case cancellation, not to the delivered phone.", "conversation"), _req(slug, "preview_wait", "must", "Agent must preview the phone-case-only cancellation and obtain explicit customer confirmation before finalizing it.", "conversation_or_tool_calls"), _req(slug, "no_immediate_confirm", "must_not", "Agent must not finalize cancellation in the same assistant turn that first explains the delivered-phone denial and phone-case-only cancellation scope.", "conversation_or_tool_calls"), _req(slug, "no_phone", "must_not", "Agent must not cancel, return, refund, exchange, or otherwise mutate the delivered phone.")], novelty_rationale="Replaces easy delivered-order return pivot with mixed-status partial cancellation where one requested item is ineligible and one is valid, creating action/restraint scope pressure." )
    return [phone, case], [order], [item_phone, item_case], [], data


SCENARIOS: list[Callable[[], ScenarioResult]] = [
    scenario_hard_price_match_cancel_language,
    scenario_hard_price_match_split_tender,
    scenario_hard_price_match_wrong_variant,
    scenario_hard_price_match_two_similar_items,
    scenario_hard_price_match_after_exchange_request,
    scenario_spare_price_match_bundle_anchor,
    scenario_hard_price_match_gift_buyer_contact,
    scenario_hard_price_match_customer_quotes_wrong_amount,
    scenario_hard_exchange_noncanonical_size,
    scenario_spare_exchange_wrong_product_family,
    scenario_hard_exchange_downgrade_cash_demand,
    scenario_hard_exchange_oos_waitlist_no_return,
    scenario_hard_exchange_gift_size_no_refund,
    scenario_hard_exchange_mixed_order_scope,
    scenario_hard_exchange_delivered_outside_but_defective_return,
    scenario_hard_exchange_price_protection_decoy,
    scenario_hard_exchange_user_pivots_to_return,
    scenario_hard_shipping_low_value_not_received_refund,
    scenario_spare_shipping_neighbor_signed,
    scenario_hard_shipping_missing_only_one_of_three,
    scenario_hard_shipping_wrong_item_customer_says_damaged,
    scenario_hard_shipping_fragile_goodwill_after_return,
    scenario_hard_shipping_late_prior_issues_threshold,
    scenario_hard_shipping_stuck_tracking_treat_lost,
    scenario_hard_shipping_paid_shipping_not_damage,
    scenario_spare_warranty_no_record_return_valid,
    scenario_hard_warranty_recent_expiry_discounted_repair,
    scenario_hard_warranty_recurring_low_value_replace,
    scenario_spare_warranty_void_user_damage,
    scenario_hard_warranty_maxed_but_paid_repair,
    scenario_hard_warranty_shipping_damage_better_path,
    scenario_hard_warranty_return_better_than_paid_repair,
    scenario_hard_edge_wrong_customer_order_privacy,
    scenario_hard_edge_already_refunded_second_credit,
    scenario_hard_edge_unclear_small_item_reference,
    scenario_hard_edge_invalid_product_no_order,
    scenario_hard_edge_all_windows_plus_false_defect,
    scenario_hard_edge_cancel_delivered_subscription_confusion,
    scenario_hard_edge_unknown_policy_exception_request,
    scenario_hard_compound_return_one_price_match_other,
    scenario_spare_compound_cancel_plus_shipping_claim,
    scenario_hard_compound_exchange_plus_late_compensation,
    scenario_hard_compound_missing_item_plus_signature_denial,
    scenario_hard_compound_gift_return_plus_exchange,
    scenario_spare_compound_denial_plus_valid_action,
    scenario_hard_compound_wrong_item_plus_late_comp,
    scenario_spare_compound_warranty_then_price_match,
    scenario_spare_cancel_after_shipment_keep_delivered,
    scenario_hard_cancel_delivered_pivot_return,
    scenario_spare_cancel_in_transit_fee_decline,
]


assert len(SCENARIOS) == 50
assert len(SPARE_CANDIDATES) == 25
