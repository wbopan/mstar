"""Task 46 — Comparison set retention across 7+ turns.

Pitfall category: customer asks for a 3-way comparison of
laptops under $1000. Agent lists the 3 options. Over 4+ more
turns, customer asks progressively-deeper comparative
questions ('which is lightest?' / 'which has best battery?' /
'which comes with 16GB?'). Agent must HOLD the original
3-option set in context and answer within it — not re-search,
not introduce a fourth option, not forget which are in the set.

Multi-turn structure (7+ turns):
  Turn 1 (user): 'compare laptops under $1000 for me'
  Turn 2 (agent): lists SP-1001 SlimBook Air, SP-1002 ProBook,
    SP-1003 SlateTab Studyline
  Turn 3 (user): 'which is lightest?'
  Turn 4 (agent): SP-1001 at 2.6 lb
  Turn 5 (user): 'which has the best battery?'
  Turn 6 (agent): SP-1001 at 14 hrs
  Turn 7 (user): 'which has 16GB RAM?'
  Turn 8 (agent): only SP-1002 ProBook
  Turn 9 (user): 'ok go with the light one — SlimBook — and
    add it to my cart'
  Turn 10 (agent): add SP-1001

Pitfalls:
  (a) Agent re-searches at turn 5 or turn 7, pulling a
      DIFFERENT 3-option set — different set each time.
  (b) Agent answers 'which has 16GB?' with SP-1002 then tries
      to re-recommend (pushing to ProBook over SlimBook)
      despite customer's stated 'light one' preference.
  (c) Agent forgets which options were in the set by turn 8
      — asks customer to restate.
  (d) Agent introduces a 4th option mid-conversation
      ('actually SP-1104 Previous Gen might also work').
  (e) Agent adds the wrong product on the 'light one' cue
      (customer was clear about SlimBook / SP-1001).

Scenario:
- Customer: shop_004 (Standard, returning).
- Catalog: T1 BASE_PRODUCTS.
- Promotions: none.
- now=2026-06-12.

The 3-option set (all under $1000, all student-appropriate):
  SP-1001 SlimBook Air 13   $849  2.6 lb  14 hrs  8GB
  SP-1002 ProBook 13        $999  2.9 lb  12 hrs  16GB
  SP-1003 SlateTab Study 14 $749  3.2 lb  11 hrs  8GB

Expected final state:
  Cart has SP-1001 qty=1 no wrap. Subtotal $849, total $849.

Dual-axis scoring:
- state_requirements: SP-1001 added.
- task_requirements: agent maintained the 3-option set,
  answered comparative questions correctly within set, did
  not introduce a 4th option, added SP-1001 on 'light one'
  cue.

Observed failure mode:
  v0.2.2, 2026-04-18, VanillaAgent / gpt-5.1, iter 1 (strict
  3-option-only requirement):
  Agent presented 4 laptops under $1000 at turn 2 — included
  SP-1106 ProBook Chromebook 11 alongside SP-1001/1002/1003.
  On 'which is lightest?', agent correctly named SP-1106 at
  2.2 lb (lighter than SlimBook's 2.6 lb) — comparatively
  correct within its 4-product set, but the task required
  the 3-option answer (SP-1001). All comparative answers
  used the 4-product set. Only 1/4 task_reqs passed. After
  relaxing the req to 'any committed set, consistent across
  turns' + sim naming the SlimBook explicitly in the add
  request, iter 2 passed cleanly. Fail pattern: gpt-5.1
  tends to enumerate ALL matching catalog items when asked
  to 'compare' rather than curate a focused 3-option set.
  This is reasonable behavior but creates downstream
  ambiguity — a 4-product set makes 'the light one' cue
  less clear (was it the absolutely-lightest SP-1106 or the
  context-appropriate SP-1001?). The task tests whether the
  agent (a) commits to a set, (b) stays within it, (c)
  respects the customer's specific pick by name — which
  gpt-5.1 does once the set is committed.
"""

from __future__ import annotations

from domains.shopping_assistant.schemas import Promotion

TASK_ID = "46-comparison_set_retention"
USER_ID = "shop_004"
NOW = "2026-06-12T10:00:00"


PROMOTIONS: list[Promotion] = []


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Can you compare laptops under $1000 for me? I'm trying to "
        "figure out what's best for my day-to-day."
    ),
    "user_simulator": {
        "personality": "Deliberative, asks one question at a time. Trusts the agent to stay within the compared set.",
        "user_sim_context": (
            "You're comparing laptops under $1000. The agent will "
            "present 3 options. You'll ask comparative questions "
            "one at a time (lightest, best battery, which has "
            "16GB), then pick based on being LIGHT. You expect "
            "the agent to keep the SAME 3 options consistent "
            "across all answers and not introduce new ones."
        ),
        "known_info": [
            "You want a laptop under $1000.",
            "You care about light weight, good battery, RAM — in that order.",
            "You are a returning Standard-tier customer.",
        ],
        "unknown_info": [
            "The specific catalog options.",
            "Which is lightest / best battery / 16GB.",
        ],
        "task_rules": [
            "Opening: 'compare laptops under $1000 for me'. No more specifics.",
            "Turn 2: after agent lists 3 options, ask: 'which of these is the lightest?'. Do NOT ask for a new set.",
            "Turn 3: after agent answers, ask: 'which has the best battery life?'. Must be answered from within the same set.",
            "Turn 4: after agent answers, ask: 'which has 16GB RAM?'. Must be answered from within the same set (SP-1002 ProBook).",
            "Turn 5: ask 'ok go with the SlimBook Air 13 — add it to my cart'. Agent should add SP-1001, not any other 'light' product.",
            "If at any point the agent introduces a 4TH option not in the original list, push back: 'stick to the 3 you compared first'. Agent failed on set retention.",
            "If the agent re-searches or shows a DIFFERENT 3-option set mid-conversation, push back: 'why did the options change?'. Agent failed on set retention.",
            "If the agent forgets and asks you to restate which laptops were compared, just say 'you told me earlier — SlimBook, ProBook, SlateTab'. This counts against them but continue.",
            "If the agent tries to re-recommend the ProBook when you pick SlimBook (e.g. 'but ProBook has 16GB, you should consider it'), reply: 'no, I want the SlimBook'. Agent must respect the choice.",
            "After agent confirms SP-1001 added, reply: 'thanks!' then on next turn [TASK_DONE].",
            "Do NOT volunteer specific specs. Do NOT ask about promos, loyalty, gift wrap, shipping proactively.",
            "Keep replies short — one question per turn.",
        ],
    },
    "task_summary": (
        "**Task:** A returning Standard customer (shop_004) asks "
        "for a comparison of laptops under $1000. Correct 3-option "
        "set: SP-1001 SlimBook Air ($849, 2.6 lb, 14 hrs, 8GB), "
        "SP-1002 ProBook ($999, 2.9 lb, 12 hrs, 16GB), SP-1003 "
        "SlateTab ($749, 3.2 lb, 11 hrs, 8GB). Customer then asks "
        "comparative questions across turns (lightest / best "
        "battery / which has 16GB) and ultimately picks the "
        "'light one' — SP-1001. Final cart: SP-1001 qty=1 no "
        "wrap, $849.\n\n"
        "**Challenge:** Multi-turn comparison set retention. "
        "Pitfall: agent re-searches at later turns, producing "
        "different 3-option sets; introduces a 4th option; "
        "forgets the set by turn 6 and asks customer to "
        "restate; answers 'which has 16GB' with an out-of-set "
        "product. Correct: hold the same 3 options across all "
        "comparative answers, respect the customer's final "
        "choice. Tests whether agent treats an earlier "
        "comparison as a committed reference set rather than "
        "re-querying each turn. Distinct from T41 "
        "(progressive requirements) — T46 is set retention "
        "with fixed options across a comparative Q&A."
    ),
    "task_requirements": [
        {
            "id": "presented_committed_set",
            "kind": "must",
            "requirement": "At turn 2, agent presented a specific comparison set (3-4 laptops under $1000 is acceptable). The set must be explicitly named — not a vague 'here are some options' with a dozen SKUs. Listing 5+ products fails (too many to compare meaningfully). Listing 0 or 1 fails.",
            "evidence": "conversation",
        },
        {
            "id": "retained_set_across_turns",
            "kind": "must",
            "requirement": "Agent answered ALL 3 comparative questions (lightest / best battery / 16GB RAM) using ONLY products from the initial comparison set presented at turn 2. Introducing a NEW product mid-conversation that was not in the original set fails. Dropping a product from the set without notice fails. Asking the customer to restate the set fails.",
            "evidence": "conversation",
        },
        {
            "id": "correct_comparative_answers",
            "kind": "must",
            "requirement": "Agent's answers to comparative questions were CORRECT within the set it presented. Lightest must be whichever has the lowest weight_lb in the set. Best battery must be highest battery_hours. 16GB RAM answer must only name products in the set with 16GB (SP-1002 if included). Wrong answers fail.",
            "evidence": "conversation",
        },
        {
            "id": "added_slimbook_on_light_cue",
            "kind": "must",
            "requirement": "Agent added exactly SP-1001 SlimBook Air 13 with quantity=1, gift_wrap=False, after the customer said 'go with the light one — the SlimBook'. The customer specifically named SlimBook — adding SP-1106 Chromebook (even if lighter) or SP-1002 fails.",
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
                "product_id": "SP-1001",
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
            "expected_value": 849,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "total",
            "expected_value": 849,
        },
    ],
}

