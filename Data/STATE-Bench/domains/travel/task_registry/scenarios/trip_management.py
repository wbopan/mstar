"""Travel scenarios for multi-step reservation management."""


from __future__ import annotations


from domains.travel.schemas import Booking, Flight

from domains.travel.task_registry._builders import (
    _USERS_BY_ID,
    DEFAULT_NOW,
    build_booking,
    build_flight,
    build_hotel,
    build_route_flights,
)


def scenario_MS01() -> tuple[list[Flight], list[Booking], dict]:
    """MS01: cascade_cancel_rebook_domestic | user_004 | train | cancel_and_rebook

    Cancel domestic economy (has insurance → free cancel), rebook to Denver.
    But rebook flights within budget all violate preferences. Agent must
    also check if the refund from cancellation affects the budget for rebooking.
    Additionally, user has a hotel in Miami that needs cancelling too.
    """
    user_id = "user_004"
    user = _USERS_BY_ID[user_id]
    now = DEFAULT_NOW

    # Original flight: ORD → MIA, economy, user_004 has insurance
    orig_flight = build_flight("WN", "ORD", "MIA", "2026-06-20", "morning", economy_price=320, business_price=800)
    orig_booking = build_booking(
        user_id,
        orig_flight,
        cabin_class="economy",
        booked_days_ago=3,
        now=now,
        booking_id="BK-MS01",
        has_insurance=True,
    )

    # Hotel in Miami for the original trip
    hotel = build_hotel(
        user_id, "MIA", "2026-06-20", "2026-06-23", room_type="standard", nightly_rate=130, booked_days_ago=3, now=now
    )
    # Hotel: 48h+ before check-in → free cancel

    # Rebook destination: ORD → DEN — preferred morning WN is over budget
    rebook_over = build_flight(
        airline_code="WN",
        origin="ORD",
        destination="DEN",
        date="2026-06-22",
        time_range="morning",
        stops=0,
        economy_price=620,
        business_price=1550,
        flight_id="WN400",
    )

    # Within-budget options all violate prefs
    rebook_opt_a = build_flight(
        airline_code="UA",
        origin="ORD",
        destination="DEN",
        date="2026-06-22",
        time_range="morning",
        stops=0,
        economy_price=350,
        business_price=875,
        flight_id="UA400",
    )
    rebook_opt_b = build_flight(
        airline_code="WN",
        origin="ORD",
        destination="DEN",
        date="2026-06-22",
        time_range="afternoon",
        stops=1,
        economy_price=280,
        business_price=700,
        flight_id="WN401",
    )
    rebook_opt_c = build_flight(
        airline_code="DL",
        origin="ORD",
        destination="DEN",
        date="2026-06-22",
        time_range="evening",
        stops=0,
        economy_price=400,
        business_price=1000,
        flight_id="DL400",
    )

    all_flights = [orig_flight, rebook_over, rebook_opt_a, rebook_opt_b, rebook_opt_c]

    task_data = {
        "task_id": "cascade_cancel_rebook_domestic",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            f"Hi, I need to cancel my flight to Miami — booking {orig_booking.booking_id} — "
            "and then rebook a flight to Denver instead."
        ),
        "user_simulator": {
            "personality": "Friendly and cooperative. Provides information when asked.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"Flight booking ID: {orig_booking.booking_id}",
                "Has travel insurance on this booking",
                "Wants to fly ORD → DEN on June 22",
                "Prefers WN airline, morning, and nonstop options",
                f"Budget max: ${user.budget}",
                f"Hotel reservation: {hotel.reservation_id}",
                "Hotel in Miami, June 20-23",
            ],
            "unknown_info": [
                "Exact cancellation refund amount",
                "Available flights to Denver and their prices",
                "Hotel cancellation fee",
            ],
            "task_rules": [
                f"Start by asking to cancel booking {orig_booking.booking_id}.",
                "Do NOT proactively mention the hotel. Only bring it up if the agent asks about other reservations.",
                "When cancellation is confirmed, say you need to book a new flight to Denver on June 22.",
                "If the agent asks about other reservations, mention the hotel.",
                "If the agent does NOT ask, do not mention it.",
                "When the agent shows rebook options and the preferred WN morning nonstop is over budget, "
                "ask what's available within $600.",
                "Pick the WN afternoon 1-stop at $280 — keeping the airline is more important than time or stops.",
                "For the replacement Denver flight, do not add WiFi, extra legroom, or insurance.",
                "If the agent asks about seat or meal details, answer directly.",
                "If the agent books the replacement flight with any add-on, ask to remove it before accepting completion.",
                "When new booking is confirmed, end with [TASK_DONE].",
            ],
        },
        "_replay_trace": [
            {"name": "cancel_booking", "arguments": {"booking_id": orig_booking.booking_id, "confirm": True}},
            {
                "name": "cancel_hotel_reservation",
                "arguments": {"reservation_id": hotel.reservation_id, "confirm": True},
            },
            {
                "name": "create_booking",
                "arguments": {
                    "flight_id": rebook_opt_b.flight_id,
                    "user_id": user_id,
                    "cabin_class": "economy",
                    "seat_type": "window",
                    "payment_method": "credit_card",
                    "meal_preference": "standard",
                    "add_wifi": False,
                    "add_extra_legroom": False,
                    "add_insurance": False,
                },
            },
        ],
        "task_summary": (
            "User first needs an insured Miami flight canceled, then needs the hidden Miami hotel canceled too, and only after that wants a replacement Denver flight within budget.\n"
            "The evaluator should check that the agent proactively discovers the linked hotel, explains why the preferred WN morning nonstop replacement is over budget, and clearly presents the trade-off that leads the user to the cheaper WN one-stop afternoon rebooking."
        ),
        "task_requirements": [
            {
                "id": "state_hidden_hotel_discovered",
                "kind": "must",
                "requirement": f"Agent must proactively discover and handle the linked Miami hotel reservation {hotel.reservation_id} rather than waiting for the user to volunteer it.",
                "evidence": "conversation",
            },
            {
                "id": "state_over_budget_option_explained",
                "kind": "must",
                "requirement": f"Agent must explain that the preferred WN morning nonstop replacement {rebook_over.flight_id} is over the user's budget and present the within-budget alternatives.",
                "evidence": "conversation",
            },
            {
                "id": "state_tradeoff_to_selected_rebook",
                "kind": "must",
                "requirement": f"Agent must make clear that the chosen replacement {rebook_opt_b.flight_id} keeps the WN airline preference but gives up both morning timing and nonstop service in order to stay within budget.",
                "evidence": "conversation",
            },
        ],
        "_hotels": [hotel],
    }

    return all_flights, [orig_booking], task_data


def scenario_MS02() -> tuple[list[Flight], list[Booking], dict]:
    """MS02: cascade_cancel_rebook_points | user_003 | train | cancel_and_rebook
    Cancel points booking (insurance → free cancel), rebook with points on different date.
    """
    user_id = "user_003"
    user = _USERS_BY_ID[user_id]
    now = DEFAULT_NOW

    # Original flight: JFK → LAX, business, paid with points
    orig_flight = build_flight("AA", "JFK", "LAX", "2026-06-20", "evening", economy_price=380, business_price=950)
    orig_booking = build_booking(
        user_id,
        orig_flight,
        cabin_class="business",
        booked_days_ago=5,
        now=now,
        booking_id="BK-MS02",
        has_insurance=True,
    )
    orig_booking.payment_method = "points"
    orig_booking.points_used = 95000
    orig_booking.cash_amount = 0

    # Rebook: JFK → LAX on different date
    rebook_target, rebook_flights = build_route_flights(
        "JFK",
        "LAX",
        "2026-06-25",
        target_airline="AA",
        target_time="evening",
        target_economy_price=400,
        target_business_price=900,
        num_distractors=3,
        seed=102,
    )

    all_flights = [orig_flight] + rebook_flights

    task_data = {
        "task_id": "cascade_cancel_rebook_points",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            f"I need to cancel my booking {orig_booking.booking_id} to LA and rebook for a later date. "
            "I'd like to use my points again."
        ),
        "user_simulator": {
            "personality": "Polite, direct, expects premium service as a platinum member.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"Booking ID: {orig_booking.booking_id}",
                "Paid with loyalty points originally",
                "Has travel insurance",
                "Wants JFK → LAX on June 25, business class",
                "Prefers AA and evening flights",
                f"Has {user.loyalty_points} loyalty points",
            ],
            "unknown_info": [
                "Exact points refund timing",
                "Available flights on June 25",
            ],
            "task_rules": [
                f"Start by asking to cancel booking {orig_booking.booking_id}.",
                "Mention you paid with points and want them refunded.",
                "When cancellation is confirmed, ask to rebook JFK → LAX on June 25 in business class.",
                "Request to pay with loyalty points again.",
                "When the agent offers options, pick the AA evening flight.",
                "When new booking is confirmed, ask for a summary of both operations.",
                "End with [TASK_DONE].",
            ],
        },
        "_replay_trace": [
            {"name": "cancel_booking", "arguments": {"booking_id": orig_booking.booking_id, "confirm": True}},
            {
                "name": "create_booking",
                "arguments": {
                    "flight_id": rebook_target.flight_id,
                    "user_id": user_id,
                    "cabin_class": "business",
                    "seat_type": "aisle",
                    "payment_method": "points",
                    "points_used": 90000,
                    "meal_preference": "standard",
                },
            },
        ],
        "task_summary": (
            "User wants an insured business-class points booking canceled and then wants a new later business booking made using loyalty points again.\n"
            "The evaluator should check that the agent treats the cancellation and rebooking as a connected points workflow by making clear that the original points payment is refunded before the replacement booking is finalized, then correctly reapplies points to the new booking, and summarizes both operations at the end."
        ),
        "task_requirements": [
            {
                "id": "state_points_refund_explained",
                "kind": "must",
                "requirement": f"Agent must explain that canceling booking {orig_booking.booking_id} refunds the original points payment before the new booking is finalized.",
                "evidence": "conversation",
            },
            {
                "id": "state_points_reapplied_to_new_booking",
                "kind": "must",
                "requirement": "Agent must make clear that the replacement June 25 business booking is being paid with loyalty points again rather than only with cash.",
                "evidence": "conversation",
            },
            {
                "id": "state_two_step_summary",
                "kind": "must",
                "requirement": "Agent must provide a summary that covers both the cancellation/refund step and the replacement booking step, not just the final booking alone.",
                "evidence": "conversation",
            },
        ],
    }

    return all_flights, [orig_booking], task_data


def scenario_MS03() -> tuple[list[Flight], list[Booking], dict]:
    """MS03: cascade_cancel_rebook_international | user_001 | test | cancel_and_rebook
    Cancel domestic business (5% fee, no insurance), rebook international flight.
    """
    user_id = "user_001"
    assert user_id in _USERS_BY_ID, f"Unknown user: {user_id}"
    now = DEFAULT_NOW

    # Original: SFO → JFK, business, no insurance, booked 5 days ago
    orig_flight = build_flight("DL", "SFO", "JFK", "2026-06-22", "morning", economy_price=350, business_price=900)
    orig_booking = build_booking(
        user_id,
        orig_flight,
        cabin_class="business",
        booked_days_ago=5,
        now=now,
        booking_id="BK-MS03",
        has_insurance=False,
    )
    # 5% of 900 = $45 fee

    # Rebook: JFK → LHR (international). Keep exactly one DL morning nonstop option
    # so replay-derived GT and the user-visible choice surface stay aligned.
    rebook_target = build_flight(
        "DL",
        "JFK",
        "LHR",
        "2026-06-24",
        "morning",
        stops=0,
        economy_price=500,
        business_price=1200,
    )
    rebook_flights = [
        rebook_target,
        build_flight("AA", "JFK", "LHR", "2026-06-24", "morning", stops=0, economy_price=520, business_price=1100),
        build_flight("DL", "JFK", "LHR", "2026-06-24", "afternoon", stops=0, economy_price=530, business_price=1180),
        build_flight("DL", "JFK", "LHR", "2026-06-24", "morning", stops=1, economy_price=490, business_price=1220),
    ]

    all_flights = [orig_flight] + rebook_flights

    task_data = {
        "task_id": "cascade_cancel_rebook_international",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            f"I'd like to cancel my San Francisco to New York flight — booking {orig_booking.booking_id} — "
            "and rebook a flight to London instead."
        ),
        "user_simulator": {
            "personality": "Professional and efficient. Expects clear fee breakdowns.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"Booking ID: {orig_booking.booking_id}",
                "Current flight is SFO → JFK, business class",
                "Does NOT have travel insurance",
                "Wants JFK → LHR on June 24, business class",
                "Prefers DL and morning flights",
            ],
            "unknown_info": [
                "Exact cancellation fee percentage",
                "Available flights to London",
                "International flight pricing",
            ],
            "task_rules": [
                f"Start by asking to cancel booking {orig_booking.booking_id}.",
                "When agent mentions a cancellation fee, ask for the exact amount before confirming.",
                "After confirming the fee amount, proceed with cancellation.",
                "When cancellation is done, request a new flight JFK → LHR on June 24 in business class.",
                "When options are shown, select the DL morning flight.",
                "If the agent asks about seat or meal details, answer directly.",
                "When booking is confirmed, ask for a summary of charges.",
                "End with [TASK_DONE].",
            ],
        },
        "_replay_trace": [
            {"name": "cancel_booking", "arguments": {"booking_id": orig_booking.booking_id, "confirm": True}},
            {
                "name": "create_booking",
                "arguments": {
                    "flight_id": rebook_target.flight_id,
                    "user_id": user_id,
                    "cabin_class": "business",
                    "seat_type": "aisle",
                    "payment_method": "credit_card",
                    "meal_preference": "kosher",
                },
            },
        ],
        "task_summary": (
            "User cancels a domestic business booking without insurance and then rebooks an international business flight to London.\n"
            "The evaluator should check that the agent quotes the correct 5% domestic-business cancellation fee before canceling, then presents and books the intended DL morning London replacement rather than collapsing the task into a generic cancel-and-book flow."
        ),
        "task_requirements": [
            {
                "id": "state_domestic_business_cancel_fee",
                "kind": "must",
                "requirement": "Agent must explain that canceling the original domestic business booking incurs a $45 cancellation fee rather than a free insured cancellation.",
                "evidence": "conversation",
            },
            {
                "id": "state_fee_before_cancel_confirmation",
                "kind": "must",
                "requirement": "Agent must give the user the exact cancellation fee before asking for or acting on final cancellation confirmation.",
                "evidence": "conversation",
            },
            {
                "id": "state_replacement_option_selection_clear",
                "kind": "must",
                "requirement": f"After the cancellation, agent must clearly present the June 24 London options and steer the user to the intended DL morning business replacement {rebook_target.flight_id}.",
                "evidence": "conversation",
            },
        ],
    }

    return all_flights, [orig_booking], task_data


def scenario_MS04() -> tuple[list[Flight], list[Booking], dict]:
    """MS04: cascade_delay_rebook_upgrade | user_002 | test | delay_handling
    4h+ delay → full compensation → rebook → upgrade to business.
    """
    user_id = "user_002"
    assert user_id in _USERS_BY_ID, f"Unknown user: {user_id}"
    now = DEFAULT_NOW

    # Delayed flight: ORD → DFW, economy, 270 min delay (4.5 hours)
    delayed_flight = build_flight(
        "UA",
        "ORD",
        "DFW",
        "2026-06-15",
        "afternoon",
        economy_price=300,
        business_price=750,
        status="delayed",
        delay_minutes=270,
    )
    booking = build_booking(
        user_id,
        delayed_flight,
        cabin_class="economy",
        booked_days_ago=7,
        now=now,
        booking_id="BK-MS04",
        has_insurance=False,
    )

    # Alternative flights for rebooking
    alt_target, alt_flights = build_route_flights(
        "ORD",
        "DFW",
        "2026-06-15",
        target_airline="DL",
        target_time="evening",
        target_economy_price=264,
        target_business_price=617,
        num_distractors=2,
        seed=104,
    )

    all_flights = [delayed_flight] + alt_flights

    task_data = {
        "task_id": "cascade_delay_rebook_upgrade",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            f"My flight {delayed_flight.flight_id} is showing a huge delay. "
            "What are my options? I really need to get to Dallas today."
        ),
        "user_simulator": {
            "personality": "Frustrated but reasonable. Wants solutions, not excuses.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"Booking ID: {booking.booking_id}",
                f"Flight {delayed_flight.flight_id} is delayed",
                "Currently in economy class",
                "Wants to get to Dallas today",
                "Willing to upgrade to business if available",
            ],
            "unknown_info": [
                "Exact delay duration",
                "Compensation eligibility rules",
                "Available alternative flights",
                "Upgrade pricing",
            ],
            "task_rules": [
                f"Start by mentioning your flight {delayed_flight.flight_id} is delayed and ask about options.",
                "When agent explains compensation, accept it and ask about rebooking.",
                "When alternative flights are offered, ask about upgrading to business class.",
                "When upgrade price is quoted, accept if the total is within budget ($800).",
                "If the agent asks about seat or meal details, answer directly.",
                "When everything is processed, ask for a summary of compensation + new booking.",
                "End with [TASK_DONE].",
            ],
        },
        "_replay_trace": [
            {
                "name": "update_booking",
                "arguments": {"booking_id": booking.booking_id, "delay_compensation": "full"},
            },
            {
                "name": "update_booking",
                "arguments": {
                    "booking_id": booking.booking_id,
                    "flight_id": alt_target.flight_id,
                    "cabin_class": "business",
                    "seat_type": "window",
                    "meal_preference": "vegetarian",
                },
            },
        ],
        "task_summary": (
            "A same-day flight is delayed 270 minutes, so the user should receive full delay compensation, get rebooked onto a later flight, and then upgrade that replacement to business.\n"
            "The evaluator should check that the agent explicitly recognizes the >=240-minute compensation threshold, claims the compensation before or alongside rebooking, and correctly explains the upgrade pricing for the rebooked flight rather than treating this as an ordinary paid change."
        ),
        "task_requirements": [
            {
                "id": "state_full_delay_compensation_explained",
                "kind": "must",
                "requirement": "Agent must explain that a 270-minute delay qualifies this booking for the full delay-compensation path, including the meal-voucher compensation, rather than a lesser delay remedy.",
                "evidence": "conversation",
            },
            {
                "id": "state_delay_waiver_not_change_fee",
                "kind": "must",
                "requirement": "Agent must make clear that the rebooking is being handled under the delay waiver rather than as an ordinary paid voluntary change with a separate change fee.",
                "evidence": "conversation",
            },
            {
                "id": "state_upgrade_price_basis",
                "kind": "must",
                "requirement": "Agent must explain the business upgrade cost as the fare difference from the original economy booking to the replacement business itinerary, totaling $500.",
                "evidence": "conversation",
            },
        ],
    }

    return all_flights, [booking], task_data


def scenario_MS05() -> tuple[list[Flight], list[Booking], dict]:
    """MS05: cross_cancel_flight_and_hotel | user_005 | train | cross_domain_cancel

    Cancel economy flight + standard hotel. Hotel is 26 hours before check-in,
    so it falls in the 24-48h tier (50% of first night fee). Agent must warn
    about the approaching 24h deadline where the fee would increase to full night.
    """
    user_id = "user_005"
    assert user_id in _USERS_BY_ID, f"Unknown user: {user_id}"
    now = "2026-06-15T13:00:00"  # 1pm, makes hotel 26h before check-in (3pm June 16)

    # Flight: BOS → MIA, economy, no insurance
    flight = build_flight("B6", "BOS", "MIA", "2026-06-16", "afternoon", economy_price=290, business_price=725)
    booking = build_booking(
        user_id, flight, cabin_class="economy", booked_days_ago=5, now=now, booking_id="BK-MS05", has_insurance=False
    )
    # Economy domestic cancel fee: max($50, 15% of $290) = max($50, $43) = $50

    # Hotel: Miami, standard, 3 nights, check-in June 16 (26h from now → 24-48h tier)
    hotel = build_hotel(
        user_id, "MIA", "2026-06-16", "2026-06-19", room_type="standard", nightly_rate=180, booked_days_ago=5, now=now
    )
    # Hotel cancel: 24-48h before check-in (3pm June 16) → 50% of first night = $90
    # If user waits past 3pm tomorrow (June 16 3pm - 24h = June 15 3pm), fee jumps to $180

    all_flights = [flight]

    task_data = {
        "task_id": "cross_cancel_flight_and_hotel",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            f"I need to cancel my whole Miami trip — both my flight (booking {booking.booking_id}) "
            f"and my hotel reservation ({hotel.reservation_id})."
        ),
        "user_simulator": {
            "personality": "Casual and straightforward. Appreciates quick resolution.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"Flight booking ID: {booking.booking_id}",
                f"Hotel reservation ID: {hotel.reservation_id}",
                "Flight is BOS → MIA on June 16",
                "Hotel is in Miami, June 16-19, $180/night",
                "Does not have travel insurance",
            ],
            "unknown_info": [
                "Flight cancellation fee amount",
                "Hotel 24-48h cancellation tier fee",
                "That the fee will increase if they wait too long",
            ],
            "task_rules": [
                f"Start by asking to cancel both the flight ({booking.booking_id}) and hotel ({hotel.reservation_id}).",
                "When agent explains fees for the flight, acknowledge and confirm cancellation.",
                "When agent explains the hotel fee, ask why there is a charge (you booked 5 days ago).",
                "When agent explains the time-based tier, ask what happens if you wait.",
                "When agent warns about the fee increasing, say you want to cancel now to avoid higher fees.",
                "After both are cancelled, ask for a total summary of refunds and fees.",
                "End with [TASK_DONE].",
            ],
        },
        "_replay_trace": [
            {"name": "cancel_booking", "arguments": {"booking_id": booking.booking_id, "confirm": True}},
            {
                "name": "cancel_hotel_reservation",
                "arguments": {"reservation_id": hotel.reservation_id, "confirm": True},
            },
        ],
        "task_summary": (
            "User wants both a domestic flight and a linked Miami hotel canceled, but the two products fall under different fee rules and the hotel is close to crossing into a worse fee tier.\n"
            "The evaluator should check that the agent explains the separate flight and hotel cancellation fees correctly, makes clear why the hotel is currently in the 24-48 hour tier, and warns that waiting past 3pm today would raise the hotel fee to a full first night."
        ),
        "task_requirements": [
            {
                "id": "state_separate_flight_hotel_fee_explanation",
                "kind": "must",
                "requirement": "Agent must make clear that the flight and hotel have different cancellation fee amounts because they follow different cancellation rules.",
                "evidence": "conversation",
            },
            {
                "id": "state_hotel_24_48h_tier_explained",
                "kind": "must",
                "requirement": "Agent must explain that the hotel cancellation fee is the 24-48 hour tier, specifically a 50% first-night charge of $90, rather than a booking-age-based fee or a free cancellation.",
                "evidence": "conversation",
            },
            {
                "id": "state_deadline_warning_given",
                "kind": "must",
                "requirement": "Agent must warn that waiting longer will move the hotel into the under-24-hour tier and raise the fee to a full first night charge of $180.",
                "evidence": "conversation",
            },
        ],
        "_hotels": [hotel],
    }

    return all_flights, [booking], task_data


SCENARIOS = [
    scenario_MS01,
    scenario_MS02,
    scenario_MS03,
    scenario_MS04,
    scenario_MS05,
]
