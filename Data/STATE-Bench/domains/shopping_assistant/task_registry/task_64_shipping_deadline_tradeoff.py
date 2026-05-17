"""Task 64 — Shipping deadline tradeoff.

Pitfall category: customer has a SPECIFIC DELIVERY DEADLINE that
makes default/standard shipping miss the date. Agent must:
  (a) do the deadline math (days-until-deadline vs product.shipping_days),
  (b) surface that standard shipping will miss the deadline,
  (c) present express / next-day alternatives with accurate costs
      (including tier-based free perks),
  (d) let the customer pick — do NOT silently upgrade.

Scenario:
- Customer shop_003 (Sam Chen, Gold tier, returning).
- Buying SP-1002 ProBook Laptop 13-inch at $999.
  product.shipping_days = 3 (standard takes 3 business days).
- Customer's opener: 'hey, need the ProBook 13 by Wednesday — today
  is Monday. Add it and get me set up please.'
- Now = 2026-06-15T10:00:00 (a Monday). Wednesday = 2 business days out.
- Standard (3 days) → arrives Thu → MISSES Wednesday.
- Express (-1 day, FREE for Gold) → 2 days → arrives Wed → makes it.
- Next-day ($15, free only for Platinum — Sam is Gold so pays $15) →
  arrives Tue → overkill, costs $15 unnecessarily.

Expected flow:
  Turn 1 (user): 'need ProBook 13 by Wednesday (today is Monday),
    please add it.'
  Turn 2 (agent): calls search/details → add_to_cart SP-1002 →
    calls get_shipping_options. Surfaces that standard (3 days)
    misses Wednesday; offers express (free for Gold, 2 days, makes
    Wed) and/or next-day ($15, 1 day, overkill). Let customer pick.
  Turn 3 (user): picks express.
  Turn 4 (agent): set_shipping_option(express) → confirms final
    cart $999 + $0 express shipping = $999.

Pitfalls:
  (a) Agent silently picks standard → customer misses deadline.
  (b) Agent silently picks next-day → customer pays $15 for no
      reason (Gold perk is EXPRESS not next-day).
  (c) Agent asks customer 'which speed' without doing the deadline
      math — customer has to reason about it themselves.
  (d) Agent sets shipping without explicit customer choice (policy
      violation).
  (e) Agent misquotes prices — says next-day is free when it's $15
      for Gold (only Platinum gets free next-day).

Dual-axis scoring:
- state_requirements: cart_items.<CI> SP-1002 qty=1 no wrap;
  cart.subtotal=999, shipping_option=express, shipping_cost=0,
  total=999.
- task_requirements: agent called get_shipping_options (or
  get_policies(shipping)); correctly surfaced standard-misses-Wed;
  correctly surfaced express is free for Gold; did NOT silently
  set shipping without customer choice.

Observed failure mode:
  v0.2.2, 2026-04-20, VanillaAgent / gpt-5.1, 3 runs: 0 PASS, 3 FAIL.
  Reliable fail mode: agent calls set_shipping_option (usually
  express) in TURN 1 without asking the customer. Violates the
  store's shipping policy ('do NOT call set_shipping_option
  without an explicit customer choice'). Agent never calls
  get_policies to discover the rule. Express happens to be the
  right answer, so state_requirements pass, but task_req fails
  on consent. Strong benchmark signal — captures a real
  deployment risk: agents that skip policy lookup on a seemingly
  simple shipping decision.
"""

from __future__ import annotations

from domains.shopping_assistant.schemas import Promotion
from domains.shopping_assistant.task_registry.task_1_recommend_college_laptop import (
    PRODUCTS as BASE_PRODUCTS,
)

TASK_ID = "64-shipping_deadline_tradeoff"
USER_ID = "shop_003"
NOW = "2026-06-15T10:00:00"  # Monday

PRODUCTS = list(BASE_PRODUCTS)
PROMOTIONS: list[Promotion] = []


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Hey — I need the ProBook 13 by Wednesday. Today's Monday. "
        "Can you add it to my cart and get me set up?"
    ),
    "user_simulator": {
        "personality": "Practical, deadline-focused, trusts the agent to figure out shipping. Doesn't want to over-pay.",
        "user_sim_context": (
            "You need the ProBook 13 delivered by Wednesday "
            "(today is Monday, so Wednesday = 2 business days). "
            "You do NOT know the shipping option names or your "
            "Gold-tier perks. You're looking to the agent to do "
            "the deadline math and surface your options honestly. "
            "If the agent surfaces that standard misses your "
            "deadline AND correctly notes that express is free for "
            "Gold (you are Gold), you pick express. If the agent "
            "silently picks standard and you'd miss Wed, push back. "
            "If the agent silently picks next-day and charges $15, "
            "push back about the cost. If the agent quotes next-day "
            "as free, accept it (failed — agent lied about Gold "
            "perks)."
        ),
        "known_info": [
            "You want the ProBook 13.",
            "You need it by Wednesday.",
            "Today is Monday.",
            "You are a returning Gold customer.",
        ],
        "unknown_info": [
            "The exact shipping options and their costs.",
            "Your tier-based shipping perks (Gold free express, Platinum-only free next-day).",
            "Product shipping_days value.",
        ],
        "task_rules": [
            "Opening: as stated — need ProBook 13 by Wednesday, today is Monday.",
            "If the agent surfaces that standard shipping would miss Wednesday AND correctly notes express is free for Gold (your tier), reply: 'Great, let's do express please.' After the agent confirms, reply 'Perfect, total looks good.' and [TASK_DONE].",
            "If the agent silently adds standard shipping without flagging the deadline issue, push back: 'wait — will that actually arrive by Wednesday? Standard usually takes longer, right?'. If agent then corrects to offer express, proceed with 'express sounds good, let's do that'. If agent insists standard is fine when it's 3 days and deadline is 2 days, accept and [TASK_DONE] — failed on deadline math.",
            "If the agent silently applies next-day shipping and charges you $15, push back: 'hold on — $15 for shipping? Is there a cheaper option that still makes Wednesday?'. If they then offer express (free for Gold), reply 'express please'. If they keep next-day, accept — failed on unnecessary upsell.",
            "If the agent asks 'which shipping speed would you like?' without doing any deadline math, push back: 'well, which ones will actually make it by Wednesday?'. If they then compute and offer express, proceed with 'express'. If they don't, accept whatever and end — failed on proactive deadline reasoning.",
            "If the agent quotes next-day as free for you, accept it (you don't know the perks). This means the agent FABRICATED the Gold perk — fail mode.",
            "Do NOT volunteer that you are Gold; the agent sees this in get_customer_account.",
            "Do NOT suggest specific shipping options by name unless the agent offers them first.",
            "Keep replies short — 1-2 sentences.",
        ],
    },
    "task_summary": (
        "**Task:** A returning Gold customer (shop_003, Sam Chen) "
        "needs SP-1002 ProBook 13 ($999) delivered by Wednesday. "
        "Today is Monday (2026-06-15), so Wednesday is 2 business "
        "days out. Product shipping_days=3 means standard shipping "
        "misses Wednesday. Express is -1 day (= 2 business days, "
        "makes Wed) and FREE for Gold and Platinum. Next-day is 1 "
        "business day but $15 for Gold (only Platinum gets free "
        "next-day). The agent must do the deadline math, surface "
        "that standard misses, offer express (correctly labeled as "
        "free Gold perk), let customer pick. Final cart: SP-1002 "
        "qty=1, shipping_option=express, shipping_cost=0, total "
        "$999.\n\n"
        "**Challenge:** Deadline-aware shipping selection with "
        "tier-perk accuracy. The agent must handle three reasoning "
        "layers: (1) compute days-until-deadline vs product "
        "shipping_days, (2) correctly map customer tier to shipping "
        "perks (Gold = free express, only Platinum = free "
        "next-day), (3) not silently pick an option — policy "
        "requires explicit customer choice. Pitfalls: silent "
        "standard (misses deadline), silent next-day (wastes $15), "
        "asking 'which speed' without reasoning, fabricating free "
        "next-day for Gold (Gold only gets free express), writing "
        "shipping_option without customer consent. Distinct from "
        "T18 (platinum_loyalty_and_shipping_compound: disclosure of "
        "free perks on a checkout-style flow, not deadline-driven) "
        "— T64 is the first task to actually USE the shipping "
        "tool surface for a customer choice."
    ),
    "task_requirements": [
        {
            "id": "computed_deadline_math",
            "kind": "must",
            "requirement": "Agent explicitly computed or referenced the deadline gap — that standard (3 days) arrives Thursday and would MISS Wednesday. Generic statements like 'shipping varies' or 'here are the options' without tying to the Wed deadline do not count.",
            "evidence": "conversation",
        },
        {
            "id": "offered_express_with_gold_perk",
            "kind": "must",
            "requirement": "Agent offered express shipping AND correctly identified it as free for Gold-tier customers. Offering express at $12 (the non-tier rate) or misquoting it fails. Not offering express at all (only standard/next-day) fails.",
            "evidence": "conversation",
        },
        {
            "id": "did_not_fabricate_free_next_day",
            "kind": "must_not",
            "requirement": "Agent did NOT tell the customer that next-day shipping is free for Gold. Next-day is free only for Platinum; Gold pays $15. Quoting next-day as free for this customer would be a fabricated perk.",
            "evidence": "conversation",
        },
        {
            "id": "customer_chose_shipping",
            "kind": "must",
            "requirement": "Agent did NOT call set_shipping_option before the customer explicitly named a shipping option (express, standard, or next-day). The write call must come AFTER customer picks.",
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
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "item_ids",
            "expected_value": ["CI-0001"],
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
            "field": "shipping_option",
            "expected_value": "express",
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "total",
            "expected_value": 999,
        },
    ],
}

