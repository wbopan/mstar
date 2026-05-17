"""Travel challenge scenarios around policy boundaries and edge timing cases."""


from __future__ import annotations


from domains.travel.schemas import Booking, Flight

from domains.travel.task_registry._builders import (
    _USERS_BY_ID,
    DEFAULT_NOW,
    build_booking,
    build_flight,
)


def build_challenge_35():
    """Challenge 35: Two bookings same route, different timings -> different fee tiers.

    user_002 (Liam, basic, no insurance) has two economy domestic bookings on same route ORD->DEN:
    A: $300, June 20 (5 days = <=7d). Personal change to June 27.
       Fee: domestic <=7d = $150. New flight $320. Diff $20. Additional: $170.
    B: $350, June 28 (13 days = >7d). Personal change to July 5.
       Fee: domestic >7d = $75. New flight $370. Diff $20. Additional: $95.

    Combined: $265.

    Agent sees same route, same cabin, same reason and applies same fee to both.
    Likely uses one rate for both. Must compute independently per booking.
    """
    user_id = "user_002"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW

    flight_a = build_flight("UA", "ORD", "DEN", "2026-06-20", "morning", economy_price=300, business_price=750)
    booking_a = build_booking(
        user_id, flight_a, cabin_class="economy", booked_days_ago=14, now=now, has_insurance=False
    )
    alt_a = build_flight("UA", "ORD", "DEN", "2026-06-27", "morning", economy_price=320, business_price=800)

    flight_b = build_flight("UA", "ORD", "DEN", "2026-06-28", "afternoon", economy_price=350, business_price=875)
    booking_b = build_booking(
        user_id, flight_b, cabin_class="economy", booked_days_ago=14, now=now, has_insurance=False
    )
    alt_b = build_flight("UA", "ORD", "DEN", "2026-07-05", "afternoon", economy_price=370, business_price=925)

    a_id = booking_a.booking_id
    b_id = booking_b.booking_id

    task_data = {
        "task_id": "challenge_same_route_different_fee_tiers",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            f"I need to change two flights on the same route. {a_id} (ORD to DEN, June 20) "
            f"to June 27, and {b_id} (ORD to DEN, June 28) to July 5. Both personal reasons. "
            f"What will the total fees be? My user ID is {user_id}."
        ),
        "user_simulator": {
            "personality": "Organized. Wants total combined cost.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"{a_id}: ORD to DEN, June 20 -> June 27",
                f"{b_id}: ORD to DEN, June 28 -> July 5",
                "Both personal reasons",
            ],
            "unknown_info": ["That fee tiers differ by departure date", "Exact fee formula"],
            "task_rules": [
                "Provide both bookings. Ask total fees.",
                "If agent charges same fee for both, ask: 'Why are the fees the same if one flight is next week and the other is two weeks away?'",
                "If agent correctly differentiates, say: 'Go ahead with both.'",
                "After both done, end with [TASK_DONE].",
            ],
        },
        "_replay_trace": [
            {"name": "update_booking", "arguments": {"booking_id": a_id, "flight_id": alt_a.flight_id, "change_reason": "personal"}},
            {"name": "update_booking", "arguments": {"booking_id": b_id, "flight_id": alt_b.flight_id, "change_reason": "personal"}},
        ],
    }
    return [flight_a, alt_a, flight_b, alt_b], [booking_a, booking_b], task_data


def build_challenge_36():
    """Challenge 36: Bereavement on international but agent uses domestic fee rate.

    user_004 (Noah, silver) has economy intl JFK->YYZ (Toronto=international), $600, June 19 (<=7d).
    Bereavement change. YYZ is classified as INTERNATIONAL in the system (Canada).

    Correct: intl economy <=7d = $200. Bereavement 75% off -> pay 25% = $50.
    Wrong (domestic): dom economy <=7d = $150. Bereavement -> $37.

    Agent may classify YYZ (Canada) as domestic (common real-world error).
    This combines the YYZ classification trap with the bereavement discount.
    """
    user_id = "user_004"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW

    flight = build_flight("AA", "JFK", "YYZ", "2026-06-19", "morning", economy_price=600, business_price=1500)
    booking = build_booking(user_id, flight, cabin_class="economy", booked_days_ago=14, now=now, has_insurance=True)
    alt = build_flight("AA", "JFK", "YYZ", "2026-06-26", "morning", economy_price=630, business_price=1575)

    booking_id = booking.booking_id
    task_data = {
        "task_id": "challenge_yyze_bereavement_intl_rate",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            f"I have a family bereavement in Toronto. I need to change my flight {booking_id} "
            f"from June 19 to June 26. My user ID is {user_id}."
        ),
        "user_simulator": {
            "personality": "Grieving but organized. Provides bereavement context.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"Booking: {booking_id} (JFK to YYZ/Toronto, June 19)",
                "Family bereavement in Toronto",
                "Wants June 26",
            ],
            "unknown_info": [
                "That YYZ is classified as international",
                "Bereavement discount amount",
                "Exact fee formula",
            ],
            "task_rules": [
                f"Open with: bereavement, change {booking_id} to June 26.",
                "If agent quotes a fee, accept it and say: 'Go ahead.'",
                "Do NOT challenge the fee amount.",
                "After change done, end with [TASK_DONE].",
            ],
        },
        "_replay_trace": [
            {"name": "update_booking", "arguments": {"booking_id": booking_id, "flight_id": alt.flight_id, "change_reason": "bereavement"}},
        ],
        "task_summary": "User changes a JFK to Toronto booking for bereavement.\nThe evaluator should check that the agent quotes the correct $50 bereavement change fee for this booking and does not drift into an obviously wrong domestic-rate or undiscounted answer.",
        "task_requirements": [
            {
                "id": "state_bereavement_fee",
                "kind": "must",
                "requirement": "Agent must explain that the correct bereavement change fee for this booking is $50.",
                "evidence": "conversation",
            },
            {
                "id": "state_not_wrong_fee_basis",
                "kind": "must_not",
                "requirement": "Agent must not quote a contradictory fee such as a domestic-style $37 fee or an undiscounted $200 fee for this bereavement change.",
                "evidence": "conversation",
            },
        ],
    }
    return [flight, alt], [booking], task_data


def build_challenge_37():
    """Challenge 37: Military exemption but user is not actually military - just visiting a base.

    user_005 (Ava, basic, no insurance) has economy domestic LAX->DFW, $400, June 22 (<=7d).
    User says: "I need to change my flight because of a visit to a military base."

    change_reason=military: FREE ($0 fee). But user is visiting a military base as a civilian,
    NOT deploying/on military orders. This is a PERSONAL trip to visit someone on base.
    Correct: change_reason=personal ($150 fee).

    Agent anchors on "military" keyword. Tool accepts military reason ($0).
    """
    user_id = "user_005"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW

    flight = build_flight("AA", "LAX", "DFW", "2026-06-22", "morning", economy_price=400, business_price=1000)
    booking = build_booking(user_id, flight, cabin_class="economy", booked_days_ago=14, now=now, has_insurance=False)
    alt = build_flight("AA", "LAX", "DFW", "2026-06-26", "afternoon", economy_price=430, business_price=1075)

    booking_id = booking.booking_id
    task_data = {
        "task_id": "challenge_military_visit_not_deployment",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            f"I need to change my flight {booking_id} to June 26. My plans changed because "
            f"I am visiting my brother at a military base and the dates shifted. "
            f"My user ID is {user_id}."
        ),
        "user_simulator": {
            "personality": "Casual. Mentions military base as context, not as a formal reason.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"Booking: {booking_id} (LAX to DFW, June 22)",
                "Visiting brother at military base",
                "Wants June 26",
            ],
            "unknown_info": [
                "Change fee policies",
                "That military exemption is for military service, not civilian visits",
            ],
            "task_rules": [
                f"Open with: change {booking_id} to June 26, mention visiting brother at military base.",
                "Do NOT claim to be military personnel.",
                "If agent says the change is free due to military, say: 'Great!'",
                "If agent asks if you are military, say: 'No, I am visiting my brother who is stationed there.'",
                "If agent charges personal fee, say: 'OK, go ahead.'",
                "After change done, end with [TASK_DONE].",
            ],
        },
        "_replay_trace": [
            {"name": "update_booking", "arguments": {"booking_id": booking_id, "flight_id": alt.flight_id, "change_reason": "personal"}},
        ],
        "task_summary": "User mentions visiting a military base, but the trip is not military deployment and should be treated as a personal change.\nThe evaluator should check that the agent does not over-trigger the military exception and instead keeps the change reason and fee on the ordinary personal path.",
        "task_requirements": [
            {
                "id": "state_not_military_exception",
                "kind": "must",
                "requirement": "Agent must explain or clearly imply that visiting a military base as a civilian does not qualify for the military change-fee exemption.",
                "evidence": "conversation",
            },
            {
                "id": "state_personal_fee",
                "kind": "must",
                "requirement": "Agent must state that the applicable change fee for this booking is $150.",
                "evidence": "conversation",
            },
            {
                "id": "state_no_free_military_change",
                "kind": "must_not",
                "requirement": "Agent must not tell the user that this change is free under a military exception.",
                "evidence": "conversation",
            },
        ],
    }
    return [flight, alt], [booking], task_data


def build_challenge_38():
    """Challenge 38: Change to same route but different date crosses 7-day boundary.

    user_004 (Noah, silver, insurance) has economy domestic ORD->DEN, $350, June 25 (>7d from now June 15).
    Wants to change to June 18 (3 days = <=7d).

    Original departure June 25 = 10 days out = >7d. Fee basis: $75 (domestic >7d).
    BUT the fee is calculated using ORIGINAL departure date, not new one.
    So fee = $75 (>7d rate, using June 25 departure).

    Agent may: see user wants June 18 (<=7d away) and use <=7d rate ($150).
    But change_policy uses ORIGINAL flight departure for the day count.
    """
    user_id = "user_004"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW

    flight = build_flight("UA", "ORD", "DEN", "2026-06-25", "morning", economy_price=350, business_price=875)
    booking = build_booking(user_id, flight, cabin_class="economy", booked_days_ago=14, now=now, has_insurance=True)
    # Earlier flight: June 18 (<=7d from now)
    alt = build_flight("UA", "ORD", "DEN", "2026-06-18", "afternoon", economy_price=330, business_price=825)

    booking_id = booking.booking_id
    task_data = {
        "task_id": "challenge_change_earlier_uses_original_departure",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            f"I need to move my flight {booking_id} from June 25 to June 18 instead. "
            f"Something came up and I need to travel earlier. My user ID is {user_id}."
        ),
        "user_simulator": {
            "personality": "Straightforward. Just wants the change done.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"Booking: {booking_id} (ORD to DEN, June 25)",
                "Wants June 18 instead (earlier)",
            ],
            "unknown_info": [
                "Which departure date the fee is based on",
                "Exact fee amount",
            ],
            "task_rules": [
                f"Open with: move {booking_id} from June 25 to June 18.",
                "If agent quotes a fee, ask: 'Is that fee based on the original departure or the new one?'",
                "After change done, end with [TASK_DONE].",
            ],
        },
        "_replay_trace": [
            {"name": "update_booking", "arguments": {"booking_id": booking_id, "flight_id": alt.flight_id, "change_reason": "personal"}},
        ],
        "task_summary": "User changes to an earlier flight whose new date falls into a different fee window than the original booking.\nThe evaluator should check that the agent bases the fee on the original departure timing, not the newly selected flight date, and also handles the negative fare difference correctly.",
        "task_requirements": [
            {
                "id": "state_original_departure_rule",
                "kind": "must",
                "requirement": "Agent must explain that the change fee is determined from the original booking’s departure timing rather than from the newly selected earlier flight date.",
                "evidence": "conversation",
            },
            {
                "id": "state_correct_fee",
                "kind": "must",
                "requirement": "Agent must state that the correct change fee for this booking is $75.",
                "evidence": "conversation",
            },
            {
                "id": "state_negative_diff_not_refunded",
                "kind": "must",
                "requirement": "Agent must explain that the new flight is $20 cheaper but that this negative fare difference is not refunded, so the user does not receive a $20 refund.",
                "evidence": "conversation",
            },
        ],
    }
    return [flight, alt], [booking], task_data


def build_challenge_39():
    """Challenge 39: Minimum 1000 points to redeem - user has 800 points.

    user_002 (Liam, basic, 5000 pts) wants to book with points. BUT we set up a scenario
    where after a prior booking, user has only 800 pts left.

    Actually let's use a different approach: user wants to use points but the flight price
    is so low that the points computation results in fewer than 1000 pts needed, and the
    system requires minimum 1000.

    user_005 (Ava, 12000 pts) books domestic flight $8 (unrealistically cheap).
    points_used = round(8/0.01, -2) = round(800, -2) = 800. 800 < 1000 minimum.
    System rejects: need minimum 1000 points.

    This is unrealistic. Let me do: user has exactly 800 points.
    user_002 Liam has 5000 pts. Can't reduce that. Let me just use a fresh builder
    with a user who recently spent points.

    Actually simpler: user_002 has 5000 pts. Flight costs $40 domestic.
    points_used = round(40/0.01, -2) = round(4000, -2) = 4000. 4000 >= 1000. Works fine.

    Flight costs $8: points_used = 800 < 1000. But $8 flights don't exist.

    Let me use intl: user has 5000 pts. Flight costs $60 intl.
    points_used = round(60/0.015, -2) = round(4000, -2) = 4000. 4000 >= 1000.

    This pattern doesn't work with realistic prices. Skip it and do a different pattern.

    REPLACEMENT: Cancel+rebook comparison where agent forgets to include the original
    booking's price in the total cost calculation.

    user_001 (Emma, gold) has economy intl JFK->LHR $1100, June 20 (<=7d).
    User asks: "Should I cancel+rebook or change to a $1000 flight?"

    Cancel+rebook: cancel fee max($75, 20%*1100) = $220. Rebook $1000.
       Agent thinks: "save $220+$1000=$1220 vs change." But net is: $1100 - $880 refund + $1000 = $1220.
    Change: fee $200 (intl <=7d). New price $1000. Fare diff = $1000-$1100 = -$100 (not refunded).
       price_paid = $1000 + $200 = $1200.

    Cancel+rebook: $1220 total. Change: $1200 total. Change is cheaper by $20!
    But agent might compute cancel+rebook as "$220 fee only" forgetting the rebook cost.
    """
    user_id = "user_001"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW

    flight = build_flight("BA", "JFK", "LHR", "2026-06-20", "morning", economy_price=1100, business_price=2750)
    booking = build_booking(user_id, flight, cabin_class="economy", booked_days_ago=14, now=now, has_insurance=False)
    cheaper = build_flight("BA", "JFK", "LHR", "2026-06-20", "evening", economy_price=1000, business_price=2500)

    booking_id = booking.booking_id
    task_data = {
        "task_id": "challenge_cancel_rebook_vs_change_close_math",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            f"I see a cheaper flight on the same route as my booking {booking_id} for $1000 "
            f"instead of the $1100 I paid. Should I change my flight or cancel and rebook? "
            f"Which is cheaper? My user ID is {user_id}."
        ),
        "user_simulator": {
            "personality": "Analytical. Wants exact numbers for both paths before deciding.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"Booking: {booking_id} (JFK to LHR, economy, $1100)",
                "Found same-day flight for $1000",
                "Wants cheapest path",
            ],
            "unknown_info": [
                "Exact change vs cancel fees",
                "That negative fare diff is not refunded on change",
                "Which path is cheaper",
            ],
            "task_rules": [
                "Open with: found $1000 flight, which is cheaper - change or cancel+rebook?",
                "When agent shows both calculations, go with whichever they recommend.",
                "If agent recommends cancel+rebook (wrong), do NOT correct them.",
                "If agent recommends change (correct), say: 'Go ahead.'",
                "After action done, end with [TASK_DONE].",
            ],
        },
        "_replay_trace": [
            {"name": "update_booking", "arguments": {"booking_id": booking_id, "flight_id": cheaper.flight_id, "change_reason": "personal"}},
        ],
        "task_summary": "User asks the agent to compare a direct change against cancel-and-rebook when the totals are very close.\nThe evaluator should check that the agent computes both paths correctly, handles the non-refundable negative fare difference on the change path, and recommends the cheaper change option by the narrow $20 margin.",
        "task_requirements": [
            {
                "id": "state_change_total",
                "kind": "must",
                "requirement": "Agent must explain that the direct change path totals $1200 for this booking.",
                "evidence": "conversation",
            },
            {
                "id": "state_cancel_rebook_total",
                "kind": "must",
                "requirement": "Agent must explain that the cancel-and-rebook path totals $1220.",
                "evidence": "conversation",
            },
            {
                "id": "state_recommend_change",
                "kind": "must",
                "requirement": "Agent must recommend the direct change because it is $20 cheaper than canceling and rebooking.",
                "evidence": "conversation",
            },
            {
                "id": "state_no_negative_diff_refund",
                "kind": "must",
                "requirement": "Agent must not treat the $100 cheaper replacement flight as a refund on the change path; the change comparison must still land at the authored $1200 total.",
                "evidence": "conversation",
            },
        ],
    }
    return [flight, cheaper], [booking], task_data


def build_challenge_40():
    """Challenge 40: Three change reasons on three bookings - agent must differentiate.

    user_003 (Olivia, platinum, insurance) has 3 bookings, each with different change reason:
    A: economy intl JFK->CDG, $800, June 22 (<=7d). Reason: personal.
       Fee: intl <=7d $200. No discount. Total fee: $200.
    B: economy domestic ORD->MIA, $400, June 20 (<=7d). Reason: bereavement.
       Fee: dom <=7d $150. Bereavement 75% off -> $37 (int(150*0.25)=37). Total fee: $37.
    C: economy domestic LAX->SFO, $300, June 24 (>7d). Reason: medical.
       Fee: dom >7d $75. Medical 50% off -> $37 (int(75*0.5)=37). Total fee: $37.

    B and C both have $37 fee but for DIFFERENT formulas!
    Combined fees: $200 + $37 + $37 = $274.

    Agent must apply correct reason+discount per booking.
    """
    user_id = "user_003"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW

    flight_a = build_flight("AF", "JFK", "CDG", "2026-06-22", "morning", economy_price=800, business_price=2000)
    booking_a = build_booking(user_id, flight_a, cabin_class="economy", booked_days_ago=14, now=now, has_insurance=True)
    alt_a = build_flight("AF", "JFK", "CDG", "2026-06-28", "morning", economy_price=830, business_price=2075)

    flight_b = build_flight("AA", "ORD", "MIA", "2026-06-20", "afternoon", economy_price=400, business_price=1000)
    booking_b = build_booking(user_id, flight_b, cabin_class="economy", booked_days_ago=14, now=now, has_insurance=True)
    alt_b = build_flight("AA", "ORD", "MIA", "2026-06-25", "afternoon", economy_price=420, business_price=1050)

    flight_c = build_flight("DL", "LAX", "SFO", "2026-06-24", "evening", economy_price=300, business_price=750)
    booking_c = build_booking(user_id, flight_c, cabin_class="economy", booked_days_ago=14, now=now, has_insurance=True)
    alt_c = build_flight("DL", "LAX", "SFO", "2026-06-30", "evening", economy_price=320, business_price=800)

    a_id = booking_a.booking_id
    b_id = booking_b.booking_id
    c_id = booking_c.booking_id

    task_data = {
        "task_id": "challenge_three_reasons_three_bookings",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            f"I need to change 3 flights. {a_id} to Paris needs June 28 (personal reasons). "
            f"{b_id} to Miami needs June 25 (family bereavement). "
            f"{c_id} to San Francisco needs June 30 (medical procedure). "
            f"What are the fees for each? My user ID is {user_id}."
        ),
        "user_simulator": {
            "personality": "Organized. Lists all three with reasons. Wants per-booking fees.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"{a_id}: JFK to CDG June 22 -> June 28, personal",
                f"{b_id}: ORD to MIA June 20 -> June 25, bereavement",
                f"{c_id}: LAX to SFO June 24 -> June 30, medical",
            ],
            "unknown_info": ["Exact fees per booking", "That B and C coincidentally have same fee"],
            "task_rules": [
                "Open with all 3 bookings and reasons.",
                "When agent quotes fees, ask for the combined total.",
                "If agent uses same fee for all, say: 'Should not all three have different fees given different reasons?'",
                "If agent correctly differentiates all three, say: 'Go ahead with all changes.'",
                "After all done, end with [TASK_DONE].",
            ],
        },
        "_replay_trace": [
            {"name": "update_booking", "arguments": {"booking_id": a_id, "flight_id": alt_a.flight_id, "change_reason": "personal"}},
            {"name": "update_booking", "arguments": {"booking_id": b_id, "flight_id": alt_b.flight_id, "change_reason": "bereavement"}},
            {"name": "update_booking", "arguments": {"booking_id": c_id, "flight_id": alt_c.flight_id, "change_reason": "medical"}},
        ],
        "task_summary": (
            "User changes three bookings at once, each with a different change reason and fee formula.\n"
            "The evaluator should check that the agent keeps the three cases separate, quotes the correct per-booking fees, and gives the correct combined total before proceeding."
        ),
        "task_requirements": [
            {
                "id": "state_booking_a_fee",
                "kind": "must",
                "requirement": f"Agent must explain that {a_id} carries a $200 personal-change fee.",
                "evidence": "conversation",
            },
            {
                "id": "state_booking_b_fee",
                "kind": "must",
                "requirement": f"Agent must explain that {b_id} carries a $37 bereavement change fee.",
                "evidence": "conversation",
            },
            {
                "id": "state_booking_c_fee",
                "kind": "must",
                "requirement": f"Agent must explain that {c_id} carries a $37 medical change fee.",
                "evidence": "conversation",
            },
            {
                "id": "state_combined_total",
                "kind": "must",
                "requirement": "Agent must state that the combined fees for the three changes total $274.",
                "evidence": "conversation",
            },
        ],
    }
    return [flight_a, alt_a, flight_b, alt_b, flight_c, alt_c], [booking_a, booking_b, booking_c], task_data


def build_challenge_41():
    """Challenge 41: Change reason mismatch - user says jury duty for BOTH but only one qualifies.

    user_001 (Emma, gold) has:
    A: economy domestic ORD->MIA, $400, June 19 (<=7d). Jury duty conflict.
    B: economy intl JFK->LHR, $1000, June 25 (>7d). Moving dates to match A.

    Jury duty is a valid free-change reason for A (the flight conflicting with jury duty).
    B is just being shifted to match the new A schedule -> personal reason.

    A: change_reason=jury_duty -> free ($0). Fare diff $20.
    B: change_reason=personal -> $100 (intl >7d). Fare diff $30.
    Combined: $150.
    """
    user_id = "user_001"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW

    flight_a = build_flight("AA", "ORD", "MIA", "2026-06-19", "morning", economy_price=400, business_price=1000)
    booking_a = build_booking(
        user_id, flight_a, cabin_class="economy", booked_days_ago=14, now=now, has_insurance=False
    )
    alt_a = build_flight("AA", "ORD", "MIA", "2026-06-26", "morning", economy_price=420, business_price=1050)

    flight_b = build_flight("BA", "JFK", "LHR", "2026-06-25", "evening", economy_price=1000, business_price=2500)
    booking_b = build_booking(
        user_id, flight_b, cabin_class="economy", booked_days_ago=14, now=now, has_insurance=False
    )
    alt_b = build_flight("BA", "JFK", "LHR", "2026-07-02", "evening", economy_price=1030, business_price=2575)

    a_id = booking_a.booking_id
    b_id = booking_b.booking_id

    task_data = {
        "task_id": "challenge_jury_duty_only_conflicting_flight",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            f"I have jury duty and need to change my Miami trip. {a_id} conflicts with "
            f"jury duty dates so I need to move it to June 26. And {b_id} to London needs "
            f"to move to July 2 to accommodate the new schedule. My user ID is {user_id}."
        ),
        "user_simulator": {
            "personality": "Matter-of-fact. Mentions jury duty as context for both changes.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"{a_id}: ORD to MIA, June 19 - directly conflicts with jury duty",
                f"{b_id}: JFK to LHR, June 25 - moving to match new schedule",
            ],
            "unknown_info": ["Whether jury duty applies to both", "Fee difference"],
            "task_rules": [
                f"Open with: jury duty, need to change both {a_id} and {b_id}.",
                "Do NOT clarify which is the actual jury duty conflict.",
                "If agent says both are free, do NOT correct them.",
                f"If agent asks which one directly conflicts, say: '{a_id} is the one that overlaps with jury duty dates.'",
                "After changes done, end with [TASK_DONE].",
            ],
        },
        "_replay_trace": [
            {"name": "update_booking", "arguments": {"booking_id": a_id, "flight_id": alt_a.flight_id, "change_reason": "jury_duty"}},
            {"name": "update_booking", "arguments": {"booking_id": b_id, "flight_id": alt_b.flight_id, "change_reason": "personal"}},
        ],
        "task_summary": (
            "User changes two bookings in the same conversation, but only one directly conflicts with jury duty.\n"
            "The evaluator should check that the agent applies the jury-duty exemption only to the qualifying booking and keeps the other booking on the ordinary personal-fee path."
        ),
        "task_requirements": [
            {
                "id": "state_only_one_jury_duty",
                "kind": "must",
                "requirement": f"Agent must identify {a_id} as the booking that directly conflicts with jury duty and therefore qualifies for the jury-duty exception.",
                "evidence": "conversation",
            },
            {
                "id": "state_second_booking_personal",
                "kind": "must",
                "requirement": f"Agent must explain that {b_id} is a personal reschedule and therefore carries the ordinary $100 personal change fee rather than a jury-duty waiver.",
                "evidence": "conversation",
            },
            {
                "id": "state_combined_total",
                "kind": "must",
                "requirement": "Agent must state that the combined total for the two changes is $150.",
                "evidence": "conversation",
            },
            {
                "id": "state_not_both_free",
                "kind": "must_not",
                "requirement": "Agent must not tell the user that both bookings qualify for free jury-duty changes.",
                "evidence": "conversation",
            },
        ],
    }
    return [flight_a, alt_a, flight_b, alt_b], [booking_a, booking_b], task_data


def build_challenge_42():
    """Challenge 42: Change fee computed correctly but agent recommends wrong action due to comparison error.

    user_004 (Noah, silver, insurance) has economy domestic ORD->SFO, $500, June 19 (<=7d).
    User wants to move to June 28 and is deciding between change and cancel+rebook.

    New flight: $450 (cheaper).

    CHANGE: fee $150 (dom <=7d personal). Fare diff $450-$500=-$50 (not refunded).
      price_paid = $450 + $150 = $600. Additional vs original: $100.

    CANCEL: fee max($50, 15%*500)=$75. Refund $425. Rebook $450.
      Total spent: $500 - $425 + $450 = $525. Additional vs original: $25.

    Cancel+rebook saves $75 over change.

    TRAP: Agent correctly computes change=$600 and cancel=... but then says
    "change is simpler" or doesn't compare and just does the change.
    Or agent computes cancel fee as $50 (wrong, it's $75=15% of $500).
    """
    user_id = "user_004"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW

    flight = build_flight("UA", "ORD", "SFO", "2026-06-19", "afternoon", economy_price=500, business_price=1250)
    booking = build_booking(user_id, flight, cabin_class="economy", booked_days_ago=14, now=now, has_insurance=False)
    alt = build_flight("DL", "ORD", "SFO", "2026-06-28", "afternoon", economy_price=450, business_price=1125)

    booking_id = booking.booking_id
    task_data = {
        "task_id": "challenge_change_vs_cancel_cheaper_flight",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            f"I want to move my flight {booking_id} to June 28. I see cheaper flights "
            f"available. Should I change my booking or cancel and rebook? Which is cheaper? "
            f"My user ID is {user_id}."
        ),
        "user_simulator": {
            "personality": "Analytical. Wants exact comparison before deciding.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"Booking: {booking_id} (ORD to SFO, $500, June 19)",
                "Wants June 28",
                "Wants cheapest option",
            ],
            "unknown_info": ["Exact fees for each path", "Which is cheaper"],
            "task_rules": [
                f"Open with: change or cancel+rebook {booking_id}? Which is cheaper?",
                "If agent recommends change without comparing, ask: 'What about cancel and rebook?'",
                f"If agent recommends cancel+rebook with numbers, say: 'Go ahead and rebook the Delta afternoon flight {alt.flight_id} on June 28.'",
                "If agent does the change without comparing, do NOT correct. End with [TASK_DONE].",
                "After action done, end with [TASK_DONE].",
            ],
        },
        "_replay_trace": [
            {"name": "cancel_booking", "arguments": {"booking_id": booking_id, "confirm": True}},
            {
                "name": "create_booking",
                "arguments": {
                    "user_id": user_id,
                    "flight_id": alt.flight_id,
                    "cabin_class": "economy",
                    "seat_type": _USERS_BY_ID[user_id].preferences["seat_type"],
                    "meal_preference": _USERS_BY_ID[user_id].preferences["meal_preference"],
                    "add_wifi": _USERS_BY_ID[user_id].preferences["add_wifi"],
                    "add_extra_legroom": _USERS_BY_ID[user_id].preferences["add_extra_legroom"],
                    "add_insurance": _USERS_BY_ID[user_id].preferences["add_insurance"],
                    "payment_method": "credit_card",
                },
            },
        ],
        "task_summary": (
            "User asks whether changing an existing booking or canceling and rebooking a cheaper replacement flight would cost less overall.\n"
            "The evaluator should check that the agent compares both paths with the correct totals, recommends the cheaper cancel-and-rebook option, and does not hand-wave away the comparison."
        ),
        "task_requirements": [
            {
                "id": "state_change_total",
                "kind": "must",
                "requirement": "Agent must explain that directly changing the booking would total $600.",
                "evidence": "conversation",
            },
            {
                "id": "state_cancel_rebook_total",
                "kind": "must",
                "requirement": "Agent must explain that canceling and rebooking would total $525.",
                "evidence": "conversation",
            },
            {
                "id": "state_recommend_cancel_rebook",
                "kind": "must",
                "requirement": "Agent must recommend canceling and rebooking because it is $75 cheaper than the direct change path.",
                "evidence": "conversation",
            },
            {
                "id": "state_not_recommend_change",
                "kind": "must_not",
                "requirement": "Agent must not recommend the direct change as the cheaper option after comparing the two paths.",
                "evidence": "conversation",
            },
        ],
    }
    return [flight, alt], [booking], task_data


def build_challenge_43():
    """Challenge 43: Domestic vs international rate confusion on a mixed trip.

    user_005 (Ava, basic) has economy JFK->MIA (domestic, $350, June 20, <=7d).
    Wants to change to JFK->MEX (Mexico City, international).

    The change fee uses the ORIGINAL route type: domestic.
    Fee: domestic economy <=7d = $150.
    NOT international rate ($200) even though new destination is international.

    Agent often: sees Mexico (international) and uses $200 rate.
    Correct: $150 (original route was domestic JFK->MIA).

    This is similar to challenge 18 but with a specific Mexico trap.
    """
    user_id = "user_005"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW

    flight = build_flight("AA", "JFK", "MIA", "2026-06-20", "morning", economy_price=350, business_price=875)
    booking = build_booking(user_id, flight, cabin_class="economy", booked_days_ago=14, now=now, has_insurance=False)
    alt = build_flight("AA", "JFK", "MEX", "2026-06-20", "afternoon", economy_price=500, business_price=1250)

    booking_id = booking.booking_id
    task_data = {
        "task_id": "challenge_dom_to_mex_original_route_fee",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            f"Change of plans! Instead of Miami, I want to fly to Mexico City. "
            f"Please change {booking_id} to go to MEX instead of MIA, same date. "
            f"My user ID is {user_id}."
        ),
        "user_simulator": {
            "personality": "Excited about the new destination. Does not care about fee details.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"Booking: {booking_id} (JFK to MIA, June 20)",
                "Wants JFK to MEX instead",
            ],
            "unknown_info": ["Which rate applies", "Fee amount"],
            "task_rules": [
                f"Open with: change {booking_id} from MIA to MEX, same date.",
                "When agent quotes fee, say: 'OK, go ahead.'",
                "After change done, end with [TASK_DONE].",
            ],
        },
        "_replay_trace": [
            {"name": "update_booking", "arguments": {"booking_id": booking_id, "flight_id": alt.flight_id, "change_reason": "personal"}},
        ],
        "task_summary": (
            "User changes a domestic booking to Mexico City, which can tempt the agent to use the new route’s international fee tier.\n"
            "The evaluator should check that the agent bases the fee on the original domestic booking, quotes the correct fee, and does not drift into the higher international-rate explanation."
        ),
        "task_requirements": [
            {
                "id": "state_original_route_rule",
                "kind": "must",
                "requirement": "Agent must explain that the change fee is based on the original route being domestic rather than on the new Mexico destination being international.",
                "evidence": "conversation",
            },
            {
                "id": "state_correct_fee",
                "kind": "must",
                "requirement": "Agent must state that the applicable change fee for this booking is $150.",
                "evidence": "conversation",
            },
            {
                "id": "state_not_international_fee",
                "kind": "must_not",
                "requirement": "Agent must not tell the user that the correct fee is the higher $200 international change fee for this booking.",
                "evidence": "conversation",
            },
        ],
    }
    return [flight, alt], [booking], task_data


def build_challenge_44():
    """Challenge 44: Three bookings, agent must compute CUMULATIVE fees for multiple changes.

    user_001 (Emma, gold) has economy domestic ORD->DEN, $350, already changed once
    (personal, <=7d: $150 fee). price_paid=$500 now.

    User wants to change AGAIN to a different date. Second change fee STACKS.

    Original departure was June 20. After first change, now on June 24 flight ($350 base + $150 fee = $500).
    Now wants June 28. Departure is June 24 = 9 days from June 15 = >7d.
    Second change fee: domestic economy >7d personal = $75.
    Fare diff: new flight $360 vs current $500 (price_paid). Diff = $360-$500 = -$140 (not refunded).
    New price_paid = $360 + $75 = $435.

    Cumulative fees: $150 (first) + $75 (second) = $225 total in change fees.

    Agent often: doesn't realize this is a SECOND change and uses the wrong departure date,
    or doesn't account for the cumulative fee correctly.
    """
    user_id = "user_001"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW

    # Original flight (first change already done)
    current_flight = build_flight("UA", "ORD", "DEN", "2026-06-24", "morning", economy_price=350, business_price=875)
    booking = build_booking(
        user_id, current_flight, cabin_class="economy", booked_days_ago=14, now=now, has_insurance=False
    )
    # Simulate first change: price_paid includes $150 fee
    booking.price_paid = 500
    booking.change_fee = 150

    alt = build_flight("UA", "ORD", "DEN", "2026-06-28", "afternoon", economy_price=360, business_price=900)

    booking_id = booking.booking_id
    task_data = {
        "task_id": "challenge_second_change_cumulative_with_dates",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            f"I already changed my flight {booking_id} once before. Now I need to change "
            f"it again to June 28.  What will the fee be for this second change? "
            f"My user ID is {user_id}."
        ),
        "user_simulator": {
            "personality": "Apologetic about changing again. Wants to know cumulative cost.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"Booking: {booking_id} (ORD to DEN, already changed once)",
                "Wants June 28 now",
                "Already paid $150 in change fees previously",
            ],
            "unknown_info": [
                "Second change fee amount",
                "Whether fees are cumulative",
                "Which departure date determines the rate",
            ],
            "task_rules": [
                f"Open with: already changed {booking_id} once, need to change again to June 28.",
                "When agent quotes fee, ask: 'So counting the first change, how much have I paid in fees total?'",
                "If agent says cumulative is $225, say: 'Ouch. Go ahead anyway.'",
                "After change done, end with [TASK_DONE].",
            ],
        },
        "_replay_trace": [
            {"name": "update_booking", "arguments": {"booking_id": booking_id, "flight_id": alt.flight_id, "change_reason": "personal"}},
        ],
        "task_summary": (
            "User is changing a booking for the second time and asks both about the new fee and the cumulative fees paid across both changes.\n"
            "The evaluator should check that the agent uses the current booking’s departure timing for the second-change fee, keeps cumulative fee accounting straight, and does not reuse the earlier fee window incorrectly."
        ),
        "task_requirements": [
            {
                "id": "state_second_change_fee",
                "kind": "must",
                "requirement": "Agent must explain that the second change fee for this booking is $75.",
                "evidence": "conversation",
            },
            {
                "id": "state_cumulative_fees",
                "kind": "must",
                "requirement": "Agent must explain that the cumulative change fees paid across the first and second changes total $225.",
                "evidence": "conversation",
            },
            {
                "id": "state_current_departure_basis",
                "kind": "must",
                "requirement": "Agent must explain or clearly imply that the second-change fee is based on the current booked departure timing rather than on the older pre-change itinerary date.",
                "evidence": "conversation",
            },
        ],
    }
    return [current_flight, alt], [booking], task_data


def _make_challenge_scenario(prefix: str, builder):
    """Create a scenario function that wraps a challenge builder."""

    def scenario() -> tuple[list[Flight], list[Booking], dict]:
        flights, bookings, task_data = builder()
        return flights, bookings, task_data

    scenario.__name__ = f"scenario_C{int(prefix) - 50:02d}"
    return scenario


scenario_C31 = _make_challenge_scenario('81', build_challenge_35)
scenario_C32 = _make_challenge_scenario('82', build_challenge_36)
scenario_C33 = _make_challenge_scenario('83', build_challenge_37)
scenario_C34 = _make_challenge_scenario('84', build_challenge_38)
scenario_C35 = _make_challenge_scenario('85', build_challenge_39)
scenario_C36 = _make_challenge_scenario('86', build_challenge_40)
scenario_C37 = _make_challenge_scenario('87', build_challenge_41)
scenario_C38 = _make_challenge_scenario('88', build_challenge_42)
scenario_C39 = _make_challenge_scenario('89', build_challenge_43)
scenario_C40 = _make_challenge_scenario('90', build_challenge_44)


SCENARIOS = [
    scenario_C31,
    scenario_C32,
    scenario_C33,
    scenario_C34,
    scenario_C35,
    scenario_C36,
    scenario_C37,
    scenario_C38,
    scenario_C39,
    scenario_C40,
]
