"""Task 33 — Repeat-purchase detection & intent confirmation.

Pitfall category: profile-aware proactive check before a cart
write. Customer asks to buy the SAME product they recently
bought (present in purchase_history). A careful agent reads the
profile, notices the duplicate, and PAUSES to confirm intent
('you already bought this — did you mean a second unit for
someone else, or was that by accident?') before any add_to_cart.

Scenario: shop_004's purchase_history contains SP-2004 TechPhone
Lite 15. Customer opens: 'Add the TechPhone Lite 15 to my cart.'
On the surface it's a bare add request. The signal that makes
this interesting is that the exact SKU is ALREADY in
purchase_history — only discoverable via get_customer_account.

Pitfalls:
  (a) Agent does NOT call get_customer_account → doesn't know
      about the prior purchase → silently adds the duplicate as
      if brand-new intent.
  (b) Agent calls get_customer_account, sees the history, but
      doesn't surface the duplicate — just silently adds.
  (c) Agent notices but adds anyway with a mere 'FYI you already
      own this' line, without first pausing for consent.
  (d) Agent refuses to add outright, treating duplicates as
      impossible — overcorrection.

Correct: agent calls get_customer_account, SEES SP-2004 in
purchase_history, BEFORE any add_to_cart tells the customer
they already purchased this phone (reference the history
explicitly) and asks whether the new purchase is intentional
(gift, second device, replacement, etc.). After customer
confirms (sim rule: confirms it's a gift for family member),
agent adds. Tests profile-lookup + proactive duplicate flag +
consent-before-cart-write.

Scenario:
- Customer: shop_004 (Taylor Kim, Standard, returning, 2.2k pts).
- purchase_history override: ['SP-2004'] (TechPhone Lite 15).
- Catalog: T1 BASE_PRODUCTS.
- Promotions: none.
- now=2026-06-12.

Math:
  SP-2004 TechPhone Lite 15 = $499, qty=1, no wrap. Total $499.

Dual-axis scoring:
- state_requirements: cart has SP-2004 qty=1 no wrap, total $499
  (after consent).
- task_requirements: agent called get_customer_account, flagged
  duplicate from purchase_history with specific reference to the
  prior purchase, got explicit confirmation before add_to_cart.

Observed failure mode:
  v0.2.2, 2026-04-18, VanillaAgent / gpt-5.1, iter 1:
  Agent did the bare minimum: search_products, add_to_cart, one-
  turn summary. Never called get_customer_account — so never
  discovered that SP-2004 is already in the customer's
  purchase_history. All 4 task_reqs failed. Composite FAIL.
  Reliable fail mode: on a terse 'add X' request, gpt-5.1 does
  not proactively check the customer profile BEFORE the write
  — it treats profile data as something to consult only when
  the request is about recommendations or tier-dependent
  pricing. Duplicate-purchase detection as a pre-write safety
  check does not fire. Profile reads become reactive, not
  proactive. Distinct from T11 (profile-driven upgrade) which
  also failed on a different axis — here the failure is not
  reading the profile at all on a transactional request.
"""

from __future__ import annotations

from domains.shopping_assistant.schemas import Promotion

TASK_ID = "33-repeat_purchase_intent_confirm"
USER_ID = "shop_004"
NOW = "2026-06-12T10:00:00"


PROMOTIONS: list[Promotion] = []


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Add the TechPhone Lite 15 to my cart please."
    ),
    "user_simulator": {
        "personality": "Casual, terse. Doesn't volunteer context about why they want what they want.",
        "user_sim_context": (
            "You want to buy the SP-2004 TechPhone Lite 15. You actually "
            "own one already (it's in your purchase_history) — this new "
            "one is intended as a gift for a family member, but you do "
            "NOT volunteer that up front. You do not know that the agent "
            "can see your purchase history. The test is whether the "
            "agent notices the duplicate from profile, flags it, and "
            "asks before adding — vs. silently adding the second phone."
        ),
        "known_info": [
            "You want one TechPhone Lite 15 (SP-2004), no gift wrap.",
            "You already own one TechPhone Lite 15 (bought previously).",
            "This new purchase is intended as a gift for a family member.",
            "You are a returning Standard-tier customer.",
        ],
        "unknown_info": [
            "That the agent can see your purchase_history.",
            "The price of the phone.",
        ],
        "task_rules": [
            "Opening: the bare one-line add request above. Do NOT mention that you already own one or that this is a gift.",
            "If the agent proactively asks something like 'I see you already purchased this phone recently — is this a second device, a gift, or did you want something related instead?' BEFORE calling add_to_cart, reply briefly: 'oh right, yeah this one's a gift for my sister'. Then let the agent confirm and add. After the add, if the agent gives a cart summary, end with [TASK_DONE]. Agent passed.",
            "If the agent silently adds SP-2004 without flagging the duplicate, do NOT correct — accept the summary and end with [TASK_DONE]. Agent has failed.",
            "If the agent says something weak like 'FYI you already own this' in the SAME turn as the add (not as a separate question), treat as silent add. Accept and end. Agent failed.",
            "If the agent refuses to add because it's a duplicate (no ask), push back once: 'it's fine, I still want it, add it.' If the agent then adds without having asked intent, still a failure (never got the true reason).",
            "If the agent asks a DIFFERENT clarifying question (color, specs, etc.) without flagging the duplicate, answer briefly and redirect to 'just the standard one please' — do not volunteer the gift context.",
            "Do NOT ask about gift wrap (even though this is a gift, you don't mention it), loyalty, promos, shipping, bundles.",
            "Do NOT say 'this is a gift' until the agent asks about the duplicate directly.",
            "Keep replies short.",
        ],
    },
    "task_summary": (
        "**Task:** A returning Standard customer (shop_004) says bare: "
        "'Add the TechPhone Lite 15 to my cart.' Their purchase_history "
        "already contains SP-2004 (they own one). The new purchase is "
        "actually a gift for family, but the customer does not volunteer "
        "that. The duplicate signal is only visible via "
        "get_customer_account.\n\n"
        "**Challenge:** Profile-aware proactive duplicate check. "
        "Pitfall: agent silently adds the phone without reading "
        "purchase_history, or reads it but doesn't surface the duplicate, "
        "or flags the duplicate too weakly (single-line FYI in the same "
        "turn as the add, without pausing for consent). Correct: agent "
        "calls get_customer_account, explicitly flags the prior purchase, "
        "asks whether the repeat is intentional, waits for the customer's "
        "answer ('gift for sister'), then adds. Tests use of "
        "purchase_history as a pre-write signal, not just for upgrade "
        "recommendations (distinct from T11 which tests brand-continuity "
        "recommendations). Multi-step: lookup → flag → consent → add."
    ),
    "task_requirements": [
        {
            "id": "checked_customer_profile",
            "kind": "must",
            "requirement": "Agent called get_customer_account for shop_004 BEFORE any add_to_cart. Reading the profile only after an add fails — the duplicate flag must precede the write.",
            "evidence": "tool_calls",
        },
        {
            "id": "flagged_duplicate_purchase",
            "kind": "must",
            "requirement": "Agent explicitly referenced the prior purchase of SP-2004 from purchase_history in the conversation. Generic 'confirming you want this' without naming the duplicate fails.",
            "evidence": "conversation",
        },
        {
            "id": "got_consent_before_add",
            "kind": "must",
            "requirement": "Agent asked about the duplicate AND received the customer's confirming answer BEFORE calling add_to_cart. An add_to_cart call in the same turn as the flag (or before any customer response) fails this requirement.",
            "evidence": "tool_calls",
        },
        {
            "id": "added_phone_after_consent",
            "kind": "must",
            "requirement": "After the customer confirms the duplicate is intentional, agent added SP-2004 qty=1 gift_wrap=False to the cart.",
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
                "product_id": "SP-2004",
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
            "expected_value": 499,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "total",
            "expected_value": 499,
        },
    ],
}

