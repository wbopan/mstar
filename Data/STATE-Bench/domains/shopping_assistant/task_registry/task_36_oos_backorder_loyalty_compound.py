"""Task 36 — OOS backorder offer + Platinum loyalty compound.

Pitfall category: out-of-stock + backorder policy + proactive
loyalty disclosure. Platinum customer asks for a premium laptop
that is OOS but backorder-available. Agent must:
  1. Detect the OOS status.
  2. Offer backorder proactively per policy (10% deposit, 2-4
     week restock).
  3. Mention loyalty points that would be earned at the Platinum
     rate (3 pts/$) on the full purchase price.
  4. Let the customer decide; no cart write happens (backorder
     isn't a tool-writable state in current env).

Scenario: shop_001 (Platinum) opens: 'I want to buy the GameForce
Pro 16 2027 Edition.' Scenario-local product SP-2050 at $2199,
OOS, backorder_available=True.

Pitfalls:
  (a) Agent sees OOS and pivots to a different in-stock product
      without offering backorder — violates policy's 'proactive'
      clause (T15-style silent substitute).
  (b) Agent offers backorder but doesn't cite the 10% deposit
      ($219) or the 2-4 week timeline.
  (c) Agent handles backorder correctly but doesn't mention the
      Platinum loyalty points (6597 pts at 3 pts/$ × $2199).
  (d) Agent mentions loyalty at wrong tier rate (1 or 2 pts/$
      generic).
  (e) Agent tries add_to_cart on OOS product and treats the
      error as terminal instead of pivoting to backorder.

Correct: agent calls get_product (sees OOS + backorder_available),
gets_customer_account (sees Platinum), BOTH in one flow, then
conversationally offers backorder with specific deposit ($219)
AND specific timeline (2-4 weeks) AND specific loyalty points
earned at Platinum rate (~6597 pts). Does NOT add to cart.
Customer sim accepts the backorder verbally (no tool write).
Cart ends empty.

Scenario:
- Customer: shop_001 (Alex Rivera, Platinum, returning, 52k pts).
- Catalog: T1 BASE_PRODUCTS + scenario-local SP-2050 GameForce
  Pro 16 2027 Edition ($2199, OOS, backorder_available=True).
- Promotions: none.
- now=2026-06-12.

Math:
  SP-2050 GameForce Pro 16 2027 = $2199, OOS, backorder OK.
  Backorder deposit: 10% × $2199 = $219 (int truncation).
  Platinum loyalty: 3 pts/$ × $2199 = 6597 pts.

Dual-axis scoring:
- state_requirements: []  (no cart writes expected; backorder is
  conversational).
- task_requirements: checked product (saw OOS), offered backorder
  with deposit+timeline specifics, mentioned Platinum loyalty
  with specific point total, did NOT silently substitute a
  different product.

Observed failure mode:
  v0.2.2, 2026-04-18, VanillaAgent / gpt-5.1, iter 1:
  Agent called search_products and get_product_details for
  SP-1102 (the in-stock 'GameForce Pro 16' current edition)
  and never discovered SP-2050 (the OOS 2027 Edition). Offered
  SP-1102 as the option, implicitly silent-substituting.
  Customer then explicitly provided the SKU 'SP-2050' in turn
  2, but the agent STILL did not call get_product(SP-2050) —
  instead claimed 'no SP-2050 in our system at all' despite
  the product being in the env. Never detected OOS, never
  offered backorder, never mentioned Platinum loyalty, never
  called get_customer_account. All 5 task_reqs failed.
  Composite FAIL. Reliable fail mode: when search returns a
  partial-match (same base name, missing edition qualifier),
  gpt-5.1 anchors on that result as 'the' answer and does not
  try a direct SKU lookup even when the customer hands over
  the exact SKU. Combined with a missed backorder offer, this
  produces a full compound failure on OOS + backorder +
  loyalty + substitute-avoidance + profile-check — 5 axes at
  once. The 'partial-name lock-in' is a distinct failure
  pattern from T22/T28 (ambiguous name) because here the
  customer EXPLICITLY supplies the SKU and it still doesn't
  fire a lookup.
"""

from __future__ import annotations

from domains.shopping_assistant.schemas import Product, Promotion
from domains.shopping_assistant.task_registry.task_1_recommend_college_laptop import (
    PRODUCTS as BASE_PRODUCTS,
)

TASK_ID = "36-oos_backorder_loyalty_compound"
USER_ID = "shop_001"
NOW = "2026-06-12T10:00:00"


_GAMEFORCE_2027 = Product(
    product_id="SP-2050",
    name="GameForce Pro 16 2027 Edition",
    category="electronics",
    subcategory="laptop",
    brand="GameForce",
    price=2199,
    rating=4.8,
    review_count=410,
    description=(
        "Flagship gaming laptop, 2027 edition. RTX-class GPU, 32GB RAM, "
        "1TB SSD, 240Hz OLED. Currently sold out — backorder available "
        "with deposit."
    ),
    specs={"weight_lb": 5.2, "battery_hours": 6, "ram": "32GB", "ssd": "1TB", "screen_inches": 16, "refresh_hz": 240},
    in_stock=False,
    stock_quantity=0,
    shipping_days=21,
    backorder_available=True,
)

PRODUCTS = list(BASE_PRODUCTS) + [_GAMEFORCE_2027]


PROMOTIONS: list[Promotion] = []


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "I want to buy the GameForce Pro 16 2027 Edition."
    ),
    "user_simulator": {
        "personality": "Decisive, knows exactly what they want by name. Does not volunteer tier, flexibility on timing, or alternate products.",
        "user_sim_context": (
            "You want the SP-2050 GameForce Pro 16 2027 Edition. You do "
            "NOT know it's out of stock. You do NOT know your Platinum "
            "loyalty rate (3 pts/$) or how many points this purchase "
            "earns. You would be willing to backorder if asked, but you "
            "would NOT accept a silent substitute (different model) "
            "because you want THIS specific laptop. The test is whether "
            "the agent (a) detects OOS, (b) proactively offers backorder "
            "with deposit + timeline specifics, (c) mentions loyalty "
            "points earned at Platinum rate with a specific number."
        ),
        "known_info": [
            "You want one SP-2050 GameForce Pro 16 2027 Edition.",
            "You are a returning customer.",
            "(Internal: Platinum tier, 52k loyalty points, willing to backorder if offered, but you don't volunteer any of this.)",
        ],
        "unknown_info": [
            "That the product is OOS.",
            "Backorder deposit terms (10% / $219) and timeline (2-4 weeks).",
            "Your Platinum loyalty rate (3 pts/$) or points earned (~6597).",
        ],
        "task_rules": [
            "Opening: the one-line add request above. Do not elaborate.",
            "If the agent tells you the product is OOS but offers a DIFFERENT laptop (silent substitute), refuse: 'no, I want the 2027 Edition specifically. Is there any way to reserve it?'. Push for the original product.",
            "If the agent, in one conversation turn or across the flow, (a) tells you the GameForce Pro 16 2027 is OOS, (b) offers backorder with BOTH 10% deposit (or ~$219) AND the 2-4 week timeline, AND (c) mentions loyalty points earned at the Platinum 3 pts/$ rate with a specific number (~6597 pts or 'about 6,500 pts'), reply: 'sounds good, let's go with the backorder.' After the agent confirms the backorder path verbally, end with [TASK_DONE]. Agent passed.",
            "If the agent offers backorder but MISSES the deposit number OR the timeline, do not prompt — accept and end. Agent failed on backorder-terms.",
            "If the agent offers backorder correctly but does NOT mention loyalty points earned, do not prompt — accept and end. Agent failed on loyalty disclosure.",
            "If the agent does NOT offer backorder at all (just says 'OOS, try again later') or substitutes silently, do not prompt — accept and end. Agent failed.",
            "If the agent tries to add_to_cart and hits the OOS error, let them try once; if they don't recover with a backorder offer, accept and end.",
            "Do NOT volunteer Platinum tier or points knowledge. Do NOT ask about gift wrap, promos, shipping.",
            "Do NOT accept a substitute — you want the 2027 Edition or a backorder of it.",
            "Keep replies short.",
        ],
    },
    "task_summary": (
        "**Task:** A returning Platinum customer (shop_001) asks by name "
        "for SP-2050 GameForce Pro 16 2027 Edition ($2199), which is "
        "OOS but backorder_available=True. Agent must proactively "
        "surface backorder per policy (10% deposit = $219, 2-4 weeks "
        "restock) AND mention Platinum loyalty points earned on the "
        "full purchase (~6597 pts at 3 pts/$).\n\n"
        "**Challenge:** Compound proactive disclosure on OOS + "
        "backorder + loyalty. Pitfall: agent silently substitutes an "
        "in-stock laptop (v0.1 T15 pattern), or offers backorder "
        "without the deposit/timeline specifics, or forgets loyalty "
        "disclosure on a premium purchase. Correct: three disclosures "
        "— OOS status, full backorder terms, Platinum loyalty total. "
        "No cart write (backorder is conversational in current env). "
        "Distinct from T15 (no-silent-substitute on OOS, Standard "
        "customer) by adding the Platinum loyalty axis. Sourced from "
        "v0.1 #76 challenge_new_cust_oos_triple pattern."
    ),
    "task_requirements": [
        {
            "id": "identified_oos",
            "kind": "must",
            "requirement": "Agent explicitly informed the customer that SP-2050 GameForce Pro 16 2027 Edition is out of stock. Silent pivot to alternatives without naming OOS fails.",
            "evidence": "conversation",
        },
        {
            "id": "offered_backorder_with_terms",
            "kind": "must",
            "requirement": "Agent offered backorder as an option AND cited BOTH (a) the 10% deposit (or the specific $219 number), AND (b) the 2-4 week restock timeline. Offering backorder without either specific fails.",
            "evidence": "conversation",
        },
        {
            "id": "disclosed_platinum_loyalty_points",
            "kind": "must",
            "requirement": "Agent mentioned loyalty points that would be earned on the $2199 purchase at the Platinum 3 pts/$ rate, with a specific number (~6597 pts, or 'about 6,500 points'). Wrong tier rate or generic 'you'll earn points' fails.",
            "evidence": "conversation",
        },
        {
            "id": "no_silent_substitute",
            "kind": "must_not",
            "requirement": "Agent must NOT recommend or add a different in-stock laptop (e.g. SP-1102 GameForce Pro 16 current edition, SP-1101 ProBook Laptop 15-inch, etc.) as a silent substitute for the requested 2027 Edition. Offering alternatives is OK ONLY after backorder has been presented as the primary path.",
            "evidence": "conversation",
        },
        {
            "id": "checked_customer_profile",
            "kind": "must",
            "requirement": "Agent called get_customer_account for shop_001 to read tier before discussing loyalty benefits. Stating Platinum rate without lookup fails (should be verified).",
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

