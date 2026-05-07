"""Travel scenarios focused on direct flight-change flows."""


from __future__ import annotations



from domains.travel.schemas import Booking, Flight

from domains.travel.task_registry._builders import (
    _USERS_BY_ID,
    DEFAULT_NOW,
    build_booking,
    build_flight,
    build_route_flights,
)


def scenario_P13() -> tuple[list[Flight], list[Booking], dict]:
    """P13: change_flight_personal — Economy domestic, personal reason, ≤7d = $150 fee."""
    now = DEFAULT_NOW
    user_id = "user_004"
    assert user_id in _USERS_BY_ID, f"Unknown user: {user_id}"

    # Original flight: June 20, 5 days from now (≤7 days) -> base_fee = $150
    original_flight = build_flight(
        airline_code="WN",
        origin="DEN",
        destination="ORD",
        date="2026-06-20",
        time_range="morning",
        economy_price=350,
        business_price=850,
    )
    booking = build_booking(
        user_id=user_id,
        flight=original_flight,
        cabin_class="economy",
        booked_days_ago=5,
        now=now,
        has_insurance=True,  # Insurance does NOT waive change fees
    )
    booking_id = booking.booking_id

    # New flight options to change to (June 22)
    new_target, new_flights = build_route_flights(
        origin="DEN",
        destination="ORD",
        date="2026-06-22",
        target_airline="WN",
        target_time="morning",
        target_stops=0,
        target_economy_price=380,
        target_business_price=900,
        num_distractors=2,
        seed=713,
    )
    new_flight_id = new_target.flight_id

    # Change fee: economy domestic, personal, ≤7d = $150
    # Fare difference: $380 - $350 = $30

    task_data = {
        "task_id": "change_flight_personal",

        "user_id": user_id,
        "now": now,
        "opening_message": "I need to change my flight from Denver to Chicago to a different date.",
        "user_simulator": {
            "personality": "Cooperative and straightforward. Understands there may be fees.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"Booking ID: {booking_id}",
                "Current flight is DEN to ORD on June 20th, economy class",
                "Wants to change to June 22nd",
                "Reason for change is personal",
                "Original price paid: $350",
                "Has travel insurance on the booking",
            ],
            "unknown_info": [
                "Exact change fee amount",
                "Whether insurance covers change fees (it does not)",
                "Available flights on the new date",
            ],
            "task_rules": [
                "When the agent asks for your booking ID, provide it.",
                "When the agent asks the reason for the change, say it is personal.",
                "When the agent quotes the change fee, ask if insurance covers it.",
                "When the agent confirms insurance does not cover change fees, acknowledge and proceed.",
                "When the agent presents new flight options, pick the WN morning nonstop flight on June 22nd.",
                "When the agent confirms the change with fee and fare difference, agree.",
                "End with [TASK_DONE] when the change is confirmed.",
            ],
        },
        "_replay_trace": [
            {
                "name": "update_booking",
                "arguments": {
                    "booking_id": booking_id,
                    "flight_id": new_flight_id,
                    "change_reason": "personal",
                },
            }
        ],
        "task_summary": (
            "User changes a domestic economy booking for a personal reason within 7 days of departure and asks whether insurance helps.\n"
            "The evaluator should check that the agent keeps the request on the ordinary personal-change path, quotes the full $150 fee, and correctly explains that insurance does not waive change fees."
        ),
        "task_requirements": [
            {
                "id": "state_personal_fee_quote",
                "kind": "must",
                "requirement": "Agent must explain that the personal change fee for this booking is $150.",
                "evidence": "conversation",
            },
            {
                "id": "state_insurance_not_waiver",
                "kind": "must",
                "requirement": "Agent must explain that the booking's insurance does not waive or remove the change fee for this request.",
                "evidence": "conversation",
            },
            {
                "id": "state_not_discounted_fee",
                "kind": "must_not",
                "requirement": "Agent must not describe this personal domestic change as eligible for a medical, bereavement, or insurance-based fee waiver or discount.",
                "evidence": "conversation",
            },
        ],
    }
    return [original_flight] + new_flights, [booking], task_data


def scenario_P14() -> tuple[list[Flight], list[Booking], dict]:
    """P14: change_flight_medical — Economy domestic, medical reason, 50% discount = $75."""
    now = DEFAULT_NOW
    user_id = "user_002"
    assert user_id in _USERS_BY_ID, f"Unknown user: {user_id}"

    # Original flight: June 19, 4 days from now (≤7 days) -> base_fee = $150, medical = 50% = $75
    original_flight = build_flight(
        airline_code="UA",
        origin="ORD",
        destination="BOS",
        date="2026-06-19",
        time_range="afternoon",
        economy_price=320,
        business_price=800,
    )
    booking = build_booking(
        user_id=user_id,
        flight=original_flight,
        cabin_class="economy",
        booked_days_ago=4,
        now=now,
        has_insurance=False,
    )
    booking_id = booking.booking_id

    # New flight options (June 26)
    new_target, new_flights = build_route_flights(
        origin="ORD",
        destination="BOS",
        date="2026-06-26",
        target_airline="UA",
        target_time="afternoon",
        target_stops=0,
        target_economy_price=340,
        target_business_price=850,
        num_distractors=2,
        seed=714,
    )
    new_flight_id = new_target.flight_id

    # Change fee: economy domestic, medical, ≤7d -> base=$150, 50% discount = $75
    # Fare difference: $340 - $320 = $20

    task_data = {
        "task_id": "change_flight_medical",

        "user_id": user_id,
        "now": now,
        "opening_message": "I need to change my flight due to a medical issue. Can you help?",
        "user_simulator": {
            "personality": "Cooperative and forthcoming. Mentions the medical reason upfront.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"Booking ID: {booking_id}",
                "Current flight is ORD to BOS on June 19th, economy class",
                "Wants to change to June 26th",
                "Reason for change is medical",
                "Original price paid: $320",
            ],
            "unknown_info": [
                "Whether medical reason qualifies for a fee discount",
                "Exact discount percentage for medical changes",
                "Available flights on the new date",
            ],
            "task_rules": [
                "When the agent asks for your booking ID, provide it.",
                "When the agent asks the reason for the change, say it is medical.",
                "When the agent mentions a medical discount on the change fee, ask what the discounted fee is.",
                "When the agent quotes $75 (50% discount), confirm you want to proceed.",
                "When the agent presents new flight options, pick the UA afternoon nonstop on June 26th.",
                "When the agent confirms the change with fee and fare difference, agree.",
                "End with [TASK_DONE] when the flight change is confirmed.",
            ],
        },
        "_replay_trace": [
            {
                "name": "update_booking",
                "arguments": {
                    "booking_id": booking_id,
                    "flight_id": new_flight_id,
                    "change_reason": "medical",
                },
            }
        ],
        "task_summary": (
            "User changes a domestic economy booking for a medical reason and expects the medical fee discount to be applied.\n"
            "The evaluator should check that the agent explicitly keeps the request on the medical-discount path and explains the discounted $75 fee rather than drifting back to the ordinary $150 personal fee."
        ),
        "task_requirements": [
            {
                "id": "state_medical_discount_fee",
                "kind": "must",
                "requirement": "Agent must explain that the medical change fee for this booking is $75.",
                "evidence": "conversation",
            },
            {
                "id": "state_medical_reason_used",
                "kind": "must",
                "requirement": "Agent must clearly treat the final change as a medical change that receives the medical discount.",
                "evidence": "conversation",
            },
            {
                "id": "state_not_full_personal_fee",
                "kind": "must_not",
                "requirement": "Agent must not tell the user that the correct fee remains the full $150 personal-change fee once the medical reason is established.",
                "evidence": "conversation",
            },
        ],
    }
    return [original_flight] + new_flights, [booking], task_data


def scenario_P15() -> tuple[list[Flight], list[Booking], dict]:
    """P15: change_flight_bereavement — Economy intl, bereavement, >7d, 75% discount = $25."""
    now = DEFAULT_NOW
    user_id = "user_003"
    assert user_id in _USERS_BY_ID, f"Unknown user: {user_id}"

    # Original flight: June 28, 13 days from now (>7 days) -> base_fee = $100 (intl, >7d)
    # Bereavement = 75% discount -> fee = $100 * 0.25 = $25
    original_flight = build_flight(
        airline_code="AA",
        origin="JFK",
        destination="LHR",
        date="2026-06-28",
        time_range="evening",
        economy_price=520,
        business_price=1300,
    )
    booking = build_booking(
        user_id=user_id,
        flight=original_flight,
        cabin_class="economy",
        booked_days_ago=10,
        now=now,
        has_insurance=True,  # Insurance does NOT waive change fees
    )
    booking_id = booking.booking_id

    # New flight options (June 18, sooner due to bereavement urgency)
    new_target, new_flights = build_route_flights(
        origin="JFK",
        destination="LHR",
        date="2026-06-18",
        target_airline="AA",
        target_time="evening",
        target_stops=0,
        target_economy_price=550,
        target_business_price=1350,
        num_distractors=2,
        seed=715,
    )
    new_flight_id = new_target.flight_id

    # Change fee: economy intl, bereavement, >7d -> base=$100, 75% discount = $25
    # Fare difference: $550 - $520 = $30

    task_data = {
        "task_id": "change_flight_bereavement",

        "user_id": user_id,
        "now": now,
        "opening_message": "I need to move my London flight to an earlier date due to a family bereavement.",
        "user_simulator": {
            "personality": "Cooperative and somber. Mentions bereavement reason clearly but does not elaborate on personal details.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"Booking ID: {booking_id}",
                "Current flight is JFK to LHR on June 28th, economy class",
                f"For this task, keep the booking in economy and choose {new_flight_id}",
                "Wants to change to June 18th (sooner)",
                "Reason for change is bereavement",
                "Original price paid: $520",
                "Has travel insurance on the booking",
            ],
            "unknown_info": [
                "Whether bereavement qualifies for a fee discount",
                "Exact discount percentage for bereavement changes",
                "Available earlier flights",
            ],
            "task_rules": [
                "When the agent asks for your booking ID, provide it.",
                "When the agent asks the reason for the change, say bereavement.",
                "Keep the existing cabin class. Do not ask for a business-class upgrade or any cabin change.",
                "When the agent mentions a bereavement discount, ask what the discounted fee is.",
                f"When the agent presents new flight options, pick {new_flight_id}, the AA evening nonstop on June 18th, in economy.",
                "When the agent asks about insurance, note that you have it but do not insist it covers the fee.",
                "When the agent confirms the change with the $25 fee and fare difference, agree.",
                "End with [TASK_DONE] when the flight change is confirmed.",
            ],
        },
        "_replay_trace": [
            {
                "name": "update_booking",
                "arguments": {
                    "booking_id": booking_id,
                    "flight_id": new_flight_id,
                    "change_reason": "bereavement",
                },
            }
        ],
        "task_summary": (
            "User changes an international economy booking more than 7 days out because of bereavement and asks about the discounted fee.\n"
            "The evaluator should check that the agent applies the correct >7 day international base fee and then the bereavement discount, landing on the $25 fee without letting insurance or the wrong fee tier interfere."
        ),
        "task_requirements": [
            {
                "id": "state_bereavement_fee_quote",
                "kind": "must",
                "requirement": "Agent must explain that the bereavement change fee for this booking is $25.",
                "evidence": "conversation",
            },
            {
                "id": "state_bereavement_formula_basis",
                "kind": "must",
                "requirement": "Agent must make clear that the $25 comes from a bereavement discount applied to the more-than-7-days international base fee, not from insurance or the wrong fee tier.",
                "evidence": "conversation",
            },
            {
                "id": "state_not_wrong_bereavement_path",
                "kind": "must_not",
                "requirement": "Agent must not describe this request as an ordinary personal change or as one whose fee is waived by insurance.",
                "evidence": "conversation",
            },
        ],
    }
    return [original_flight] + new_flights, [booking], task_data


SCENARIOS = [
    scenario_P13,
    scenario_P14,
    scenario_P15,
]
