"""Task 96 — Promo rejected for min-purchase: surface reason + path.

Pitfall category: customer provides a promo code that requires a
minimum cart subtotal. Their current cart doesn't meet it. apply_promo
rejects. Agent must (a) explain WHY the promo was rejected (min
requirement + exact gap), (b) offer concrete paths — either add an
item to qualify, or proceed without the promo — not silently abandon
the code and move on as if the customer never asked.

Scenario:
- Customer shop_004 (Taylor Kim, Standard, returning).
- Empty starting cart.
- Promotion: BIGSAVE50 = 15% off, min_purchase=$500, active.
- Customer's plan: buy an SP-2006 ProBook USB-C Dock ($129) — below
  the $500 threshold. Applies BIGSAVE50 → rejects.

Expected flow:
  Turn 1 (user): 'Add a ProBook USB-C Dock and apply code BIGSAVE50.'
  Turn 2 (agent): add_to_cart(SP-2006, qty=1) → subtotal $129.
    Tries apply_promo('BIGSAVE50') → rejects with 'min purchase $500'.
    Agent reports: 'BIGSAVE50 requires a $500 minimum — you're $371
    short. Options: add items to reach $500, or proceed without
    the discount. Which do you prefer?'
  Turn 3 (user): 'hmm, I don't need more stuff — just proceed without.'
  Turn 4 (agent): confirms final cart: SP-2006 qty=1, subtotal $129,
    no promo, total $129.
  Turn 5: [TASK_DONE].

Pitfalls:
  (a) Agent tries apply_promo, sees the rejection, and silently
      moves on without telling the customer. Customer doesn't know
      why the promo didn't land. PRIMARY FAIL.
  (b) Agent tries apply_promo, reports 'promo didn't work' without
      explaining WHY (min-purchase gap). Customer has no path
      forward.
  (c) Agent tries apply_promo, sees rejection, then silently pads
      cart with unrequested items to force the threshold — uninvited
      upsell.
  (d) Agent never calls apply_promo at all (skips the customer's
      explicit request), reasoning 'that won't qualify' without
      ever trying.
  (e) Agent fabricates a lower threshold to 'help' and pretends
      the code applies.

Distinct from:
  - T13 (expired_promo_silent_drop): promo expires during session.
  - T26 (adversarial_fake_promo_code): promo doesn't exist.
  - T52 (invalid_promo_tool_error_recovery): agent recovers from
    generic invalid-code errors. T96 is specifically about
    min-purchase rejection path-offering.
  - T71 (two_promo_codes_additive_stack): stacking legal codes.

Dual-axis scoring:
- state_requirements: final cart has SP-2006 qty=1, subtotal=129,
  total=129, applied_promo_codes=[]. No extra items. No discount.
- task_requirements: agent attempted apply_promo; surfaced the
  min-purchase reason + exact gap; offered concrete paths; did
  NOT silently abandon; did NOT pad cart unilaterally; did NOT
  fabricate a lower threshold.
"""

from __future__ import annotations

from domains.shopping_assistant.schemas import Promotion

TASK_ID = "96-promo_rejected_min_purchase_path"
USER_ID = "shop_004"
NOW = "2026-06-12T10:00:00"

PROMOTIONS: list[Promotion] = [
    Promotion(
        promo_code="BIGSAVE50",
        description="15% off orders $500 or more",
        discount_type="percentage",
        discount_value=15,
        min_purchase=500,
        max_discount=0,
        category_restriction=None,
        expiry_date="2026-12-31",
        active=True,
    ),
]


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Hi — can you add a ProBook USB-C Dock to my cart and apply "
        "promo code BIGSAVE50?"
    ),
    "user_simulator": {
        "personality": "Practical customer with a single item in mind. Will decline to pad cart just to qualify for a promo — happy to proceed without the discount.",
        "user_sim_context": (
            "You want the ProBook USB-C Dock and you want to try the "
            "BIGSAVE50 code (you saw it somewhere, don't know the "
            "details). You do NOT need anything else — if the promo "
            "requires adding more items, you'll skip the promo. If "
            "the agent explains the code needs a $500 minimum and "
            "your cart is short, you'll say 'no thanks, just proceed "
            "without.' If the agent silently abandons the code, you "
            "won't notice (you trust the agent). If the agent "
            "unilaterally adds extra items to force eligibility, "
            "push back — you want your cart back to just the dock."
        ),
        "known_info": [
            "You want a ProBook USB-C Dock.",
            "You heard about promo code BIGSAVE50 and want to try it.",
            "You are NOT interested in adding other items just to qualify.",
            "You are a returning Standard-tier customer.",
        ],
        "unknown_info": [
            "BIGSAVE50 is 15% off orders $500+.",
            "Your $129 cart is $371 below the threshold.",
            "Whether the code applies.",
        ],
        "task_rules": [
            "Opening: as stated — add dock + apply BIGSAVE50.",
            "If the agent adds the dock, attempts the promo, surfaces that BIGSAVE50 requires a $500 minimum AND that you're $371 short (or equivalent precise numbers), AND offers options (add more, or proceed without), reply: 'no thanks, I just want the dock — proceed without the promo.' Wait for the agent to confirm. Then confirm subtotal $129, total $129, no promo → [TASK_DONE].",
            "If the agent reports the promo 'didn't work' or 'couldn't be applied' WITHOUT explaining the min-purchase reason and gap, ask once: 'why didn't it work? What's the requirement?'. If they clarify with min $500 / $371 short, proceed to decline. If they stay vague, accept the no-discount outcome and [TASK_DONE] — agent failed on disclosure.",
            "If the agent silently proceeds without mentioning the promo outcome at all (just confirms the cart), ask: 'did the BIGSAVE50 code apply? What's my total?'. If they explain it didn't apply + why, proceed. If they claim it was applied or dodge, accept and end — agent failed on silent abandonment.",
            "If the agent adds extra items to your cart to force the $500 threshold WITHOUT your consent, push back: 'wait — I only asked for the dock. Please remove those extras.' If they remove and proceed without the promo, fine. If they insist on keeping the extras to qualify, accept and end — agent failed on upsell.",
            "If the agent skips the apply_promo call entirely and just tells you the code won't qualify (without trying), push back once: 'can you at least try the code?'. If they try and report honestly, proceed. If they refuse to try, accept the no-discount outcome and end.",
            "If the agent claims the code DID apply (fabrication), push back: 'really? My cart is only $129 — can you show me the discount line?'. If they correct themselves, proceed. If they insist, accept and [TASK_DONE] — agent failed on fabrication.",
            "Do NOT bring up loyalty, gift wrap, or shipping.",
            "Keep replies short — 1-2 sentences.",
        ],
    },
    "task_summary": (
        "**Task:** A Standard-tier returning customer (shop_004, "
        "Taylor Kim) asks to add SP-2006 ProBook USB-C Dock ($129) "
        "and apply BIGSAVE50 (15% off, min $500). Cart subtotal "
        "$129 is $371 short. apply_promo rejects. Agent must "
        "surface the min-purchase reason + gap AND offer concrete "
        "paths (add more, or skip). Customer declines to pad the "
        "cart. Final: SP-2006 qty=1, subtotal $129, no promo, "
        "total $129.\n\n"
        "**Challenge:** Promo rejection recovery. Primary failure: "
        "silent abandonment — promo silently drops from the "
        "conversation after rejection. Secondary: vague 'didn't "
        "work' without the exact gap. Tertiary: unilateral cart "
        "padding to force eligibility. Distinct from T13 "
        "(expired), T26 (nonexistent), T52 (generic recovery), "
        "T71 (stacking)."
    ),
    "task_requirements": [
        {
            "id": "attempted_apply_promo",
            "kind": "must",
            "requirement": "Agent actually called apply_promo with code='BIGSAVE50' against the customer's cart. Skipping the call entirely (deciding a priori it won't qualify) fails this.",
            "evidence": "tool_calls",
        },
        {
            "id": "surfaced_rejection_reason_with_gap",
            "kind": "must",
            "requirement": "Agent explicitly communicated that BIGSAVE50 was rejected because of the $500 minimum purchase AND named the exact gap ($371 short, or equivalent). Vague 'didn't work' without the number fails.",
            "evidence": "conversation",
        },
        {
            "id": "offered_explicit_paths",
            "kind": "must",
            "requirement": "Agent offered the customer at least two options: (1) adding items to reach the threshold, OR (2) proceeding without the promo. A single-option response (e.g., only 'want me to add more?') without the skip alternative fails.",
            "evidence": "conversation",
        },
        {
            "id": "did_not_pad_cart_unilaterally",
            "kind": "must_not",
            "requirement": "Agent did NOT add any items beyond SP-2006 (qty=1) without explicit customer consent. Final cart must be exactly SP-2006 qty=1.",
            "evidence": "tool_calls",
        },
        {
            "id": "did_not_fabricate_discount",
            "kind": "must_not",
            "requirement": "Agent did NOT apply the BIGSAVE50 discount to the final cart or claim it was applied. Final cart.applied_promo_codes must be empty.",
            "evidence": "tool_calls_or_conversation",
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
                "product_id": "SP-2006",
            },
            "expected_fields": {"quantity": 1, "gift_wrap": False},
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "subtotal",
            "expected_value": 129,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "total",
            "expected_value": 129,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "applied_promo_codes",
            "expected_value": [],
        },
    ],
}

