"""Task 11 — Profile-driven upgrade recommendation (check purchase_history first).

Pitfall category: using customer profile data to contextualize a vague
request. The customer says 'I want to upgrade my laptop' WITHOUT naming
what they currently own. Their profile's purchase_history contains
SP-1001 SlimBook Air 13, which the agent must check via
get_customer_account. Correct behavior: look up the profile, see the
existing SlimBook, recommend a same-brand upgrade (SP-1107 SlimBook
Touch 15, $1099) rather than generic options. Pitfall: agent asks the
customer to specify what they own (pushing work the agent should do
itself via the profile), or recommends a different-brand laptop.

Scenario (reuses Task 1's catalog):
- Customer: shop_003 (Sam Chen, Gold tier, not-first-time). We override
  purchase_history in-task to include SP-1001 so the profile is the
  signal. This keeps user_attributes.py untouched.
- Catalog: identical to Task 1.
- Promotions: none.

Expected flow:
  Turn 1: customer asks for an 'upgrade' vaguely. Agent should call
    get_customer_account, see SP-1001 in purchase_history, and use that
    to anchor the recommendation.
  Turn 2+: agent recommends a same-brand upgrade from SlimBook's line.
    Best in-catalog upgrade from SP-1001 (2.6lb/8GB/$849) is SP-1107
    SlimBook Touch 15 (4lb/16GB/$1099): touchscreen, 2x storage, 2x RAM,
    larger screen. Agent adds it after customer confirms.

Dual-axis scoring:
- state_requirements: cart has SP-1107 (qty 1, no gift wrap).
  subtotal=1099, total=1099. If agent recommends wrong product (e.g.
  ProBook, or no-brand match), state fails.
- task_requirements: agent called get_customer_account AND referenced
  the SlimBook from purchase_history when recommending.

Observed failure mode (v0.2.2, 2026-04-17, VanillaAgent / gpt-5.1):
  Agent DID call get_customer_account AND referenced the existing
  SlimBook Air 13 from purchase_history when comparing specs. But the
  agent's PRIMARY upgrade pitch was the ProBook Laptop 13-inch (SP-1002),
  treating the customer's existing SlimBook as a spec reference rather
  than a brand-preference signal. SlimBook Touch 15 came up only as a
  secondary option. When the sim insisted on staying in the SlimBook
  family, the agent pivoted and added SP-1107 — but by then the primary-
  recommendation failure had fired. One task_req failed:
  recommended_same_brand_upgrade. Real pitfall: agent optimizes for "best
  spec fit" rather than honoring brand continuity from purchase history.
"""

from __future__ import annotations

from domains.shopping_assistant.schemas import Promotion

TASK_ID = "11-profile_driven_upgrade"
USER_ID = "shop_003"
NOW = "2026-06-12T10:00:00"


PROMOTIONS: list[Promotion] = []


# ---------------------------------------------------------------------------
# Task JSON
# ---------------------------------------------------------------------------

TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Hey — I'd like to upgrade my laptop. I've bought from you before. What would "
        "you recommend?"
    ),
    "user_simulator": {
        "personality": "Casual. Expects the agent to use customer profile context without being asked. Will not name the current laptop unprompted — the store already has that information.",
        "user_sim_context": (
            "You are a returning Gold-tier shopper who bought the SlimBook Air 13 a while back "
            "and wants to upgrade to something better. You believe the store's agent should "
            "know what you own from your profile. You have a budget of ~$1,200."
        ),
        "known_info": [
            "You own a SlimBook Air 13 (SP-1001) and want to upgrade.",
            "You prefer staying with the same brand family (SlimBook) since you liked the Air.",
            "Budget is around $1,200.",
        ],
        "unknown_info": [
            "The specific SlimBook upgrade options and their specs.",
            "Prices of upgrade laptops in the catalog.",
        ],
        "task_rules": [
            "You will NOT name your current laptop unless the agent explicitly asks. You expect them to check your profile first.",
            "If the agent asks what you currently own WITHOUT first checking your profile, you are mildly annoyed — tell them you'd expect that info to be on file.",
            "If the agent recommends a same-brand SlimBook upgrade with better specs (RAM, storage, screen, etc.) AND confirms it fits your ~$1,200 budget, accept and ask them to add it to your cart.",
            "If the agent recommends a different-brand laptop (ProBook, SlateTab, etc.) without acknowledging your SlimBook preference, push back — say you liked the SlimBook family and want to stay with it.",
            "If the agent offers multiple upgrade options, pick the SlimBook-brand one.",
            "Decline gift wrap if asked.",
            "Do not ask about promos, discounts, loyalty points, or brand bundles.",
            "When the agent has added the SlimBook upgrade to your cart and summarized the total, end your next message with [TASK_DONE].",
        ],
    },
    "task_summary": (
        "**Task:** A returning Gold-tier customer (shop_003) asks vaguely for 'an upgrade to my "
        "laptop'. Their purchase_history contains SP-1001 SlimBook Air 13. The correct upgrade "
        "path is same-brand: SP-1107 SlimBook Touch 15 ($1,099) — bigger screen, 2x RAM, 2x "
        "storage, touchscreen, within budget.\n\n"
        "**Challenge:** The customer expects the agent to use profile data. Pitfall: agent asks "
        "the customer to name their current laptop rather than calling get_customer_account to "
        "find it. Second pitfall: agent recommends a non-SlimBook laptop, missing the brand "
        "preference signal implicit in 'upgrade my current SlimBook.' The task tests profile-"
        "aware personalization — does the agent mine the customer record rather than asking "
        "redundant questions?"
    ),
    "task_requirements": [
        {
            "id": "checked_customer_profile",
            "kind": "must",
            "requirement": "Agent called get_customer_account (or equivalent) to read the customer's purchase_history before asking the customer to specify what they currently own.",
            "evidence": "tool_calls",
        },
        {
            "id": "referenced_current_laptop",
            "kind": "must",
            "requirement": "Agent referenced the customer's current SlimBook Air 13 (from purchase_history) in the recommendation reasoning. Generic 'here are some good laptops' without connecting to the profile fails.",
            "evidence": "conversation",
        },
        {
            "id": "recommended_same_brand_upgrade",
            "kind": "must",
            "requirement": "Agent recommended a SlimBook-brand upgrade (SP-1107 SlimBook Touch 15) as the primary suggestion, citing the brand continuity with the customer's existing Air 13.",
            "evidence": "conversation",
        },
        {
            "id": "correct_product_added",
            "kind": "must",
            "requirement": "Agent added exactly SP-1107 (SlimBook Touch 15) to the cart via add_to_cart with quantity 1 and gift_wrap=False.",
            "evidence": "tool_calls",
        },
        {
            "id": "no_redundant_question",
            "kind": "must_not",
            "requirement": "Agent must NOT ask the customer to name their current laptop BEFORE checking get_customer_account. Asking the customer first when the info is in their profile is redundant and signals the agent isn't using profile data.",
            "evidence": "conversation",
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
                "product_id": "SP-1107",
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
            "expected_value": 1099,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "total",
            "expected_value": 1099,
        },
    ],
}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

