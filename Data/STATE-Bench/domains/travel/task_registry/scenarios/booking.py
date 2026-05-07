"""Travel scenarios focused on initial flight booking flows."""


from __future__ import annotations



from domains.travel.schemas import Booking, Flight

from domains.travel.task_registry._builders import (
    _USERS_BY_ID,
    DEFAULT_NOW,
    build_flight,
    build_hotel_inventory,
    build_route_flights,
)


def scenario_P07() -> tuple[list[Flight], list[Booking], dict]:
    """P07: book_simple_domestic — Budget-constrained booking with preference conflicts.

    User wants B6, nonstop, afternoon, economy, $700 max. But the B6 nonstop is $720
    (over budget). Within-budget options all violate at least one soft pref:
    - Cheap B6 with 1 stop ($340) — violates nonstop pref
    - Non-B6 nonstop afternoon ($380) — violates airline pref
    - B6 morning nonstop ($390) — violates time pref
    Agent must present trade-offs and help user pick.
    """
    now = DEFAULT_NOW
    user_id = "user_005"
    assert user_id in _USERS_BY_ID, f"Unknown user: {user_id}"

    # Target: B6 nonstop afternoon — but $720 (OVER $700 budget!)
    over_budget = build_flight(
        airline_code="B6",
        origin="JFK",
        destination="LAX",
        date="2026-06-22",
        time_range="afternoon",
        stops=0,
        economy_price=720,
        business_price=1800,
        flight_id="B6200",
    )

    # Option A: B6 with 1 stop, afternoon, $340 (within budget, violates nonstop)
    opt_a = build_flight(
        airline_code="B6",
        origin="JFK",
        destination="LAX",
        date="2026-06-22",
        time_range="afternoon",
        stops=1,
        economy_price=340,
        business_price=850,
        flight_id="B6201",
    )

    # Option B: UA nonstop afternoon, $380 (within budget, violates airline pref)
    opt_b = build_flight(
        airline_code="UA",
        origin="JFK",
        destination="LAX",
        date="2026-06-22",
        time_range="afternoon",
        stops=0,
        economy_price=380,
        business_price=950,
        flight_id="UA200",
    )

    # Option C: B6 nonstop morning, $390 (within budget, violates time pref)
    opt_c = build_flight(
        airline_code="B6",
        origin="JFK",
        destination="LAX",
        date="2026-06-22",
        time_range="morning",
        stops=0,
        economy_price=390,
        business_price=975,
        flight_id="B6202",
    )

    # Distractor: expensive DL nonstop
    distractor = build_flight(
        airline_code="DL",
        origin="JFK",
        destination="LAX",
        date="2026-06-22",
        time_range="evening",
        stops=0,
        economy_price=450,
        business_price=1125,
    )

    all_flights = [over_budget, opt_a, opt_b, opt_c, distractor]

    task_data = {
        "task_id": "book_simple_domestic",

        "user_id": user_id,
        "now": now,
        "opening_message": "I'd like to book a flight from New York to Los Angeles on June 22nd.",
        "user_simulator": {
            "personality": "Cooperative and organized. Shares preferences one at a time when asked.",
            "known_info": [
                f"Your user ID: {user_id}",
                "Wants to fly JFK to LAX on June 22nd",
                "Budget is $700 maximum (non-negotiable)",
            ],
            "unknown_info": [
                "The B6 nonstop afternoon flight costs $720 (over budget)",
                "Available alternatives and their trade-offs",
            ],
            "task_rules": [
                "When the agent says the ideal B6 nonstop afternoon flight is over budget, express disappointment.",
                "Ask the agent what alternatives are available within $700.",
                "When the agent presents options, ask which search preference each one trades off.",
                "If the ideal B6 afternoon nonstop is over budget, choose the B6 morning nonstop flight — keeping airline and nonstop is more important than time.",
                "End with [TASK_DONE] when the booking is confirmed on the agreed flight.",
            ],
        },
        "_search_intent": {"airline": "B6", "time_range": "afternoon", "max_stops": 0, "cabin_class": "economy"},
        "_replay_trace": [
            {
                "name": "create_booking",
                "arguments": {
                    "user_id": user_id,
                    "flight_id": opt_c.flight_id,
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
            "User wants a B6 nonstop afternoon JFK to LAX flight under a hard $700 budget, but the exact ideal option is slightly over budget.\n"
            "The evaluator should check that the agent surfaces the over-budget ideal option, explains the trade-offs among the within-budget alternatives, and steers the user to the chosen B6 nonstop morning fallback rather than hiding the preference conflict."
        ),
        "task_requirements": [
            {
                "id": "state_over_budget_ideal_disclosed",
                "kind": "must",
                "requirement": f"Agent must explain that the ideal B6 nonstop afternoon option {over_budget.flight_id} is over the $700 budget.",
                "evidence": "conversation",
            },
            {
                "id": "state_tradeoffs_explained",
                "kind": "must",
                "requirement": f"Agent must explain what search preference is being traded off by the within-budget alternatives, including why {opt_c.flight_id} keeps airline and nonstop but gives up the afternoon departure preference.",
                "evidence": "conversation",
            },
            {
                "id": "state_not_hide_budget_conflict",
                "kind": "must_not",
                "requirement": "Agent must not act as if the exact preferred B6 nonstop afternoon itinerary fits within the stated $700 budget.",
                "evidence": "conversation",
            },
        ],
    }
    return all_flights, [], task_data


def scenario_P08() -> tuple[list[Flight], list[Booking], dict]:
    """P08: book_with_addons — Book business class with addons + hotel booking.

    User wants to book a business class flight AND a hotel in Miami.
    Preferred AA evening nonstop business is $1800. After booking the flight,
    the agent should help book a hotel too (multi-step). User wants to know
    total baggage allowance (platinum + business = 5 free checked bags).
    """
    now = DEFAULT_NOW
    user_id = "user_003"
    assert user_id in _USERS_BY_ID, f"Unknown user: {user_id}"

    # Multiple flight options — no distractors from build_route since we want control
    target = build_flight(
        airline_code="AA",
        origin="JFK",
        destination="MIA",
        date="2026-06-20",
        time_range="evening",
        stops=0,
        economy_price=280,
        business_price=750,
        flight_id="AA500",
    )
    # Distractor: DL morning, cheaper business
    dist1 = build_flight(
        airline_code="DL",
        origin="JFK",
        destination="MIA",
        date="2026-06-20",
        time_range="morning",
        stops=0,
        economy_price=220,
        business_price=580,
    )
    # Distractor: AA afternoon with 1 stop
    dist2 = build_flight(
        airline_code="AA",
        origin="JFK",
        destination="MIA",
        date="2026-06-20",
        time_range="afternoon",
        stops=1,
        economy_price=200,
        business_price=500,
    )

    all_flights = [target, dist1, dist2]

    # Hotels for user to choose from
    hotel_standard = build_hotel_inventory(
        "MIA", "2026-06-20", "2026-06-24", room_type="standard", nightly_rate=180
    )
    hotel_suite = build_hotel_inventory(
        "MIA", "2026-06-20", "2026-06-24", room_type="suite", nightly_rate=380
    )

    task_data = {
        "task_id": "book_with_addons",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            "I want to book a business class flight from New York to Miami on June 20th. "
            "I'll also need a hotel for 4 nights."
        ),
        "user_simulator": {
            "personality": "Cooperative and detail-oriented. Wants the trip booked correctly and within budget.",
            "known_info": [
                f"Your user ID: {user_id}",
                "Wants JFK to MIA on June 20th",
                "Is a platinum loyalty member",
                "Needs a hotel in Miami for 4 nights (June 20-24)",
                "Budget is $2000 total for the entire trip",
                "Prefers standard room (not suite — too expensive for a business trip)",
            ],
            "unknown_info": [
                "Exact baggage allowance for platinum + business",
                "Flight prices",
                "Hotel nightly rates",
            ],
            "task_rules": [
                "Mention the hotel need if the agent focuses only on the flight.",
                "When the agent presents flight options, pick the AA nonstop evening flight.",
                "When the agent mentions baggage, ask how many free checked bags you get.",
                "For the hotel, pick the standard room option.",
                "Ask for a total trip cost summary (flight + hotel).",
                "End with [TASK_DONE] when both are confirmed.",
            ],
        },
        "_search_intent": {"airline": "AA", "time_range": "evening", "max_stops": 0, "cabin_class": "business"},
        "_replay_trace": [
            {
                "name": "create_booking",
                "arguments": {
                    "user_id": user_id,
                    "flight_id": target.flight_id,
                    "cabin_class": "business",
                    "seat_type": "aisle",
                    "meal_preference": "standard",
                    "add_wifi": True,
                    "add_extra_legroom": True,
                    "add_insurance": True,
                    "payment_method": "credit_card",
                },
            },
            {
                "name": "book_hotel",
                "arguments": {
                    "user_id": user_id,
                    "hotel_id": hotel_standard.hotel_id,
                },
            },
        ],
        "task_summary": (
            "User needs both a business-class Miami flight and a four-night hotel within a total $2,000 trip budget.\n"
            "The evaluator should check that the agent handles the task as a coordinated flight-plus-hotel booking, gives the correct platinum-plus-business baggage allowance, and provides the right total trip cost rather than treating the flight in isolation."
        ),
        "task_requirements": [
            {
                "id": "state_baggage_allowance_explained",
                "kind": "must",
                "requirement": "Agent must explain that a platinum traveler flying business class gets 5 free checked bags on this trip.",
                "evidence": "conversation",
            },
            {
                "id": "state_flight_and_hotel_coordinated",
                "kind": "must",
                "requirement": f"Agent must handle both the AA evening nonstop flight {target.flight_id} and the standard-room hotel booking rather than leaving either component unaddressed.",
                "evidence": "conversation",
            },
            {
                "id": "state_total_cost_summary",
                "kind": "must",
                "requirement": "Agent must summarize that the combined trip cost is $1,470 and remains within the $2,000 budget.",
                "evidence": "conversation",
            },
        ],
        "_hotel_inventory": [hotel_standard, hotel_suite],
    }
    return all_flights, [], task_data


def scenario_P09() -> tuple[list[Flight], list[Booking], dict]:
    """P09: book_international — Budget vs nonstop tradeoff.

    User wants UA nonstop afternoon ORD→LHR economy, $800 budget. But all nonstop
    flights are $820+ (over budget). Within-budget flights have 1 stop. Agent must
    present the trade-off and negotiate. User also has an existing booking on a
    similar date that might conflict — agent should check for schedule overlap.
    """
    now = DEFAULT_NOW
    user_id = "user_002"
    assert user_id in _USERS_BY_ID, f"Unknown user: {user_id}"

    # Nonstop UA afternoon — $820 (OVER $800 budget)
    over_budget_1 = build_flight(
        airline_code="UA",
        origin="ORD",
        destination="LHR",
        date="2026-06-25",
        time_range="afternoon",
        stops=0,
        economy_price=820,
        business_price=2050,
        flight_id="UA300",
    )

    # Nonstop DL morning — $850 (also over budget)
    over_budget_2 = build_flight(
        airline_code="DL",
        origin="ORD",
        destination="LHR",
        date="2026-06-25",
        time_range="morning",
        stops=0,
        economy_price=850,
        business_price=2125,
        flight_id="DL300",
    )

    # Option A: UA 1-stop, afternoon, $480 (within budget, violates nonstop pref)
    opt_a = build_flight(
        airline_code="UA",
        origin="ORD",
        destination="LHR",
        date="2026-06-25",
        time_range="afternoon",
        stops=1,
        economy_price=480,
        business_price=1200,
        flight_id="UA301",
    )

    # Option B: AA 1-stop, evening, $520 (within budget, violates airline + time + nonstop)
    opt_b = build_flight(
        airline_code="AA",
        origin="ORD",
        destination="LHR",
        date="2026-06-25",
        time_range="evening",
        stops=1,
        economy_price=520,
        business_price=1300,
        flight_id="AA300",
    )

    # Option C: UA 1-stop, morning, $460 (within budget, violates time + nonstop)
    opt_c = build_flight(
        airline_code="UA",
        origin="ORD",
        destination="LHR",
        date="2026-06-25",
        time_range="morning",
        stops=1,
        economy_price=460,
        business_price=1150,
        flight_id="UA302",
    )

    all_flights = [over_budget_1, over_budget_2, opt_a, opt_b, opt_c]

    task_data = {
        "task_id": "book_international",

        "user_id": user_id,
        "now": now,
        "opening_message": "I'd like to book a flight from Chicago to London on June 25th.",
        "user_simulator": {
            "personality": "Cooperative and friendly. Provides information clearly when asked.",
            "known_info": [
                f"Your user ID: {user_id}",
                "Wants to fly ORD to LHR on June 25th",
                "Budget is $800 maximum (non-negotiable)",
            ],
            "unknown_info": [
                "All nonstop flights are over $800",
                "Available alternatives with stops",
            ],
            "task_rules": [
                "When the agent says nonstop flights are over budget, ask what alternatives are within $800.",
                "Ask the agent to explain what each search-stage option trades off.",
                "Choose the UA afternoon 1-stop flight — keeping airline and time preference is more important than nonstop.",
                "End with [TASK_DONE] when the booking is confirmed on the agreed flight.",
            ],
        },
        "_search_intent": {"airline": "UA", "time_range": "afternoon", "max_stops": 0, "cabin_class": "economy"},
        "_replay_trace": [
            {
                "name": "create_booking",
                "arguments": {
                    "user_id": user_id,
                    "flight_id": opt_a.flight_id,
                    "cabin_class": "economy",
                    "seat_type": "window",
                    "meal_preference": "vegetarian",
                    "add_wifi": False,
                    "add_extra_legroom": False,
                    "add_insurance": False,
                    "payment_method": "credit_card",
                },
            }
        ],
        "task_summary": (
            "User wants a UA afternoon nonstop flight to London within an $800 budget, but every nonstop option is over budget.\n"
            "The evaluator should check that the agent clearly explains the nonstop-versus-budget trade-off, presents the viable connecting alternatives, and helps the user choose the UA afternoon one-stop option rather than pretending a nonstop solution fits."
        ),
        "task_requirements": [
            {
                "id": "state_nonstop_over_budget_disclosed",
                "kind": "must",
                "requirement": f"Agent must explain that the nonstop options such as {over_budget_1.flight_id} are over the $800 budget.",
                "evidence": "conversation",
            },
            {
                "id": "state_option_tradeoffs_explained",
                "kind": "must",
                "requirement": f"Agent must explain what trade-off the within-budget alternatives make, including that {opt_a.flight_id} preserves airline and afternoon timing but gives up the nonstop preference.",
                "evidence": "conversation",
            },
            {
                "id": "state_not_nonstop_within_budget",
                "kind": "must_not",
                "requirement": "Agent must not imply that a nonstop itinerary satisfying all stated search preferences is available within the $800 budget.",
                "evidence": "conversation",
            },
        ],
    }
    return all_flights, [], task_data


def scenario_P10() -> tuple[list[Flight], list[Booking], dict]:
    """P10: book_with_points_full — Full points domestic, 75k pts at $0.01/pt."""
    now = DEFAULT_NOW
    user_id = "user_001"
    assert user_id in _USERS_BY_ID, f"Unknown user: {user_id}"
    # 75000 pts * $0.01 = $750 max value. Flight economy = $500, fully covered.

    target, all_flights = build_route_flights(
        origin="JFK",
        destination="SFO",
        date="2026-06-24",
        target_airline="DL",
        target_time="morning",
        target_stops=0,
        target_economy_price=500,
        target_business_price=1250,
        num_distractors=3,
        seed=710,
    )
    target_flight_id = target.flight_id
    # Points: 75000 * $0.01 = $750 >= $500 price. Points used = 500 / 0.01 = 50000. Remaining cash = $0.
    points_used = 50000

    task_data = {
        "task_id": "book_with_points_full",

        "user_id": user_id,
        "now": now,
        "opening_message": "I'd like to book a flight from New York to San Francisco using my loyalty points.",
        "user_simulator": {
            "personality": "Cooperative and clear. Wants to use points for the full payment.",
            "known_info": [
                f"Your user ID: {user_id}",
                "Wants to fly JFK to SFO on June 24th",
                "Wants to pay entirely with loyalty points",
                "Has 75,000 loyalty points",
            ],
            "unknown_info": [
                "Exact point redemption rate",
                "How many points will be needed for the flight",
            ],
            "task_rules": [
                "When the agent asks about payment, say you want to pay entirely with points.",
                "When the agent presents flight options, pick the DL nonstop morning flight.",
                "When the agent calculates the points needed, verify the amount seems reasonable.",
                "When the agent confirms the booking is fully covered by points, confirm.",
                "End with [TASK_DONE] when the booking is confirmed with points payment.",
            ],
        },
        "_search_intent": {"airline": "DL", "time_range": "morning", "max_stops": 0, "cabin_class": "economy"},
        "_replay_trace": [
            {
                "name": "create_booking",
                "arguments": {
                    "user_id": user_id,
                    "flight_id": target_flight_id,
                    "cabin_class": "economy",
                    "seat_type": "aisle",
                    "meal_preference": "kosher",
                    "add_wifi": True,
                    "add_extra_legroom": True,
                    "add_insurance": False,
                    "payment_method": "points",
                    "points_used": points_used,
                },
            }
        ],
        "task_summary": (
            "User wants to book a domestic flight entirely with loyalty points and has enough points for full coverage.\n"
            "The evaluator should check that the agent computes the full-points redemption correctly, uses the right 50,000-point figure for the selected flight, and makes clear that no cash payment remains."
        ),
        "task_requirements": [
            {
                "id": "state_full_points_math",
                "kind": "must",
                "requirement": "Agent must explain that the selected flight can be fully covered with 50,000 points.",
                "evidence": "conversation",
            },
            {
                "id": "state_zero_cash_remaining",
                "kind": "must",
                "requirement": "Agent must explain that the remaining cash payment after applying points is $0.",
                "evidence": "conversation",
            },
            {
                "id": "state_not_partial_payment_claim",
                "kind": "must_not",
                "requirement": "Agent must not tell the user that this booking requires a cash remainder once the full points redemption is applied correctly.",
                "evidence": "conversation",
            },
        ],
    }
    return all_flights, [], task_data


def scenario_P11() -> tuple[list[Flight], list[Booking], dict]:
    """P11: book_with_points_partial — Partial points, 15k pts = $150."""
    now = DEFAULT_NOW
    user_id = "user_004"
    assert user_id in _USERS_BY_ID, f"Unknown user: {user_id}"
    # 15000 pts * $0.01 (domestic) = $150. Flight economy = $400. Remaining cash = $250.

    target, all_flights = build_route_flights(
        origin="DEN",
        destination="ATL",
        date="2026-06-23",
        target_airline="WN",
        target_time="morning",
        target_stops=0,
        target_economy_price=400,
        target_business_price=1000,
        num_distractors=3,
        seed=711,
    )
    target_flight_id = target.flight_id
    points_used = 15000
    remaining_cash = 250.0

    task_data = {
        "task_id": "book_with_points_partial",

        "user_id": user_id,
        "now": now,
        "opening_message": "I want to book a flight from Denver to Atlanta and use my loyalty points to offset the cost.",
        "user_simulator": {
            "personality": "Cooperative and practical. Understands points may not cover the full price.",
            "known_info": [
                f"Your user ID: {user_id}",
                "Wants to fly DEN to ATL on June 23rd",
                f"For this task, choose {target_flight_id}",
                "Has 15,000 loyalty points to apply",
                "Budget is $600 maximum (total including points value)",
            ],
            "unknown_info": [
                "Exact point redemption value",
                "How much cash will remain after applying points",
            ],
            "task_rules": [
                "When the agent asks about your request, mention June 23 and that you want to use loyalty points.",
                "Do not ask for nearby dates, different times, or alternative routes.",
                f"When the agent presents flight options, pick {target_flight_id} only.",
                "When the agent calculates the points value, ask how much cash you still need to pay.",
                "When the agent confirms the split payment (points + cash), agree to proceed.",
                "End with [TASK_DONE] when the booking is confirmed with points_plus_cash payment.",
            ],
        },
        "_search_intent": {"airline": "WN", "time_range": "morning", "max_stops": 0, "cabin_class": "economy"},
        "_replay_trace": [
            {
                "name": "create_booking",
                "arguments": {
                    "user_id": user_id,
                    "flight_id": target_flight_id,
                    "cabin_class": "economy",
                    "seat_type": "window",
                    "meal_preference": "standard",
                    "add_wifi": False,
                    "add_extra_legroom": False,
                    "add_insurance": True,
                    "payment_method": "points_plus_cash",
                    "points_used": points_used,
                    "cash_amount": int(remaining_cash),
                },
            }
        ],
        "task_summary": (
            "User wants to apply 15,000 loyalty points toward a domestic booking that still requires some cash.\n"
            "The evaluator should check that the agent computes the domestic points value correctly, explains the remaining cash owed after the points are applied, and treats the purchase as a true points-plus-cash split rather than full coverage."
        ),
        "task_requirements": [
            {
                "id": "state_partial_points_value",
                "kind": "must",
                "requirement": "Agent must explain that 15,000 points are worth $150 for this domestic redemption.",
                "evidence": "conversation",
            },
            {
                "id": "state_remaining_cash_due",
                "kind": "must",
                "requirement": "Agent must explain that $250 in cash remains to be paid after applying the 15,000 points.",
                "evidence": "conversation",
            },
            {
                "id": "state_not_full_points_coverage",
                "kind": "must_not",
                "requirement": "Agent must not claim that the 15,000 points fully cover this booking or leave no cash balance.",
                "evidence": "conversation",
            },
        ],
    }
    return all_flights, [], task_data


def scenario_P12() -> tuple[list[Flight], list[Booking], dict]:
    """P12: book_with_points_international — Intl points at $0.015/pt, 12k pts = $180."""
    now = DEFAULT_NOW
    user_id = "user_005"
    assert user_id in _USERS_BY_ID, f"Unknown user: {user_id}"
    # 12000 pts * $0.015 (international) = $180. Flight economy = $450. Remaining cash = $270.

    target, all_flights = build_route_flights(
        origin="LAX",
        destination="NRT",
        date="2026-06-26",
        target_airline="B6",
        target_time="afternoon",
        target_stops=0,
        target_economy_price=450,
        target_business_price=1150,
        num_distractors=3,
        seed=712,
    )
    target_flight_id = target.flight_id
    points_used = 12000
    remaining_cash = 270.0

    task_data = {
        "task_id": "book_with_points_international",

        "user_id": user_id,
        "now": now,
        "opening_message": "I'd like to book a flight from Los Angeles to Tokyo and apply my loyalty points.",
        "user_simulator": {
            "personality": "Cooperative and curious. Wants to understand the international points rate.",
            "known_info": [
                f"Your user ID: {user_id}",
                "Wants to fly LAX to NRT on June 26th",
                f"For this task, choose {target_flight_id}",
                "Has 12,000 loyalty points to apply",
                "Budget is $700 maximum (total including points value)",
            ],
            "unknown_info": [
                "International points redemption rate ($0.015/pt vs $0.01/pt domestic)",
                "Exact cash remaining after applying points",
            ],
            "task_rules": [
                "When the agent asks about your request, mention loyalty points and June 26.",
                "Do not ask for nearby dates, different airports, different times of day, or connecting options.",
                f"When the agent presents flight options, pick {target_flight_id} only. Do not switch to a nearby date or a different time of day.",
                "When the agent calculates the international points rate, ask how much each point is worth.",
                "When the agent confirms the split payment amount, verify and agree.",
                "End with [TASK_DONE] when the booking is confirmed with points_plus_cash payment.",
            ],
        },
        "_search_intent": {"airline": "B6", "time_range": "afternoon", "max_stops": 0, "cabin_class": "economy"},
        "_replay_trace": [
            {
                "name": "create_booking",
                "arguments": {
                    "user_id": user_id,
                    "flight_id": target_flight_id,
                    "cabin_class": "economy",
                    "seat_type": "aisle",
                    "meal_preference": "vegan",
                    "add_wifi": True,
                    "add_extra_legroom": False,
                    "add_insurance": False,
                    "payment_method": "points_plus_cash",
                    "points_used": points_used,
                    "cash_amount": int(remaining_cash),
                },
            }
        ],
        "task_summary": (
            "User wants to apply 12,000 points toward an international booking where the international redemption rate is higher than the domestic rate.\n"
            "The evaluator should check that the agent uses the international $0.015 per point valuation, computes the correct $270 cash remainder, and does not fall back to the domestic points rate."
        ),
        "task_requirements": [
            {
                "id": "state_international_points_rate",
                "kind": "must",
                "requirement": "Agent must explain that the international redemption rate here is $0.015 per point, making 12,000 points worth $180.",
                "evidence": "conversation",
            },
            {
                "id": "state_international_cash_remainder",
                "kind": "must",
                "requirement": "Agent must explain that $270 in cash remains after applying the 12,000 points to the booking.",
                "evidence": "conversation",
            },
            {
                "id": "state_not_domestic_rate",
                "kind": "must_not",
                "requirement": "Agent must not use or claim the lower domestic points valuation for this international redemption.",
                "evidence": "conversation",
            },
        ],
    }
    return all_flights, [], task_data


SCENARIOS = [
    scenario_P07,
    scenario_P08,
    scenario_P09,
    scenario_P10,
    scenario_P11,
    scenario_P12,
]
