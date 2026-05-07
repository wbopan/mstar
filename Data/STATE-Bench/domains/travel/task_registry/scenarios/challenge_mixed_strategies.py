"""Travel challenge scenarios with mixed-strategy tradeoffs."""


from __future__ import annotations


from domains.travel.schemas import Booking, Flight

from domains.travel.task_registry._builders import (
    _USERS_BY_ID,
    DEFAULT_NOW,
    build_booking,
    build_flight,
)


def build_challenge_51():
    """Challenge 51: Bereavement on intl <=7d — the hardest single-change fee.

    user_005 (Ava, basic) economy intl JFK->MEX, $700, June 18 (<=7d, 3 days).
    Bereavement. Change to June 25.

    Correct: intl <=7d = $200 base. Bereavement 75% off = pay 25% = $50.
    Common errors: domestic rate ($150*25%=$37), or 75% of $200=$150, or wrong tier.
    """
    user_id = "user_005"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW

    flight = build_flight("AA", "JFK", "MEX", "2026-06-18", "morning", economy_price=700, business_price=1750)
    booking = build_booking(user_id, flight, cabin_class="economy", booked_days_ago=14, now=now, has_insurance=False)
    alt = build_flight("AA", "JFK", "MEX", "2026-06-25", "morning", economy_price=730, business_price=1825)

    booking_id = booking.booking_id
    task_data = {
        "task_id": "challenge_bereavement_intl_lt7d_fee",

        "user_id": user_id,
        "now": now,
        "opening_message": (f"Family bereavement. Change {booking_id} to June 25 please. My user ID is {user_id}."),
        "user_simulator": {
            "personality": "Brief.",
            "known_info": [f"Your user ID: {user_id}", f"Booking: {booking_id} (JFK to MEX, June 18)", "Bereavement"],
            "unknown_info": ["Fee"],
            "task_rules": [
                f"Open with: bereavement, change {booking_id} to June 25.",
                "Accept fee and end with [TASK_DONE].",
            ],
        },
        "task_summary": (
            "User requests a bereavement change on an international booking within 7 days, which combines the highest international base tier with the strongest discount.\n"
            "The evaluator should check that the agent keeps the route classification and time window straight, applies bereavement as a 75% discount off the $200 base fee, and lands on the correct $50 fee instead of a domestic or reversed-discount answer."
        ),
        "task_requirements": [
            {
                "id": "bereavement_intl_lt7d_fee_is_50",
                "kind": "must",
                "requirement": "Agent must explain that the correct bereavement change fee for this booking is $50.",
                "evidence": "conversation",
            },
            {
                "id": "must_use_intl_lt7d_base",
                "kind": "must",
                "requirement": "Agent must keep the fee reasoning on the international within-7-days base of $200 rather than drifting to a domestic or more-than-7-days base fee.",
                "evidence": "conversation",
            },
            {
                "id": "must_not_quote_150_or_37",
                "kind": "must_not",
                "requirement": "Agent must not tell the user that the correct bereavement fee is $150 or $37 for this booking.",
                "evidence": "conversation",
            },
        ],
        "_replay_trace": [
            {"name": "update_booking", "arguments": {"booking_id": booking_id, "flight_id": alt.flight_id, "change_reason": "bereavement"}},
        ],
    }
    return [flight, alt], [booking], task_data


def build_challenge_52():
    """Challenge 52: Personal intl <=7d change — highest base fee.

    user_001 (Emma, gold) economy intl JFK->NRT, $1500, June 19 (<=7d, 4 days).
    Personal. Change to June 26.

    Correct: intl <=7d personal = $200 (no discount).
    New flight $1550. Diff $50. Additional $250.
    Agent sometimes uses >7d rate ($100) or domestic rate ($150).
    """
    user_id = "user_001"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW

    flight = build_flight("AA", "JFK", "NRT", "2026-06-19", "morning", economy_price=1500, business_price=3750)
    booking = build_booking(user_id, flight, cabin_class="economy", booked_days_ago=14, now=now, has_insurance=False)
    alt = build_flight("AA", "JFK", "NRT", "2026-06-26", "morning", economy_price=1550, business_price=3875)

    booking_id = booking.booking_id
    task_data = {
        "task_id": "challenge_personal_intl_lt7d_highest_fee",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            f"I need to push my Tokyo flight {booking_id} to June 26. Personal reasons. My user ID is {user_id}."
        ),
        "user_simulator": {
            "personality": "Professional.",
            "known_info": [f"Your user ID: {user_id}", f"Booking: {booking_id} (JFK to NRT, June 19)", "Personal"],
            "unknown_info": ["Fee"],
            "task_rules": [
                f"Open with: change {booking_id} to June 26, personal.",
                "Accept fee and end with [TASK_DONE].",
            ],
        },
        "task_summary": (
            "User requests a plain personal change on an international booking departing within 7 days, which should trigger the benchmark's highest standard change fee.\n"
            "The evaluator should check that the agent keeps the route and timing on the international within-7-days path and quotes the full $200 fee rather than drifting to the lower $100 or $150 alternatives."
        ),
        "task_requirements": [
            {
                "id": "personal_intl_lt7d_fee_is_200",
                "kind": "must",
                "requirement": "Agent must explain that the correct personal change fee for this booking is $200.",
                "evidence": "conversation",
            },
            {
                "id": "must_use_highest_standard_tier",
                "kind": "must",
                "requirement": "Agent must keep the fee reasoning on the international within-7-days tier rather than on a more-than-7-days or domestic tier.",
                "evidence": "conversation",
            },
            {
                "id": "must_not_quote_100_or_150",
                "kind": "must_not",
                "requirement": "Agent must not tell the user that the correct personal change fee is $100 or $150 for this booking.",
                "evidence": "conversation",
            },
        ],
        "_replay_trace": [
            {"name": "update_booking", "arguments": {"booking_id": booking_id, "flight_id": alt.flight_id, "change_reason": "personal"}},
        ],
    }
    return [flight, alt], [booking], task_data


def build_challenge_53():
    """Challenge 53: Two bookings, same reason (medical), different routes — different fees.

    user_004 (Noah, silver) has:
    A: economy intl JFK->CDG, $900, June 19 (<=7d, 4 days). Medical.
       Fee: intl <=7d $200 * 50% (medical) = $100.
    B: economy domestic ORD->DEN, $350, June 20 (<=7d, 5 days). Medical.
       Fee: domestic <=7d $150 * 50% (medical) = $75.

    Both medical, both <=7d, but different route types = different base fees.
    Agent may apply same fee to both. Combined: $175.
    """
    user_id = "user_004"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW

    flight_a = build_flight("AF", "JFK", "CDG", "2026-06-19", "morning", economy_price=900, business_price=2250)
    booking_a = build_booking(user_id, flight_a, cabin_class="economy", booked_days_ago=14, now=now, has_insurance=True)
    alt_a = build_flight("AF", "JFK", "CDG", "2026-06-26", "morning", economy_price=940, business_price=2350)

    flight_b = build_flight("UA", "ORD", "DEN", "2026-06-20", "afternoon", economy_price=350, business_price=875)
    booking_b = build_booking(user_id, flight_b, cabin_class="economy", booked_days_ago=14, now=now, has_insurance=True)
    alt_b = build_flight("UA", "ORD", "DEN", "2026-06-27", "afternoon", economy_price=380, business_price=950)

    a_id = booking_a.booking_id
    b_id = booking_b.booking_id

    task_data = {
        "task_id": "challenge_same_medical_different_routes",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            f"Due to a medical procedure, I need to change both {a_id} (Paris flight) "
            f"and {b_id} (Denver flight). Both to the following week. "
            f"Both for medical reasons. My user ID is {user_id}."
        ),
        "user_simulator": {
            "personality": "Organized. Lists both with same reason.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"{a_id}: JFK to CDG, June 19 -> June 26, medical",
                f"{b_id}: ORD to DEN, June 20 -> June 27, medical",
            ],
            "unknown_info": ["That fees differ by route type even with same reason"],
            "task_rules": [
                f"Open with: medical reason, change both {a_id} and {b_id}.",
                "Ask: 'What is the combined fee for both changes?'",
                "If agent charges same for both, ask: 'Should the fees differ since one is international and the other domestic?'",
                "After done, end with [TASK_DONE].",
            ],
        },
        "task_summary": (
            "User changes two bookings for the same medical reason, but one booking is international and the other is domestic, so the discounted fees should still differ.\n"
            "The evaluator should check that the agent does not collapse the two medical changes into one shared fee, applies the correct $100 international fee and $75 domestic fee, and gives the correct combined total of $175."
        ),
        "task_requirements": [
            {
                "id": "intl_medical_fee_is_100",
                "kind": "must",
                "requirement": "Agent must explain that the Paris booking carries a $100 medical change fee.",
                "evidence": "conversation",
            },
            {
                "id": "domestic_medical_fee_is_75",
                "kind": "must",
                "requirement": "Agent must explain that the Denver booking carries a $75 medical change fee.",
                "evidence": "conversation",
            },
            {
                "id": "combined_total_is_175",
                "kind": "must",
                "requirement": "Agent must explain or otherwise make clear that the combined fees for the two medical changes total $175.",
                "evidence": "conversation",
            },
            {
                "id": "must_not_same_fee_both_routes",
                "kind": "must_not",
                "requirement": "Agent must not tell the user that both bookings have the same medical change fee despite the different route types.",
                "evidence": "conversation",
            },
        ],
        "_replay_trace": [
            {"name": "update_booking", "arguments": {"booking_id": a_id, "flight_id": alt_a.flight_id, "change_reason": "medical"}},
            {"name": "update_booking", "arguments": {"booking_id": b_id, "flight_id": alt_b.flight_id, "change_reason": "medical"}},
        ],
    }
    return [flight_a, alt_a, flight_b, alt_b], [booking_a, booking_b], task_data


def build_challenge_54():
    """Challenge 54: Medical on intl <=7d with YYZ (Canada = international).

    user_003 (Olivia, platinum) economy JFK->YYZ, $550, June 20 (<=7d, 5 days).
    Medical. Change to June 27.

    YYZ = international (Canada).
    Correct: intl <=7d = $200 base. Medical 50% = $100 fee.
    Common errors: domestic rate (thinks Canada=domestic), wrong tier, wrong discount.

    This combines the YYZ classification with the medical discount.
    """
    user_id = "user_003"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW

    flight = build_flight("AA", "JFK", "YYZ", "2026-06-20", "morning", economy_price=550, business_price=1375)
    booking = build_booking(user_id, flight, cabin_class="economy", booked_days_ago=14, now=now, has_insurance=True)
    alt = build_flight("AA", "JFK", "YYZ", "2026-06-27", "morning", economy_price=580, business_price=1450)

    booking_id = booking.booking_id
    task_data = {
        "task_id": "challenge_medical_yyze_intl_lt7d",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            f"Medical procedure requires me to change {booking_id} to Toronto on June 27 in the same economy cabin. My user ID is {user_id}."
        ),
        "user_simulator": {
            "personality": "Matter-of-fact and single-purpose.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"Booking: {booking_id} (JFK to YYZ, June 20)",
                "Medical",
                "Original booking cabin is economy",
                f"For this task, change to {alt.flight_id} in the existing economy cabin only",
            ],
            "unknown_info": ["Fee", "That YYZ is international"],
            "task_rules": [
                f"Open with: medical, change {booking_id} to June 27 in the same economy cabin.",
                "If the agent asks about cabin, say 'Keep me in my current economy cabin.'",
                "Never ask for business class or any cabin upgrade.",
                f"If the agent offers multiple June 27 options, choose {alt.flight_id} in the existing economy cabin only.",
                "Accept the quoted fee and fare difference and end with [TASK_DONE].",
            ],
        },
        "_replay_trace": [
            {"name": "update_booking", "arguments": {"booking_id": booking_id, "flight_id": alt.flight_id, "change_reason": "medical"}},
        ],
    }
    return [flight, alt], [booking], task_data


def build_challenge_55():
    """Challenge 55: Mixed strategy with shared cash budget and points depletion.

    One booking is basic economy with insurance, so it must use cancel+rebook.
    The other is business with no insurance, so direct change is cheaper.
    The user only has $120 total cash and 15,000 points, so the agent must
    allocate points to the cancel+rebook leg and avoid applying one strategy to both.
    """
    user_id = "user_004"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW

    # Booking A: basic economy + insurance -> cannot change, but can cancel free.
    flight_a = build_flight("WN", "LAX", "DFW", "2026-06-20", "morning", economy_price=250, business_price=625)
    flight_a.cabin_prices["basic_economy"] = 175
    booking_a = build_booking(
        user_id,
        flight_a,
        cabin_class="basic_economy",
        booked_days_ago=5,
        now=now,
        has_insurance=True,
    )
    alt_a_nonstop = build_flight(
        "DL", "LAX", "DFW", "2026-06-23", "morning", economy_price=280, business_price=700, stops=0
    )
    alt_a_target = build_flight(
        "AS", "LAX", "DFW", "2026-06-23", "afternoon", economy_price=240, business_price=600, stops=1
    )

    # Booking B: business, no insurance -> direct change is cheaper than cancel+rebook.
    flight_b = build_flight("UA", "SFO", "SEA", "2026-06-21", "morning", economy_price=260, business_price=600)
    booking_b = build_booking(
        user_id,
        flight_b,
        cabin_class="business",
        booked_days_ago=10,
        now=now,
        has_insurance=False,
    )
    alt_b_target = build_flight("UA", "SFO", "SEA", "2026-06-24", "afternoon", economy_price=280, business_price=630)
    alt_b_distractor = build_flight("AA", "SFO", "SEA", "2026-06-24", "afternoon", economy_price=250, business_price=680)

    a_id = booking_a.booking_id
    b_id = booking_b.booking_id
    task_data = {
        "task_id": "challenge_mixed_strategy_shared_budget",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            f"I need to move two trips and I only have about $120 cash total to spend. Booking {a_id} needs to move from June 20 to June 23, "
            f"and booking {b_id} needs to move from June 21 to June 24. One of them has insurance, and I also have some points. What's the cheapest valid way to handle both?"
        ),
        "user_simulator": {
            "personality": "Careful with money. Wants the cheapest total valid plan before approving anything.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"{a_id}: LAX→DFW on June 20, basic economy, has insurance",
                f"{b_id}: SFO→SEA on June 21, business class, no insurance",
                "Needs June 23 for the Dallas trip and June 24 for the Seattle trip",
                "Has 15,000 loyalty points and only $120 cash total to spend",
                "No extra airline, seat, meal, WiFi, legroom, or insurance preferences matter beyond keeping the persisted booking fields consistent",
            ],
            "unknown_info": [
                "Which booking should use points",
                "Whether cancel+rebook or direct change is cheaper for each booking",
                "Whether the total can be kept within $120",
            ],
            "task_rules": [
                "Open by asking for the cheapest valid total plan across both bookings before making any changes.",
                "Do not proactively mention the policy mechanics. Make the agent discover them.",
                "If the agent starts executing changes before comparing both bookings, stop them and ask for the full math first.",
                "If the agent proposes the same strategy for both bookings, ask: 'Are you sure both bookings should use the same approach? One has insurance and one is business class.'",
                f"If the agent presents June 23 Dallas options, reject the $280 nonstop and accept {alt_a_target.flight_id} only if they explain it is the only option that keeps total cash within $120.",
                f"If the agent presents June 24 Seattle options, accept changing {b_id} to {alt_b_target.flight_id} once they explain that direct change is cheaper than cancel+rebook.",
                "Once the agent explains the mixed strategy total is $120, say 'That works. Go ahead with the cheapest valid option for each booking.'",
                "After both actions are completed, end with [TASK_DONE].",
            ],
        },
        "_replay_trace": [
            {"name": "cancel_booking", "arguments": {"booking_id": a_id, "confirm": True}},
            {
                "name": "create_booking",
                "arguments": {
                    "user_id": user_id,
                    "flight_id": alt_a_target.flight_id,
                    "cabin_class": "economy",
                    "seat_type": _USERS_BY_ID[user_id].preferences["seat_type"],
                    "meal_preference": _USERS_BY_ID[user_id].preferences["meal_preference"],
                    "add_wifi": _USERS_BY_ID[user_id].preferences["add_wifi"],
                    "add_extra_legroom": _USERS_BY_ID[user_id].preferences["add_extra_legroom"],
                    "add_insurance": _USERS_BY_ID[user_id].preferences["add_insurance"],
                    "payment_method": "points_plus_cash",
                    "points_used": 15000,
                    "cash_amount": 90,
                },
            },
            {
                "name": "update_booking",
                "arguments": {
                    "booking_id": b_id,
                    "flight_id": alt_b_target.flight_id,
                    "change_reason": "personal",
                },
            },
        ],
    }
    return [flight_a, alt_a_nonstop, alt_a_target, flight_b, alt_b_target, alt_b_distractor], [booking_a, booking_b], task_data


def _make_challenge_scenario(prefix: str, builder):
    """Create a scenario function that wraps a challenge builder."""

    def scenario() -> tuple[list[Flight], list[Booking], dict]:
        flights, bookings, task_data = builder()
        return flights, bookings, task_data

    scenario.__name__ = f"scenario_C{int(prefix) - 50:02d}"
    return scenario


scenario_C47 = _make_challenge_scenario('97', build_challenge_51)
scenario_C48 = _make_challenge_scenario('98', build_challenge_52)
scenario_C49 = _make_challenge_scenario('99', build_challenge_53)
scenario_C50 = _make_challenge_scenario('100', build_challenge_54)
scenario_C51 = _make_challenge_scenario('101', build_challenge_55)


SCENARIOS = [
    scenario_C47,
    scenario_C48,
    scenario_C49,
    scenario_C50,
    scenario_C51,
]
