"""Travel informational scenarios with no booking execution target."""


from __future__ import annotations


from domains.travel.schemas import Booking, Flight

from domains.travel.task_registry._builders import (
    DEFAULT_NOW,
    build_booking,
    build_flight,
    build_hotel,
)


def scenario_I01() -> tuple[list[Flight], list[Booking], dict]:
    """I01: Baggage allowance — platinum + business = 5 free checked bags.

    user_003 (Olivia, platinum) has a business booking. Same calculation as PR10
    but framed as a pure informational query with no action needed.
    """
    now = DEFAULT_NOW
    user_id = "user_003"

    flight = build_flight(
        airline_code="AA",
        origin="ORD",
        destination="SFO",
        date="2026-06-21",
        time_range="morning",
        economy_price=350,
        business_price=880,
    )

    booking = build_booking(
        user_id="user_003",
        flight=flight,
        cabin_class="business",
        booked_days_ago=4,
        now=now,
        booking_id="BK-I01",
    )

    task_data = {
        "task_id": "info_baggage_allowance",

        "user_id": "user_003",
        "now": now,
        "opening_message": (
            "I have booking BK-I01. I'm platinum and flying business. How many checked bags do I get for free?"
        ),
        "user_simulator": {
            "personality": "Quick and to-the-point. Just wants the number.",
            "known_info": [
                f"Your user ID: {user_id}",
                "Booking ID is BK-I01",
                "Platinum loyalty member",
                "Business class booking",
            ],
            "unknown_info": [
                "Exact number of free checked bags (5)",
                "Breakdown: 2 cabin + 3 platinum",
                "Extra bag fees",
            ],
            "task_rules": [
                "Ask your question about baggage allowance.",
                "When the agent provides the number, ask for the breakdown (cabin vs loyalty).",
                "When you have complete information, end with [TASK_DONE].",
            ],
        },
        "task_summary": "User asks for baggage allowance on an existing business-class booking with platinum status.\nThe evaluator should check whether the agent states the correct 5-bag total and gives the business-plus-platinum breakdown the user asked for.",
        "task_requirements": [
            {
                "id": "state_checked_bag_count",
                "kind": "must",
                "requirement": "Agent must state that the user gets 5 free checked bags.",
                "evidence": "conversation",
            },
            {
                "id": "state_baggage_breakdown",
                "kind": "must",
                "requirement": "Agent must explain the breakdown as 2 free checked bags from business class plus 3 from platinum status.",
                "evidence": "conversation",
            },
        ],
        "_replay_trace": [],
    }

    return [flight], [booking], task_data


def scenario_I02() -> tuple[list[Flight], list[Booking], dict]:
    """I02: Basic economy baggage — 0 free bags, $50/bag.

    user_005 (Ava, basic tier) has a basic_economy booking. Gets 0 free checked bags
    and must pay $50 per bag (basic economy rate).
    """
    now = DEFAULT_NOW
    user_id = "user_005"

    flight = build_flight(
        airline_code="B6",
        origin="MIA",
        destination="JFK",
        date="2026-06-19",
        time_range="afternoon",
        economy_price=220,
        business_price=550,
    )
    flight.cabin_prices["basic_economy"] = 130

    booking = build_booking(
        user_id="user_005",
        flight=flight,
        cabin_class="basic_economy",
        booked_days_ago=3,
        now=now,
        booking_id="BK-I02",
    )

    task_data = {
        "task_id": "info_baggage_basic_economy",

        "user_id": "user_005",
        "now": now,
        "opening_message": (
            "I'm flying on BK-I02 in basic economy. Do I get any free checked bags? How much to check a suitcase?"
        ),
        "user_simulator": {
            "personality": "Budget-conscious. Wants to weigh costs carefully.",
            "known_info": [
                f"Your user ID: {user_id}",
                "Booking ID is BK-I02",
                "Basic economy fare",
                "Basic loyalty tier",
            ],
            "unknown_info": [
                "0 free checked bags on basic economy",
                "Checked bag fee is $50 per bag for basic economy",
                "Still gets 1 free carry-on",
            ],
            "task_rules": [
                "Ask your question about baggage allowance for basic economy.",
                "When the agent provides the information, ask if there's any way to get free bags (loyalty upgrade, etc.).",
                "When you have complete information, end with [TASK_DONE].",
            ],
        },
        "task_summary": "User asks what baggage they get on a basic economy booking and what a checked suitcase would cost.\nThe evaluator should check that the agent explains there are no free checked bags, states the $50 checked-bag fee, and mentions the carry-on allowance.",
        "task_requirements": [
            {
                "id": "state_no_free_checked_bags",
                "kind": "must",
                "requirement": "Agent must state that this basic economy booking includes 0 free checked bags.",
                "evidence": "conversation",
            },
            {
                "id": "state_checked_bag_fee",
                "kind": "must",
                "requirement": "Agent must state that checking a bag costs $50 per bag on this booking.",
                "evidence": "conversation",
            },
            {
                "id": "state_carry_on_allowance",
                "kind": "must",
                "requirement": "Agent must state that the user still gets 1 free carry-on.",
                "evidence": "conversation",
            },
        ],
        "_replay_trace": [],
    }

    return [flight], [booking], task_data


def scenario_I03() -> tuple[list[Flight], list[Booking], dict]:
    """I03: Cancel policy explanation — business domestic cancel fee is 5%.

    user_001 (Emma, gold) has a business domestic booking. Wants to know the
    cancellation policy and exact fee. Business domestic = 5% of price paid.
    """
    now = DEFAULT_NOW
    user_id = "user_001"

    flight = build_flight(
        airline_code="DL",
        origin="ATL",
        destination="ORD",
        date="2026-06-22",
        time_range="morning",
        economy_price=320,
        business_price=800,
    )

    booking = build_booking(
        user_id="user_001",
        flight=flight,
        cabin_class="business",
        booked_days_ago=5,
        now=now,
        booking_id="BK-I03",
        has_insurance=False,
    )
    # Business domestic: 5% of $800 = $40 fee, $760 refund

    task_data = {
        "task_id": "info_cancel_policy_explanation",

        "user_id": "user_001",
        "now": now,
        "opening_message": (
            "Before I decide anything, can you explain the cancellation policy for my "
            "business class booking BK-I03? What would I be charged?"
        ),
        "user_simulator": {
            "personality": "Cautious planner. Asks about policies before taking action.",
            "known_info": [
                f"Your user ID: {user_id}",
                "Booking ID is BK-I03",
                "Business class domestic flight",
                "Price paid was around $800",
            ],
            "unknown_info": [
                "Business domestic cancellation fee is 5%",
                "The exact fee is $40 on an $800 booking",
                "Business class gets free changes as an alternative",
            ],
            "task_rules": [
                "Ask your question about the cancellation policy.",
                "When the agent provides the fee, ask about the refund amount.",
                "Ask if there are alternatives to cancellation (like changing instead).",
                "When you have complete information, end with [TASK_DONE].",
            ],
        },
        "task_summary": "User asks for the cancellation policy on an existing business-class domestic booking before deciding what to do.\nThe evaluator should check that the agent states the 5% fee rule, gives the exact $40 fee and $760 refund for this booking, and mentions that business class also allows free changes.",
        "task_requirements": [
            {
                "id": "state_fee_formula",
                "kind": "must",
                "requirement": "Agent must explain that business-class domestic cancellation uses a 5% fee formula.",
                "evidence": "conversation",
            },
            {
                "id": "state_exact_fee_and_refund",
                "kind": "must",
                "requirement": "Agent must state that this $800 booking would have a $40 cancellation fee and a $760 refund.",
                "evidence": "conversation",
            },
            {
                "id": "state_business_change_alternative",
                "kind": "must",
                "requirement": "Agent must mention that business class bookings can be changed for free as an alternative to cancellation.",
                "evidence": "conversation",
            },
            {
                "id": "no_cancel_action",
                "kind": "must_not",
                "requirement": "Agent must not cancel the booking in this information-only policy explanation task.",
                "evidence": "conversation_or_tool_calls",
            },
        ],
        "_replay_trace": [],
    }

    return [flight], [booking], task_data


def scenario_I04() -> tuple[list[Flight], list[Booking], dict]:
    """I04: Change vs cancel+rebook cost comparison with concrete numbers.

    user_004 (Noah, silver) has an economy domestic booking. Wants to compare:
    - Change fee: $150 (economy, <=7 days, personal)
    - Cancel+rebook: cancel fee ($50 or 15%) + new ticket price - refund
    Agent must run the numbers both ways.
    """
    now = DEFAULT_NOW
    user_id = "user_004"

    current_flight = build_flight(
        airline_code="WN",
        origin="SEA",
        destination="DFW",
        date="2026-06-19",
        time_range="morning",
        economy_price=340,
        business_price=850,
    )

    # Alternative flight at a different price
    alt_flight = build_flight(
        airline_code="WN",
        origin="SEA",
        destination="DFW",
        date="2026-06-22",
        time_range="afternoon",
        economy_price=300,
        business_price=780,
    )

    booking = build_booking(
        user_id="user_004",
        flight=current_flight,
        cabin_class="economy",
        booked_days_ago=5,
        now=now,
        booking_id="BK-I04",
        has_insurance=False,
    )

    # Change path: $150 fee + fare difference ($300 - $340 = -$40, so $0 extra) = $150 total
    # Cancel+rebook path: cancel fee = max($50, 15% of $340) = max($50, $51) = $51
    #   Refund = $340 - $51 = $289. New ticket = $300. Out of pocket = $300 - $289 = $11 + $51 fee = $62 total
    # Cancel+rebook is cheaper ($62 vs $150)

    task_data = {
        "task_id": "info_change_vs_cancel_tradeoff",

        "user_id": "user_004",
        "now": now,
        "opening_message": (
            "I want to move my trip from June 19 to June 22. I have booking BK-I04. "
            "What's cheaper — changing the flight or cancelling and rebooking?"
        ),
        "user_simulator": {
            "personality": "Analytical and numbers-driven. Wants a clear comparison.",
            "known_info": [
                f"Your user ID: {user_id}",
                "Booking ID is BK-I04",
                "Wants to move to June 22",
                "Current booking is economy domestic",
            ],
            "unknown_info": [
                "Change fee is $150",
                "Cancel fee is $51",
                "The exact cost comparison between the two options",
            ],
            "task_rules": [
                "Ask your question about change vs cancel+rebook costs.",
                "When the agent provides one option's cost, ask about the other for comparison.",
                "Ask which option the agent recommends and why.",
                "Do NOT ask the agent to cancel, change, or rebook anything in this conversation.",
                "If the agent offers to execute a cancellation or rebooking, say you only wanted the comparison and are not ready to take action.",
                "When you have complete information with both numbers, end with [TASK_DONE].",
            ],
        },
        "task_summary": "User wants an information-only comparison between changing a booking and canceling plus rebooking.\nThe evaluator should check that the agent gives both cost paths, identifies the cheaper option, and does not execute any booking action.",
        "task_requirements": [
            {
                "id": "compare_change_cost",
                "kind": "must",
                "requirement": "Agent must explain that changing the booking costs $150 total.",
                "evidence": "conversation",
            },
            {
                "id": "compare_cancel_rebook_cost",
                "kind": "must",
                "requirement": "Agent must explain that canceling and rebooking has a $51 cancellation fee, a $289 refund, a $300 replacement ticket, and $11 net additional cost after the refund.",
                "evidence": "conversation",
            },
            {
                "id": "compare_recommend_cheaper_path",
                "kind": "must",
                "requirement": "Agent must make clear that canceling and rebooking is cheaper than changing.",
                "evidence": "conversation",
            },
            {
                "id": "compare_no_action",
                "kind": "must_not",
                "requirement": "Agent must not cancel, change, or rebook anything for this information-only comparison task.",
                "evidence": "conversation_or_tool_calls",
            },
        ],
        "_replay_trace": [],
    }

    return [current_flight, alt_flight], [booking], task_data


def scenario_I05() -> tuple[list[Flight], list[Booking], dict]:
    """I05: Loyalty points value — 75k pts = $750 domestic / $1125 international.

    user_001 (Emma, gold, 75000 points) asks about the value of her points.
    Domestic: 75000 * $0.01 = $750. International: 75000 * $0.015 = $1125.
    """
    now = DEFAULT_NOW
    user_id = "user_001"

    task_data = {
        "task_id": "info_loyalty_points_value",

        "user_id": "user_001",
        "now": now,
        "opening_message": ("I have 75,000 loyalty points. How much are they worth? Can I use them for a flight?"),
        "user_simulator": {
            "personality": "Curious and planning ahead. Wants to understand the system.",
            "known_info": [
                f"Your user ID: {user_id}",
                "Has 75,000 loyalty points",
                "Gold loyalty tier",
            ],
            "unknown_info": [
                "Domestic rate: $0.01/point = $750",
                "International rate: $0.015/point = $1,125",
                "Minimum 1,000 points to redeem",
                "Points rounded to nearest 100",
            ],
            "task_rules": [
                "Ask your question about loyalty points value.",
                "When the agent provides the domestic value, ask about international value too.",
                "Ask about any minimum redemption requirements.",
                "Do NOT ask the agent to search for flights or book anything in this conversation.",
                "When you have complete information, end with [TASK_DONE].",
            ],
        },
        "task_summary": "User asks how much 75,000 loyalty points are worth for domestic and international travel.\nThe evaluator should check that the agent gives both redemption values and explains the minimum redemption size and points-rounding rule.",
        "task_requirements": [
            {
                "id": "state_domestic_value",
                "kind": "must",
                "requirement": "Agent must explain that at the domestic rate of $0.01 per point, 75,000 points are worth $750.",
                "evidence": "conversation",
            },
            {
                "id": "state_international_value",
                "kind": "must",
                "requirement": "Agent must explain that at the international rate of $0.015 per point, 75,000 points are worth $1,125.",
                "evidence": "conversation",
            },
            {
                "id": "state_minimum_redemption",
                "kind": "must",
                "requirement": "Agent must mention that the minimum redemption is 1,000 points.",
                "evidence": "conversation",
            },
            {
                "id": "state_rounding_rule",
                "kind": "must",
                "requirement": "Agent must mention that redeemed points are rounded to the nearest 100.",
                "evidence": "conversation",
            },
            {
                "id": "no_booking_action",
                "kind": "must_not",
                "requirement": "Agent must not search for flights or make a booking in this information-only points-value task.",
                "evidence": "conversation_or_tool_calls",
            },
        ],
        "_replay_trace": [],
    }

    # No flights or bookings needed for a pure points inquiry
    return [], [], task_data


def scenario_I06() -> tuple[list[Flight], list[Booking], dict]:
    """I06: Upgrade options and pricing from economy.

    user_002 (Liam, basic) has an economy booking and wants to know what
    upgrade paths exist and their costs.
    """
    now = DEFAULT_NOW
    user_id = "user_002"

    flight = build_flight(
        airline_code="UA",
        origin="LAX",
        destination="SFO",
        date="2026-06-20",
        time_range="afternoon",
        economy_price=280,
        business_price=700,
    )
    flight.cabin_prices["first"] = 1260  # for reference

    booking = build_booking(
        user_id="user_002",
        flight=flight,
        cabin_class="economy",
        booked_days_ago=3,
        now=now,
        booking_id="BK-I06",
    )

    # Economy->business: 2.5x * $280 = $700, fare diff = $420
    # Economy->first: blocked (must go through business)
    # Business->first: 1.8x * $700 = $1260, fare diff = $560

    task_data = {
        "task_id": "info_upgrade_options",

        "user_id": "user_002",
        "now": now,
        "opening_message": (
            "I'm on booking BK-I06 in economy. What are my upgrade options? Can I go "
            "to business or first class, and how much would each cost?"
        ),
        "user_simulator": {
            "personality": "Curious but budget-aware. Wants to know all options before deciding.",
            "known_info": [
                f"Your user ID: {user_id}",
                "Booking ID is BK-I06",
                "Currently in economy",
                "Wants to see all upgrade options",
            ],
            "unknown_info": [
                "Economy->business costs $420",
                "Economy->first is not directly available",
                "Must go economy->business->first if wants first class",
                "Total to reach first would be $420 + $560 = $980",
            ],
            "task_rules": [
                "Ask your question about upgrade options from economy.",
                "When the agent provides economy-to-business cost, ask about first class.",
                "When the agent explains the two-step requirement, ask for the total cost to reach first.",
                "Do NOT ask for cheaper upgrade options, special deals, point redemptions, or for the agent to execute any upgrade.",
                "If the agent asks whether you want to proceed with an upgrade, say you only wanted the pricing and rules.",
                "When you have complete information, end with [TASK_DONE].",
            ],
        },
        "task_summary": "User asks what upgrade options exist from an economy booking and how much each path would cost.\nThe evaluator should check that the agent explains the economy-to-business cost, says economy cannot upgrade directly to first class, and gives the business-to-first cost or total path to first.",
        "task_requirements": [
            {
                "id": "state_economy_to_business_cost",
                "kind": "must",
                "requirement": "Agent must explain that upgrading from economy to business costs $420 on this booking.",
                "evidence": "conversation",
            },
            {
                "id": "state_no_direct_economy_to_first",
                "kind": "must",
                "requirement": "Agent must explain that economy cannot upgrade directly to first class and must go through business first.",
                "evidence": "conversation",
            },
            {
                "id": "state_first_path_cost",
                "kind": "must",
                "requirement": "Agent must explain that business to first would cost $560 more, or equivalently that the total additional cost to reach first from the current booking is $980.",
                "evidence": "conversation",
            },
            {
                "id": "no_upgrade_action",
                "kind": "must_not",
                "requirement": "Agent must not execute any upgrade in this information-only pricing task.",
                "evidence": "conversation_or_tool_calls",
            },
        ],
        "_replay_trace": [],
    }

    return [flight], [booking], task_data


def scenario_I07() -> tuple[list[Flight], list[Booking], dict]:
    """I07: Hotel cancellation policies — standard vs suite.

    user_003 (Olivia, platinum) has TWO hotel reservations: one standard room and
    one suite. Different cancellation policies apply. Pure informational.
    """
    now = DEFAULT_NOW
    user_id = "user_003"

    # Standard hotel — check-in is 5 days away (well over 48h = free cancel)
    hotel_standard = build_hotel(
        user_id="user_003",
        city="Chicago",
        check_in="2026-06-20",
        check_out="2026-06-23",
        room_type="standard",
        nightly_rate=180,
        reservation_id="HR-I07A",
        booked_days_ago=10,
        now=now,
    )

    # Suite hotel — non-refundable regardless of timing
    hotel_suite = build_hotel(
        user_id="user_003",
        city="Chicago",
        check_in="2026-06-20",
        check_out="2026-06-22",
        room_type="suite",
        nightly_rate=350,
        reservation_id="HR-I07B",
        booked_days_ago=10,
        now=now,
    )

    # Standard: 5 days out > 48h → free cancel, refund $540 (3 nights * $180)
    # Suite: non-refundable, fee = $700 (2 nights * $350), refund $0

    task_data = {
        "task_id": "info_hotel_cancel_policies",

        "user_id": "user_003",
        "now": now,
        "_hotels": [hotel_standard, hotel_suite],
        "opening_message": (
            "I have two hotel reservations in Chicago — HR-I07A and HR-I07B. "
            "What are the cancellation policies for each? I might need to cancel one."
        ),
        "user_simulator": {
            "personality": "Thorough. Wants to understand all the details before deciding.",
            "known_info": [
                f"Your user ID: {user_id}",
                "Reservation IDs are HR-I07A and HR-I07B",
                "Both are in Chicago for June 20",
                "One is a standard room, one is a suite",
            ],
            "unknown_info": [
                "Standard room: free cancellation since it's 5 days out",
                "Suite: non-refundable regardless of timing",
                "The tiered cancellation rules for standard rooms",
            ],
            "task_rules": [
                "Ask your question about hotel cancellation policies for both reservations.",
                "When the agent provides one policy, ask about the other.",
                "Ask about the general timing tiers for standard room cancellations.",
                "Do NOT ask the agent to cancel either reservation in this conversation; you only want the policy information.",
                "When you have complete information for both, end with [TASK_DONE].",
            ],
        },
        "task_summary": "User asks for the cancellation policies on two hotel reservations, one standard and one suite, before deciding what to do.\nThe evaluator should check that the agent correctly explains the standard-room policy, the suite non-refundable policy, and the general timing tiers for standard-room cancellations.",
        "task_requirements": [
            {
                "id": "state_standard_policy",
                "kind": "must",
                "requirement": "Agent must explain that reservation HR-I07A is a standard room with the standard time-based cancellation policy, including that cancelling more than 48 hours before check-in is free.",
                "evidence": "conversation",
            },
            {
                "id": "state_suite_policy",
                "kind": "must",
                "requirement": "Agent must explain that reservation HR-I07B is a suite booking and is non-refundable regardless of timing.",
                "evidence": "conversation",
            },
            {
                "id": "state_standard_tiers",
                "kind": "must",
                "requirement": "Agent must explain the standard-room cancellation tiers: 48 or more hours is free, 24 to 48 hours is 50% of the first night, and under 24 hours is the full first night.",
                "evidence": "conversation",
            },
            {
                "id": "no_hotel_cancel_action",
                "kind": "must_not",
                "requirement": "Agent must not cancel either hotel reservation in this information-only policy task.",
                "evidence": "conversation_or_tool_calls",
            },
        ],
        "_replay_trace": [],
    }

    return [], [], task_data


def scenario_I08() -> tuple[list[Flight], list[Booking], dict]:
    """I08: Delay compensation rights — explain all 3 tiers.

    user_004 (Noah, silver) asks about delay compensation rules in general.
    Agent must explain all three tiers: <120min (nothing), 120-239min (meal voucher),
    240+ min (full: rebook + meal + hotel).
    """
    now = DEFAULT_NOW
    user_id = "user_004"

    # Give the user a booking so they have context for the question
    flight = build_flight(
        airline_code="WN",
        origin="DEN",
        destination="SFO",
        date="2026-06-18",
        time_range="morning",
        economy_price=290,
        business_price=730,
    )

    booking = build_booking(
        user_id="user_004",
        flight=flight,
        cabin_class="economy",
        booked_days_ago=4,
        now=now,
        booking_id="BK-I08",
    )

    task_data = {
        "task_id": "info_delay_rights",

        "user_id": "user_004",
        "now": now,
        "opening_message": (
            "I have an upcoming flight BK-I08. I want to be prepared — what are my "
            "rights if the flight gets delayed? What compensation tiers exist?"
        ),
        "user_simulator": {
            "personality": "Proactive planner. Wants to know rights before anything happens.",
            "known_info": [
                f"Your user ID: {user_id}",
                "Has booking BK-I08",
                "Flight is currently on time",
                "Wants to know about delay compensation",
            ],
            "unknown_info": [
                "Under 120min: no compensation",
                "120-239min: $25 meal voucher",
                "240+ min: rebook + meal + hotel",
                "The exact threshold boundaries",
            ],
            "task_rules": [
                "Ask your question about delay compensation tiers.",
                "When the agent provides the tiers, ask for the exact minute thresholds.",
                "Ask whether the compensation applies equally regardless of cabin class or loyalty.",
                "Do NOT ask the agent to issue compensation, change the booking, or take any action; this is informational only.",
                "When you have complete information, end with [TASK_DONE].",
            ],
        },
        "task_summary": "User asks for a general explanation of delay-compensation rights before travel.\nThe evaluator should check that the agent describes all three compensation tiers with the correct minute thresholds and keeps the interaction informational only.",
        "task_requirements": [
            {
                "id": "state_under_120",
                "kind": "must",
                "requirement": "Agent must explain that delays under 120 minutes do not qualify for compensation.",
                "evidence": "conversation",
            },
            {
                "id": "state_120_to_239",
                "kind": "must",
                "requirement": "Agent must explain that delays from 120 to 239 minutes qualify for a $25 meal voucher.",
                "evidence": "conversation",
            },
            {
                "id": "state_240_plus",
                "kind": "must",
                "requirement": "Agent must explain that delays of 240 minutes or more qualify for the full package, including rebooking plus a meal voucher and hotel accommodation if needed overnight.",
                "evidence": "conversation",
            },
            {
                "id": "no_delay_action",
                "kind": "must_not",
                "requirement": "Agent must not issue compensation or modify the booking in this general information task.",
                "evidence": "conversation_or_tool_calls",
            },
        ],
        "_replay_trace": [],
    }

    return [flight], [booking], task_data


SCENARIOS = [
    scenario_I01,
    scenario_I02,
    scenario_I03,
    scenario_I04,
    scenario_I05,
    scenario_I06,
    scenario_I07,
    scenario_I08,
]
