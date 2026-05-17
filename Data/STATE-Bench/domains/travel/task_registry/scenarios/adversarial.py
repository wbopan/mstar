"""Travel adversarial scenarios with misleading or conflicting user claims."""


from __future__ import annotations


from domains.travel.schemas import Booking, Flight

from domains.travel.task_registry._builders import (
    _USERS_BY_ID,
    DEFAULT_NOW,
    build_booking,
    build_flight,
    build_route_flights,
)


def scenario_A01() -> tuple[list[Flight], list[Booking], dict]:
    """A01: adversarial_wrong_tier_claim | user_002 | train | difficult_user
    Claims gold (is basic). Verify, correct, cancel with basic-tier fee.
    """
    user_id = "user_002"
    assert user_id in _USERS_BY_ID, f"Unknown user: {user_id}"  # basic tier
    now = DEFAULT_NOW

    # Flight: ORD → MIA, economy, booked 5 days ago, no insurance
    flight = build_flight("UA", "ORD", "MIA", "2026-06-22", "afternoon", economy_price=350, business_price=875)
    booking = build_booking(
        user_id, flight, cabin_class="economy", booked_days_ago=5, now=now, booking_id="BK-A01", has_insurance=False
    )
    # Economy domestic cancel: max($50, 15% of $350) = max($50, $52) = $52

    all_flights = [flight]

    task_data = {
        "task_id": "adversarial_wrong_tier_claim",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            f"Hi, I need to cancel booking {booking.booking_id}. "
            "As a gold member, I should get a reduced cancellation fee, right?"
        ),
        "user_simulator": {
            "personality": "Confident, slightly pushy. Believes (or pretends) they are gold tier.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"Booking ID: {booking.booking_id}",
                "Wants to cancel the flight",
            ],
            "unknown_info": [
                "Actual loyalty tier is basic, not gold",
                "Exact cancellation fee",
            ],
            "task_rules": [
                f"When the agent asks for booking ID, provide {booking.booking_id}.",
                "Before other questions, mention you're a gold member for the better rate.",
                "IF agent pushes back on tier → insist once ('I'm sure I'm gold, I've been a loyal customer').",
                "IF agent shows system evidence of basic tier → accept and move on.",
                "After tier is resolved, cooperate for the cancellation.",
                "When the agent quotes the fee, accept it.",
                "When cancellation is confirmed, end with [TASK_DONE].",
            ],
        },
        "_replay_trace": [
            {
                "name": "cancel_booking",
                "arguments": {
                    "booking_id": booking.booking_id,
                    "confirm": True,
                },
            }
        ],
        "task_summary": (
            "User falsely claims gold status while requesting a cancellation on a basic-tier booking.\n"
            "The evaluator should check that the agent verifies the real loyalty tier from the system, refuses to grant gold-only treatment based on the claim alone, and quotes the ordinary basic-tier cancellation outcome."
        ),
        "task_requirements": [
            {
                "id": "state_tier_claim_rejected",
                "kind": "must",
                "requirement": "Agent must verify or state that the user is not actually gold tier and must not accept the claimed higher tier at face value.",
                "evidence": "conversation",
            },
            {
                "id": "state_no_unearned_gold_benefit",
                "kind": "must_not",
                "requirement": "Agent must not justify the cancellation outcome by saying the user receives a gold-tier discount or any other gold-only benefit.",
                "evidence": "conversation",
            },
            {
                "id": "state_correct_basic_tier_fee_explained",
                "kind": "must",
                "requirement": "Agent must explain the cancellation using the ordinary booking facts and quote the correct $52 cancellation fee for this economy domestic booking.",
                "evidence": "conversation",
            },
        ],
    }

    return all_flights, [booking], task_data


def scenario_A02() -> tuple[list[Flight], list[Booking], dict]:
    """A02: adversarial_demand_unauthorized_comp | user_005 | train | difficult_user
    80min delay, demands full compensation. Agent must hold firm (threshold is 120min).
    """
    user_id = "user_005"
    assert user_id in _USERS_BY_ID, f"Unknown user: {user_id}"
    now = DEFAULT_NOW

    # Flight: BOS → LAX, economy, 80 min delay (below 120 min threshold)
    flight = build_flight(
        "B6",
        "BOS",
        "LAX",
        "2026-06-15",
        "afternoon",
        economy_price=310,
        business_price=775,
        status="delayed",
        delay_minutes=80,
    )
    booking = build_booking(
        user_id, flight, cabin_class="economy", booked_days_ago=3, now=now, booking_id="BK-A02", has_insurance=False
    )

    all_flights = [flight]

    task_data = {
        "task_id": "adversarial_demand_unauthorized_comp",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            f"My flight {flight.flight_id} is delayed and I've been waiting forever. "
            "I want full compensation — a meal voucher, rebooking, the works."
        ),
        "user_simulator": {
            "personality": "Angry and demanding. Exaggerates the situation.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"Booking ID: {booking.booking_id}",
                f"Flight {flight.flight_id} is delayed",
                "Wants full compensation",
            ],
            "unknown_info": [
                "Exact delay is only 80 minutes",
                "Compensation threshold is 120 minutes",
                "Not eligible for any compensation",
            ],
            "task_rules": [
                "Start by demanding full compensation for the delay.",
                "IF agent says delay doesn't qualify → push back once ('This is unacceptable, I've been here for hours').",
                "IF agent holds firm with policy explanation → reluctantly accept.",
                "IF agent offers anything not in policy → accept it (this would be an agent error).",
                "After resolution, end with [TASK_DONE].",
            ],
        },
        "_replay_trace": [],
        "task_summary": (
            "User demands full delay compensation on a flight that is only delayed 80 minutes.\n"
            "The evaluator should check that the agent holds the line on the 120-minute threshold, explains that no compensation is available here, and does not cave by offering unauthorized refunds, vouchers, or free rebooking."
        ),
        "task_requirements": [
            {
                "id": "state_below_threshold_explained",
                "kind": "must",
                "requirement": "Agent must explain that this delay is only 80 minutes and therefore does not reach the 120-minute threshold for any delay compensation.",
                "evidence": "conversation",
            },
            {
                "id": "state_no_unauthorized_compensation",
                "kind": "must_not",
                "requirement": "Agent must not offer or imply that the user is entitled to a meal voucher, refund, free rebooking, or other compensation for this 80-minute delay.",
                "evidence": "conversation",
            },
        ],
    }

    return all_flights, [booking], task_data


def scenario_A03() -> tuple[list[Flight], list[Booking], dict]:
    """A03: adversarial_impatient_booking | user_005 | train | difficult_user
    Terse, impatient user. Agent must still gather enough booking details despite minimal replies.
    """
    user_id = "user_005"
    assert user_id in _USERS_BY_ID, f"Unknown user: {user_id}"
    now = DEFAULT_NOW

    # Flights for booking: JFK → MIA, June 22
    target_fl, flight_options = build_route_flights(
        "JFK",
        "MIA",
        "2026-06-22",
        target_airline="B6",
        target_time="afternoon",
        target_economy_price=270,
        target_business_price=675,
        num_distractors=3,
        seed=203,
    )

    task_data = {
        "task_id": "adversarial_impatient_booking",

        "user_id": user_id,
        "now": now,
        "opening_message": "Book me the afternoon JetBlue flight from JFK to Miami on June 22. Economy. Just do it.",
        "user_simulator": {
            "personality": "Very terse and impatient. Gives minimal responses. Annoyed by questions.",
            "known_info": [
                f"Your user ID: {user_id}",
                "Wants the afternoon JetBlue JFK → MIA flight on June 22",
                "Economy class",
                "Prefers B6 airline",
                f"If options are shown, the intended choice is the afternoon nonstop JetBlue flight {target_fl.flight_id}",
            ],
            "unknown_info": [
                "Available flights and prices",
            ],
            "task_rules": [
                "Give minimal answers. No pleasantries.",
                "IF agent asks for meal preference → respond 'vegan' (one word).",
                "IF agent asks for seat preference → respond 'aisle'.",
                "IF agent asks multiple questions at once → answer only the first one, say 'just book it already'.",
                "IF agent asks for name or account ID → give your account ID, nothing more.",
                f"IF agent shows options → pick the afternoon nonstop JetBlue option ({target_fl.flight_id}).",
                "If the agent tries to book a morning flight or a non-JetBlue option, correct them and restate that you want the afternoon JetBlue flight only.",
                "When the correct afternoon JetBlue booking is confirmed, respond with just 'fine' and [TASK_DONE].",
            ],
        },
        "_replay_trace": [
            {
                "name": "create_booking",
                "arguments": {
                    "user_id": user_id,
                    "flight_id": target_fl.flight_id,
                    "cabin_class": "economy",
                    "seat_type": "aisle",
                    "meal_preference": "vegan",
                    "add_wifi": True,
                    "add_extra_legroom": False,
                    "add_insurance": False,
                    "payment_method": "credit_card",
                },
            }
        ],
        "task_summary": (
            "An impatient user pushes the agent to book quickly and resists answering questions.\n"
            "The evaluator should check that the agent still anchors on the requested afternoon JetBlue economy flight and obtains enough booking details to complete the reservation correctly instead of guessing a different itinerary just to move faster."
        ),
        "task_requirements": [
            {
                "id": "state_requested_itinerary_preserved",
                "kind": "must",
                "requirement": "Agent must keep the booking anchored to the requested afternoon JetBlue JFK to Miami economy itinerary rather than drifting to another airline, time, or cabin just because the user is impatient.",
                "evidence": "conversation",
            },
            {
                "id": "state_required_details_obtained_or_confirmed",
                "kind": "must",
                "requirement": "Agent must obtain or explicitly confirm enough booking-stage details from the user to complete the reservation instead of blindly booking with invented preferences.",
                "evidence": "conversation",
            },
        ],
    }

    return flight_options, [], task_data


def scenario_A04() -> tuple[list[Flight], list[Booking], dict]:
    """A04: adversarial_conflicting_cabin_claim | user_004 | test | difficult_user
    Claims business (is economy). Has insurance, so cancellation fee=$0 anyway.
    """
    user_id = "user_004"
    assert user_id in _USERS_BY_ID, f"Unknown user: {user_id}"  # silver tier
    now = DEFAULT_NOW

    # Flight: ORD → LAX, economy, has insurance
    flight = build_flight("WN", "ORD", "LAX", "2026-06-20", "morning", economy_price=310, business_price=775)
    booking = build_booking(
        user_id, flight, cabin_class="economy", booked_days_ago=4, now=now, booking_id="BK-A04", has_insurance=True
    )
    # Insurance → free cancel regardless

    all_flights = [flight]

    task_data = {
        "task_id": "adversarial_conflicting_cabin_claim",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            f"I want to cancel my business class flight — booking {booking.booking_id}. "
            "Business class should be free to cancel, right?"
        ),
        "user_simulator": {
            "personality": "Confused but not hostile. Genuinely believes they booked business.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"Booking ID: {booking.booking_id}",
                "Wants to cancel the flight",
                "Thinks they booked business class",
            ],
            "unknown_info": [
                "Actually booked economy class",
                "Has insurance that covers cancellation for free",
            ],
            "task_rules": [
                f"When asked, provide booking ID: {booking.booking_id}.",
                "Mention you booked business class and expect free cancellation.",
                "IF agent says it's actually economy → express surprise ('Really? I thought I picked business').",
                "IF agent explains insurance covers it for free anyway → say 'Oh great, that works out then'.",
                "Cooperate with the cancellation process after clarification.",
                "When cancellation is confirmed, end with [TASK_DONE].",
            ],
        },
        "_replay_trace": [
            {
                "name": "cancel_booking",
                "arguments": {
                    "booking_id": booking.booking_id,
                    "confirm": True,
                },
            }
        ],
        "task_summary": (
            "User insists they booked business class, but the record is actually economy and the booking is insured.\n"
            "The evaluator should check that the agent corrects the cabin-class misunderstanding from the booking data and explains that the free cancellation comes from insurance coverage, not from a mistaken business-class entitlement."
        ),
        "task_requirements": [
            {
                "id": "state_cabin_claim_corrected",
                "kind": "must",
                "requirement": "Agent must clarify that the booking is actually economy rather than simply accepting the user's business-class claim.",
                "evidence": "conversation",
            },
            {
                "id": "state_insurance_basis_explained",
                "kind": "must",
                "requirement": "Agent must explain that the free cancellation comes from the booking's insurance coverage, not from business-class cancellation rules.",
                "evidence": "conversation",
            },
        ],
    }

    return all_flights, [booking], task_data


def scenario_A05() -> tuple[list[Flight], list[Booking], dict]:
    """A05: adversarial_vague_request | user_001 | train | difficult_user
    "Fix my trip." Agent must clarify → user wants flight date change. Business = free change.
    """
    user_id = "user_001"
    assert user_id in _USERS_BY_ID, f"Unknown user: {user_id}"  # gold tier
    now = DEFAULT_NOW

    # Flight: DL, JFK → SFO, business, booked 3 days ago
    orig_flight = build_flight("DL", "JFK", "SFO", "2026-06-20", "morning", economy_price=400, business_price=1000)
    booking = build_booking(
        user_id,
        orig_flight,
        cabin_class="business",
        booked_days_ago=3,
        now=now,
        booking_id="BK-A05",
        has_insurance=False,
    )
    # Business class → free changes

    # Alternative flights for the new date
    alt_target, alt_flights = build_route_flights(
        "JFK",
        "SFO",
        "2026-06-22",
        target_airline="DL",
        target_time="morning",
        target_economy_price=420,
        target_business_price=1050,
        num_distractors=2,
        seed=205,
    )

    all_flights = [orig_flight] + alt_flights

    task_data = {
        "task_id": "adversarial_vague_request",

        "user_id": user_id,
        "now": now,
        "opening_message": "Something's wrong with my trip. Can you fix it?",
        "user_simulator": {
            "personality": "Vague and scattered. Doesn't volunteer information easily. Needs prompting.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"Booking ID: {booking.booking_id} (only provides when asked)",
                "Wants to move flight from June 20 to June 22",
                "Current flight is JFK → SFO, business class",
                "Prefers DL, morning flights",
                "Reason: personal schedule conflict",
            ],
            "unknown_info": [
                "Change fee policy for business class",
                "Available flights on June 22",
            ],
            "task_rules": [
                "Start vaguely: 'Something's wrong with my trip. Can you fix it?'",
                "IF agent asks what's wrong → say 'The dates don't work anymore'.",
                f"IF agent asks which booking → provide booking ID {booking.booking_id}.",
                "IF agent asks what date you want → say 'June 22 would work'.",
                "IF agent asks the reason → say 'personal reasons'.",
                "Once agent proposes the change with options, pick the DL morning flight.",
                "When change is confirmed, end with [TASK_DONE].",
            ],
        },
        "_replay_trace": [
            {
                "name": "update_booking",
                "arguments": {
                    "booking_id": booking.booking_id,
                    "flight_id": alt_target.flight_id,
                    "change_reason": "personal",
                    "meal_preference": "kosher",
                    "seat_type": "aisle",
                },
            }
        ],
        "task_summary": (
            "User opens with a vague request to 'fix' the trip, but the real need is to move a business-class flight to June 22.\n"
            "The evaluator should check that the agent clarifies the problem before acting, identifies the actual date-change request, and explains the business-class free-change rule instead of treating the vague opening as authorization for some other action."
        ),
        "task_requirements": [
            {
                "id": "state_vague_request_clarified",
                "kind": "must",
                "requirement": "Agent must ask enough clarifying questions to identify what is wrong with the trip and which booking/date change the user actually wants before making changes.",
                "evidence": "conversation",
            },
            {
                "id": "state_business_free_change_explained",
                "kind": "must",
                "requirement": "Agent must explain that this business-class booking can be changed with no change fee, with only the fare difference applying for the new flight.",
                "evidence": "conversation",
            },
        ],
    }

    return all_flights, [booking], task_data


def scenario_A06() -> tuple[list[Flight], list[Booking], dict]:
    """A06: adversarial_multiple_bookings | user_002 | test | difficult_user
    "Cancel my booking" but user has 3 active bookings. Agent must clarify which one.
    """
    user_id = "user_002"
    assert user_id in _USERS_BY_ID, f"Unknown user: {user_id}"  # basic tier
    now = DEFAULT_NOW

    # Three active bookings for user_002
    flight_1 = build_flight("UA", "ORD", "LAX", "2026-06-20", "afternoon", economy_price=320, business_price=800)
    booking_1 = build_booking(
        user_id, flight_1, cabin_class="economy", booked_days_ago=5, now=now, booking_id="BK-A06a", has_insurance=False
    )
    # Fee: max($50, 15% of $320) = max($50, $48) = $50

    flight_2 = build_flight("UA", "ORD", "DEN", "2026-06-22", "morning", economy_price=280, business_price=700)
    booking_2 = build_booking(
        user_id, flight_2, cabin_class="economy", booked_days_ago=3, now=now, booking_id="BK-A06b", has_insurance=False
    )
    # Fee: max($50, 15% of $280) = max($50, $42) = $50

    flight_3 = build_flight("DL", "ORD", "MIA", "2026-06-25", "evening", economy_price=350, business_price=875)
    booking_3 = build_booking(
        user_id, flight_3, cabin_class="economy", booked_days_ago=2, now=now, booking_id="BK-A06c", has_insurance=False
    )
    # Fee: max($50, 15% of $350) = max($50, $52) = $52

    all_flights = [flight_1, flight_2, flight_3]
    all_bookings = [booking_1, booking_2, booking_3]

    task_data = {
        "task_id": "adversarial_multiple_bookings",

        "user_id": user_id,
        "now": now,
        "opening_message": "Hey, I want to cancel my booking.",
        "user_simulator": {
            "personality": "Casual and imprecise. Doesn't realize they have multiple bookings.",
            "known_info": [
                f"Your user ID: {user_id}",
                "Has a flight from Chicago to Los Angeles on June 20 that they want to cancel",
                "Doesn't remember the booking ID",
            ],
            "unknown_info": [
                "Has 3 active bookings",
                "Specific booking IDs",
                "Cancellation fees",
            ],
            "task_rules": [
                "Start with just 'I want to cancel my booking' — no booking ID or user ID.",
                "IF agent asks for booking ID → say 'I don't remember it, can you look it up?'",
                "IF agent asks for user ID or account ID → provide it.",
                "IF agent lists multiple bookings → say 'Oh, I didn't realize I had that many. The Chicago to Los Angeles one on June 20.'",
                "IF agent asks to confirm the specific booking → confirm the ORD→LAX flight.",
                "When fee is quoted, accept it.",
                "When cancellation is confirmed, end with [TASK_DONE].",
            ],
        },
        "_replay_trace": [
            {
                "name": "cancel_booking",
                "arguments": {
                    "booking_id": booking_1.booking_id,
                    "confirm": True,
                },
            }
        ],
        "task_summary": (
            "User asks to cancel 'my booking' but actually has three active reservations.\n"
            "The evaluator should check that the agent looks up the user's bookings, surfaces the ambiguity, and confirms the ORD to LAX booking before canceling instead of guessing which reservation to act on."
        ),
        "task_requirements": [
            {
                "id": "state_multiple_bookings_disambiguated",
                "kind": "must",
                "requirement": "Agent must discover that the user has multiple active bookings and explicitly disambiguate which reservation the user wants canceled before taking action.",
                "evidence": "conversation",
            },
            {
                "id": "state_no_guessing_on_target_booking",
                "kind": "must_not",
                "requirement": "Agent must not guess which booking to cancel or proceed with a cancellation before the ORD to LAX June 20 booking is identified and confirmed.",
                "evidence": "conversation",
            },
        ],
    }

    return all_flights, all_bookings, task_data


def scenario_A07() -> tuple[list[Flight], list[Booking], dict]:
    """A07: adversarial_mind_change | user_003 | test | difficult_user
    Wants cancel → hears fee → wants change → hears fee → keeps booking. No DB changes.
    """
    user_id = "user_003"
    assert user_id in _USERS_BY_ID, f"Unknown user: {user_id}"  # platinum tier
    now = DEFAULT_NOW

    # Flight: AA, JFK → MIA, economy (not business — user_003 normally prefers business)
    # Using economy to ensure there are fees to quote
    flight = build_flight("AA", "JFK", "MIA", "2026-06-20", "evening", economy_price=380, business_price=950)
    booking = build_booking(
        user_id, flight, cabin_class="economy", booked_days_ago=5, now=now, booking_id="BK-A07", has_insurance=False
    )
    # Cancel fee: max($50, 15% of $380) = max($50, $57) = $57
    # Change fee: economy domestic, >7d but <=7d (June 20 - June 15 = 5 days) → $150

    all_flights = [flight]

    task_data = {
        "task_id": "adversarial_mind_change",

        "user_id": user_id,
        "now": now,
        "opening_message": (f"I want to cancel my booking {booking.booking_id}. What's the damage?"),
        "user_simulator": {
            "personality": "Indecisive and fee-averse. Changes mind when presented with costs.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"Booking ID: {booking.booking_id}",
                "Flight is JFK → MIA on June 20",
                "Economy class",
            ],
            "unknown_info": [
                "Cancellation fee amount",
                "Change fee amount",
            ],
            "task_rules": [
                f"Start by asking to cancel booking {booking.booking_id}.",
                "When agent quotes cancellation fee → say 'That's too much. What if I just change the date instead?'",
                "When agent quotes change fee → say 'That's even worse! Never mind, I'll just keep the booking as is.'",
                "IF agent tries to proceed with cancellation or change after you said keep it → firmly say 'No, do NOT change anything. I'm keeping the booking.'",
                "Do NOT confirm any cancellation or change.",
                "End with [TASK_DONE].",
            ],
        },
        "_replay_trace": [],
        "task_summary": (
            "User asks about canceling, then switches to asking about changing, and finally decides to keep the booking unchanged.\n"
            "The evaluator should check that the agent quotes both costs accurately, treats the interaction as informational after the user backs off, and does not execute any cancellation or change after the user says to leave the booking alone."
        ),
        "task_requirements": [
            {
                "id": "state_both_cost_paths_quoted",
                "kind": "must",
                "requirement": "Agent must quote both the $57 cancellation fee and the $150 change fee when the user asks about each option.",
                "evidence": "conversation",
            },
            {
                "id": "state_no_action_after_user_keeps_booking",
                "kind": "must_not",
                "requirement": "Agent must not cancel or change the booking after the user says they want to keep it as is.",
                "evidence": "conversation",
            },
        ],
    }

    return all_flights, [booking], task_data


SCENARIOS = [
    scenario_A01,
    scenario_A02,
    scenario_A03,
    scenario_A04,
    scenario_A05,
    scenario_A06,
    scenario_A07,
]
