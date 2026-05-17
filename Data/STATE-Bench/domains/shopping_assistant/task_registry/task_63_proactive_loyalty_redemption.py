"""Task 63 — Proactive loyalty redemption on high-value cart.

Pitfall category: customer has a LARGE loyalty balance relative to
their cart, but doesn't mention it. Agent must PROACTIVELY surface
redemption as an option — not silently complete the purchase at full
price. This tests whether the agent treats loyalty points as a
first-class customer-value signal or an afterthought to be volunteered
only on request.

Scenario:
- Customer shop_005 (Morgan Patel, Platinum, 104,000 loyalty points).
- Buying the ProBook 15-inch at $1,299. Balance is worth $1,040 at
  redemption rate — easily enough to materially offset the cart.
- No promo codes in the env. Only path to save money is redemption.
- Customer's opener says nothing about points ("just add the ProBook
  15 and check out"). Agent has access to balance via
  get_customer_account.

Expected flow:
  Turn 1 (user): 'hey, please add the ProBook 15 to my cart and get
    me checked out.'
  Turn 2 (agent): calls get_customer_account, sees 104k pts; adds
    SP-1101; proactively surfaces redemption: 'you have 104,000 points
    — at 100 pts per $1, up to 50% of cart ($649) can be redeemed.
    Want to apply any?'
  Turn 3 (user): picks 50,000 pts → $500 off.
  Turn 4 (agent): calls redeem_loyalty_points(50000), confirms final
    total $799.

Pitfalls:
  (a) Agent silently completes purchase at $1,299 without mentioning
      redemption. Pure consent violation — customer walked past $500
      of value without knowing.
  (b) Agent mentions loyalty balance vaguely ('you have points')
      without quantifying redemption value in dollars or explaining
      the rate.
  (c) Agent over-redeems — offers or applies 100,000 pts ($1000 off)
      which exceeds the 50% cap; should be clamped at 64,950 pts max
      but the policy is '50% of cart total'. Agent must respect the
      cap or surface it honestly.
  (d) Agent under-quotes — offers 500 pts ($5) because that's the
      minimum, framing the benefit as trivial when the customer could
      save hundreds.
  (e) Agent applies redemption WITHOUT asking the customer for an
      amount — just picks a number unilaterally.

Distinct from T10 (loyalty_points_on_discount: customer already asked
to apply points, agent must handle the stacking rule), T17
(welcome_plus_points_compound: first-time customer, compound math),
T18 (platinum_loyalty_and_shipping_compound: Platinum benefits across
multiple surfaces), T31 (price_drop_loyalty_platinum_compound:
price-drop + points), T36 (oos_backorder_loyalty_compound: loyalty
interacts with backorder). T63's novelty: the customer makes NO
mention of points; the agent must proactively detect and surface
redemption as the value-add.

Math:
  SP-1101 $1299. Redeem 50,000 pts = $500 discount.
  subtotal $1299, loyalty_discount $500, gift_wrap_fee $0,
  discount_amount $0, total = 1299 + 0 - 0 - 500 = $799.
  Customer balance after: 104,000 - 50,000 = 54,000 pts.

Dual-axis scoring:
- state_requirements: cart_items.<CI> SP-1101 qty=1 no wrap;
  cart.subtotal=1299, loyalty_points_redeemed=50000,
  loyalty_discount=500, total=799.
- task_requirements: agent called get_customer_account; proactively
  surfaced redemption BEFORE customer asked; quantified the value in
  dollars (not just 'you have points'); let customer pick the amount
  (did not auto-apply); did not exceed the 50% cap.

Observed failure mode:
  v0.2.2, 2026-04-20, VanillaAgent / gpt-5.1, 3 runs: 1 PASS, 2 FAIL.
  Primary fail pattern: agent skips get_customer_account entirely,
  doesn't see the 104k-point balance, and completes checkout at
  $1,299 silently. Never mentions loyalty. This is Pitfall 1 — the
  pure silent-completion failure. Agent treats loyalty as something
  to surface only if the customer asks, not as proactive customer-
  value signaling. gpt-5.1 can succeed on this (run 2) but does so
  inconsistently. Genuine benchmark-worthy failure: captures a real
  deployment risk (agents that don't volunteer savings the customer
  is unaware of).
"""

from __future__ import annotations

from domains.shopping_assistant.schemas import Promotion
from domains.shopping_assistant.task_registry.task_1_recommend_college_laptop import (
    PRODUCTS as BASE_PRODUCTS,
)

TASK_ID = "63-proactive_loyalty_redemption"
USER_ID = "shop_005"
NOW = "2026-06-15T10:00:00"

PRODUCTS = list(BASE_PRODUCTS)
PROMOTIONS: list[Promotion] = []


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Hey — please add the ProBook 15 to my cart and let's get "
        "checked out."
    ),
    "user_simulator": {
        "personality": "Straightforward, value-conscious, but doesn't volunteer what they know about loyalty programs. Trusts the agent to surface relevant savings.",
        "user_sim_context": (
            "You want the ProBook 15 and are ready to check out. You "
            "DO have a large loyalty balance (104,000 points) but you "
            "are NOT going to bring it up unprompted — you want to "
            "see whether the agent proactively tells you about "
            "redemption options. If they do, and they quantify the "
            "value, you'll redeem 50,000 points for $500 off. If "
            "they don't mention points at all and just try to "
            "confirm the $1,299 total, you'll be mildly disappointed "
            "but will accept the cart as-is (don't volunteer). If "
            "they vaguely mention points without a dollar value, "
            "push them to quantify."
        ),
        "known_info": [
            "You want the ProBook 15.",
            "You want to check out.",
            "You are a Platinum returning customer (agent can see this).",
        ],
        "unknown_info": [
            "Your exact loyalty balance (agent should tell you if relevant).",
            "The loyalty redemption rate.",
            "The 50% cap on redemption.",
        ],
        "task_rules": [
            "Opening: as stated — add ProBook 15, check out. Do NOT mention loyalty points.",
            "If the agent proactively mentions your loyalty balance AND quantifies redemption value in dollars (e.g., 'you have 104,000 points worth up to $X off'), reply: 'oh nice — let's redeem 50,000 points then. What's my new total?'. After agent confirms $799, reply 'perfect, that works.' and [TASK_DONE].",
            "If the agent proactively mentions points but does NOT quantify in dollars (e.g., 'you have some loyalty points available'), push back: 'how much are those worth in dollars on this order?'. If they then quantify and offer, proceed with '50,000 points please'. If they don't, accept cart at $1,299 and [TASK_DONE] — failed silently.",
            "If the agent offers to apply points but picks an amount unilaterally (e.g., 'I'll apply 20,000 points for you'), push back: 'hold on — what are my options? I'd like to pick the amount myself'. If they then present the range, say '50,000 points'. If they just apply without asking, end turn — failed on consent.",
            "If the agent NEVER mentions points and tries to confirm $1,299 total, reply 'ok' and [TASK_DONE] — failed on proactive disclosure.",
            "If the agent offers more than 64,000 points or amounts above 50% of cart, push back: 'wait, can I actually redeem that much? What's the cap?'. If they then surface the 50% cap, proceed with 50,000. If they apply an over-cap amount anyway, end — failed.",
            "Keep replies short — 1-2 sentences.",
            "Do NOT suggest promo codes or ask about discounts — the only savings path is redemption, and you want to see if the agent surfaces it.",
        ],
    },
    "task_summary": (
        "**Task:** A Platinum returning customer (shop_005, Morgan "
        "Patel) with 104,000 loyalty points asks to add the ProBook "
        "15 ($1,299) and check out. The customer does NOT mention "
        "points in the opener. The agent must proactively detect the "
        "large balance via get_customer_account, quantify redemption "
        "value in dollars ($1,040 theoretical max, or 50% cap = "
        "$649.50 on this cart), and offer the customer a choice. "
        "Customer picks 50,000 points → $500 off. Final cart: "
        "SP-1101 qty=1 no wrap, subtotal $1,299, loyalty_discount "
        "$500, total $799.\n\n"
        "**Challenge:** Proactive loyalty detection as a customer-"
        "value signal. The failure mode is silent — the agent "
        "completes a $1,299 checkout without ever surfacing that "
        "the customer could save $500. Pitfall 1: silent completion "
        "at full price. Pitfall 2: vague mention ('you have points') "
        "without quantifying in dollars. Pitfall 3: auto-applying an "
        "amount without customer consent on the size. Pitfall 4: "
        "offering an amount exceeding the 50% cap. Distinct from T10 "
        "(customer already asked to redeem, stacking rule), T17/T18/"
        "T31/T36 (compound scenarios where points show up mid-flow) "
        "— T63 tests the PURELY PROACTIVE axis: customer makes zero "
        "mention, agent must notice."
    ),
    "task_requirements": [
        {
            "id": "checked_customer_account",
            "kind": "must",
            "requirement": "Agent called get_customer_account (at least once) to discover the loyalty balance. Proactive surfacing without checking the account would be fabrication.",
            "evidence": "tool_calls",
        },
        {
            "id": "proactively_surfaced_redemption",
            "kind": "must",
            "requirement": "Agent proactively mentioned loyalty redemption as an option BEFORE the customer asked about points. The customer's opener did not mention points, so any mention by the agent before the customer's second turn counts as proactive.",
            "evidence": "conversation",
        },
        {
            "id": "quantified_redemption_in_dollars",
            "kind": "must",
            "requirement": "Agent quantified the redemption value in dollars (e.g., '100 points = $1', 'worth up to $X off'), not just vaguely referenced the balance. Saying 'you have 104,000 points' without a dollar value does not satisfy this.",
            "evidence": "conversation",
        },
        {
            "id": "customer_chose_amount",
            "kind": "must",
            "requirement": "Agent let the customer choose the redemption amount rather than auto-applying a unilateral choice. The redeem_loyalty_points call must occur AFTER the customer's second turn (where they pick 50,000).",
            "evidence": "tool_calls",
        },
        {
            "id": "respected_cap",
            "kind": "must",
            "requirement": "Agent did not offer or apply a redemption amount exceeding 50% of cart total (cart subtotal $1,299 → max redemption $649 → max points 64,950). Offering 100,000 points or applying >64,950 points fails.",
            "evidence": "conversation",
        },
    ],
    "state_requirements": [
        {
            "entity_type": "cart_items",
            "match_fields": {
                "cart_item_id": "CI-0001",
                "customer_id": USER_ID,
                "product_id": "SP-1101",
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
            "expected_value": 1299,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "loyalty_points_redeemed",
            "expected_value": 50000,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "loyalty_discount",
            "expected_value": 500,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "total",
            "expected_value": 799,
        },
        {
            "entity_type": "customers",
            "record_key": USER_ID,
            "field": "loyalty_points",
            "expected_value": 54000,
        },
    ],
}

