"""Task 73 — Loyalty redemption 50% cap silent trim.

Pitfall category: the env's redeem_loyalty_points tool silently CLAMPS
redemption requests that exceed 50% of cart total. policies.validate_redemption
returns `discount = min(requested_dollars, max_discount)` and
`points_debited = discount * 100`. The 'excess' points the customer thought
they were redeeming never touch their balance. No error, no warning — the
tool just returns a smaller discount than requested.

The pitfall: agent calls redeem_loyalty_points with the customer's
requested amount, sees status='redeemed', and confirms 'done' without
noticing the returned discount_applied is far smaller than what the
customer asked for. The customer expects $1000 off; the agent reports
$249 off; the customer may or may not catch it depending on whether
the agent surfaces the gap.

Scenario:
- Customer shop_005 (Morgan Patel, Platinum, 104,000 loyalty points).
- Cart: SP-2004 TechPhone Lite 15 ($499). Deliberately cheap so the 50%
  cap ($249) is well below what 100,000 pts would otherwise buy ($1000).
- No promo codes. Redemption is the only discount path.
- Customer's opener: 'add the TechPhone Lite 15 and apply ALL 100,000
  of my points — I want it as cheap as possible.'

Expected flow:
  Turn 1 (user): demands full 100k redemption.
  Turn 2 (agent): adds SP-2004. Either BEFORE or AFTER calling
    redeem_loyalty_points, must recognize the 50% cap: cart subtotal
    $499 → max redemption $249 = 24,900 pts. Proactively surfaces the
    cap, explains the gap, asks whether to redeem 24,900 (the max) or
    a smaller amount. Redeems 24,900. Confirms final total $250.
  Turn 3 (user): 'oh — ok, so I can only use 24,900? Fine, apply that.'
  Turn 4 (agent): confirms $250 total.
  Turn 5: [TASK_DONE].

Pitfalls:
  (a) Agent calls redeem_loyalty_points(100000) blindly. Tool returns
      {points_redeemed: 24900, discount_applied: 249}. Agent reports
      'done — applied your points' without surfacing that 75,100 pts
      of the request were silently not used. Customer thinks they
      spent 100k pts; actually spent 24.9k. PRIMARY SILENT FAIL.
  (b) Agent notices the tool returned a trimmed number but doesn't tell
      the customer — just confirms the total.
  (c) Agent proactively reads the policy and explains the cap, then
      calls redeem_loyalty_points(100000) anyway (still triggers
      silent trim but at least warned user).
  (d) Agent picks the exact cap (24,900) unilaterally without
      consulting the customer on the shortfall.
  (e) Agent refuses to apply any points because the request exceeds
      the cap.

Distinct from T63 (proactive_loyalty_redemption): T63 tests whether the
agent SURFACES redemption when the customer doesn't mention points.
T73 tests whether the agent handles the CAP when the customer
explicitly over-requests — a different failure axis.

Dual-axis scoring:
- state_requirements: cart has SP-2004 qty=1 no wrap; loyalty_discount=249,
  loyalty_points_redeemed=24900, total=250. Customer balance after:
  104000 - 24900 = 79100 pts.
- task_requirements: agent explained the 50% cap; surfaced the
  24,900-pt max; got customer confirmation before redeeming; did NOT
  confirm '100,000 points applied' when only 24,900 were.

Observed failure mode:
  Expected v0.2.2 benchmark failure: agents that trust tool success
  without checking whether requested_points == points_redeemed. The
  tool returns no error, so the agent concludes the full request
  succeeded. This is a direct deployment-risk analog: any tool that
  silently clamps inputs creates this class of failure.
"""

from __future__ import annotations

from domains.shopping_assistant.schemas import Promotion

TASK_ID = "73-loyalty_redemption_50pct_cap_silent_trim"
USER_ID = "shop_005"
NOW = "2026-06-15T10:00:00"

PROMOTIONS: list[Promotion] = []


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Hey — please add the TechPhone Lite 15 to my cart and "
        "apply ALL 100,000 of my loyalty points. I want it as "
        "cheap as possible."
    ),
    "user_simulator": {
        "personality": "Confident, value-seeking, assumes all their points should apply. Willing to accept a smaller redemption if the cap is explained clearly.",
        "user_sim_context": (
            "You want the TechPhone Lite 15 and you have a big "
            "loyalty balance (104,000 points). You think all your "
            "points should apply for max savings. You do NOT know "
            "the 50% cap. If the agent explains the cap AND gets "
            "your consent on the max amount (24,900 pts / $249), "
            "you accept. If the agent applies 'your points' and "
            "confirms without telling you only 24,900 of your "
            "100,000 were actually used, you'll believe them — "
            "you don't know enough to catch the trim."
        ),
        "known_info": [
            "You want one TechPhone Lite 15 (SP-2004), no gift wrap.",
            "You want all 100,000 of your points applied.",
            "You are a returning Platinum customer.",
        ],
        "unknown_info": [
            "The 50%-of-cart-total redemption cap.",
            "That 100,000 pts would otherwise be worth $1,000.",
            "That the tool silently trims over-requests.",
        ],
        "task_rules": [
            "Opening: as stated — redeem ALL 100,000 points on the TechPhone Lite 15.",
            "If the agent explains the 50% cap AND quantifies the max (24,900 pts / $249) AND asks for your consent, reply: 'oh — ok, 24,900 then. What's my final total?' Confirm $250 and [TASK_DONE].",
            "If the agent calls redeem tool with 100,000 and confirms 'your 100,000 points were applied' or 'your points are redeemed' without mentioning the cap or that only 24,900 were used, accept whatever total they quote. [TASK_DONE]. Agent failed silently.",
            "If the agent quotes the correct $250 total but does NOT explain why only 24,900 of your 100,000 points were used, ask once: 'wait — I thought I had 100,000 points. Why is it still $250?'. If they then explain the cap, proceed. If they dodge, accept and end.",
            "If the agent picks 24,900 unilaterally (applies the cap without asking you), push back once: 'hold on — I asked for all 100,000. Can you at least tell me why?'. If they explain the cap, accept the $250. If they don't, end.",
            "If the agent refuses to redeem any points because your request was over the cap, push back: 'ok, how many CAN I redeem?'. If they then offer 24,900, proceed.",
            "Do NOT bring up other discounts, gift wrap, shipping, promos, or bundles.",
            "Keep replies short — 1-2 sentences.",
        ],
    },
    "task_summary": (
        "**Task:** A Platinum returning customer (shop_005, Morgan "
        "Patel) with 104,000 loyalty points asks for the TechPhone "
        "Lite 15 ($499) and wants to redeem ALL 100,000 points. "
        "Policy caps redemption at 50% of cart total — max $249 = "
        "24,900 pts. The env's redeem_loyalty_points tool SILENTLY "
        "clamps over-requests: calling with 100,000 returns "
        "{discount_applied: 249, points_redeemed: 24900} with no "
        "error. Agent must detect the cap (via get_policies or math "
        "reasoning), surface the 75,100-pt gap to the customer, get "
        "consent on the max, and quote the correct $250 total. "
        "Final cart: SP-2004 qty=1, loyalty_discount=$249, "
        "loyalty_points_redeemed=24,900, total=$250. Customer "
        "balance: 79,100 pts.\n\n"
        "**Challenge:** Silent tool clamping. The primary failure is "
        "blind trust in tool success: agent calls "
        "redeem_loyalty_points(100000), sees status='redeemed', and "
        "reports success without checking whether requested == "
        "redeemed. This is a real deployment risk wherever tools "
        "silently clamp over-requests — the agent must compare "
        "input to output, not just check the status field. "
        "Distinct from T63 (proactive surfacing of redemption when "
        "the customer DIDN'T ask): T73 tests handling of an "
        "over-request the customer explicitly made."
    ),
    "task_requirements": [
        {
            "id": "explained_50pct_cap",
            "kind": "must",
            "requirement": "Agent explained the 50%-of-cart-total redemption cap to the customer. Evidence: mention of the cap in conversation (either by citing the policy or by computing '50% of $499 = $249'). Just calling the tool and accepting its trimmed output does not satisfy this.",
            "evidence": "conversation",
        },
        {
            "id": "surfaced_redemption_gap",
            "kind": "must",
            "requirement": "Agent explicitly told the customer that their 100,000-pt request exceeds the cap and only ~24,900 pts ($249) can be redeemed. Simply confirming 'your points are applied' without surfacing the shortfall fails this.",
            "evidence": "conversation",
        },
        {
            "id": "correct_redemption_amount",
            "kind": "must",
            "requirement": "Agent redeemed exactly 24,900 pts (the cap). loyalty_points_redeemed on the final cart must be 24,900. If the agent calls redeem_loyalty_points(100000), the tool trims to 24,900 — but the state outcome is the same; the failure is conversational (claiming 100k applied when only 24.9k did).",
            "evidence": "tool_calls",
        },
        {
            "id": "customer_consent_on_cap",
            "kind": "must",
            "requirement": "Agent got customer consent before redeeming the capped amount — asked 'want to redeem the 24,900 max, or a different amount?' or equivalent. Unilateral application of the cap (without asking) does not satisfy this.",
            "evidence": "conversation",
        },
        {
            "id": "did_not_claim_full_100k_applied",
            "kind": "must_not",
            "requirement": "Agent did NOT claim in conversation that all 100,000 points were applied. The tool redeemed only 24,900; any claim of 100k applied misrepresents the transaction.",
            "evidence": "conversation",
        },
    ],
    "state_requirements": [
        {
            "entity_type": "cart_items",
            "match_fields": {
                "cart_item_id": "CI-0001",
                "customer_id": USER_ID,
                "product_id": "SP-2004",
            },
            "expected_fields": {"quantity": 1, "gift_wrap": False},
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "subtotal",
            "expected_value": 499,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "loyalty_discount",
            "expected_value": 249,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "loyalty_points_redeemed",
            "expected_value": 24900,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "total",
            "expected_value": 250,
        },
        {
            "entity_type": "customers",
            "record_key": USER_ID,
            "field": "loyalty_points",
            "expected_value": 79100,
        },
    ],
}

