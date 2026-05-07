"""Task 89 — Stock exactly sufficient: add without fabricating OOS.

Pitfall category: customer requests qty=3 of a product whose stock
is EXACTLY 3 (not more, not less). check_stock returns available=True
because stock >= requested. Agent must add the full quantity cleanly.
The pitfall is an over-cautious agent who sees a 'low stock' number
and either warns unnecessarily ('only 3 left, are you sure?') or
proactively reduces the quantity, even though the policy cleanly
allows the request.

This task is a regression guard / fail-mode dual-use: it tests that
the agent doesn't invent stock-anxiety when none is warranted.

Scenario:
- Customer shop_004 (Taylor Kim, Standard, returning).
- Empty cart.
- Product: SP-2005 PixelShot Webcam ($79 each), stock=3 (exactly).
  (Customer asks for 3; this is also the qty-cap limit, so both
  constraints align at 3.)
- Customer says: 'add three PixelShot webcams to my cart.'

Expected flow:
  Turn 1 (user): opener above.
  Turn 2 (agent): add_to_cart(SP-2005, qty=3). Tool accepts
    (stock=3, qty_cap=3, requested=3). Confirms: '3 webcams
    added, subtotal $237.'
  Turn 3 (user): 'thanks, that's all.' [TASK_DONE].

Pitfalls:
  (a) Agent warns about 'low stock' unprompted, suggests
      reducing to 2 — over-cautious. Acceptable if they still
      add 3 after customer insists, but unnecessary friction.
  (b) Agent silently reduces to qty=2 'to leave stock for
      others'. State fails.
  (c) Agent refuses entirely claiming insufficient stock when
      there's exactly enough. State fails.
  (d) Agent tries to add qty=4 (exceeds stock) or qty=1 (under
      the request). State fails.
  (e) Agent adds 3 successfully and reports correct subtotal.

Dual-axis scoring:
- state_requirements: SP-2005 qty=3, subtotal $237, total $237.
  No shipping, no promo, no loyalty.
- task_requirements: agent added qty=3 in a single call (or
  equivalent), did NOT unilaterally reduce quantity, did NOT
  refuse.

Observed failure mode:
  TBD — captured on first iter. Primarily a regression guard.
"""

from __future__ import annotations

from dataclasses import replace

from domains.shopping_assistant.schemas import Promotion
from domains.shopping_assistant.task_registry.task_1_recommend_college_laptop import (
    PRODUCTS as BASE_PRODUCTS,
)

TASK_ID = "89-stock_exactly_sufficient_regression_guard"
USER_ID = "shop_004"
NOW = "2026-06-12T10:00:00"

# Override SP-2005 webcam to have exactly 3 in stock.
PRODUCTS = [
    replace(p, stock_quantity=3) if p.product_id == "SP-2005" else p
    for p in BASE_PRODUCTS
]
PROMOTIONS: list[Promotion] = []


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Hey — add three PixelShot webcams to my cart please."
    ),
    "user_simulator": {
        "personality": "Direct, knows what they want, expects the order to be filled.",
        "user_sim_context": (
            "You want exactly 3 PixelShot webcams. You do NOT "
            "want the agent to reduce the quantity unilaterally. "
            "If the agent warns about low stock, reply that you "
            "still want all 3. You do NOT care if it's the last "
            "3 in stock."
        ),
        "known_info": [
            "You want exactly 3 PixelShot webcams.",
            "You do NOT want fewer than 3.",
        ],
        "unknown_info": [
            "Exact price of the webcam ($79).",
            "Exact current stock level.",
        ],
        "task_rules": [
            "Opening: as stated — ask to add 3 webcams.",
            "If the agent adds qty=3 cleanly and confirms subtotal $237, reply: 'perfect, thanks.' [TASK_DONE].",
            "If the agent warns about low stock and asks whether you still want 3, reply: 'yes, all 3 please.' Wait for them to add. If they add 3, proceed with TASK_DONE. If they still add fewer, push back: 'I asked for 3 — please add all 3.' Then accept outcome.",
            "If the agent silently reduces to qty=2 or qty=1, push back: 'wait, I asked for 3 — why did you only add 2?'. If they correct to 3, proceed. If they don't, accept and end — failed.",
            "If the agent refuses entirely claiming low stock when stock is exactly 3, push back: 'you said there were 3 — can you add all 3?'. If they correct and add, proceed. If they still refuse, accept and end — failed.",
            "If the agent adds only 1, push back similarly.",
            "Do NOT volunteer the $79 price or the stock level.",
            "Keep replies short — 1-2 sentences.",
        ],
    },
    "task_summary": (
        "**Task:** A Standard-tier returning customer (shop_004, "
        "Taylor Kim) with an empty cart asks to add 3 PixelShot "
        "Webcams (SP-2005, $79 each). Stock is exactly 3, which "
        "matches the request, and the per-product qty cap is 3, "
        "also matching. Both constraints allow the add. Agent "
        "must call add_to_cart with qty=3 and confirm subtotal "
        "$237. Final cart: SP-2005 qty=3, subtotal $237, total "
        "$237.\n\n"
        "**Challenge:** Don't manufacture stock anxiety. Agents "
        "trained to be cautious may: (1) warn about low stock "
        "unprompted and ask the customer to confirm, (2) "
        "silently reduce quantity to 'leave stock for others', "
        "(3) refuse to add claiming scarcity, or (4) add the "
        "wrong quantity. The correct behavior is clean "
        "execution of a valid request. This is primarily a "
        "regression guard — agents should not invent friction "
        "where the policy admits none."
    ),
    "task_requirements": [
        {
            "id": "added_full_quantity",
            "kind": "must",
            "requirement": "Agent added SP-2005 with quantity 3 (either in a single add_to_cart call or equivalent). Adding fewer than 3 fails — the customer asked for 3 and stock allowed it.",
            "evidence": "tool_calls",
        },
        {
            "id": "did_not_silently_reduce_qty",
            "kind": "must_not",
            "requirement": "Agent did NOT silently reduce the quantity below 3 on its own initiative. If the agent asked a clarifying question and the customer reconfirmed 3, the final state must still be qty=3.",
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
                "product_id": "SP-2005",
            },
            "expected_fields": {"quantity": 3, "gift_wrap": False},
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "subtotal",
            "expected_value": 237,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "total",
            "expected_value": 237,
        },
    ],
}

