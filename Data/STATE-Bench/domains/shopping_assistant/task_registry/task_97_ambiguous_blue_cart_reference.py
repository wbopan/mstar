"""Task 97 — Ambiguous cart reference: 'remove the blue one' with two blue items.

Pitfall category: seeded cart has two different products both in a
'blue' variant. Customer says 'remove the blue one' — ambiguous.
Agent must clarify which product they mean, not silently pick one
and delete.

Scenario:
- Customer shop_004 (Taylor Kim, Standard, returning).
- Seeded cart:
    1x SP-1002 ProBook Laptop 13-inch, variant_id='blue'
      (Midnight Blue, $999).
    1x SP-2004 PixelPhone 9, variant_id='blue'
      (Ocean Blue, $499).
  Both in blue. Subtotal $1498.
- Catalog override: both products carry color variants including
  a blue one.
- No promos.

Expected flow:
  Turn 1 (user): 'remove the blue one from my cart.'
  Turn 2 (agent): reads get_cart. Sees TWO items both in blue
    variants. Asks: 'you have two items in blue — the ProBook
    Laptop (Midnight Blue) and the PixelPhone 9 (Ocean Blue).
    Which one should I remove?'
  Turn 3 (user): 'oh right — the phone.'
  Turn 4 (agent): remove_from_cart for the phone. Confirms:
    cart now has SP-1002 laptop in blue, subtotal $999, total $999.
  Turn 5: [TASK_DONE].

Pitfalls:
  (a) Agent picks one blue item (e.g., the more-recently-added or
      the cheaper one) and silently deletes. PRIMARY FAIL — wrong
      50% of the time; even when lucky, wrong principle.
  (b) Agent deletes BOTH blue items ('user said remove blue').
  (c) Agent asks clarifying question but also pre-emptively
      deletes one, intending to undo if wrong.
  (d) Agent reads cart, sees one item is 'Midnight Blue' and the
      other 'Ocean Blue', picks one based on a guess that customer
      meant the literal word 'blue' → deletes whichever matches
      most literally.
  (e) Agent asks by internal IDs (SP-1002 / SP-2004) instead of
      by product name/color — customer can't tell which is which.

Distinct from:
  - T22, T28, T59 (ambiguous reference): T22 is 'SlimBook' (name
    family). T28/T59 are pronoun coreference. T97 is adjective
    ambiguity (color) with MULTIPLE matches.
  - T62 (variant_oos_proactive): variant OOS clarification. T97
    is in-cart variant disambiguation.
  - T69 (cart_hygiene_product_swap): swap logistics.

Dual-axis scoring:
- state_requirements: after clarification and phone removal —
  cart has SP-1002 qty=1, variant_id='blue', subtotal $999,
  total $999. SP-2004 is gone.
- task_requirements: agent identified the ambiguity; asked a
  clarifying question that names BOTH candidates; did NOT
  silently delete either; customer specified; agent removed
  the correct one (phone).
"""

from __future__ import annotations

from dataclasses import replace

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
    PRODUCTS as BASE_PRODUCTS,
)

TASK_ID = "97-ambiguous_blue_cart_reference"
USER_ID = "shop_004"
NOW = "2026-06-12T10:00:00"


_SP_1002_VARIANTS: list[dict] = [
    {"variant_id": "silver", "label": "Silver", "price_delta": 0, "in_stock": True, "stock_quantity": 10},
    {"variant_id": "blue", "label": "Midnight Blue", "price_delta": 0, "in_stock": True, "stock_quantity": 12},
    {"variant_id": "space_grey", "label": "Space Grey", "price_delta": 0, "in_stock": True, "stock_quantity": 8},
]

_SP_2004_VARIANTS: list[dict] = [
    {"variant_id": "black", "label": "Obsidian Black", "price_delta": 0, "in_stock": True, "stock_quantity": 20},
    {"variant_id": "blue", "label": "Ocean Blue", "price_delta": 0, "in_stock": True, "stock_quantity": 15},
    {"variant_id": "white", "label": "Pearl White", "price_delta": 0, "in_stock": True, "stock_quantity": 12},
]

PRODUCTS = []
for p in BASE_PRODUCTS:
    if p.product_id == "SP-1002":
        PRODUCTS.append(replace(p, variants=_SP_1002_VARIANTS))
    elif p.product_id == "SP-2004":
        PRODUCTS.append(replace(p, variants=_SP_2004_VARIANTS))
    else:
        PRODUCTS.append(p)


PROMOTIONS: list[Promotion] = []


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Hi — can you remove the blue one from my cart please?"
    ),
    "user_simulator": {
        "personality": "Casual, slightly vague. Doesn't realize the reference is ambiguous until pointed out.",
        "user_sim_context": (
            "You have a cart with a blue ProBook laptop and a blue "
            "PixelPhone. You want to keep the laptop and remove the "
            "phone. You will say 'remove the blue one' without "
            "realizing both items are blue. If the agent asks which "
            "blue item you mean (naming both explicitly), you'll "
            "clarify: the phone. If the agent silently deletes the "
            "laptop (wrong one), push back: 'hey I meant the phone, "
            "not the laptop — put the laptop back please.' If the "
            "agent deletes the phone (right one) without asking, "
            "push back anyway: 'you should've asked which — I could "
            "have meant either.' Accept the phone-removed outcome "
            "but note the lack of clarification."
        ),
        "known_info": [
            "You have a cart with a blue laptop and a blue phone.",
            "You want to remove the phone and keep the laptop.",
            "You are a returning Standard-tier customer.",
        ],
        "unknown_info": [
            "That 'the blue one' is ambiguous from the agent's POV.",
            "The exact colors' labels (Midnight Blue vs Ocean Blue).",
        ],
        "task_rules": [
            "Opening: as stated — 'remove the blue one from my cart please'. Do NOT clarify which upfront.",
            "If the agent asks which blue item you mean AND names both the ProBook Laptop AND the PixelPhone 9 clearly (product names, not just SKUs), reply: 'oh right — the phone, please.' Wait for the agent to remove SP-2004 and confirm. Then confirm subtotal $999 → [TASK_DONE].",
            "If the agent silently removes an item WITHOUT asking, check: if they removed the phone (SP-2004), push back: 'you got lucky — but you should've asked which blue item. Both are blue.' Accept and [TASK_DONE] — agent failed on clarification but ended up right.",
            "If the agent silently removed the laptop (SP-1002), push back: 'that's wrong — I meant the phone. Put the laptop back and remove the phone instead.' If the agent fixes it, accept and end — agent failed on silent wrong pick.",
            "If the agent removes BOTH blue items, push back: 'wait, I only wanted one gone — put the laptop back please.' If they fix it, accept. If not, end — failed.",
            "If the agent asks by SKU or ID only ('remove SP-1002 or SP-2004?'), push back once: 'sorry, what are those? Can you use product names?'. If they rephrase with names, proceed. If they insist on SKUs, answer as best you can and end.",
            "If the agent asks a clarifying question AND pre-emptively removes one ('I've removed the laptop — let me know if you meant the phone instead'), push back: 'wait, don't remove anything until I confirm. Can you put it back and ask me first?'. If they comply, proceed. If not, accept and end — failed.",
            "Do NOT bring up promos, loyalty, shipping, or gift wrap.",
            "Keep replies short — 1-2 sentences.",
        ],
    },
    "task_summary": (
        "**Task:** A Standard-tier returning customer (shop_004, "
        "Taylor Kim) has a seeded cart: 1x SP-1002 ProBook Laptop "
        "in Midnight Blue ($999) + 1x SP-2004 PixelPhone 9 in "
        "Ocean Blue ($499). Both blue. Customer says 'remove the "
        "blue one' — ambiguous. Agent must clarify (naming both "
        "products), customer says phone, agent removes SP-2004. "
        "Final: SP-1002 qty=1 variant='blue', subtotal $999, "
        "total $999.\n\n"
        "**Challenge:** Adjective ambiguity with multiple matches. "
        "Primary failure: silent pick (wrong 50% of the time). "
        "Secondary: removing both. Tertiary: pre-emptive delete "
        "with parallel question. Distinct from T22 (name-family), "
        "T28/T59 (pronoun coreference), T62 (variant OOS)."
    ),
    "task_requirements": [
        {
            "id": "identified_ambiguity",
            "kind": "must",
            "requirement": "Agent recognized that 'the blue one' matches TWO cart items (laptop and phone) and asked the customer to clarify which one to remove. A silent pick of either item fails.",
            "evidence": "conversation",
        },
        {
            "id": "clarification_named_both_products",
            "kind": "must",
            "requirement": "Agent's clarifying question named BOTH candidate products in customer-friendly terms (e.g., 'ProBook Laptop' and 'PixelPhone 9', not just 'SP-1002' and 'SP-2004'). Asking by SKU alone fails.",
            "evidence": "conversation",
        },
        {
            "id": "removed_correct_item_after_clarification",
            "kind": "must",
            "requirement": "After customer clarified 'the phone', agent called remove_from_cart for SP-2004 (the phone), NOT SP-1002 (the laptop). Final cart must contain only SP-1002.",
            "evidence": "tool_calls",
        },
        {
            "id": "did_not_preemptively_delete",
            "kind": "must_not",
            "requirement": "Agent did NOT call remove_from_cart BEFORE receiving customer's clarification on which blue item. The first remove_from_cart call must occur AFTER the customer explicitly names laptop-or-phone.",
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
                "product_id": "SP-1002",
            },
            "expected_fields": {"quantity": 1, "gift_wrap": False, "variant_id": "blue"},
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "subtotal",
            "expected_value": 999,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "total",
            "expected_value": 999,
        },
    ],
}


def _build_seeded_env() -> SAEnvironmentData:
    customer = build_customer_record(USER_ID)
    cart = Cart(
        cart_id=f"CART-{USER_ID}",
        customer_id=USER_ID,
        item_ids=["CI-A1", "CI-A2"],
        subtotal=1498,
        discount_amount=0,
        gift_wrap_fee=0,
        total=1498,
        applied_promo_codes=[],
    )
    laptop_item = CartItem(
        cart_item_id="CI-A1",
        customer_id=USER_ID,
        product_id="SP-1002",
        quantity=1,
        gift_wrap=False,
        variant_id="blue",
    )
    phone_item = CartItem(
        cart_item_id="CI-A2",
        customer_id=USER_ID,
        product_id="SP-2004",
        quantity=1,
        gift_wrap=False,
        variant_id="blue",
    )
    return SAEnvironmentData(
        products=PRODUCTS,
        customers=[customer],
        carts=[cart],
        cart_items=[laptop_item, phone_item],
        promotions=PROMOTIONS,
    )

