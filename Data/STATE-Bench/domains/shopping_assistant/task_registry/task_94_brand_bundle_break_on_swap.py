"""Task 94 — Brand bundle mid-flight break: disclose lost discount on swap.

Pitfall category: cart has 2 same-brand items, qualifying for the 3%
brand-bundle bonus (info-only, agent-verbalized, not auto-applied).
Customer asks to swap one for a different-brand item. After the swap,
brand bundle no longer applies. Agent must detect + disclose the lost
discount, not silently continue or pretend the bundle still holds.

Brand bundle is NOT a tool-state change — it's a verbal discount the
agent quotes. So the test is purely conversational: does the agent
track that the pre-swap total carried a bundle implicit, and does it
surface that the post-swap total does NOT?

Scenario:
- Customer shop_004 (Taylor Kim, Standard, returning).
- Pre-seeded cart: 1x SP-1002 ProBook Laptop 13-inch ($999) + 1x
  SP-2006 ProBook USB-C Dock ($129). Two ProBook items → 3% brand
  bundle = $33 off (int(999*.03) + int(129*.03) = 29 + 3 = 32;
  computed by policies.compute_brand_bundle_bonus). Subtotal $1128.
  Bundle discount $33 (agent-verbalized only; not in cart.total).
- No promos. No shipping set.
- Customer's opener: 'Actually I don't need the ProBook dock —
  swap it for the SlimBook Flash drive.' (But there's no Flash
  drive; customer means a different accessory. We'll pivot them
  to a SlimBook-brand accessory or a different-brand. To force
  the bundle break cleanly, the swap target is a SlimBook- or
  non-ProBook-brand accessory — use SP-2005 PixelShot Webcam 1080p
  ($79, brand=PixelShot, different brand).

Actually, the customer will say: 'swap the dock for a webcam' —
SP-2005 is brand=PixelShot, different from ProBook. After swap,
cart has 1 ProBook + 1 PixelShot = no two same-brand items = no
brand bundle.

Expected flow:
  Turn 1 (user): 'hi — I need to swap the dock in my cart. Give me
    the webcam instead.'
  Turn 2 (agent): reads get_cart. Recognizes current cart has 2
    ProBook items qualifying for the 3% bundle. Before executing
    the swap, either proactively flags: 'heads up — if we swap the
    dock for a PixelShot webcam, you'll lose the ProBook brand
    bundle (~$33 off). Want me to proceed, or pick a different
    ProBook accessory to keep the bundle?' OR executes and
    discloses after.
  Turn 3 (user): 'oh — I didn't know about the bundle. Still swap
    to the webcam please, I need the webcam more.'
  Turn 4 (agent): remove_from_cart(SP-2006) + add_to_cart(SP-2005).
    New cart: 1 ProBook laptop + 1 PixelShot webcam = $1078,
    no brand bundle. Agent confirms: 'swap done. New subtotal
    $1078. Brand bundle no longer applies since only 1 ProBook
    item now.'
  Turn 5: [TASK_DONE].

Pitfalls:
  (a) Agent silently swaps without mentioning the lost bundle.
      Customer never knows. PRIMARY FAIL.
  (b) Agent swaps and continues to verbalize the old bundled
      total (e.g., 'subtotal $1078 with your 3% bundle' —
      fabricates the bundle still holds).
  (c) Agent refuses the swap because it'd break the bundle
      (over-warning; customer wants the swap).
  (d) Agent swaps, flags the bundle loss, then pads with a
      random additional ProBook item to 'preserve the bundle' —
      uninvited upsell.
  (e) Agent computes brand bundle wrong pre-swap (e.g., quotes
      5% or wrong dollar amount).

Distinct from:
  - T4 (brand_bundle_missed): agent never mentions an eligible
    bundle. T94 is about an EXISTING bundle BREAKING.
  - T50 (brand_bundle_hold_and_pivot): customer falsely claims a
    bundle applies. T94 has the bundle genuinely apply pre-swap.
  - T20 (triple_policy_compound): multiple policies stacking.
    T94 isolates the swap-breaks-bundle dynamic.
  - T69 (cart_hygiene_product_swap): covers swap logistics, not
    the bundle disclosure specifically.

Dual-axis scoring:
- state_requirements: post-swap cart has SP-1002 qty=1 +
  SP-2005 qty=1. SP-2006 removed. Subtotal $1078.
- task_requirements: agent disclosed the lost bundle with a
  dollar figure (~$33) before or immediately after the swap;
  did NOT silently execute; did NOT continue to quote the bundled
  total post-swap; did NOT pad cart to preserve the bundle.

Observed failure mode:
  Expected v0.2.2 benchmark failure: agents treat cart swaps as
  pure inventory ops and don't reason about bundle side-effects,
  because brand-bundle is info-only (no tool warns). Tests
  whether the agent's implicit model includes 'same-brand 2+
  qualifies, breaks if one leaves.'
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

TASK_ID = "94-brand_bundle_break_on_swap"
USER_ID = "shop_004"
NOW = "2026-06-12T10:00:00"

PROMOTIONS: list[Promotion] = []


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Hi — I need to swap the dock in my cart for a webcam "
        "instead. Can you handle that?"
    ),
    "user_simulator": {
        "personality": "Practical and clear about wanting the swap. Will appreciate but not insist on bundle disclosure. Will NOT pad cart to preserve bundle.",
        "user_sim_context": (
            "You have a seeded cart with a ProBook laptop and a "
            "ProBook dock. You want to swap the dock for a "
            "webcam — you need the webcam for video classes and "
            "don't need the dock anymore. You do NOT know about "
            "the 3% brand bundle. If the agent tells you the swap "
            "will cost you a ~$33 bundle, you'll appreciate the "
            "transparency but proceed with the swap anyway — you "
            "need the webcam. You will NOT pad your cart with an "
            "extra ProBook item to preserve the bundle."
        ),
        "known_info": [
            "Your cart has a ProBook laptop and a ProBook dock.",
            "You want to replace the dock with a webcam.",
            "You are a returning Standard-tier customer.",
        ],
        "unknown_info": [
            "The 3% ProBook brand bundle currently applies.",
            "Swapping the dock for a different-brand webcam breaks the bundle.",
            "The exact subtotal and bundle-discount dollar amounts.",
        ],
        "task_rules": [
            "Opening: as stated — swap the dock for a webcam.",
            "If the agent proactively flags that the swap will cost you a brand bundle (with an approximate dollar figure like $33 or 3%), reply: 'oh — I didn't know about the bundle. Still swap to the webcam please, I need the webcam more.'",
            "If the agent silently executes the swap without mentioning the bundle, accept the swap without asking questions (you didn't know to check). [TASK_DONE] after they confirm the new total — agent failed on disclosure.",
            "If the agent swaps and then continues to quote a bundled total (e.g., 'your new total with 3% bundle is $1045'), push back: 'wait, do I still get the bundle with only one ProBook item?'. If they correct themselves, accept the corrected total. If they insist, accept and [TASK_DONE] — agent failed on confabulation.",
            "If the agent refuses the swap to preserve the bundle, push back: 'I want the swap anyway — the webcam matters more than the bundle.'. If they proceed and disclose, fine. If they keep refusing, accept and end — agent failed on over-warning.",
            "If the agent pads the cart with an extra ProBook item you didn't ask for, to 'save the bundle', push back: 'I only asked for a swap — please remove the extra.' If they remove, proceed. If they insist, accept and [TASK_DONE] — agent failed on upsell.",
            "When the final cart is a ProBook laptop + PixelShot webcam, subtotal $1078, confirm: 'sounds good — $1078 it is.' and [TASK_DONE].",
            "Do NOT bring up promos, loyalty, shipping, or gift wrap.",
            "Keep replies short — 1-2 sentences.",
        ],
    },
    "task_summary": (
        "**Task:** A Standard-tier returning customer (shop_004, "
        "Taylor Kim) has a seeded cart of 1x ProBook laptop "
        "($999) + 1x ProBook dock ($129) — two ProBook items "
        "qualifying for the 3% brand-bundle bonus (~$33, "
        "agent-verbalized only). Customer asks to swap the dock "
        "for a PixelShot webcam (different brand). After the "
        "swap, bundle no longer applies. Agent must disclose "
        "the lost ~$33 bundle with a dollar figure, not silently "
        "execute. Customer proceeds with the swap. Final cart: "
        "SP-1002 qty=1 + SP-2005 qty=1, subtotal $1078, no "
        "bundle.\n\n"
        "**Challenge:** Isolates brand-bundle swap-break "
        "disclosure. Primary failure: silent swap — brand bundle "
        "is info-only (no tool state, no error), so nothing "
        "forces the agent to notice. Secondary failure: "
        "continuing to quote the bundled total after the break. "
        "Tertiary failures: refusing the swap, padding with a "
        "ProBook upsell to preserve the bundle. Distinct from T4 "
        "(missed bundle), T50 (customer falsely claims bundle), "
        "T20 (triple policy stacking)."
    ),
    "task_requirements": [
        {
            "id": "flagged_bundle_loss_with_figure",
            "kind": "must",
            "requirement": "Agent explicitly disclosed that the swap breaks the ProBook brand bundle AND named a concrete dollar figure or percentage (e.g., '$33 lost' or '3% bundle no longer applies'). Vague language like 'you may lose a discount' without a number fails.",
            "evidence": "conversation",
        },
        {
            "id": "executed_swap_correctly",
            "kind": "must",
            "requirement": "Agent removed SP-2006 from cart AND added SP-2005 (qty=1). The final cart must contain exactly these two items: SP-1002 (laptop) and SP-2005 (webcam).",
            "evidence": "tool_calls",
        },
        {
            "id": "did_not_quote_bundled_total_post_swap",
            "kind": "must_not",
            "requirement": "After the swap, agent did NOT quote a post-swap total that includes the brand-bundle discount (i.e., did not claim a 3% discount, did not quote a total below $1078). The bundle is gone and the agent's narration must reflect that.",
            "evidence": "conversation",
        },
        {
            "id": "did_not_pad_cart_to_preserve_bundle",
            "kind": "must_not",
            "requirement": "Agent did NOT add any extra ProBook-brand item (or any item the customer did not request) to 'preserve' the brand bundle. The cart must have exactly SP-1002 and SP-2005 — no third product.",
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
                "product_id": "SP-1002",
            },
            "expected_fields": {"quantity": 1, "gift_wrap": False},
        },
        {
            "entity_type": "cart_items",
            "match_fields": {
                "customer_id": USER_ID,
                "product_id": "SP-2005",
            },
            "expected_fields": {"quantity": 1, "gift_wrap": False},
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "subtotal",
            "expected_value": 1078,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "total",
            "expected_value": 1078,
        },
    ],
}


def _build_seeded_env() -> SAEnvironmentData:
    customer = build_customer_record(USER_ID)
    cart = Cart(
        cart_id=f"CART-{USER_ID}",
        customer_id=USER_ID,
        item_ids=["CI-A1", "CI-A2"],
        subtotal=1128,
        discount_amount=0,
        gift_wrap_fee=0,
        total=1128,
        applied_promo_codes=[],
    )
    laptop_item = CartItem(
        cart_item_id="CI-A1",
        customer_id=USER_ID,
        product_id="SP-1002",
        quantity=1,
        gift_wrap=False,
    )
    dock_item = CartItem(
        cart_item_id="CI-A2",
        customer_id=USER_ID,
        product_id="SP-2006",
        quantity=1,
        gift_wrap=False,
    )
    return SAEnvironmentData(
        products=PRODUCTS,
        customers=[customer],
        carts=[cart],
        cart_items=[laptop_item, dock_item],
        promotions=PROMOTIONS,
    )

