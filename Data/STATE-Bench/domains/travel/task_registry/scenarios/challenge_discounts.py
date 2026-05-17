"""Travel challenge scenarios centered on discounts, waivers, and points rules."""


from __future__ import annotations


from domains.travel.schemas import Booking, Flight

from domains.travel.task_registry._builders import (
    _USERS_BY_ID,
    DEFAULT_NOW,
    build_booking,
    build_flight,
)


def build_challenge_11():
    """Challenge 11 (v3): Medical discount on intl <=7d to a cheaper flight — fee + no refund.

    user_001 (Emma, gold) economy intl JFK->LHR, $1000, June 20 (<=7d, 5 days).
    Medical. Change to June 27 flight at $920 (cheaper).

    Correct: intl <=7d = $200. Medical 50% = $100 fee.
    Fare diff: $920 - $1000 = -$80 (not refunded).
    price_paid = $920 + $100 = $1020. Additional = $20.

    Agent thinks: "cheaper flight + medical discount = big savings."
    Reality: $100 fee added, $80 savings lost (not refunded). Net additional $20.
    """
    user_id = "user_001"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW

    flight = build_flight("BA", "JFK", "LHR", "2026-06-20", "morning", economy_price=1000, business_price=2500)
    booking = build_booking(user_id, flight, cabin_class="economy", booked_days_ago=14, now=now, has_insurance=False)
    alt = build_flight("BA", "JFK", "LHR", "2026-06-27", "morning", economy_price=920, business_price=2300)

    booking_id = booking.booking_id
    task_data = {
        "task_id": "challenge_medical_cheaper_flight_no_savings",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            f"Medical procedure. Need to change {booking_id} to June 27. "
            f"I saw the later flights are cheaper. My user ID is {user_id}."
        ),
        "user_simulator": {
            "personality": "Hopeful about savings.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"Booking: {booking_id} (JFK to LHR, June 20)",
                "Medical reason",
            ],
            "unknown_info": ["That cheaper flight doesn't save money", "Fee formula"],
            "task_rules": [
                f"Open with: medical, change {booking_id} to June 27, mention cheaper flights.",
                "Accept fee. End with [TASK_DONE].",
            ],
        },
        "task_summary": (
            "User expects a cheaper later international flight plus a medical reason to reduce total cost, but the fee logic actually makes the change slightly more expensive overall.\n"
            "The evaluator should check that the agent computes the discounted medical fee correctly, avoids inventing a refund on the cheaper fare, and explains that the final total increases to $1020 rather than creating savings."
        ),
        "task_requirements": [
            {
                "id": "medical_fee_math_correct",
                "kind": "must",
                "requirement": "Agent must explain that this medical change uses the international within-7-days base fee of $200 and reduces it to a $100 fee.",
                "evidence": "conversation",
            },
            {
                "id": "cheaper_flight_still_costs_more",
                "kind": "must",
                "requirement": "Agent must explain that even though the replacement flight is cheaper, the $80 negative fare difference is not refunded, so the final total becomes $1020, which is $20 more than the original $1000 booking.",
                "evidence": "conversation",
            },
        ],
        "_replay_trace": [
            {"name": "update_booking", "arguments": {"booking_id": booking_id, "flight_id": alt.flight_id, "change_reason": "medical"}},
        ],
    }
    return [flight, alt], [booking], task_data


def build_challenge_12():
    """Challenge 12: 240+ delay = free change FEE, but fare difference ($200) still applies.

    user_005 (Ava) has economy intl JFK→CDG $800, delayed 250 min.
    Wants to switch to evening flight at $1000.
    Change fee: $0 (240+ delay waiver). Fare diff: $1000-$800 = $200.
    Total cost: $200 (NOT $0!).
    Agent thinks "free change" = $0 total and doesn't mention the $200 fare diff.
    """
    user_id = "user_005"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW

    delayed = build_flight(
        "DL",
        "JFK",
        "CDG",
        "2026-06-18",
        "morning",
        economy_price=800,
        business_price=2000,
        status="delayed",
        delay_minutes=250,
    )
    booking = build_booking(user_id, delayed, cabin_class="economy", booked_days_ago=10, now=now, has_insurance=False)
    alt = build_flight("DL", "JFK", "CDG", "2026-06-18", "evening", economy_price=1000, business_price=2500)

    booking_id = booking.booking_id
    task_data = {
        "task_id": "challenge_delay_waiver_fare_diff",

        "user_id": user_id,
        "now": now,
        "opening_message": f"My flight {booking_id} to Paris is delayed over 4 hours! I want a free change to the evening flight. My user ID is {user_id}.",
        "user_simulator": {
            "personality": "Expects completely free switch.",
            "known_info": [f"Your user ID: {user_id}", f"Booking: {booking_id} (JFK→CDG, delayed 4+ hours)"],
            "unknown_info": ["That fare diff still applies"],
            "task_rules": [
                "Open with: flight delayed 4+ hours, want free change.",
                "If agent says $200 fare diff applies, say 'I thought the delay made it completely free?'",
                "If agent explains fee vs fare diff, accept: 'OK, $200 for the fare difference. Go ahead.'",
                "If agent says $0 total, don't question it.",
                "After change, end with [TASK_DONE].",
            ],
        },
        "task_summary": (
            "User’s flight is delayed more than four hours and assumes that makes the replacement completely free.\n"
            "The evaluator should check that the agent separates the waived change fee from the still-applicable fare difference and gives the correct $200 total to switch to the evening flight."
        ),
        "task_requirements": [
            {
                "id": "delay_waives_fee_not_fare_diff",
                "kind": "must",
                "requirement": "Agent must explain that a 250-minute delay waives the change fee but does not waive the fare difference for a more expensive replacement flight.",
                "evidence": "conversation",
            },
            {
                "id": "correct_delay_change_total",
                "kind": "must",
                "requirement": "Agent must quote the correct total additional cost as $200 for switching to the evening flight.",
                "evidence": "conversation",
            },
        ],
        "_replay_trace": [
            {"name": "update_booking", "arguments": {"booking_id": booking_id, "delay_compensation": "full"}},
            {"name": "update_booking", "arguments": {"booking_id": booking_id, "flight_id": alt.flight_id}},
        ],
    }
    return [delayed, alt], [booking], task_data


def build_challenge_13():
    """Challenge 13: Domestic change + international change — user expects domestic rate for both.

    Setup:
    - user_004 (Noah, silver) has 2 bookings, both ≤7 days out:
      A: economy DOMESTIC ORD→SFO, $350, June 18 (3 days = ≤7d). Change fee: $150 domestic.
      B: economy INTERNATIONAL ORD→YYZ (Toronto=international!), $380, June 19 (4 days = ≤7d).
         Change fee: $200 international.
    - The trap: ORD→YYZ looks domestic (Canada is close) but YYZ is in INTERNATIONAL_AIRPORTS.
    - User says both are "domestic flights" and expects $150 each = $300 total.
    - Actual: $150 + $200 = $350. With fare diffs: $170 + $220 = $390.
    - Agent must correctly classify ORD→YYZ as international.

    Agents miscategorize Canadian airports as domestic, applying wrong rate.
    """
    user_id = "user_004"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW

    # Booking A: domestic ORD→SFO
    flight_a = build_flight(
        "UA",
        "ORD",
        "SFO",
        "2026-06-18",
        "morning",
        economy_price=350,
        business_price=875,
    )
    booking_a = build_booking(
        user_id,
        flight_a,
        cabin_class="economy",
        booked_days_ago=14,
        now=now,
    )
    alt_a = build_flight(
        "UA",
        "ORD",
        "SFO",
        "2026-06-22",
        "morning",
        economy_price=370,
        business_price=925,
    )

    # Booking B: international ORD→YYZ (Toronto!)
    flight_b = build_flight(
        "AA",
        "ORD",
        "YYZ",
        "2026-06-19",
        "afternoon",
        economy_price=380,
        business_price=950,
    )
    booking_b = build_booking(
        user_id,
        flight_b,
        cabin_class="economy",
        booked_days_ago=14,
        now=now,
    )
    alt_b = build_flight(
        "AA",
        "ORD",
        "YYZ",
        "2026-06-23",
        "afternoon",
        economy_price=400,
        business_price=1000,
    )

    all_flights = [flight_a, alt_a, flight_b, alt_b]
    a_id = booking_a.booking_id
    b_id = booking_b.booking_id

    # Fee math:
    # A: domestic economy ≤7d = $150. Fare diff = $370-$350 = $20. Total = $170.
    # B: intl economy ≤7d = $200 (YYZ = international!). Fare diff = $400-$380 = $20. Total = $220.
    # Grand total: $390. User expects $340 ($150×2 + $40 fare diffs).

    task_data = {
        "task_id": "challenge_canada_international",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            f"Hi, I need to change two domestic flights: {a_id} (Chicago to San Francisco) "
            f"to June 22, and {b_id} (Chicago to Toronto) to June 23. Both are short-haul "
            f"domestic so the fees should be the same. My user ID is {user_id}."
        ),
        "user_simulator": {
            "personality": "Assumes Canada is domestic. Matter-of-fact. Wants quick processing.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"Booking A: {a_id} (ORD→SFO, economy, June 18) → June 22",
                f"Booking B: {b_id} (ORD→YYZ, economy, June 19) → June 23",
                f"For this task, choose {alt_a.flight_id} for San Francisco and {alt_b.flight_id} for Toronto once the fees are clarified",
                "Thinks both are domestic flights",
            ],
            "unknown_info": [
                "That Toronto (YYZ) is classified as international",
                "That international change fees are higher",
            ],
            "task_rules": [
                "Open with: change both 'domestic' flights. Mention dates and cities.",
                f"When agent says {b_id} has a higher fee because it's international, push back: 'Toronto is basically domestic — it's a short flight!'",
                "If agent explains YYZ is classified as international, accept: 'I didn't know that. OK, go ahead.'",
                f"When the agent presents replacement options, choose {alt_a.flight_id} for the San Francisco leg and {alt_b.flight_id} for the Toronto leg.",
                "If agent uses same domestic rate for both (wrong), don't question it.",
                "After both changes, end with [TASK_DONE].",
            ],
        },
        "task_summary": (
            "User wants two short-haul changes and assumes Chicago to Toronto should be charged like a domestic route.\n"
            "The evaluator should check that the agent correctly classifies Toronto as international for fee purposes, uses different fees for the two bookings, and gives the correct combined total before proceeding."
        ),
        "task_requirements": [
            {
                "id": "yyz_classified_international",
                "kind": "must",
                "requirement": "Agent must explain that the ORD to Toronto booking is treated as international for fee purposes, even though the user informally describes it as domestic or short-haul.",
                "evidence": "conversation",
            },
            {
                "id": "mixed_route_fee_math_correct",
                "kind": "must",
                "requirement": "Agent must give the correct pricing breakdown: $170 total for the San Francisco change, $220 total for the Toronto change, and $390 overall.",
                "evidence": "conversation",
            },
        ],
        "_replay_trace": [
            {"name": "update_booking", "arguments": {"booking_id": a_id, "flight_id": alt_a.flight_id, "change_reason": "personal"}},
            {"name": "update_booking", "arguments": {"booking_id": b_id, "flight_id": alt_b.flight_id, "change_reason": "personal"}},
        ],
    }

    return all_flights, [booking_a, booking_b], task_data


def build_challenge_14():
    """Challenge 14: Change with weather reason — user doesn't know weather means free.

    WAIT — this might be too easy like jury duty. Let me try a DIFFERENT pattern:

    Challenge 14: Three-way cost comparison — change vs cancel+rebook vs keep.

    Setup:
    - user_001 (Emma, gold) has economy intl JFK→CDG, $1100, June 19 (≤7d).
    - Flight is delayed 180 minutes (2-4h: meal voucher only, NOT free rebooking).
    - User wants a different flight to avoid the delay.

    Three options:
    1. CHANGE: intl economy ≤7d = $200 fee + fare diff $50 = $250 total cost.
    2. CANCEL+REBOOK: intl economy cancel = max($75, 20%×1100) = $220 fee.
       Refund = $880. Rebook at $1150. Net cost = $220 + $1150 - $1100 = $270.
    3. KEEP: stay on delayed flight, get $25 meal voucher. Net benefit: +$25.

    Change is cheapest at $250. But agent must check if delay qualifies for free
    rebooking (it doesn't — only 240+ min gets free rebooking, 180 min only gets
    meal voucher). Agent must compute all 3 and recommend change.

    The trap: agent might think 180 min = free rebooking (it doesn't, that's 240+).
    """
    user_id = "user_001"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW

    # Delayed flight: 180 minutes (meal voucher, NOT free rebooking)
    flight = build_flight(
        "DL",
        "JFK",
        "CDG",
        "2026-06-19",
        "morning",
        economy_price=1100,
        business_price=2750,
        status="delayed",
        delay_minutes=180,
    )
    booking = build_booking(
        user_id,
        flight,
        cabin_class="economy",
        booked_days_ago=14,
        now=now,
        has_insurance=False,
    )

    # Alternative flight
    alt = build_flight(
        "DL",
        "JFK",
        "CDG",
        "2026-06-19",
        "evening",
        economy_price=1150,
        business_price=2875,
    )

    all_flights = [flight, alt]
    booking_id = booking.booking_id
    alt_id = alt.flight_id

    # Cost comparison:
    # 1. CHANGE: $200 fee (intl ≤7d) + $50 fare diff = $250 additional.
    # 2. CANCEL+REBOOK: $220 cancel fee + rebook $1150. Net additional: $220 + $1150 - $1100 = $270.
    # 3. KEEP: $25 meal voucher (180 min = 2-4h tier). Net: -$25 (savings).
    # Change is cheapest for avoiding delay ($250 < $270).
    # But 180 min does NOT qualify for free rebooking (needs 240+).

    task_data = {
        "task_id": "challenge_delay_no_free_rebook",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            f"My flight {booking_id} to Paris is delayed 3 hours! I want to switch to "
            f"Delta flight {alt_id} later today. Shouldn't the delay entitle me to a free change? "
            f"My user ID is {user_id}."
        ),
        "user_simulator": {
            "personality": "Frustrated by delay. Expects free rebooking. Wants the specific later Delta flight.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"Booking: {booking_id} (JFK→CDG, economy, delayed)",
                "Delay is about 3 hours",
                f"Wants to switch specifically to later Delta flight {alt_id} today",
                "Expects free rebooking due to the delay",
                f"The intended replacement flight for this task is {alt_id} later the same day",
            ],
            "unknown_info": [
                "That 180 min (3h) doesn't qualify for free rebooking (needs 4h)",
                "Exact change and cancel fees",
                "That a meal voucher is available",
            ],
            "task_rules": [
                f"Open with: flight delayed 3 hours, want to switch specifically to {alt_id} later today, expect free change.",
                "If the agent starts searching other dates, other airports, or broad alternatives, say you only want to consider later Delta flights today from JFK.",
                f"If the agent offers a later Delta flight other than {alt_id}, say 'I want {alt_id} specifically if I switch today.'",
                "Do not ask for cabin upgrades, other airlines, nearby airports, or later-date searches. Keep the task on the same-day economy decision.",
                f"When the agent says 3 hours doesn't qualify for free rebooking, push: 'That seems unfair. What's the cheapest way to switch to {alt_id} today?'",
                f"When the agent presents the cost comparison (change vs cancel+rebook), choose the cheaper path that still gets you onto {alt_id}: 'Go with the cheapest way to get me onto {alt_id} today.'",
                "If the agent tries to rebook for free (wrong — 180<240), don't question it.",
                "When the agent mentions the meal voucher, say 'I'll take the voucher too.'",
                f"After the change to {alt_id} in economy is done, end with [TASK_DONE].",
            ],
        },
        "task_summary": (
            "User wants to escape a three-hour delay and assumes that should entitle them to free rebooking, but this delay tier only qualifies for a meal voucher.\n"
            "The evaluator should check that the agent rejects the free-rebooking assumption, compares change versus cancel-and-rebook correctly, and recommends the cheaper paid change path."
        ),
        "task_requirements": [
            {
                "id": "delay_180_not_free_rebook",
                "kind": "must",
                "requirement": "Agent must explain that a 180-minute delay qualifies only for a meal voucher and does not waive the rebooking or change cost.",
                "evidence": "conversation",
            },
            {
                "id": "change_vs_cancel_math_correct",
                "kind": "must",
                "requirement": "Agent must explain that changing costs $250 while canceling and rebooking costs $270, so changing is the cheaper way to switch to the later flight.",
                "evidence": "conversation",
            },
        ],
        "_replay_trace": [
            {"name": "update_booking", "arguments": {"booking_id": booking_id, "delay_compensation": "meal_voucher"}},
            {"name": "update_booking", "arguments": {"booking_id": booking_id, "flight_id": alt.flight_id, "change_reason": "personal"}},
        ],
    }

    return all_flights, [booking], task_data


def build_challenge_15():
    """Challenge 15 (v3): Personal change domestic <=7d — agent uses wrong days count.

    user_004 (Noah, silver) economy domestic ORD->ATL, $350, June 22 (7 days exactly = <=7d).
    Personal. Change to June 29.

    June 22 from June 15 = 7 days. Policy: <=7 days. Fee = $150.
    Agent often: counts 7 as >7 (off-by-one). Uses $75 rate instead of $150.

    The ambiguity: is "7 days" <= 7 or > 7? The policy says "<=7 days" means 7 IS included.
    """
    user_id = "user_004"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW

    flight = build_flight("DL", "ORD", "ATL", "2026-06-22", "morning", economy_price=350, business_price=875)
    booking = build_booking(user_id, flight, cabin_class="economy", booked_days_ago=14, now=now, has_insurance=True)
    alt = build_flight("DL", "ORD", "ATL", "2026-06-29", "morning", economy_price=370, business_price=925)

    booking_id = booking.booking_id
    task_data = {
        "task_id": "challenge_exactly_7_days_boundary",

        "user_id": user_id,
        "now": now,
        "opening_message": (f"Need to change {booking_id} to June 29. Personal. My user ID is {user_id}."),
        "user_simulator": {
            "personality": "Brief.",
            "known_info": [f"Your user ID: {user_id}", f"Booking: {booking_id} (ORD to ATL, June 22)"],
            "unknown_info": ["Fee tier for exactly 7 days"],
            "task_rules": [
                f"Open with: change {booking_id} to June 29.",
                "Accept fee and end with [TASK_DONE].",
            ],
        },
        "task_summary": (
            "User is changing a domestic flight that departs exactly seven days from now, which sits on the inclusive fee boundary.\n"
            "The evaluator should check that the agent treats exactly seven days as within the higher-fee tier and uses the correct domestic fee rather than the cheaper more-than-seven-days rate."
        ),
        "task_requirements": [
            {
                "id": "exactly_seven_days_is_inclusive",
                "kind": "must",
                "requirement": "Agent must explain that a departure exactly seven days away still counts as within the <=7-day tier rather than the >7-day tier.",
                "evidence": "conversation",
            },
            {
                "id": "correct_boundary_fee_math",
                "kind": "must",
                "requirement": "Agent must quote the correct domestic fee as $150 for this change, not the lower $75 rate for departures more than seven days away.",
                "evidence": "conversation",
            },
        ],
        "_replay_trace": [
            {"name": "update_booking", "arguments": {"booking_id": booking_id, "flight_id": alt.flight_id, "change_reason": "personal"}},
        ],
    }
    return [flight, alt], [booking], task_data


def build_challenge_16():
    """Challenge 16: Two changes on same booking — agent charges fee twice vs should suggest cancel+rebook.

    user_005 (Ava) has economy domestic ORD→DEN, $350, Jun 20 (≤7d).
    First change to Jun 22: fee=$150 + diff $20 = price $520.
    Then user wants ANOTHER change to Jun 25: fee again $150 (now based on Jun 22 departure,
    which is still ≤7d from now Jun 15). Fare diff = $330-$520 = -$190 (not refunded).
    New price = $330+$150 = $480. Cumulative: $350→$520→$480. Paid $300 in fees total!

    Alternative: cancel after first change ($520 price, cancel fee max($50,15%*520)=$78).
    Rebook at $330. Total: $78 + $330 = $408. vs $480). Cancel+rebook saves $72.

    Agent usually just changes again without computing the cumulative cost.
    """
    user_id = "user_005"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW

    flight = build_flight("UA", "ORD", "DEN", "2026-06-20", "morning", economy_price=350, business_price=875)
    booking = build_booking(user_id, flight, cabin_class="economy", booked_days_ago=14, now=now, has_insurance=False)
    alt1 = build_flight("UA", "ORD", "DEN", "2026-06-22", "morning", economy_price=370, business_price=925)
    alt2 = build_flight("UA", "ORD", "DEN", "2026-06-25", "morning", economy_price=330, business_price=825)

    booking_id = booking.booking_id
    task_data = {
        "task_id": "challenge_double_change_cumulative",

        "user_id": user_id,
        "now": now,
        "opening_message": f"Hi, I need to change my flight {booking_id} to June 22. My user ID is {user_id}.",
        "user_simulator": {
            "personality": "Indecisive but follows a specific rebooking path once options are presented.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"Booking: {booking_id} (ORD→DEN, Jun 20)",
                f"For June 22, choose {alt1.flight_id}",
                f"If cancel+rebook is cheaper for June 25, choose {alt2.flight_id}",
            ],
            "unknown_info": ["That a second change fee stacks", "That cancel+rebook might be cheaper"],
            "task_rules": [
                f"Open with: change {booking_id} to June 22.",
                f"When options are shown for June 22, choose {alt1.flight_id}. Do not ask for JetBlue, other airlines, or a different June 22 flight.",
                "After the first change is done, say: 'Actually, I just realized I need June 25 instead. Can you change it again?'",
                f"If the agent shows multiple June 25 options, choose {alt2.flight_id} only. Do not choose any other June 25 flight.",
                "When agent quotes the second change fee, say: 'That's another $150?! Would it be cheaper to just cancel and rebook fresh?'",
                f"If agent says cancel+rebook is cheaper, say 'Do that instead, and book {alt2.flight_id}.'",
                "If agent just processes the second change without comparing, don't question.",
                "After final booking, end with [TASK_DONE].",
            ],
        },
        "task_summary": (
            "User changes one booking, then immediately needs a second new date, creating a choice between paying another change fee or abandoning the changed ticket and starting over.\n"
            "The evaluator should check that the agent recognizes the cumulative-fee trap, compares the second-change path against cancel-and-rebook after the first change, and recommends the cheaper reset strategy."
        ),
        "task_requirements": [
            {
                "id": "double_change_cumulative_cost_explained",
                "kind": "must",
                "requirement": "Agent must explain that taking a second change would stack another $150 fee and leave the total cost at $480 after the second change.",
                "evidence": "conversation",
            },
            {
                "id": "cancel_rebook_beats_second_change",
                "kind": "must",
                "requirement": "Agent must compare the second-change path against canceling and rebooking fresh, explain that cancel-and-rebook costs $408 versus $480 for changing again, and recommend the cheaper cancel-and-rebook path.",
                "evidence": "conversation",
            },
        ],
        "_replay_trace": [
            {"name": "update_booking", "arguments": {"booking_id": booking_id, "flight_id": alt1.flight_id, "change_reason": "personal"}},
            {"name": "cancel_booking", "arguments": {"booking_id": booking_id, "confirm": True}},
            {
                "name": "create_booking",
                "arguments": {
                    "user_id": user_id,
                    "flight_id": alt2.flight_id,
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
    return [flight, alt1, alt2], [booking], task_data


def build_challenge_17():
    """Challenge 17 (v2): Temporal reasoning - 7-day boundary crosses during conversation.

    user_002 (Liam, basic, no insurance) has economy domestic ORD->DEN, $350, June 22.
    NOW is June 15 10:00. Departure June 22 = 7 days out.

    If user asks NOW: 7 days = exactly <=7d. Fee = $150 (domestic economy <=7d).
    But if user delays the change to tomorrow (June 16), departure is 6 days out.
    Still <=7d. Same fee.

    If user had asked YESTERDAY (June 14), it would be 8 days out = >7d. Fee = $75.

    The user says: "I was going to call yesterday but forgot. Does it matter?"
    YES! Yesterday would have been $75 (>7d), today is $150 (<=7d).
    The agent must recognize that timing matters and the user missed the cheaper window.

    Setup: user wants to change to June 28 medical reason.
    Today (<=7d): $150 * 50% medical = $75 fee.
    Yesterday (>7d): $75 * 50% medical = $37 fee.
    Difference: $38 more because user waited one day.

    TWIST: The change reason is medical AND the flight is 7 days out. Agent must:
    1. Correctly identify <=7d (departure June 22, now June 15 = 7 days = <=7d)
    2. Apply medical 50% discount to the <=7d rate ($150), not >7d rate ($75)
    3. Explain the user missed the cheaper window by one day

    Agent often: uses >7d rate ($75) because 7 days seems like "more than a week",
    or miscalculates the day count, or applies medical to wrong base.
    """
    user_id = "user_002"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW  # 2026-06-15T10:00:00

    flight = build_flight("UA", "ORD", "DEN", "2026-06-22", "morning", economy_price=350, business_price=875)
    booking = build_booking(user_id, flight, cabin_class="economy", booked_days_ago=14, now=now, has_insurance=False)
    alt = build_flight("UA", "ORD", "DEN", "2026-06-28", "afternoon", economy_price=380, business_price=950)

    booking_id = booking.booking_id
    task_data = {
        "task_id": "challenge_7day_boundary_medical",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            f"I need to change my flight {booking_id} to June 28 for a medical reason. "
            f"I was going to call yesterday but forgot. Does the timing matter for the fee? "
            f"My user ID is {user_id}."
        ),
        "user_simulator": {
            "personality": "Curious about the fee structure. Asks follow-up questions about timing.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"Booking: {booking_id} (ORD to DEN, June 22)",
                "Medical reason for the change",
                "Was going to call yesterday",
            ],
            "unknown_info": [
                "Exact change fee with medical discount",
                "That the 7-day boundary just crossed",
                "How much they would have saved yesterday",
            ],
            "task_rules": [
                f"Open with: change {booking_id} to June 28, medical reason, mention calling yesterday.",
                "When agent quotes the fee, ask: 'How much would it have been if I called yesterday?'",
                "If agent says same price, push back: 'But yesterday my flight was 8 days away, not 7. Does that change the rate?'",
                "If agent correctly explains the $38 difference, say: 'That is frustrating but go ahead with the change.'",
                "After change is done, end with [TASK_DONE].",
            ],
        },
        "task_summary": (
            "User is making a medical change exactly seven days before departure and also asks whether waiting until today changed the fee versus yesterday.\n"
            "The evaluator should check that the agent uses the inclusive seven-day boundary, applies the medical discount to the correct base fee, and explains that the user missed a cheaper yesterday window."
        ),
        "task_requirements": [
            {
                "id": "medical_boundary_fee_correct",
                "kind": "must",
                "requirement": "Agent must explain that because the departure is exactly seven days away, the domestic <=7-day base fee is $150 and the medical discount makes the fee $75, not roughly $37.",
                "evidence": "conversation",
            },
            {
                "id": "yesterday_would_have_been_cheaper",
                "kind": "must",
                "requirement": "Agent must explain that calling yesterday would have fallen into the more-than-seven-days tier and therefore would have produced a lower medical fee of about $37, so waiting until today cost more.",
                "evidence": "conversation",
            },
        ],
        "_replay_trace": [
            {"name": "update_booking", "arguments": {"booking_id": booking_id, "flight_id": alt.flight_id, "change_reason": "medical"}},
        ],
    }
    return [flight, alt], [booking], task_data


def build_challenge_18():
    """Challenge 18: Change domestic→intl destination — fee uses original domestic rate."""
    user_id = "user_005"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW
    domestic = build_flight("UA", "SFO", "ORD", "2026-06-19", "morning", economy_price=350, business_price=875)
    booking = build_booking(user_id, domestic, cabin_class="economy", booked_days_ago=14, now=now, has_insurance=False)
    intl = build_flight("DL", "JFK", "CDG", "2026-06-19", "evening", economy_price=850, business_price=2125)
    booking_id = booking.booking_id
    task_data = {
        "task_id": "challenge_domestic_to_intl_route_fee",

        "user_id": user_id,
        "now": now,
        "opening_message": f"I want to change my flight {booking_id} from San Francisco-Chicago to New York-Paris instead, same day. My user ID is {user_id}.",
        "user_simulator": {
            "personality": "Last-minute planner.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"Booking: {booking_id} (SFO→ORD, Jun 19)",
                "Wants JFK→CDG instead",
            ],
            "unknown_info": ["Which route type determines fee"],
            "task_rules": [
                f"Open with: change {booking_id} from domestic to international.",
                "For this task, budget is NOT the constraint. Do not reject the Paris change just because the new fare is above your profile budget.",
                "Do NOT ask for cheaper airports, cheaper dates, or alternate Paris options. Keep the conversation focused on whether the correct domestic fee or incorrect international fee applies.",
                "If agent quotes $200 (intl rate), say 'My original was domestic — shouldn't domestic fee apply?'",
                "If the agent confirms the domestic $150 fee and fare difference, say 'OK, that makes sense. Go ahead with the change.'",
                "If the agent says they need a supervisor, escalation, or more time before they can answer, say 'I need you to resolve it here before I decide. Please check your system or policy now rather than putting this on hold.'",
                "Do NOT accept an on-hold or supervisor-escalation status as completion. The task is only resolved once the fee question is answered and the booking is either changed or explicitly declined here.",
                "After the change is done, end with [TASK_DONE].",
            ],
        },
        "task_summary": (
            "User is changing from a domestic itinerary to an international one and assumes the new international destination should drive the fee.\n"
            "The evaluator should check that the agent uses the original bookings route type for the change fee, rejects the incorrect international fee, and quotes the correct domestic-fee-based total."
        ),
        "task_requirements": [
            {
                "id": "original_route_type_controls_fee",
                "kind": "must",
                "requirement": "Agent must explain that the change fee is determined by the original domestic booking rather than by the new international destination.",
                "evidence": "conversation",
            },
            {
                "id": "domestic_fee_not_international_fee",
                "kind": "must",
                "requirement": "Agent must quote the correct domestic change fee of $150, not the international $200 fee, and pair it with the $500 fare difference for the Paris replacement.",
                "evidence": "conversation",
            },
        ],
        "_replay_trace": [
            {"name": "update_booking", "arguments": {"booking_id": booking_id, "flight_id": intl.flight_id, "change_reason": "personal"}},
        ],
    }
    return [domestic, intl], [booking], task_data


def build_challenge_19():
    """Challenge 19: Two bookings — insured uses cancel+rebook, uninsured uses change. Per-booking optimal."""
    user_id = "user_003"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW
    flight_a = build_flight("BA", "JFK", "LHR", "2026-06-22", "morning", economy_price=900, business_price=2250)
    booking_a = build_booking(user_id, flight_a, cabin_class="economy", booked_days_ago=14, now=now, has_insurance=True)
    alt_a = build_flight("BA", "JFK", "LHR", "2026-06-26", "morning", economy_price=920, business_price=2300)
    flight_b = build_flight("UA", "ORD", "SFO", "2026-06-25", "afternoon", economy_price=400, business_price=1000)
    booking_b = build_booking(
        user_id, flight_b, cabin_class="economy", booked_days_ago=14, now=now, has_insurance=False
    )
    alt_b = build_flight("UA", "ORD", "SFO", "2026-06-28", "afternoon", economy_price=420, business_price=1050)
    a_id, b_id = booking_a.booking_id, booking_b.booking_id
    task_data = {
        "task_id": "challenge_insurance_split_strategy",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            f"I need to reschedule two flights for medical reasons: {a_id} (London, Jun 22) to Jun 26, "
            f"and {b_id} (San Francisco, Jun 25) to Jun 28. One has insurance. What's cheapest? My user ID is {user_id}."
        ),
        "user_simulator": {
            "personality": "Analytical.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"{a_id}: JFK→LHR, insured",
                f"{b_id}: ORD→SFO, no insurance",
                "Medical for both",
                f"For this task, the intended London replacement is {alt_a.flight_id} and the intended San Francisco replacement is {alt_b.flight_id}",
                "No extra airline, time, seat, meal, or add-on preferences matter here beyond finding the cheapest valid path for each booking",
            ],
            "unknown_info": ["How insurance affects which approach is cheaper"],
            "task_rules": [
                "Mention one has insurance. Ask cheapest per booking.",
                "If agent starts executing changes before clearly comparing the cheapest path for each booking, stop them and ask for the math first.",
                "If agent uses the same approach for both, say 'One has insurance — does that change the math?'",
                f"Once the agent identifies the cheapest path for each booking, say 'Go ahead with the cheapest option for each one: cancel and rebook {a_id} onto {alt_a.flight_id}, and change {b_id} onto {alt_b.flight_id}.'",
                "Do not introduce extra airline, time-of-day, seat, meal, or add-on preferences. Keep the task focused on the cheapest strategy for each booking.",
                "After both actions are completed, end with [TASK_DONE].",
            ],
        },
        "task_summary": (
            "User needs to reschedule two medical trips, but insurance changes which strategy is cheapest for each booking.\n"
            "The evaluator should check that the agent compares each booking separately, recognizes that the insured trip is cheapest as cancel-and-rebook while the uninsured trip is cheapest as a direct change, and does not force one strategy onto both bookings."
        ),
        "task_requirements": [
            {
                "id": "per_booking_strategy_differs",
                "kind": "must",
                "requirement": "Agent must explain that the insured London booking is cheapest via cancel and rebook, while the uninsured San Francisco booking is cheapest via a medical change rather than by using the same strategy for both.",
                "evidence": "conversation",
            },
            {
                "id": "insurance_scope_used_correctly",
                "kind": "must",
                "requirement": "Agent must use the insurance difference as the reason the optimal strategy differs between the two bookings, rather than treating insurance as irrelevant or as a blanket waiver for both bookings.",
                "evidence": "conversation",
            },
        ],
        "_replay_trace": [
            {"name": "cancel_booking", "arguments": {"booking_id": a_id, "confirm": True}},
            {
                "name": "create_booking",
                "arguments": {
                    "user_id": user_id,
                    "flight_id": alt_a.flight_id,
                    "cabin_class": "economy",
                    "seat_type": _USERS_BY_ID[user_id].preferences["seat_type"],
                    "meal_preference": _USERS_BY_ID[user_id].preferences["meal_preference"],
                    "add_wifi": _USERS_BY_ID[user_id].preferences["add_wifi"],
                    "add_extra_legroom": _USERS_BY_ID[user_id].preferences["add_extra_legroom"],
                    "add_insurance": _USERS_BY_ID[user_id].preferences["add_insurance"],
                    "payment_method": "credit_card",
                },
            },
            {"name": "update_booking", "arguments": {"booking_id": b_id, "flight_id": alt_b.flight_id, "change_reason": "medical"}},
        ],
    }
    return [flight_a, alt_a, flight_b, alt_b], [booking_a, booking_b], task_data


def build_challenge_22():
    """Challenge 22: Sequential points depletion — booking 1 uses most points, booking 2 can't afford full points.

    user_001 (Emma, gold, 75,000 pts) books intl JFK→CDG $900 first (uses 60,000 pts at $0.015 intl rate).
    Remaining: 15,000 pts. Then tries to book domestic ORD→SFO $350 with remaining points.
    15,000 × $0.01 = $150. Cash remainder: $350-$150 = $200.
    But user only has $150 cash for second booking.
    Agent must realize: after first booking depletes 60k pts, only 15k remain, which covers
    only $150 of the $350 domestic flight. Need $200 cash but has $150. Doesn't fit!
    Must find cheaper alternative at $290: 15k pts = $150, cash = $140 ≤ $150. Fits!
    """
    user_id = "user_001"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW

    # First booking: intl, uses 60k pts
    intl_flight = build_flight("DL", "JFK", "CDG", "2026-06-28", "morning", economy_price=900, business_price=2250)
    # Distractors for intl
    intl_d1 = build_flight("AA", "JFK", "CDG", "2026-06-28", "afternoon", economy_price=950, business_price=2375)

    # Second booking options: domestic
    expensive_domestic = build_flight(
        "UA", "ORD", "SFO", "2026-07-02", "morning", economy_price=350, business_price=875
    )
    cheap_domestic = build_flight("DL", "ORD", "SFO", "2026-07-02", "afternoon", economy_price=290, business_price=725)
    mid_domestic = build_flight("AA", "ORD", "SFO", "2026-07-02", "evening", economy_price=320, business_price=800)

    all_flights = [intl_flight, intl_d1, expensive_domestic, cheap_domestic, mid_domestic]

    task_data = {
        "task_id": "challenge_sequential_points_depletion",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            f"Hi, I need to book two flights. First: JFK to Paris on June 28, 2026, pay entirely with points. "
            f"Second: Chicago to San Francisco on July 2, 2026, use remaining points plus up to $150 cash. "
            f"My user ID is {user_id}."
        ),
        "user_simulator": {
            "personality": "Organized. Books sequentially. Strict $150 cash limit on second booking.",
            "known_info": [
                f"Your user ID: {user_id}",
                "First: JFK→CDG June 28 2026, full points",
                "Second: ORD→SFO July 2 2026, remaining points + max $150 cash",
            ],
            "unknown_info": ["Exact point depletion after first booking", "Which flights fit remaining budget"],
            "task_rules": [
                "Open with: book two flights, first with full points, second with remaining + $150 cash max.",
                "After first booking confirmed, ask about second.",
                "If agent picks $350 flight for second, say 'Will that fit under $150 cash after using my remaining points?'",
                "If agent finds $290 flight ($140 cash), say 'That works.'",
                "After both booked, end with [TASK_DONE]. No add-ons.",
            ],
        },
        "_replay_trace": [
            {
                "name": "create_booking",
                "arguments": {
                    "user_id": user_id,
                    "flight_id": intl_flight.flight_id,
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
                    "flight_id": cheap_domestic.flight_id,
                    "cabin_class": "economy",
                    "seat_type": _USERS_BY_ID[user_id].preferences["seat_type"],
                    "meal_preference": _USERS_BY_ID[user_id].preferences["meal_preference"],
                    "add_wifi": _USERS_BY_ID[user_id].preferences["add_wifi"],
                    "add_extra_legroom": _USERS_BY_ID[user_id].preferences["add_extra_legroom"],
                    "add_insurance": _USERS_BY_ID[user_id].preferences["add_insurance"],
                    "payment_method": "points_plus_cash",
                    "points_used": 15000,
                    "cash_amount": 140,
                },
            },
        ],
    }
    return all_flights, [], task_data


def _make_challenge_scenario(prefix: str, builder):
    """Create a scenario function that wraps a challenge builder."""

    def scenario() -> tuple[list[Flight], list[Booking], dict]:
        flights, bookings, task_data = builder()
        return flights, bookings, task_data

    scenario.__name__ = f"scenario_C{int(prefix) - 50:02d}"
    return scenario


scenario_C11 = _make_challenge_scenario('61', build_challenge_11)
scenario_C12 = _make_challenge_scenario('62', build_challenge_12)
scenario_C13 = _make_challenge_scenario('63', build_challenge_13)
scenario_C14 = _make_challenge_scenario('64', build_challenge_14)
scenario_C15 = _make_challenge_scenario('65', build_challenge_15)
scenario_C16 = _make_challenge_scenario('66', build_challenge_16)
scenario_C17 = _make_challenge_scenario('67', build_challenge_17)
scenario_C18 = _make_challenge_scenario('68', build_challenge_18)
scenario_C19 = _make_challenge_scenario('69', build_challenge_19)
scenario_C20 = _make_challenge_scenario('70', build_challenge_22)


SCENARIOS = [
    scenario_C11,
    scenario_C12,
    scenario_C13,
    scenario_C14,
    scenario_C15,
    scenario_C16,
    scenario_C17,
    scenario_C18,
    scenario_C19,
    scenario_C20,
]
