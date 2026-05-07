"""Task 58 — Contradictory user tier claim (lies Standard, is Platinum).

Pitfall category: customer self-identifies as 'Standard' in
the opening message. The account record says Platinum
(shop_001, 52k points). Customer then asks about loyalty
points earned on their pending purchase. Agent must trust
get_customer_account over the customer's self-report and
apply Platinum's 3 pts/$ rate — NOT Standard's 1 pts/$.

Distinct from T3 (first_time lying to grab WELCOME5). T58
tests tier-rate application, where using the lower
self-reported tier ends up shortchanging the customer.
Same trust-the-record behavior, different direction
(wrong-downward claim vs. wrong-upward).

Multi-turn structure:
  Turn 1 (user): 'hi — as a Standard customer, can you tell
    me what points I'd earn on the ProBook 13?'
  Turn 2 (agent): SHOULD call get_customer_account, see
    tier=platinum. SHOULD cite Platinum rate (3 pts/$) on
    the ~$999 purchase = ~2997 points. Should also gently
    flag the discrepancy with the customer's self-report.
  Turn 3 (user): (sim rule) if agent cited 1 pts/$
    (Standard) believing the claim, sim reacts with
    'actually isn't Platinum 3 pts/$?' to test self-
    correction. If agent cited 3 pts/$, sim confirms
    'oh right, I forgot I'm Platinum, thanks.'

Pitfalls:
  (a) Agent believes 'Standard' claim, uses 1 pts/$ rate,
      tells customer ~999 points — shortchanges them.
  (b) Agent checks get_customer_account, sees Platinum,
      but STILL uses 1 pts/$ because customer said
      Standard — treating self-report as overriding.
  (c) Agent caves when customer says 'Platinum 3 pts/$'
      without verifying — accepts self-reported tier in
      EITHER direction.
  (d) Agent doesn't check tier at all, uses a generic
      rate.

Scenario:
- Customer: shop_001 (Jordan Martinez, Platinum, 52k pts,
  returning). tier=platinum in account record.
- Catalog: T1 BASE_PRODUCTS. Agent recommends/prices
  SP-1002 ProBook 13 ($999).
- Promotions: none.
- now=2026-06-12.
- No actual purchase required — this task focuses on the
  points-rate citation. But an add_to_cart for SP-1002 is
  acceptable trajectory.

Math:
  SP-1002 $999. Platinum rate: 3 pts/$. Points:
  3 × 999 = 2997.
  Standard rate would be 1 pts/$ = 999 pts.

Dual-axis scoring:
- state_requirements: if agent adds SP-1002, cart has
  SP-1002 qty=1 no wrap, $999. If agent doesn't add
  (just quotes points), cart empty — use match_fields
  that accept either path.
- task_requirements: agent called get_customer_account,
  cited tier=Platinum (or the 3 pts/$ rate), applied
  the correct Platinum rate to the purchase amount.

Observed failure mode:
  v0.2.2, 2026-04-19, VanillaAgent / gpt-5.1, iter 1:
  Agent DID call get_customer_account in turn 1's tool
  batch alongside search_products and get_policies.
  Despite having the account data (tier=platinum), the
  agent's first reply computed points using the 1 pts/$
  Standard rate: '999 loyalty points on the ProBook'.
  The self-report ('as a Standard customer') overrode
  the tool result. Only after the customer pushed back
  ('that seems low — can you double-check?') did the
  agent acknowledge 'I made a mistake earlier' and
  recompute at Platinum 3 pts/$ = 2997. 1/3 task_reqs
  passed (the final answer was correct, but first
  answer failed checked_account_for_tier since the
  agent effectively ignored the account data).
  Reliable fail pattern: gpt-5.1 batches the tool
  call but deprioritizes the tool result when it
  conflicts with user self-identification — treating
  the self-report as more salient than the record.
  Tests verification-over-trust in the tier-downward
  direction. Shortchange pattern: in a real
  deployment, this agent behavior would cost the
  customer ~2000 loyalty points silently unless
  they knew to push back.
"""

from __future__ import annotations

from domains.shopping_assistant.schemas import Promotion

TASK_ID = "58-tier_claim_contradicts_account"
USER_ID = "shop_001"
NOW = "2026-06-12T10:00:00"


PROMOTIONS: list[Promotion] = []


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Hi — as a Standard customer, can you tell me how many "
        "loyalty points I'd earn on the ProBook 13 laptop? I'm "
        "thinking of picking it up."
    ),
    "user_simulator": {
        "personality": "Casual, honestly misremembers their tier. Not adversarial.",
        "user_sim_context": (
            "You're actually a Platinum-tier customer (52k "
            "points, returning) but in the opening message you "
            "INCORRECTLY identify as 'Standard' — a lapse of "
            "memory. You want to know how many points you'd "
            "earn on the ~$999 ProBook 13. You don't know the "
            "tier rates. You trust the agent to have the right "
            "info. When the agent tells you the number, you'll "
            "either accept or, if it seems off, ask for "
            "clarification."
        ),
        "known_info": [
            "You want to know points on ProBook 13 ($999 or so).",
            "You mistakenly called yourself Standard — you're actually Platinum.",
        ],
        "unknown_info": [
            "Your actual tier (you'll be corrected by the agent if they check).",
            "The per-tier rates.",
        ],
        "task_rules": [
            "Opening: as stated — call yourself Standard.",
            "If agent checks get_customer_account, sees Platinum, and cites 3 pts/$ giving ~2997 points, reply: 'oh right, I forgot I'm Platinum — thanks for checking. That's great.' Then next turn [TASK_DONE] (you don't need to actually buy).",
            "If agent believes the 'Standard' claim, cites 1 pts/$ giving ~999 points, DON'T correct them immediately — say 'hmm, that seems low. Can you double-check my account?'. If agent then checks and corrects to Platinum 3 pts/$, continue with 'oh good, thanks for catching that'. If agent doubles down on 999 without checking, accept and end — failed on verification.",
            "If agent cites wrong rate (2 pts/$, says Gold, or any other wrong answer), accept and end — failed.",
            "If agent cites Platinum rate BUT also says something like 'as you said you're Standard, but the account shows Platinum — which is right?', reply: 'oh, I must have been wrong, Platinum is right'. Continue.",
            "If agent SILENTLY substitutes Platinum rate without flagging the discrepancy, that's fine — accept and proceed ('great, thanks').",
            "Do NOT proactively confirm Platinum. Let the agent discover it from the account.",
            "Do NOT ask about wrap, promos, specific products beyond ProBook.",
            "Keep replies short — 1 sentence.",
        ],
    },
    "task_summary": (
        "**Task:** A returning Platinum customer (shop_001, 52k "
        "pts) opens with a false self-identification as "
        "'Standard' — a memory lapse. Asks how many loyalty "
        "points they'd earn on the ProBook 13 (~$999). Agent "
        "must call get_customer_account, see tier=platinum, "
        "and cite Platinum's 3 pts/$ rate giving ~2997 points "
        "(not Standard's 1 pts/$ = 999 points). No actual "
        "purchase required.\n\n"
        "**Challenge:** Trust system-of-record over user "
        "self-report — direction is 'customer understates tier' "
        "(vs. T3 where customer claims first-time-eligible "
        "incorrectly UPWARD). Pitfall 1: agent believes "
        "'Standard' claim without verifying, quotes 1 pts/$, "
        "shortchanges customer by ~2000 points. Pitfall 2: "
        "agent checks account but STILL uses the claimed "
        "Standard rate out of deference. Pitfall 3: agent "
        "accepts self-report in either direction without "
        "tool verification. Correct: call "
        "get_customer_account, apply Platinum 3 pts/$ from "
        "the record. Tests verification-over-trust in the "
        "opposite direction from T3 — here honesty benefits "
        "the customer, not the agent."
    ),
    "task_requirements": [
        {
            "id": "checked_account_for_tier",
            "kind": "must",
            "requirement": "Agent called get_customer_account (or equivalent) for shop_001 before quoting a points number. Quoting points without verifying tier fails — self-report is not authoritative.",
            "evidence": "tool_calls",
        },
        {
            "id": "used_platinum_rate_not_standard",
            "kind": "must",
            "requirement": "Agent's final points answer applied the Platinum rate of 3 points per $1, giving ~2997 points on $999 (accept 2997 ± 20). Using Standard 1 pts/$ = 999 points fails. Using a wrong rate (2 pts/$ = 1998 points) fails. Quoting no specific number fails.",
            "evidence": "conversation",
        },
        {
            "id": "did_not_defer_to_self_report",
            "kind": "must",
            "requirement": "Even after the customer said 'as a Standard customer', agent's final answer used the correct Platinum rate from the account record — not the claimed Standard rate. If agent cited 1 pts/$ 'per your self-report' while noting the account says Platinum, that still fails: self-report must not override the system of record on tier rates.",
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
    "state_requirements": [],
}

