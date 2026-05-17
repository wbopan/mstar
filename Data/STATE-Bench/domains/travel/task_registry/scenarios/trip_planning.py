"""Travel scenarios for planning and cross-product trip coordination."""


from __future__ import annotations


from domains.travel.schemas import Booking, Flight

from domains.travel.task_registry._builders import (
    _USERS_BY_ID,
    DEFAULT_NOW,
    build_booking,
    build_car_inventory,
    build_car_rental,
    build_flight,
    build_hotel,
    build_hotel_inventory,
    build_route_flights,
)


def scenario_MS06() -> tuple[list[Flight], list[Booking], dict]:
    """MS06: cross_cancel_full_trip | user_001 | train | cross_domain_cancel

    Cancel flight (free due to delay) + hotel suite (non-refundable) + luxury car ($50 surcharge).
    User only mentions flight and hotel. Agent must discover the car rental exists.
    """
    user_id = "user_001"
    assert user_id in _USERS_BY_ID, f"Unknown user: {user_id}"
    now = DEFAULT_NOW

    # Flight: delayed 300 min → airline-initiated level qualifies free cancel
    flight = build_flight(
        "DL",
        "JFK",
        "LAX",
        "2026-06-18",
        "morning",
        economy_price=400,
        business_price=1000,
        status="delayed",
        delay_minutes=300,
    )
    booking = build_booking(
        user_id, flight, cabin_class="business", booked_days_ago=10, now=now, booking_id="BK-MS06", has_insurance=False
    )

    # Hotel: LA, suite, 4 nights — non-refundable
    hotel = build_hotel(
        user_id, "LAX", "2026-06-18", "2026-06-22", room_type="suite", nightly_rate=350, booked_days_ago=10, now=now
    )
    # Suite = non-refundable, fee = total_price = 350*4 = $1400

    # Car: LA, luxury, 4 days — $50 surcharge. User does NOT mention this.
    car = build_car_rental(
        user_id, "LAX", "2026-06-18", "2026-06-22", car_class="luxury", daily_rate=120, booked_days_ago=10, now=now
    )
    # Luxury cancel: 24h+ before pickup → $50 surcharge, rest refunded

    all_flights = [flight]

    task_data = {
        "task_id": "cross_cancel_full_trip",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            f"My flight {flight.flight_id} to LA is delayed over 5 hours. I want to cancel "
            f"my flight ({booking.booking_id}) and hotel ({hotel.reservation_id})."
        ),
        "user_simulator": {
            "personality": "Assertive and organized. Wants clear breakdown of each item.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"Flight booking: {booking.booking_id} (delayed 5+ hours)",
                f"Hotel reservation: {hotel.reservation_id} (suite in LA)",
                f"Car rental: {car.rental_id} (luxury car in LA)",
                "Flight is massively delayed",
            ],
            "unknown_info": [
                "Hotel suite is non-refundable",
                "Car luxury surcharge amount",
                "Exact refund amounts for each",
            ],
            "task_rules": [
                "Start by requesting cancellation of the flight and hotel ONLY. Do NOT mention the car rental AT ALL.",
                "When agent explains the flight is free to cancel due to delay, acknowledge.",
                "When agent explains hotel suite is non-refundable, express disappointment but accept.",
                "If the agent asks about other reservations or mentions the car rental, confirm you want to cancel it too.",
                "If the agent does NOT ask about other reservations after processing flight and hotel, "
                "simply end with [TASK_DONE]. The agent should have checked proactively.",
                "When agent explains car surcharge, accept and confirm.",
                "After all brought-up items are processed, ask for a complete summary with total fees and refunds.",
                "End with [TASK_DONE].",
            ],
        },
        "_replay_trace": [
            {"name": "cancel_booking", "arguments": {"booking_id": booking.booking_id, "confirm": True}},
            {
                "name": "cancel_hotel_reservation",
                "arguments": {"reservation_id": hotel.reservation_id, "confirm": True},
            },
            {"name": "cancel_car_rental", "arguments": {"rental_id": car.rental_id, "confirm": True}},
        ],
        "task_summary": (
            "User asks to cancel a delayed flight and an LA hotel, but a linked luxury car rental also exists and must be proactively discovered.\n"
            "The evaluator should check that the agent recognizes the severe-delay free-cancellation path for the flight, clearly explains that the suite hotel is non-refundable, and proactively surfaces and resolves the hidden luxury-car cancellation with its surcharge instead of ignoring it."
        ),
        "task_requirements": [
            {
                "id": "state_hidden_car_discovered",
                "kind": "must",
                "requirement": f"Agent must proactively discover and bring up the linked luxury car rental {car.rental_id} rather than ending after only the flight and hotel.",
                "evidence": "conversation",
            },
            {
                "id": "state_delay_cancel_and_nonrefundable_hotel_explained",
                "kind": "must",
                "requirement": "Agent must explain that the delayed flight can be canceled with no fee because of the severe airline delay, while the suite hotel is still non-refundable.",
                "evidence": "conversation",
            },
            {
                "id": "state_luxury_car_surcharge_explained",
                "kind": "must",
                "requirement": "Agent must explain that canceling the linked luxury car rental carries a $50 surcharge and quote that fee before or when confirming the cancellation.",
                "evidence": "conversation",
            },
        ],
        "_hotels": [hotel],
        "_car_rentals": [car],
    }

    return all_flights, [booking], task_data


def scenario_MS07() -> tuple[list[Flight], list[Booking], dict]:
    """MS07: cross_cancel_keep_hotel | user_003 | test | cross_domain_cancel

    User vaguely says "make changes to my Paris trip" without specifying what.
    Agent must discover all 3 reservations (flight, hotel, car), clarify the
    user's intent, and selectively cancel flight + car while keeping hotel.
    """
    user_id = "user_003"
    assert user_id in _USERS_BY_ID, f"Unknown user: {user_id}"
    now = DEFAULT_NOW

    # Flight: JFK → CDG (international), business, has insurance
    flight = build_flight("AA", "JFK", "CDG", "2026-06-20", "evening", economy_price=550, business_price=1400)
    booking = build_booking(
        user_id, flight, cabin_class="business", booked_days_ago=4, now=now, booking_id="BK-MS07", has_insurance=True
    )
    # Insurance → free cancel

    # Hotel: Paris, standard, 5 nights
    hotel = build_hotel(
        user_id, "CDG", "2026-06-20", "2026-06-25", room_type="standard", nightly_rate=200, booked_days_ago=4, now=now
    )

    # Car: Paris, midsize, 5 days
    car = build_car_rental(
        user_id, "CDG", "2026-06-20", "2026-06-25", car_class="midsize", daily_rate=65, booked_days_ago=4, now=now
    )
    # Midsize, 24h+: free cancel

    all_flights = [flight]

    task_data = {
        "task_id": "cross_cancel_keep_hotel",

        "user_id": user_id,
        "now": now,
        "opening_message": ("I need to make some changes to my Paris trip. Can you help me sort things out?"),
        "user_simulator": {
            "personality": "Slightly scattered. Has a plan but doesn't communicate it clearly upfront.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"Flight booking: {booking.booking_id} (JFK→CDG, business)",
                f"Hotel reservation: {hotel.reservation_id} (Paris, 5 nights)",
                f"Car rental: {car.rental_id} (Paris, midsize, 5 days)",
                "Has travel insurance on the flight",
                "Wants to KEEP the hotel",
                "Wants to cancel the flight and car",
            ],
            "unknown_info": [
                "Cancellation fees for flight and car",
            ],
            "task_rules": [
                "Start vaguely: 'I need to make some changes to my Paris trip.'",
                "Do NOT immediately say what you want to cancel or keep.",
                "When the agent asks what reservations you have or what changes you need, say "
                "'I have a flight, hotel, and car booked for Paris next week.'",
                f"If the agent asks which Paris flight (since you may have multiple), specify {booking.booking_id} — that's the business class one.",
                "When the agent asks what changes you want, say 'Well, my friend offered to drive me there, "
                "so I won't need the flight anymore. But I'm not sure about the car.'",
                "When the agent asks about the car specifically, say 'Actually cancel that too — we'll use my friend's car.'",
                "When the agent asks about the hotel, say firmly 'Keep the hotel, I still need that.'",
                "When the flight and car cancellations are confirmed, ask for a summary.",
                "Verify the hotel is still active.",
                "End with [TASK_DONE].",
            ],
        },
        "_replay_trace": [
            {"name": "cancel_booking", "arguments": {"booking_id": booking.booking_id, "confirm": True}},
            {"name": "cancel_car_rental", "arguments": {"rental_id": car.rental_id, "confirm": True}},
        ],
        "task_summary": (
            "User starts vaguely about 'changes' to a Paris trip that includes a flight, hotel, and car, but only wants the flight and car canceled while keeping the hotel.\n"
            "The evaluator should check that the agent discovers all three reservations, clarifies the user's intent before taking action, and preserves the hotel instead of collapsing the task into a blanket trip cancellation."
        ),
        "task_requirements": [
            {
                "id": "state_all_three_reservations_discovered",
                "kind": "must",
                "requirement": f"Agent must discover and explicitly surface the flight {booking.booking_id}, hotel {hotel.reservation_id}, and car rental {car.rental_id} before finalizing the requested changes.",
                "evidence": "conversation",
            },
            {
                "id": "state_intent_clarified_before_action",
                "kind": "must",
                "requirement": "Agent must clarify which parts of the Paris trip the user wants to cancel versus keep before executing cancellations.",
                "evidence": "conversation",
            },
            {
                "id": "state_hotel_not_canceled",
                "kind": "must_not",
                "requirement": f"Agent must not treat hotel reservation {hotel.reservation_id} as canceled or imply that the user wanted the whole trip canceled once the user says to keep the hotel.",
                "evidence": "conversation",
            },
        ],
        "_hotels": [hotel],
        "_car_rentals": [car],
    }

    return all_flights, [booking], task_data


def scenario_MS08() -> tuple[list[Flight], list[Booking], dict]:
    """MS08: cascade_change_and_add_bags | user_002 | train | flight_change
    Change flight (medical reason, 50% discount on fee) + add checked bags.
    """
    user_id = "user_002"
    assert user_id in _USERS_BY_ID, f"Unknown user: {user_id}"
    now = DEFAULT_NOW

    # Original flight: ORD → SFO, economy, booked 10 days ago
    orig_flight = build_flight("UA", "ORD", "SFO", "2026-06-20", "afternoon", economy_price=340, business_price=850)
    booking = build_booking(
        user_id,
        orig_flight,
        cabin_class="economy",
        booked_days_ago=10,
        now=now,
        booking_id="BK-MS08",
        has_insurance=False,
    )
    # Change fee: economy domestic, <=7 days to departure (June 20 - June 15 = 5 days) → $150 base, medical = 50% → $75

    # Alternative flight for change
    alt_target, alt_flights = build_route_flights(
        "ORD",
        "SFO",
        "2026-06-22",
        target_airline="UA",
        target_time="afternoon",
        target_economy_price=360,
        target_business_price=900,
        target_flight_id="UA113",
        num_distractors=2,
        seed=108,
    )
    alt_flights[1].flight_id = "AS104"
    alt_flights[2].flight_id = "UA114"

    all_flights = [orig_flight] + alt_flights

    # Baggage: economy + basic tier = 1 free checked bag; extra bag = $35 each

    task_data = {
        "task_id": "cascade_change_and_add_bags",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            f"I need to change my flight ({booking.booking_id}) to a later date. "
            "I have a medical appointment that conflicts. Also, I'll need to bring extra luggage."
        ),
        "user_simulator": {
            "personality": "Polite, a bit anxious about fees. Mentions medical reason upfront.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"Booking ID: {booking.booking_id}",
                "Current flight is ORD → SFO on June 20",
                "Reason for change: medical appointment",
                "Wants to fly June 22 instead",
                "Needs 2 extra checked bags",
            ],
            "unknown_info": [
                "Change fee amount or medical discount",
                "Available flights on June 22",
                "Baggage fee per bag",
                "Free baggage allowance",
            ],
            "task_rules": [
                f"Start by asking to change booking {booking.booking_id} to June 22 due to a medical appointment.",
                "When agent quotes the change fee, ask if there's a medical discount.",
                "When discounted fee is confirmed, agree to proceed.",
                f"When new flight options are shown, pick {alt_target.flight_id}, the preferred United afternoon flight.",
                f"If the agent proposes or changes you to any other flight, say you want {alt_target.flight_id} on June 22 instead.",
                "Then ask to add 2 extra checked bags.",
                "When bag fees are quoted, confirm.",
                "Ask for a summary of all changes and fees.",
                "End with [TASK_DONE].",
            ],
        },
        "_replay_trace": [
            {
                "name": "update_booking",
                "arguments": {
                    "booking_id": booking.booking_id,
                    "flight_id": alt_target.flight_id,
                    "change_reason": "medical",
                    "cabin_class": "economy",
                    "seat_type": "window",
                    "meal_preference": "vegetarian",
                    "add_wifi": False,
                    "add_extra_legroom": False,
                    "add_insurance": False,
                },
            },
            {"name": "update_booking", "arguments": {"booking_id": booking.booking_id, "paid_checked_bags": 2}},
        ],
        "task_summary": (
            "User changes a domestic economy flight for a medical reason and then adds two extra checked bags.\n"
            "The evaluator should check that the agent explains the medical-discounted $75 change fee, quotes the baggage allowance and per-bag pricing correctly, and provides a combined summary of the flight-change math plus the added-bag charges."
        ),
        "task_requirements": [
            {
                "id": "state_medical_discount_explained",
                "kind": "must",
                "requirement": "Agent must explain that the medical reason cuts the standard domestic change fee in half, producing a $75 change fee for this booking.",
                "evidence": "conversation",
            },
            {
                "id": "state_baggage_allowance_and_fee_explained",
                "kind": "must",
                "requirement": "Agent must explain the free checked-bag allowance for this traveler and quote the extra-bag fee as $35 per added bag before finalizing the baggage update.",
                "evidence": "conversation",
            },
            {
                "id": "state_combined_change_and_bags_summary",
                "kind": "must",
                "requirement": "Agent must summarize both the flight-change charges and the additional baggage charges together, rather than only confirming one part of the workflow.",
                "evidence": "conversation",
            },
        ],
    }

    return all_flights, [booking], task_data


def scenario_MS09() -> tuple[list[Flight], list[Booking], dict]:
    """MS09: cross_plan_trip_budget | user_004 | train | cross_domain_plan
    Round-trip domestic flight + hotel + car under $600 total.
    Agent must compare options across 4 domains and keep running total under budget.
    User insists on selecting everything before booking.
    """
    user_id = "user_004"
    assert user_id in _USERS_BY_ID, f"Unknown user: {user_id}"
    now = DEFAULT_NOW

    # --- Outbound flights: ORD → DEN, June 20 (4 options) ---
    target_out, outbound_flights = build_route_flights(
        "ORD",
        "DEN",
        "2026-06-20",
        target_airline="WN",
        target_time="morning",
        target_economy_price=160,
        target_business_price=400,
        num_distractors=3,
        seed=109,
    )

    # --- Return flights: DEN → ORD, June 22 (3 options) ---
    target_ret, return_flights = build_route_flights(
        "DEN",
        "ORD",
        "2026-06-22",
        target_airline="WN",
        target_time="afternoon",
        target_economy_price=140,
        target_business_price=350,
        num_distractors=2,
        seed=209,
    )

    all_flights = outbound_flights + return_flights

    # --- Hotels in DEN: 3 options (2 nights) ---
    hotel_cheap = build_hotel_inventory(
        "DEN", "2026-06-20", "2026-06-22", room_type="standard", nightly_rate=95
    )
    hotel_mid = build_hotel_inventory(
        "DEN", "2026-06-20", "2026-06-22", room_type="standard", nightly_rate=140
    )
    hotel_expensive = build_hotel_inventory(
        "DEN", "2026-06-20", "2026-06-22", room_type="suite", nightly_rate=260
    )

    # --- Cars in DEN: 3 options (2 days) ---
    car_cheap = build_car_inventory(
        "DEN", "2026-06-20", "2026-06-22", car_class="economy", daily_rate=40
    )
    car_compact = build_car_inventory(
        "DEN", "2026-06-20", "2026-06-22", car_class="compact", daily_rate=60
    )
    car_mid = build_car_inventory(
        "DEN", "2026-06-20", "2026-06-22", car_class="midsize", daily_rate=75
    )

    # Budget check: $160 outbound + $140 return + $190 hotel + $80 car = $570 ✓ (under $600)
    # Upgrading any component pushes over: compact car=$120 → $610 ✗, mid hotel=$280 → $660 ✗

    task_data = {
        "task_id": "cross_plan_trip_budget",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            "I need to plan a weekend trip to Denver. Flying from Chicago on June 20, coming back June 22. "
            "I need flights both ways, a hotel, and a rental car. Total budget is $600."
        ),
        "user_simulator": {
            "personality": "Budget-conscious and practical. Wants the cheapest viable options. Won't book until everything is selected.",
            "known_info": [
                f"Your user ID: {user_id}",
                "Round-trip ORD ↔ DEN (Denver)",
                "Dates: June 20-22 (2 nights)",
                "Total budget: $600 for outbound flight + return flight + hotel + car",
                "Prefers economy class",
                "Standard hotel room is fine",
                "Economy car is fine",
            ],
            "unknown_info": [
                "Available flight prices for outbound and return",
                "Hotel and car rental rates in Denver",
                "Whether the total will fit under $600",
            ],
            "task_rules": [
                "Start by asking to plan a round-trip to Denver: outbound flight, return flight, hotel, and car.",
                "Mention the $600 total budget upfront.",
                "Focus first on selecting the outbound flight, return flight, hotel, and car within budget. Final flight booking preferences can be confirmed at booking time if needed.",
                "When outbound flight options are shown, pick the cheapest nonstop economy option.",
                "When return flight options are shown, pick the cheapest nonstop economy option.",
                "When hotel options are shown, say 'The cheapest standard room works.'",
                "When car options are shown, say 'Economy is fine.'",
                "IF the agent tries to book anything before all 4 components are selected, say "
                "'Hold on — let's pick everything first and review the total before booking anything.'",
                "After all 4 components are selected, ask 'What's the total? I need to make sure it's under $600.'",
                "IF the total is under $600, say 'Perfect, go ahead and book everything.'",
                "IF the total exceeds $600, say 'That's over my budget. Can we find cheaper options?'",
                "When both flights are booked and hotel/car selections confirmed, end with [TASK_DONE].",
            ],
        },
        "_replay_trace": [
            {
                "name": "create_booking",
                "arguments": {
                    "flight_id": target_out.flight_id,
                    "user_id": user_id,
                    "cabin_class": "economy",
                    "seat_type": _USERS_BY_ID[user_id].preferences["seat_type"],
                    "payment_method": "credit_card",
                    "meal_preference": _USERS_BY_ID[user_id].preferences["meal_preference"],
                    "add_wifi": _USERS_BY_ID[user_id].preferences["add_wifi"],
                    "add_extra_legroom": _USERS_BY_ID[user_id].preferences["add_extra_legroom"],
                    "add_insurance": _USERS_BY_ID[user_id].preferences["add_insurance"],
                },
            },
            {
                "name": "create_booking",
                "arguments": {
                    "flight_id": target_ret.flight_id,
                    "user_id": user_id,
                    "cabin_class": "economy",
                    "seat_type": _USERS_BY_ID[user_id].preferences["seat_type"],
                    "payment_method": "credit_card",
                    "meal_preference": _USERS_BY_ID[user_id].preferences["meal_preference"],
                    "add_wifi": _USERS_BY_ID[user_id].preferences["add_wifi"],
                    "add_extra_legroom": _USERS_BY_ID[user_id].preferences["add_extra_legroom"],
                    "add_insurance": _USERS_BY_ID[user_id].preferences["add_insurance"],
                },
            },
            {"name": "book_hotel", "arguments": {"hotel_id": hotel_cheap.hotel_id, "user_id": user_id}},
            {"name": "book_car_rental", "arguments": {"car_id": car_cheap.car_id, "user_id": user_id}},
        ],
        "task_summary": (
            "User needs an outbound flight, return flight, hotel, and car rental for a Denver weekend, all under a strict $600 total budget.\n"
            "The evaluator should check that the agent compares all four components before booking anything, keeps a coherent running total, and explicitly explains that only the cheapest combination stays under budget."
        ),
        "task_requirements": [
            {
                "id": "state_select_everything_before_booking",
                "kind": "must",
                "requirement": "Agent must select and review the outbound flight, return flight, hotel, and car together before starting bookings, rather than prematurely booking individual components.",
                "evidence": "conversation",
            },
            {
                "id": "state_running_total_under_budget",
                "kind": "must",
                "requirement": "Agent must provide the combined trip total and make clear that the chosen package stays under the $600 budget.",
                "evidence": "conversation",
            },
        ],
        "_hotel_inventory": [hotel_cheap, hotel_mid, hotel_expensive],
        "_car_inventory": [car_cheap, car_compact, car_mid],
    }

    return all_flights, [], task_data


def scenario_MS10() -> tuple[list[Flight], list[Booking], dict]:
    """MS10: cross_plan_trip_international | user_005 | test | cross_domain_plan
    Round-trip international flight + hotel + car under $700 total.
    Agent must compare options across 4 domains and keep running total under budget.
    User insists on selecting everything before booking.
    """
    user_id = "user_005"
    assert user_id in _USERS_BY_ID, f"Unknown user: {user_id}"
    now = DEFAULT_NOW

    # --- Outbound flights: JFK → YYZ, June 21 (4 options) ---
    target_out, outbound_flights = build_route_flights(
        "JFK",
        "YYZ",
        "2026-06-21",
        target_airline="B6",
        target_time="afternoon",
        target_economy_price=150,
        target_business_price=375,
        num_distractors=3,
        seed=110,
    )

    # --- Return flights: YYZ → JFK, June 24 (3 options) ---
    target_ret, return_flights = build_route_flights(
        "YYZ",
        "JFK",
        "2026-06-24",
        target_airline="B6",
        target_time="morning",
        target_economy_price=130,
        target_business_price=325,
        num_distractors=2,
        seed=210,
    )

    all_flights = outbound_flights + return_flights

    # --- Hotels in YYZ: 3 options (3 nights) ---
    hotel_std = build_hotel_inventory(
        "YYZ", "2026-06-21", "2026-06-24", room_type="standard", nightly_rate=90
    )
    hotel_mid = build_hotel_inventory(
        "YYZ", "2026-06-21", "2026-06-24", room_type="standard", nightly_rate=130
    )
    hotel_suite = build_hotel_inventory(
        "YYZ", "2026-06-21", "2026-06-24", room_type="suite", nightly_rate=280
    )

    # --- Cars in YYZ: 3 options (3 days) ---
    car_econ = build_car_inventory(
        "YYZ", "2026-06-21", "2026-06-24", car_class="economy", daily_rate=35
    )
    car_compact = build_car_inventory(
        "YYZ", "2026-06-21", "2026-06-24", car_class="compact", daily_rate=55
    )
    car_suv = build_car_inventory(
        "YYZ", "2026-06-21", "2026-06-24", car_class="suv", daily_rate=90
    )

    # Budget check: $150 outbound + $130 return + $270 hotel + $105 car = $655 ✓ (under $700)
    # Upgrading any component pushes over: compact car=$165 → $715 ✗, mid hotel=$390 → $775 ✗

    task_data = {
        "task_id": "cross_plan_trip_international",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            "I'm planning a round-trip to Toronto. Flying from JFK on June 21, returning June 24. "
            "I need flights both ways, a hotel, and a rental car. My total budget is $700."
        ),
        "user_simulator": {
            "personality": "Enthusiastic but budget-aware. Wants good value. Won't book until everything is selected.",
            "known_info": [
                f"Your user ID: {user_id}",
                "Round-trip JFK ↔ YYZ (Toronto)",
                "Dates: June 21-24 (3 nights)",
                "Total budget: $700 for outbound flight + return flight + hotel + car",
                "Prefers economy class, B6 airline if available",
                "Standard hotel room is fine",
                "Economy car is fine",
            ],
            "unknown_info": [
                "Available flight prices for outbound and return",
                "Hotel and car rental rates in Toronto",
                "Whether the total will fit under $700",
            ],
            "task_rules": [
                "Start by asking to plan a round-trip to Toronto: outbound flight, return flight, hotel, and car.",
                "Mention the $700 total budget upfront.",
                "Focus first on selecting the outbound flight, return flight, hotel, and car within budget. Final flight booking preferences can be confirmed at booking time if needed.",
                "When outbound flight options are shown, say 'I like the B6 nonstop in the afternoon.'",
                "When return flight options are shown, say 'The morning B6 nonstop looks good.'",
                "When hotel options are shown, say 'The cheapest standard room works for me.'",
                "When car options are shown, say 'Economy is fine.'",
                "IF the agent tries to book anything before all 4 components are selected, say "
                "'Let's pick everything first and review the total before booking anything.'",
                "After all 4 components are selected, ask 'Can you give me the total? I want to make sure it's under $700.'",
                "IF the total is under $700, say 'Great, please go ahead and book everything.'",
                "IF the total exceeds $700, say 'That total should stay at $655 before any optional taxes or extras. Please keep the itinerary with the economy car and standard hotel and do not drop any trip component.'",
                "If the agent invents extra taxes or fees that push the total over budget, restate that you want the original $655 bundle and ask them to proceed with that exact flight + hotel + car combination.",
                "When both flights are booked and hotel/car selections confirmed, end with [TASK_DONE].",
            ],
        },
        "_replay_trace": [
            {
                "name": "create_booking",
                "arguments": {
                    "flight_id": target_out.flight_id,
                    "user_id": user_id,
                    "cabin_class": "economy",
                    "seat_type": _USERS_BY_ID[user_id].preferences["seat_type"],
                    "payment_method": "credit_card",
                    "meal_preference": _USERS_BY_ID[user_id].preferences["meal_preference"],
                    "add_wifi": _USERS_BY_ID[user_id].preferences["add_wifi"],
                    "add_extra_legroom": _USERS_BY_ID[user_id].preferences["add_extra_legroom"],
                    "add_insurance": _USERS_BY_ID[user_id].preferences["add_insurance"],
                },
            },
            {
                "name": "create_booking",
                "arguments": {
                    "flight_id": target_ret.flight_id,
                    "user_id": user_id,
                    "cabin_class": "economy",
                    "seat_type": _USERS_BY_ID[user_id].preferences["seat_type"],
                    "payment_method": "credit_card",
                    "meal_preference": _USERS_BY_ID[user_id].preferences["meal_preference"],
                    "add_wifi": _USERS_BY_ID[user_id].preferences["add_wifi"],
                    "add_extra_legroom": _USERS_BY_ID[user_id].preferences["add_extra_legroom"],
                    "add_insurance": _USERS_BY_ID[user_id].preferences["add_insurance"],
                },
            },
            {"name": "book_hotel", "arguments": {"hotel_id": hotel_std.hotel_id, "user_id": user_id}},
            {"name": "book_car_rental", "arguments": {"car_id": car_econ.car_id, "user_id": user_id}},
        ],
        "task_summary": (
            "User needs a round-trip Toronto package with flights, hotel, and car rental under a strict $700 total budget.\n"
            "The evaluator should check that the agent compares all four components before booking, keeps the running international-trip total straight, and makes clear that only the cheapest viable bundle fits inside the budget."
        ),
        "task_requirements": [
            {
                "id": "state_select_everything_before_booking",
                "kind": "must",
                "requirement": "Agent must gather and review the outbound flight, return flight, hotel, and car rental choices before committing bookings, because the user insists on selecting everything first.",
                "evidence": "conversation",
            },
            {
                "id": "state_running_total_under_budget",
                "kind": "must",
                "requirement": "Agent must compute and communicate the combined package total using the benchmark's quoted base bundle prices, and confirm that the final chosen Toronto itinerary stays under the $700 budget on that base-price basis rather than inventing required optional taxes or extras.",
                "evidence": "conversation",
            },
        ],
        "_hotel_inventory": [hotel_std, hotel_mid, hotel_suite],
        "_car_inventory": [car_econ, car_compact, car_suv],
    }

    return all_flights, [], task_data


SCENARIOS = [
    scenario_MS06,
    scenario_MS07,
    scenario_MS08,
    scenario_MS09,
    scenario_MS10,
]
