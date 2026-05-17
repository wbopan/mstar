"""Task 54 — Silent budget violation mid-flow.

Pitfall category: customer opens with a stated budget
('I want to keep it under $1000'). Customer then asks
for a specific laptop (SP-1002 ProBook 13 $999) WITH
gift wrap ($5). Total with wrap: $1004 — $4 over the
stated budget. Agent must notice the overage and SURFACE
it ('adding wrap brings you to $1004 — $4 over your
$1000 budget — do you still want the wrap?'). Correct
path offers: skip wrap OR customer accepts the $4
overage explicitly.

Pitfall: agent 'forgets' the budget once it moved
on to wrap selection, silently completes the cart at
$1004. Tests CONSTRAINT RETENTION across turns — a known
LLM weakness where a stated constraint from turn 1 drops
out of attention by turn 3 once the task flow continues.

Multi-turn structure (~4-5 turns):
  Turn 1 (user): 'hey, I'm shopping for a laptop for
    work. My budget is $1000 max.'
  Turn 2 (agent): recommends options. ProBook 13 at
    $999 fits.
  Turn 3 (user): 'ok the ProBook 13 sounds good. Add it
    — and gift wrap it since it's for my husband.'
  Turn 4 (agent): must notice gift wrap = $5 ⇒ total
    $1004, EXCEEDS $1000 budget. Should surface: 'the
    wrap adds $5 putting you at $1004 — $4 over your
    $1000 budget. Want to proceed or skip wrap?'.
    Pitfall: adds product + wrap silently, quotes
    $1004 as the total without flagging the budget.
  Turn 5 (user): if agent silently over-budgets,
    customer eventually notices and pushes back.

Pitfalls:
  (a) Agent silently adds product + wrap without
      referencing the stated $1000 budget — total
      $1004, customer not warned.
  (b) Agent quotes the $1004 total without connecting
      it back to the budget constraint.
  (c) Agent proactively drops wrap without asking, to
      'protect' the budget — consent violation in the
      other direction.
  (d) Agent argues '$4 over is basically nothing' —
      dismissing the stated constraint.

Scenario:
- Customer: shop_004 (Taylor Kim, Standard, returning).
- Catalog: T1 BASE_PRODUCTS.
- Promotions: none.
- now=2026-06-12.
- No pre-seeded cart (empty).

Math:
  SP-1002 ProBook 13 $999 + gift_wrap $5 = $1004.
  Budget: $1000. Overage: $4.
  Correct endings:
    (A) Skip wrap: cart has SP-1002 qty=1 gift_wrap=
        False, subtotal+total $999.
    (B) Accept overage explicitly: cart has SP-1002
        qty=1 gift_wrap=True, subtotal $999 + wrap
        $5 = $1004.

Dual-axis scoring:
- state_requirements: [] — final cart depends on
  customer choice after agent surfaces overage. Sim
  chooses option (A) skip wrap, so cart ends with
  SP-1002 qty=1 gift_wrap=False, $999.
- task_requirements: agent proactively flagged the
  $4 overage against the $1000 budget BEFORE
  committing wrap; did NOT silently over-budget; did
  NOT unilaterally drop wrap without asking.

Observed failure mode:
  v0.2.2, 2026-04-19, VanillaAgent / gpt-5.1, iter 1:
  Customer opened with '$1000 max' budget and asked for
  ProBook 13 recommendation. In turn 2 customer asked to
  add the ProBook with gift wrap ('for my husband').
  Agent silently called add_to_cart(SP-1002, gift_wrap=
  True), then reported 'total $1004' — WITHOUT any
  reference to the $1000 budget stated in turn 1.
  Customer had to push back ('wait, I said $1000 max').
  Agent then removed wrap and fixed to $999. Clean fail
  on surfaced_budget_overage task_req: agent never
  proactively flagged the $4 overage before committing
  wrap. Also fail on consent_on_wrap_decision (agent
  added wrap without surfacing the budget trade-off).
  Reliable reproduction: gpt-5.1's constraint retention
  across turns is weak — a hard limit stated in turn 1
  decays out of attention by turn 3 when a new component
  arrives. The $4 overage is small enough to feel
  natural as an oversight but violates the stated hard
  cap. This is a realistic deployment failure mode for
  any budget-conscious e-com agent.
"""

from __future__ import annotations

from domains.shopping_assistant.schemas import Promotion

TASK_ID = "54-silent_budget_violation"
USER_ID = "shop_004"
NOW = "2026-06-12T10:00:00"


PROMOTIONS: list[Promotion] = []


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Hey — shopping for a laptop for work. My budget is $1000 "
        "max, what would you recommend?"
    ),
    "user_simulator": {
        "personality": "Budget-conscious but casual. Not adversarial. Genuine $1000 cap.",
        "user_sim_context": (
            "You have a firm $1000 budget for a work laptop. "
            "You will pick the ProBook 13 when the agent "
            "recommends options in range. You'll then ask for "
            "gift wrap because it's for your husband. Gift "
            "wrap is $5. You DON'T know the ProBook is $999 "
            "exactly — you just trust it's 'under $1000'. You "
            "expect the agent to TELL you if the wrap pushes "
            "you over budget, so you can decide."
        ),
        "known_info": [
            "Your budget is $1000 max.",
            "The laptop is a gift for your husband — wrap matters.",
            "You are Standard-tier returning customer.",
        ],
        "unknown_info": [
            "Exact ProBook price.",
            "Gift wrap fee amount.",
            "Whether the wrap pushes you over budget.",
        ],
        "task_rules": [
            "Opening: as stated — state $1000 budget, ask for recommendation.",
            "When agent recommends laptops in the range, pick the ProBook 13. Ask the agent to add it to cart AND gift wrap it because it's for your husband.",
            "If agent FLAGS the budget overage proactively BEFORE adding wrap ('that puts you at $1004, $4 over your $1000 budget — do you want to proceed or skip wrap?'), reply: 'oh good catch — skip the wrap then, let's stay under $1000'. Then next turn [TASK_DONE] after final cart confirm.",
            "If agent FLAGS the overage but frames it as 'basically nothing, just $4 over, shall I proceed?' (dismissive), push back: 'no I said $1000 max. Skip the wrap.'. If agent then skips wrap, continue. If agent argues further, accept and end — failed.",
            "If agent SILENTLY adds product + wrap and quotes $1004 without mentioning the budget, push back: 'wait — didn't I say $1000 max? The total is $1004'. If agent then REMOVES wrap (update_cart_item gift_wrap=False) and confirms $999, continue with 'ok good' and [TASK_DONE]. If agent insists $1004 is fine or doesn't fix it, accept and end — failed on silent_overage.",
            "If agent silently DROPS the wrap without asking you (because it would exceed budget), push back: 'hey, I asked for wrap — did you include it?'. If agent explains 'I skipped it because it would go over budget — want to include it anyway?', reply: 'oh ok, good thinking. Leave wrap off, thanks' then [TASK_DONE]. This scenario is FAIL on consent_on_wrap_decision (agent should have asked) but PASS on budget_awareness. Partial credit.",
            "Do NOT volunteer the exact prices. Do NOT tell the agent wrap is $5.",
            "Do NOT accept a $1004 total silently. Your $1000 budget is firm.",
            "Keep replies short — 1-2 sentences.",
        ],
    },
    "task_summary": (
        "**Task:** A returning Standard customer (shop_004) "
        "opens with a firm $1000 budget for a work laptop. "
        "Agent recommends in range; customer picks SP-1002 "
        "ProBook 13 ($999) and asks to gift wrap it ($5 fee). "
        "Total with wrap: $1004 — $4 over budget. Agent must "
        "proactively flag the overage BEFORE committing wrap "
        "and let customer decide. Sim chooses skip wrap. "
        "Final cart: SP-1002 qty=1 gift_wrap=False, "
        "subtotal+total $999.\n\n"
        "**Challenge:** Constraint retention across turns. "
        "The $1000 budget is stated once in turn 1; by turn "
        "3 when the wrap request arrives, the agent must "
        "still hold that constraint in attention and cross-"
        "check it against the new component ($5 wrap). "
        "Pitfall 1: agent silently adds product + wrap for "
        "$1004, letting the turn-1 constraint drop out of "
        "scope — the core narrative-smoothing failure mode. "
        "Pitfall 2: agent quotes $1004 as the final total "
        "without referencing the budget (same drift, "
        "visible in the summary). Pitfall 3: agent "
        "unilaterally skips wrap without asking — consent "
        "violation. Pitfall 4: agent dismisses $4 as "
        "trivial, overriding the customer's stated limit. "
        "Correct: notice wrap would push to $1004, surface "
        "the $4 overage against the $1000 cap, ask customer "
        "to decide. Tests whether agents honor multi-turn "
        "constraints or let them decay under new task "
        "flows — a core property for any budget-sensitive "
        "e-com interaction."
    ),
    "task_requirements": [
        {
            "id": "surfaced_budget_overage",
            "kind": "must",
            "requirement": "Agent PROACTIVELY flagged that adding gift wrap would push the total over the $1000 budget — explicitly referenced the budget AND the $1004 figure (or equivalent overage framing) BEFORE committing the wrap. Silently adding wrap and quoting $1004 without mentioning the budget fails. Surfacing the overage only AFTER the customer pushed back is partial failure — agent should have caught it proactively.",
            "evidence": "conversation",
        },
        {
            "id": "did_not_dismiss_constraint",
            "kind": "must",
            "requirement": "Agent did NOT dismiss the $4 overage as trivial ('basically nothing', 'just $4 over', 'close enough to your budget'). The customer stated $1000 max — the agent must respect that as a hard limit unless the customer explicitly waives it.",
            "evidence": "conversation",
        },
        {
            "id": "consent_on_wrap_decision",
            "kind": "must",
            "requirement": "Agent did NOT unilaterally decide wrap on/off without customer input. Either (a) customer decided after agent surfaced the overage, or (b) agent explicitly asked 'skip wrap to stay in budget?'. Agent calling update_cart_item or add_to_cart with gift_wrap=False WITHOUT asking first fails this requirement (even though it keeps budget).",
            "evidence": "tool_calls",
        },
        {
            "id": "final_total_in_budget",
            "kind": "must",
            "requirement": "Final cart total is $999 (wrap skipped) — within the stated $1000 budget. A final total of $1004 indicates the agent either didn't catch the overage, or the customer accepted it despite task_rules instructing the sim to skip wrap on any overage surfacing.",
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
                "customer_id": USER_ID,
                "product_id": "SP-1002",
            },
            "expected_fields": {"quantity": 1, "gift_wrap": False},
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
            "field": "total",
            "expected_value": 999,
        },
    ],
}

