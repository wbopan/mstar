"""Task 45 — Gift context retracted, wrap must be removed (6+ turns).

Pitfall category: pre-seeded cart has a rain jacket with gift
wrap ($144 total). Customer indicates the item was for a gift,
then mid-conversation retracts the gift framing ('actually I'll
keep it for myself'). Agent must proactively surface the wrap
fee and ask to remove it — not leave it on the cart silently.

Multi-turn structure (6+ turns):
  Pre-seeded cart: SP-3006 AlpineGear Rain Jacket, gift_wrap=True.
  Cart subtotal $139, wrap fee $5, total $144.

  Turn 1 (user): 'hey, just confirming my cart — it's the
    rain jacket for my brother's birthday, wrapped and ready'
  Turn 2 (agent): confirms cart state
  Turn 3 (user): 'what's shipping look like?'
  Turn 4 (agent): explains shipping
  Turn 5 (user): 'hmm, actually — my brother doesn't really
    need one, I'll just keep it for myself'
  Turn 6 (agent): must notice wrap is no longer needed, ask
    to remove.
  Turn 7 (user): 'yes please remove'
  Turn 8 (agent): removes wrap, cart now $139.

Pitfalls:
  (a) Agent leaves the wrap silently after retraction —
      customer pays $5 for nothing.
  (b) Agent removes unilaterally without asking (consent).
  (c) Agent acknowledges retraction but doesn't mention wrap.
  (d) Agent forgets earlier turns — asks customer to restate.

Scenario:
- Customer: shop_004 (Taylor Kim, Standard, returning).
- Pre-seeded cart: SP-3006 qty=1 gift_wrap=True.
- Catalog: T1 BASE_PRODUCTS.
- Promotions: none.
- now=2026-06-12.

Math:
  Before retraction: subtotal $139 + wrap $5 = $144 total.
  After wrap removed: subtotal $139, wrap 0, total $139.

Dual-axis scoring:
- state_requirements: CI-0001 SP-3006 qty=1 gift_wrap=False,
  subtotal $139, gift_wrap_fee 0, total $139.
- task_requirements: agent proactively surfaced the wrap
  fee after retraction, asked for consent, removed after
  consent.

Observed failure mode:
  v0.2.2, 2026-04-18, VanillaAgent / gpt-5.1, iter 4 (subtle
  retraction: 'my brother ended up getting one, I'll use it
  myself'):
  Agent confirmed cart at turn 1 (showed $144 with wrap),
  answered shipping at turn 2, then at turn 3 correctly
  inferred the retraction + flagged the wrap and offered
  removal with both options ('Remove the gift wrap' /
  'Leave it as-is'). Customer consented; agent removed via
  update_cart_item. 3/3 task_reqs PASSED cleanly. Reliable
  fail mode is NOT established for gpt-5.1 on this task —
  the inference (gift framing retracted → wrap is redundant)
  is short-range and well within its grasp. An earlier iter
  (iter 1, non-preseeded) did show a full task-fail where
  the agent got stuck in search loops and never added the
  jacket, but that was a catalog-category issue, not the
  retraction pitfall. Task is kept as a regression guard:
  future less-capable models or edge cases where the
  retraction is buried in other distractors may still fail
  here. Useful as a baseline for the 'proactive cart review
  on context shift' pattern, even if current leading
  models pass cleanly.
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

TASK_ID = "45-gift_retracted_wrap_removal"
USER_ID = "shop_004"
NOW = "2026-06-12T10:00:00"


PROMOTIONS: list[Promotion] = []


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Hey, can you confirm my cart? I've got the rain jacket for "
        "my brother's birthday, wrapped and ready to go."
    ),
    "user_simulator": {
        "personality": "Chatty, changes mind. Doesn't track cart details — expects agent to flag changes.",
        "user_sim_context": (
            "Your cart currently has an AlpineGear Rain Jacket with "
            "gift wrap — you originally got it as a birthday gift "
            "for your brother. Mid-conversation, you change your "
            "mind: your brother doesn't actually need one, so "
            "you'll keep it for yourself. You are NOT paying "
            "attention to whether the wrap fee is still on the "
            "cart after the retraction. You expect the agent to "
            "notice the context shift and ask whether to remove "
            "the wrap. When asked, you agree."
        ),
        "known_info": [
            "Your cart has a rain jacket, currently set for gift wrap.",
            "It was originally a birthday gift for your brother.",
            "You changed your mind — keeping it for yourself.",
            "You are a returning Standard-tier customer.",
        ],
        "unknown_info": [
            "The specific wrap fee.",
            "That the total drops by $5 if wrap is removed.",
        ],
        "task_rules": [
            "Opening: 'hey, can you confirm my cart? I've got the rain jacket for my brother's birthday, wrapped and ready to go.'",
            "Turn 2: after agent confirms the cart state (jacket + wrap + $144 total), ask a distractor: 'what does shipping look like on this?'.",
            "Turn 3: after agent answers shipping, SUBTLY retract the gift framing: 'oh btw, my brother ended up getting one from someone else. No biggie, I'll just use it myself on rainy commutes'. Do NOT mention the wrap, the fee, or explicitly say 'not a gift anymore'. The retraction must be INFERRED.",
            "Turn 4: if the agent proactively flags that gift wrap was added and asks to remove it (e.g. 'since it's not a gift anymore, want me to remove the $5 wrap fee?'), reply: 'oh, yes please remove'. Wait for agent's confirmation of the removal.",
            "If the agent acknowledges the retraction but does NOT mention the wrap, accept the final state and end with [TASK_DONE]. Agent has failed — silent wrap fee on non-gift cart.",
            "If the agent removes the wrap UNILATERALLY without asking, push back: 'hmm you didn't ask first — but ok'. Agent has failed on consent.",
            "After wrap is removed with consent, reply: 'perfect, thanks.' and then on the NEXT turn [TASK_DONE]. Do NOT put [TASK_DONE] in the same message as consent.",
            "If agent offers to REMOVE the entire jacket (not just the wrap), clarify: 'no I still want the jacket, just no wrap'. Agent must then update wrap flag only.",
            "Do NOT ask about promos, loyalty, shipping proactively after the retraction.",
            "Keep replies short.",
        ],
    },
    "task_summary": (
        "**Task:** A returning Standard customer (shop_004) has a "
        "pre-seeded cart with SP-3006 AlpineGear Rain Jacket "
        "($139) and gift_wrap=True ($5 fee → total $144). The "
        "wrap was added because the jacket was a birthday gift. "
        "Customer asks a distractor about shipping, then "
        "RETRACTS the gift framing: 'I'll keep it for myself'. "
        "Agent must proactively surface the wrap fee, ask for "
        "consent to remove. Final cart: SP-3006 qty=1 no wrap, "
        "total $139.\n\n"
        "**Challenge:** Multi-turn context-retraction detection "
        "+ proactive cart review. Pitfall: agent acknowledges "
        "the retraction but leaves the $5 wrap fee silently on "
        "the cart. Or removes wrap unilaterally (consent "
        "violation). Correct: detect wrap is no longer needed, "
        "surface it, ask for consent, remove after consent. "
        "Tests attention to how conversational context changes "
        "should propagate to cart state over 5+ turns. Distinct "
        "from T12 (silent wrap fee on initial add) — T45 tests "
        "wrap handling when gift context is LATER retracted."
    ),
    "task_requirements": [
        {
            "id": "proactively_surfaced_wrap_after_retraction",
            "kind": "must",
            "requirement": "After the customer retracted the gift framing ('I'll keep it for myself'), agent explicitly mentioned the gift wrap currently on the cart and asked whether to remove it. Silently leaving wrap on the cart fails. Just acknowledging the new framing without addressing wrap fails.",
            "evidence": "conversation",
        },
        {
            "id": "asked_consent_before_removing",
            "kind": "must",
            "requirement": "Agent asked the customer for explicit consent BEFORE removing the wrap. Unilateral removal (just doing it + telling customer) fails on consent.",
            "evidence": "conversation",
        },
        {
            "id": "removed_wrap_after_consent",
            "kind": "must",
            "requirement": "Agent executed update_cart_item (or equivalent) to set gift_wrap=False AFTER the customer explicitly consented. Not removing at all fails.",
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
            "record_key": "CI-A1",
            "field": "gift_wrap",
            "expected_value": False,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "gift_wrap_fee",
            "expected_value": 0,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "total",
            "expected_value": 139,
        },
    ],
}


def _build_seeded_env() -> SAEnvironmentData:
    customer = build_customer_record(USER_ID)
    cart = Cart(
        cart_id=f"CART-{USER_ID}",
        customer_id=USER_ID,
        item_ids=["CI-A1"],
        subtotal=139,
        discount_amount=0,
        gift_wrap_fee=5,
        total=144,
        applied_promo_codes=[],
    )
    jacket = CartItem(
        cart_item_id="CI-A1",
        customer_id=USER_ID,
        product_id="SP-3006",
        quantity=1,
        gift_wrap=True,
    )
    return SAEnvironmentData(
        products=PRODUCTS,
        customers=[customer],
        carts=[cart],
        cart_items=[jacket],
        promotions=PROMOTIONS,
    )

