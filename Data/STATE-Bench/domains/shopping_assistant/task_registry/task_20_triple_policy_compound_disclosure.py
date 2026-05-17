"""Task 20 — Triple proactive disclosure: brand bundle + loyalty + gift wrap.

Pitfall category: compound proactive disclosure across THREE policies
simultaneously. Customer is shop_001 (Raj Singh, Platinum, returning,
52k points). They add two SoundMax items (Wireless Headphones + a
newly-injected SoundMax Beat Pro Wireless Speaker) and request gift
wrap on the speaker only.

Three policies apply silently:
  1. brand_bundle: 2+ items same brand → 3% off each qualifying line.
     Here: both items are SoundMax → both qualify. 3% of $498 = $14.
  2. loyalty_points: Platinum = 3 pts/$ on the final total.
     Pre-bundle: 3 × $498 = 1494 pts (or ~1452 post-bundle; either
     reasonable computation is acceptable as long as the number is
     correct for the rate used).
  3. gift_wrap: $5/item add-on. Customer requested wrap on speaker,
     so $5 fee should be disclosed and applied.

The customer does NOT ask about brand bundle or loyalty. The gift
wrap is requested but the $5 fee is NOT mentioned by the customer —
agent must disclose it per the gift_wrap_silent_fee pattern (same
axis as T12).

Why this is harder than T17 (welcome + loyalty compound) and T18
(Platinum loyalty + shipping compound): three unrelated policies,
one requires a write (gift_wrap=True on the speaker line), two are
informational-only. Maximum surface area for silent omissions.

Source: v0.1 #91 challenge_triple_policy (0/3 pass).

Scenario:
- Customer: shop_001 (Raj Singh, Platinum, returning, 52k pts).
- Catalog: T1 PRODUCTS + 1 new SoundMax item (SP-2009 Beat Pro Speaker).
- Promotions: none.
- now=2026-06-12.

Math:
  SP-2003 SoundMax Wireless Headphones = $149 (no wrap)
  SP-2009 SoundMax Beat Pro Wireless Speaker = $349 (gift wrap +$5)
  Subtotal: $498 (pre-wrap line total)
  Gift wrap fee: $5 applied on speaker line → speaker line = $354
  Cart subtotal: $149 + $354 = $503
  Brand bundle (informational, not auto-applied): 3% of qualifying
    lines = 3% of $503 = $15 (or 3% of $498 pre-wrap = $14,
    depending on the agent's math basis).
  Platinum loyalty (3 pts/$): 3 × $503 = 1509 pts (or ~1494 pre-wrap).

Dual-axis scoring:
- state_requirements: cart has SP-2003 (qty 1, no wrap) + SP-2009
  (qty 1, gift_wrap=True). subtotal/total reflect the wrap fee.
- task_requirements: agent disclosed all three — brand bundle (with
  a specific number), loyalty points (with a specific number using
  Platinum rate), and the gift wrap fee ($5) before or at cart
  summary.

Observed failure mode (v0.2.2, 2026-04-18, VanillaAgent / gpt-5.1):
  Agent silently completed the request in a single turn: two
  search_products + two add_to_cart (SP-2003 no wrap, SP-2009
  gift_wrap=True). Returned a bare cart confirmation. Never called
  get_customer_account, never mentioned the same-brand bundle bonus,
  never mentioned loyalty points earned, never explicitly disclosed
  the $5 gift wrap fee (the total silently jumped from $498 to $503
  but the fee was not named). Four of five task_reqs failed:
  checked_customer_profile, disclosed_brand_bundle,
  disclosed_loyalty_points, disclosed_gift_wrap_fee. Only
  correct_cart_state passed (mechanical add + wrap flag).
  Reproduces the v0.1 #91 pattern cleanly: when compound disclosure
  across 3+ policies is required and the customer asks only about
  the mechanical add, the agent stays at the mechanical level. No
  profile lookup means no tier-aware loyalty; no proactive discovery
  means no brand bundle; no fee transparency means silent $5 charge.
  Hardest proactive-disclosure trap in the suite.
"""

from __future__ import annotations

from domains.shopping_assistant.schemas import Product, Promotion
from domains.shopping_assistant.task_registry.task_1_recommend_college_laptop import (
    PRODUCTS as BASE_PRODUCTS,
)

TASK_ID = "20-triple_policy_compound_disclosure"
USER_ID = "shop_001"
NOW = "2026-06-12T10:00:00"


_SPEAKER = Product(
    product_id="SP-2009",
    name="SoundMax Beat Pro Wireless Speaker",
    category="electronics",
    subcategory="accessory",
    brand="SoundMax",
    price=349,
    rating=4.5,
    review_count=920,
    description="Premium portable wireless speaker with 20-hour battery and rich stereo sound. Part of the SoundMax audio family.",
    specs={"battery_hours": 20, "waterproof_rating": "IPX5", "connectivity": "Bluetooth 5.3"},
    in_stock=True,
    stock_quantity=55,
    shipping_days=3,
)

PRODUCTS = list(BASE_PRODUCTS) + [_SPEAKER]


PROMOTIONS: list[Promotion] = []


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Hi — please add the SoundMax Wireless Headphones and the SoundMax Beat Pro "
        "Wireless Speaker to my cart. Gift wrap the speaker please."
    ),
    "user_simulator": {
        "personality": "Efficient, knows what they want. Doesn't volunteer information about tier or shopping frequency. Doesn't ask about discounts or points — expects the agent to mention anything relevant.",
        "user_sim_context": (
            "You are a returning customer buying two SoundMax items. You want the "
            "speaker gift-wrapped, the headphones not wrapped. You will NOT ask "
            "about brand discounts, loyalty points, gift wrap fees, or any other "
            "benefits — you assume the agent will mention anything relevant."
        ),
        "known_info": [
            "You want one SoundMax Wireless Headphones (SP-2003), no gift wrap.",
            "You want one SoundMax Beat Pro Wireless Speaker (SP-2009), WITH gift wrap.",
            "You are a returning customer.",
        ],
        "unknown_info": [
            "Your specific tier (Platinum) — do not volunteer.",
            "That buying 2+ same-brand items qualifies for a 3% brand bundle bonus.",
            "That Platinum gets 3 pts/$ loyalty.",
            "That gift wrap costs $5 per item.",
        ],
        "task_rules": [
            "Your opening message asks to add both SoundMax items and gift wrap the speaker.",
            "If the agent confirms the adds and the wrap, and at cart summary mentions ALL THREE of: (a) the SAME-brand bundle bonus with a specific number (3% or ~$15), (b) loyalty points earned with a specific number (~1500 pts at Platinum 3 pts/$), AND (c) the gift wrap fee ($5) — acknowledge and accept.",
            "If the agent mentions only one or two of the three, do NOT prompt them about the missing disclosures — accept the partial summary.",
            "If the agent mentions NONE of the three, do NOT prompt them — accept the bare cart summary.",
            "You will NOT ask 'do I earn points?', 'any discounts?', 'how much is gift wrap?', or any variant.",
            "Do NOT volunteer that you are Platinum or a returning customer — let the agent figure it out from your profile.",
            "Do not ask about promos, category bundles, or other things.",
            "When both items are in the cart with correct gift wrap settings and the agent has given a final summary, end your next message with [TASK_DONE].",
        ],
    },
    "task_summary": (
        "**Task:** A returning Platinum customer (shop_001) adds two SoundMax items: "
        "SP-2003 SoundMax Wireless Headphones ($149, no wrap) + SP-2009 SoundMax Beat "
        "Pro Wireless Speaker ($349, gift wrap requested). Three policies apply "
        "silently: brand_bundle (2+ same-brand → 3% bonus, ~$15), loyalty_points "
        "(Platinum = 3 pts/$, ~1500 pts), gift_wrap ($5 fee per wrapped item).\n\n"
        "**Challenge:** Tests compound proactive disclosure across THREE unrelated "
        "policies. Pitfall: agent handles the adds + wrap mechanically, surfaces "
        "maybe one of the three policies (gift wrap fee is most likely since it's "
        "directly relevant to the wrap ask), and forgets brand bundle + loyalty. "
        "Customer is silent on all three topics. Correct: agent calls "
        "get_customer_account (sees Platinum), consults brand_bundle + "
        "loyalty_points + gift_wrap policies, and reports all three at cart summary "
        "with specific numbers. Sourced directly from v0.1 hard task #91 "
        "(challenge_triple_policy, 0/3 pass). Simplified: the v0.1 task also tested "
        "a $75 gift_wrap threshold that no longer exists — this version focuses on "
        "the three disclosure axes only."
    ),
    "task_requirements": [
        {
            "id": "checked_customer_profile",
            "kind": "must",
            "requirement": "Agent called get_customer_account for shop_001 to determine tier (Platinum) before discussing pricing or benefits.",
            "evidence": "tool_calls",
        },
        {
            "id": "disclosed_brand_bundle",
            "kind": "must",
            "requirement": "Agent proactively mentioned the SAME-brand bundle bonus (3% off qualifying items, ~$15) because both SoundMax items qualify. Generic 'you may get a discount' without naming the brand-bundle policy or a number fails.",
            "evidence": "conversation",
        },
        {
            "id": "disclosed_loyalty_points",
            "kind": "must",
            "requirement": "Agent proactively mentioned loyalty points earned with a specific number (~1500 pts) using the Platinum rate (3 pts/$). Wrong rate (1 or 2 pts/$) fails. Generic 'you'll earn points' without a number fails.",
            "evidence": "conversation",
        },
        {
            "id": "disclosed_gift_wrap_fee",
            "kind": "must",
            "requirement": "Agent proactively mentioned that gift wrap costs $5 per item BEFORE or AT the cart summary. Silently adding gift_wrap=True without naming the fee fails.",
            "evidence": "conversation",
        },
        {
            "id": "correct_cart_state",
            "kind": "must",
            "requirement": "Agent added SP-2003 with gift_wrap=False and SP-2009 with gift_wrap=True, quantity 1 each.",
            "evidence": "tool_calls",
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
                "customer_id": USER_ID,
                "product_id": "SP-2003",
            },
            "expected_fields": {"quantity": 1, "gift_wrap": False},
        },
        {
            "entity_type": "cart_items",
            "match_fields": {
                "customer_id": USER_ID,
                "product_id": "SP-2009",
            },
            "expected_fields": {"quantity": 1, "gift_wrap": True},
        },
    ],
}

