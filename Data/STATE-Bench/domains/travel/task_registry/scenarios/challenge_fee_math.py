"""Travel challenge scenarios centered on fee math and repricing."""


from __future__ import annotations


from domains.travel.schemas import Booking, Flight

from domains.travel.task_registry._builders import (
    _USERS_BY_ID,
    DEFAULT_NOW,
    build_booking,
    build_flight,
    build_route_flights,
)


def build_challenge_task():
    """Challenge: Two flight changes with interrelated fee calculations.

    Setup:
    - Booking A: economy international JFK→LHR, $900, departing June 19 (4 days out = ≤7 days).
      Change reason: medical. Fee = 50% of $200 (intl economy ≤7d base) = $100.
      New flight is $950 → fare diff = $50. Total cost for change A: $100 fee + $50 diff = $150.

    - Booking B: economy domestic ORD→SFO, $400, departing June 22 (7 days out = ≤7 days).
      Change reason: personal. Fee = $150 (domestic economy ≤7d).
      New flight is $380 → fare diff = -$20 (cheaper, but no refund on fare diff).
      Total cost for change B: $150 fee + $0 diff (no refund for cheaper flight) = $150.

    The catch: The user has a $250 total budget for BOTH changes combined.
    Change A costs $150, Change B costs $150 → total $300. Over budget!

    The user asks the agent to figure out both costs, realize they're over budget,
    and suggest which change to prioritize. The medical change should be prioritized
    (50% discount makes it cheaper). The agent must explain the trade-off.

    If the agent gets either fee wrong, the budget analysis is wrong.
    If the agent doesn't know fare diff rules, it's wrong.
    If the agent doesn't realize ≤7 days applies to BOTH, it's wrong.
    """
    user_id = "user_001"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW  # 2026-06-15T10:00:00

    # --- Booking A: JFK → LHR, international economy, June 19 ---
    flight_a = build_flight(
        "BA",
        "JFK",
        "LHR",
        "2026-06-19",
        "morning",
        economy_price=900,
        business_price=2250,
    )
    booking_a = build_booking(
        user_id,
        flight_a,
        cabin_class="economy",
        booked_days_ago=14,
        now=now,
    )

    # Alternative flight for A: June 21, slightly more expensive
    alt_a, alt_a_flights = build_route_flights(
        "JFK",
        "LHR",
        "2026-06-21",
        target_airline="BA",
        target_time="morning",
        target_economy_price=950,
        target_business_price=2375,
        num_distractors=2,
        seed=888,
    )

    # --- Booking B: ORD → SFO, domestic economy, June 22 ---
    flight_b = build_flight(
        "UA",
        "ORD",
        "SFO",
        "2026-06-22",
        "afternoon",
        economy_price=400,
        business_price=1000,
    )
    booking_b = build_booking(
        user_id,
        flight_b,
        cabin_class="economy",
        booked_days_ago=14,
        now=now,
    )

    # Alternative flight for B: June 25, slightly cheaper
    alt_b, alt_b_flights = build_route_flights(
        "ORD",
        "SFO",
        "2026-06-25",
        target_airline="UA",
        target_time="afternoon",
        target_economy_price=380,
        target_business_price=950,
        num_distractors=2,
        seed=889,
    )

    all_flights = [flight_a, flight_b] + alt_a_flights + alt_b_flights

    # Fee math:
    # Booking A (JFK→LHR, intl economy, June 19, 4 days out):
    #   Base change fee (intl economy, ≤7 days): $200
    #   Medical discount: 50% → $100
    #   Fare diff: $950 - $900 = $50
    #   Total cost A: $100 + $50 = $150
    #
    # Booking B (ORD→SFO, domestic economy, June 22, 7 days out):
    #   Base change fee (domestic economy, ≤7 days): $150
    #   Personal reason: no discount → $150
    #   Fare diff: $380 - $400 = -$20 (cheaper flight, no refund on diff)
    #   Total cost B: $150 + $0 = $150
    #
    # Combined: $150 + $150 = $300 > $250 budget
    # Recommendation: prioritize A (medical, $150) since it has the discount
    #   If only A: $150 ≤ $250 ✓
    #   If only B: $150 ≤ $250 ✓
    #   Both: $300 > $250 ✗

    booking_a_id = booking_a.booking_id
    booking_b_id = booking_b.booking_id

    task_data = {
        "task_id": "challenge_chained_changes",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            f"I need to change two of my flights. Booking {booking_a_id} to London needs to move "
            f"to June 21 — I have a medical reason. And booking {booking_b_id} to San Francisco "
            f"needs to move to June 25 for personal reasons. My total budget for both changes is $250."
        ),
        "user_simulator": {
            "personality": "Organized and cost-conscious. Provides all info upfront. Wants exact numbers before deciding.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"Booking A: {booking_a_id} (JFK→LHR, economy, June 19) — needs to move to June 21, medical reason",
                f"Booking B: {booking_b_id} (ORD→SFO, economy, June 22) — needs to move to June 25, personal reason",
                "Total budget for both changes combined: $250",
                "Medical reason for booking A is genuine",
            ],
            "unknown_info": [
                "Exact change fee formulas",
                "Whether medical gets a discount",
                "Fare differences for the new flights",
                "Whether both changes fit under $250",
            ],
            "task_rules": [
                f"Provide both booking IDs ({booking_a_id} and {booking_b_id}) and change reasons upfront in the opening message.",
                "When the agent calculates fees for each change, ask 'What's the total for both changes combined?'",
                "If the total exceeds $250, ask which one the agent recommends doing first.",
                "If the agent recommends prioritizing the medical change, agree: 'Let's do the medical one.'",
                "If the agent tries to execute both changes without mentioning the budget issue, say 'Wait — will both fit under my $250 budget?'",
                "After the recommended change is executed, ask if there's any way to reduce the cost of the second change.",
                "When the agent confirms there's no discount available for the personal change, accept it and say you'll hold off on that one.",
                "End with [TASK_DONE].",
            ],
        },
        "_replay_trace": [
            {
                "name": "update_booking",
                "arguments": {
                    "booking_id": booking_a_id,
                    "flight_id": alt_a.flight_id,
                    "change_reason": "medical",
                },
            }
        ],
        "task_summary": (
            "User needs to change two bookings under a shared $250 budget, but only one can be afforded.\n"
            "The evaluator should check that the agent computes both change costs correctly, recognizes the combined total is over budget, and recommends executing only the medical booking instead of trying to change both."
        ),
        "task_requirements": [
            {
                "id": "state_both_changes_priced_correctly",
                "kind": "must",
                "requirement": "Agent must compute that each change costs $150, with the London medical change using a discounted $100 fee plus $50 fare difference and the San Francisco personal change costing $150 with no refund for the cheaper replacement flight.",
                "evidence": "conversation",
            },
            {
                "id": "state_budget_tradeoff_explained",
                "kind": "must",
                "requirement": "Agent must explain that both changes together total $300 and therefore exceed the $250 budget.",
                "evidence": "conversation",
            },
            {
                "id": "state_medical_change_prioritized",
                "kind": "must",
                "requirement": "Agent must recommend prioritizing and executing the medical London change rather than proceeding with both changes.",
                "evidence": "conversation",
            },
        ],
    }

    return all_flights, [booking_a, booking_b], task_data


def build_challenge_2():
    """Challenge 2: Basic economy insurance cancel+rebook workaround discovery.

    Setup:
    - user_004 (Noah, silver, 15k points, add_insurance=True) has a basic_economy
      booking LAX→DFW on June 20, $175, booked 5 days ago.
    - Basic economy: can't change, can't cancel normally.
    - BUT insurance overrides cancellation → $0 fee, full $175 refund.
    - Agent must discover: (1) basic_economy blocks change, (2) insurance allows
      free cancellation, (3) cancel+rebook workaround, (4) rebook with points_plus_cash
      under a $100 cash budget.

    Alternative flights on June 23:
    - DL nonstop: economy $280 → 15k pts covers $150, $130 cash remainder > $100 (OVER)
    - AS 1-stop: economy $240 → 15k pts covers $150, $90 cash remainder ≤ $100 (FITS)

    The agent must chain three discoveries:
    1. basic_economy can't be changed
    2. insurance overrides cancellation restriction for basic_economy
    3. points_plus_cash math under budget constraint
    """
    user_id = "user_004"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW  # 2026-06-15T10:00:00

    # --- Original booking: basic_economy LAX→DFW, June 20, $175 ---
    orig_flight = build_flight(
        "WN",
        "LAX",
        "DFW",
        "2026-06-20",
        "morning",
        economy_price=250,
        business_price=625,
    )
    orig_flight.cabin_prices["basic_economy"] = 175

    booking = build_booking(
        user_id,
        orig_flight,
        cabin_class="basic_economy",
        booked_days_ago=5,
        now=now,
        has_insurance=True,
    )

    # --- Alternative flights on June 23: LAX→DFW ---
    # Target: DL nonstop $280 economy (over budget with points)
    target_alt, alt_flights = build_route_flights(
        "LAX",
        "DFW",
        "2026-06-23",
        target_airline="DL",
        target_time="morning",
        target_economy_price=280,
        target_business_price=700,
        target_stops=0,
        num_distractors=2,
        seed=920,
    )

    # Cheap alternative: AS 1-stop $240 economy (fits budget with points)
    cheap_alt = build_flight(
        "AS",
        "LAX",
        "DFW",
        "2026-06-23",
        "afternoon",
        economy_price=240,
        business_price=600,
        stops=1,
    )
    alt_flights.append(cheap_alt)

    all_flights = [orig_flight] + alt_flights
    booking_id = booking.booking_id

    # Fee/points math:
    # Cancel: insurance → $0 fee, $175 refund
    # Rebook option 1 (DL nonstop $280):
    #   15,000 pts × $0.01 = $150 value
    #   Cash remainder: $280 - $150 = $130 > $100 budget (OVER)
    # Rebook option 2 (AS 1-stop $240):
    #   15,000 pts × $0.01 = $150 value
    #   Cash remainder: $240 - $150 = $90 ≤ $100 budget (FITS)

    task_data = {
        "task_id": "challenge_insurance_cancel_rebook",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            f"Hi, I need to change my flight {booking_id} to June 23 instead. "
            f"I have about $100 to work with for any fees or price differences."
        ),
        "user_simulator": {
            "personality": (
                "Practical and budget-conscious. Doesn't know airline policies well. "
                "Trusts the agent to find solutions."
            ),
            "known_info": [
                f"Your user ID: {user_id}",
                f"Booking ID: {booking_id} (LAX→DFW, June 20)",
                "Wants to move the flight to June 23",
                "Has about $100 cash budget for this change",
                "Has travel insurance on this booking (but doesn't think of it as relevant to changing)",
            ],
            "unknown_info": [
                "That the booking is basic economy",
                "That basic economy can't be changed",
                "That insurance can override cancellation restrictions",
                "The cancel+rebook workaround",
                "Points redemption rates",
                "Exact flight prices on June 23",
            ],
            "task_rules": [
                f"Open with: you want to change flight {booking_id} to June 23, mention $100 budget.",
                "When the agent says basic economy can't be changed, say 'That's really frustrating. Is there ANY other option to get me on a June 23 flight?'",
                "Do NOT mention insurance, cancellation, or points proactively. Let the agent discover these paths.",
                "If the agent asks whether you have insurance, confirm: 'Yes, I added travel insurance when I booked.'",
                "If the agent proposes cancel+rebook, say 'That could work — what would it actually cost me?'",
                "If the agent asks about using loyalty points, say 'Sure, I'm open to using points if it helps.'",
                "When presented with flight options, say you'd prefer the nonstop option.",
                "If the agent explains the nonstop is over your cash budget but the 1-stop fits, accept the 1-stop: 'Okay, the 1-stop works if it fits my budget.'",
                "After the booking is confirmed, say 'Great, thanks for figuring that out!' and end with [TASK_DONE].",
                "If the agent says there's nothing they can do (gives up), say 'Are you sure? I really need to get on a June 23 flight.' Give them one more chance. If they still can't find a solution, end with [TASK_DONE].",
            ],
        },
        "_replay_trace": [
            {"name": "cancel_booking", "arguments": {"booking_id": booking_id, "confirm": True}},
            {
                "name": "create_booking",
                "arguments": {
                    "user_id": user_id,
                    "flight_id": cheap_alt.flight_id,
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
        ],
        "task_summary": (
            "User wants to move a basic-economy booking under a strict cash budget, but the workable path is cancel plus rebook using insurance and points plus cash.\n"
            "The evaluator should check that the agent discovers the cancel-rebook workaround, explains why the nonstop option is still over budget, and steers the user to the cheaper 1-stop points-plus-cash booking that actually fits."
        ),
        "task_requirements": [
            {
                "id": "state_cancel_rebook_workaround_discovered",
                "kind": "must",
                "requirement": "Agent must explain that the basic-economy ticket cannot simply be changed but that insurance enables a free cancellation, creating a cancel-and-rebook workaround.",
                "evidence": "conversation",
            },
            {
                "id": "state_points_budget_math_explained",
                "kind": "must",
                "requirement": "Agent must explain that 15,000 points cover $150 domestically, making the $280 nonstop option require $130 cash and the $240 one-stop option require only $90 cash.",
                "evidence": "conversation",
            },
            {
                "id": "state_budget_fit_recommendation",
                "kind": "must",
                "requirement": "Agent must recommend the one-stop June 23 option because it is the only rebooking path that stays within the user's $100 cash budget.",
                "evidence": "conversation",
            },
        ],
    }

    return all_flights, [booking], task_data


def build_challenge_3():
    """Challenge 3: Bereavement change is cheaper than cancel.

    Setup:
    - user_005 (Ava, basic) has economy international JFK→CDG booking, $800.
    - Family emergency: wants to either cancel or change to a later flight.
    - Change reason: bereavement (75% discount on change fee).
    - Change fee: international economy, ≤7 days = $200. With bereavement = $50.
    - Cancel fee: international economy = max($75, 20% of $800) = $160.
    - Cancel + rebook: $160 cancel fee, then pay new flight ($820) = $160 + $820 = $980 total
    - Change: $50 fee + fare diff ($820-$800=$20) = $70 total (on top of $800 already paid)
    - CHANGE IS MASSIVELY CHEAPER! ($50+$20=$70 vs $160 cancel fee alone)

    The user expects to cancel (the "default" response to emergencies). The agent
    must compute both options and recommend the change — counterintuitive because
    most people think "cancel" when plans change due to bereavement.

    Agents typically: (a) just cancel without checking change fees, (b) don't know
    bereavement gets a 75% discount, or (c) don't compare the two options.
    """
    user_id = "user_005"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW

    # Current flight: JFK→CDG, June 19 (4 days out = ≤7 days)
    current_flight = build_flight(
        "DL",
        "JFK",
        "CDG",
        "2026-06-19",
        "evening",
        economy_price=800,
        business_price=2000,
    )
    booking = build_booking(
        user_id,
        current_flight,
        cabin_class="economy",
        booked_days_ago=10,
        now=now,
        has_insurance=False,
    )

    # Alternative flight on June 28. Keep the intended change target uniquely cheapest
    # so the task tests change-vs-cancel reasoning rather than arbitrary flight selection.
    alt_target = build_flight(
        "DL",
        "JFK",
        "CDG",
        "2026-06-28",
        "evening",
        economy_price=820,
        business_price=2050,
    )
    alt_distractor_1 = build_flight(
        "B6",
        "JFK",
        "CDG",
        "2026-06-28",
        "evening",
        economy_price=880,
        business_price=2200,
    )
    alt_distractor_2 = build_flight(
        "DL",
        "JFK",
        "CDG",
        "2026-06-28",
        "early_morning",
        economy_price=910,
        business_price=2275,
    )

    all_flights = [current_flight, alt_target, alt_distractor_1, alt_distractor_2]
    booking_id = booking.booking_id
    alt_flight_id = alt_target.flight_id

    # Cost comparison:
    # CANCEL + REBOOK:
    #   Cancel fee: max($75, 20% of $800) = $160
    #   Rebook: $820 for new flight
    #   Total out of pocket: $800 - ($800-$160) + $820 = $160 + $820 = $980
    #   Net additional cost: $160 (cancel fee) + $820 (new) - $800 (refund) = $180
    #
    # CHANGE (bereavement):
    #   Change fee: intl economy ≤7d = $200 × 25% (bereavement 75% discount) = $50
    #   Fare diff: $820 - $800 = $20
    #   Total additional cost: $50 + $20 = $70
    #
    # Change saves $110 compared to cancel+rebook!

    task_data = {
        "task_id": "challenge_bereavement_change_vs_cancel",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            f"Hi, I have a family emergency — a bereavement situation. I need to cancel "
            f"my flight {booking_id} to Paris. My user ID is {user_id}."
        ),
        "user_simulator": {
            "personality": (
                "Emotional and stressed due to bereavement. Defaults to wanting to cancel. "
                "Open to suggestions if the agent explains a better option."
            ),
            "known_info": [
                f"Your user ID: {user_id}",
                f"Booking: {booking_id} (JFK→CDG, economy, June 19)",
                "Has a bereavement situation (genuine family emergency)",
                "Wants to travel to Paris on June 28 instead",
                "Does not have travel insurance",
            ],
            "unknown_info": [
                "Exact cancellation fee",
                "That bereavement gets a 75% discount on change fees",
                "That changing is cheaper than cancelling",
                "Fare difference for the later flight",
            ],
            "task_rules": [
                f"Open with: family bereavement, need to cancel flight {booking_id}.",
                "When the agent asks about your plans, mention you still need to go to Paris but on June 28 instead.",
                "If the agent offers to check change fees, say 'I assumed cancelling was the way to go, but sure, check the change option too.'",
                "If the agent recommends changing over cancelling (because it's cheaper), say 'Really? That's surprising. Tell me the exact numbers.'",
                "When the agent shows change costs $70 vs cancel costs $160, say 'Wow, that's a big difference. Let's go with the change then.'",
                "If the agent just cancels without mentioning the change option, ask 'Wait — would it have been cheaper to change the flight instead of cancelling?'",
                "After the change is executed, say 'Thank you for suggesting the better option.' and end with [TASK_DONE].",
            ],
        },
        "_replay_trace": [
            {
                "name": "update_booking",
                "arguments": {
                    "booking_id": booking_id,
                    "flight_id": alt_flight_id,
                    "change_reason": "bereavement",
                },
            }
        ],
        "task_summary": (
            "User opens by wanting to cancel because of bereavement, but changing the booking is actually much cheaper.\n"
            "The evaluator should check that the agent compares cancel versus change, applies the bereavement discount correctly, and actively recommends the cheaper change path instead of defaulting to cancellation."
        ),
        "task_requirements": [
            {
                "id": "state_cancel_vs_change_compared",
                "kind": "must",
                "requirement": "Agent must compare both the cancellation path and the bereavement change path rather than treating cancellation as the only option.",
                "evidence": "conversation",
            },
            {
                "id": "state_bereavement_discount_math_correct",
                "kind": "must",
                "requirement": "Agent must explain that the bereavement change costs $70 total, made up of a $50 discounted change fee plus a $20 fare difference, while cancellation costs $160.",
                "evidence": "conversation",
            },
            {
                "id": "state_change_recommended_over_cancel",
                "kind": "must",
                "requirement": "Agent must recommend changing the booking instead of canceling because the bereavement change is materially cheaper.",
                "evidence": "conversation",
            },
        ],
    }

    return all_flights, [booking], task_data


def build_challenge_4():
    """Challenge 4: Points rounding edge case + international rate.

    Setup:
    - user_001 (Emma, gold, 75,000 points) needs to book TWO flights with points:
      1. Domestic: LAX→ORD, economy $350 (rate: 1pt = $0.01)
      2. International: JFK→LHR, economy $900 (rate: 1pt = $0.015)

    Both bookings draw from the same 75,000 point pool. The user wants to minimize
    total cash spent. The optimal booking ORDER matters:

    ORDER A (domestic first): 350/0.01 = 35k pts, then 40k pts for intl → 40k×0.015
      = $600 covers $600 of $900, cash=$300. Total cash = $300.

    ORDER B (intl first): 900/0.015 = 60k pts, then 15k pts for domestic → 15k×0.01
      = $150 covers $150 of $350, cash=$200. Total cash = $200.

    ORDER B saves $100! International rate is 1.5x domestic, so using points on
    international flights first maximizes dollar value per point.

    The agent must:
    1. Know the two different redemption rates
    2. Reason about optimal booking order
    3. Compute correct points_used for each (60,000 then 15,000)
    4. Execute both bookings with correct payment params

    Most agents will: (a) book in conversation order (domestic first), (b) use the
    wrong rate for one, or (c) fail the points_used arithmetic.
    """
    user_id = "user_001"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW

    # --- Domestic flight: LAX→ORD, economy $350 ---
    domestic_target, domestic_flights = build_route_flights(
        "LAX",
        "ORD",
        "2026-06-25",
        target_airline="DL",
        target_time="morning",
        target_economy_price=350,
        target_business_price=875,
        target_stops=0,
        num_distractors=2,
        seed=940,
    )

    # --- International flight: JFK→LHR, economy $900 ---
    # Build target manually since distractors from build_route_flights would be
    # randomly cheaper (economy range is $200-500). Add explicit expensive distractors.
    intl_target = build_flight(
        "BA",
        "JFK",
        "LHR",
        "2026-06-28",
        "morning",
        economy_price=900,
        business_price=2250,
    )
    intl_distractor1 = build_flight(
        "DL",
        "JFK",
        "LHR",
        "2026-06-28",
        "afternoon",
        economy_price=950,
        business_price=2375,
    )
    intl_distractor2 = build_flight(
        "AA",
        "JFK",
        "LHR",
        "2026-06-28",
        "evening",
        economy_price=1050,
        business_price=2625,
        stops=1,
    )
    intl_flights = [intl_target, intl_distractor1, intl_distractor2]

    all_flights = domestic_flights + intl_flights

    # Points math (optimal order — international first):
    # Intl: 900 / 0.015 = 60,000 pts, cash=$0. Remaining: 75k-60k = 15k
    # Domestic: 15k × 0.01 = $150. 350-150 = $200 cash. points_used=15000
    # Total: $200 cash + 75,000 points
    #
    # Suboptimal order (domestic first):
    # Domestic: 350 / 0.01 = 35,000 pts, cash=$0. Remaining: 75k-35k = 40k
    # Intl: 40k × 0.015 = $600. 900-600 = $300 cash. points_used=40000
    # Total: $300 cash + 75,000 points

    domestic_id = domestic_target.flight_id
    intl_id = intl_target.flight_id

    task_data = {
        "task_id": "challenge_points_dual_rate",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            f"Hi, I need to book two flights. One domestic — LAX to Chicago on June 25, 2026 — "
            f"and one international — JFK to London on June 28, 2026. I want to use my loyalty points "
            f"for both and pay as little cash as possible. My user ID is {user_id}."
        ),
        "user_simulator": {
            "personality": (
                "Analytical and frugal. Wants to optimize point usage. Expects the agent to find the cheapest option."
            ),
            "known_info": [
                f"Your user ID: {user_id}",
                "Wants domestic flight: LAX to Chicago (ORD), June 25, 2026, economy",
                "Wants international flight: JFK to London (LHR), June 28, 2026, economy",
                "For the London leg, wants the nonstop morning British Airways option.",
                "Has 75,000 loyalty points",
                "Wants to use points for both flights to minimize cash",
            ],
            "unknown_info": [
                "Exact redemption rates (domestic vs international)",
                "That booking order affects total cash cost",
                "Exact flight prices",
                "How many points each flight requires",
            ],
            "task_rules": [
                "Provide both flight requests in the opening message. Do NOT specify booking order.",
                f"If the agent presents flight options, choose the cheapest economy nonstop domestic flight ({domestic_id}) and the nonstop morning British Airways London option ({intl_id}).",
                "If the agent offers a London flight that is not the nonstop morning British Airways option, say 'I want the nonstop morning British Airways flight if it's available.'",
                "If the agent claims that nonstop morning British Airways option is unavailable, ask them to check again specifically for a nonstop morning British Airways flight and do not accept another London option unless they confirm that exact search preference truly cannot be met.",
                "If the agent still cannot offer that nonstop morning British Airways option, say you do not want a substitute London flight and would rather stop than book the wrong one.",
                "If the agent asks about payment preference, say 'Use as many points as possible — I want to minimize cash.'",
                "If the agent proposes a booking order and explains WHY (international rate is higher), agree.",
                "If the agent books the domestic flight first without explaining the rate difference, ask 'Wait — is the points rate the same for domestic and international? I want to make sure I'm getting the best deal.'",
                "When the agent presents the total cash cost, confirm and proceed.",
                "After both bookings are confirmed, say 'Great, thanks!' and end with [TASK_DONE].",
                "Do NOT request date changes or unrelated extras. Focus on booking the correct flights and minimizing cash while still confirming required booking preferences.",
            ],
        },
        "_replay_trace": [
            {
                "name": "create_booking",
                "arguments": {
                    "user_id": user_id,
                    "flight_id": intl_id,
                    "cabin_class": "economy",
                    "seat_type": _USERS_BY_ID[user_id].preferences["seat_type"],
                    "meal_preference": _USERS_BY_ID[user_id].preferences["meal_preference"],
                    "add_wifi": _USERS_BY_ID[user_id].preferences["add_wifi"],
                    "add_extra_legroom": _USERS_BY_ID[user_id].preferences["add_extra_legroom"],
                    "add_insurance": _USERS_BY_ID[user_id].preferences["add_insurance"],
                    "payment_method": "points",
                    "points_used": 60000,
                },
            },
            {
                "name": "create_booking",
                "arguments": {
                    "user_id": user_id,
                    "flight_id": domestic_id,
                    "cabin_class": "economy",
                    "seat_type": _USERS_BY_ID[user_id].preferences["seat_type"],
                    "meal_preference": _USERS_BY_ID[user_id].preferences["meal_preference"],
                    "add_wifi": _USERS_BY_ID[user_id].preferences["add_wifi"],
                    "add_extra_legroom": _USERS_BY_ID[user_id].preferences["add_extra_legroom"],
                    "add_insurance": _USERS_BY_ID[user_id].preferences["add_insurance"],
                    "payment_method": "points_plus_cash",
                    "points_used": 15000,
                    "cash_amount": 200,
                },
            },
        ],
        "task_summary": (
            "User wants to book one domestic and one international flight with a shared points pool while minimizing cash.\n"
            "The evaluator should check that the agent recognizes the higher international redemption rate, books in the cash-optimal order, and explains why using points on the international leg first produces the lowest total cash spend."
        ),
        "task_requirements": [
            {
                "id": "state_dual_rate_explained",
                "kind": "must",
                "requirement": "Agent must explain that domestic and international redemptions use different point values, with the international flight redeeming at the higher rate.",
                "evidence": "conversation",
            },
            {
                "id": "state_optimal_booking_order_selected",
                "kind": "must",
                "requirement": "Agent must recognize that booking the international flight first is the cash-optimal order for the shared 75,000-point pool.",
                "evidence": "conversation",
            },
            {
                "id": "state_min_cash_math_correct",
                "kind": "must",
                "requirement": "Agent must explain the resulting optimal cash outcome: 60,000 points cover the $900 international flight first, then the remaining 15,000 points reduce the $350 domestic fare to a $200 cash remainder.",
                "evidence": "conversation",
            },
        ],
    }

    return all_flights, [], task_data


def build_challenge_5():
    """Challenge 5: Triple fee modifier stack — bereavement + international + ≤7 days.

    Setup:
    - user_004 (Noah, silver) has 3 economy bookings that all need changes for bereavement:
      A. Domestic, >7 days: base $75, bereavement 75% off = $18 (int(75*0.25)=18)
      B. International, >7 days: base $100, bereavement 75% off = $25
      C. International, ≤7 days: base $200, bereavement 75% off = $50
    - Total change fees: $18 + $25 + $50 = $93
    - Plus fare differences on each.
    - User has a $120 budget for total fees (not counting fare diffs).
    - Agent must compute all 3 correctly and confirm they fit.

    Most agents miscalculate the bereavement discount (apply 75% instead of
    25% of base, or forget the route/timing modifiers). Getting all 3 right
    while tracking the fee budget is the challenge.
    """
    user_id = "user_004"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW

    # Booking A: domestic, departure June 25 (>7 days out), $300
    flight_a = build_flight(
        "UA",
        "ORD",
        "SFO",
        "2026-06-25",
        "morning",
        economy_price=300,
        business_price=750,
    )
    booking_a = build_booking(
        user_id,
        flight_a,
        cabin_class="economy",
        booked_days_ago=10,
        now=now,
        has_insurance=False,
    )

    # Alt for A: June 27, $320
    alt_a = build_flight(
        "UA",
        "ORD",
        "SFO",
        "2026-06-27",
        "morning",
        economy_price=320,
        business_price=800,
    )

    # Booking B: international, departure June 28 (>7 days out), $700
    flight_b = build_flight(
        "BA",
        "JFK",
        "LHR",
        "2026-06-28",
        "morning",
        economy_price=700,
        business_price=1750,
    )
    booking_b = build_booking(
        user_id,
        flight_b,
        cabin_class="economy",
        booked_days_ago=10,
        now=now,
        has_insurance=False,
    )

    # Alt for B: June 30, $720
    alt_b = build_flight(
        "BA",
        "JFK",
        "LHR",
        "2026-06-30",
        "morning",
        economy_price=720,
        business_price=1800,
    )

    # Booking C: international, departure June 20 (5 days = ≤7 days), $650
    flight_c = build_flight(
        "DL",
        "JFK",
        "CDG",
        "2026-06-20",
        "evening",
        economy_price=650,
        business_price=1625,
    )
    booking_c = build_booking(
        user_id,
        flight_c,
        cabin_class="economy",
        booked_days_ago=10,
        now=now,
        has_insurance=False,
    )

    # Alt for C: June 23, $680
    alt_c = build_flight(
        "DL",
        "JFK",
        "CDG",
        "2026-06-23",
        "evening",
        economy_price=680,
        business_price=1700,
    )

    all_flights = [flight_a, alt_a, flight_b, alt_b, flight_c, alt_c]
    a_id = booking_a.booking_id
    b_id = booking_b.booking_id
    c_id = booking_c.booking_id

    # Fee calculations (bereavement = 75% discount → pay 25% of base):
    # A: domestic economy >7d = $75 base. Bereavement: int(75/4) = $18
    # B: intl economy >7d = $100 base. Bereavement: int(100/4) = $25
    # C: intl economy ≤7d = $200 base. Bereavement: int(200/4) = $50
    # Total fees: $18 + $25 + $50 = $93 (under $120 budget)
    #
    # Fare diffs: A=$20, B=$20, C=$30. Total fare diffs: $70
    # Grand total additional: $93 + $70 = $163

    task_data = {
        "task_id": "challenge_triple_fee_stack",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            f"I have a family bereavement and need to reschedule 3 flights. "
            f"Booking {a_id} (ORD→SFO) to June 27, booking {b_id} (JFK→LHR) to June 30, "
            f"and booking {c_id} (JFK→CDG) to June 23. My user ID is {user_id}. "
            f"My total budget for change fees is $120 — can all 3 changes fit?"
        ),
        "user_simulator": {
            "personality": (
                "Organized despite grief. Gives all info upfront. Wants exact fee breakdown before proceeding."
            ),
            "known_info": [
                f"Your user ID: {user_id}",
                f"Booking A: {a_id} (ORD→SFO, June 25) → change to June 27",
                f"Booking B: {b_id} (JFK→LHR, June 28) → change to June 30",
                f"Booking C: {c_id} (JFK→CDG, June 20) → change to June 23",
                "Change reason: bereavement (genuine family emergency)",
                "Budget for change fees only (not fare differences): $120",
            ],
            "unknown_info": [
                "Exact change fees for each booking",
                "Whether bereavement discount applies",
                "How much the bereavement discount is",
                "Fare differences for new flights",
            ],
            "task_rules": [
                "Provide all 3 bookings and new dates in the opening message. Mention bereavement and $120 fee budget.",
                "When agent calculates fees, ask 'Can you break down each fee separately so I can see the math?'",
                "If agent's fee calculation matches ($18 + $25 + $50 = $93), say 'Great, that's under my $120 budget. Go ahead with all 3 changes.'",
                "If agent miscalculates any fee, say 'That doesn't sound right — can you double-check the bereavement discount? I thought it was 75% off.'",
                "After all 3 changes are executed, say 'Thank you for your help during this difficult time.' and end with [TASK_DONE].",
            ],
        },
        "_replay_trace": [
            {
                "name": "update_booking",
                "arguments": {
                    "booking_id": a_id,
                    "flight_id": alt_a.flight_id,
                    "change_reason": "bereavement",
                    "add_insurance": _USERS_BY_ID[user_id].preferences["add_insurance"],
                },
            },
            {
                "name": "update_booking",
                "arguments": {
                    "booking_id": b_id,
                    "flight_id": alt_b.flight_id,
                    "change_reason": "bereavement",
                    "add_insurance": _USERS_BY_ID[user_id].preferences["add_insurance"],
                },
            },
            {
                "name": "update_booking",
                "arguments": {
                    "booking_id": c_id,
                    "flight_id": alt_c.flight_id,
                    "change_reason": "bereavement",
                    "add_insurance": _USERS_BY_ID[user_id].preferences["add_insurance"],
                },
            },
        ],
        "task_summary": (
            "User needs three bereavement-related date changes with different route and timing tiers, but only has a $120 budget for the change fees themselves.\n"
            "The evaluator should check that the agent computes all three bereavement fees correctly, keeps the fee-budget reasoning separate from fare differences, and confirms that the fee total fits while still giving the full grand-total breakdown."
        ),
        "task_requirements": [
            {
                "id": "state_three_bereavement_fees_correct",
                "kind": "must",
                "requirement": "Agent must compute the three bereavement change fees correctly as $18, $25, and $50 for the three bookings.",
                "evidence": "conversation",
            },
            {
                "id": "state_fee_budget_vs_fare_diff_distinguished",
                "kind": "must",
                "requirement": "Agent must explain that the $120 budget applies to change fees only, that the total fees are $93, and that fare differences are separate additional amounts.",
                "evidence": "conversation",
            },
            {
                "id": "state_all_three_fit_and_can_proceed",
                "kind": "must",
                "requirement": "Agent must conclude that all three changes can proceed because the fee total stays under budget.",
                "evidence": "conversation",
            },
        ],
    }

    return all_flights, [booking_a, booking_b, booking_c], task_data


def build_challenge_6():
    """Challenge 6: Retroactive change reason — personal fee already paid, then bereavement revealed.

    Setup:
    - user_002 (Liam, basic) has economy international JFK→LHR, $750, June 20 (≤7 days).
    - User first asks to change for personal reasons. Agent executes change.
    - Change fee: intl economy ≤7d personal = $200. Fare diff = $30. Total = $980.
    - THEN user reveals it was actually bereavement.
    - Agent must call update_booking(booking_id, change_reason='bereavement') to
      trigger fee recalculation: $200 → $50 (75% discount). Price adjusts down by $150.
    - The environment's retroactive recalculation logic handles this (lines 547-566).

    Most agents: (a) don't know you can update the reason after the fact,
    (b) tell the user "sorry, already processed," or (c) try to cancel and redo.
    """
    user_id = "user_002"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW

    # Current flight: JFK→LHR, June 20 (5 days = ≤7 days)
    current_flight = build_flight(
        "BA",
        "JFK",
        "LHR",
        "2026-06-20",
        "morning",
        economy_price=750,
        business_price=1875,
    )
    booking = build_booking(
        user_id,
        current_flight,
        cabin_class="economy",
        booked_days_ago=10,
        now=now,
        has_insurance=False,
    )

    # Alternative flight on June 24. Keep one intended cheapest valid replacement so the
    # task stays focused on retroactive fee recalculation, not replacement-flight ambiguity.
    alt_target = build_flight(
        "BA",
        "JFK",
        "LHR",
        "2026-06-24",
        "morning",
        economy_price=780,
        business_price=1950,
    )
    alt_distractor_1 = build_flight(
        "UA",
        "JFK",
        "LHR",
        "2026-06-24",
        "morning",
        economy_price=840,
        business_price=2100,
    )
    alt_distractor_2 = build_flight(
        "BA",
        "JFK",
        "LHR",
        "2026-06-24",
        "evening",
        economy_price=860,
        business_price=2150,
    )

    all_flights = [current_flight, alt_target, alt_distractor_1, alt_distractor_2]
    booking_id = booking.booking_id
    alt_id = alt_target.flight_id

    # Fee math:
    # Personal change: intl economy ≤7d = $200 fee. Fare diff = $780-$750 = $30.
    # price_paid after change = $780 + $200 = $980
    #
    # Retroactive bereavement: $200 → int(200/4) = $50. Diff = $150 refund.
    # price_paid after update = $980 - $200 + $50 = $830

    task_data = {
        "task_id": "challenge_retroactive_reason",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            f"Hi, I need to change my flight {booking_id} to June 24 for personal reasons. My user ID is {user_id}."
        ),
        "user_simulator": {
            "personality": (
                "Initially guarded about reasons. Opens up after the change is done. "
                "Hopeful that the fee can be adjusted."
            ),
            "known_info": [
                f"Your user ID: {user_id}",
                f"Booking: {booking_id} (JFK→LHR, economy, June 20)",
                "Wants to change to June 24",
                "The real reason is bereavement but you initially said personal",
                "You're hoping the fee can be reduced retroactively",
            ],
            "unknown_info": [
                "That bereavement gets a 75% fee discount",
                "Whether the reason can be changed after the flight change",
                "Exact fee amounts",
            ],
            "task_rules": [
                f"Open with: change flight {booking_id} to June 24, say 'personal reasons'.",
                "After the agent executes the change, say: 'Actually, I should tell you — the real reason is a family bereavement. I said personal because I wasn't sure if it mattered. Is there any way to adjust the fee?'",
                "If the agent says they can update the reason and reduce the fee, say 'Yes please, go ahead.'",
                "If the agent says it's already processed and can't be changed, push: 'Can you at least try updating the reason on the booking? Maybe the system allows it.'",
                "After the fee is adjusted, say 'Thank you, that really helps.' and end with [TASK_DONE].",
                "If the agent refuses to try at all, end with [TASK_DONE].",
            ],
        },
        "_replay_trace": [
            {"name": "update_booking", "arguments": {"booking_id": booking_id, "flight_id": alt_id, "change_reason": "personal"}},
            {"name": "update_booking", "arguments": {"booking_id": booking_id, "change_reason": "bereavement"}},
        ],
        "task_summary": (
            "User first changes a booking for personal reasons, then reveals the real reason was bereavement and asks whether the fee can be adjusted retroactively.\n"
            "The evaluator should check that the agent recognizes the change reason can be updated after the initial change, recalculates the fee instead of saying it is locked in, and explains the $150 savings from the retroactive bereavement discount."
        ),
        "task_requirements": [
            {
                "id": "state_retroactive_reason_update_attempted",
                "kind": "must",
                "requirement": "Agent must recognize or attempt that the booking's change reason can be updated retroactively after the initial flight change instead of treating the original personal reason as permanent.",
                "evidence": "conversation",
            },
            {
                "id": "state_retroactive_fee_reduction_explained",
                "kind": "must",
                "requirement": "Agent must explain that the fee can be reduced from $200 to $50 once the bereavement reason is applied retroactively, either by stating the $150 savings directly or by clearly giving the before-and-after fee amounts.",
                "evidence": "conversation",
            },
        ],
    }

    return all_flights, [booking], task_data


def build_challenge_7():
    """Challenge 7: Change to EARLIER flight — timing uses ORIGINAL departure, not new.

    user_002 (Liam) has economy domestic ORD→SFO, $350, departing June 25 (>7d from now Jun 15).
    Wants to change to June 18 (≤7d from now). Personal reason.
    Change fee uses ORIGINAL departure (Jun 25, >7d): $75 (domestic >7d).
    NOT new departure (Jun 18, ≤7d): $150 (domestic ≤7d).
    Fare diff: $380 - $350 = $30.
    Total: $75 + $30 = $105.
    Agent usually uses the new departure date (Jun 18, ≤7d) → $150 + $30 = $180. Wrong!
    """
    user_id = "user_002"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW

    flight = build_flight("UA", "ORD", "SFO", "2026-06-25", "morning", economy_price=350, business_price=875)
    booking = build_booking(user_id, flight, cabin_class="economy", booked_days_ago=14, now=now, has_insurance=False)
    alt = build_flight("UA", "ORD", "SFO", "2026-06-18", "afternoon", economy_price=380, business_price=950)

    booking_id = booking.booking_id
    task_data = {
        "task_id": "challenge_earlier_flight_timing",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            f"Hi, I need to move my flight {booking_id} from June 25 to June 18 instead — "
            f"something came up and I need to fly earlier. My user ID is {user_id}."
        ),
        "user_simulator": {
            "personality": "Direct. Wants quick processing.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"Booking: {booking_id} (ORD→SFO, economy, June 25)",
                "Needs to fly June 18 instead (earlier)",
            ],
            "unknown_info": ["Which departure date determines the fee tier", "Exact fee amount"],
            "task_rules": [
                f"Open with: change {booking_id} from Jun 25 to Jun 18.",
                "If agent quotes $150+ fee, say 'That seems high — my original flight is June 25 which is more than 7 days away. Shouldn't the lower rate apply?'",
                "If agent says $75, accept: 'That sounds right. Go ahead.'",
                "After change, end with [TASK_DONE].",
            ],
        },
        "_replay_trace": [
            {"name": "update_booking", "arguments": {"booking_id": booking_id, "flight_id": alt.flight_id, "change_reason": "personal"}},
        ],
        "task_summary": (
            "User moves a flight to an earlier date, but the change-fee tier should still be based on the original departure date rather than the new one.\n"
            "The evaluator should check that the agent uses the original June 25 departure to pick the lower $75 fee tier, explicitly rejects the tempting but wrong $150 new-date tier, and gives the correct $105 total change cost."
        ),
        "task_requirements": [
            {
                "id": "state_original_departure_basis_explained",
                "kind": "must",
                "requirement": "Agent must explain that the applicable fee tier is determined by the original June 25 departure timing rather than the newly selected June 18 flight date.",
                "evidence": "conversation",
            },
            {
                "id": "state_correct_earlier_change_math",
                "kind": "must",
                "requirement": "Agent must quote the correct math for this change as a $75 change fee plus a $30 fare difference, for a total additional cost of $105.",
                "evidence": "conversation",
            },
        ],
    }
    return [flight, alt], [booking], task_data


def build_challenge_8():
    """Challenge 8 (v2): Sunk cost fallacy — already-paid change fee shouldn't affect next decision.

    Setup:
    - user_001 (Emma, gold) has economy international JFK→LHR, originally $800.
    - Previously changed once: paid $100 change fee (intl >7d). price_paid now $900 ($800 + $100).
    - Flight got WORSE — schedule changed to a terrible time. User wants to fix it.
    - Option A: Change AGAIN to a better flight ($850). Second change fee: intl ≤7d = $200.
      Total additional: $200 fee + ($850-$900=-$50, no refund) = $200. price_paid = $850+$200 = $1050.
    - Option B: Cancel + rebook. Cancel fee: max($75, 20% of $900) = $180.
      Refund = $900-$180 = $720. Book new at $850. Total spent: $180+$850 = $1030.
      Net from original: $800 original + $100 first fee + $180 cancel + $850 rebook - $720 refund = $1210. Bad.
    - Option C: Cancel + rebook to a CHEAPER flight at $750.
      Cancel fee: $180. Refund $720. Book $750. Total out: $180+$750 = $930.
    - CORRECT: Option C ($930 total) beats A ($1050) by $120.
    - TRAP: Agent anchors on sunk $100 change fee and tries to "protect" the investment by
      changing again (option A) instead of cutting losses and cancelling to a cheaper flight (option C).
    """
    user_id = "user_001"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW

    # Original flight: JFK→LHR, changed once already
    current_flight = build_flight(
        "BA",
        "JFK",
        "LHR",
        "2026-06-19",
        "red_eye",
        economy_price=800,
        business_price=2000,
    )
    booking = build_booking(
        user_id,
        current_flight,
        cabin_class="economy",
        booked_days_ago=14,
        now=now,
        has_insurance=False,
    )
    # Simulate prior change: price_paid includes $100 change fee
    booking.price_paid = 900
    booking.change_fee = 100
    booking.fare_difference = 0

    # Better same-route flight (expensive): $850. This is the cheapest change option;
    # there must NOT be a cheaper direct-change path than the cancel+rebook alternative.
    alt_expensive = build_flight(
        "BA",
        "JFK",
        "LHR",
        "2026-06-21",
        "morning",
        economy_price=850,
        business_price=2125,
    )
    alt_expensive_distractor = build_flight(
        "B6",
        "JFK",
        "LHR",
        "2026-06-21",
        "early_morning",
        economy_price=980,
        business_price=2450,
    )

    # Cheaper different-time flight: $750, but only as a fresh rebook target after cancellation.
    alt_cheap = build_flight(
        "DL",
        "JFK",
        "LHR",
        "2026-06-21",
        "afternoon",
        economy_price=750,
        business_price=1875,
    )

    all_flights = [current_flight, alt_expensive, alt_expensive_distractor, alt_cheap]
    booking_id = booking.booking_id

    # Math:
    # Option A (change to $850): fee $200 (intl ≤7d, second change), fare diff $850-$900=-$50 (not refunded).
    #   price_paid = $850 + $200 = $1050. Total spent from pocket = $1050.
    # Option C (cancel + rebook $750): cancel fee max($75, 20%*900) = $180. Refund $720.
    #   Book $750. Total spent = $900 (already paid) - $720 (refund) + $750 = $930.
    # Option C saves $120. The $100 already-paid change fee is a SUNK COST in both paths.

    task_data = {
        "task_id": "challenge_sunk_cost_change_fee",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            f"I already changed my flight {booking_id} once and paid a $100 fee for it. "
            f"But the new time is terrible — a red-eye! I need to fix this. "
            f"What are my options? I don't want to waste the $100 I already spent. "
            f"My user ID is {user_id}."
        ),
        "user_simulator": {
            "personality": (
                "Loss-averse. Explicitly anchors on the $100 already spent. "
                "Wants to 'not waste' the previous investment. Will accept the cheaper path "
                "if agent clearly explains the sunk cost logic."
            ),
            "known_info": [
                f"Your user ID: {user_id}",
                f"Booking: {booking_id} (JFK→LHR, economy, red-eye, already changed once)",
                "Already paid $100 change fee",
                "Wants the cheapest reasonable June 21 replacement and cares more about total cost than airline or morning timing",
                "Doesn't want to waste the $100 already spent",
            ],
            "unknown_info": [
                "Exact costs of change-again vs cancel+rebook",
                "That the $100 is a sunk cost irrelevant to the forward decision",
                "Specific flight prices for June 21",
                "That the cheapest correct fix is the $750 economy replacement rather than a pricier morning or business option",
            ],
            "task_rules": [
                f"Open with: already changed {booking_id} once, paid $100, new time is bad, want to fix it.",
                "Emphasize: 'I don't want to waste the $100 I already spent.'",
                "If agent recommends changing again or pushes a pricier replacement, ask 'What about cancelling and rebooking to a cheaper flight? I saw some around $750.'",
                "If agent says cancel+rebook is cheaper overall, say 'But I'll lose the $100 change fee I already paid!' Then accept if agent explains it's sunk either way.",
                "If agent recommends cancel+rebook to the cheaper $750 economy flight and explains the math, agree: 'OK, let's do it.'",
                "Do not request Delta, business class, or a morning-only replacement unless the agent asks you to compare options; cost is the deciding factor for this task.",
                "After the action is complete, end with [TASK_DONE].",
            ],
        },
        "task_summary": (
            "User is anchored on a previously paid $100 change fee and wants help choosing between changing again or canceling and rebooking.\n"
            "The evaluator should check that the agent treats the earlier fee as sunk, compares the live options correctly, and does not recommend the more expensive path just to protect sunk cost."
        ),
        "task_requirements": [
            {
                "id": "explain_sunk_cost",
                "kind": "must",
                "requirement": "Agent must explain that the previously paid $100 change fee is a sunk cost and should not drive the current decision.",
                "evidence": "conversation",
            },
            {
                "id": "compare_change_vs_cancel_rebook",
                "kind": "must",
                "requirement": "Agent must compare changing again versus canceling and rebooking, and conclude that canceling and rebooking is cheaper overall.",
                "evidence": "conversation",
            },
            {
                "id": "must_not_recommend_pricier_change",
                "kind": "must_not",
                "requirement": "Agent must not recommend the more expensive change-again path just to avoid wasting the prior $100 fee.",
                "evidence": "conversation",
            },
        ],
        "_replay_trace": [
            {"name": "cancel_booking", "arguments": {"booking_id": booking_id, "confirm": True}},
            {
                "name": "create_booking",
                "arguments": {
                    "user_id": user_id,
                    "flight_id": alt_cheap.flight_id,
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
    }

    return all_flights, [booking], task_data


def build_challenge_9():
    """Challenge 9 (v2): Premature commitment — agent must search BEFORE cancelling.

    Setup:
    - user_002 (Liam, basic, 5k pts, no insurance) has economy domestic ORD→LAX, $600,
      June 18 (3 days out = ≤7d).
    - User wants to move to June 22 for a cheaper price.
    - Change path: domestic economy ≤7d = $150 fee. Agent would need alternatives.
    - Cancel+rebook: cancel fee = max($50, 15% of $600) = $90. Refund $510.
    - Available flights on June 22 ORD→LAX: ALL are $650+ (more expensive!)
    - The ONLY affordable option: change to a June 22 flight at $480 (cheaper, fee $150 but
      fare diff is negative = not refunded, total $150 + $480 = $630).
    - But if agent CANCELS first (premature commitment), they lose $90 to cancel fee,
      get $510 refund, then must book at $650+ = $740+ total. MUCH worse.
    - Agent must discover: (1) search June 22 flights FIRST, (2) see $650+ prices,
      (3) realize change ($630) is cheaper than cancel+rebook ($740+),
      (4) recommend change despite the $150 fee.
    - TRAP: Agent instinctively cancels to "free up" for rebooking, then finds only expensive options.

    Two interacting traps:
    1. Agent thinks "cancel first, shop later" → premature commitment, stuck with expensive options
    2. Even if agent searches first, the math is tricky: change to $480 flight costs
       $150 fee (no fare diff refund even though cheaper), vs cancel($90)+rebook($650)=$740
    """
    user_id = "user_002"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW

    # Current flight: ORD→LAX, June 18 (3 days = ≤7d)
    current_flight = build_flight(
        "UA",
        "ORD",
        "LAX",
        "2026-06-18",
        "morning",
        economy_price=600,
        business_price=1500,
    )
    booking = build_booking(
        user_id,
        current_flight,
        cabin_class="economy",
        booked_days_ago=10,
        now=now,
        has_insurance=False,
    )

    # June 22 flights — all expensive except one change-only option
    exp_1 = build_flight("UA", "ORD", "LAX", "2026-06-22", "morning", economy_price=650, business_price=1625)
    exp_2 = build_flight("DL", "ORD", "LAX", "2026-06-22", "afternoon", economy_price=680, business_price=1700)
    exp_3 = build_flight("AA", "ORD", "LAX", "2026-06-22", "evening", economy_price=700, business_price=1750)
    # Cheap one available for change (lower economy price)
    cheap = build_flight("WN", "ORD", "LAX", "2026-06-22", "red_eye", economy_price=480, business_price=1200)

    all_flights = [current_flight, exp_1, exp_2, exp_3, cheap]
    booking_id = booking.booking_id

    # Math:
    # CHANGE to cheap $480: fee $150 (domestic ≤7d personal). fare_diff = $480-$600 = -$120 (not refunded).
    #   price_paid = $480 + $150 = $630.
    # CANCEL + REBOOK cheapest ($650): cancel fee max($50, 15%*600)=$90. Refund $510.
    #   Total: $90 + $650 = $740.
    # CHANGE saves $110! ($630 vs $740).
    # If agent cancels first (premature commitment), stuck with $740+.

    task_data = {
        "task_id": "challenge_premature_cancel_commitment",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            f"I need to move my flight {booking_id} to June 22. I'm hoping to find something "
            f"cheaper — what are my options? My user ID is {user_id}."
        ),
        "user_simulator": {
            "personality": (
                "Budget-conscious but flexible on times. Wants the cheapest total option. "
                "Would accept a red-eye if it saves money."
            ),
            "known_info": [
                f"Your user ID: {user_id}",
                f"Booking: {booking_id} (ORD→LAX, economy, June 18, $600)",
                "Wants June 22 instead",
                "Budget is tight (max $800 for this trip)",
            ],
            "unknown_info": [
                "June 22 flight prices",
                "Change fee amount",
                "That change could be cheaper than cancel+rebook",
            ],
            "task_rules": [
                f"Open with: want to move {booking_id} to June 22, hoping for cheaper.",
                "If agent says they'll cancel first, ask 'Wait — shouldn't we check what's available on June 22 before cancelling? I want to know my total cost.'",
                "If agent shows flight options and they're expensive ($650+), say 'Those are more than I paid originally! Is there anything cheaper, even late at night?'",
                "If agent mentions the $480 red-eye change option, ask 'What's the total cost if I change vs cancel and rebook?'",
                "If agent recommends change (cheaper), agree: 'OK, the red-eye works. Go ahead and change it.'",
                "After change is done, end with [TASK_DONE].",
            ],
        },
        "task_summary": (
            "User wants the cheapest way to move an existing booking to June 22, but canceling too early would lock in a worse outcome.\n"
            "The evaluator should check that the agent searches and compares costs before committing, recognizes that changing to the $480 red-eye is cheaper than canceling and rebooking, and recommends the lower-total-cost path."
        ),
        "task_requirements": [
            {
                "id": "search_before_commitment",
                "kind": "must",
                "requirement": "Agent must search or otherwise compare the June 22 options before committing to cancellation, rather than canceling first and shopping later.",
                "evidence": "conversation",
            },
            {
                "id": "change_beats_cancel_rebook_math",
                "kind": "must",
                "requirement": "Agent must explain that changing to the $480 red-eye costs $630 total, while canceling and rebooking the cheapest available alternative costs $740 total, so changing is cheaper by $110.",
                "evidence": "conversation",
            },
            {
                "id": "recommend_change_path",
                "kind": "must",
                "requirement": "Agent must recommend the cheaper change path rather than steering the user toward cancel-and-rebook.",
                "evidence": "conversation",
            },
        ],
        "_replay_trace": [
            {"name": "update_booking", "arguments": {"booking_id": booking_id, "flight_id": cheap.flight_id, "change_reason": "personal"}},
        ],
    }
    return all_flights, [booking], task_data


def build_challenge_10():
    """Challenge 10 (v4): Bereavement intl <=7d + cheaper flight — fee eats all savings.

    user_002 (Liam, basic, no insurance) economy intl JFK->FRA, $800, June 18 (<=7d, 3 days).
    Bereavement. Change to July 2 flight at $750 (cheaper).

    Correct: intl <=7d = $200. Bereavement 75% off -> pay 25% = $50 fee.
    Fare diff = $750 - $800 = -$50 (not refunded).
    price_paid = $750 + $50 = $800. Same as original! Additional = $0.

    Agent may: (1) compute wrong fee, (2) think there are savings from cheaper flight,
    (3) use wrong base rate, (4) apply discount wrong direction.
    """
    user_id = "user_002"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW

    flight = build_flight("DL", "JFK", "FRA", "2026-06-18", "morning", economy_price=800, business_price=2000)
    booking = build_booking(user_id, flight, cabin_class="economy", booked_days_ago=14, now=now, has_insurance=False)
    alt = build_flight("DL", "JFK", "FRA", "2026-07-02", "morning", economy_price=750, business_price=1875)

    booking_id = booking.booking_id
    task_data = {
        "task_id": "challenge_bereavement_intl_cheaper_no_savings",

        "user_id": user_id,
        "now": now,
        "opening_message": (f"Family bereavement. Need to change {booking_id} to July 2. My user ID is {user_id}."),
        "user_simulator": {
            "personality": "Brief, grieving.",
            "known_info": [f"Your user ID: {user_id}", f"Booking: {booking_id} (JFK to FRA, June 18)", "Bereavement"],
            "unknown_info": ["Fee amount", "That savings are eaten by fee"],
            "task_rules": [
                f"Open with: bereavement, change {booking_id} to July 2.",
                "Accept fee. End with [TASK_DONE].",
            ],
        },
        "task_summary": (
            "User has a bereavement change to a cheaper international flight, but the discount only reduces the change fee rather than creating a refund windfall.\n"
            "The evaluator should check that the agent computes the discounted fee correctly, recognizes that the lower fare does not create extra savings because negative fare differences are not refunded, and explains that the final total stays flat."
        ),
        "task_requirements": [
            {
                "id": "bereavement_fee_math_correct",
                "kind": "must",
                "requirement": "Agent must explain that this bereavement change uses the international within-7-days base fee of $200 and reduces it to a $50 fee.",
                "evidence": "conversation",
            },
            {
                "id": "no_net_savings_explained",
                "kind": "must",
                "requirement": "Agent must explain that the cheaper $750 replacement does not create a net savings because the negative fare difference is not refunded and the final total remains $800 overall.",
                "evidence": "conversation",
            },
        ],
        "_replay_trace": [
            {"name": "update_booking", "arguments": {"booking_id": booking_id, "flight_id": alt.flight_id, "change_reason": "bereavement"}},
        ],
    }
    return [flight, alt], [booking], task_data


def _make_challenge_scenario(prefix: str, builder):
    """Create a scenario function that wraps a challenge builder."""

    def scenario() -> tuple[list[Flight], list[Booking], dict]:
        flights, bookings, task_data = builder()
        return flights, bookings, task_data

    scenario.__name__ = f"scenario_C{int(prefix) - 50:02d}"
    return scenario


scenario_C01 = _make_challenge_scenario('51', build_challenge_task)
scenario_C02 = _make_challenge_scenario('52', build_challenge_2)
scenario_C03 = _make_challenge_scenario('53', build_challenge_3)
scenario_C04 = _make_challenge_scenario('54', build_challenge_4)
scenario_C05 = _make_challenge_scenario('55', build_challenge_5)
scenario_C06 = _make_challenge_scenario('56', build_challenge_6)
scenario_C07 = _make_challenge_scenario('57', build_challenge_7)
scenario_C08 = _make_challenge_scenario('58', build_challenge_8)
scenario_C09 = _make_challenge_scenario('59', build_challenge_9)
scenario_C10 = _make_challenge_scenario('60', build_challenge_10)


SCENARIOS = [
    scenario_C01,
    scenario_C02,
    scenario_C03,
    scenario_C04,
    scenario_C05,
    scenario_C06,
    scenario_C07,
    scenario_C08,
    scenario_C09,
    scenario_C10,
]
