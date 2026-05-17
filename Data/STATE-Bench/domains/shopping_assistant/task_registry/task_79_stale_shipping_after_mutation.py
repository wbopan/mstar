"""Task 79 — Stale shipping cost after cart mutation.

Pitfall category: set_shipping_option writes cart.shipping_cost based on
cart contents at call time. Subsequent cart mutations (add_to_cart /
update_cart_item / remove_from_cart) re-compute subtotal / discount /
total via _recompute_cart — but NOT shipping_cost. So if shipping was
set at 3 items, then a later mutation pushes the cart over the 5+ free-
standard threshold, shipping_cost stays at the old $6 and customer
overpays. Agent must detect the stale state and re-call
set_shipping_option (or proactively alert the customer).

Scenario:
- Customer shop_004 (Taylor Kim, Standard, returning).
- Empty starting cart.
- Catalog: task_1 base (has SP-2006 dock $129 + SP-2005 webcam $79 plus
  filler products; no promos in scope).

Expected flow:
  Turn 1 (user): 'Add 2 ProBook docks and 1 PixelShot webcam,
    please. Standard shipping.'
  Turn 2 (agent): adds SP-2006 qty=2, adds SP-2005 qty=1. Reads
    get_shipping_options (3 units, standard = $6 since below 5+
    threshold). Calls set_shipping_option('standard'). Confirms:
    subtotal $337, shipping $6, total $343.
  Turn 3 (user): 'Actually I need 3 docks and 2 webcams total — add
    one more of each.'
  Turn 4 (agent): update_cart_item(SP-2006, qty=3),
    update_cart_item(SP-2005, qty=2). Now 5 units, subtotal $545 =
    3*$129 + 2*$79. Recognizes shipping cost is stale at $6 — the
    cart has crossed the 5+ threshold, standard is now free. Calls
    set_shipping_option('standard') again to refresh (or removes
    shipping via a recompute path). Confirms new total $545 with
    free standard. Proactively tells the customer the fee dropped.
  Turn 5 (user): 'nice — thanks.' [TASK_DONE].

Pitfalls:
  (a) Agent adds the extra units via update_cart_item and quotes
      total $551 (= $545 + stale $6). Customer overpays $6.
      PRIMARY SILENT FAIL.
  (b) Agent reads get_cart after the updates and sees shipping_cost
      $6 but doesn't recognize the 5+ threshold applies now; lets
      it ride.
  (c) Agent recognizes the stale state but doesn't tell the customer
      they crossed the threshold — just silently re-sets shipping
      and lets them discover the saving.
  (d) Agent never re-calls set_shipping_option and never reads the
      cart again after the updates, so the final total report is
      stale or extrapolated incorrectly.

Distinct from:
  - T75 (qty-cap collision when trying to cross threshold): T75's
    failure is about pivoting around the qty cap. T79's failure is
    about re-reading shipping state after a cart mutation.
  - T56 (stale_seeded_total_price_drop): T56 is about PRICES changing
    on resume. T79 is about SHIPPING changing because of an item-
    count threshold.

Dual-axis scoring:
- state_requirements: dock qty=3, webcam qty=2, shipping_option=
  'standard', shipping_cost=0, subtotal=$545, total=$545.
- task_requirements: agent re-evaluated shipping after the cart
  mutation; proactively told the customer shipping is now free;
  final shipping cost=0; did NOT quote a stale $551 total.

Observed failure mode:
  Expected v0.2.2 benchmark failure: agents that treat shipping as a
  one-and-done decision. The env does not re-evaluate shipping on
  cart mutation — it's the agent's responsibility to notice when a
  threshold is crossed.
"""

from __future__ import annotations

from domains.shopping_assistant.schemas import Promotion

TASK_ID = "79-stale_shipping_after_mutation"
USER_ID = "shop_004"
NOW = "2026-06-12T10:00:00"

PROMOTIONS: list[Promotion] = []


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Hi — please add 2 ProBook USB-C docks and 1 PixelShot "
        "webcam to my cart. Use standard shipping."
    ),
    "user_simulator": {
        "personality": "Practical buyer provisioning equipment. Not pushing back on shipping math; assumes the agent handles it correctly.",
        "user_sim_context": (
            "You first need 2 docks and 1 webcam with standard "
            "shipping. Then mid-conversation you realize you need "
            "more — you'll ask to bump to 3 docks and 2 webcams. "
            "You don't know about shipping thresholds or how cart "
            "updates affect the fee. You assume whatever total the "
            "agent quotes is correct."
        ),
        "known_info": [
            "You want ProBook USB-C docks and PixelShot webcams.",
            "You want standard shipping.",
            "You are a returning Standard-tier customer.",
        ],
        "unknown_info": [
            "The 5+ threshold for free standard shipping.",
            "That set_shipping_option isn't re-run on cart updates.",
            "The actual shipping cost at different cart sizes.",
        ],
        "task_rules": [
            "Opening: as stated — 2 docks + 1 webcam + standard shipping.",
            "After the agent confirms the first cart (should be 3 units + $6 shipping + total around $343), reply: 'Actually, let's make it 3 docks and 2 webcams total. Add one more of each.'",
            "If the agent updates the cart AND recognizes shipping is now free (5+ units) AND re-sets standard to refresh the cost AND tells you shipping dropped to $0, reply: 'oh nice, thanks!' Confirm $545 and [TASK_DONE].",
            "If the agent updates and quotes a total around $551 (stale $6 shipping still on), accept the number without question — you don't know the threshold. [TASK_DONE]. Agent failed silently.",
            "If the agent updates and says something vague like 'your new total is around $550', ask: 'what's shipping on this?'. If they then notice the stale fee and refresh it, proceed. If they confirm $6, accept.",
            "If the agent silently re-sets shipping to $0 without telling you (total is $545 but they don't mention why), accept the number but don't reward them — they got state right but failed on disclosure.",
            "Do NOT bring up loyalty, promos, welcome, or gift wrap.",
            "Keep replies short — 1-2 sentences.",
        ],
    },
    "task_summary": (
        "**Task:** A Standard-tier returning customer (shop_004) "
        "adds 2 ProBook docks ($129 ea) + 1 PixelShot webcam ($79) "
        "with standard shipping ($6, since below 5+ threshold). "
        "Total $343. Then updates to 3 docks + 2 webcams (5 units, "
        "subtotal $545). The 5+ threshold makes standard shipping "
        "free, but _recompute_cart does NOT re-evaluate shipping on "
        "cart mutation — shipping_cost stays stale at $6. Agent must "
        "detect the stale state, re-call set_shipping_option to "
        "refresh (or recognize the implicit recompute path), and "
        "proactively tell the customer shipping is now free. Final: "
        "dock qty=3, webcam qty=2, shipping_option='standard', "
        "shipping_cost=0, total $545.\n\n"
        "**Challenge:** Shipping state is decoupled from cart "
        "recompute. The agent must know this — or at least "
        "re-read shipping options after every cart update. Primary "
        "failure: trusting the initial set_shipping_option call as "
        "permanent. Distinct from T75 (qty-cap collides with "
        "threshold) and T56 (stale prices on resume). T79 is "
        "specifically the threshold-crossing + stale shipping axis."
    ),
    "task_requirements": [
        {
            "id": "refreshed_shipping_after_mutation",
            "kind": "must",
            "requirement": "Agent re-evaluated shipping AFTER the cart update (either via a second set_shipping_option call or via get_shipping_options + recognition). Final shipping_cost must be 0. If the agent never re-touches shipping, shipping_cost stays stale at $6 and state fails.",
            "evidence": "tool_calls",
        },
        {
            "id": "disclosed_threshold_crossing",
            "kind": "must",
            "requirement": "Agent proactively told the customer that standard shipping is now free because the cart crossed the 5+ threshold. Silently refreshing without disclosure does not satisfy this — the customer should know why their total dropped.",
            "evidence": "conversation",
        },
        {
            "id": "correct_final_total",
            "kind": "must",
            "requirement": "Agent quoted the correct final total of $545 (subtotal with free shipping). Quoting $551 (= subtotal + stale $6) fails.",
            "evidence": "conversation",
        },
        {
            "id": "did_not_overcharge_shipping",
            "kind": "must_not",
            "requirement": "Agent did NOT finalize the cart with shipping_cost still at $6 (the stale value). Final cart must show shipping_cost=0.",
            "evidence": "tool_calls",
        },
    ],
    "state_requirements": [
        {
            "entity_type": "cart_items",
            "match_fields": {
                "customer_id": USER_ID,
                "product_id": "SP-2006",
            },
            "expected_fields": {"quantity": 3, "gift_wrap": False},
        },
        {
            "entity_type": "cart_items",
            "match_fields": {
                "customer_id": USER_ID,
                "product_id": "SP-2005",
            },
            "expected_fields": {"quantity": 2, "gift_wrap": False},
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "subtotal",
            "expected_value": 545,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "shipping_option",
            "expected_value": "standard",
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "shipping_cost",
            "expected_value": 0,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "total",
            "expected_value": 545,
        },
    ],
}

