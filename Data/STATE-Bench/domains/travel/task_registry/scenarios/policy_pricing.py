"""Travel policy scenarios about pricing, fees, and upgrade constraints."""


from __future__ import annotations


from datetime import datetime, timedelta

from domains.travel.schemas import Booking, Flight

from domains.travel.task_registry._builders import (
    DEFAULT_NOW,
    build_booking,
    build_flight,
    build_route_flights,
)


def scenario_PR01() -> tuple[list[Flight], list[Booking], dict]:
    """PR01: Insurance covers cancellation, not changes. Suggest cancel+rebook workaround.

    user_003 (Olivia, platinum, has_insurance=True) has an economy domestic booking
    she wants to CHANGE. Insurance does NOT waive change fees. Agent should explain
    that insurance only covers cancellation, and suggest cancel (free via insurance)
    then rebook as a workaround.
    """
    now = DEFAULT_NOW
    user_id = "user_003"
    flight_date = "2026-06-22"

    # Current booked flight
    current_flight, all_flights = build_route_flights(
        origin="ORD",
        destination="LAX",
        date=flight_date,
        target_airline="AA",
        target_time="morning",
        target_economy_price=380,
        target_business_price=950,
        num_distractors=3,
        seed=5501,
    )

    # Alternative flight the user could rebook onto
    alt_flight = build_flight(
        airline_code="AA",
        origin="ORD",
        destination="LAX",
        date=flight_date,
        time_range="afternoon",
        economy_price=400,
        business_price=980,
    )
    all_flights.append(alt_flight)

    booking = build_booking(
        user_id="user_003",
        flight=current_flight,
        cabin_class="economy",
        booked_days_ago=5,
        now=now,
        booking_id="BK-PR01",
        has_insurance=True,
    )

    # Change fee for economy domestic >7 days out = $75
    # But insurance does NOT waive it. Cancel is free via insurance, then rebook.
    task_data = {
        "task_id": "policy_insurance_cancel_not_change",

        "user_id": "user_003",
        "now": now,
        "opening_message": (
            "Hi, I need to change my flight BK-PR01 to a later departure. "
            "I have travel insurance so that should cover any fees, right?"
        ),
        "user_simulator": {
            "personality": "Polite and detail-oriented. Expects insurance to cover everything.",
            "known_info": [
                f"Your user ID: {user_id}",
                "Booking ID is BK-PR01",
                "Current booking is economy class",
                "Has travel insurance on this booking",
                "Wants an afternoon flight on the same route and date",
                "This task is about understanding the policy, not actually changing, cancelling, or rebooking the booking",
            ],
            "unknown_info": [
                "Insurance only covers cancellation, not change fees",
                "The cancel+rebook workaround exists",
                "Change fee would be $150 for economy domestic (<=7 days)",
            ],
            "task_rules": [
                "Start by asking to change your flight, mentioning insurance should cover it.",
                "When the agent explains insurance doesn't cover changes, express surprise and ask what options you have.",
                "If the agent suggests cancel+rebook, ask for confirmation that insurance covers the cancellation fully.",
                "When the agent confirms the workaround, ask if there are afternoon flights available.",
                "Do not ask the agent to execute a cancellation, rebooking, or flight change. Keep the conversation at the policy/advice level only.",
                "Do not change cabin class, do not claim the current booking is business, and do not ask for add-ons.",
                "Once the policy distinction is clear and the workaround is explained, end with [TASK_DONE].",
            ],
        },
        "task_summary": "User wants to change an insured booking and assumes insurance should waive the change fee.\nThe evaluator should check that the agent explains insurance covers cancellation but not change fees, describes the cancel-and-rebook workaround, and does not execute any booking action in this policy-only task.",
        "task_requirements": [
            {
                "id": "state_insurance_not_change_fee",
                "kind": "must",
                "requirement": "Agent must explain that travel insurance covers cancellation but does not waive the fee for changing this booking.",
                "evidence": "conversation",
            },
            {
                "id": "state_cancel_rebook_workaround",
                "kind": "must",
                "requirement": "Agent must explain that a workable alternative is to cancel the current booking with insurance coverage and then rebook the preferred flight separately.",
                "evidence": "conversation",
            },
            {
                "id": "no_execution",
                "kind": "must_not",
                "requirement": "Agent must not execute a cancellation, rebooking, or flight change in this policy-only task.",
                "evidence": "conversation_or_tool_calls",
            },
        ],
        "_replay_trace": [],
    }

    return all_flights, [booking], task_data


def scenario_PR02() -> tuple[list[Flight], list[Booking], dict]:
    """PR02: Basic economy restrictions — changes, upgrades, cancel, AND baggage.

    user_002 (Liam, basic tier) has a basic_economy booking. Wants to change/upgrade
    AND wants to know about baggage and add-ons. Agent must synthesize restrictions
    from multiple policy domains: cancellation, change, upgrade, and baggage.
    """
    now = DEFAULT_NOW
    user_id = "user_002"
    flight_date = "2026-06-20"

    flight, all_flights = build_route_flights(
        origin="JFK",
        destination="MIA",
        date=flight_date,
        target_airline="UA",
        target_time="afternoon",
        target_economy_price=180,
        target_business_price=550,
        num_distractors=2,
        seed=5502,
    )
    # Basic economy price — set it manually in cabin_prices
    flight.cabin_prices["basic_economy"] = 120
    booking = build_booking(
        user_id="user_002",
        flight=flight,
        cabin_class="basic_economy",
        booked_days_ago=4,
        now=now,
        booking_id="BK-PR02",
    )

    # Baggage for basic tier + basic_economy: 0 base + 0 loyalty = 0 free, extra $50/bag

    task_data = {
        "task_id": "policy_basic_economy_restrictions",

        "user_id": "user_002",
        "now": now,
        "opening_message": (
            "I have booking BK-PR02 and I'd like to either change it to a different "
            "date or upgrade to business class. Also, how many bags can I check?"
        ),
        "user_simulator": {
            "personality": "Calm but hopeful. Budget-conscious traveler.",
            "known_info": [
                f"Your user ID: {user_id}",
                "Booking ID is BK-PR02",
                "Booked a cheap fare (basic economy)",
                "Is a basic tier loyalty member",
                "Wants to bring 2 checked bags on this trip",
            ],
            "unknown_info": [
                "Basic economy cannot be changed after 24h",
                "Basic economy cannot be upgraded",
                "Basic economy cannot be cancelled after 24h without insurance",
                "Basic economy gets 0 free checked bags",
                "Extra bags are $50 each for basic economy",
            ],
            "task_rules": [
                "Ask about changing or upgrading your booking AND about checked bags.",
                "When the agent says changes are blocked, ask if upgrading is possible instead.",
                "When the agent says upgrades are also blocked, ask about cancellation as a last resort.",
                "When the agent explains cancellation is also blocked, ask about checked baggage.",
                "When the agent says 0 free checked bags, ask how much extra bags cost.",
                "Express frustration that basic economy has so many restrictions.",
                "Ask if there is ANY way to get a better deal or more flexibility in general terms only.",
                "This is an information-only task. If the agent offers to search, book, cancel, or execute anything, say you only wanted the policy explained and do not want any action taken.",
                "End with [TASK_DONE] once all restrictions and baggage info have been explained.",
            ],
        },
        "task_summary": "User asks for a full explanation of what a basic economy booking does and does not allow.\nThe evaluator should check that the agent covers the core basic-economy restrictions on changes, upgrades, cancellation, and checked bags, and keeps the conversation informational only.",
        "task_requirements": [
            {
                "id": "state_no_changes_after_24h",
                "kind": "must",
                "requirement": "Agent must explain that this basic economy booking cannot be changed after the initial 24-hour window.",
                "evidence": "conversation",
            },
            {
                "id": "state_no_upgrades",
                "kind": "must",
                "requirement": "Agent must explain that this basic economy booking is not eligible for upgrades.",
                "evidence": "conversation",
            },
            {
                "id": "state_cancel_restriction",
                "kind": "must",
                "requirement": "Agent must explain that after the first 24 hours this basic economy booking cannot be cancelled without insurance coverage.",
                "evidence": "conversation",
            },
            {
                "id": "state_baggage_rules",
                "kind": "must",
                "requirement": "Agent must explain that this booking includes 0 free checked bags and that checked bags would cost $50 each.",
                "evidence": "conversation",
            },
            {
                "id": "no_execution",
                "kind": "must_not",
                "requirement": "Agent must not execute any booking action in this information-only policy task.",
                "evidence": "conversation_or_tool_calls",
            },
        ],
        "_replay_trace": [],
    }

    return all_flights, [booking], task_data


def scenario_PR03() -> tuple[list[Flight], list[Booking], dict]:
    """PR03: 24h vs 48h free cancellation window — domestic vs international.

    user_001 (Emma, gold) has TWO bookings made 30h ago: one domestic, one international.
    Domestic 24h window has expired; international 48h window is still active.
    Agent must correctly identify which can be cancelled for free.
    """
    now = DEFAULT_NOW
    user_id = "user_001"

    # Domestic flight (ORD -> LAX)
    domestic_flight = build_flight(
        airline_code="DL",
        origin="ORD",
        destination="LAX",
        date="2026-06-22",
        time_range="morning",
        economy_price=350,
        business_price=875,
    )

    # International flight (JFK -> LHR)
    intl_flight = build_flight(
        airline_code="DL",
        origin="JFK",
        destination="LHR",
        date="2026-06-25",
        time_range="evening",
        economy_price=650,
        business_price=1600,
    )

    # Both booked 30h ago
    domestic_booking = build_booking(
        user_id="user_001",
        flight=domestic_flight,
        cabin_class="economy",
        now=now,
        booking_id="BK-PR03A",
        has_insurance=False,
    )
    # Override booked_at to exactly 30h ago
    booked_at_30h = (datetime.fromisoformat(now) - timedelta(hours=30)).isoformat()
    domestic_booking.booked_at = booked_at_30h

    intl_booking = build_booking(
        user_id="user_001",
        flight=intl_flight,
        cabin_class="economy",
        now=now,
        booking_id="BK-PR03B",
        has_insurance=False,
    )
    intl_booking.booked_at = booked_at_30h

    # Domestic: 30h > 24h window → fee applies (economy domestic: max($50, 15% of $350) = $52)
    # International: 30h < 48h window → free cancellation

    task_data = {
        "task_id": "policy_24h_vs_48h_window",

        "user_id": "user_001",
        "now": now,
        "opening_message": (
            "I made two bookings yesterday — BK-PR03A for a domestic flight and "
            "BK-PR03B for an international flight. I'm thinking of cancelling both. "
            "Can you tell me the cancellation fees for each?"
        ),
        "user_simulator": {
            "personality": "Organized and likes clear comparisons. Asks for specifics.",
            "known_info": [
                f"Your user ID: {user_id}",
                "Booking IDs are BK-PR03A (domestic) and BK-PR03B (international)",
                "Both were booked yesterday (about 30 hours ago)",
                "Neither has insurance",
            ],
            "unknown_info": [
                "Domestic has 24h free window (expired)",
                "International has 48h free window (still active)",
                "Exact cancellation fees for each",
            ],
            "task_rules": [
                "Ask about cancellation fees for both bookings.",
                "When the agent provides the fees, ask why they are different.",
                "When the agent explains the 24h vs 48h windows, confirm understanding.",
                "Ask specifically if the international one can still be cancelled for free.",
                "When you have complete information on both, end with [TASK_DONE].",
            ],
        },
        "task_summary": "User asks to compare cancellation fees on one domestic booking and one international booking that were both made about 30 hours ago.\nThe evaluator should check that the agent applies the 24-hour domestic window and 48-hour international window correctly, including the exact fee result for each booking.",
        "task_requirements": [
            {
                "id": "state_domestic_fee",
                "kind": "must",
                "requirement": "Agent must explain that domestic booking BK-PR03A is past its 24-hour free-cancellation window and would incur a $52 cancellation fee.",
                "evidence": "conversation",
            },
            {
                "id": "state_international_free",
                "kind": "must",
                "requirement": "Agent must explain that international booking BK-PR03B is still within its 48-hour free-cancellation window and can be cancelled for free.",
                "evidence": "conversation",
            },
            {
                "id": "state_window_reasoning",
                "kind": "must",
                "requirement": "Agent must explain that the different answers come from domestic flights using a 24-hour free-cancellation window while international flights use a 48-hour window.",
                "evidence": "conversation",
            },
        ],
        "_replay_trace": [],
    }

    return [domestic_flight, intl_flight], [domestic_booking, intl_booking], task_data


def scenario_PR04() -> tuple[list[Flight], list[Booking], dict]:
    """PR04: 150min delay = $25 meal voucher only.

    user_005 (Ava, basic) has a flight delayed 150 minutes. Qualifies for meal
    voucher ($25) but NOT full compensation (needs 240+).
    """
    now = DEFAULT_NOW
    user_id = "user_005"

    flight, all_flights = build_route_flights(
        origin="SFO",
        destination="SEA",
        date="2026-06-15",
        target_airline="B6",
        target_time="afternoon",
        target_economy_price=280,
        target_business_price=700,
        target_status="delayed",
        target_delay=150,
        num_distractors=2,
        seed=5504,
    )

    booking = build_booking(
        user_id="user_005",
        flight=flight,
        cabin_class="economy",
        booked_days_ago=7,
        now=now,
        booking_id="BK-PR04",
        has_insurance=True,
    )

    task_data = {
        "task_id": "policy_delay_meal_voucher",

        "user_id": "user_005",
        "now": now,
        "opening_message": (
            "My flight BK-PR04 seems to be delayed. Can you check what's going on "
            "and what compensation I'm entitled to?"
        ),
        "user_simulator": {
            "personality": "Slightly anxious but cooperative. Wants clear answers.",
            "known_info": [
                f"Your user ID: {user_id}",
                "Booking ID is BK-PR04",
                "The flight appears to be delayed",
                "Has travel insurance on the booking",
            ],
            "unknown_info": [
                "The delay is exactly 150 minutes",
                "150 minutes qualifies for a $25 meal voucher only",
                "Rebooking and hotel require 240+ minutes",
                "Change fee for economy domestic",
                "Insurance doesn't cover change fees",
            ],
            "task_rules": [
                "When the agent asks for booking ID, provide it.",
                "When the agent reports the delay duration, ask what compensation you're entitled to.",
                "When the agent offers the meal voucher, accept it.",
                "Then ask: 'Given the delay, I'm also thinking about changing to a different flight. "
                "Does my insurance cover the change fee?'",
                "When the agent explains insurance doesn't cover changes, ask what it DOES cover.",
                "When the agent explains the cancel+rebook workaround, ask how much that would save.",
                "After understanding both the voucher and the cancel+rebook option, end with [TASK_DONE].",
            ],
        },
        "task_summary": "User first asks what compensation applies to a 150-minute delay, then asks whether insurance would waive the fee for changing away from that flight.\nThe evaluator should check that the agent distinguishes meal-voucher compensation from full delay compensation, explains that insurance still does not cover change fees, and surfaces the cancel-and-rebook workaround.",
        "task_requirements": [
            {
                "id": "state_meal_voucher_only",
                "kind": "must",
                "requirement": "Agent must explain that a 150-minute delay qualifies for the $25 meal-voucher tier and not the full delay-compensation package.",
                "evidence": "conversation",
            },
            {
                "id": "state_no_full_compensation",
                "kind": "must",
                "requirement": "Agent must make clear that full delay compensation such as free rebooking or hotel accommodation requires a delay of at least 240 minutes, so it does not apply here.",
                "evidence": "conversation",
            },
            {
                "id": "state_insurance_not_change_fee",
                "kind": "must",
                "requirement": "When the user asks about changing flights, the agent must explain that insurance does not waive the change fee for this booking.",
                "evidence": "conversation",
            },
            {
                "id": "state_cancel_rebook_workaround",
                "kind": "must",
                "requirement": "Agent must explain that the alternative way to avoid the change fee is to cancel under insurance coverage and rebook separately.",
                "evidence": "conversation",
            },
        ],
        "_replay_trace": [
            {
                "name": "update_booking",
                "arguments": {
                    "booking_id": "BK-PR04",
                    "delay_compensation": "meal_voucher",
                },
            }
        ],
    }

    return all_flights, [booking], task_data


def scenario_PR05() -> tuple[list[Flight], list[Booking], dict]:
    """PR05: 300min delay = full compensation (rebook + meal + hotel).

    user_001 (Emma, gold) has a flight delayed 300 minutes. Qualifies for
    full compensation: rebooking, $25 meal voucher, and hotel accommodation.
    """
    now = DEFAULT_NOW
    user_id = "user_001"

    flight, all_flights = build_route_flights(
        origin="DFW",
        destination="BOS",
        date="2026-06-15",
        target_airline="DL",
        target_time="morning",
        target_economy_price=420,
        target_business_price=1050,
        target_status="delayed",
        target_delay=300,
        num_distractors=3,
        seed=5505,
    )

    # Add alternative flights for rebooking
    alt_flight = build_flight(
        airline_code="DL",
        origin="DFW",
        destination="BOS",
        date="2026-06-15",
        time_range="evening",
        economy_price=450,
        business_price=1100,
    )
    all_flights.append(alt_flight)

    booking = build_booking(
        user_id="user_001",
        flight=flight,
        cabin_class="economy",
        booked_days_ago=10,
        now=now,
        booking_id="BK-PR05",
        has_insurance=False,
    )

    task_data = {
        "task_id": "policy_delay_full_compensation",

        "user_id": "user_001",
        "now": now,
        "opening_message": ("I just saw that my flight BK-PR05 is massively delayed! What can you do for me?"),
        "user_simulator": {
            "personality": "Frustrated but reasonable. Wants the agent to take initiative.",
            "known_info": [
                f"Your user ID: {user_id}",
                "Booking ID is BK-PR05",
                "The flight is significantly delayed",
                "For this task, make sure the full-compensation entitlement is applied to the existing booking",
            ],
            "unknown_info": [
                "The delay is exactly 300 minutes",
                "300 minutes qualifies for full compensation (rebook + meal + hotel)",
                "Alternative flights may be available",
            ],
            "task_rules": [
                "When the agent asks for booking ID, provide it.",
                "When the agent reports the delay duration, ask what compensation you're entitled to.",
                "When the agent offers full compensation (rebook + meal + hotel), ask for confirmation that the compensation has been applied to your existing booking.",
                "Do not authorize any rebooking, cabin upgrade, cancellation, or other booking change in this task.",
                "If the agent offers to switch flights, upgrade cabins, or otherwise modify the trip, say you only want the delay compensation applied to your current booking and no other changes.",
                "Once the full-compensation entitlement is clearly confirmed and applied to the existing booking, end with [TASK_DONE].",
            ],
        },
        "task_summary": "User reports a 300-minute delay and wants to know what compensation applies, but does not authorize any trip change.\nThe evaluator should check that the agent explains the full delay-compensation package triggered at 240 or more minutes and keeps the task focused on applying that entitlement to the current booking rather than executing other travel changes.",
        "task_requirements": [
            {
                "id": "state_full_comp_threshold",
                "kind": "must",
                "requirement": "Agent must explain that a 300-minute delay qualifies this booking for the full delay-compensation tier because it is at or above the 240-minute threshold.",
                "evidence": "conversation",
            },
            {
                "id": "state_full_comp_package",
                "kind": "must",
                "requirement": "Agent must explain that the full delay-compensation package includes free rebooking, a $25 meal voucher, and hotel accommodation if the delay requires an overnight stay.",
                "evidence": "conversation",
            },
            {
                "id": "no_other_booking_change",
                "kind": "must_not",
                "requirement": "Agent must not cancel, rebook, upgrade, or otherwise modify the itinerary beyond applying the delay-compensation entitlement to the current booking.",
                "evidence": "conversation_or_tool_calls",
            },
        ],
        "_replay_trace": [
            {
                "name": "update_booking",
                "arguments": {
                    "booking_id": "BK-PR05",
                    "delay_compensation": "full",
                },
            }
        ],
    }

    return all_flights, [booking], task_data


SCENARIOS = [
    scenario_PR01,
    scenario_PR02,
    scenario_PR03,
    scenario_PR04,
    scenario_PR05,
]
