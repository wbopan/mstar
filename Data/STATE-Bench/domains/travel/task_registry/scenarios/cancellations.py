"""Travel scenarios focused on booking cancellations and refund rules."""


from __future__ import annotations


from datetime import datetime, timedelta

from domains.travel.schemas import Booking, Flight

from domains.travel.task_registry._builders import (
    _USERS_BY_ID,
    DEFAULT_NOW,
    build_booking,
    build_car_rental,
    build_flight,
    build_hotel,
)


def scenario_P01() -> tuple[list[Flight], list[Booking], dict]:
    """P01: cancel_economy_domestic — Economy domestic cancel with connecting flight conflict.

    User wants to cancel ORD→ATL leg, but also has a same-day connecting ATL→SFO.
    Cancelling leg 1 orphans leg 2. Agent must discover the connection and warn.
    """
    now = DEFAULT_NOW
    user_id = "user_002"
    assert user_id in _USERS_BY_ID, f"Unknown user: {user_id}"

    # Leg 1: ORD → ATL (afternoon)
    flight1 = build_flight(
        airline_code="UA",
        origin="ORD",
        destination="ATL",
        date="2026-06-20",
        time_range="afternoon",
        economy_price=350,
        business_price=875,
    )
    booking1 = build_booking(
        user_id=user_id,
        flight=flight1,
        cabin_class="economy",
        booked_days_ago=3,
        now=now,
        has_insurance=False,
    )

    # Leg 2: ATL → SFO (evening, same day — connecting flight)
    flight2 = build_flight(
        airline_code="UA",
        origin="ATL",
        destination="SFO",
        date="2026-06-20",
        time_range="evening",
        economy_price=180,
        business_price=450,
    )
    booking2 = build_booking(
        user_id=user_id,
        flight=flight2,
        cabin_class="economy",
        booked_days_ago=3,
        now=now,
        has_insurance=False,
    )

    booking1_id = booking1.booking_id
    booking2_id = booking2.booking_id
    # Fee for leg 1: max($50, 15% of $350) = max($50, $52) = $52.
    # Fee for leg 2: max($50, 15% of $180) = max($50, $27) = $50.

    task_data = {
        "task_id": "cancel_economy_domestic",

        "user_id": user_id,
        "now": now,
        "opening_message": "Hi, I need to cancel my upcoming flight to Atlanta.",
        "user_simulator": {
            "personality": "Cooperative and straightforward. Provides information when asked.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"Booking ID for ORD→ATL: {booking1_id}",
                f"Booking ID for ATL→SFO: {booking2_id}",
                "Flight 1 is economy class, domestic (ORD to ATL), $350",
                "Flight 2 is economy class, domestic (ATL to SFO), $180 — a connecting flight same day",
            ],
            "unknown_info": [
                "Exact cancellation fee amounts for each leg",
                "Refund processing time",
            ],
            "task_rules": [
                "When the agent asks for your booking ID, provide only the ORD→ATL booking ID.",
                "Do NOT mention the connecting flight to SFO AT ALL, even if the agent doesn't bring it up.",
                "If the agent warns about the connecting flight, confirm you want to cancel both.",
                "If the agent does NOT mention the connecting flight and proceeds to cancel only the first, "
                "simply confirm — do NOT reveal the connecting flight yourself.",
                "When all discussed cancellations are confirmed with fees and refunds, end with [TASK_DONE].",
            ],
        },
        "_replay_trace": [
            {"name": "cancel_booking", "arguments": {"booking_id": booking1_id, "confirm": True}},
            {"name": "cancel_booking", "arguments": {"booking_id": booking2_id, "confirm": True}},
        ],
        "task_summary": (
            "User asks to cancel the first leg of a same-day connecting trip without mentioning the onward segment.\n"
            "The evaluator should check that the agent proactively discovers the hidden connection, warns that cancelling the first leg would strand the second, and only then proceeds with the full cancellation."
        ),
        "task_requirements": [
            {
                "id": "state_hidden_connection_discovered",
                "kind": "must",
                "requirement": f"Agent must proactively discover and mention that {booking2_id} is a same-day onward connection tied to {booking1_id}.",
                "evidence": "conversation",
            },
            {
                "id": "state_orphan_warning",
                "kind": "must",
                "requirement": "Agent must warn that cancelling the first leg alone would leave the user stranded or orphan the remaining connection.",
                "evidence": "conversation",
            },
            {
                "id": "state_not_single_leg_only",
                "kind": "must_not",
                "requirement": "Agent must not treat the request as a simple single-flight cancellation without surfacing the connected onward leg.",
                "evidence": "conversation",
            },
        ],
    }
    return [flight1, flight2], [booking1, booking2], task_data


def scenario_P02() -> tuple[list[Flight], list[Booking], dict]:
    """P02: cancel_business_international — Business intl cancel with return flight + hotel.

    User wants to cancel outbound JFK→LHR. But also has a return LHR→JFK booking
    and a hotel in London. Agent must discover the return flight and hotel, warn
    about the implications, and handle all three cancellations.
    """
    now = DEFAULT_NOW
    user_id = "user_001"
    assert user_id in _USERS_BY_ID, f"Unknown user: {user_id}"

    # Outbound: JFK → LHR, business
    flight_out = build_flight(
        airline_code="DL",
        origin="JFK",
        destination="LHR",
        date="2026-06-22",
        time_range="morning",
        economy_price=450,
        business_price=900,
    )
    booking_out = build_booking(
        user_id=user_id,
        flight=flight_out,
        cabin_class="business",
        booked_days_ago=5,
        now=now,
        has_insurance=False,
    )

    # Return: LHR → JFK, ECONOMY (different fee formula!), same user
    flight_ret = build_flight(
        airline_code="DL",
        origin="LHR",
        destination="JFK",
        date="2026-06-29",
        time_range="evening",
        economy_price=480,
        business_price=950,
    )
    booking_ret = build_booking(
        user_id=user_id,
        flight=flight_ret,
        cabin_class="economy",
        booked_days_ago=5,
        now=now,
        has_insurance=False,
    )

    # Hotel in London
    hotel = build_hotel(
        user_id, "LHR", "2026-06-22", "2026-06-29", room_type="standard", nightly_rate=220, booked_days_ago=5, now=now
    )

    out_id = booking_out.booking_id
    ret_id = booking_ret.booking_id
    # Fee outbound = 8% of $900 = $72 (business intl).
    # Fee return = max($75, 20% of $480) = max($75, $96) = $96 (economy intl).
    # Hotel: 48h+ before check-in → free

    task_data = {
        "task_id": "cancel_business_international",

        "user_id": user_id,
        "now": now,
        "opening_message": "Hello, I'd like to cancel my business class flight to London.",
        "user_simulator": {
            "personality": "Cooperative and polite. Shares details promptly when requested.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"Outbound booking ID: {out_id}",
                f"Return booking ID: {ret_id}",
                "Outbound is business class, JFK to LHR, $900",
                "Return is economy class, LHR to JFK, $480",
                f"Hotel reservation: {hotel.reservation_id}",
                "Hotel in London, June 22-29, $220/night",
            ],
            "unknown_info": [
                "Exact cancellation fee percentage for business international",
                "Refund timeline",
                "Hotel cancellation fee",
            ],
            "task_rules": [
                "When the agent asks for your booking ID, provide only the outbound booking ID.",
                "Do NOT mention the return flight or hotel upfront.",
                "When the agent explains the outbound cancellation fee, acknowledge and confirm.",
                "If the agent asks about other reservations, mention the return flight and hotel.",
                "If the agent does NOT ask about other reservations after cancelling the outbound, "
                f"say 'Oh wait, I also have a return flight — booking {ret_id}. I should cancel that too since the trip is off. "
                "And I think I have a hotel as well.' Do NOT mention the hotel reservation ID unless the agent finds it.",
                "When all cancellations are confirmed with fees, end with [TASK_DONE].",
            ],
        },
        "_replay_trace": [
            {"name": "cancel_booking", "arguments": {"booking_id": out_id, "confirm": True}},
            {"name": "cancel_booking", "arguments": {"booking_id": ret_id, "confirm": True}},
            {"name": "cancel_hotel_reservation", "arguments": {"reservation_id": hotel.reservation_id, "confirm": True}},
        ],
        "task_summary": (
            "User initially asks to cancel only the outbound London business flight, but the trip also includes a return flight and hotel.\n"
            "The evaluator should check that the agent proactively uncovers the linked reservations and keeps the outbound business and return economy fee logic distinct instead of collapsing them into one cancellation path."
        ),
        "task_requirements": [
            {
                "id": "state_linked_trip_discovery",
                "kind": "must",
                "requirement": f"Agent must proactively surface that the user also has return booking {ret_id} and a London hotel tied to the same trip.",
                "evidence": "conversation",
            },
            {
                "id": "state_different_fee_logic",
                "kind": "must",
                "requirement": "Agent must explain that the outbound business cancellation and return economy cancellation use different fee logic rather than one shared formula.",
                "evidence": "conversation",
            },
            {
                "id": "state_not_outbound_only",
                "kind": "must_not",
                "requirement": "Agent must not act as if cancelling the outbound alone fully resolves the London trip once the linked return and hotel are discoverable.",
                "evidence": "conversation",
            },
        ],
        "_hotels": [hotel],
    }
    return [flight_out, flight_ret], [booking_out, booking_ret], task_data


def scenario_P03() -> tuple[list[Flight], list[Booking], dict]:
    """P03: cancel_economy_international — Economy intl cancel + hotel discovery.

    User wants to cancel JFK→CDG flight. Also has a hotel in Paris. Agent should
    discover the hotel and ask about cancelling it too.
    """
    now = DEFAULT_NOW
    user_id = "user_005"
    assert user_id in _USERS_BY_ID, f"Unknown user: {user_id}"

    flight = build_flight(
        airline_code="B6",
        origin="JFK",
        destination="CDG",
        date="2026-06-25",
        time_range="afternoon",
        economy_price=450,
        business_price=1100,
    )
    booking = build_booking(
        user_id=user_id,
        flight=flight,
        cabin_class="economy",
        booked_days_ago=4,
        now=now,
        has_insurance=False,
    )
    booking_id = booking.booking_id
    # Fee = max($75, 20% of $450) = max($75, $90) = $90.

    # Hotel in Paris for the same trip
    hotel = build_hotel(
        user_id, "CDG", "2026-06-25", "2026-06-30", room_type="standard", nightly_rate=160, booked_days_ago=4, now=now
    )
    # Hotel: 48h+ before check-in → free cancel

    task_data = {
        "task_id": "cancel_economy_international",

        "user_id": user_id,
        "now": now,
        "opening_message": "I need to cancel my flight to Paris. Can you help me with that?",
        "user_simulator": {
            "personality": "Cooperative and direct. Answers questions clearly.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"Flight booking ID: {booking_id}",
                "Flight is economy class, international (JFK to CDG)",
                "Price paid: $450",
                f"Hotel reservation: {hotel.reservation_id}",
                "Hotel in Paris, June 25-30, $160/night",
            ],
            "unknown_info": [
                "International economy cancellation fee formula",
                "Hotel cancellation fee",
            ],
            "task_rules": [
                "When the agent asks for your booking ID, provide only the flight booking ID.",
                "Do NOT proactively mention the hotel. Only bring it up if the agent asks about other reservations.",
                "When the agent quotes the cancellation fee, acknowledge it and confirm cancellation.",
                "If the agent asks about other reservations, mention the hotel.",
                "If the agent does NOT ask about other reservations after cancelling the flight, "
                "simply end with [TASK_DONE]. The agent should have checked proactively.",
                "When all brought-up cancellations are done, end with [TASK_DONE].",
            ],
        },
        "_replay_trace": [
            {"name": "cancel_booking", "arguments": {"booking_id": booking_id, "confirm": True}},
            {"name": "cancel_hotel_reservation", "arguments": {"reservation_id": hotel.reservation_id, "confirm": True}},
        ],
        "task_summary": (
            "User asks to cancel an international Paris flight but does not mention the Paris hotel reservation.\n"
            "The evaluator should check that the agent proactively looks for the hidden hotel reservation and offers to handle it instead of stopping at the flight cancellation alone."
        ),
        "task_requirements": [
            {
                "id": "state_hotel_discovered",
                "kind": "must",
                "requirement": f"Agent must proactively discover and mention hotel reservation {hotel.reservation_id} after handling the Paris flight cancellation request.",
                "evidence": "conversation",
            },
            {
                "id": "state_offer_hotel_cancellation",
                "kind": "must",
                "requirement": "Agent must offer or ask about cancelling the related hotel instead of ignoring the rest of the trip.",
                "evidence": "conversation",
            },
            {
                "id": "state_not_flight_only",
                "kind": "must_not",
                "requirement": "Agent must not present the Paris trip as fully handled while leaving a discoverable linked hotel unaddressed.",
                "evidence": "conversation",
            },
        ],
        "_hotels": [hotel],
    }
    return [flight], [booking], task_data


def scenario_P04() -> tuple[list[Flight], list[Booking], dict]:
    """P04: cancel_with_insurance — Has insurance, fee waived, but also has a hotel.

    User wants to cancel flight (insurance covers it). But they also have a hotel
    reservation for the same trip. Agent should proactively mention the hotel
    needs separate cancellation. User then cancels both.
    """
    now = DEFAULT_NOW
    user_id = "user_004"
    assert user_id in _USERS_BY_ID, f"Unknown user: {user_id}"

    flight = build_flight(
        airline_code="WN",
        origin="DEN",
        destination="SFO",
        date="2026-06-19",
        time_range="morning",
        economy_price=400,
        business_price=950,
    )
    booking = build_booking(
        user_id=user_id,
        flight=flight,
        cabin_class="economy",
        booked_days_ago=5,
        now=now,
        has_insurance=True,
    )
    booking_id = booking.booking_id
    # Insurance covers cancellation: fee = $0, refund = $400

    # Hotel in SFO for the same trip: 3 nights starting June 19
    hotel = build_hotel(
        user_id, "SFO", "2026-06-19", "2026-06-22", room_type="standard", nightly_rate=180, booked_days_ago=5, now=now
    )
    # Hotel cancel: 48h+ before check-in (June 19), now is June 15 → free cancel

    task_data = {
        "task_id": "cancel_with_insurance",

        "user_id": user_id,
        "now": now,
        "opening_message": "Hi, I'd like to cancel my flight from Denver to San Francisco.",
        "user_simulator": {
            "personality": "Cooperative and patient. Provides booking details when asked.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"Flight booking ID: {booking_id}",
                "Flight is economy class, domestic (DEN to SFO)",
                "Has travel insurance on the booking",
                "Price paid: $400",
                f"Hotel reservation ID: {hotel.reservation_id}",
                "Hotel is in San Francisco, June 19-22, $180/night",
            ],
            "unknown_info": [
                "Whether insurance actually waives the cancellation fee",
                "Refund processing details",
                "Hotel cancellation fee",
            ],
            "task_rules": [
                "When the agent asks for your booking ID, provide only the flight booking ID.",
                "Do NOT proactively mention the hotel. Only bring it up if the agent asks about other reservations.",
                "When the agent mentions insurance coverage, acknowledge it.",
                "When the agent says the flight fee is waived, confirm you want to proceed.",
                "If the agent asks about other reservations on this trip, mention the hotel.",
                "If the agent does NOT mention or ask about other reservations after cancelling the flight, "
                "simply end with [TASK_DONE]. The agent should have checked proactively.",
                "When all brought-up cancellations are complete, end with [TASK_DONE].",
            ],
        },
        "_replay_trace": [
            {"name": "cancel_booking", "arguments": {"booking_id": booking_id, "confirm": True}},
            {"name": "cancel_hotel_reservation", "arguments": {"reservation_id": hotel.reservation_id, "confirm": True}},
        ],
        "task_summary": (
            "User asks to cancel an insured domestic flight and has a linked hotel reservation that is not mentioned up front.\n"
            "The evaluator should check that the agent recognizes the insurance waiver on the flight cancellation and still proactively looks for the hidden hotel reservation instead of stopping after the waived-fee flight cancel."
        ),
        "task_requirements": [
            {
                "id": "state_insurance_waiver_explained",
                "kind": "must",
                "requirement": "Agent must explain that the flight cancellation fee is waived because the booking has insurance.",
                "evidence": "conversation",
            },
            {
                "id": "state_related_hotel_discovered",
                "kind": "must",
                "requirement": f"Agent must proactively discover and mention hotel reservation {hotel.reservation_id} for the same trip.",
                "evidence": "conversation",
            },
            {
                "id": "state_not_ignore_hotel",
                "kind": "must_not",
                "requirement": "Agent must not stop after the insured flight cancellation as if no other trip reservation needs attention.",
                "evidence": "conversation",
            },
        ],
        "_hotels": [hotel],
    }
    return [flight], [booking], task_data


def scenario_P05() -> tuple[list[Flight], list[Booking], dict]:
    """P05: cancel_airline_cancelled — Airline cancelled flight, free refund.

    Flight is cancelled by airline. User also has a hotel and car rental for this trip.
    Agent should proactively mention those need attention too.
    """
    now = DEFAULT_NOW
    user_id = "user_003"
    assert user_id in _USERS_BY_ID, f"Unknown user: {user_id}"

    flight = build_flight(
        airline_code="AA",
        origin="DFW",
        destination="MIA",
        date="2026-06-18",
        time_range="evening",
        economy_price=320,
        business_price=800,
        status="cancelled",
    )
    booking = build_booking(
        user_id=user_id,
        flight=flight,
        cabin_class="business",
        booked_days_ago=7,
        now=now,
        has_insurance=True,
    )
    booking_id = booking.booking_id
    # Airline-initiated cancellation: fee = $0, refund = $800

    # Hotel in Miami for the trip — check-in tomorrow, 28h from now → 24-48h tier
    hotel = build_hotel(
        user_id, "MIA", "2026-06-16", "2026-06-20", room_type="standard", nightly_rate=200, booked_days_ago=7, now=now
    )
    # Hotel cancel: 24-48h before check-in → 50% of first night.

    # Car rental in Miami — luxury = $50 surcharge
    car = build_car_rental(
        user_id, "MIA", "2026-06-18", "2026-06-22", car_class="luxury", daily_rate=85, booked_days_ago=7, now=now
    )
    # Luxury cancel: 24h+ before pickup → $50 surcharge

    task_data = {
        "task_id": "cancel_airline_cancelled",

        "user_id": user_id,
        "now": now,
        "opening_message": "I just saw that my flight to Miami was cancelled. I need a refund.",
        "user_simulator": {
            "personality": "Cooperative but slightly frustrated about the airline cancellation. Provides information readily.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"Flight booking ID: {booking_id}",
                "Flight was cancelled by the airline (DFW to MIA)",
                "Flight is business class, domestic",
                "Price paid: $800",
                f"Hotel reservation ID: {hotel.reservation_id}",
                "Hotel in Miami, June 16-20, $200/night",
                f"Car rental ID: {car.rental_id}",
                "Luxury car in Miami, June 18-22",
            ],
            "unknown_info": [
                "Whether airline-initiated cancellations always get full refunds",
                "Hotel and car cancellation fees",
            ],
            "task_rules": [
                "When the agent asks for your booking ID, provide only the flight booking ID.",
                "Do NOT mention the hotel or car rental AT ALL, even if the agent doesn't bring them up.",
                "When the agent confirms the flight cancellation refund, acknowledge.",
                "If the agent asks about other reservations for this trip, confirm the hotel and car.",
                "If the agent does NOT mention or ask about other reservations, simply end with [TASK_DONE] "
                "after the flight cancellation is confirmed. The agent should have checked proactively.",
                "When all brought-up cancellations are complete, end with [TASK_DONE].",
            ],
        },
        "_replay_trace": [
            {"name": "cancel_booking", "arguments": {"booking_id": booking_id, "confirm": True}},
            {"name": "cancel_hotel_reservation", "arguments": {"reservation_id": hotel.reservation_id, "confirm": True}},
            {"name": "cancel_car_rental", "arguments": {"rental_id": car.rental_id, "confirm": True}},
        ],
        "task_summary": (
            "User asks for a refund after the airline cancels the flight, but there is also a destination hotel and car rental that the user does not volunteer.\n"
            "The evaluator should check that the agent recognizes the airline-caused flight refund path and proactively surfaces both the hotel and car rental rather than treating the flight refund as the whole trip cleanup."
        ),
        "task_requirements": [
            {
                "id": "state_airline_cancel_refund_path",
                "kind": "must",
                "requirement": "Agent must explain that the flight is cancelled by the airline and therefore should be refunded without a cancellation fee.",
                "evidence": "conversation",
            },
            {
                "id": "state_hidden_trip_components_discovered",
                "kind": "must",
                "requirement": f"Agent must proactively discover and mention both hotel reservation {hotel.reservation_id} and car rental {car.rental_id} tied to the Miami trip.",
                "evidence": "conversation",
            },
            {
                "id": "state_not_flight_refund_only",
                "kind": "must_not",
                "requirement": "Agent must not treat the airline refund as the entire trip resolution while leaving discoverable hotel and car reservations unaddressed.",
                "evidence": "conversation",
            },
        ],
        "_hotels": [hotel],
        "_car_rentals": [car],
    }
    return [flight], [booking], task_data


def scenario_P06() -> tuple[list[Flight], list[Booking], dict]:
    """P06: cancel_within_free_window_intl — TWO intl bookings, different window states.

    Booking A: 46h old → within 48h intl free window.
    Booking B: 50h old → outside 48h intl free window (fee applies).
    Agent must compute which qualifies for free cancel.
    """
    now = DEFAULT_NOW
    user_id = "user_001"
    assert user_id in _USERS_BY_ID, f"Unknown user: {user_id}"

    # Flight A: SFO → NRT
    flight_a = build_flight(
        airline_code="DL",
        origin="SFO",
        destination="NRT",
        date="2026-06-28",
        time_range="morning",
        economy_price=550,
        business_price=1400,
    )
    # Booked 46 hours ago — within the 48-hour international free cancellation window
    booked_at_a = (datetime.fromisoformat(now) - timedelta(hours=46)).isoformat()
    booking_a = build_booking(
        user_id=user_id,
        flight=flight_a,
        cabin_class="business",
        booked_days_ago=0,
        now=now,
        has_insurance=False,
    )
    booking_a.booked_at = booked_at_a

    # Flight B: JFK → LHR
    flight_b = build_flight(
        airline_code="DL",
        origin="JFK",
        destination="LHR",
        date="2026-06-30",
        time_range="evening",
        economy_price=480,
        business_price=1200,
    )
    # Booked 50 hours ago — outside the 48-hour window
    booked_at_b = (datetime.fromisoformat(now) - timedelta(hours=50)).isoformat()
    booking_b = build_booking(
        user_id=user_id,
        flight=flight_b,
        cabin_class="economy",
        booked_days_ago=0,
        now=now,
        has_insurance=False,
    )
    booking_b.booked_at = booked_at_b

    booking_a_id = booking_a.booking_id
    booking_b_id = booking_b.booking_id
    # Booking A: within window → $0 fee, refund $1400
    # Booking B: outside window, ECONOMY intl → max($75, 20% of $480) = max($75, $96) = $96

    task_data = {
        "task_id": "cancel_within_free_window_intl",

        "user_id": user_id,
        "now": now,
        "opening_message": "I need to cancel both my upcoming international flights. Can you help?",
        "user_simulator": {
            "personality": "Cooperative and slightly anxious about whether the free cancellation window still applies.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"Booking A (SFO→NRT): {booking_a_id}, business class, booked about 46 hours ago, $1400",
                f"Booking B (JFK→LHR): {booking_b_id}, economy class, booked about 50 hours ago, $480",
                "Different cabin classes on each booking",
            ],
            "unknown_info": [
                "Exact duration of the free cancellation window for international flights",
                "Which booking is still within the free window",
                "Fee amount for the one outside the window",
            ],
            "task_rules": [
                "When the agent asks for booking IDs, provide both.",
                "Claim that you booked BOTH flights 'yesterday morning' (imply both are within the free window).",
                "When the agent says one is outside the window, express surprise and ask how they calculated that.",
                "If the agent explains the exact booking timestamps, accept the correction.",
                "If the agent tries to cancel both for free without checking timestamps, push back: "
                "'Are you sure? I want to make sure I'm not being overcharged.'",
                "When the agent provides correct fees for both bookings, confirm and proceed.",
                "When both cancellations are complete with correct fees, end with [TASK_DONE].",
            ],
        },
        "_replay_trace": [
            {"name": "cancel_booking", "arguments": {"booking_id": booking_a_id, "confirm": True}},
            {"name": "cancel_booking", "arguments": {"booking_id": booking_b_id, "confirm": True}},
        ],
        "task_summary": (
            "User asks to cancel two international bookings that were made only a few hours apart, one just inside and one just outside the free-cancellation window.\n"
            "The evaluator should check that the agent distinguishes the two booking timestamps correctly, explains why only one qualifies for free cancellation, and does not collapse both bookings into the same window logic."
        ),
        "task_requirements": [
            {
                "id": "state_one_free_one_paid",
                "kind": "must",
                "requirement": f"Agent must explain that {booking_a_id} qualifies for free cancellation while {booking_b_id} does not.",
                "evidence": "conversation",
            },
            {
                "id": "state_timestamp_window_reasoning",
                "kind": "must",
                "requirement": "Agent must explain the distinction using the actual booking timing or 48-hour window logic rather than treating both bookings as if they were booked at the same time.",
                "evidence": "conversation",
            },
            {
                "id": "state_not_both_free",
                "kind": "must_not",
                "requirement": "Agent must not claim that both international bookings qualify for free cancellation under the same 48-hour window.",
                "evidence": "conversation",
            },
        ],
    }
    return [flight_a, flight_b], [booking_a, booking_b], task_data


SCENARIOS = [
    scenario_P01,
    scenario_P02,
    scenario_P03,
    scenario_P04,
    scenario_P05,
    scenario_P06,
]
