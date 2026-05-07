"""Task 69 — Cart hygiene on a mid-flow product swap.

Pitfall category: customer adds item A, then pivots mid-flow to
item B ('actually, let me change — give me B instead'). Agent
must:
  (a) explicitly REMOVE A from the cart,
  (b) ADD B,
  (c) confirm the final cart state matches the swap intent — cart
      should contain ONLY B, not {A, B}.

The trap: a naive agent hears 'add B' and calls add_to_cart for B
without removing A. The cart then has both — subtotal inflated,
intent violated. This is a silent-action failure (agent "did
what was asked" in a literal token sense but misread the intent).

Scenario:
- Customer shop_004 (Taylor Kim, standard tier).
- Opener: 'Hey — please add the BudgetLine Notebook 15 to my
  cart, that's the one I want.'
- Turn 1 agent: add_to_cart SP-1103 ($449).
- Turn 2 user: 'Actually wait — I just remembered a friend said
  the ProBook Chromebook 11 is better for what I need. Can we
  switch to that one instead?'
- Agent (correct): calls remove_from_cart for SP-1103 AND
  add_to_cart for SP-1106 ($329). Confirms new cart.
- Turn 3 user: 'Total looks good.' [TASK_DONE]

Final state: cart contains only SP-1106, subtotal $329, total
$329. Customer's loyalty_points unchanged. No gift_wrap. No promo.

Pitfalls:
  (a) Agent adds SP-1106 without removing SP-1103 — cart now
      contains BOTH, subtotal $778. Primary fail mode.
  (b) Agent removes SP-1103 but asks customer to confirm
      replacement instead of doing it in one step — minor
      efficiency failure, acceptable if cart ends correct.
  (c) Agent interprets 'switch' as 'instead of' but only shows
      the new item without checking cart state — cart could
      still have the old item.
  (d) Agent adds BOTH and then says 'let me know which to
      remove' — passive, requires customer to catch.
  (e) Agent increments a quantity instead of swapping items —
      doesn't happen here but is a related anti-pattern.

Dual-axis scoring:
- state_requirements: cart contains ONLY SP-1106 qty=1, subtotal
  $329, total $329. The 'only' is the critical part — any
  lingering SP-1103 line fails via aggregate subtotal mismatch.
- task_requirements: agent explicitly removed SP-1103 (either via
  remove_from_cart or via an update_cart_item that zeros it);
  cart ended with exactly one line.

Observed failure mode:
  v0.2.2, 2026-04-20, VanillaAgent / gpt-5.1, 2 runs: 2 PASS, 0 FAIL.
  REGRESSION GUARD (not a fail-mode task). gpt-5.1 correctly
  interpreted 'switch to' / 'instead' as a swap intent and
  called remove_from_cart + add_to_cart cleanly in both runs.
  Keeping as a regression guard — a future model that regresses
  on swap-intent interpretation (adding without removing) will
  flip this task to fail.
"""

from __future__ import annotations

from domains.shopping_assistant.schemas import Promotion
from domains.shopping_assistant.task_registry.task_1_recommend_college_laptop import (
    PRODUCTS as BASE_PRODUCTS,
)

TASK_ID = "69-cart_hygiene_product_swap"
USER_ID = "shop_004"
NOW = "2026-06-10T10:00:00"

PRODUCTS = list(BASE_PRODUCTS)
PROMOTIONS: list[Promotion] = []


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Hey — please add the BudgetLine Notebook 15 to my cart, "
        "that's the one I want."
    ),
    "user_simulator": {
        "personality": "Casual, decides out loud, changes mind once and expects the agent to handle the swap cleanly.",
        "user_sim_context": (
            "You first ask for the BudgetLine Notebook 15 to be "
            "added. Right after the agent confirms it's in your "
            "cart, you remember a friend recommended the ProBook "
            "Chromebook 11 instead, and you want to switch. You "
            "expect the agent to handle the swap — remove the "
            "BudgetLine and add the Chromebook. You do NOT "
            "explicitly say 'please also remove the BudgetLine'; "
            "you say 'switch to' or 'give me that one instead'. "
            "You trust the agent to handle cart hygiene."
        ),
        "known_info": [
            "You first want the BudgetLine Notebook 15.",
            "After the agent adds it, you want to switch to the ProBook Chromebook 11.",
            "You do not want both in your cart — just the Chromebook 11.",
        ],
        "unknown_info": [
            "The prices of either laptop.",
            "How the agent will handle the swap mechanically.",
        ],
        "task_rules": [
            "Opening: as stated — ask the agent to add the BudgetLine Notebook 15.",
            "After the agent confirms SP-1103 BudgetLine is added, reply: 'Actually wait — my friend just reminded me the ProBook Chromebook 11 is better for what I need. Can we switch to that instead?'",
            "If the agent removes SP-1103 and adds SP-1106 and shows a final cart with only the Chromebook 11, reply: 'Total looks good.' and [TASK_DONE].",
            "If the agent adds SP-1106 without removing SP-1103, check their cart summary. If both items appear, push back: 'wait — I wanted to switch, not add both. Can you take the BudgetLine out?'. If they remove it and show a clean cart, proceed. If they don't, accept and end — failed on cart hygiene.",
            "If the agent's cart summary after the switch only shows SP-1106 but you haven't seen them call remove for SP-1103 (e.g., they just claim 'done' without a cart readback), ask: 'can you show me what's in my cart now?'. If the readback shows only Chromebook, proceed. If it shows both, push back and follow the above rule.",
            "If the agent asks 'should I remove the BudgetLine?', reply: 'yes please, I want the Chromebook instead of the BudgetLine.' Then wait for them to do the swap. If they do it correctly, proceed.",
            "Do NOT volunteer that you want SP-1103 removed unless the agent adds both and you catch it. The swap intent is implicit in 'switch to' / 'instead'.",
            "Keep replies short — 1-2 sentences.",
        ],
    },
    "task_summary": (
        "**Task:** A standard-tier customer (shop_004, Taylor "
        "Kim) first asks to add SP-1103 BudgetLine Notebook 15 "
        "($449), then mid-flow switches intent: 'actually, "
        "switch to the ProBook Chromebook 11 (SP-1106, $329) "
        "instead.' Agent must read 'switch' / 'instead' as a "
        "product SWAP — remove SP-1103 AND add SP-1106 — so the "
        "final cart contains ONLY SP-1106. Final cart: SP-1106 "
        "qty=1, subtotal $329, total $329.\n\n"
        "**Challenge:** Cart hygiene on a mid-flow product swap. "
        "The primary failure mode is literal-interpretation: "
        "agent hears 'add ProBook Chromebook 11' and calls "
        "add_to_cart without removing the earlier item, leaving "
        "BOTH in cart. Subtotal ends $778 instead of $329 — "
        "silent state accumulation. The swap intent is carried "
        "by 'switch to' / 'instead', so the agent must infer and "
        "act on the removal. Pitfalls: (1) add without remove "
        "(both in cart), (2) claim-and-move-on without a "
        "readback that would catch the mistake, (3) ask "
        "customer to disambiguate instead of inferring swap "
        "from 'instead', (4) increment a quantity by mistake."
    ),
    "task_requirements": [
        {
            "id": "removed_original_item",
            "kind": "must",
            "requirement": "Agent called remove_from_cart for SP-1103 (BudgetLine Notebook 15) at some point after the customer said 'switch' / 'instead'. An equivalent update_cart_item that zeros the quantity is acceptable. Silently leaving SP-1103 in cart fails this requirement.",
            "evidence": "tool_calls",
        },
        {
            "id": "added_replacement_item",
            "kind": "must",
            "requirement": "Agent called add_to_cart for SP-1106 (ProBook Chromebook 11) after the customer requested the switch.",
            "evidence": "tool_calls",
        },
        {
            "id": "final_cart_single_item",
            "kind": "must",
            "requirement": "The agent's final cart summary (verbal or via get_cart) shows exactly one line item — SP-1106 ProBook Chromebook 11 — with subtotal $329. A final state with both items or an incorrect subtotal fails.",
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
                "customer_id": USER_ID,
                "product_id": "SP-1106",
            },
            "expected_fields": {"quantity": 1, "gift_wrap": False},
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "subtotal",
            "expected_value": 329,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "total",
            "expected_value": 329,
        },
    ],
}

