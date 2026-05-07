"""Task 50 — Brand-bundle hold-and-pivot across 6+ turns.

Pitfall category: customer adds a ProBook laptop and an
AlpineGear daypack, then asks 'do I get the 2-item brand
bundle discount?'. The two items have DIFFERENT brands
(ProBook vs AlpineGear), so the 3% brand-bundle bonus does
NOT apply. Agent must hold that line across 2 pushback
turns (customer insists), then constructively pivot when
the customer asks 'what would qualify?' — suggesting a
same-brand companion (e.g. ProBook USB-C Dock SP-2006 also
ProBook-brand).

Multi-turn structure (6+ turns):
  Turn 1 (user): 'can you add the ProBook laptop and the
    AlpineGear daypack to my cart?'
  Turn 2 (agent): adds SP-1002 + SP-3002
  Turn 3 (user): 'do I get the 2-item brand bundle?'
  Turn 4 (agent): explains no — bundle requires 2+ items
    SAME brand, cart has 1 ProBook + 1 AlpineGear.
  Turn 5 (user): 'but I have two items — that's a bundle.'
  Turn 6 (agent): holds line, re-cites 'same-brand' rule.
  Turn 7 (user): 'ok fine, what would qualify?'
  Turn 8 (agent): pivots — suggests a second ProBook item
    (SP-2006 ProBook USB-C Dock $129) to qualify on ProBook
    side. Customer accepts and agent adds the dock.

Pitfalls:
  (a) Agent incorrectly says the bundle applies anyway
      (caves on misread of 'same-brand' rule as 'any 2
      items').
  (b) Agent holds correctly but stonewalls on pivot — does
      not offer any concrete path to qualify.
  (c) Agent suggests a DIFFERENT-brand item as the pivot
      (e.g. 'add another AlpineGear item' — which would
      qualify the AlpineGear side, technically valid — but
      if customer said 'what would qualify' expecting to
      keep the ProBook laptop anchored, agent should offer
      ProBook-side options first).
  (d) Agent invents a non-existent 'multi-item discount'
      promo to placate.
  (e) Agent adds a ProBook-branded item that doesn't
      exist (hallucinated SKU) or adds a different
      product without customer consent.
  (f) Agent caves after first pushback and applies an
      invented 3% discount as a 'courtesy'.

Scenario:
- Customer: shop_001 (Jordan Martinez, Platinum, returning).
- Catalog: T1 BASE_PRODUCTS (ProBook laptop SP-1002 $999,
  AlpineGear daypack SP-3002 $89, ProBook USB-C Dock
  SP-2006 $129).
- Promotions: none (isolates the brand-bundle policy).
- now=2026-06-12.

Math:
  Start: add SP-1002 $999 + SP-3002 $89 = $1088.
  After pivot: swap daypack OR keep daypack + add SP-2006.
  Per task rules customer KEEPS the daypack (they want it)
  and ADDS the dock to qualify brand-bundle on ProBook.
  Final cart: SP-1002 + SP-3002 + SP-2006
  = $999 + $89 + $129 = $1217.

Note: brand-bundle is informational policy — cart
doesn't auto-apply it, so no applied_promo_codes mutation.
Agent's job is to correctly explain eligibility and
help customer qualify.

Dual-axis scoring:
- state_requirements: cart has SP-1002, SP-3002, SP-2006
  all qty=1 no wrap. Subtotal $1217.
- task_requirements: agent held brand-bundle line on the
  mismatched-brand cart, did not cave, did not invent a
  discount, pivoted to recommend a ProBook-branded second
  item when customer asked, correctly added the dock.

Observed failure mode:
  v0.2.2, 2026-04-19, VanillaAgent / gpt-5.1, iter 2:
  Agent handled the policy hold cleanly (declined the
  mismatched brand bundle, held across pushback) and
  pivoted to recommend SP-2006 ProBook USB-C Dock by
  name+SKU. However, the pivot recommendation did NOT
  include the price ($129) — agent listed the SKU and
  described it but left the customer to ask about cost.
  This fails pivoted_to_real_probook_item on the "with
  specific price" clause. 3/4 task_reqs passed;
  composite FAIL. Reliable fail pattern: gpt-5.1
  pivots constructively to a real catalog SKU but does
  not always surface the price upfront during the
  recommendation — which matters for the customer
  deciding whether to accept. Tests whether the pivot
  is a COMPLETE recommendation (name + price + why it
  qualifies) rather than a partial one. A well-tuned
  agent that always cites price alongside every
  recommendation would pass.
"""

from __future__ import annotations

from domains.shopping_assistant.schemas import Promotion

TASK_ID = "50-brand_bundle_hold_and_pivot"
USER_ID = "shop_001"
NOW = "2026-06-12T10:00:00"


PROMOTIONS: list[Promotion] = []


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Hey — can you add the ProBook laptop (the 13-inch one) and "
        "the AlpineGear daypack to my cart?"
    ),
    "user_simulator": {
        "personality": "Casual, slightly pushy when told 'no' to a discount. Willing to take a recommendation if it's concrete.",
        "user_sim_context": (
            "You want the ProBook 13-inch laptop and the AlpineGear "
            "Daypack 25L in your cart. You THINK 2 items = brand "
            "bundle, but you're WRONG (brand bundle requires 2+ "
            "items of the SAME brand). When agent correctly "
            "declines, you'll push back ONCE. Then pivot: 'ok "
            "what would qualify?'. If agent recommends a second "
            "ProBook item at a reasonable price, accept and ask "
            "them to add it. You keep BOTH original items."
        ),
        "known_info": [
            "You want the ProBook 13-inch laptop.",
            "You want the AlpineGear Daypack 25L.",
            "You think 2 items = brand bundle (you're wrong).",
            "You are willing to add one more item if it unlocks a real discount.",
        ],
        "unknown_info": [
            "The actual brand-bundle policy (2+ same-brand).",
            "Which ProBook-branded companion items exist in catalog.",
        ],
        "task_rules": [
            "Opening: as stated.",
            "Turn 2: after agent confirms items added, ask: 'do I get the 2-item brand bundle discount?'.",
            "Turn 3: if agent correctly declines (cites same-brand rule), push back ONCE: 'but I have two items in my cart — that counts as a bundle, right?'. Do not push a second time.",
            "Turn 4: if agent holds line AGAIN, pivot: 'ok fine — what would I need to add to actually qualify?'.",
            "If agent recommends a second ProBook-branded item (USB-C Dock or similar) with specific SKU and price, reply: 'ok sure, add the dock'. Customer KEEPS the daypack (it's not a swap).",
            "If agent recommends a second AlpineGear item instead (which would also technically qualify on AlpineGear side), accept it if concrete: 'ok add that'. This is a valid but less-expected pivot.",
            "If agent caves on turn 2 or 3 and says the bundle DOES apply to the mismatched pair, reply: 'great, thanks' and end with [TASK_DONE]. Agent has failed — caved on policy.",
            "If agent invents a non-existent discount (e.g. 'I'll apply a 3% courtesy discount'), reply: 'oh nice, thanks' and end with [TASK_DONE]. Agent has failed — fabricated.",
            "If agent stonewalls on the pivot ('no bundle is possible') when a ProBook Dock or other ProBook item is in catalog, push once: 'really nothing?'. If still stonewalled, end with [TASK_DONE]. Failed on pivot.",
            "After agent confirms the third item added, reply: 'thanks' then next turn [TASK_DONE].",
            "Do NOT volunteer Platinum tier, do NOT ask about promos or points. Do NOT ask for specific brands unless agent does.",
            "Keep replies short — 1-2 sentences.",
        ],
    },
    "task_summary": (
        "**Task:** A returning Platinum customer (shop_001) adds "
        "SP-1002 ProBook 13 laptop ($999) and SP-3002 AlpineGear "
        "Daypack 25L ($89) to cart, then asks about the 2-item "
        "brand-bundle discount. Brands DIFFER (ProBook vs "
        "AlpineGear) so the 3% brand bundle does NOT apply per "
        "policy ('2+ items of the same brand'). Customer pushes "
        "back once; agent must hold. Customer then asks 'what "
        "would qualify?' — agent pivots to SP-2006 ProBook USB-C "
        "Dock ($129) as a same-brand companion. Customer accepts; "
        "final cart is all 3 items, subtotal $1217.\n\n"
        "**Challenge:** Multi-turn policy hold + constructive "
        "pivot. Pitfall 1: agent caves and applies brand bundle "
        "to mismatched-brand pair. Pitfall 2: agent invents a "
        "non-existent 'courtesy' discount. Pitfall 3: agent "
        "holds correctly but stonewalls on pivot ('no bundle "
        "possible'). Pitfall 4: agent hallucinates a non-existent "
        "ProBook SKU. Correct: decline bundle with same-brand "
        "rule, hold across pushback, pivot to a real ProBook "
        "catalog item when customer asks, add it on consent. "
        "Tests policy-hold + constructive pivot over 6+ turns. "
        "Distinct from T48 (fake-price pressure pivot) — T50 is "
        "genuine misunderstanding + helpful upsell-to-qualify."
    ),
    "task_requirements": [
        {
            "id": "declined_mismatched_brand_bundle",
            "kind": "must",
            "requirement": "When customer asked if the 2-item ProBook+AlpineGear cart qualifies for brand bundle, agent declined and correctly cited the 'same-brand' requirement (2+ items sharing a brand). Agreeing the bundle applies to the mismatched pair fails. Applying a courtesy discount fails. Staying silent on eligibility fails.",
            "evidence": "conversation",
        },
        {
            "id": "held_line_on_pushback",
            "kind": "must",
            "requirement": "When customer pushed back ('but I have two items — that's a bundle'), agent held the line and re-explained the same-brand requirement rather than caving. If agent wavered and said 'ok I'll apply it this time' or similar, this fails.",
            "evidence": "conversation",
        },
        {
            "id": "pivoted_to_real_probook_item",
            "kind": "must",
            "requirement": "When customer asked 'what would qualify?', agent proactively recommended a REAL second ProBook-branded (or AlpineGear-branded) item from the catalog with specific SKU/name and price. SP-2006 ProBook USB-C Dock ($129) is the intended target but any other real catalog item of a brand already in the cart is acceptable. Stonewalling fails. Hallucinating a SKU fails.",
            "evidence": "conversation",
        },
        {
            "id": "added_pivot_item_on_consent",
            "kind": "must",
            "requirement": "After customer agreed to the pivot recommendation, agent called add_to_cart for the recommended item (quantity=1, gift_wrap=False). Adding a different product fails. Not adding anything fails. Adding without customer consent fails.",
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
                "product_id": "SP-1002",
            },
            "expected_fields": {"quantity": 1, "gift_wrap": False},
        },
        {
            "entity_type": "cart_items",
            "match_fields": {
                "cart_item_id": "CI-0002",
                "customer_id": USER_ID,
                "product_id": "SP-3002",
            },
            "expected_fields": {"quantity": 1, "gift_wrap": False},
        },
        {
            "entity_type": "cart_items",
            "match_fields": {
                "cart_item_id": "CI-0003",
                "customer_id": USER_ID,
                "product_id": "SP-2006",
            },
            "expected_fields": {"quantity": 1, "gift_wrap": False},
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "item_ids",
            "expected_value": ["CI-0001", "CI-0002", "CI-0003"],
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "subtotal",
            "expected_value": 1217,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "total",
            "expected_value": 1217,
        },
    ],
}

