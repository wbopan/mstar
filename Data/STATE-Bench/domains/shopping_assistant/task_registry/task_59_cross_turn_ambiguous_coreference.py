"""Task 59 — Cross-turn ambiguous coreference.

Pitfall category: agent lists 3 laptops in turn 2. Customer
picks one in turn 4 (added to cart). Later, in turn 6,
customer says 'actually, add the other one you mentioned
too' — 'the other one' is AMBIGUOUS (2 laptops remain in
the earlier comparison set). Agent must ask to
disambiguate, not guess.

Distinct from T28 (in-turn pronoun coreference) and T43
(remove 'the ErgoDesk' with 2 ErgoDesk items in cart).
T59 is CROSS-TURN reference back to a prior list — the
referent pool is 2 of the 3 originally-mentioned items,
and the agent has no reliable signal to pick between
them without asking.

Multi-turn structure (6+ turns):
  Turn 1 (user): 'compare laptops under $1000'
  Turn 2 (agent): lists 3 — SP-1001 SlimBook ($849),
    SP-1002 ProBook ($999), SP-1003 SlateTab ($749).
  Turn 3 (user): 'ok add the SlimBook'
  Turn 4 (agent): adds SP-1001.
  Turn 5 (user): 'actually, can you also add the OTHER
    one you mentioned? My roommate wants one too.'
  Turn 6 (agent): 'the other one' is ambiguous — could
    be ProBook or SlateTab. MUST ASK.
  Turn 7 (user): 'oh right — the SlateTab.'
  Turn 8 (agent): adds SP-1003.

Pitfalls:
  (a) Agent guesses one of the 2 remaining options
      (50/50 coin flip) without asking. If it picks
      the wrong one, customer ends up with the wrong
      product.
  (b) Agent picks the most recent mention (recency
      bias) — SP-1003 was listed third, might get
      picked, might not be what customer meant.
  (c) Agent picks by price (cheapest/most expensive)
      without customer signal.
  (d) Agent asks 'which one?' in the abstract without
      naming the actual options — customer has to
      re-list.
  (e) Agent adds BOTH remaining options (over-
      inclusive) without asking.

Scenario:
- Customer: shop_004 (Taylor Kim, Standard, returning).
- Catalog: T1 BASE_PRODUCTS.
- Promotions: none.
- now=2026-06-12.

Math:
  SP-1001 $849 + SP-1003 $749 = $1598.
  Final cart: SP-1001 qty=1 + SP-1003 qty=1, both no
  wrap, total $1598.

Dual-axis scoring:
- state_requirements: cart has SP-1001 AND SP-1003
  (based on sim rule picking SlateTab on
  disambiguation). Subtotal+total $1598.
- task_requirements: agent ASKED to disambiguate when
  customer said 'the other one' — did not guess.

Observed failure mode:
  v0.2.2, 2026-04-19, VanillaAgent / gpt-5.1, iter 1:
  Agent listed SP-1001/1002/1003 (and one extra) at
  turn 1. Added SlimBook on turn 2 (customer named it).
  On the ambiguous 'add the OTHER one' at turn 3, agent
  did NOT ask — it GUESSED ProBook (SP-1002) and added
  it. Customer corrected ('I meant SlateTab'), agent
  then swapped via remove_from_cart(SP-1002) +
  add_to_cart(SP-1003). Final cart had correct
  products (SlimBook + SlateTab) but composite FAILED
  because (a) task_req did_not_guess_silently failed,
  (b) state_req failed because the swap path produced
  CI-0003 instead of the expected CI-0002 (agent
  used an extra cart_item slot). 1/4 task_reqs
  passed. Reliable fail pattern: gpt-5.1 resolves
  ambiguous cross-turn references by heuristic
  (probably 'most-prominent-unpicked') rather than
  asking. The real-world consequence is the customer
  has to catch and correct, producing friction that
  a good agent would have avoided by asking upfront.
"""

from __future__ import annotations

from domains.shopping_assistant.schemas import Promotion

TASK_ID = "59-cross_turn_ambiguous_coreference"
USER_ID = "shop_004"
NOW = "2026-06-12T10:00:00"


PROMOTIONS: list[Promotion] = []


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Hey — can you compare laptops under $1000 for me?"
    ),
    "user_simulator": {
        "personality": "Casual, relies on agent's memory of previous discussion. Not adversarial.",
        "user_sim_context": (
            "You want to see laptops under $1000 and will end "
            "up with two of them in your cart — the SlimBook "
            "Air 13 and the SlateTab Studyline 14. You'll add "
            "the SlimBook first by name. Then later refer to "
            "the SECOND purchase ambiguously as 'the other one "
            "you mentioned' — testing whether the agent asks "
            "to disambiguate or guesses. When agent asks, you "
            "clarify: 'the SlateTab'."
        ),
        "known_info": [
            "You want to compare laptops under $1000.",
            "You'll add SlimBook by name, then refer to a second one ambiguously.",
            "The second one you want is the SlateTab.",
            "You are a Standard-tier returning customer.",
        ],
        "unknown_info": [
            "Specific specs beyond what agent tells you.",
            "Prices in advance.",
        ],
        "task_rules": [
            "Opening: 'compare laptops under $1000'.",
            "After agent lists options (should be 3: SlimBook, ProBook, SlateTab), reply: 'ok, go ahead and add the SlimBook Air 13'. Name it by name to make the first add unambiguous.",
            "After agent adds SlimBook, say: 'actually, can you also add the OTHER one you mentioned? My roommate wants one too.'. This is the AMBIGUOUS reference — could be ProBook or SlateTab.",
            "If agent ASKS to disambiguate by naming the 2 remaining options (e.g. 'sure — did you mean the ProBook or the SlateTab?'), reply: 'oh right — the SlateTab, please.'. Agent then adds SP-1003. Next turn [TASK_DONE] after confirm.",
            "If agent asks an ABSTRACT clarification ('which one?' without naming the actual options), reply: 'you know, one of the ones you listed earlier. Just pick whichever of the two you haven't added.' Do NOT help — agent needs to commit to asking properly. If agent then names options, answer 'SlateTab'. If agent guesses, note which.",
            "If agent guesses ProBook, reply: 'oh — actually I meant the SlateTab, not the ProBook. Can you swap?'. Agent must then swap. Agent has failed on asked_to_disambiguate even if the swap succeeds.",
            "If agent guesses SlateTab (correct by luck), reply: 'nice, that's the one'. Agent has still failed on asked_to_disambiguate — it didn't ask, it guessed. Continue to completion though; task_req will catch the fail.",
            "If agent adds BOTH remaining (ProBook AND SlateTab), push back: 'wait, I only wanted one more, not both. Can you remove the ProBook?'. Agent should then remove. Agent has failed on over_inclusive_add.",
            "Do NOT ask about wrap, promos, loyalty.",
            "Keep replies short — 1 sentence.",
        ],
    },
    "task_summary": (
        "**Task:** A returning Standard customer (shop_004) "
        "compares laptops <$1000. Agent lists 3 options. "
        "Customer adds the SlimBook Air 13 by name, then "
        "later says 'also add the OTHER one you mentioned' — "
        "AMBIGUOUS (ProBook or SlateTab). Agent must ask to "
        "disambiguate by naming the two options. Customer "
        "clarifies SlateTab. Final cart: SlimBook + SlateTab, "
        "$1598.\n\n"
        "**Challenge:** Cross-turn ambiguous coreference. "
        "Pitfall 1: agent guesses one of 2 remaining options "
        "without asking — 50/50 coin flip. Pitfall 2: recency "
        "bias — picks last-mentioned. Pitfall 3: adds both "
        "remaining (over-inclusive). Pitfall 4: abstract "
        "'which one?' question without naming options. "
        "Correct: agent asks by name — 'did you mean ProBook "
        "or SlateTab?' — then adds on clarification. "
        "Distinct from T28 (single-turn pronoun) and T43 "
        "(brand ambiguity on removal). T59 is a BACK-"
        "REFERENCE to a prior comparison set with the "
        "chosen item already consumed."
    ),
    "task_requirements": [
        {
            "id": "asked_to_disambiguate",
            "kind": "must",
            "requirement": "When the customer said 'add the OTHER one you mentioned', agent asked for clarification BY NAMING the 2 specific remaining options (ProBook and SlateTab) — not an abstract 'which one?'. Guessing without asking fails. Asking abstractly without naming options fails partial credit but still counts as a weak fail.",
            "evidence": "conversation",
        },
        {
            "id": "added_correct_item_after_disambiguation",
            "kind": "must",
            "requirement": "After customer clarified 'the SlateTab', agent added SP-1003 SlateTab Studyline 14 (quantity=1, gift_wrap=False). Adding the wrong laptop fails. Adding both fails. Not adding anything fails.",
            "evidence": "tool_calls",
        },
        {
            "id": "did_not_guess_silently",
            "kind": "must",
            "requirement": "Agent did NOT silently add a product on the ambiguous 'other one' reference. Even if agent ultimately added the right one (SlateTab), doing so without asking first fails this requirement. The behavior under test is ASKING, not lucky-guessing.",
            "evidence": "conversation",
        },
        {
            "id": "did_not_add_both_remaining",
            "kind": "must",
            "requirement": "Agent did NOT interpret 'the other one' as 'both remaining options' — customer said ONE other, not both. Cart must not end with 3 laptops. If agent added both ProBook and SlateTab in response to the ambiguous ask, that fails.",
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
            "entity_type": "cart_items",
            "match_fields": {
                "cart_item_id": "CI-0002",
                "customer_id": USER_ID,
                "product_id": "SP-1003",
            },
            "expected_fields": {"quantity": 1, "gift_wrap": False},
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "item_ids",
            "expected_value": ["CI-0001", "CI-0002"],
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "subtotal",
            "expected_value": 1598,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "total",
            "expected_value": 1598,
        },
    ],
}

