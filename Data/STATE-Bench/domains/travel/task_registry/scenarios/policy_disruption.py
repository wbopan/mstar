"""Travel policy scenarios about disruption handling and compensation."""


from __future__ import annotations



from domains.travel.schemas import Booking, Flight

from domains.travel.task_registry._builders import (
    DEFAULT_NOW,
    build_booking,
    build_flight,
)


def scenario_PR06() -> tuple[list[Flight], list[Booking], dict]:
    """PR06: TWO flights delayed. One 90min (under threshold), one 150min (meal voucher).

    user_004 (Noah, silver) has two flights today. Agent must check delay status for
    each and apply different compensation rules: 90min = nothing, 150min = $25 meal voucher.
    """
    now = DEFAULT_NOW
    user_id = "user_004"

    # Flight 1: 90min delay (under threshold)
    flight1 = build_flight(
        airline_code="WN",
        origin="DEN",
        destination="ATL",
        date="2026-06-15",
        time_range="morning",
        economy_price=310,
        business_price=780,
        status="delayed",
        delay_minutes=90,
    )

    booking1 = build_booking(
        user_id="user_004",
        flight=flight1,
        cabin_class="economy",
        booked_days_ago=6,
        now=now,
        booking_id="BK-PR06a",
    )

    # Flight 2: 150min delay (qualifies for meal voucher)
    flight2 = build_flight(
        airline_code="WN",
        origin="ATL",
        destination="MIA",
        date="2026-06-15",
        time_range="afternoon",
        economy_price=250,
        business_price=625,
        status="delayed",
        delay_minutes=150,
    )

    booking2 = build_booking(
        user_id="user_004",
        flight=flight2,
        cabin_class="economy",
        booked_days_ago=6,
        now=now,
        booking_id="BK-PR06b",
    )

    task_data = {
        "task_id": "policy_delay_under_threshold",

        "user_id": "user_004",
        "now": now,
        "opening_message": ("Both my flights today are delayed. I'd like to know what compensation I can get."),
        "user_simulator": {
            "personality": "Somewhat impatient but ultimately accepts policy. Asks follow-up questions.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"Flight 1 booking: BK-PR06a ({flight1.origin}→{flight1.destination})",
                f"Flight 2 booking: BK-PR06b ({flight2.origin}→{flight2.destination})",
                "Both flights are delayed today",
                "This task is about understanding compensation eligibility, not claiming the voucher",
            ],
            "unknown_info": [
                "Flight 1 is delayed only 90 minutes (under threshold)",
                "Flight 2 is delayed 150 minutes (above threshold)",
                "Only flight 2 qualifies for a $25 meal voucher",
                "The threshold tiers are 120min and 240min",
            ],
            "task_rules": [
                "When the agent asks for booking IDs, provide both.",
                "When the agent reports the delay durations, ask what compensation you get for each.",
                "If the agent gives a blanket answer for both, push back and ask them to check each separately.",
                "When the agent says only one qualifies, ask what the minimum delay threshold is.",
                "Do not ask the agent to issue or claim the voucher. Keep this conversation at the policy/eligibility level only.",
                "When both are explained with correct compensation, accept the situation.",
                "End with [TASK_DONE] once the policy is clear for both flights.",
            ],
        },
        "task_summary": "User asks about compensation on two delayed flights with different delay lengths.\nThe evaluator should check that the agent distinguishes the 90-minute no-compensation case from the 150-minute meal-voucher case, explains the threshold logic, and keeps the interaction informational only.",
        "task_requirements": [
            {
                "id": "state_first_flight_no_comp",
                "kind": "must",
                "requirement": "Agent must explain that the 90-minute delayed flight does not qualify for compensation because it is below the 120-minute threshold.",
                "evidence": "conversation",
            },
            {
                "id": "state_second_flight_meal_voucher",
                "kind": "must",
                "requirement": "Agent must explain that the 150-minute delayed flight qualifies for the $25 meal-voucher tier.",
                "evidence": "conversation",
            },
            {
                "id": "state_delay_thresholds",
                "kind": "must",
                "requirement": "Agent must explain that delay-compensation thresholds begin at 120 minutes and that higher full-compensation benefits require 240 minutes or more.",
                "evidence": "conversation",
            },
            {
                "id": "no_voucher_claim",
                "kind": "must_not",
                "requirement": "Agent must not issue or claim compensation in this eligibility-only task.",
                "evidence": "conversation_or_tool_calls",
            },
        ],
        "_replay_trace": [],
    }

    return [flight1, flight2], [booking1, booking2], task_data


def scenario_PR07() -> tuple[list[Flight], list[Booking], dict]:
    """PR07: Economy->first blocked + budget impossibility.

    user_004 (Noah, silver, $600 budget) has economy booking at $400.
    Wants first class. Direct economy→first is blocked (must go via business).
    Economy→business = 2.5x * $400 = $1000, fare diff = $600.
    Business→first = 1.8x * $1000 = $1800, fare diff = $800.
    Total upgrade: $1,400 — FAR over user's $600 budget.
    Even just economy→business ($600) equals the entire budget.
    Agent must explain the path AND the financial impossibility.
    """
    now = DEFAULT_NOW
    user_id = "user_004"

    flight = build_flight(
        airline_code="WN",
        origin="LAX",
        destination="JFK",
        date="2026-06-20",
        time_range="morning",
        economy_price=400,
        business_price=1000,
    )
    # Add first class pricing
    flight.cabin_prices["first"] = 1800

    booking = build_booking(
        user_id="user_004",
        flight=flight,
        cabin_class="economy",
        booked_days_ago=3,
        now=now,
        booking_id="BK-PR07",
    )

    # Economy->business: 2.5x * $400 = $1000, fare diff = $600
    # Business->first: 1.8x * $1000 = $1800, fare diff = $800
    # Total: $600 + $800 = $1400 — budget is only $600

    task_data = {
        "task_id": "policy_upgrade_path_blocked",

        "user_id": "user_004",
        "now": now,
        "opening_message": (
            "I have booking BK-PR07 in economy. I'd like to upgrade to first class. How much would that cost?"
        ),
        "user_simulator": {
            "personality": "Direct and numbers-focused. Wants costs laid out clearly.",
            "known_info": [
                f"Your user ID: {user_id}",
                "Booking ID is BK-PR07",
                "Currently in economy class",
                "Wants first class",
                "Maximum budget for upgrades is $600",
            ],
            "unknown_info": [
                "Direct economy-to-first upgrade is not available",
                "Must upgrade in two steps: economy→business, then business→first",
                "Economy→business costs $600, business→first costs $800",
                "Total $1,400 is way over budget",
            ],
            "task_rules": [
                "Ask to upgrade from economy to first class.",
                "When the agent says direct upgrade is blocked, ask what the alternative is.",
                "When the agent explains the two-step path, ask for the total cost breakdown.",
                "When the agent provides both costs ($600 + $800 = $1,400), mention your budget is $600.",
                "Ask if just the economy→business upgrade ($600) is possible within budget.",
                "When the agent confirms economy→business is $600, consider it but decide it's too expensive "
                "since it consumes the entire budget leaving nothing for the trip.",
                "Decide to stay in economy. End with [TASK_DONE].",
            ],
        },
        "task_summary": "User wants to go from an economy booking directly to first class while staying within a $600 budget.\nThe evaluator should check that the agent explains the blocked direct path, gives the two-step upgrade costs, and makes clear that even the intermediate options are not realistically within the user’s budget.",
        "task_requirements": [
            {
                "id": "state_no_direct_first_upgrade",
                "kind": "must",
                "requirement": "Agent must explain that the user cannot upgrade directly from economy to first class and would have to go through business first.",
                "evidence": "conversation",
            },
            {
                "id": "state_two_step_costs",
                "kind": "must",
                "requirement": "Agent must explain that economy to business costs $600 and business to first costs $800, for a total of $1,400 to reach first class from the current booking.",
                "evidence": "conversation",
            },
            {
                "id": "state_budget_conflict",
                "kind": "must",
                "requirement": "Agent must explain that the $1,400 total exceeds the user’s $600 budget and that even the economy-to-business step alone would consume the entire budget.",
                "evidence": "conversation",
            },
            {
                "id": "no_upgrade_action",
                "kind": "must_not",
                "requirement": "Agent must not execute any upgrade in this policy-and-pricing discussion task.",
                "evidence": "conversation_or_tool_calls",
            },
        ],
        "_replay_trace": [],
    }

    return [flight], [booking], task_data


def scenario_PR08() -> tuple[list[Flight], list[Booking], dict]:
    """PR08: Two bookings, different upgrade eligibility.

    user_005 (Ava, basic) has two bookings:
    - BK-PR08a: basic_economy (upgrade blocked entirely)
    - BK-PR08b: economy (upgrade available, economy→business = 2.5x)
    User asks about upgrading "both flights". Agent must check each and explain
    different rules apply.
    """
    now = DEFAULT_NOW
    user_id = "user_005"

    # Flight 1: basic economy
    flight1 = build_flight(
        airline_code="B6",
        origin="BOS",
        destination="MIA",
        date="2026-06-18",
        time_range="afternoon",
        economy_price=250,
        business_price=625,
    )
    flight1.cabin_prices["basic_economy"] = 150

    booking1 = build_booking(
        user_id="user_005",
        flight=flight1,
        cabin_class="basic_economy",
        booked_days_ago=5,
        now=now,
        booking_id="BK-PR08a",
    )

    # Flight 2: economy (upgrade eligible)
    flight2 = build_flight(
        airline_code="B6",
        origin="MIA",
        destination="BOS",
        date="2026-06-25",
        time_range="morning",
        economy_price=280,
        business_price=700,
    )

    booking2 = build_booking(
        user_id="user_005",
        flight=flight2,
        cabin_class="economy",
        booked_days_ago=5,
        now=now,
        booking_id="BK-PR08b",
    )

    # Economy→business for flight 2: 2.5x * $280 = $700, fare diff = $420

    task_data = {
        "task_id": "policy_upgrade_basic_blocked",

        "user_id": "user_005",
        "now": now,
        "opening_message": (
            "I have two upcoming flights and I'd like to upgrade both to business class. "
            "My bookings are BK-PR08a and BK-PR08b."
        ),
        "user_simulator": {
            "personality": "Friendly and hopeful. Accepts bad news gracefully.",
            "known_info": [
                f"Your user ID: {user_id}",
                "Booking BK-PR08a is basic economy (BOS→MIA)",
                "Booking BK-PR08b is economy (MIA→BOS)",
                "Budget is $700 maximum",
            ],
            "unknown_info": [
                "Basic economy fares cannot be upgraded",
                "Economy can be upgraded to business at 2.5x fare",
                "Upgrade cost for BK-PR08b",
            ],
            "task_rules": [
                "Ask about upgrading both bookings to business class.",
                "When the agent says BK-PR08a cannot be upgraded, ask why.",
                "When the agent explains basic economy restrictions, ask about BK-PR08b.",
                "When the agent quotes the upgrade cost for BK-PR08b, ask if it's within your $700 budget.",
                "If the cost is within budget, ask the agent to proceed with upgrading BK-PR08b only.",
                "When the upgrade is confirmed for BK-PR08b, end with [TASK_DONE].",
            ],
        },
        "task_summary": "User asks about upgrading two bookings, one basic economy and one regular economy, with a $700 budget.\nThe evaluator should check that the agent blocks the basic-economy upgrade, quotes the eligible economy-to-business upgrade correctly for the second booking, and frames the result against the user’s budget before proceeding only on the eligible booking.",
        "task_requirements": [
            {
                "id": "state_basic_blocked",
                "kind": "must",
                "requirement": "Agent must explain that booking BK-PR08a cannot be upgraded because it is a basic economy fare.",
                "evidence": "conversation",
            },
            {
                "id": "state_second_booking_upgrade_cost",
                "kind": "must",
                "requirement": "Agent must explain that booking BK-PR08b can be upgraded to business for a $420 fare difference.",
                "evidence": "conversation",
            },
            {
                "id": "state_budget_tradeoff",
                "kind": "must",
                "requirement": "Agent must explain that the $420 upgrade for BK-PR08b fits within the user’s $700 budget, while still making clear that only the second booking is eligible.",
                "evidence": "conversation",
            },
        ],
        "_replay_trace": [
            {
                "name": "update_booking",
                "arguments": {
                    "booking_id": "BK-PR08b",
                    "cabin_class": "business",
                },
            }
        ],
    }

    return [flight1, flight2], [booking1, booking2], task_data


def scenario_PR09() -> tuple[list[Flight], list[Booking], dict]:
    """PR09: Change reason affects fee — initially 'personal' ($150), then reveals jury duty ($0).

    user_002 (Liam, basic) has an economy domestic booking. Wants to change the flight.
    Initially says it's personal ($150 fee, <=7 days to departure). Then reveals it's
    actually for jury duty, which makes it a free change.
    """
    now = DEFAULT_NOW
    user_id = "user_002"
    flight_date = "2026-06-19"  # 4 days out => <=7 days => $150 base

    current_flight = build_flight(
        airline_code="UA",
        origin="SFO",
        destination="DEN",
        date=flight_date,
        time_range="morning",
        economy_price=320,
        business_price=800,
    )

    # Alternative flight
    alt_flight = build_flight(
        airline_code="UA",
        origin="SFO",
        destination="DEN",
        date="2026-06-22",
        time_range="afternoon",
        economy_price=290,
        business_price=750,
    )

    booking = build_booking(
        user_id="user_002",
        flight=current_flight,
        cabin_class="economy",
        booked_days_ago=5,
        now=now,
        booking_id="BK-PR09",
    )

    task_data = {
        "task_id": "policy_change_reason_affects_fee",

        "user_id": "user_002",
        "now": now,
        "opening_message": (
            "I need to change my flight BK-PR09. Something came up and I can't travel on the original date."
        ),
        "user_simulator": {
            "personality": "Initially vague about the reason, then forthcoming when prompted.",
            "known_info": [
                f"Your user ID: {user_id}",
                "Booking ID is BK-PR09",
                "Needs to change to a later date (June 22)",
                "The real reason is jury duty",
            ],
            "unknown_info": [
                "Personal reason fee is $150",
                "Jury duty qualifies for a free change",
                "The reason for the change matters for fee calculation",
            ],
            "task_rules": [
                "Ask to change your flight without specifying a reason.",
                "If the agent asks why, initially say 'personal reasons' or be vague.",
                "When the agent quotes a $150 fee, express concern about the cost.",
                "When pressed or when considering the fee, reveal 'actually, it's because I have jury duty that week'.",
                "When the agent recalculates to $0, confirm you'd like to proceed.",
                "When the change is processed or confirmed, end with [TASK_DONE].",
            ],
        },
        "task_summary": "User first frames a flight change as personal and later reveals the true reason is jury duty.\nThe evaluator should check that the agent first quotes the correct personal fee for this case, then updates the fee to zero when jury duty is disclosed, and does not keep applying the old fee afterward.",
        "task_requirements": [
            {
                "id": "quote_personal_fee_first",
                "kind": "must",
                "requirement": "Before the user reveals jury duty, the agent must explicitly quote the personal-reason change fee as $150 for this change request.",
                "evidence": "conversation",
            },
            {
                "id": "update_fee_after_jury_duty",
                "kind": "must",
                "requirement": "After the user reveals jury duty, the agent must explain that the change fee becomes $0 because jury duty is exempt.",
                "evidence": "conversation",
            },
            {
                "id": "must_not_keep_wrong_fee",
                "kind": "must_not",
                "requirement": "After the user reveals jury duty, the agent must not continue to claim that a $150 change fee still applies.",
                "evidence": "conversation",
            },
        ],
        "_replay_trace": [
            {
                "name": "update_booking",
                "arguments": {
                    "booking_id": "BK-PR09",
                    "flight_id": alt_flight.flight_id,
                    "change_reason": "jury_duty",
                },
            }
        ],
    }

    return [current_flight, alt_flight], [booking], task_data


def scenario_PR10() -> tuple[list[Flight], list[Booking], dict]:
    """PR10: Baggage + loyalty interaction — 3 bookings in different cabins.

    user_003 (Olivia, platinum) has 3 bookings:
    - BK-PR10a: economy (1 base + 3 platinum = 4 free)
    - BK-PR10b: business (2 base + 3 platinum = 5 free)
    - BK-PR10c: basic_economy (0 base + 3 platinum = 3 free, extra = $50/bag)
    User asks about bags for "all my flights". Agent must compute each separately.
    """
    now = DEFAULT_NOW
    user_id = "user_003"

    # Flight 1: economy
    flight1 = build_flight(
        airline_code="AA",
        origin="JFK",
        destination="LAX",
        date="2026-06-20",
        time_range="evening",
        economy_price=380,
        business_price=950,
    )
    booking1 = build_booking(
        user_id="user_003",
        flight=flight1,
        cabin_class="economy",
        booked_days_ago=7,
        now=now,
        booking_id="BK-PR10a",
    )

    # Flight 2: business
    flight2 = build_flight(
        airline_code="AA",
        origin="LAX",
        destination="ORD",
        date="2026-06-25",
        time_range="morning",
        economy_price=350,
        business_price=880,
    )
    booking2 = build_booking(
        user_id="user_003",
        flight=flight2,
        cabin_class="business",
        booked_days_ago=5,
        now=now,
        booking_id="BK-PR10b",
    )

    # Flight 3: basic economy
    flight3 = build_flight(
        airline_code="AA",
        origin="ORD",
        destination="JFK",
        date="2026-06-30",
        time_range="afternoon",
        economy_price=280,
        business_price=700,
    )
    flight3.cabin_prices["basic_economy"] = 150
    booking3 = build_booking(
        user_id="user_003",
        flight=flight3,
        cabin_class="basic_economy",
        booked_days_ago=3,
        now=now,
        booking_id="BK-PR10c",
    )

    task_data = {
        "task_id": "policy_baggage_loyalty_interaction",

        "user_id": "user_003",
        "now": now,
        "opening_message": (
            "I'm a platinum member and I have several upcoming flights. "
            "Can you tell me how many bags I can check for free on each one? "
            "I'm packing for a multi-city trip."
        ),
        "user_simulator": {
            "personality": "Experienced traveler. Wants precise numbers for planning.",
            "known_info": [
                f"Your user ID: {user_id}",
                "Has booking BK-PR10a (economy, JFK→LAX)",
                "Has booking BK-PR10b (business, LAX→ORD)",
                "Has booking BK-PR10c (basic economy, ORD→JFK)",
                "Is a platinum loyalty member",
                "Bringing different amounts of luggage on each leg",
            ],
            "unknown_info": [
                "Base checked bag allowance per cabin class",
                "Platinum bonus bags count",
                "Different extra bag fees for basic economy vs others",
            ],
            "task_rules": [
                "When the agent asks which booking you mean, say you want info for ALL your upcoming flights.",
                "If the agent gives a single answer, ask them to break it down per booking since each is in a different cabin.",
                "When the agent provides the breakdown, verify the total for the basic economy booking specifically.",
                "Ask about the extra bag fee — note it should be different for basic economy.",
                "Ask about oversized bags.",
                "When you have the full breakdown for all 3 bookings, end with [TASK_DONE].",
            ],
        },
        "task_summary": "A platinum member asks for checked-bag rules across three bookings in different cabin classes.\nThe evaluator should check that the agent gives a per-booking baggage breakdown, correctly applies the platinum bonus to each cabin, and explains the different extra-bag charges for basic economy versus the other bookings.",
        "task_requirements": [
            {
                "id": "state_per_booking_allowances",
                "kind": "must",
                "requirement": "Agent must explain that BK-PR10a allows 4 free checked bags, BK-PR10b allows 5 free checked bags, and BK-PR10c allows 3 free checked bags.",
                "evidence": "conversation",
            },
            {
                "id": "state_loyalty_breakdown",
                "kind": "must",
                "requirement": "Agent must make clear that these totals come from each cabin’s base allowance plus the platinum bonus of 3 additional checked bags.",
                "evidence": "conversation",
            },
            {
                "id": "state_extra_bag_fees",
                "kind": "must",
                "requirement": "Agent must explain that extra checked bags cost $35 on BK-PR10a and BK-PR10b, but $50 on the basic-economy booking BK-PR10c.",
                "evidence": "conversation",
            },
            {
                "id": "state_carry_on_or_oversize",
                "kind": "must",
                "requirement": "Agent must mention either that each booking still includes one carry-on or that oversized bags cost $100 each.",
                "evidence": "conversation",
            },
        ],
        "_replay_trace": [],
    }

    return [flight1, flight2, flight3], [booking1, booking2, booking3], task_data


SCENARIOS = [
    scenario_PR06,
    scenario_PR07,
    scenario_PR08,
    scenario_PR09,
    scenario_PR10,
]
