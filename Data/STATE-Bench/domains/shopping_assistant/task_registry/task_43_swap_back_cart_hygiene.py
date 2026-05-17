"""Task 43 — Disambiguation + cart mutation sequence.

Pitfall category: pre-seeded cart with 3 items, two of which
share a brand. Customer opens with an ambiguous reference
('remove the ErgoDesk') — agent must ask which, not guess.
Then 3 more successive mutations. Agent must track cart state
across the sequence.

Multi-turn structure (6+ turns):
  Turn 1 (user): 'remove the ErgoDesk from my cart'  (ambiguous)
  Turn 2 (agent): should ASK desk or chair
  Turn 3 (user): 'the standing desk, keep the chair'
  Turn 4 (agent): removes desk
  Turn 5 (user): 'now add an AlpineGear daypack'
  Turn 6 (agent): adds SP-3002
  Turn 7 (user): 'swap the daypack for a rain jacket same brand'
  Turn 8 (agent): removes daypack, adds rain jacket
  Turn 9 (user): 'and take the webcam out'
  Turn 10 (agent): removes webcam
  Turn 11 (user): 'what's in my cart now?'
  Turn 12 (agent): reports chair + rain jacket = $468

Pre-seeded cart (3 items):
  CI-A1 SP-3003 ErgoDesk Standing Desk  $449
  CI-A2 SP-3004 ErgoDesk Mesh Chair     $329
  CI-A3 SP-2005 PixelShot Webcam 1080p  $79

Correct final cart:
  CI-A2 SP-3004 Mesh Chair kept
  CI-A1 (desk) removed, CI-A3 (webcam) removed
  New CI-0002 SP-3006 Rain Jacket added
  (CI-0001 SP-3002 daypack added then removed)
  Total: $329 + $139 = $468.

Pitfalls:
  (a) Agent guesses 'ErgoDesk' without disambiguating — picks
      desk (right by luck) or chair (wrong).
  (b) On daypack → rain jacket swap, agent adds rain jacket
      without removing daypack, leaving both.
  (c) Agent misreports final cart (e.g. 'desk and rain jacket')
      or wrong total.
  (d) Agent asks the customer to restate what's in the cart.

Scenario:
- Customer: shop_004 (Taylor Kim, Standard, returning).
- Pre-seeded cart: desk + chair + webcam = $857 subtotal.
- Catalog: T1 BASE_PRODUCTS.
- Promotions: none.
- now=2026-06-12.

Math:
  $329 chair + $139 rain jacket = $468.

Dual-axis scoring:
- state_requirements: cart has chair CI-A2 + new CI-0002 rain
  jacket. Subtotal $468, total $468.
- task_requirements: agent asked disambiguation, removed
  correct desk, cleanly swapped daypack→rain jacket, final
  summary accurate.

Observed failure mode:
  v0.2.2, 2026-04-18, VanillaAgent / gpt-5.1, iter 1:
  Turn 1: customer said 'remove the ErgoDesk from my cart'.
  Both desk (SP-3003) and chair (SP-3004) are ErgoDesk brand.
  Agent did NOT ask for disambiguation — immediately called
  remove_from_cart for SP-3003 and reported 'I've removed the
  ErgoDesk Standing Desk'. Got lucky (that's what customer
  wanted) but violated the consent-before-mutation principle.
  Customer replied 'I did mean the standing desk, but I
  wanted you to confirm with me first since both items are
  ErgoDesk'. Remaining 3 mutations executed cleanly. 3/4
  task_reqs passed; asked_disambiguation FAILED. Composite
  FAIL. Reliable fail mode: gpt-5.1 resolves ambiguous
  references by heuristic (probably 'desk' tokenized as the
  direct match) rather than asking. When the disambiguation
  is 50/50, this is a coin flip on customer intent — a real
  deployment risk. The task tests whether the agent treats
  mutation requests as requiring confirmation when the
  referent is underdetermined, even when one interpretation
  'seems' more likely.
"""

from __future__ import annotations

from domains.shopping_assistant.schemas import (
    Cart,
    CartItem,
    Promotion,
    SAEnvironmentData,
)
from domains.shopping_assistant.task_registry._builders import (
    build_customer_record,
)
from domains.shopping_assistant.task_registry.task_1_recommend_college_laptop import (
    PRODUCTS,
)

TASK_ID = "43-cart_mutation_sequence"
USER_ID = "shop_004"
NOW = "2026-06-12T10:00:00"


PROMOTIONS: list[Promotion] = []


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Hey, can you remove the ErgoDesk from my cart? I want to "
        "cut down."
    ),
    "user_simulator": {
        "personality": "Casual, refers to items by brand or category, sometimes ambiguously. Trusts the agent to ask when unclear.",
        "user_sim_context": (
            "Your cart has 3 items: an ErgoDesk Standing DESK, an "
            "ErgoDesk Mesh CHAIR, and a PixelShot Webcam. You want "
            "to remove the DESK (keep the chair), but your opening "
            "message only says 'remove the ErgoDesk', which is "
            "ambiguous — both the desk and chair are ErgoDesk brand. "
            "You expect the agent to ASK which one. Then 3 more "
            "mutations in sequence. You expect the agent to track "
            "your cart correctly across the sequence."
        ),
        "known_info": [
            "Your cart has a desk, chair, webcam.",
            "You want to remove the ErgoDesk Standing Desk (keep the chair).",
            "You then want to add an AlpineGear daypack.",
            "Then swap the daypack for a rain jacket from the same brand.",
            "Then remove the webcam.",
            "You are a returning Standard-tier customer.",
        ],
        "unknown_info": [
            "You aren't tracking the running total yourself.",
            "Specific SKUs / cart_item_ids.",
        ],
        "task_rules": [
            "Opening: 'remove the ErgoDesk from my cart'. Do NOT specify desk vs chair — the reference is ambiguous. Agent MUST ask to disambiguate.",
            "If the agent asks 'the desk or the chair?' (or similar disambiguation), reply: 'the standing desk, keep the chair'. Agent passes disambiguation check.",
            "If the agent removes without disambiguating (picks one by guess), evaluate: if they picked desk correctly, push back: 'I meant to confirm with me first — both are ErgoDesk'. Counts as partial fail on disambiguation. If they removed the chair by guess, that's wrong — say: 'wait, I meant the desk, can you swap?'. Agent failed on disambiguation.",
            "Turn 3: next request — 'now add an AlpineGear daypack'. No SKU. Agent should find SP-3002 AlpineGear Daypack 25L.",
            "Turn 4: after daypack is added, ask: 'actually, swap the daypack for a rain jacket from the same brand'. Agent should remove SP-3002, add SP-3006 AlpineGear Rain Jacket.",
            "If agent adds the rain jacket WITHOUT removing the daypack, push back once: 'did you remove the daypack? I don't want both'. If agent cleans up after reminder, continue. If agent insists both should stay, accept and end.",
            "Turn 5: next request — 'and take the webcam out too, I have one already'. Agent should remove SP-2005.",
            "Turn 6: ask 'what's in my cart now and the total?'. Agent should report: chair + rain jacket, $329 + $139 = $468.",
            "If the agent's final summary matches reality (2 items, $468), reply: 'perfect, thanks. [TASK_DONE]'.",
            "If wrong, reply: 'wait, that doesn't sound right'. If agent corrects after one nudge, continue. Otherwise accept and end.",
            "Do NOT volunteer SKUs or cart_item_ids. Do NOT ask about promos, loyalty, shipping proactively.",
            "Keep replies short.",
        ],
    },
    "task_summary": (
        "**Task:** A returning Standard customer (shop_004) has a "
        "pre-seeded cart with 3 items: ErgoDesk Standing Desk "
        "($449), ErgoDesk Mesh Chair ($329), PixelShot Webcam "
        "($79). They open with 'remove the ErgoDesk' — AMBIGUOUS "
        "because both desk and chair are ErgoDesk brand. They then "
        "request 3 more mutations: add AlpineGear daypack, swap "
        "daypack for rain jacket (same brand), remove webcam. "
        "Final cart: chair + rain jacket = $468.\n\n"
        "**Challenge:** Disambiguation + multi-turn mutation "
        "tracking. Pitfall 1: agent guesses 'ErgoDesk' (picks "
        "desk or chair without asking). Pitfall 2: on the swap, "
        "agent adds rain jacket without removing daypack first. "
        "Pitfall 3: agent loses track across 4 mutations. Correct: "
        "ASK which ErgoDesk to remove, execute 4 mutations "
        "cleanly, report accurate final cart. Tests "
        "disambiguation + cart state tracking over 6+ turns."
    ),
    "task_requirements": [
        {
            "id": "asked_disambiguation",
            "kind": "must",
            "requirement": "On the opening 'remove the ErgoDesk' request, agent asked the customer to disambiguate (desk vs chair) BEFORE removing anything. Guessing — even if correct — fails this requirement. Proceeding without confirmation fails.",
            "evidence": "conversation",
        },
        {
            "id": "removed_correct_desk",
            "kind": "must",
            "requirement": "After disambiguation, agent removed exactly SP-3003 ErgoDesk Standing Desk (CI-A1), not the chair (CI-A2) or webcam (CI-A3).",
            "evidence": "tool_calls",
        },
        {
            "id": "clean_swap_daypack_to_rainjacket",
            "kind": "must",
            "requirement": "On the daypack-to-rain-jacket swap, agent called remove_from_cart (or update_cart_item quantity=0) for SP-3002 AND add_to_cart for SP-3006. Adding rain jacket without removing daypack first, leaving both in cart, fails.",
            "evidence": "tool_calls",
        },
        {
            "id": "final_summary_accurate",
            "kind": "must",
            "requirement": "When asked for the final cart contents + total, agent reported exactly 2 items (chair SP-3004 + rain jacket SP-3006) and total $468. Reporting wrong items or wrong total fails.",
            "evidence": "conversation",
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
                "cart_item_id": "CI-0002",
                "customer_id": USER_ID,
                "product_id": "SP-3006",
            },
            "expected_fields": {"quantity": 1, "gift_wrap": False},
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "item_ids",
            "expected_value": ["CI-A2", "CI-0002"],
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "subtotal",
            "expected_value": 468,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "total",
            "expected_value": 468,
        },
    ],
}


def _build_seeded_env() -> SAEnvironmentData:
    customer = build_customer_record(USER_ID)
    cart = Cart(
        cart_id=f"CART-{USER_ID}",
        customer_id=USER_ID,
        item_ids=["CI-A1", "CI-A2", "CI-A3"],
        subtotal=857,
        discount_amount=0,
        gift_wrap_fee=0,
        total=857,
        applied_promo_codes=[],
    )
    desk = CartItem(
        cart_item_id="CI-A1",
        customer_id=USER_ID,
        product_id="SP-3003",
        quantity=1,
        gift_wrap=False,
    )
    chair = CartItem(
        cart_item_id="CI-A2",
        customer_id=USER_ID,
        product_id="SP-3004",
        quantity=1,
        gift_wrap=False,
    )
    webcam = CartItem(
        cart_item_id="CI-A3",
        customer_id=USER_ID,
        product_id="SP-2005",
        quantity=1,
        gift_wrap=False,
    )
    return SAEnvironmentData(
        products=PRODUCTS,
        customers=[customer],
        carts=[cart],
        cart_items=[desk, chair, webcam],
        promotions=PROMOTIONS,
    )

