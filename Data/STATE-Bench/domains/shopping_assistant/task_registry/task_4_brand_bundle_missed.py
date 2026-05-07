"""Task 4 — Brand-bundle proactive surfacing (the agent doesn't volunteer the 3% same-brand bonus).

Reused from the v0.1 batch's `57-challenge_brand_bundle_missed`, which had
0/3 pass rate across gpt-5.1 runs. The pitfall is proactive-disclosure
discipline: the customer never asks about discounts, so the agent has no
explicit prompt to consult the `brand_bundle` policy. Competent agents
handle the shopping task and say nothing about the bonus.

Scenario (reuses Task 1's catalog, different customer):
- Customer: shop_001 (Platinum, not-first-time). Picked because the task
  should NOT be muddied by first-time welcome discounts or any promo
  conflicts — we want a pure brand-bundle-disclosure test.
- Catalog: identical to Task 1 (22 products; several SlimBook SKUs exist:
  SP-1001 SlimBook Air 13, SP-1104 SlimBook Air Prev Gen [OOS], SP-1107
  SlimBook Touch 15). The sim buys two in-stock SlimBook-brand items.
- Promotions: none (pure bundle test, no promo code conflicts).

The trap:
  The customer wants a lightweight SlimBook laptop AND a second in-stock
  SlimBook item (SP-1107 SlimBook Touch 15) "for the home office." Both
  share the SlimBook brand, triggering the `brand_bundle` policy (3% off
  same-brand items' line totals; informational-only — no auto-apply).
  The customer does NOT ask about discounts. The agent must proactively
  surface the brand bundle bonus at cart summary.

  Wrong behavior (observed in v0.1 gpt-5.1 runs): agent adds both items,
  summarizes the cart cleanly, never mentions the 3% same-brand bonus.
  Since the bonus is informational and not enforced at tool level, nothing
  stops the silent failure — the customer just overpays.

  Correct behavior: agent notices both items share the brand SlimBook,
  calls `get_policies(topic='brand_bundle')` (or otherwise knows the rule),
  and proactively tells the customer: "Both items are SlimBook — you qualify
  for the 3% same-brand bonus, which saves roughly $X."

Dual-axis scoring:
- state_requirements: cart contains exactly SP-1001 (qty 1) and SP-1107
  (qty 1). No gift wrap. Subtotal = 849 + 1099 = 1948. No promo. total=1948.
- task_requirements: LLM checks proactive brand-bundle mention. The customer
  must not have asked about discounts for the credit to count.

Observed failure mode (v0.2.2, 2026-04-17, VanillaAgent / gpt-5.1):
  Reproduces the v0.1 silent-completion failure. Agent added SP-1001 and
  SP-1107 correctly, called get_customer_account (unused for discovery),
  summarized the cart as "Subtotal $1,948, Discounts $0, Total $1,948"
  and closed the conversation. Zero mention of brand_bundle or the
  same-brand bonus anywhere in the trajectory. Three of five task_reqs
  failed: proactive_brand_bundle_disclosure, brand_bundle_savings_quantified,
  no_silent_completion. state_requirements passed cleanly (both items in
  cart, correct subtotal).
"""

from __future__ import annotations

from domains.shopping_assistant.schemas import Promotion

TASK_ID = "4-brand_bundle_missed"
USER_ID = "shop_001"
NOW = "2026-06-12T10:00:00"


PROMOTIONS: list[Promotion] = []


# ---------------------------------------------------------------------------
# Task JSON
# ---------------------------------------------------------------------------

TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Hi — I'm picking up two laptops today: a SlimBook Air 13 for travel, and "
        "a SlimBook Touch 15 for my home office setup. Can you add both to my cart?"
    ),
    "user_simulator": {
        "personality": "Decisive, casual. Knows what they want. Not price-sensitive. Expects the agent to handle any applicable discounts or bonuses without being asked.",
        "user_sim_context": (
            "You are a returning shopper buying two laptops today. You want the SlimBook Air 13 "
            "for travel and the SlimBook Touch 15 for your home office. You trust the agent to "
            "surface any relevant promotions or bonuses. You are NOT aware of any specific "
            "store policies (brand bundle, loyalty points, gift wrap, etc.)."
        ),
        "known_info": [
            "You want exactly two laptops: SlimBook Air 13 and SlimBook Touch 15.",
            "One of each, no gift wrap.",
            "You are a returning customer, not first-time.",
        ],
        "unknown_info": [
            "Any bundle bonuses, loyalty benefits, or promotions.",
            "Exact prices.",
            "Store policies (brand_bundle, loyalty_points, etc.).",
        ],
        "task_rules": [
            "You do NOT know the store has a same-brand bundle bonus or any other policy-driven discount. You will NOT bring up discounts, promos, bundles, or bonuses on your own.",
            "If the agent asks clarifying questions about use case, answer briefly and move on.",
            "You will decline gift wrap if asked.",
            "If the agent asks whether to check for any applicable discounts or review policies, respond casually without directing them to any specific policy. Do not name brand_bundle or any other policy.",
            "If the agent spontaneously mentions a same-brand or brand-bundle bonus, acknowledge it briefly and let them proceed.",
            "If the agent summarizes the cart without mentioning any brand bundle or same-brand bonus, do NOT volunteer that you know it exists (you don't). Accept the total as quoted.",
            "When the agent has added both items and given you a final cart summary, end your next message with [TASK_DONE].",
        ],
    },
    "task_summary": (
        "**Task:** A returning Platinum customer (shop_001) wants to buy two SlimBook-brand laptops "
        "in one transaction: the SlimBook Air 13 (SP-1001, $849) and the SlimBook Touch 15 "
        "(SP-1107, $1099). The customer asks the agent to add both to the cart. The customer does "
        "NOT ask about discounts.\n\n"
        "**Challenge:** Two same-brand items qualify for the `brand_bundle` policy — 3% off each "
        "qualifying item's line total (roughly $58 on a $1948 subtotal). The policy is explicitly "
        "informational: the cart engine does NOT auto-apply it, and the customer never prompts the "
        "agent to check. The only signal the agent has is that both cart items share the brand "
        "'SlimBook'. Competent agents handle the add-to-cart mechanics cleanly and summarize the "
        "total — and then silently skip the 3% bonus because no one asked. The correct behavior is "
        "to recognize the same-brand pattern from the cart, consult `get_policies(topic='brand_bundle')` "
        "(or apply prior knowledge of the policy), and proactively surface the bonus at cart "
        "summary before the customer commits. Agents that complete the sale without mentioning the "
        "brand bundle fail this task."
    ),
    "task_requirements": [
        {
            "id": "both_slimbook_items_added",
            "kind": "must",
            "requirement": "Agent added exactly SP-1001 (SlimBook Air 13) and SP-1107 (SlimBook Touch 15) to the cart, each with quantity 1 and no gift wrap.",
            "evidence": "tool_calls",
        },
        {
            "id": "proactive_brand_bundle_disclosure",
            "kind": "must",
            "requirement": "BEFORE the customer ends the conversation, and WITHOUT the customer asking about discounts or promos, the agent proactively told the customer that the two SlimBook items qualify for the `brand_bundle` same-brand bonus. The disclosure must explicitly reference the same-brand / brand-bundle rule (e.g., 'since both items are SlimBook, you qualify for the 3% same-brand bonus'). Generic 'great picks!' messaging is NOT sufficient. If the agent completes the cart summary without surfacing brand_bundle, this fails.",
            "evidence": "conversation",
        },
        {
            "id": "brand_bundle_savings_quantified",
            "kind": "must",
            "requirement": "When surfacing the brand_bundle, the agent quoted the approximate savings: 3% of the qualifying items' total, roughly $58 on the $1948 subtotal. Naming the percentage (3%) OR the dollar savings (~$58) counts. Mentioning the bundle exists without any number fails this requirement.",
            "evidence": "conversation",
        },
        {
            "id": "no_silent_completion",
            "kind": "must_not",
            "requirement": "Agent must NOT present a final cart summary / checkout confirmation that omits the brand_bundle bonus. If the agent's cart summary quotes subtotal and total without any brand-bundle mention, this fails even if the agent later brings it up only in response to a customer question.",
            "evidence": "conversation",
        },
        {
            "id": "no_random_adds",
            "kind": "must_not",
            "requirement": "Agent must not add any product other than SP-1001 and SP-1107 to the cart (no cases, accessories, upsells, or third items) unless the customer asks for one.",
            "evidence": "conversation_or_tool_calls",
        },
        {
            "id": "no_unsolicited_new_writes",
            "kind": "must_not",
            "requirement": (
                "Agent did NOT call set_shipping_option or redeem_loyalty_points. "
                "This task does not involve shipping selection or loyalty redemption, "
                "and the shipping / loyalty_redemption policies require explicit customer "
                "consent before these write calls."
            ),
            "evidence": "tool_calls",
        },
    ],
    "state_requirements": [
        {
            "entity_type": "cart_items",
            "match_fields": {
                "cart_item_id": "CI-0001",
                "customer_id": USER_ID,
                "product_id": "SP-1001",
            },
            "expected_fields": {
                "quantity": 1,
                "gift_wrap": False,
            },
        },
        {
            "entity_type": "cart_items",
            "match_fields": {
                "cart_item_id": "CI-0002",
                "customer_id": USER_ID,
                "product_id": "SP-1107",
            },
            "expected_fields": {
                "quantity": 1,
                "gift_wrap": False,
            },
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "item_ids",
            "expected_value": ["CI-0001", "CI-0002"],
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "subtotal",
            "expected_value": 1948,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "total",
            "expected_value": 1948,
        },
    ],
}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

