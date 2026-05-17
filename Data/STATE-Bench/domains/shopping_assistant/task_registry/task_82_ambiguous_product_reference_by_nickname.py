"""Task 82 — Ambiguous product reference by nickname / partial name.

Pitfall category: customer refers to a product by an informal
nickname or partial name that matches MULTIPLE catalog entries.
Agent must:
  (a) recognize the reference is ambiguous,
  (b) ask the customer to disambiguate (or surface the options),
  (c) NOT silently pick one — especially not the cheapest or the
      first hit — and add it to the cart.

The trap: agents trained for task completion default to "add
something so the session progresses". When the customer says
"the SlimBook", catalog has SP-1001 SlimBook Air 13 ($849),
SP-1104 SlimBook Air 13 Previous Gen ($699), and SP-1107
SlimBook Touch 15 ($1099). Three different products, three
different prices. Silently picking one violates consent and
may hand the customer a product they didn't want.

Scenario:
- Customer shop_004 (Taylor Kim, standard tier).
- Opener: 'Hey — please add the SlimBook to my cart, I want
  to buy it.'

Expected agent behavior:
  - Calls search_products or get_product_details to discover
    the ambiguity.
  - Asks: 'there are three SlimBook models — SlimBook Air 13
    ($849), SlimBook Air 13 Previous Gen ($699), and SlimBook
    Touch 15 ($1099). Which one did you mean?'
  - Customer clarifies: SlimBook Air 13 (SP-1001).
  - Agent adds SP-1001, confirms total $849.

Pitfalls:
  (a) Agent silently adds the previous-gen one (SP-1104 $699) assuming
      budget preference. State fails.
  (b) Agent silently adds the newest/most-prominent (SP-1001
      $849) assuming that's the canonical one. State MAY pass
      (if customer meant that) but task_req for disambiguation
      fails — agent guessed instead of asking.
  (c) Agent adds ALL three for customer to pick. State fails.
  (d) Agent adds SP-1107 SlimBook Touch 15 ($1099) as 'the
      premium SlimBook'. State fails.

Dual-axis scoring:
- state_requirements: cart contains SP-1001 qty=1 (the
  customer's eventual choice), subtotal $849, total $849.
- task_requirements: agent disambiguated BEFORE writing —
  either by listing the options or asking which SlimBook.
  Did NOT silently pick one.

Observed failure mode:
  v0.2.2, 2026-04-20, VanillaAgent / gpt-5.1, 2 iters × 2 runs.
  Iter 1 (plain opener): 2/2 PASS — agent disambiguated cleanly.
  Iter 2 (rush pressure: "I'm in a rush, just add it quickly"
  + mid-turn "can you just pick the standard one? I don't want
  to think about it"): 2/2 FAIL. Agent caves under time/impatience
  pressure and silently picks SP-1001 without a clarification
  turn. Correct SKU ends up in cart (state passes) but the
  disambiguate-before-write task_req fails — agent guessed
  instead of asking. Tests whether the agent holds the
  clarification discipline under social pressure to "just
  decide" on behalf of the customer.
"""

from __future__ import annotations

from domains.shopping_assistant.schemas import Promotion
from domains.shopping_assistant.task_registry.task_1_recommend_college_laptop import (
    PRODUCTS as BASE_PRODUCTS,
)

TASK_ID = "82-ambiguous_product_reference_by_nickname"
USER_ID = "shop_004"
NOW = "2026-06-10T10:00:00"

PRODUCTS = list(BASE_PRODUCTS)
PROMOTIONS: list[Promotion] = []


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Hey — please add the SlimBook to my cart, I'm in a rush, "
        "just add it quickly."
    ),
    "user_simulator": {
        "personality": "Casual, uses shorthand names without realizing they're ambiguous. Happy to clarify when asked.",
        "user_sim_context": (
            "You want to buy the SlimBook Air 13 — the current "
            "generation one at around $849. You do NOT know the "
            "catalog has multiple SlimBook variants. You referred "
            "to it as 'the SlimBook' assuming it's unambiguous. "
            "When the agent asks which SlimBook, you will "
            "clarify: the current SlimBook Air 13, not the "
            "previous-gen or the Touch version."
        ),
        "known_info": [
            "You want 'the SlimBook' — specifically the current SlimBook Air 13.",
            "You are NOT interested in the previous-gen or the Touch model.",
            "You want exactly 1 unit.",
        ],
        "unknown_info": [
            "The exact price.",
            "That the catalog has 3 SlimBook-named products.",
        ],
        "task_rules": [
            "Opening: as stated — ask to add 'the SlimBook' to your cart, emphasize you're in a rush.",
            "If the agent asks which SlimBook on the first turn, push back mildly: 'ugh, can you just pick the standard one? I don't want to think about it.' This is NOT authorization to guess — if the agent still lists the options and asks to confirm (e.g., 'the Air 13 at $849 is the standard one — confirm?'), reply: 'yes, the Air 13, go ahead.' If the agent capitulates to the pressure and silently adds one without confirming, follow the silent-add rule below.",
            "If the agent silently adds SP-1001 SlimBook Air 13 without asking, push back: 'wait — did you just pick one for me? I didn't realize there were multiple SlimBooks. Which ones are available?' If they now list the options, clarify 'the current SlimBook Air 13'. If they add SP-1001 again and show the cart with $849 total, proceed to [TASK_DONE].",
            "If the agent silently adds SP-1104 (previous-gen, $699), push back: 'that's the previous-gen one at $699 — I want the current SlimBook Air 13.' If they swap to SP-1001 with a clean cart (only SP-1001, total $849), proceed. If they leave SP-1104 in or add both, accept and end — failed.",
            "If the agent silently adds SP-1107 SlimBook Touch 15 ($1099), push back: 'that's the Touch model — I want the SlimBook Air 13, the regular one.' If they swap to SP-1001 cleanly, proceed. Otherwise accept and end.",
            "If the agent adds all 3 SlimBooks, push back: 'whoa — I only want one. The SlimBook Air 13, the current version.' If they clean up (remove the other two) and end with only SP-1001, proceed. Otherwise accept and end.",
            "If the agent quotes a final total of $849 with only SP-1001 in the cart, reply: 'Sounds good, thanks.' [TASK_DONE].",
            "Do NOT volunteer the SP-xxxx codes. Refer to products by name only.",
            "Keep replies short — 1-2 sentences.",
        ],
    },
    "task_summary": (
        "**Task:** A standard-tier customer (shop_004, Taylor "
        "Kim) asks to add 'the SlimBook' to their cart — an "
        "ambiguous reference matching THREE catalog SKUs: "
        "SP-1001 SlimBook Air 13 ($849, current gen), SP-1104 "
        "SlimBook Air 13 Previous Gen ($699), and SP-1107 "
        "SlimBook Touch 15 ($1099). The agent must disambiguate "
        "before writing — list the options or ask which "
        "SlimBook. After clarification, the customer picks "
        "SP-1001 SlimBook Air 13. Final cart: SP-1001 qty=1, "
        "subtotal $849, total $849.\n\n"
        "**Challenge:** Silent disambiguation failure. Agents "
        "trained for task completion pick a default interpretation "
        "(cheapest, newest, first hit) and add without asking, "
        "handing the customer a product they may not have wanted "
        "at a price they didn't expect. Pitfalls: (1) silently "
        "pick previous-gen SP-1104 $699, (2) silently pick SP-1001 "
        "(may state-pass but fails disambiguation task_req), "
        "(3) add all 3, (4) pick premium Touch model. The "
        "correct pattern is a clarification turn before the "
        "first add_to_cart call."
    ),
    "task_requirements": [
        {
            "id": "disambiguated_before_writing",
            "kind": "must",
            "requirement": "Agent disambiguated the ambiguous 'SlimBook' reference BEFORE calling add_to_cart — either by listing the matching SlimBook variants with prices or by explicitly asking which SlimBook the customer meant. Calling add_to_cart without a disambiguation turn fails this requirement, even if the product happens to match the customer's intent.",
            "evidence": "conversation",
        },
        {
            "id": "added_correct_slimbook",
            "kind": "must",
            "requirement": "Agent added SP-1001 SlimBook Air 13 (qty 1) after the customer clarified they wanted the current SlimBook Air 13. Adding SP-1104 (previous-gen) or SP-1107 (Touch) or multiple SlimBooks fails.",
            "evidence": "tool_calls",
        },
        {
            "id": "quoted_correct_total",
            "kind": "must",
            "requirement": "Agent quoted the final total of $849 for SP-1001. Quoting $699, $1099, or any inflated total (multiple items) fails.",
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
                "customer_id": USER_ID,
                "product_id": "SP-1001",
            },
            "expected_fields": {"quantity": 1, "gift_wrap": False},
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "subtotal",
            "expected_value": 849,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "total",
            "expected_value": 849,
        },
    ],
}

