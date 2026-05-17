"""Task 37 — History-driven complementary accessory recommendation.

Pitfall category: open-ended 'recommend for me' request that
requires the agent to anchor recommendations in the customer's
purchase_history rather than generic best-sellers. Customer owns
SP-1002 ProBook Laptop 13-inch (in purchase_history) and asks
what accessories they should consider. Agent should:
  1. Read purchase_history → SP-1002 ProBook 13.
  2. Search for accessories that pair naturally (same brand, dock
     category, or compatible peripherals).
  3. Recommend SP-2006 ProBook USB-C Dock ($129) — explicit brand
     match, accessory category, genuinely complementary to the
     owned laptop.
  4. Explain the reasoning linking the recommendation to the
     laptop from history.
  5. Add after consent.

Pitfalls:
  (a) Agent asks 'what kind of accessories?' pushing the work
      back to the customer instead of using profile data.
  (b) Agent recommends best-selling generic accessories (e.g.
      SoundMax headphones) without connecting to the owned
      laptop — misses the 'for what I own' framing.
  (c) Agent reads profile but recommends a SlimBook-branded
      accessory (brand mismatch — incompatible with ProBook in
      this catalog's schema).
  (d) Agent recommends multiple items without explaining the
      link to the laptop, treating it as generic recommendation.

Correct: agent calls get_customer_account, sees SP-1002 ProBook
Laptop 13-inch in purchase_history, searches for ProBook-brand
accessories (or USB-C dock / laptop accessory category), finds
SP-2006 ProBook USB-C Dock, explicitly references the laptop
('for your ProBook 13, the matching USB-C dock adds HDMI +
Ethernet for desk use'), gets consent, adds SP-2006.

Scenario:
- Customer: shop_003 (Sam Chen, Gold, returning, 18.5k pts).
- purchase_history override: ['SP-1002'].
- Catalog: T1 BASE_PRODUCTS (SP-2006 ProBook USB-C Dock $129).
- Promotions: none.
- now=2026-06-12.

Math:
  SP-2006 ProBook USB-C Dock = $129, qty=1, no wrap. Total $129.

Dual-axis scoring:
- state_requirements: cart has SP-2006 qty=1 no wrap, total $129.
- task_requirements: agent called get_customer_account, referenced
  the ProBook from purchase_history in reasoning, recommended a
  ProBook-brand-matching accessory (SP-2006), added after consent.

Observed failure mode:
  v0.2.2, 2026-04-18, VanillaAgent / gpt-5.1, iter 1:
  Turn 1: agent asked the customer what their main device was
  ('to recommend something that truly fits your setup, I need
  to know what you already own') instead of checking
  purchase_history proactively. Customer pushed back ('check
  my profile — you should have that info'). Turn 2: agent
  then called get_customer_account, found SP-1002, correctly
  recommended SP-2006 with good reasoning, and added after
  consent. 3/4 task_reqs passed — but read_purchase_history
  FAILED because the lookup was reactive (after pushback) not
  proactive (before the first response). Composite FAIL.
  Reliable fail mode: gpt-5.1 treats purchase_history as
  optional context it can ask the customer to provide, rather
  than canonical profile data it should consult first on any
  'for me' framing. The agent had every tool needed but used
  them in the wrong order. Distinct from T33 (which also
  tested profile-before-write, but where the customer never
  mentioned a reason to check): here the customer's framing
  ('pair well with what I ALREADY OWN') is an explicit signal
  to read profile first.
"""

from __future__ import annotations

from domains.shopping_assistant.schemas import Promotion

TASK_ID = "37-history_driven_accessory"
USER_ID = "shop_003"
NOW = "2026-06-12T10:00:00"


PROMOTIONS: list[Promotion] = []


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Can you recommend an accessory that would pair well with what "
        "I already own? I'd like something useful for my setup."
    ),
    "user_simulator": {
        "personality": "Open-ended, trusts the agent to do the work. Won't spoon-feed context.",
        "user_sim_context": (
            "You already own an SP-1002 ProBook Laptop 13-inch (it's in "
            "your purchase_history — bought previously). You are asking "
            "the agent to recommend a USEFUL accessory for that laptop, "
            "but you do NOT mention the laptop by name — you expect the "
            "agent to check your profile and figure it out. You want a "
            "genuinely complementary accessory, not a generic gadget. "
            "The test is whether the agent reads purchase_history, "
            "anchors the recommendation in your owned laptop, and "
            "picks a compatible/matching accessory."
        ),
        "known_info": [
            "You already own an SP-1002 ProBook Laptop 13-inch.",
            "You want a useful accessory for your setup.",
            "You are a returning customer.",
            "(Internal: Gold tier, 18.5k pts, but you don't volunteer this.)",
        ],
        "unknown_info": [
            "Specific catalog items, prices, or compatibility details.",
            "Which brand of accessory pairs best with ProBook.",
        ],
        "task_rules": [
            "Opening: the vague 'what pairs well with what I own' message. Do NOT name the ProBook yourself.",
            "If the agent asks 'what laptop do you own?' or similar, reply: 'check my profile — you should have that info'. Push the work back to the agent. This counts against the profile-lookup task_req (agent should have looked first).",
            "If the agent recommends SP-2006 ProBook USB-C Dock and explicitly ties the reasoning to your ProBook laptop (e.g. 'for your ProBook 13, this dock adds HDMI/Ethernet'), and asks to add it — reply with go-ahead. Do NOT include [TASK_DONE] in this message; wait for confirmation.",
            "Only end with [TASK_DONE] AFTER the agent has confirmed SP-2006 is in the cart.",
            "If the agent recommends SP-2006 but does NOT reference the ProBook from purchase_history in the reasoning, accept and end. Agent has failed on reasoning-link requirement.",
            "If the agent recommends a different accessory that matches a DIFFERENT brand (e.g. SlimBook accessory) or is a generic best-seller without link to your laptop (e.g. headphones, blender), accept and end. Agent has failed.",
            "If the agent recommends MULTIPLE accessories, push back: 'just the single best one for my setup'. Then let them pick one.",
            "Do NOT ask about gift wrap, loyalty, promos, shipping, bundles.",
            "Do NOT volunteer the ProBook name — rely on the agent to find it via profile.",
            "Keep replies short.",
        ],
    },
    "task_summary": (
        "**Task:** A returning Gold customer (shop_003) owns SP-1002 "
        "ProBook Laptop 13-inch (in purchase_history, not mentioned "
        "in conversation). They ask open-ended: 'recommend an "
        "accessory that pairs well with what I already own'. Correct "
        "pick: SP-2006 ProBook USB-C Dock ($129) — brand match, "
        "complementary category.\n\n"
        "**Challenge:** Profile-anchored recommendation on a vague "
        "request. Multi-step: (1) call get_customer_account to read "
        "purchase_history, (2) identify the owned laptop, (3) search "
        "for a brand-matching accessory, (4) recommend with reasoning "
        "that cites the owned laptop explicitly, (5) add after "
        "consent. Pitfall: agent bounces the question back ('what "
        "kind of accessories?') instead of reading profile, or "
        "recommends generic best-sellers. Correct: use profile as "
        "the primary constraint. Distinct from T11 (upgrade brand "
        "continuity), T33 (duplicate detection), and T34 (latent "
        "second device) — each exercises purchase_history for a "
        "different purpose. T37 specifically tests complementary "
        "accessory reasoning."
    ),
    "task_requirements": [
        {
            "id": "read_purchase_history",
            "kind": "must",
            "requirement": "Agent called get_customer_account for shop_003 to read purchase_history BEFORE recommending an accessory. Recommending or asking the customer what they own (when the profile already answers) fails.",
            "evidence": "tool_calls",
        },
        {
            "id": "referenced_owned_laptop",
            "kind": "must",
            "requirement": "Agent explicitly referenced the customer's owned ProBook Laptop 13-inch (or 'ProBook 13' / 'your ProBook') in the recommendation reasoning. Generic 'this is a great accessory' without linking to the owned product fails.",
            "evidence": "conversation",
        },
        {
            "id": "recommended_probook_match",
            "kind": "must",
            "requirement": "Agent recommended SP-2006 ProBook USB-C Dock (brand match: both ProBook). Recommending a different-brand accessory or a generic item (SoundMax headphones, AlpineGear backpack, etc.) fails.",
            "evidence": "conversation",
        },
        {
            "id": "correct_product_added",
            "kind": "must",
            "requirement": "Agent added exactly SP-2006 ProBook USB-C Dock to the cart with quantity=1, gift_wrap=False.",
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
                "product_id": "SP-2006",
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
            "expected_value": 129,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "total",
            "expected_value": 129,
        },
    ],
}

