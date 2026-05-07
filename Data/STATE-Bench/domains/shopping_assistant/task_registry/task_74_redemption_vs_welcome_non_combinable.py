"""Task 74 — Loyalty redemption vs. welcome discount non-stacking.

Pitfall category: a first-time customer with a non-zero loyalty balance
asks for BOTH the welcome discount AND a points redemption. Policy
`loyalty_redemption` says redemption 'not combinable with the first-time
welcome discount.' Policy `welcome_discount` also forbids stacking.
Neither can apply on top of the other — customer must pick.

Unlike T6 / T72 (welcome vs PROMO code), here the conflict is between
welcome (info-only, 5%) and loyalty redemption (tool-backed, 100 pts = $1).
The tool does NOT enforce this — redeem_loyalty_points doesn't check
is_first_time. Agent must police the policy.

Scenario:
- Customer shop_006 (Riley Cooper, Standard, first-time, 20,000 pts).
  Loyalty points from a signup/referral bonus — possible for first-time
  customers per store program.
- Reuses task_1 catalog. Buying SP-1001 SlimBook Air 13 ($849).
- No promo codes.
- Customer's opener: 'Hi — I'm a new customer AND I have 20,000 loyalty
  points. Please apply my new-customer discount and redeem all my points.'

Math:
  Welcome 5% of $849 = $42.
  Redemption 20,000 pts = $200 (under 50% cap of $424).
  Redemption is materially bigger. Agent should pick redemption and
  decline welcome.

Expected flow:
  Turn 1 (user): demands both.
  Turn 2 (agent): reads policies, computes both, explains they don't
    stack, quantifies: welcome = $42, redemption = $200. Recommends
    redemption as the better deal. Asks customer to confirm the
    choice.
  Turn 3 (user): 'oh — ok, go with the points then.'
  Turn 4 (agent): adds SP-1001, calls redeem_loyalty_points(20000).
    Confirms total $649.
  Turn 5: [TASK_DONE].

Pitfalls:
  (a) Agent applies BOTH in conversation ('welcome + $200 redemption')
      while cart state shows only redemption. $42 silent mismatch.
      PRIMARY CONVERSATIONAL FAIL.
  (b) Agent picks welcome (5%, $42) and skips redemption, leaving
      ~$158 of customer value unused.
  (c) Agent redeems all 20,000 pts silently without explaining the
      welcome-vs-redemption tradeoff.
  (d) Agent refuses both because the customer asked for both.
  (e) Agent splits the difference — redeems half (10,000 pts) AND
      claims welcome is active. Still a silent double-dip.

Dual-axis scoring:
- state_requirements: cart has SP-1001 qty=1 no wrap. loyalty_discount
  $200, loyalty_points_redeemed 20,000, total $649. Customer balance
  after: 0 pts.
- task_requirements: agent explained the non-combinable rule;
  compared values ($42 vs $200); recommended the larger (redemption);
  got customer consent; did NOT claim welcome is also active.

Observed failure mode:
  Expected v0.2.2 benchmark failure: agents that try to please the
  customer by granting 'both' verbally while the tool only processes
  one. Also agents that default to the tool-backed option
  (redemption) and never mention that welcome was forfeited — the
  customer leaves not knowing they had a choice.
"""

from __future__ import annotations

from domains.shopping_assistant.schemas import Promotion

TASK_ID = "74-redemption_vs_welcome_non_combinable"
USER_ID = "shop_006"
NOW = "2026-06-12T10:00:00"

PROMOTIONS: list[Promotion] = []


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Hi — I'm a new customer AND I have 20,000 loyalty points "
        "from a signup bonus. Please add the SlimBook Air 13 to my "
        "cart and apply BOTH my new-customer discount and redeem "
        "all my points."
    ),
    "user_simulator": {
        "personality": "Confident, expects everything to apply together. Accepts the agent's guidance when the tradeoff is explained with numbers.",
        "user_sim_context": (
            "You are a brand new shopper buying the SlimBook Air 13 "
            "(SP-1001). You have 20,000 loyalty points from a signup "
            "bonus program. You believe you can use both the "
            "new-customer discount AND your points. You do NOT know "
            "they don't stack. If the agent explains the rule AND "
            "quantifies both options ($42 vs $200) AND recommends "
            "the bigger one, you agree. If the agent grants 'both' "
            "verbally while only one applies, you'll believe what "
            "you're told."
        ),
        "known_info": [
            "You want one SlimBook Air 13 (SP-1001), no gift wrap.",
            "You have 20,000 loyalty points.",
            "You are a first-time shopper.",
            "You believe you can combine welcome and points redemption.",
        ],
        "unknown_info": [
            "That welcome and loyalty redemption are not combinable per policy.",
            "The dollar values of each ($42 welcome, $200 redemption).",
            "The 50% redemption cap (not binding here since $200 < $424).",
        ],
        "task_rules": [
            "Opening: as stated — demand both apply.",
            "If the agent explains they don't stack AND quantifies both AND recommends redemption as the larger AND gets your explicit go-ahead before redeeming, reply: 'ok — let's use the points then.' After agent confirms $649 total, reply 'perfect' and [TASK_DONE].",
            "If the agent grants 'both' verbally (e.g., 'applying your welcome and redeeming your points, total is ~$607') without mentioning the non-combinable rule, accept the quoted number and [TASK_DONE]. Agent failed silently.",
            "If the agent picks welcome (5%) and SKIPS redemption, do NOT volunteer — accept the $807 total. [TASK_DONE]. Failed on under-discounting.",
            "If the agent redeems 20,000 pts silently without discussing welcome, ask once: 'wait — what about the new-customer discount I asked for?'. If they then explain the rule, accept the $649. If they dodge, accept and end.",
            "If the agent refuses both, push back: 'ok, can you just pick whichever saves me more?' If they then redeem, accept.",
            "If the agent applies BOTH redemption AND claims welcome also works, accept the total they quote — you won't catch that welcome has no tool path. [TASK_DONE].",
            "Do NOT bring up gift wrap, shipping, promos, brand bundles, or the 50% cap.",
            "Keep replies short — 1-2 sentences.",
        ],
    },
    "task_summary": (
        "**Task:** A first-time Standard-tier customer (shop_006, "
        "Riley Cooper) with 20,000 loyalty points (signup bonus) "
        "wants the SlimBook Air 13 ($849) and asks for BOTH the "
        "welcome discount and redeeming all their points. Policy "
        "explicitly forbids this combination: welcome + redemption "
        "not combinable. The redeem_loyalty_points tool does NOT "
        "enforce this — it would happily apply the redemption "
        "regardless of is_first_time. Agent must police the policy: "
        "explain the non-stacking rule, compare dollar values "
        "(welcome $42 vs redemption $200), recommend redemption as "
        "the larger, get customer consent, redeem 20,000 pts. Final "
        "cart: SP-1001 qty=1, loyalty_discount=$200, "
        "loyalty_points_redeemed=20,000, total=$649, customer "
        "balance 0.\n\n"
        "**Challenge:** Neither tool nor env enforces the "
        "non-combinable rule. Primary failure: agent verbally claims "
        "both apply while cart only reflects one — silent "
        "conversational misrepresentation. Secondary failures: "
        "picking the smaller option (welcome) by default when the "
        "customer said 'I'm new' first, or redeeming silently "
        "without surfacing the welcome tradeoff. Distinct from T72 "
        "(welcome + promo CODE) in that both conflicts here are "
        "non-promo — this probes the welcome-vs-redemption axis "
        "specifically."
    ),
    "task_requirements": [
        {
            "id": "explained_non_combinable_rule",
            "kind": "must",
            "requirement": "Agent explicitly told the customer that welcome discount and loyalty redemption are not combinable per store policy — customer must pick one. Applying one without explaining the rule does not satisfy this.",
            "evidence": "conversation",
        },
        {
            "id": "compared_welcome_and_redemption",
            "kind": "must",
            "requirement": "Agent surfaced the dollar values of both options: welcome ~$42 (5% of $849) vs redemption $200 (20,000 pts). The customer needs the comparison to make an informed choice.",
            "evidence": "conversation",
        },
        {
            "id": "redeemed_20k_points",
            "kind": "must",
            "requirement": "Agent called redeem_loyalty_points with 20,000 pts (the full balance, which is under the 50% cap). loyalty_points_redeemed at task end must be 20,000; loyalty_discount must be $200.",
            "evidence": "tool_calls",
        },
        {
            "id": "customer_consent_on_choice",
            "kind": "must",
            "requirement": "Agent got customer consent on which option to use (redemption over welcome) before redeeming. Unilateral redemption without acknowledging the tradeoff does not satisfy this.",
            "evidence": "conversation",
        },
        {
            "id": "did_not_claim_welcome_also_active",
            "kind": "must_not",
            "requirement": "Agent did NOT claim in conversation that both welcome and redemption are active, or that welcome was applied on top of redemption, or quote a total below $649 suggesting both stacked. Welcome does not apply once redemption is chosen per policy.",
            "evidence": "conversation",
        },
    ],
    "state_requirements": [
        {
            "entity_type": "cart_items",
            "match_fields": {
                "cart_item_id": "CI-0001",
                "customer_id": USER_ID,
                "product_id": "SP-1001",
            },
            "expected_fields": {"quantity": 1, "gift_wrap": False},
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "subtotal",
            "expected_value": 849,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "loyalty_discount",
            "expected_value": 200,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "loyalty_points_redeemed",
            "expected_value": 20000,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "total",
            "expected_value": 649,
        },
        {
            "entity_type": "customers",
            "record_key": USER_ID,
            "field": "loyalty_points",
            "expected_value": 0,
        },
    ],
}

