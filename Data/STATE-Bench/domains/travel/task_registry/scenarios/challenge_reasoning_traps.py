"""Travel challenge scenarios centered on hidden constraints and reasoning traps."""


from __future__ import annotations


from domains.travel.schemas import Booking, Flight

from domains.travel.task_registry._builders import (
    _USERS_BY_ID,
    DEFAULT_NOW,
    build_booking,
    build_flight,
    build_route_flights,
)


def build_challenge_25():
    """Challenge 25: Bereavement discount applies to ONE booking only, not both.

    user_001 (Emma, gold) has 2 bookings:
    A: economy intl JFK->CDG, $900, June 19 (4 days = <=7d). Bereavement reason.
       Fee: intl economy <=7d = $200. Bereavement 75% discount -> $50.
       New flight $950. Fare diff $50. Total additional: $50 + $50 = $100.
    B: economy domestic ORD->SFO, $400, June 25 (10 days = >7d). Personal reason.
       Fee: domestic economy >7d = $75. No discount (personal).
       New flight $420. Fare diff $20. Total additional: $75 + $20 = $95.

    Combined: $100 + $95 = $195.

    Trap: Agent sees bereavement mentioned and applies the 75% discount to BOTH bookings.
    Wrong answer: $50 + (25% of $75 = $18) + fare diffs = $50 + $18 + $50 + $20 = $138.
    Correct: $50 + $75 + $50 + $20 = $195.
    """
    user_id = "user_001"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW

    flight_a = build_flight("AF", "JFK", "CDG", "2026-06-19", "morning", economy_price=900, business_price=2250)
    booking_a = build_booking(
        user_id, flight_a, cabin_class="economy", booked_days_ago=14, now=now, has_insurance=False
    )
    alt_a = build_flight("AF", "JFK", "CDG", "2026-06-24", "morning", economy_price=950, business_price=2375)

    flight_b = build_flight("UA", "ORD", "SFO", "2026-06-25", "afternoon", economy_price=400, business_price=1000)
    booking_b = build_booking(
        user_id, flight_b, cabin_class="economy", booked_days_ago=14, now=now, has_insurance=False
    )
    alt_b = build_flight("UA", "ORD", "SFO", "2026-06-28", "afternoon", economy_price=420, business_price=1050)

    a_id = booking_a.booking_id
    b_id = booking_b.booking_id

    task_data = {
        "task_id": "challenge_bereavement_one_booking_only",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            f"I have a family bereavement and need to postpone my trip. "
            f"Please change {a_id} (Paris flight) to June 24 — that is the bereavement-related one. "
            f"Also change {b_id} (San Francisco) to June 28 — that one is just personal scheduling. "
            f"My user ID is {user_id}."
        ),
        "user_simulator": {
            "personality": "Clear communicator. Distinguishes reasons for each booking. Wants exact costs.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"Booking A: {a_id} (JFK to CDG, June 19) - bereavement reason",
                f"Booking B: {b_id} (ORD to SFO, June 25) - personal reason",
                "Bereavement only applies to the Paris trip",
            ],
            "unknown_info": [
                "Exact fee formulas",
                "That bereavement gives 75% discount",
                "That personal has no discount",
            ],
            "task_rules": [
                f"Open with: bereavement for {a_id}, personal for {b_id}. Clearly state different reasons.",
                "When agent quotes fees, ask: 'What is the total for both changes combined?'",
                "If agent applies bereavement discount to both, say: 'Wait, the San Francisco change is personal, not bereavement. Does that affect the fee?'",
                "If agent correctly charges different fees, agree: 'Go ahead with both changes.'",
                "After both changes done, end with [TASK_DONE].",
            ],
        },
        "task_summary": (
            "User changes two bookings in the same conversation, but bereavement only applies to one of them.\n"
            "The evaluator should check that the agent keeps the change reasons separate per booking, applies the bereavement discount only to the Paris booking, and does not incorrectly discount the personal San Francisco change."
        ),
        "task_requirements": [
            {
                "id": "bereavement_not_blanket_discount",
                "kind": "must",
                "requirement": "Agent must explain or otherwise make clear that the bereavement discount applies only to the Paris booking and not to the separate personal San Francisco change.",
                "evidence": "conversation",
            },
            {
                "id": "different_fees_for_two_reasons",
                "kind": "must",
                "requirement": "Agent must distinguish the two fee paths by treating the Paris change as bereavement-discounted and the San Francisco change as an ordinary personal-fee change, rather than quoting one blended or uniformly discounted rule for both.",
                "evidence": "conversation",
            },
        ],
        "_replay_trace": [
            {"name": "update_booking", "arguments": {"booking_id": a_id, "flight_id": alt_a.flight_id, "change_reason": "bereavement"}},
            {"name": "update_booking", "arguments": {"booking_id": b_id, "flight_id": alt_b.flight_id, "change_reason": "personal"}},
        ],
    }
    return [flight_a, alt_a, flight_b, alt_b], [booking_a, booking_b], task_data


def build_challenge_26():
    """Challenge 26: Weather mention is casual context, not the change reason. User does NOT correct agent.

    user_002 (Liam, basic) has economy domestic ORD->DEN, $350, June 20 (<=7d).
    User casually says: "weather looks terrible, wanna push my trip."
    change_reason should be personal ($150) not weather ($0).

    CRITICAL: The user does NOT correct the agent if it uses weather reason.
    The user just accepts whatever the agent says. The judge must catch the error.
    """
    user_id = "user_002"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW

    flight = build_flight("UA", "ORD", "DEN", "2026-06-20", "morning", economy_price=350, business_price=875)
    booking = build_booking(user_id, flight, cabin_class="economy", booked_days_ago=14, now=now, has_insurance=False)
    alt = build_flight("UA", "ORD", "DEN", "2026-06-27", "morning", economy_price=380, business_price=950)

    booking_id = booking.booking_id
    task_data = {
        "task_id": "challenge_weather_mention_not_reason",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            f"Hey, the weather forecast for Denver next weekend is looking awful - "
            f"thunderstorms the whole time. I wanna push my trip {booking_id} "
            f"to June 27 instead. My user ID is {user_id}."
        ),
        "user_simulator": {
            "personality": "Casual, trusting. Does not know the difference between weather exemption and personal change.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"Booking: {booking_id} (ORD to DEN, June 20)",
                "Bad weather forecast in Denver",
                "Wants to move to June 27",
            ],
            "unknown_info": [
                "Change fee policies",
                "That weather exemptions only apply to airline disruptions",
                "The difference between weather and personal change reasons",
            ],
            "task_rules": [
                f"Open with: bad weather forecast, want to push {booking_id} to June 27.",
                "Do NOT mention or clarify that this is a personal choice vs airline weather event.",
                "If agent says the change is free, just say: 'Great, that works!'",
                "If agent asks if this is an airline weather event, say: 'No, the flight is fine, I just do not want to go in bad weather.'",
                "If agent charges a fee, say: 'OK, go ahead.'",
                "After change is done, end with [TASK_DONE].",
            ],
        },
        "task_summary": (
            "User casually mentions bad weather but is really making a voluntary personal change, which makes the word choice itself a trap.\n"
            "The evaluator should check that the agent does not convert that casual weather mention into the free weather exemption and instead keeps the fee reasoning on the ordinary personal-change path."
        ),
        "task_requirements": [
            {
                "id": "weather_mention_not_exemption",
                "kind": "must",
                "requirement": "Agent must treat the request as a personal change rather than as a weather-exempt airline disruption, even though the user mentions a bad forecast.",
                "evidence": "conversation",
            },
            {
                "id": "must_not_quote_free_weather_change",
                "kind": "must_not",
                "requirement": "Agent must not tell the user that this change is free because of weather unless the conversation establishes an actual airline weather disruption affecting the booking.",
                "evidence": "conversation",
            },
        ],
        "_replay_trace": [
            {"name": "update_booking", "arguments": {"booking_id": booking_id, "flight_id": alt.flight_id, "change_reason": "personal"}},
        ],
    }
    return [flight, alt], [booking], task_data


def build_challenge_27():
    """Challenge 27: Jury duty exemption applies to outbound only, return is personal.

    user_004 (Noah, silver, insurance=True) has round trip:
    A: economy domestic ORD->MIA, $350, June 19 (<=7d). Change to June 26 for jury duty.
    B: economy domestic MIA->ORD, $320, June 23 (>7d). Change to June 30 personal.

    A: jury_duty = free change ($0). New flight $380. Fare diff $30. Total additional: $30.
    B: personal >7d domestic = $75. New flight $340. Fare diff $20. Total additional: $95.
    Combined: $125.

    Agent sees "jury duty" context and applies free change to BOTH legs. Wrong result: $50 total.
    Correct: only outbound A gets jury duty exemption. Return B is personal ($75 fee).
    """
    user_id = "user_004"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW

    out_flight = build_flight("AA", "ORD", "MIA", "2026-06-19", "morning", economy_price=350, business_price=875)
    booking_out = build_booking(
        user_id, out_flight, cabin_class="economy", booked_days_ago=14, now=now, has_insurance=True
    )
    alt_out = build_flight("AA", "ORD", "MIA", "2026-06-26", "morning", economy_price=380, business_price=950)

    ret_flight = build_flight("AA", "MIA", "ORD", "2026-06-23", "afternoon", economy_price=320, business_price=800)
    booking_ret = build_booking(
        user_id, ret_flight, cabin_class="economy", booked_days_ago=14, now=now, has_insurance=True
    )
    alt_ret = build_flight("AA", "MIA", "ORD", "2026-06-30", "afternoon", economy_price=340, business_price=850)

    out_id = booking_out.booking_id
    ret_id = booking_ret.booking_id

    task_data = {
        "task_id": "challenge_jury_duty_one_leg_only",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            f"I got called for jury duty starting June 23, so I need to push my "
            f"outbound flight {out_id} to Miami to June 26. And I will need to move "
            f"my return {ret_id} to June 30 to match. My user ID is {user_id}."
        ),
        "user_simulator": {
            "personality": "Matter-of-fact. Provides both booking IDs and dates upfront.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"Outbound: {out_id} (ORD to MIA, June 19) - jury duty is the reason",
                f"Return: {ret_id} (MIA to ORD, June 23) - rescheduling to match new outbound",
                "Jury duty starts June 23",
            ],
            "unknown_info": [
                "Exact change fees",
                "That jury duty exemption only applies to the disrupted leg",
            ],
            "task_rules": [
                f"Open with: jury duty, need to change both {out_id} and {ret_id}.",
                "Do NOT clarify that the return change is personal. Let the agent figure it out.",
                "If the agent only checks the June 30 return in the morning, ask them to check other times on June 30 before changing dates or airports.",
                f"If the agent finds the June 30 American return {alt_ret.flight_id}, accept it.",
                "If agent says both changes are free, do NOT correct them. Just say 'Great!' and do not raise the return-fee issue later.",
                "If agent charges a fee for the return and explains why, say 'OK, makes sense.'",
                "Do NOT volunteer that the return should be personal or that the return should have a $75 fee unless the agent already brings up that distinction.",
                "For this task, budget is NOT the constraint. Do not reject valid June 26 / June 30 options just because the face-value ticket totals exceed your profile budget.",
                "Do NOT drift into alternate airports or later dates unless the agent clearly establishes there is no valid June 30 return option after checking other times that same day.",
                "After both changes done, end with [TASK_DONE].",
            ],
        },
        "task_summary": (
            "User has a round trip affected by jury duty on only one leg, with the return being moved only to match the outbound adjustment.\n"
            "The evaluator should check that the agent applies the jury-duty exemption only to the outbound leg, keeps the return on the ordinary personal path, and does not spread the free exemption across both bookings."
        ),
        "task_requirements": [
            {
                "id": "jury_duty_only_one_leg",
                "kind": "must",
                "requirement": "Agent must make clear that jury duty is the reason for the outbound change only and that the return change is a separate personal rescheduling step.",
                "evidence": "conversation",
            },
            {
                "id": "must_not_zero_both_legs",
                "kind": "must_not",
                "requirement": "Agent must not apply a blanket free jury-duty exemption to both legs of the round trip.",
                "evidence": "conversation",
            },
        ],
        "_replay_trace": [
            {"name": "update_booking", "arguments": {"booking_id": out_id, "flight_id": alt_out.flight_id, "change_reason": "jury_duty"}},
            {"name": "update_booking", "arguments": {"booking_id": ret_id, "flight_id": alt_ret.flight_id, "change_reason": "personal"}},
        ],
    }
    return [out_flight, alt_out, ret_flight, alt_ret], [booking_out, booking_ret], task_data


def build_challenge_28():
    """Challenge 28: Insurance does NOT waive change fees - only covers cancellation.

    user_003 (Olivia, platinum, insurance=True) has economy intl JFK->CDG, $900, June 20 (<=7d).
    Wants to change to June 27, personal reason.

    Agent sees has_insurance=True and may assume change fee is waived.
    WRONG: insurance only covers CANCELLATION fees, not change fees.
    Change fee: intl economy <=7d = $200. Insurance irrelevant.

    The user explicitly asks "will my insurance cover the change fee?"
    Correct answer: No, insurance only covers cancellation, not changes.

    New flight $950. Fare diff $50. Total additional: $200 + $50 = $250.
    """
    user_id = "user_003"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW

    flight = build_flight("AF", "JFK", "CDG", "2026-06-20", "morning", economy_price=900, business_price=2250)
    booking = build_booking(user_id, flight, cabin_class="economy", booked_days_ago=14, now=now, has_insurance=True)
    alt = build_flight("AF", "JFK", "CDG", "2026-06-27", "morning", economy_price=950, business_price=2375)

    booking_id = booking.booking_id
    task_data = {
        "task_id": "challenge_insurance_no_change_fee_waiver",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            f"I need to change my flight {booking_id} to June 27. I have travel insurance "
            f"on this booking - will that cover the change fee? My user ID is {user_id}."
        ),
        "user_simulator": {
            "personality": "Hopeful that insurance helps. Trusts agent expertise on policy.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"Booking: {booking_id} (JFK to CDG, economy, June 20)",
                "Has travel insurance on this booking",
                "Wants June 27 instead",
            ],
            "unknown_info": [
                "Whether insurance covers change fees",
                "Exact change fee amount",
            ],
            "task_rules": [
                f"Open with: change {booking_id} to June 27, ask if insurance covers the change fee.",
                "If agent says insurance waives the change fee ($0), say: 'Great!' Do NOT correct them.",
                "If agent correctly says insurance does not cover change fees and quotes $200, "
                "say: 'That is disappointing but go ahead with the change.'",
                "After change is done, end with [TASK_DONE].",
            ],
        },
        "task_summary": (
            "User has insurance on an international booking and assumes that insurance should also waive the change fee.\n"
            "The evaluator should check that the agent distinguishes change fees from cancellation coverage, explicitly keeps the insurance change-fee waiver off the table, and quotes the correct $250 additional cost if the user proceeds."
        ),
        "task_requirements": [
            {
                "id": "insurance_does_not_waive_change_fee",
                "kind": "must",
                "requirement": "Agent must make clear that travel insurance does not waive the change fee for this booking change and only affects cancellation coverage.",
                "evidence": "conversation",
            },
            {
                "id": "quote_change_cost_with_fee_and_diff",
                "kind": "must",
                "requirement": "Agent must explain or otherwise make clear that completing this change costs $250 total in additional charges, made up of a $200 change fee plus a $50 fare difference.",
                "evidence": "conversation",
            },
        ],
        "_replay_trace": [
            {"name": "update_booking", "arguments": {"booking_id": booking_id, "flight_id": alt.flight_id, "change_reason": "personal"}},
        ],
    }
    return [flight, alt], [booking], task_data


def build_challenge_29():
    """Challenge 29: Negative fare difference not refunded on changes.

    user_005 (Ava, basic, no insurance) has economy domestic ORD->SFO $500, June 22 (<=7d).
    Wants to change to a CHEAPER flight on June 28, $380.

    Change fee: domestic economy <=7d = $150.
    Fare diff: $380 - $500 = -$120. Negative diff NOT refunded.
    price_paid = $380 + $150 = $530.

    User thinks: "cheaper flight, so I'll save money on the change."
    Reality: $530 total (MORE than original $500). The $120 savings is eaten by $150 fee.
    Net additional cost: $30.

    Alternative: cancel + rebook.
    Cancel fee: max($50, 15%*500) = $75. Refund $425.
    Rebook $380. Total new spend: $75 + $380 = $455 (less than $500!).

    Cancel+rebook SAVES $45 vs original. Change COSTS $30 more.
    Optimal: cancel+rebook. But agent usually just changes.

    Unique lesson: negative fare diff is lost on changes. Cancel captures the savings.
    """
    user_id = "user_005"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW

    flight = build_flight("UA", "ORD", "SFO", "2026-06-22", "afternoon", economy_price=500, business_price=1250)
    booking = build_booking(user_id, flight, cabin_class="economy", booked_days_ago=14, now=now, has_insurance=False)
    alt = build_flight("UA", "ORD", "SFO", "2026-06-28", "afternoon", economy_price=380, business_price=950)

    booking_id = booking.booking_id
    task_data = {
        "task_id": "challenge_negative_fare_diff_no_refund",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            f"I want to switch my flight {booking_id} to June 28. I noticed flights "
            f"are cheaper that week so hopefully I will save some money! My user ID is {user_id}."
        ),
        "user_simulator": {
            "personality": "Optimistic about saving money. Expects the cheaper flight to reduce total cost.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"Booking: {booking_id} (ORD to SFO, economy, $500, June 22)",
                "Wants June 28 instead",
                "Expects to save money with cheaper flight",
            ],
            "unknown_info": [
                "That negative fare diffs are not refunded on changes",
                "The change fee amount",
                "That cancel+rebook could be cheaper",
            ],
            "task_rules": [
                f"Open with: switch {booking_id} to June 28, expect savings.",
                "If agent just changes without comparing to cancel+rebook, "
                "ask: 'Wait, if the new flight is $120 cheaper, why did my total go UP?'",
                "If agent explains the fee and recommends cancel+rebook, say: 'That makes sense. Do the cancel and rebook.'",
                "If agent says you will save money by changing, do NOT correct them.",
                "After the action is done, end with [TASK_DONE].",
            ],
        },
        "task_summary": (
            "User sees a cheaper replacement flight and assumes that changing should save money, but the change path discards the negative fare difference while cancel-and-rebook captures it.\n"
            "The evaluator should check that the agent compares both paths, explains why the direct change is actually more expensive, and recommends cancel plus rebook as the cheaper outcome."
        ),
        "task_requirements": [
            {
                "id": "negative_fare_diff_not_refunded_on_change",
                "kind": "must",
                "requirement": "Agent must make clear that changing to the cheaper flight does not return the $120 negative fare difference as savings on the change path.",
                "evidence": "conversation",
            },
            {
                "id": "compare_change_vs_cancel_rebook",
                "kind": "must",
                "requirement": "Agent must compare the direct-change path against cancel and rebook, rather than treating the cheaper ticket price alone as sufficient reasoning.",
                "evidence": "conversation",
            },
            {
                "id": "recommend_cancel_rebook",
                "kind": "must",
                "requirement": "Agent must recommend canceling and rebooking because that path is cheaper than changing this booking.",
                "evidence": "conversation",
            },
        ],
        "_replay_trace": [
            {"name": "cancel_booking", "arguments": {"booking_id": booking_id, "confirm": True}},
            {
                "name": "create_booking",
                "arguments": {
                    "user_id": user_id,
                    "flight_id": alt.flight_id,
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
    return [flight, alt], [booking], task_data


def build_challenge_30():
    """Challenge 30: Three policies interact: basic_economy + 180min delay + insurance.

    user_004 (Noah, silver, insurance=True) has basic_economy domestic ORD->DEN, $200,
    June 16 (tomorrow). Flight delayed 180 minutes.

    Three policies interact:
    1. Basic economy: can't change, can't cancel (past 24h window)
    2. 180 min delay: meal voucher only ($25), NOT free rebooking (needs 240+)
    3. Insurance: overrides cancel restriction -> free cancel

    Agent must synthesize:
    - Can't CHANGE (basic economy blocks changes regardless of delay)
    - CAN cancel (insurance overrides basic economy cancel restriction)
    - 180 min delay provides meal voucher but NOT free rebooking
    - If cancelling: insurance = free cancel ($0 fee), get $200 refund
    - Then rebook on alt flight at $250 economy (not basic_economy)
    - Net additional: $250 - $200 = $50 extra

    Common agent errors:
    a) Thinks 180 min delay = free change (wrong threshold)
    b) Thinks basic_economy = totally stuck (forgets insurance overrides cancel)
    c) Doesn't check delay compensation in addition to cancel/rebook
    """
    user_id = "user_004"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW

    flight = build_flight(
        "UA",
        "ORD",
        "DEN",
        "2026-06-16",
        "afternoon",
        economy_price=350,
        business_price=875,
        status="delayed",
        delay_minutes=180,
    )
    flight.cabin_prices["basic_economy"] = 200
    booking = build_booking(
        user_id, flight, cabin_class="basic_economy", booked_days_ago=5, now=now, has_insurance=True
    )

    # Alt flight: next day morning, economy only (no basic_economy)
    alt = build_flight("UA", "ORD", "DEN", "2026-06-17", "morning", economy_price=250, business_price=625)

    booking_id = booking.booking_id
    task_data = {
        "task_id": "challenge_triple_policy_interaction",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            f"My flight {booking_id} is delayed 3 hours! What can I do? "
            f"I want to get to Denver as soon as possible, but if there is nothing workable left today I can take the next available flight. My user ID is {user_id}."
        ),
        "user_simulator": {
            "personality": "Frustrated by delay. Wants options. Does not know their fare class or policies.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"Booking: {booking_id} (ORD to DEN, delayed 3 hours)",
                "Has travel insurance",
                "Wants to get to Denver ASAP, but will take the next available flight if nothing workable remains today",
            ],
            "unknown_info": [
                "That the booking is basic_economy",
                "That basic economy can't be changed",
                "That 180 min delay doesn't qualify for free rebooking",
                "That insurance can override the cancel restriction",
                "Meal voucher eligibility",
            ],
            "task_rules": [
                f"Open with: flight {booking_id} delayed 3 hours, what are my options?",
                "If agent says you cannot change or cancel (stuck), say: 'But I have travel insurance! Does that help?'",
                "If the agent says there is nothing earlier left today, ask whether insurance lets you cancel and rebook the next available economy flight, even if it is tomorrow.",
                "If agent says delay qualifies for free rebook, do NOT correct them.",
                "If agent offers cancel+rebook path, ask: 'Is there any compensation for the delay too?'",
                "If the agent confirms there is no better option left today but offers the next available economy replacement, say: 'OK, please go ahead with cancel+rebook onto the next available economy flight and include the meal voucher.'",
                "If the agent only proposes rebooking you onto the same delayed flight, ask whether there is a later or next-day replacement you can switch to after canceling.",
                "After booking is done, end with [TASK_DONE].",
            ],
        },
        "task_summary": (
            "A delayed basic-economy booking sits at the intersection of three policies: basic economy blocks changes, a 3-hour delay earns only a meal voucher, and insurance rescues the cancellation path.\n"
            "The evaluator should check that the agent keeps those policy lines separate, does not invent a free delay-based rebooking right, and lands on the insurance-backed cancel-plus-rebook path while also mentioning the meal voucher."
        ),
        "task_requirements": [
            {
                "id": "basic_economy_blocks_change",
                "kind": "must",
                "requirement": "Agent must make clear that this basic economy booking cannot simply be changed onto another flight.",
                "evidence": "conversation",
            },
            {
                "id": "delay_only_meal_voucher_not_free_rebook",
                "kind": "must",
                "requirement": "Agent must make clear that the 3-hour delay qualifies only for the meal voucher and does not by itself create a free rebooking right.",
                "evidence": "conversation",
            },
            {
                "id": "insurance_enables_cancel_rebook",
                "kind": "must",
                "requirement": "Agent must identify cancel plus rebook, enabled by the insurance-backed cancellation path, as the workable way to move the traveler onto the next available economy option.",
                "evidence": "conversation",
            },
        ],
        "_replay_trace": [
            {"name": "update_booking", "arguments": {"booking_id": booking_id, "delay_compensation": "meal_voucher"}},
            {"name": "cancel_booking", "arguments": {"booking_id": booking_id, "confirm": True}},
            {
                "name": "create_booking",
                "arguments": {
                    "user_id": user_id,
                    "flight_id": alt.flight_id,
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
    return [flight, alt], [booking], task_data


def build_challenge_31():
    """Challenge 31: Two bookings for same user, different cabins -> different change fees.

    user_001 (Emma, gold) has:
    A: economy intl JFK->LHR, $800, June 20 (<=7d). Personal change to June 26.
       Fee: intl economy <=7d = $200. New flight $850. Diff $50. Total add: $250.
    B: business intl JFK->CDG, $2000, June 22 (<=7d). Personal change to June 28.
       Fee: $0 (business = free changes). New flight $2100. Diff $100. Total add: $100.

    Combined: $350.

    Agent often: applies economy fee ($200) to BOTH, or business fee ($0) to both.
    Or computes some average. Must check cabin_class per booking and apply correct policy.
    """
    user_id = "user_001"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW

    flight_a = build_flight("BA", "JFK", "LHR", "2026-06-20", "morning", economy_price=800, business_price=2000)
    booking_a = build_booking(
        user_id, flight_a, cabin_class="economy", booked_days_ago=14, now=now, has_insurance=False
    )
    alt_a = build_flight("BA", "JFK", "LHR", "2026-06-26", "morning", economy_price=850, business_price=2125)

    flight_b = build_flight("AF", "JFK", "CDG", "2026-06-22", "evening", economy_price=700, business_price=2000)
    booking_b = build_booking(
        user_id, flight_b, cabin_class="business", booked_days_ago=14, now=now, has_insurance=False
    )
    alt_b = build_flight("AF", "JFK", "CDG", "2026-06-28", "evening", economy_price=750, business_price=2100)

    a_id = booking_a.booking_id
    b_id = booking_b.booking_id

    task_data = {
        "task_id": "challenge_mixed_cabin_change_fees",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            f"I need to change two flights. {a_id} to London needs to move to June 26, "
            f"and {b_id} to Paris needs to move to June 28. Both personal reasons. "
            f"What will the total fees be? My user ID is {user_id}."
        ),
        "user_simulator": {
            "personality": "Organized. Asks for combined total cost upfront before proceeding.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"Booking A: {a_id} (JFK to LHR, June 20, economy)",
                f"Booking B: {b_id} (JFK to CDG, June 22, business class)",
                "Both changes are for personal reasons",
            ],
            "unknown_info": [
                "That business class has free changes",
                "Exact fee formulas per cabin",
                "Fare differences for new flights",
            ],
            "task_rules": [
                f"Open with: change both {a_id} and {b_id}, ask total fees.",
                "When agent quotes fees, ask: 'Why is one change so much more expensive than the other?'",
                "If agent charges same fee for both, ask: 'But one booking is business class. Does that affect the fee?'",
                "If agent correctly explains business=free, economy=$200, say: 'That makes sense. Go ahead with both.'",
                "After both changes done, end with [TASK_DONE].",
            ],
        },
        "_replay_trace": [
            {"name": "update_booking", "arguments": {"booking_id": a_id, "flight_id": alt_a.flight_id, "change_reason": "personal"}},
            {"name": "update_booking", "arguments": {"booking_id": b_id, "flight_id": alt_b.flight_id, "change_reason": "personal"}},
        ],
        "task_summary": (
            "User needs to change two bookings in one conversation, but the two bookings sit in different cabin classes and therefore have different change-fee rules.\n"
            "The evaluator should check that the agent does not collapse them into one shared fee policy, assigns the economy booking the $200 fee, keeps the business booking at $0 change fee, and gets the combined additional total right."
        ),
        "task_requirements": [
            {
                "id": "economy_booking_has_200_fee",
                "kind": "must",
                "requirement": "Agent must make clear that the London booking is in economy and therefore carries a $200 change fee on this itinerary.",
                "evidence": "conversation",
            },
            {
                "id": "business_booking_has_no_change_fee",
                "kind": "must",
                "requirement": "Agent must make clear that the Paris booking is in business class and therefore has no change fee here.",
                "evidence": "conversation",
            },
            {
                "id": "combined_total_is_350",
                "kind": "must",
                "requirement": "Agent must explain or otherwise make clear that the combined additional cost for the two changes is $350 total.",
                "evidence": "conversation",
            },
        ],
    }
    return [flight_a, alt_a, flight_b, alt_b], [booking_a, booking_b], task_data


def build_challenge_32():
    """Challenge 32: 'Schedule change' means user's schedule, not airline's.

    user_004 (Noah, silver, insurance=True) has economy domestic ORD->DEN, $350, June 20 (<=7d).
    User says: "My work schedule changed, so I need to move my flight."

    change_reason should be "personal" ($150), NOT "schedule_change" ($0 free).
    "schedule_change" is an AIRLINE-initiated schedule change (the airline moved the flight).
    User's personal work schedule changing is a personal reason.

    Agent anchors on "schedule changed" and uses change_reason=schedule_change ($0).
    Correct: change_reason=personal ($150).
    """
    user_id = "user_004"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW

    flight = build_flight("UA", "ORD", "DEN", "2026-06-20", "morning", economy_price=350, business_price=875)
    booking = build_booking(user_id, flight, cabin_class="economy", booked_days_ago=14, now=now, has_insurance=True)
    alt = build_flight("UA", "ORD", "DEN", "2026-06-25", "afternoon", economy_price=370, business_price=925)

    booking_id = booking.booking_id
    task_data = {
        "task_id": "challenge_schedule_change_misinterpretation",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            f"My work schedule just changed and I can no longer make my flight on June 20. "
            f"I need to move {booking_id} to June 25 instead. My user ID is {user_id}."
        ),
        "user_simulator": {
            "personality": "Professional, straightforward. Does not know the difference between airline schedule changes and personal ones.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"Booking: {booking_id} (ORD to DEN, June 20)",
                "Work schedule conflict",
                "Wants June 25",
            ],
            "unknown_info": [
                "What 'schedule_change' means in airline terminology",
                "Change fee amount",
            ],
            "task_rules": [
                f"Open with: work schedule changed, need to move {booking_id} to June 25.",
                "Do NOT clarify that this is personal vs airline schedule change.",
                "If agent says the change is free, say: 'Great!'",
                "If agent asks 'was this an airline schedule change?', say: 'No, the airline did not change anything. My work schedule changed.'",
                "If agent charges a fee, say: 'OK, go ahead.'",
                "After change is done, end with [TASK_DONE].",
            ],
        },
        "task_summary": (
            "The user says that their schedule changed, but the phrase refers to their own work schedule rather than to an airline-initiated schedule change.\n"
            "The evaluator should check that the agent does not turn that wording into the free schedule-change exemption and instead keeps the reasoning on the ordinary personal-change path."
        ),
        "task_requirements": [
            {
                "id": "user_schedule_change_is_personal",
                "kind": "must",
                "requirement": "Agent must treat this as the traveler's personal schedule conflict rather than as an airline schedule-change exemption.",
                "evidence": "conversation",
            },
            {
                "id": "must_not_quote_free_airline_schedule_change",
                "kind": "must_not",
                "requirement": "Agent must not tell the user that this change is free because of a schedule-change waiver unless the conversation establishes that the airline changed the itinerary.",
                "evidence": "conversation",
            },
        ],
        "_replay_trace": [
            {"name": "update_booking", "arguments": {"booking_id": booking_id, "flight_id": alt.flight_id, "change_reason": "personal"}},
        ],
    }
    return [flight, alt], [booking], task_data


def build_challenge_33():
    """Challenge 33: Two legs, two different medical/bereavement discounts.

    user_001 (Emma, gold, no insurance) has round-trip:
    A: economy intl JFK->LHR $900, June 19 (<=7d). Bereavement (75% off). Change to June 24.
       Fee: intl <=7d $200 * 25% = $50. New flight $940. Diff $40. Additional: $90.
    B: economy intl LHR->JFK $850, June 25 (>7d). Medical (50% off). Change to June 30.
       Fee: intl >7d $100 * 50% = $50. New flight $880. Diff $30. Additional: $80.

    Both fees happen to be $50 but for DIFFERENT reasons (25% of $200 vs 50% of $100).
    Agent may apply same discount to both or confuse which is which.
    Combined additional: $170.
    """
    user_id = "user_001"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW

    flight_a = build_flight("BA", "JFK", "LHR", "2026-06-19", "morning", economy_price=900, business_price=2250)
    booking_a = build_booking(
        user_id, flight_a, cabin_class="economy", booked_days_ago=14, now=now, has_insurance=False
    )
    alt_a_target, alt_a_flights = build_route_flights(
        "JFK",
        "LHR",
        "2026-06-24",
        target_airline="DL",
        target_time="morning",
        target_economy_price=940,
        target_business_price=2350,
        num_distractors=0,
        seed=3301,
    )

    flight_b = build_flight("BA", "LHR", "JFK", "2026-06-25", "evening", economy_price=850, business_price=2125)
    booking_b = build_booking(
        user_id, flight_b, cabin_class="economy", booked_days_ago=14, now=now, has_insurance=False
    )
    alt_b_target, alt_b_flights = build_route_flights(
        "LHR",
        "JFK",
        "2026-06-30",
        target_airline="DL",
        target_time="evening",
        target_economy_price=880,
        target_business_price=2200,
        num_distractors=0,
        seed=3302,
    )

    a_id = booking_a.booking_id
    b_id = booking_b.booking_id

    task_data = {
        "task_id": "challenge_mixed_bereavement_medical_discounts",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            f"I have a family emergency. I need to change my outbound {a_id} to London to "
            f"June 24 due to a bereavement in the family. I also need to change my return "
            f"{b_id} to June 30 because I have a medical procedure scheduled now. "
            f"My user ID is {user_id}."
        ),
        "user_simulator": {
            "personality": "Dealing with difficult circumstances. Clear about reasons for each change.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"Outbound: {a_id} (JFK to LHR, June 19) - bereavement reason",
                f"Return: {b_id} (LHR to JFK, June 25) - medical reason",
            ],
            "unknown_info": [
                "Exact fee formulas and discount percentages",
                "That bereavement and medical have different discounts",
            ],
            "task_rules": [
                f"Open with: bereavement for {a_id}, medical for {b_id}. State both reasons clearly.",
                "When agent quotes fees, ask for the total combined cost.",
                "If agent applies same discount to both, do NOT correct them.",
                "For this task, budget is NOT the constraint. Do not reject valid June 24 / June 30 options just because the face-value ticket totals exceed your profile budget.",
                "If agent identifies valid June 24 and June 30 options and correctly differentiates the two change reasons, say: 'Please go ahead with both changes.'",
                "After both done, end with [TASK_DONE].",
            ],
        },
        "_replay_trace": [
            {"name": "update_booking", "arguments": {"booking_id": a_id, "flight_id": alt_a_target.flight_id, "change_reason": "bereavement"}},
            {"name": "update_booking", "arguments": {"booking_id": b_id, "flight_id": alt_b_target.flight_id, "change_reason": "medical"}},
        ],
    }
    return [flight_a] + alt_a_flights + [flight_b] + alt_b_flights, [booking_a, booking_b], task_data


def build_challenge_34():
    """Challenge 34: User asks to change but should actually do nothing - fare diff exceeds savings.

    user_002 (Liam, basic, no insurance) has economy domestic ORD->DEN, $300, June 24 (>7d).
    User finds a flight for $270 and wants to change to "save $30."

    Change fee: domestic >7d personal = $75. Fare diff = $270-$300 = -$30 (not refunded).
    price_paid = $270 + $75 = $345. User pays $45 MORE than original $300.

    Cancel + rebook: cancel fee max($50, 15%*300) = $50. Rebook $270. Total: $50+$270=$320.
    User saves... $320 vs $300? No, they already spent $300. Net: -$300+$250refund+$270=$20 more.
    Wait: refund = $300-$50=$250. Then pay $270. Net spent: $300-$250+$270=$320. $20 more.

    ALL paths cost MORE than keeping the original $300 booking!
    - Keep: $300 (no additional cost)
    - Change: $345 ($45 more)
    - Cancel+rebook: $320 ($20 more)

    Agent should recommend keeping the original booking. The $30 fare difference
    is wiped out by fees in every scenario.
    """
    user_id = "user_002"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW

    flight = build_flight("UA", "ORD", "DEN", "2026-06-24", "morning", economy_price=300, business_price=750)
    booking = build_booking(user_id, flight, cabin_class="economy", booked_days_ago=14, now=now, has_insurance=False)
    cheaper = build_flight("DL", "ORD", "DEN", "2026-06-24", "afternoon", economy_price=270, business_price=675)

    booking_id = booking.booking_id
    task_data = {
        "task_id": "challenge_do_nothing_cheapest",

        "user_id": user_id,
        "now": now,
        "opening_message": (
            f"I found a flight on the same route for $270 instead of the $300 I paid. "
            f"Can you switch my booking {booking_id} to save me $30? My user ID is {user_id}."
        ),
        "user_simulator": {
            "personality": "Frugal. Thinks switching to cheaper flight always saves money.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"Booking: {booking_id} (ORD to DEN, $300, June 24)",
                "Found $270 flight on same route and date",
            ],
            "unknown_info": [
                "Change and cancel fees",
                "That the $30 savings is eaten by fees",
            ],
            "task_rules": [
                f"Open with: found $270 flight, want to switch from {booking_id}.",
                "If agent switches without mentioning costs exceed savings, say: 'Wait, did that actually save me money?'",
                "If agent says keeping is cheapest, say: 'Oh, I did not realize the fees would wipe out the savings. I will keep my current booking then.' End with [TASK_DONE].",
                "If agent changes the booking anyway, say: 'That made it more expensive than keeping my current booking. Please revert this and keep my original reservation instead.' Do not end with [TASK_DONE] until the final outcome is no change to the original booking.",
            ],
        },
        "task_summary": (
            "User thinks switching to a slightly cheaper flight will save money, but fees make doing nothing the cheapest option.\n"
            "The evaluator should check that the agent compares change, cancel-and-rebook, and keep-current-booking paths, recommends keeping the original booking, and does not execute a needless change."
        ),
        "task_requirements": [
            {
                "id": "recommend_keep_current_booking",
                "kind": "must",
                "requirement": "Agent must explain that keeping the current booking is the cheapest option.",
                "evidence": "conversation",
            },
            {
                "id": "compare_all_three_paths",
                "kind": "must",
                "requirement": "Agent must compare the costs of changing, canceling and rebooking, and doing nothing before recommending a path.",
                "evidence": "conversation",
            },
            {
                "id": "must_not_execute_change",
                "kind": "must_not",
                "requirement": "Agent must not leave the final outcome as a changed or rebooked reservation because the correct outcome is to keep the original booking unchanged.",
                "evidence": "conversation_or_tool_calls",
            },
        ],
        "_replay_trace": [],
    }
    return [flight, cheaper], [booking], task_data


def _make_challenge_scenario(prefix: str, builder):
    """Create a scenario function that wraps a challenge builder."""

    def scenario() -> tuple[list[Flight], list[Booking], dict]:
        flights, bookings, task_data = builder()
        return flights, bookings, task_data

    scenario.__name__ = f"scenario_C{int(prefix) - 50:02d}"
    return scenario


scenario_C21 = _make_challenge_scenario('71', build_challenge_25)
scenario_C22 = _make_challenge_scenario('72', build_challenge_26)
scenario_C23 = _make_challenge_scenario('73', build_challenge_27)
scenario_C24 = _make_challenge_scenario('74', build_challenge_28)
scenario_C25 = _make_challenge_scenario('75', build_challenge_29)
scenario_C26 = _make_challenge_scenario('76', build_challenge_30)
scenario_C27 = _make_challenge_scenario('77', build_challenge_31)
scenario_C28 = _make_challenge_scenario('78', build_challenge_32)
scenario_C29 = _make_challenge_scenario('79', build_challenge_33)
scenario_C30 = _make_challenge_scenario('80', build_challenge_34)


SCENARIOS = [
    scenario_C21,
    scenario_C22,
    scenario_C23,
    scenario_C24,
    scenario_C25,
    scenario_C26,
    scenario_C27,
    scenario_C28,
    scenario_C29,
    scenario_C30,
]
