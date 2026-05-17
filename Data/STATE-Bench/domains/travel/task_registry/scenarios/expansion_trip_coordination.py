"""Expanded travel scenarios for cross-product trip coordination."""

from __future__ import annotations

from domains.travel.task_registry._builders import (
    _USERS_BY_ID,
    DEFAULT_NOW,
    build_booking,
    build_car_inventory,
    build_car_rental,
    build_flight,
    build_hotel,
    build_hotel_inventory,
)


def scenario_ET01():
    user_id = "user_001"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW

    flight = build_flight("UA", "JFK", "MIA", "2026-06-21", "morning", economy_price=320, business_price=860)
    booking = build_booking(user_id, flight, cabin_class="economy", booked_days_ago=6, now=now, booking_id="BK-ET01", has_insurance=True)
    hotel = build_hotel(user_id, "MIA", "2026-06-21", "2026-06-24", room_type="standard", nightly_rate=180, booked_days_ago=6, now=now)
    car = build_car_rental(user_id, "MIA", "2026-06-21", "2026-06-24", car_class="economy", daily_rate=55, booked_days_ago=6, now=now)
    replacement_car = build_car_inventory("MIA", "2026-06-22", "2026-06-24", car_class="economy", daily_rate=58, car_id="CAR-ET01R")

    task_data = {
        "task_id": "cross_cancel_flight_keep_hotel_replace_late_car",
        "user_id": user_id,
        "now": now,
        "opening_message": f"I may cancel my Miami flight {booking.booking_id} and get there the next morning another way, but I have other trip pieces booked and do not want to break the trip accidentally. Before you change anything, can you compare whether I should keep the rest as-is, cancel the whole trip, or keep only the pieces that still fit if I arrive a day later? I am especially trying not to lose my lodging if it can still work. My user ID is {user_id}.",
        "user_simulator": {
            "personality": "Direct and practical.",
            "user_sim_context": "You may skip the flight and reach Miami the next morning instead, but you already have other trip pieces booked and want the agent to discover them before recommending anything. The tricky part is that the hotel can still work if you arrive a day later, but the current car pickup no longer lines up and should be replaced with a later-start rental. You care strongly about preserving the existing hotel if that is still viable, and you do not want the agent previewing or treating hotel cancellation as the recommended path once that viability is clear. The first phase must stay informational and comparative. After the agent recommends the selective path, you still want a separate price-and-option step for the replacement car before giving final permission to execute anything.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"Flight booking: {booking.booking_id}",
                f"Hotel reservation: {hotel.reservation_id}",
                f"Car rental: {car.rental_id}",
                "If you skip the flight, you expect to reach Miami on June 22 instead of June 21.",
            ],
            "unknown_info": [
                "Whether the agent will discover both linked reservations before recommending what to keep",
                "Whether the agent will notice that the hotel can stay but the current car timing no longer fits",
                "Whether the agent will wait for explicit confirmation before canceling and rebooking anything",
            ],
            "task_rules": [
                "Open by asking only for the compare-first recommendation and do not authorize any cancellation or rebooking yet.",
                "Do not volunteer the hotel or car unless the agent asks what else is booked for the Miami trip or what pieces would be affected by arriving later.",
                "If the agent recommends keeping everything unchanged without surfacing the hotel and car dates, ask how the rest of the trip still fits if you arrive on June 22 instead of June 21.",
                "If the agent notices the hotel can stay but the current car pickup should move later, agree that this is the path you want in principle, but do not authorize any writes yet.",
                "Once the agent has compared the options and explained why the hotel should stay while the car should be replaced, say: 'That sounds like the right approach, but before you change anything I need the replacement-car option and the revised total cost for the trip. Then I will confirm.'",
                "If the agent tries to preview or discuss canceling the hotel after establishing that the hotel can still work for the June 22 arrival, push back once by saying the hotel is the one piece you want to preserve if at all possible.",
                "Only after the agent gives the replacement-car option and revised total should you say: 'That total works for me. Now please do that exact plan: cancel the flight, keep the hotel, and replace the car so it starts June 22 instead.'",
                "If the agent starts canceling the hotel, correct them immediately and say the hotel should stay because you still need the room from June 21 onward.",
                "End with [TASK_DONE] only after the flight is canceled, the original car is canceled, the replacement car is booked, and the agent explicitly confirms the hotel stayed active throughout.",
            ],
        },
        "_replay_trace": [
            {"name": "cancel_booking", "arguments": {"booking_id": booking.booking_id, "confirm": True}},
            {"name": "cancel_car_rental", "arguments": {"rental_id": car.rental_id, "confirm": True}},
            {"name": "book_car_rental", "arguments": {"car_id": replacement_car.car_id, "user_id": user_id}},
        ],
        "task_summary": "Traveler may skip the Miami flight and arrive a day later by another route, but already has other trip components booked and explicitly wants to preserve lodging if it still works. Correct resolution: the agent should proactively discover the hotel and car, compare keep-all versus cancel-all versus selective changes, realize the hotel can stay but the current car timing no longer fits a June 22 arrival, recommend preserving the hotel rather than canceling it, surface the replacement-car option and revised trip total, and only then after separate final approval cancel the insured flight, keep the hotel active, cancel the original car rental, and book the later replacement car.\n\nChallenge: This tests linked-reservation discovery, compare-then-act discipline, preservation-oriented trip integrity, and sequential carryover with a separate cost-confirmation gate.",
        "task_requirements": [
            {"id": "cross_cancel_flight_keep_hotel_replace_late_car_discover", "kind": "must", "requirement": f"Agent must discover and acknowledge hotel reservation {hotel.reservation_id} and car rental {car.rental_id} during the compare-first phase before executing any writes.", "evidence": "conversation"},
            {"id": "cross_cancel_flight_keep_hotel_replace_late_car_compare", "kind": "must", "requirement": "Agent must compare the major trip options before acting, including the selective path that keeps only the reservations that still fit a June 22 arrival.", "evidence": "conversation"},
            {"id": "cross_cancel_flight_keep_hotel_replace_late_car_sequence_reasoning", "kind": "must", "requirement": f"Agent must explain that hotel reservation {hotel.reservation_id} can remain active while car rental {car.rental_id} should be replaced with a later-start rental because the user will arrive a day later.", "evidence": "conversation"},
            {"id": "cross_cancel_flight_keep_hotel_replace_late_car_recommend_preserve_hotel", "kind": "must", "requirement": f"Agent must recommend preserving hotel reservation {hotel.reservation_id} as the preferred lodging path once it establishes that the June 22 arrival still fits the existing stay, rather than treating hotel cancellation as an equally preferred plan.", "evidence": "conversation"},
            {"id": "cross_cancel_flight_keep_hotel_replace_late_car_quote_revised_total", "kind": "must", "requirement": f"Before executing any cancellation or rebooking, agent must surface the replacement car option {replacement_car.car_id} and quote the revised total trip cost for the selective plan that keeps hotel reservation {hotel.reservation_id} active.", "evidence": "conversation"},
            {"id": "cross_cancel_flight_keep_hotel_replace_late_car_preserve_hotel", "kind": "must", "requirement": f"Agent must make clear that hotel reservation {hotel.reservation_id} remains active after the flight cancellation and car replacement.", "evidence": "conversation"},
            {"id": "cross_cancel_flight_keep_hotel_replace_late_car_no_premature_write", "kind": "must_not", "requirement": "Agent must not cancel or rebook anything before the user explicitly approves execution after seeing the replacement-car option and revised total cost for the selective plan.", "evidence": "conversation"},
            {"id": "cross_cancel_flight_keep_hotel_replace_late_car_no_hotel_preview", "kind": "must_not", "requirement": f"Once the agent has established that hotel reservation {hotel.reservation_id} still works for the June 22 arrival, it must not preview, recommend, or imply hotel cancellation as part of the preferred path.", "evidence": "conversation"},
            {"id": "cross_cancel_flight_keep_hotel_replace_late_car_no_hotel_cancel", "kind": "must_not", "requirement": f"Agent must not cancel or imply cancellation of hotel reservation {hotel.reservation_id}.", "evidence": "conversation"},
        ],
        "_hotels": [hotel],
        "_car_rentals": [car],
        "_car_inventory": [replacement_car],
    }
    return [flight], [booking], task_data


def scenario_ET02():
    user_id = "user_002"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW

    flight = build_flight("AA", "ORD", "LAX", "2026-06-19", "afternoon", economy_price=360, business_price=940)
    booking = build_booking(user_id, flight, cabin_class="economy", booked_days_ago=8, now=now, booking_id="BK-ET02", has_insurance=False)
    hotel = build_hotel(user_id, "LAX", "2026-06-19", "2026-06-22", room_type="standard", nightly_rate=170, booked_days_ago=8, now=now)
    car = build_car_rental(user_id, "LAX", "2026-06-19", "2026-06-22", car_class="suv", daily_rate=95, booked_days_ago=8, now=now)

    task_data = {
        "task_id": "cross_cancel_hotel_only_keep_flight_and_car",
        "user_id": user_id,
        "now": now,
        "opening_message": f"I think I need to cancel my LA hotel reservation {hotel.reservation_id}, but before you change anything I want to make sure the rest of the trip still makes sense if I stay somewhere else. My user ID is {user_id}.",
        "user_simulator": {
            "personality": "Matter-of-fact.",
            "user_sim_context": "You expect to stay with a friend instead of using the LA hotel, but you do not want the agent to assume that also means the car should be dropped. The key hidden trip fact is that your friend lives well away from LAX, so the flight and car should stay active even though the hotel is no longer needed. The first phase must stay informational and comparative. After the agent recommends canceling only the hotel, you still want a separate preview-only step for the hotel cancellation terms and then a final explicit go-ahead before any write happens.",
            "known_info": [
                f"Your user ID: {user_id}",
                f"Flight booking: {booking.booking_id}",
                f"Hotel reservation: {hotel.reservation_id}",
                f"Car rental: {car.rental_id}",
                "You may stay with a friend instead of using the hotel.",
            ],
            "unknown_info": [
                "Whether canceling the hotel should also affect the car rental",
                "Whether the agent will discover why the flight and car still matter before changing anything",
            ],
            "task_rules": [
                "Open by asking for the compare-first recommendation and do not authorize any cancellation yet.",
                "Do not volunteer the friend or location details unless the agent asks where you would stay instead or whether canceling the hotel changes the need for the car.",
                "If the agent asks, say you would stay with a friend in Pasadena and still need to get between there and LAX, so you expect the car may still matter.",
                "If the agent jumps straight to canceling the hotel without first checking the linked flight and car, stop them and say you asked to think through the rest of the trip first.",
                "If the agent recommends canceling the hotel but keeping the flight and car because the flight is unchanged and your friend stay still requires local transportation, say that this is the plan you want in principle but that you do not authorize any cancellation yet.",
                "Then say: 'Before you cancel anything, preview only the hotel cancellation terms and confirm again that the flight and car stay untouched. After that I will decide.'",
                "After the preview, ask one more confirmation question about whether canceling the hotel has any knock-on effect on the flight or car, and do not authorize cancellation until the agent answers it.",
                "Only then say: 'Yes, now cancel just the hotel. Keep the flight and car exactly as they are.'",
                "If the agent suggests canceling the car too without surfacing the Pasadena logistics, push back once and ask why the car would no longer be needed.",
                "End with [TASK_DONE] only after the hotel is canceled and the agent explicitly confirms the flight and car stayed active and unchanged.",
            ],
        },
        "_replay_trace": [
            {"name": "cancel_hotel_reservation", "arguments": {"reservation_id": hotel.reservation_id, "confirm": True}},
        ],
        "task_summary": "Traveler expects to stay with a friend instead of using the LA hotel, but wants to think through the rest of the trip before changing anything. Correct resolution: the agent should proactively surface the linked flight and car, compare cancel-hotel-only versus cancel-hotel-and-car implications, discover that the friend stay is in Pasadena so the unchanged flight and car still make sense, recommend canceling only the hotel, then stop at a preview-only hotel-cancellation step and wait for a separate final approval before actually canceling the hotel.\n\nChallenge: This tests linked-reservation discovery, compare-then-act discipline, and a three-stage recommendation-preview-execute confirmation flow rather than a simple hotel-only cancellation.",
        "task_requirements": [
            {"id": "cross_cancel_hotel_only_keep_flight_and_car_discover", "kind": "must", "requirement": f"Agent must acknowledge linked flight {booking.booking_id} and car rental {car.rental_id} before executing the hotel cancellation.", "evidence": "conversation"},
            {"id": "cross_cancel_hotel_only_keep_flight_and_car_compare", "kind": "must", "requirement": "Agent must compare canceling only the hotel against canceling the hotel and car before acting, rather than treating the hotel cancellation as automatically sufficient analysis.", "evidence": "conversation"},
            {"id": "cross_cancel_hotel_only_keep_flight_and_car_reasoning", "kind": "must", "requirement": f"Agent must explain why flight {booking.booking_id} and car rental {car.rental_id} should remain active after hotel cancellation, including that the flight is unchanged and the alternate stay still requires local transportation rather than making the car unnecessary.", "evidence": "conversation"},
            {"id": "cross_cancel_hotel_only_keep_flight_and_car_preserve", "kind": "must", "requirement": f"Agent must make clear that flight {booking.booking_id} and car rental {car.rental_id} remain active and unchanged after hotel cancellation.", "evidence": "conversation"},
            {"id": "cross_cancel_hotel_only_keep_flight_and_car_no_premature_write", "kind": "must_not", "requirement": "Agent must not cancel the hotel until after the user explicitly approves cancellation in a separate final step following the compare-first discussion and the hotel-cancellation preview.", "evidence": "conversation"},
            {"id": "cross_cancel_hotel_only_keep_flight_and_car_no_blanket", "kind": "must_not", "requirement": "Agent must not interpret the hotel-focused request as permission or preference to cancel the full trip or to cancel the car without first establishing that the car is no longer needed.", "evidence": "conversation"},
        ],
        "_hotels": [hotel],
        "_car_rentals": [car],
    }
    return [flight], [booking], task_data


def scenario_ET03():
    user_id = "user_003"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW

    outbound = build_flight("DL", "JFK", "MIA", "2026-06-22", "morning", economy_price=280, business_price=780, flight_id="DL-ET03A")
    inbound = build_flight("DL", "MIA", "JFK", "2026-06-25", "evening", economy_price=300, business_price=820, flight_id="DL-ET03B")
    hotel_basic = build_hotel_inventory("MIA", "2026-06-22", "2026-06-25", room_type="standard", nightly_rate=165, hotel_id="HOTEL-ET03A", hotel_name="Bayside Stay")
    hotel_better = build_hotel_inventory("MIA", "2026-06-22", "2026-06-25", room_type="standard", nightly_rate=210, hotel_id="HOTEL-ET03B", hotel_name="Ocean Central")
    car_basic = build_car_inventory("MIA", "2026-06-22", "2026-06-25", car_class="economy", daily_rate=48, car_id="CAR-ET03A")
    car_better = build_car_inventory("MIA", "2026-06-22", "2026-06-25", car_class="midsize", daily_rate=66, car_id="CAR-ET03B")

    task_data = {
        "task_id": "cross_plan_trip_balanced_mid_budget",
        "user_id": user_id,
        "now": now,
        "opening_message": f"I need a Miami trip from June 22 to June 25 with flights, a hotel, and a rental car. My total budget is $1,050 and I do not want the absolute cheapest trip if a slightly better full package still fits. My user ID is {user_id}.",
        "user_simulator": {
            "personality": "Thoughtful and tradeoff-oriented.",
            "user_sim_context": "You want a full Miami package but not in a purely cheapest-wins way. If a somewhat better hotel or car still fits the full budget, you want the agent to compare complete bundles instead of locking onto the lowest-price component in each category automatically.",
            "known_info": [f"Your user ID: {user_id}", "Budget is $1,050 total.", "You need flights, a hotel, and a car rental."],
            "unknown_info": ["Which full bundle is the best value while still fitting budget"],
            "task_rules": [
                "Ask the agent to compare full-trip bundles, not just the cheapest item in each category.",
                "If a slightly better hotel or car still fits the total budget, prefer the best overall bundle within budget rather than the absolute cheapest package.",
                "End with [TASK_DONE] once the chosen flight, hotel, and car are all booked and the total is explained.",
            ],
        },
        "_replay_trace": [
            {"name": "create_booking", "arguments": {"flight_id": outbound.flight_id, "user_id": user_id, "cabin_class": "economy", "seat_type": "aisle", "payment_method": "credit_card", "meal_preference": "standard", "add_wifi": True, "add_extra_legroom": True, "add_insurance": True}},
            {"name": "create_booking", "arguments": {"flight_id": inbound.flight_id, "user_id": user_id, "cabin_class": "economy", "seat_type": "aisle", "payment_method": "credit_card", "meal_preference": "standard", "add_wifi": True, "add_extra_legroom": True, "add_insurance": True}},
            {"name": "book_hotel", "arguments": {"hotel_id": hotel_better.hotel_id, "user_id": user_id}},
            {"name": "book_car_rental", "arguments": {"car_id": car_basic.car_id, "user_id": user_id}},
        ],
        "task_summary": "Traveler wants a full-trip Miami package under a mid-range budget, but prefers the best overall bundle within budget rather than the absolute cheapest component in every category. Correct resolution: the agent should compare whole-package tradeoffs and select the higher-value hotel while keeping the total trip under budget with the cheaper car.\n\nChallenge: This tests bundle-level optimization instead of greedy per-component minimization.",
        "task_requirements": [
            {"id": "cross_plan_trip_balanced_mid_budget_bundle_compare", "kind": "must", "requirement": "Agent must compare at least two complete flight-plus-hotel-plus-car bundles rather than optimizing components in isolation.", "evidence": "conversation"},
            {"id": "cross_plan_trip_balanced_mid_budget_not_absolute_cheapest", "kind": "must", "requirement": f"Agent must make clear why choosing hotel {hotel_better.hotel_id} with car {car_basic.car_id} is the best in-budget bundle rather than simply defaulting to the cheapest hotel and cheapest car.", "evidence": "conversation"},
        ],
        "_hotel_inventory": [hotel_basic, hotel_better],
        "_car_inventory": [car_basic, car_better],
    }
    return [outbound, inbound], [], task_data


def scenario_ET04():
    user_id = "user_004"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW

    outbound = build_flight("UA", "ORD", "DEN", "2026-06-23", "morning", economy_price=240, business_price=760, flight_id="UA-ET04A")
    inbound = build_flight("UA", "DEN", "ORD", "2026-06-26", "evening", economy_price=250, business_price=770, flight_id="UA-ET04B")
    hotel_ok = build_hotel_inventory("DEN", "2026-06-23", "2026-06-26", room_type="standard", nightly_rate=125, hotel_id="HOTEL-ET04A", hotel_name="Union Square Lodge")
    hotel_nicer = build_hotel_inventory("DEN", "2026-06-23", "2026-06-26", room_type="suite", nightly_rate=220, hotel_id="HOTEL-ET04B", hotel_name="Peak View Suites")
    car_econ = build_car_inventory("DEN", "2026-06-23", "2026-06-26", car_class="economy", daily_rate=42, car_id="CAR-ET04A")
    car_suv = build_car_inventory("DEN", "2026-06-23", "2026-06-26", car_class="suv", daily_rate=88, car_id="CAR-ET04B")

    task_data = {
        "task_id": "cross_plan_trip_budget_with_preference_floor",
        "user_id": user_id,
        "now": now,
        "opening_message": f"I need a Denver trip June 23 to June 26 with flights, hotel, and car. My budget is $900, but do not give me a suite or SUV unless you can prove the whole package still fits. My user ID is {user_id}.",
        "user_simulator": {
            "personality": "Budget-conscious and explicit.",
            "user_sim_context": "You want a full Denver package under a strict budget and are explicitly wary of nicer hotel or car options that could quietly blow the total. You need the agent to treat the stated budget as a hard cap and justify any upgrade-like choice against the full package total.",
            "known_info": [f"Your user ID: {user_id}", "Budget is a hard $900 cap.", "You need flights, hotel, and car."],
            "unknown_info": ["Which complete package actually fits under budget"],
            "task_rules": [
                "If the agent suggests a nicer hotel or SUV, ask for the full package total before accepting it.",
                "Reject any package that exceeds $900 total.",
                "End with [TASK_DONE] once the in-budget package is booked and summarized.",
            ],
        },
        "_replay_trace": [
            {"name": "create_booking", "arguments": {"flight_id": outbound.flight_id, "user_id": user_id, "cabin_class": "economy", "seat_type": "window", "payment_method": "credit_card", "meal_preference": "standard", "add_wifi": False, "add_extra_legroom": False, "add_insurance": True}},
            {"name": "create_booking", "arguments": {"flight_id": inbound.flight_id, "user_id": user_id, "cabin_class": "economy", "seat_type": "window", "payment_method": "credit_card", "meal_preference": "standard", "add_wifi": False, "add_extra_legroom": False, "add_insurance": True}},
            {"name": "book_hotel", "arguments": {"hotel_id": hotel_ok.hotel_id, "user_id": user_id}},
            {"name": "book_car_rental", "arguments": {"car_id": car_econ.car_id, "user_id": user_id}},
        ],
        "task_summary": "Traveler needs a full Denver package under a hard budget and explicitly warns against nicer options unless the whole bundle still fits. Correct resolution: the agent should keep the package on the standard hotel and economy car because the higher-end alternatives break the hard cap once the whole trip is totaled.\n\nChallenge: This tests package-level budget discipline against tempting component upgrades.",
        "task_requirements": [
            {"id": "cross_plan_trip_budget_with_preference_floor_hard_cap", "kind": "must", "requirement": "Agent must keep the full booked package at or below the stated $900 total budget.", "evidence": "conversation"},
            {"id": "cross_plan_trip_budget_with_preference_floor_reject_upgrades", "kind": "must", "requirement": "Agent must make clear why the suite and SUV options do not fit once the whole trip total is considered.", "evidence": "conversation"},
        ],
        "_hotel_inventory": [hotel_ok, hotel_nicer],
        "_car_inventory": [car_econ, car_suv],
    }
    return [outbound, inbound], [], task_data


def scenario_ET05():
    user_id = "user_005"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW

    flight = build_flight("AA", "LAX", "SEA", "2026-06-20", "morning", economy_price=230, business_price=690)
    booking = build_booking(user_id, flight, cabin_class="economy", booked_days_ago=3, now=now, booking_id="BK-ET05", has_insurance=False)
    hotel = build_hotel(user_id, "SEA", "2026-06-20", "2026-06-23", room_type="standard", nightly_rate=150, booked_days_ago=3, now=now)

    same_day_replacement = build_flight("AA", "LAX", "SEA", "2026-06-20", "evening", economy_price=320, business_price=790, flight_id="AA-ET05S")
    next_day_replacement = build_flight("AA", "LAX", "SEA", "2026-06-21", "morning", economy_price=260, business_price=740, flight_id="AA-ET05R")

    task_data = {
        "task_id": "cascade_rebook_flight_keep_existing_hotel",
        "user_id": user_id,
        "now": now,
        "opening_message": f"I still want my Seattle trip, but I may need to move flight booking {booking.booking_id}. I already have a Seattle hotel, and before you change anything I want to compare the reasonable flight options against what that would do to the trip overall. My user ID is {user_id}.",
        "user_simulator": {
            "personality": "Focused and practical.",
            "user_sim_context": "You still want the Seattle trip and already have a hotel reservation starting June 20. The hard part is not just comparing two replacement flights, but revising the recommendation when a late trip-integrity constraint appears. The cheaper next-day flight initially looks attractive, but after the comparison you reveal that you arranged a June 20 evening dinner near the hotel and that this was one reason for keeping the original first night. The correct recommendation should pivot to the pricier same-day evening flight because it preserves the June 20 commitment and the full hotel stay. The first phase must stay informational and comparative, and the agent should not execute the change until after the post-pivot final approval.",
            "known_info": [f"Your user ID: {user_id}", f"Flight booking: {booking.booking_id}", f"Hotel reservation: {hotel.reservation_id}"],
            "unknown_info": [
                "Whether the agent will compare the cheaper next-day move against the same-day hotel-preserving move before changing anything",
                "Whether the agent will revise its recommendation after learning about the June 20 dinner tied to the hotel stay",
            ],
            "task_rules": [
                "Open by asking for a compare-first recommendation and do not authorize any flight change yet.",
                "If the agent does not surface two distinct flight-change paths, ask whether there is a same-day option that preserves the full hotel stay versus a next-day option that sacrifices the first hotel night.",
                "After the initial comparison, say the cheaper next-day option sounds tempting on price alone, but then reveal that you arranged a June 20 evening dinner near the hotel and that missing the first hotel night would also mean missing that plan.",
                "If the agent does not revise its recommendation after that reveal, ask whether the June 20 commitment changes which option is actually best for the trip overall.",
                "If the agent pivots to the same-day evening flight because it preserves both the full hotel stay and the June 20 dinner plan, agree that this is the path you want.",
                "Only then say: 'Yes, change the flight to the same-day option. Leave the hotel exactly as it is.'",
                "If the agent tries to cancel or change the hotel, stop them and say the hotel should remain active and unchanged.",
                "End with [TASK_DONE] only after the flight is changed to the same-day hotel-preserving option and the agent explicitly confirms the hotel remained active and unchanged.",
            ],
        },
        "_replay_trace": [
            {"name": "update_booking", "arguments": {"booking_id": booking.booking_id, "flight_id": same_day_replacement.flight_id, "change_reason": "personal", "cabin_class": "economy", "seat_type": "aisle", "meal_preference": "vegan", "add_wifi": True, "add_extra_legroom": False, "add_insurance": False}},
        ],
        "task_summary": "Traveler still wants the Seattle trip and already has a hotel reservation starting June 20, but now needs help comparing the best flight-change path. Correct resolution: the agent should compare the cheaper next-day replacement flight against a pricier same-day evening flight, then revise its recommendation after the user reveals a June 20 evening dinner tied to the hotel stay. The correct final choice is the same-day evening option because it preserves both the full hotel stay and the June 20 commitment. The agent should only after explicit post-pivot approval change the flight while keeping the hotel active and unchanged.\n\nChallenge: This tests sequential trip-integrity reasoning and willingness to revise a locally cheaper recommendation when new linked-trip information appears.",
        "task_requirements": [
            {"id": "cascade_rebook_flight_keep_existing_hotel_discover", "kind": "must", "requirement": f"Agent must acknowledge linked hotel reservation {hotel.reservation_id} when handling the flight change.", "evidence": "conversation"},
            {"id": "cascade_rebook_flight_keep_existing_hotel_compare", "kind": "must", "requirement": "Agent must compare a same-day hotel-preserving flight-change path against a cheaper next-day flight-change path before acting, rather than treating the flight change as a single-option update.", "evidence": "conversation"},
            {"id": "cascade_rebook_flight_keep_existing_hotel_reasoning", "kind": "must", "requirement": f"Agent must explain why keeping hotel reservation {hotel.reservation_id} fully usable makes the same-day replacement flight preferable to the cheaper next-day replacement flight once the June 20 dinner commitment is revealed.", "evidence": "conversation"},
            {"id": "cascade_rebook_flight_keep_existing_hotel_pivot", "kind": "must", "requirement": "Agent must revise or reaffirm its recommendation in light of the newly revealed June 20 dinner plan, rather than sticking to a price-only view from earlier in the conversation.", "evidence": "conversation"},
            {"id": "cascade_rebook_flight_keep_existing_hotel_preserve", "kind": "must", "requirement": f"Agent must keep hotel reservation {hotel.reservation_id} active and unchanged while changing flight booking {booking.booking_id} to the same-day hotel-preserving option.", "evidence": "conversation"},
            {"id": "cascade_rebook_flight_keep_existing_hotel_no_premature_write", "kind": "must_not", "requirement": "Agent must not change the flight before the user explicitly approves the same-day hotel-preserving recommendation after the post-pivot discussion.", "evidence": "conversation"},
        ],
        "_hotels": [hotel],
    }
    return [flight, same_day_replacement, next_day_replacement], [booking], task_data


def scenario_ET06():
    user_id = "user_002"
    assert user_id in _USERS_BY_ID
    now = DEFAULT_NOW

    hotel = build_hotel(user_id, "LAX", "2026-06-24", "2026-06-27", room_type="standard", nightly_rate=155, booked_days_ago=4, now=now)
    car = build_car_rental(user_id, "LAX", "2026-06-24", "2026-06-27", car_class="economy", daily_rate=46, booked_days_ago=4, now=now)
    flight_out = build_flight("UA", "ORD", "LAX", "2026-06-24", "morning", economy_price=250, business_price=760, flight_id="UA-ET06A")
    flight_ret = build_flight("UA", "LAX", "ORD", "2026-06-27", "evening", economy_price=260, business_price=770, flight_id="UA-ET06B")

    task_data = {
        "task_id": "cross_plan_add_flights_to_existing_ground_trip",
        "user_id": user_id,
        "now": now,
        "opening_message": f"I already have a Los Angeles hotel and car booked, but now I need to add flights to complete the trip. Can you help me build around what I already have? My user ID is {user_id}.",
        "user_simulator": {
            "personality": "Organized and constraint-aware.",
            "user_sim_context": "You already have the ground portion of an LA trip and now need flights that fit around those existing bookings. You want the agent to treat the hotel and car dates as fixed constraints rather than as suggestions that can be silently changed.",
            "known_info": [f"Your user ID: {user_id}", f"Hotel reservation: {hotel.reservation_id}", f"Car rental: {car.rental_id}"],
            "unknown_info": ["Whether the agent will anchor the flight search to the existing ground-trip dates"],
            "task_rules": [
                "If the agent suggests flights on different dates than the hotel and car, remind them the ground trip is already fixed.",
                "Approve only flights that align with the existing hotel and car reservation dates.",
                "End with [TASK_DONE] after both matching flights are booked and summarized.",
            ],
        },
        "_replay_trace": [
            {"name": "create_booking", "arguments": {"flight_id": flight_out.flight_id, "user_id": user_id, "cabin_class": "economy", "seat_type": "window", "payment_method": "credit_card", "meal_preference": "vegetarian", "add_wifi": False, "add_extra_legroom": False, "add_insurance": False}},
            {"name": "create_booking", "arguments": {"flight_id": flight_ret.flight_id, "user_id": user_id, "cabin_class": "economy", "seat_type": "window", "payment_method": "credit_card", "meal_preference": "vegetarian", "add_wifi": False, "add_extra_legroom": False, "add_insurance": False}},
        ],
        "task_summary": "Traveler already has hotel and car reservations and now needs flights built around those fixed dates. Correct resolution: the agent should anchor the flight plan to the existing ground-trip reservations instead of proposing flights that require rebuilding the trip.\n\nChallenge: This tests whether the agent can plan around pre-existing trip state rather than assuming every package starts from scratch.",
        "task_requirements": [
            {"id": "cross_plan_add_flights_to_existing_ground_trip_anchor", "kind": "must", "requirement": f"Agent must use hotel reservation {hotel.reservation_id} and car rental {car.rental_id} as fixed date constraints when proposing flights.", "evidence": "conversation"},
            {"id": "cross_plan_add_flights_to_existing_ground_trip_no_date_drift", "kind": "must_not", "requirement": "Agent must not propose or book flights that force the user to change the already-booked hotel or car dates.", "evidence": "conversation"},
        ],
        "_hotels": [hotel],
        "_car_rentals": [car],
    }
    return [flight_out, flight_ret], [], task_data


SCENARIOS = [
    scenario_ET01,
    scenario_ET02,
    scenario_ET03,
    scenario_ET04,
    scenario_ET05,
    scenario_ET06,
]
