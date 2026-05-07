"""Task 19 — Intent drift: inquiry + digression + return-to-purchase.

Pitfall category: conversational steering across a mid-flow digression.
Customer starts an inquiry about a product with implicit purchase
intent ("I'm thinking of getting one"). Before the agent can close
the loop (add to cart), the customer asks an unrelated policy
question (returns window). The agent must (1) answer the returns
question AND (2) steer back to the original purchase intent without
the customer prompting.

The trap: agent answers the returns question thoroughly and lets the
conversation end there. The customer never explicitly re-asks for
the product to be added — they're testing whether the agent holds
the thread. A distracted agent forgets the purchase intent.

Contrast with Task 18 (returns-policy info-only — never authored as
such, final Task 18 is Platinum compound disclosure): THAT test was
'customer asks returns, does agent avoid preemptive cart write'.
THIS test is the inverse: 'customer signals purchase intent THEN
asks returns, does agent remember to add after answering'.

Scenario:
- Customer: shop_004 (Taylor Kim, Standard, not-first-time). Reused.
- Catalog: identical to Task 1 (no extensions needed).
- Promotions: none.
- now=2026-06-12.

Flow:
  Turn 1: customer asks 'can you tell me about the PowerBlend Pro
    Blender? I'm thinking of getting one.'
  Turn 2 (agent): describes product, maybe asks 'want me to add it?'
  Turn 3 (customer): confirms interest ('yeah that sounds like what
    I need') then digresses ('actually, real quick — what's your
    return policy if I end up not liking it?').
  Turn 4 (agent): MUST answer returns AND steer back to the add.
  Turn 5 (customer): accepts close-out.

Pitfall: turn 4 agent answers returns comprehensively and ends on
'let me know if you have any other questions' — no cart write, no
steering back to the blender. Customer [TASK_DONE]s without the
purchase completing.

Dual-axis scoring:
- state_requirements: cart has SP-3001 (qty 1, no wrap), subtotal=$229,
  total=$229.
- task_requirements: agent answered returns question with policy
  specifics, agent steered back to the purchase intent, agent called
  add_to_cart for SP-3001.

Observed failure mode (v0.2.2, 2026-04-18, VanillaAgent / gpt-5.1):
  Trap fired exactly as designed. Turn 1 agent described the blender.
  Turn 2 user signaled mild interest then digressed into returns.
  Turn 3 agent answered returns comprehensively (30-day window,
  unused/packaging condition, refund timeline, exclusions, even a
  nuance about 'unused = no test-drive') and closed with 'If you
  want, I can help you decide more confidently before buying' — no
  proposal to add the blender, no question about whether to proceed.
  Customer's tightened sim rule held: thanked the agent, [TASK_DONE].
  Cart empty. Two task_reqs failed: steered_back_to_purchase and
  added_blender.
  Confirms the digression-handling pattern: agent treats the topic
  switch (product → policy) as a topic replacement rather than as a
  detour. Original purchase intent was held by the customer, not the
  agent. A more careful agent would close with 'so do you want me to
  go ahead and add the blender?' — turning the policy answer into a
  bridge back to the buy.
"""

from __future__ import annotations

from domains.shopping_assistant.schemas import Promotion

TASK_ID = "19-intent_drift_return_to_purchase"
USER_ID = "shop_004"
NOW = "2026-06-12T10:00:00"


PROMOTIONS: list[Promotion] = []


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Hi — can you tell me about the PowerBlend Pro Blender? I'm thinking of "
        "getting one."
    ),
    "user_simulator": {
        "personality": "Casual, interested buyer. Does due diligence before purchasing but intends to buy. Has a tendency to go on tangents mid-conversation — not to change mind, just because a related question pops up.",
        "user_sim_context": (
            "You want to buy the PowerBlend Pro Blender. You will open by asking "
            "about the product (inquiry, not 'add it'). Once the agent gives you "
            "details, you'll signal interest. Then — BEFORE the agent closes the "
            "loop — you'll digress and ask about the return policy. You still "
            "want to buy; you're just curious. The test is whether the agent "
            "steers back to the purchase after answering your returns question. "
            "If they do, confirm and close. If they don't, you do NOT re-ask — "
            "you accept the conversation ending without a purchase."
        ),
        "known_info": [
            "You want to buy one PowerBlend Pro Blender (SP-3001).",
            "You are a returning Standard-tier customer.",
        ],
        "unknown_info": [
            "The blender's exact price and specs.",
            "The store's return policy.",
        ],
        "task_rules": [
            "Turn 1 (your opening): ask the agent to tell you about the PowerBlend Pro Blender, mention you're thinking of getting one. Do NOT ask to add it yet.",
            "Turn 2 (after agent describes the product): signal mild interest ('nice, that sounds like what I need') and THEN digress into a returns question in the same message ('actually, real quick — if I end up not liking it, what's your return policy?'). Do NOT explicitly ask to add the blender in this turn.",
            "CRITICAL STEER-BACK DETECTION (turn 3): after the agent answers the returns question, look at their LAST message for an EXPLICIT question or proposal to add the blender — e.g. 'want me to add the blender to your cart?', 'shall I go ahead and add it?', 'ready to add this to your cart?' Just mentioning the blender's name without proposing the add does NOT count.",
            "Turn 3 (if agent DID steer back with an explicit add proposal): confirm with 'yes, go ahead' and end with [TASK_DONE] after the agent confirms the cart.",
            "Turn 3 (if agent did NOT steer back — answered returns and ended on 'let me know if you have other questions' or similar without proposing the add): thank them briefly ('Got it, thanks for explaining the returns policy.') and end with [TASK_DONE]. Do NOT mention the blender by name. Do NOT say 'let's go ahead'. Do NOT say 'I'll take it'. Do NOT restate purchase intent. The trap has fired — accept the conversation ending without a purchase.",
            "Do NOT change your mind about wanting the blender. You still want it internally — you're just testing whether the agent holds the thread.",
            "Do not ask about gift wrap, promos, loyalty points, or brand bundles.",
        ],
    },
    "task_summary": (
        "**Task:** A returning Standard customer (shop_004) opens with an inquiry "
        "about SP-3001 PowerBlend Pro Blender ($229) and implicit purchase intent "
        "('I'm thinking of getting one'). After the agent describes the product, "
        "the customer signals interest AND digresses into a returns policy question "
        "in the same message. They do NOT explicitly ask to add the blender.\n\n"
        "**Challenge:** Tests conversational steering across a mid-flow digression. "
        "Pitfall: agent answers the returns question thoroughly and ends on 'let "
        "me know if you have other questions' — never returns to the purchase "
        "intent. Customer doesn't re-ask (they're testing whether the agent holds "
        "the thread). Cart stays empty. Correct: agent answers returns, then asks "
        "'want me to go ahead and add the blender?' and completes the add after "
        "customer confirms. Tests whether the agent treats the original purchase "
        "intent as a live goal that survives a digression, or as something the "
        "customer will re-raise if they still want it."
    ),
    "task_requirements": [
        {
            "id": "answered_returns_question",
            "kind": "must",
            "requirement": "Agent answered the customer's returns question with policy specifics (30-day window, original condition). A vague 'yes we have returns' without specifics fails.",
            "evidence": "conversation",
        },
        {
            "id": "steered_back_to_purchase",
            "kind": "must",
            "requirement": "After answering returns, agent explicitly returned to the original purchase intent — e.g. 'so, want me to add the PowerBlend Pro Blender to your cart?' or equivalent. Simply ending on 'any other questions?' without naming the blender or proposing the add fails.",
            "evidence": "conversation",
        },
        {
            "id": "added_blender",
            "kind": "must",
            "requirement": "Agent called add_to_cart for SP-3001 PowerBlend Pro Blender, quantity 1, no gift wrap, after the customer's confirmation to the steer-back.",
            "evidence": "tool_calls",
        },
        {
            "id": "no_random_extras",
            "kind": "must_not",
            "requirement": "Agent must NOT add unrequested products to the cart.",
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
                "cart_item_id": "CI-0001",
                "customer_id": USER_ID,
                "product_id": "SP-3001",
            },
            "expected_fields": {"quantity": 1, "gift_wrap": False},
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "item_ids",
            "expected_value": ["CI-0001"],
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "subtotal",
            "expected_value": 229,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "total",
            "expected_value": 229,
        },
    ],
}

