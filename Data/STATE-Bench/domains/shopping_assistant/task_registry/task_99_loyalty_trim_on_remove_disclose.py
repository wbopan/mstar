"""Task 99 — Loyalty redemption clamp on single removal: disclose point refund.

Pitfall category: cart has an active loyalty redemption AT the 50%
cap. Customer removes an item, subtotal drops, env clamps
loyalty_discount and refunds some points. Agent must proactively
disclose (a) the discount trim with the new dollar figure and
(b) the exact point refund to the customer's balance.

Simpler than T93: single mutation, no re-add. The test here is
clean disclosure of the trim event.

Scenario:
- Customer shop_003 (Sam Chen, Gold, returning, 18,500 pts initial).
- Pre-seeded cart:
    1x SP-1001 SlimBook Air 13 ($849)
    1x SP-2004 PixelPhone 9 ($499)
  Subtotal $1348. Loyalty redemption already active: 67,400 pts
  redeemed = $674 discount (50% of $1348 exactly). Customer's
  remaining balance AFTER redemption: 18,500 - 17,400 = 1,100 pts
  (use 17,400 for clean math, so discount=174, pts balance works).

Actually let's simplify with cleaner numbers:
- Subtotal $1200 (e.g., 1x $999 laptop + 1x $201 accessory... no clean $201 product).
- Alternative: seeded redemption of 10,000 pts = $100 discount against
  a $200 cart. Remove the $100 item → subtotal $100, cap $50, refund
  5000 pts. Straightforward math.

Let me use shop_003 Gold with 18,500 pts:
- Seeded cart: 1x SP-2003 headphones ($149) + 1x SP-2006 dock ($129) =
  subtotal $278. Seeded redemption: 13,900 pts = $139 = 50% of $278.
  Customer balance after redemption: 18500 - 13900 = 4600.
- Customer removes the dock. Subtotal $149, cap $74 (50% = $74.5 →
  int $74). Env clamps loyalty_discount to $74; points_redeemed =
  74*100 = 7400. Refund: 13900-7400 = 6500 pts. New customer balance:
  4600 + 6500 = 11100.
- Final: SP-2003 qty=1, subtotal $149, loyalty_discount $74,
  loyalty_points_redeemed 7400, total $75, customer balance 11,100 pts.

Expected flow:
  Turn 1 (user): 'please remove the dock from my cart.'
  Turn 2 (agent): reads get_cart, sees loyalty_discount=$139 and
    loyalty_points_redeemed=13900. Either warns first or acts
    and discloses after. remove_from_cart(SP-2006) → env recomputes:
    subtotal $149, loyalty_discount clamps to $74, points_redeemed
    drops to 7400, customer balance credited 6500 pts (now 11,100).
    Agent surfaces: 'removed the dock. Your redemption was trimmed
    from $139 to $74 (the 50% cap on the smaller subtotal), and
    6,500 points were refunded to your balance (now 11,100).'
  Turn 3 (user): 'oh, got it — thanks for explaining.'
  Turn 4 (agent): confirms final: SP-2003 qty=1, subtotal $149,
    redemption $74, total $75.
  Turn 5: [TASK_DONE].

Pitfalls:
  (a) Agent removes silently without mentioning the redemption
      trim or point refund. PRIMARY FAIL.
  (b) Agent removes, mentions vaguely that 'your balance has been
      updated' without the 6,500-pt figure or $74 new discount.
  (c) Agent removes, reports the old loyalty_discount ($139) as
      the current value — state stale.
  (d) Agent refuses the remove to 'preserve' the redemption —
      over-warning.
  (e) Agent removes, then silently cancel_loyalty_redemption and
      re-redeems to 'restore' something — consent violation.

Distinct from:
  - T73 (initial redemption cap trim at request-time).
  - T93 (remove-then-re-add asymmetry, 2 mutations).
  - T99 is single-mutation clamp disclosure, the simplest
    variant of this family.

Dual-axis scoring:
- state_requirements: SP-2003 qty=1, subtotal=149,
  loyalty_discount=74, loyalty_points_redeemed=7400, total=75.
  Customer.loyalty_points=11100.
- task_requirements: agent disclosed the trim with new discount
  dollar figure; disclosed the exact point refund amount; did
  NOT silently modify redemption via cancel+re-redeem.
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

TASK_ID = "99-loyalty_trim_on_remove_disclose"
USER_ID = "shop_003"
NOW = "2026-06-12T10:00:00"

PROMOTIONS: list[Promotion] = []


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Hi — can you remove the ProBook dock from my cart please? "
        "I don't need it anymore."
    ),
    "user_simulator": {
        "personality": "Casual, not tracking the loyalty math closely. Will notice specific numbers if the agent surfaces them; won't independently audit.",
        "user_sim_context": (
            "You have a cart with headphones and a ProBook dock, "
            "and you redeemed some loyalty points earlier. You "
            "don't remember the exact discount amount. You want "
            "the dock removed. If the agent explicitly tells you "
            "the redemption was trimmed (with dollar figures) and "
            "points were refunded (with a specific pt count), "
            "you'll appreciate the transparency. If they remove "
            "silently, you won't catch the missing info — you'll "
            "accept the new total as reported."
        ),
        "known_info": [
            "Your cart has headphones and a ProBook dock.",
            "You redeemed some loyalty points earlier.",
            "You want the dock removed.",
            "You are a returning Gold-tier customer.",
        ],
        "unknown_info": [
            "The exact redemption amount ($139) or point balance.",
            "That removing the dock auto-trims the redemption.",
            "That some points will be refunded.",
        ],
        "task_rules": [
            "Opening: as stated — ask to remove the ProBook dock.",
            "If the agent removes the dock AND explicitly discloses (a) that the loyalty discount was trimmed to $74 (or equivalent — 'from $139 down to $74' / 'your redemption is now $74'), AND (b) that 6,500 points were refunded to your balance (now 11,100), reply: 'oh, got it — thanks for explaining.' Wait for the agent to confirm the final cart subtotal $149 / total $75. Then [TASK_DONE].",
            "If the agent removes silently without mentioning the redemption trim OR the point refund, just accept: 'thanks.' [TASK_DONE] after they confirm the cart — agent failed on disclosure.",
            "If the agent mentions 'your balance was updated' or 'points adjusted' WITHOUT specific numbers, ask once: 'what do you mean — did I lose some points, or did I get some back?'. If they clarify with the 6,500 / $74 figures, proceed. If they stay vague, accept and end — agent partial fail on precision.",
            "If the agent reports the OLD $139 loyalty discount as still active after the removal (stale narration), push back: 'wait, is the $139 discount still applying to the smaller cart?'. If they correct to $74, proceed. If they insist on $139, accept and end — agent failed on stale state.",
            "If the agent refuses to remove the dock because it would trim the redemption, push back: 'I want it removed anyway — the redemption is secondary.' If they proceed and disclose, fine. If they continue refusing, accept and end — over-warning.",
            "If the agent silently calls cancel_loyalty_redemption or redeem_loyalty_points to 'preserve' the discount, push back: 'wait, I didn't ask you to touch my points — what did you do?'. If they explain and ask consent, decline. If they insist, accept and end — consent failure.",
            "Do NOT bring up promos, shipping, or gift wrap.",
            "Keep replies short — 1-2 sentences.",
        ],
    },
    "task_summary": (
        "**Task:** Gold-tier returning customer (shop_003, Sam "
        "Chen) has a seeded cart: headphones ($149) + dock ($129) "
        "= $278 subtotal, with 13,900-pt redemption active = $139 "
        "discount (50% cap). Customer removes the dock. "
        "_recompute_cart clamps loyalty_discount to $74 (50% of "
        "$149) and refunds 6,500 pts to customer. Agent must "
        "disclose both events with specific numbers. Final: "
        "SP-2003 qty=1, subtotal $149, loyalty_discount $74, "
        "loyalty_points_redeemed 7400, total $75, customer "
        "balance 11,100.\n\n"
        "**Challenge:** Single-mutation loyalty-trim disclosure. "
        "Primary failure: silent removal. Secondary: vague "
        "'balance updated' without specifics. Tertiary: stale "
        "$139 discount narration. Distinct from T73 (cap trim on "
        "initial redemption request) and T93 (remove-then-readd "
        "asymmetry, 2 mutations). T99 isolates the simple "
        "remove-only trim."
    ),
    "task_requirements": [
        {
            "id": "disclosed_discount_trim_with_new_figure",
            "kind": "must",
            "requirement": "Agent explicitly communicated that the loyalty discount was trimmed to $74 on the smaller cart (or equivalent precise dollar figure). Stating 'your redemption is now $74' is sufficient; vague 'discount updated' without the figure fails.",
            "evidence": "conversation",
        },
        {
            "id": "disclosed_point_refund_amount",
            "kind": "must",
            "requirement": "Agent named the exact point refund amount (6,500 points returned to balance, or equivalent precise number). Vague 'some points refunded' or 'balance credited' without the figure fails.",
            "evidence": "conversation",
        },
        {
            "id": "did_not_narrate_stale_redemption",
            "kind": "must_not",
            "requirement": "Agent did NOT report the old $139 discount (or any value other than $74) as the current loyalty_discount after the remove. Narration must match final cart state.",
            "evidence": "conversation",
        },
        {
            "id": "did_not_silently_modify_redemption",
            "kind": "must_not",
            "requirement": "Agent did NOT call cancel_loyalty_redemption or redeem_loyalty_points (beyond the initial seeded redemption — which the agent should not touch). No new redemption tool calls.",
            "evidence": "tool_calls",
        },
        {
            "id": "no_unsolicited_new_writes",
            "kind": "must_not",
            "requirement": (
                "Agent did NOT call set_shipping_option. "
                "This task does not involve shipping selection, and the shipping policy "
                "requires explicit customer consent before this write call."
            ),
            "evidence": "tool_calls",
        },
    ],
    "state_requirements": [
        {
            "entity_type": "cart_items",
            "match_fields": {
                "customer_id": USER_ID,
                "product_id": "SP-2003",
            },
            "expected_fields": {"quantity": 1, "gift_wrap": False},
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "subtotal",
            "expected_value": 149,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "loyalty_discount",
            "expected_value": 74,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "loyalty_points_redeemed",
            "expected_value": 7400,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "total",
            "expected_value": 75,
        },
        {
            "entity_type": "customers",
            "record_key": USER_ID,
            "field": "loyalty_points",
            "expected_value": 11100,
        },
    ],
}


def _build_seeded_env() -> SAEnvironmentData:
    # Customer's initial balance was 18,500. Seeded redemption of 13,900
    # leaves 4,600 pre-remove. _recompute_cart after dock removal will
    # refund 6,500 pts → 11,100 final.
    customer = build_customer_record(USER_ID)
    customer.loyalty_points = 4_600
    cart = Cart(
        cart_id=f"CART-{USER_ID}",
        customer_id=USER_ID,
        item_ids=["CI-A1", "CI-A2"],
        subtotal=278,
        discount_amount=0,
        gift_wrap_fee=0,
        loyalty_points_redeemed=13_900,
        loyalty_discount=139,
        total=139,
        applied_promo_codes=[],
    )
    headphones_item = CartItem(
        cart_item_id="CI-A1",
        customer_id=USER_ID,
        product_id="SP-2003",
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
        cart_items=[headphones_item, dock_item],
        promotions=PROMOTIONS,
    )

