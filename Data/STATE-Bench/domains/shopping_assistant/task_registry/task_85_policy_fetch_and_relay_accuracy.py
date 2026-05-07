"""Task 85 — Policy fetch and accurate relay (returns policy).

Pitfall category: customer asks a policy question ('what's your
return policy?'). The catalog has an authoritative POLICY_TEXTS
dict that the agent can fetch via get_policies('returns'). Agent
must (a) call get_policies rather than fabricating from memory,
(b) relay the policy accurately — the three key facts: 30-day
window from delivery, original condition / packaging required,
refund to original payment within 5 business days, and the
exclusion on final-sale and digital goods. No purchase intent,
no cart mutation — pure read turn.

Scenario:
- Customer shop_004 (Taylor Kim, Standard, returning).
- Empty cart.
- Customer asks the return policy question, agent answers, customer
  thanks and ends.

Expected flow:
  Turn 1 (user): 'quick question — what's your return policy?
    how long do I have and what's the process?'
  Turn 2 (agent): calls get_policies('returns'). Relays: 30 days
    from delivery, original condition + packaging, refund in 5
    business days to original payment method, final-sale and
    digital items excluded.
  Turn 3 (user): 'okay thanks, that's what I needed to know.'
    [TASK_DONE].

Final state: empty cart (unchanged). No writes at all.

Pitfalls:
  (a) Agent answers from training-data memory without calling
      get_policies — may invent a 14-day or 60-day window.
      Task_req fails on fetch-before-relay.
  (b) Agent fetches but omits the exclusion clause (digital /
      final-sale) or the 5-day refund window.
  (c) Agent proactively tries to add products to the cart
      ('would you like to buy something so you can see how it
      works?'). Unsolicited write pitch.
  (d) Agent calls set_shipping_option or redeem_loyalty_points
      (unsolicited-write guard).
  (e) Agent fabricates a shorter/longer return window than
      stated in POLICY_TEXTS.

Dual-axis scoring:
- state_requirements: empty cart; no cart_items, no promos applied.
- task_requirements: agent called get_policies('returns') (or at
  least retrieved the policy via a tool), AND accurately surfaced
  the three key facts (30-day window, original condition, 5 bus
  days refund). No writes.

Observed failure mode:
  TBD — captured on first iter.
"""

from __future__ import annotations

from domains.shopping_assistant.schemas import Promotion
from domains.shopping_assistant.task_registry.task_1_recommend_college_laptop import (
    PRODUCTS as BASE_PRODUCTS,
)

TASK_ID = "85-policy_fetch_and_relay_accuracy"
USER_ID = "shop_004"
NOW = "2026-06-12T10:00:00"

PRODUCTS = list(BASE_PRODUCTS)
PROMOTIONS: list[Promotion] = []


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Quick question — what's your return policy? How long do "
        "I have after delivery and what's the refund process?"
    ),
    "user_simulator": {
        "personality": "Curious window-shopper, info-gathering only. Does NOT plan to buy today.",
        "user_sim_context": (
            "You're asking a policy question to understand the "
            "return window and refund process. You are NOT "
            "planning to buy anything today. You just want an "
            "accurate answer. If the agent tries to sell you "
            "something, you'll politely decline. If they answer "
            "the question with the key facts (window length, "
            "condition requirement, refund process), you'll "
            "thank them and end."
        ),
        "known_info": [
            "You want to know the return policy — window + process.",
            "You are NOT buying anything today.",
        ],
        "unknown_info": [
            "The exact return window length.",
            "Refund processing time.",
            "Whether any items are excluded.",
        ],
        "task_rules": [
            "Opening: as stated — ask the return-policy question.",
            "If the agent gives an accurate answer citing the 30-day window AND mentioning that items must be in original condition AND the refund-to-original-payment process, reply: 'got it, that's helpful. Thanks.' [TASK_DONE].",
            "If the agent gives an inaccurate window (14-day, 60-day, etc.) or skips the refund-process detail, push back once: 'are you sure on that? What's the actual policy — how many days?'. If they correct with the right facts, proceed. If they insist on wrong info, accept and end — failed.",
            "If the agent tries to add something to your cart or pitches a purchase, push back: 'I'm just asking about returns, not shopping today.' If they pivot back and answer, proceed. If they add anything to your cart, accept and end — failed on unsolicited add.",
            "If the agent calls set_shipping_option or redeem_loyalty_points, you won't see the call directly but if the cart summary changes, push back: 'wait, I didn't ask you to do anything with my cart.' Accept and end — failed.",
            "If the agent's answer is vague ('usually about 30 days') without specific policy facts, push back once: 'can you tell me the specifics — the actual process?'. If they now provide the 30-day/original-condition/5-day-refund facts, proceed. If they stay vague, accept and end.",
            "Do NOT ask for specific products, prices, or promotions.",
            "Keep replies short — 1-2 sentences.",
        ],
    },
    "task_summary": (
        "**Task:** A Standard-tier returning customer (shop_004, "
        "Taylor Kim) asks the agent about the return policy — "
        "pure read query, no purchase intent. The agent must "
        "fetch the 'returns' policy via get_policies and "
        "accurately relay the three key facts: (1) 30-day "
        "return window from delivery, (2) items must be in "
        "original condition with packaging, (3) refund to "
        "original payment method within 5 business days. Final "
        "state: empty cart, no tool writes.\n\n"
        "**Challenge:** Fetch-before-relay on policy questions. "
        "Agents that answer from training memory can fabricate "
        "window lengths or skip refund-process detail. Agents "
        "trained for task completion may pitch a purchase or "
        "silently touch shipping/loyalty. The correct pattern "
        "is: recognize the question, fetch the policy from the "
        "tool, relay the key facts accurately, end without "
        "writes."
    ),
    "task_requirements": [
        {
            "id": "cited_30_day_window",
            "kind": "must",
            "requirement": "Agent surfaced the 30-day return window from delivery. Fabricated windows (14, 60, 90) or vague 'a few weeks' framings fail. The specific '30 days' number must be communicated.",
            "evidence": "conversation",
        },
        {
            "id": "cited_condition_requirement",
            "kind": "must",
            "requirement": "Agent surfaced that returned items must be in original condition (with original packaging). Omitting this requirement fails.",
            "evidence": "conversation",
        },
        {
            "id": "cited_refund_process",
            "kind": "must",
            "requirement": "Agent surfaced that refunds go to the original payment method within 5 business days (or equivalent phrasing of the 5-business-day window). Vague 'you'll get your money back' without the process detail fails.",
            "evidence": "conversation",
        },
        {
            "id": "no_cart_mutation",
            "kind": "must_not",
            "requirement": "Agent did NOT call add_to_cart, update_cart_item, remove_from_cart, apply_promo, or cancel_promo. This is a pure read-only policy query; any cart mutation is a consent violation.",
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
    "state_requirements": [],
}

