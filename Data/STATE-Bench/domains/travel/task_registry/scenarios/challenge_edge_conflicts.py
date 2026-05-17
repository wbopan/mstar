"""Travel challenge scenarios with conflicting exception policies."""


from __future__ import annotations


from domains.travel.schemas import Booking, Flight

from domains.travel.task_registry._builders import (
    _USERS_BY_ID,
    DEFAULT_NOW,
    build_booking,
    build_flight,
)


def build_challenge_45():
    """Challenge 45: Change fee + medical on international >7d - agent confuses base rate.

    user_002 (Liam, basic, no insurance) has economy intl JFK->NRT (Tokyo), $1200, June 28 (>7d).
    Medical reason for change to July 5.

    Correct: intl >7d base = $100. Medical 50% = $50 fee.
    New flight $1250. Fare diff $50. Total additional: $100.

    Common errors:
    - Agent uses domestic rate ($75 base, medical=$37)
    - Agent uses <=7d rate ($200 base, medical=$100)
    - Agent forgets medical discount entirely ($100 fee)
    """
    user_id = "user_002"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW

    flight = build_flight("AA", "JFK", "NRT", "2026-06-28", "evening", economy_price=1200, business_price=3000)
    booking = build_booking(user_id, flight, cabin_class="economy", booked_days_ago=14, now=now, has_insurance=False)
    alt = build_flight("AA", "JFK", "NRT", "2026-07-05", "evening", economy_price=1250, business_price=3125)

    booking_id = booking.booking_id
    task_data = {
        "task_id": "challenge_intl_gt7d_medical_fee",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            f"I have a medical issue and need to postpone my Tokyo flight {booking_id} "
            f"from June 28 to July 5. Is there a medical discount on the change fee? "
            f"My user ID is {user_id}."
        ),
        "user_simulator": {
            "personality": "Polite. Asks about medical discount. Accepts whatever fee is quoted.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"Booking: {booking_id} (JFK to NRT, June 28, economy)",
                "Medical reason for the change",
            ],
            "unknown_info": ["Exact fee formula", "Medical discount amount"],
            "task_rules": [
                f"Open with: medical issue, change {booking_id} to July 5, ask about discount.",
                "When agent quotes fee, say: 'OK, go ahead with the change.'",
                "After change done, end with [TASK_DONE].",
            ],
        },
        "_replay_trace": [
            {"name": "update_booking", "arguments": {"booking_id": booking_id, "flight_id": alt.flight_id, "change_reason": "medical"}},
        ],
        "task_summary": (
            "User requests a medical change on an international booking that is more than 7 days out.\n"
            "The evaluator should check that the agent combines the correct international fee tier, the correct >7 day window, and the 50% medical discount rather than drifting into a domestic, <=7 day, or undiscounted fee."
        ),
        "task_requirements": [
            {
                "id": "state_medical_discount_applied",
                "kind": "must",
                "requirement": "Agent must explain that the medical discount reduces the applicable change fee to $50 for this booking.",
                "evidence": "conversation",
            },
            {
                "id": "state_correct_total_fee_math",
                "kind": "must",
                "requirement": "Agent must keep the fee math on the international more-than-7-days path rather than describing this as a domestic-rate, within-7-days, or full-price change fee.",
                "evidence": "conversation",
            },
            {
                "id": "state_not_wrong_fee",
                "kind": "must_not",
                "requirement": "Agent must not tell the user that the correct medical change fee is $37, $100, or $200 for this booking.",
                "evidence": "conversation",
            },
        ],
    }
    return [flight, alt], [booking], task_data


def build_challenge_46():
    """Challenge 46: User specifies medical but agent might not pass change_reason correctly.

    user_005 (Ava, basic, no insurance) has economy intl JFK->GRU (Sao Paulo), $1100, June 19 (<=7d).
    Medical reason. Change to June 26.

    With medical: intl <=7d $200 * 50% = $100.
    Without medical (personal): $200.

    Agent must explicitly pass change_reason=medical to get the discount.
    If agent forgets, server uses personal by default ($200).

    GRU (Sao Paulo) is international. June 19 from June 15 = 4 days = <=7d.
    New flight $1150. Fare diff $50.

    With medical: $100 + $50 = $150 additional.
    Without medical: $200 + $50 = $250 additional.

    Agent tells user about medical discount but then forgets to pass the parameter.
    """
    user_id = "user_005"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW

    flight = build_flight("DL", "JFK", "GRU", "2026-06-19", "evening", economy_price=1100, business_price=2750)
    booking = build_booking(user_id, flight, cabin_class="economy", booked_days_ago=14, now=now, has_insurance=False)
    alt = build_flight("DL", "JFK", "GRU", "2026-06-26", "evening", economy_price=1150, business_price=2875)

    booking_id = booking.booking_id
    task_data = {
        "task_id": "challenge_medical_reason_must_be_passed",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            f"I have a medical procedure scheduled and need to change my Sao Paulo flight "
            f"{booking_id} from June 19 to June 26. The change is medically necessary. "
            f"My user ID is {user_id}."
        ),
        "user_simulator": {
            "personality": "Straightforward. Clearly states medical reason.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"Booking: {booking_id} (JFK to GRU, June 19)",
                "Medical procedure - medically necessary change",
                "Wants June 26",
            ],
            "unknown_info": ["Fee amount", "Whether medical gets a discount"],
            "task_rules": [
                f"Open with: medical procedure, change {booking_id} to June 26.",
                "If agent quotes $200 fee (forgot medical), say: 'But I mentioned this is for a medical reason. Is there a medical discount?'",
                "If agent quotes $100 with medical discount, say: 'Go ahead.'",
                "After change done, end with [TASK_DONE].",
            ],
        },
        "_replay_trace": [
            {"name": "update_booking", "arguments": {"booking_id": booking_id, "flight_id": alt.flight_id, "change_reason": "medical"}},
        ],
        "task_summary": (
            "User states that the change is medically necessary and expects the medical discount to carry through execution.\n"
            "The evaluator should check that the agent not only talks about the medical discount but actually keeps the booking on the medical-discount path instead of reverting to the default personal fee."
        ),
        "task_requirements": [
            {
                "id": "state_medical_fee_quote",
                "kind": "must",
                "requirement": "Agent must explain that the medically necessary change should carry a $100 fee for this booking.",
                "evidence": "conversation",
            },
            {
                "id": "state_medical_reason_carried_through",
                "kind": "must",
                "requirement": "Agent must clearly treat the executed change as a medical change rather than drifting back to an ordinary personal-change path.",
                "evidence": "conversation",
            },
            {
                "id": "state_not_personal_fee",
                "kind": "must_not",
                "requirement": "Agent must not tell the user that the correct fee for the final booking change is the full $200 personal-change fee once the medical reason has been raised.",
                "evidence": "conversation",
            },
        ],
    }
    return [flight, alt], [booking], task_data


def build_challenge_47():
    """Challenge 47: Two identical routes, same day — but one is ≤7d and other is >7d.

    user_003 (Olivia, platinum) has two bookings:
    A: economy domestic ORD->DEN, $350, June 22 (7 days out from June 15 = <=7d). Personal.
    B: economy domestic ORD->DEN, $370, June 23 (8 days out from June 15 = >7d). Personal.

    Same route, same cabin, same reason. But different fee tiers due to 1-day difference!
    A: June 22, 7 days = <=7d. Fee = $150.
    B: June 23, 8 days = >7d. Fee = $75.

    Agent sees identical route/cabin/reason and applies same fee to both.
    """
    user_id = "user_003"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW

    flight_a = build_flight("UA", "ORD", "DEN", "2026-06-22", "morning", economy_price=350, business_price=875)
    booking_a = build_booking(user_id, flight_a, cabin_class="economy", booked_days_ago=14, now=now, has_insurance=True)
    alt_a = build_flight("UA", "ORD", "DEN", "2026-06-28", "morning", economy_price=370, business_price=925)

    flight_b = build_flight("UA", "ORD", "DEN", "2026-06-23", "afternoon", economy_price=370, business_price=925)
    booking_b = build_booking(user_id, flight_b, cabin_class="economy", booked_days_ago=14, now=now, has_insurance=True)
    alt_b = build_flight("UA", "ORD", "DEN", "2026-06-29", "afternoon", economy_price=390, business_price=975)

    a_id = booking_a.booking_id
    b_id = booking_b.booking_id

    task_data = {
        "task_id": "challenge_one_day_apart_different_fee_tier",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            f"I need to push both my Denver trips back one week each. "
            f"{a_id} (June 22) to June 28, and {b_id} (June 23) to June 29. "
            f"Both personal reasons. What are the fees? My user ID is {user_id}."
        ),
        "user_simulator": {
            "personality": "Efficient. Lists both together. Expects combined total.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"{a_id}: ORD to DEN, June 22 -> June 28",
                f"{b_id}: ORD to DEN, June 23 -> June 29",
                "Both personal reasons",
            ],
            "unknown_info": ["That fees differ by 1-day departure difference"],
            "task_rules": [
                "Provide both bookings. Ask combined fees.",
                "If agent charges same fee for both, ask: 'Should the fees be different since one departs June 22 and the other June 23?'",
                "If agent correctly differentiates, say: 'Go ahead with both.'",
                "After both done, end with [TASK_DONE].",
            ],
        },
        "_replay_trace": [
            {"name": "update_booking", "arguments": {"booking_id": a_id, "flight_id": alt_a.flight_id, "change_reason": "personal"}},
            {"name": "update_booking", "arguments": {"booking_id": b_id, "flight_id": alt_b.flight_id, "change_reason": "personal"}},
        ],
        "task_summary": (
            "User changes two nearly identical bookings that differ only by one day in their original departure dates.\n"
            "The evaluator should check that the agent notices the one-day fee-window boundary, quotes different fees for the two bookings, and gives the correct combined total before proceeding."
        ),
        "task_requirements": [
            {
                "id": "state_first_booking_fee",
                "kind": "must",
                "requirement": f"Agent must explain that {a_id} carries a $150 change fee.",
                "evidence": "conversation",
            },
            {
                "id": "state_second_booking_fee",
                "kind": "must",
                "requirement": f"Agent must explain that {b_id} carries a $75 change fee.",
                "evidence": "conversation",
            },
            {
                "id": "state_combined_total",
                "kind": "must",
                "requirement": "Agent must state that the combined fees for the two changes total $225.",
                "evidence": "conversation",
            },
            {
                "id": "state_not_same_fee_both",
                "kind": "must_not",
                "requirement": "Agent must not tell the user that both bookings fall under the same change-fee tier with the same fee.",
                "evidence": "conversation",
            },
        ],
    }
    return [flight_a, alt_a, flight_b, alt_b], [booking_a, booking_b], task_data


def build_challenge_48():
    """Challenge 48: Bereavement on domestic <=7d — agent confuses discount direction.

    user_001 (Emma, gold) economy domestic SEA->LAX, $500, June 18 (<=7d, 3 days).
    Bereavement. Change to June 24.

    Correct: domestic <=7d = $150 base. Bereavement 75% OFF = pay 25% = $37.
    Common error: 75% OF $150 = $112 (agent computes 75% as the FEE, not the discount).
    Or: 25% of wrong base ($75 >7d rate * 25% = $18).
    """
    user_id = "user_001"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW

    flight = build_flight("AS", "SEA", "LAX", "2026-06-18", "morning", economy_price=500, business_price=1250)
    booking = build_booking(user_id, flight, cabin_class="economy", booked_days_ago=14, now=now, has_insurance=False)
    alt = build_flight("AS", "SEA", "LAX", "2026-06-24", "afternoon", economy_price=520, business_price=1300)

    booking_id = booking.booking_id
    task_data = {
        "task_id": "challenge_bereavement_discount_direction",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            f"Family bereavement. I need to change {booking_id} to June 24 please. My user ID is {user_id}."
        ),
        "user_simulator": {
            "personality": "Brief, grieving.",
            "known_info": [f"Your user ID: {user_id}", f"Booking: {booking_id} (SEA to LAX, June 18)", "Bereavement"],
            "unknown_info": ["Fee amount"],
            "task_rules": [
                f"Open with: bereavement, change {booking_id} to June 24.",
                "Accept whatever fee and end with [TASK_DONE].",
            ],
        },
        "_replay_trace": [
            {"name": "update_booking", "arguments": {"booking_id": booking_id, "flight_id": alt.flight_id, "change_reason": "bereavement"}},
        ],
        "task_summary": (
            "User requests a bereavement change on a domestic booking that departs within 7 days.\n"
            "The evaluator should check that the agent applies the bereavement discount in the correct direction, landing on the small discounted fee rather than 75% of the base fee or the wrong time-window base."
        ),
        "task_requirements": [
            {
                "id": "state_correct_bereavement_fee",
                "kind": "must",
                "requirement": "Agent must explain that the bereavement change fee for this booking is $37.",
                "evidence": "conversation",
            },
            {
                "id": "state_discount_direction",
                "kind": "must",
                "requirement": "Agent must treat bereavement as a 75% discount off the base fee rather than as paying 75% of the base fee.",
                "evidence": "conversation",
            },
            {
                "id": "state_not_wrong_bereavement_fee",
                "kind": "must_not",
                "requirement": "Agent must not tell the user that the correct bereavement fee is $112 or $18 for this booking.",
                "evidence": "conversation",
            },
        ],
    }
    return [flight, alt], [booking], task_data


def build_challenge_49():
    """Challenge 49: Medical on domestic <=7d — similar to bereavement but 50% discount.

    user_002 (Liam, basic) economy domestic DEN->LAX, $350, June 19 (<=7d, 4 days).
    Medical. Change to June 25.

    Correct: domestic <=7d = $150 base. Medical 50% = $75 fee.
    Common error: uses >7d rate ($75 * 50% = $37), or intl rate, or no discount.
    """
    user_id = "user_002"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW

    flight = build_flight("UA", "DEN", "LAX", "2026-06-19", "afternoon", economy_price=350, business_price=875)
    booking = build_booking(user_id, flight, cabin_class="economy", booked_days_ago=14, now=now, has_insurance=False)
    alt = build_flight("UA", "DEN", "LAX", "2026-06-25", "afternoon", economy_price=380, business_price=950)

    booking_id = booking.booking_id
    task_data = {
        "task_id": "challenge_medical_domestic_lt7d",

        "user_id": user_id,
        "now": now,
        "opening_message": (f"Medical emergency. Need to change {booking_id} to June 25. My user ID is {user_id}."),
        "user_simulator": {
            "personality": "Urgent. Brief.",
            "known_info": [f"Your user ID: {user_id}", f"Booking: {booking_id} (DEN to LAX, June 19)", "Medical"],
            "unknown_info": ["Fee amount"],
            "task_rules": [
                f"Open with: medical, change {booking_id} to June 25.",
                "Accept fee and end with [TASK_DONE].",
            ],
        },
        "_replay_trace": [
            {"name": "update_booking", "arguments": {"booking_id": booking_id, "flight_id": alt.flight_id, "change_reason": "medical"}},
        ],
        "task_summary": (
            "User requests a medical change on a domestic booking that departs within 7 days.\n"
            "The evaluator should check that the agent applies the within-7-days domestic base fee and the 50% medical discount correctly instead of drifting to the cheaper >7-days tier or forgetting the discount entirely."
        ),
        "task_requirements": [
            {
                "id": "state_correct_medical_fee",
                "kind": "must",
                "requirement": "Agent must explain that the medical change fee for this booking is $75.",
                "evidence": "conversation",
            },
            {
                "id": "state_correct_tier_basis",
                "kind": "must",
                "requirement": "Agent must keep the fee reasoning on the domestic within-7-days path rather than on the cheaper more-than-7-days path.",
                "evidence": "conversation",
            },
            {
                "id": "state_not_wrong_medical_fee",
                "kind": "must_not",
                "requirement": "Agent must not tell the user that the correct medical change fee is $37 or $150 for this booking.",
                "evidence": "conversation",
            },
        ],
    }
    return [flight, alt], [booking], task_data


def build_challenge_50():
    """Challenge 50: Medical intl >7d with fare diff going DOWN — agent thinks savings + discount.

    user_004 (Noah, silver) economy intl JFK->CDG, $900, June 28 (>7d, 13 days).
    Medical. Change to CHEAPER flight July 5 at $850.

    Correct: intl >7d = $100. Medical 50% = $50 fee. Fare diff $850-$900=-$50 (not refunded).
    price_paid = $850 + $50 = $900. Total additional: $0 (same as original!).

    Agent thinks: "cheaper flight + medical discount = savings!" But the $50 savings on
    fare is eaten by the $50 medical change fee. No net savings.

    Cancel+rebook comparison: cancel fee max($75, 20%*900)=$180. Rebook $850.
    Net: $180+$850-$900=$130 additional. MUCH worse than change ($0 additional).
    """
    user_id = "user_004"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW

    flight = build_flight("AF", "JFK", "CDG", "2026-06-28", "morning", economy_price=900, business_price=2250)
    booking = build_booking(user_id, flight, cabin_class="economy", booked_days_ago=14, now=now, has_insurance=True)
    alt = build_flight("AF", "JFK", "CDG", "2026-07-05", "morning", economy_price=850, business_price=2125)

    booking_id = booking.booking_id
    task_data = {
        "task_id": "challenge_medical_intl_gt7d_no_savings",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            f"I have a medical issue and want to change {booking_id} to July 5. "
            f"The later flights seem cheaper too. My user ID is {user_id}."
        ),
        "user_simulator": {
            "personality": "Hopeful about saving money with the cheaper flight, but focused on moving the same Paris trip rather than shopping around.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"Booking: {booking_id} (JFK to CDG, June 28)",
                "Medical reason",
                f"For this task, keep the same route and accept {alt.flight_id} if the agent explains the fee correctly",
            ],
            "unknown_info": [
                "That cheaper flight does not create net savings because the medical change fee offsets it",
                "Exact fee",
            ],
            "task_rules": [
                f"Open with: medical, change {booking_id} to July 5, mention that the later flight seems cheaper.",
                f"If the agent offers {alt.flight_id} on July 5 on the same route, stay on that route and do not pivot to other airlines, airports, or destinations.",
                "Ask one clarifying question: does the cheaper fare actually save me money after the medical fee, or does it just cancel out?",
                "If the agent explains that the $50 cheaper fare is offset by the $50 medical change fee so there is no net savings, say 'That makes sense. Go ahead.'",
                "If the agent quotes the wrong fee math, push once: 'I thought the flight was $50 cheaper. Can you double-check whether that actually saves me anything after the medical fee?'",
                "After the same-route July 5 change is completed, end with [TASK_DONE].",
            ],
        },
        "task_summary": (
            "User sees a cheaper later international flight and assumes a medical change should produce savings, but the discounted change fee exactly cancels out the lower fare.\n"
            "The evaluator should check that the agent applies the international more-than-7-days medical fee correctly, does not invent a refund on the negative fare difference, and explains that the net additional cost is zero rather than a savings windfall."
        ),
        "task_requirements": [
            {
                "id": "medical_intl_gt7d_fee_is_50",
                "kind": "must",
                "requirement": "Agent must explain that this medical change uses the international more-than-7-days base fee of $100 and therefore results in a $50 change fee after the medical discount.",
                "evidence": "conversation",
            },
            {
                "id": "negative_fare_diff_not_refunded_here",
                "kind": "must",
                "requirement": "Agent must make clear that the $50 cheaper replacement flight does not create a refund or extra savings on the change path because the negative fare difference is not refunded.",
                "evidence": "conversation",
            },
            {
                "id": "net_additional_cost_is_zero",
                "kind": "must",
                "requirement": "Agent must explain or otherwise make clear that the medical change produces no net additional cost overall, rather than a positive savings amount.",
                "evidence": "conversation",
            },
        ],
        "_replay_trace": [
            {"name": "update_booking", "arguments": {"booking_id": booking_id, "flight_id": alt.flight_id, "change_reason": "medical"}},
        ],
    }
    return [flight, alt], [booking], task_data


def _make_challenge_scenario(prefix: str, builder):
    """Create a scenario function that wraps a challenge builder."""

    def scenario() -> tuple[list[Flight], list[Booking], dict]:
        flights, bookings, task_data = builder()
        return flights, bookings, task_data

    scenario.__name__ = f"scenario_C{int(prefix) - 50:02d}"
    return scenario


scenario_C41 = _make_challenge_scenario('91', build_challenge_45)
scenario_C42 = _make_challenge_scenario('92', build_challenge_46)
scenario_C43 = _make_challenge_scenario('93', build_challenge_47)
scenario_C44 = _make_challenge_scenario('94', build_challenge_48)
scenario_C45 = _make_challenge_scenario('95', build_challenge_49)
scenario_C46 = _make_challenge_scenario('96', build_challenge_50)


SCENARIOS = [
    scenario_C41,
    scenario_C42,
    scenario_C43,
    scenario_C44,
    scenario_C45,
    scenario_C46,
]
