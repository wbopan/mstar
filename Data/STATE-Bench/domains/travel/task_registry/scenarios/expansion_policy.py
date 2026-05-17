"""Expanded travel scenarios focused on policy and information reasoning."""

from __future__ import annotations

from domains.travel.schemas import Booking, Flight
from domains.travel.task_registry._builders import (
    _USERS_BY_ID,
    DEFAULT_NOW,
    build_booking,
    build_car_rental,
    build_flight,
    build_hotel,
)


def _make_policy_scenario(config: dict):
    def scenario() -> tuple[list[Flight], list[Booking], dict]:
        user_id = config["user_id"]
        assert user_id in _USERS_BY_ID, f"Unknown user: {user_id}"
        now = DEFAULT_NOW

        flights: list[Flight] = []
        bookings: list[Booking] = []
        hotels = []
        car_rentals = []
        booking_ids: list[str] = []
        known_info = [f"Your user ID: {user_id}"]
        for booking_cfg in config.get("bookings", []):
            flight = build_flight(
                airline_code=booking_cfg["airline"],
                origin=booking_cfg["origin"],
                destination=booking_cfg["destination"],
                date=booking_cfg["date"],
                time_range=booking_cfg.get("time_range", "morning"),
                stops=booking_cfg.get("stops", 0),
                economy_price=booking_cfg["economy_price"],
                business_price=booking_cfg["business_price"],
                flight_id=booking_cfg.get("flight_id"),
                status=booking_cfg.get("status", "scheduled"),
                delay_minutes=booking_cfg.get("delay_minutes", 0),
            )
            booking = build_booking(
                user_id=user_id,
                flight=flight,
                cabin_class=booking_cfg["cabin_class"],
                booked_days_ago=booking_cfg.get("booked_days_ago", 5),
                now=now,
                booking_id=booking_cfg.get("booking_id"),
                has_insurance=booking_cfg.get("has_insurance", False),
            )
            if booking_cfg.get("payment_method") == "points":
                booking.payment_method = "points"
                booking.points_used = booking_cfg["points_used"]
                booking.cash_amount = 0
            flights.append(flight)
            bookings.append(booking)
            booking_ids.append(booking.booking_id)
            known_info.append(f"Relevant booking: {booking.booking_id}")

        for hotel_cfg in config.get("hotels", []):
            hotel = build_hotel(
                user_id=user_id,
                city=hotel_cfg["city"],
                check_in=hotel_cfg["check_in"],
                check_out=hotel_cfg["check_out"],
                room_type=hotel_cfg.get("room_type", "standard"),
                nightly_rate=hotel_cfg.get("nightly_rate", 150),
                reservation_id=hotel_cfg.get("reservation_id"),
                booked_days_ago=hotel_cfg.get("booked_days_ago", 5),
                now=now,
            )
            hotels.append(hotel)
            known_info.append(f"Hotel reservation: {hotel.reservation_id}")

        for car_cfg in config.get("car_rentals", []):
            car_rental = build_car_rental(
                user_id=user_id,
                pickup_location=car_cfg["pickup_location"],
                pickup_date=car_cfg["pickup_date"],
                dropoff_date=car_cfg["dropoff_date"],
                car_class=car_cfg.get("car_class", "economy"),
                daily_rate=car_cfg.get("daily_rate", 50),
                rental_id=car_cfg.get("rental_id"),
                booked_days_ago=car_cfg.get("booked_days_ago", 5),
                now=now,
            )
            car_rentals.append(car_rental)
            known_info.append(f"Car rental: {car_rental.rental_id}")

        task_requirements = []
        for idx, requirement in enumerate(config["requirements"], start=1):
            task_requirements.append(
                {
                    "id": f"{config['task_id']}_{idx}",
                    "kind": requirement.get("kind", "must"),
                    "requirement": requirement["text"],
                    "evidence": "conversation",
                }
            )

        task_data = {
            "task_id": config["task_id"],
            "user_id": user_id,
            "now": now,
            "opening_message": config["opening_message"].format(user_id=user_id, booking_ids=booking_ids),
            "user_simulator": {
                "personality": config.get("personality", "Calm and detail-oriented."),
                "user_sim_context": config["user_sim_context"],
                "known_info": known_info,
                "unknown_info": config.get("unknown_info", []),
                "task_rules": config["task_rules"],
            },
            "task_summary": config["task_summary"],
            "task_requirements": task_requirements,
            "state_requirements": [],
        }
        if hotels:
            task_data["_hotels"] = hotels
        if car_rentals:
            task_data["_car_rentals"] = car_rentals
        return flights, bookings, task_data

    scenario.__name__ = config["func_name"]
    return scenario


_POLICY_CONFIGS = [
    {
        "func_name": "scenario_EP01",
        "task_id": "policy_cancel_vs_change_business_international",
        "user_id": "user_001",
        "bookings": [
            {
                "airline": "AA",
                "origin": "JFK",
                "destination": "LHR",
                "date": "2026-06-25",
                "cabin_class": "business",
                "economy_price": 880,
                "business_price": 1800,
                "booking_id": "BK-EP01",
                "booked_days_ago": 10,
            }
        ],
        "opening_message": "Before I decide what to do with booking BK-EP01, can you compare what it would cost me to cancel versus just change it? Do not cancel or change anything yet. My user ID is {user_id}.",
        "user_sim_context": "You have an international business-class booking and want a clean compare-only explanation first. Because business class is flexible in some ways but not necessarily in every way, you want the agent to separate cancellation rules from change rules instead of hand-waving both as 'premium'. After that informational comparison, you want the agent to help you decide what to do under a hard budget for cancellation loss, but only after keeping the first phase informational.",
        "unknown_info": ["Exact international business cancellation fee", "Whether business changes stay free internationally", "Which path preserves more value under a hard cancellation-loss budget"],
        "task_rules": [
            "Ask for both the cancellation rule and the change rule on the same booking.",
            "If the agent gives only one side, ask for the missing comparison.",
            "Do not authorize any write action during the first phase; you only want a clean informational compare-first answer.",
            "After the agent explains both rules, say you would only cancel if the cancellation loss were $250 or less, and ask which path the agent would recommend under that budget constraint.",
            "Do not authorize any actual write action even after the recommendation; this is still a compare-and-recommend policy task, not an execution task.",
            "End with [TASK_DONE] once the comparison and recommendation are clear.",
        ],
        "task_summary": "Traveler wants a compare-first explanation of cancel versus change for an international business-class booking, then a recommendation under a hard budget for acceptable cancellation loss. Correct resolution: the agent should explain that the booking can be changed for no fee, that cancellation is not free and still follows the international business cancellation formula, and then recommend keeping the change path because cancellation exceeds the user's loss threshold.\n\nChallenge: This tests whether the agent can keep premium-cabin cancellation and change rules separate, preserve an information-only first phase, and then reason from those rules into a recommendation without jumping into execution.",
        "requirements": [
            {"text": "Agent must explain that changing the international business booking does not incur a change fee."},
            {"text": "Agent must explain that cancellation is not free and still follows the international business cancellation policy for this booking."},
            {"text": "After the user introduces a hard maximum acceptable cancellation loss of $250, agent must recommend against cancellation because the cancellation loss exceeds that threshold while the change path remains fee-free."},
            {"kind": "must_not", "text": "Agent must not claim that international business cancellation is automatically free just because business-class changes are free."},
            {"kind": "must_not", "text": "Agent must not attempt to cancel or change the booking during this compare-and-recommend policy task."},
        ],
    },
    {
        "func_name": "scenario_EP02",
        "task_id": "policy_cancel_keep_trip_loss_compare",
        "user_id": "user_003",
        "bookings": [
            {
                "airline": "DL",
                "origin": "JFK",
                "destination": "MIA",
                "date": "2026-06-19",
                "cabin_class": "economy",
                "economy_price": 420,
                "business_price": 980,
                "booking_id": "BK-EP02",
                "booked_days_ago": 9,
                "has_insurance": True,
            }
        ],
        "hotels": [
            {
                "city": "MIA",
                "check_in": "2026-06-19",
                "check_out": "2026-06-22",
                "room_type": "standard",
                "nightly_rate": 180,
                "reservation_id": "HR-EP02",
                "booked_days_ago": 9,
            }
        ],
        "car_rentals": [
            {
                "pickup_location": "MIA",
                "pickup_date": "2026-06-19",
                "dropoff_date": "2026-06-22",
                "car_class": "suv",
                "daily_rate": 70,
                "rental_id": "CR-EP02",
                "booked_days_ago": 9,
            }
        ],
        "opening_message": "Before I decide what to do with my Miami trip, can you compare the loss if I cancel only flight booking BK-EP02 versus if I cancel the whole trip? Do not cancel anything yet. My user ID is {user_id}.",
        "user_sim_context": "You still might take the Miami trip another way, so the first thing you want is a clean compare-only explanation of two strategies: canceling only the insured flight, or canceling the full trip including the linked hotel and car. You do not volunteer the hotel and car upfront because you want to see whether the agent discovers them as part of the whole-trip option. After the comparison, you want a recommendation under a strict maximum total-loss budget, but this remains informational only and not an execution request.",
        "unknown_info": ["Whether canceling only the flight loses any money", "Whether the rest of the Miami trip has linked hotel and car reservations", "What the total loss would be if the whole trip were canceled now", "Which strategy fits a maximum total-loss budget of $120 while preserving the ability to still take the trip another way"],
        "task_rules": [
            "Open by asking only for a comparison between canceling the flight versus canceling the whole trip, and make clear you do not want anything canceled yet.",
            "Do not volunteer the hotel or car unless the agent asks about other reservations or explicitly evaluates what canceling the whole trip would mean.",
            "If the agent compares only flight outcomes and ignores the rest of the trip, ask what 'cancel the whole trip' would actually include.",
            "Once the agent has surfaced the linked hotel and car, ask which option the agent would recommend if you want to keep your total loss at $120 or less and still preserve the option to travel another way.",
            "Do not authorize any cancellation in either phase; this is a compare-and-recommend policy task only.",
            "End with [TASK_DONE] once the comparison and recommendation are clear.",
        ],
        "task_summary": "Traveler wants a compare-first explanation of the loss from canceling only an insured Miami flight versus canceling the full linked trip, then a recommendation under a maximum total-loss budget while preserving the option to travel another way. Correct resolution: the agent should explain that canceling only the insured flight loses $0, proactively surface that the full-trip path also includes hotel reservation HR-EP02 and car rental CR-EP02, explain that the hotel is still in the 24-48 hour tier with a $90 fee while the SUV rental cancels for a $50 surcharge, and recommend canceling only the flight because the whole-trip path would lose $140 and exceed the user's $120 cap.\\n\\nChallenge: This tests whether the agent can proactively discover linked reservations, compare multiple policy engines in one informational flow, and recommend the globally better strategy instead of answering only the visible flight question.",
        "requirements": [
            {"text": "Agent must explain that canceling insured flight booking BK-EP02 would result in no flight cancellation loss."},
            {"text": "Agent must proactively surface that evaluating the whole-trip option requires including hotel reservation HR-EP02 and car rental CR-EP02 rather than treating the request as flight-only."},
            {"text": "Agent must explain that canceling hotel reservation HR-EP02 now would incur the 24-48 hour hotel fee tier, specifically a $90 charge."},
            {"text": "Agent must explain that canceling SUV rental CR-EP02 now would incur only the $50 SUV surcharge because it is still 24 or more hours before pickup."},
            {"text": "After the user introduces the $120 maximum total-loss budget while wanting to preserve the option to still take the trip another way, agent must recommend canceling only the flight because the whole-trip option would lose $140 and exceed the stated cap."},
            {"kind": "must_not", "text": "Agent must not cancel any part of the trip during this compare-and-recommend policy task."},
        ],
    },
    {
        "func_name": "scenario_EP03",
        "task_id": "policy_upgrade_with_current_price_paid_anchor",
        "user_id": "user_004",
        "bookings": [
            {
                "airline": "UA",
                "origin": "DEN",
                "destination": "MIA",
                "date": "2026-06-24",
                "cabin_class": "economy",
                "economy_price": 320,
                "business_price": 860,
                "booking_id": "BK-EP03",
                "booked_days_ago": 8,
            }
        ],
        "opening_message": "I have booking BK-EP03 in economy. Before I do anything, can you explain how the upgrade price should be calculated from what I already paid? My user ID is {user_id}.",
        "user_sim_context": "You are not asking the agent to execute an upgrade yet. You want the pricing logic explained from the amount already paid on the booking because you do not trust vague upgrade quotes that ignore the original fare. After that, you want a recommendation about whether a business upgrade still makes sense under a hard comfort budget, but this remains informational and comparison-focused rather than an execution request.",
        "unknown_info": ["How economy-to-business upgrade pricing is anchored", "What the actual business upgrade amount would be on this booking", "Whether upgrading still makes sense under a hard $500 comfort budget"],
        "task_rules": [
            "Ask the agent to explain the formula before quoting the number.",
            "If the agent only gives the final amount, ask how it was derived from the original fare already paid.",
            "Once the agent explains the formula and amount, say you only want to spend up to $500 total on comfort upgrades for this trip and ask whether the business upgrade still fits that budget.",
            "Keep this informational only; do not authorize the upgrade itself.",
            "End with [TASK_DONE] once the explanation and recommendation are clear.",
        ],
        "task_summary": "Traveler wants a policy-level explanation of how an upgrade quote is derived from the amount already paid on an economy booking, then a recommendation under a hard comfort budget. Correct resolution: the agent should explain that the business-upgrade quote is based on the target-cabin price minus the amount already paid on the booking, apply that math to show the actual upgrade amount for BK-EP03, and then recommend against upgrading because the required spend exceeds the user's $500 comfort budget.\n\nChallenge: This tests whether the agent can move from upgrade-price explanation into budget-based recommendation without flattening the answer into either a generic fare-difference formula or a generic budget warning.",
        "requirements": [
            {"text": "Agent must explain that the upgrade quote is based on the target-cabin price minus the amount already paid on the booking."},
            {"text": "Agent must apply that pricing logic to booking BK-EP03 rather than speaking only in generic terms."},
            {"text": "After the user introduces a hard $500 comfort budget, agent must recommend against the business upgrade because the required upgrade spend exceeds that budget."},
            {"kind": "must_not", "text": "Agent must not attempt to execute the upgrade during this compare-and-recommend policy task."},
        ],
    },
    {
        "func_name": "scenario_EP04",
        "task_id": "policy_baggage_same_user_two_tiers",
        "user_id": "user_002",
        "bookings": [
            {
                "airline": "DL",
                "origin": "ORD",
                "destination": "ATL",
                "date": "2026-06-20",
                "cabin_class": "basic_economy",
                "economy_price": 220,
                "business_price": 720,
                "booking_id": "BK-EP04A",
                "booked_days_ago": 4,
            },
            {
                "airline": "DL",
                "origin": "ORD",
                "destination": "ATL",
                "date": "2026-06-28",
                "cabin_class": "economy",
                "economy_price": 260,
                "business_price": 760,
                "booking_id": "BK-EP04B",
                "booked_days_ago": 4,
            },
        ],
        "opening_message": "I have two Atlanta trips, BK-EP04A and BK-EP04B. They are the same route, but one is basic economy and one is regular economy. Can you compare my baggage rules on both? My user ID is {user_id}.",
        "user_sim_context": "You are comparing baggage policy on two bookings that feel nearly identical except for fare class. You first want the side-by-side allowance explanation. After that, you want practical advice for two packing plans: one where you bring two checked bags on the basic-economy trip, and another where you bring three checked bags on the regular-economy trip but would prefer to avoid paying extra on that booking if possible. The agent needs to keep the first phase informational, then reason through both plans separately rather than flattening them into one generic baggage answer.",
        "unknown_info": ["How baggage rules differ between basic economy and economy on the same route", "What happens if you bring two checked bags on the basic-economy trip", "Whether three checked bags on the regular-economy trip still triggers extra-bag cost"],
        "task_rules": [
            "Ask for a side-by-side comparison rather than two isolated explanations.",
            "If the agent answers one booking only, ask for the other booking explicitly.",
            "Keep the first phase informational only.",
            "After the comparison, say you are considering two packing plans: bringing two checked bags on BK-EP04A, and bringing three checked bags on BK-EP04B while hoping to avoid extra baggage charges on the regular-economy booking if possible.",
            "Ask the agent which plan is more fee-efficient and whether the regular-economy booking really avoids extra cost for three checked bags.",
            "Do not authorize any change. End with [TASK_DONE] after the comparison and recommendation are clear.",
        ],
        "task_summary": "Traveler wants a side-by-side baggage comparison for two otherwise similar bookings that differ only in fare class, then a recommendation across two concrete packing plans. Correct resolution: the agent should explain the allowances for both bookings separately, make clear that the bookings do not have the same checked-bag entitlement even on the same route, explain that taking two checked bags on the basic-economy booking is costly because that fare starts with no free checked bags and higher extra-bag fees, explain that three checked bags on the regular-economy booking still fit within the traveler's free-bag allowance, and recommend the regular-economy three-bag plan as the more fee-efficient option.\n\nChallenge: This tests whether the agent can move from fare-class policy comparison into a packing recommendation without losing track of the loyalty-tier baggage interaction on the regular-economy booking.",
        "requirements": [
            {"text": "Agent must explain the baggage allowance for the basic-economy booking separately from the regular-economy booking."},
            {"text": "Agent must make clear that the two bookings do not have the same checked-bag entitlement despite sharing the same traveler and route."},
            {"text": "After the user introduces the two packing plans, agent must explain that bringing two checked bags on BK-EP04A is not fee-efficient because the basic-economy booking starts with no free checked bags and higher extra-bag fees."},
            {"text": "After the user introduces the two packing plans, agent must explain that bringing three checked bags on BK-EP04B still fits within the regular-economy booking's free checked-bag allowance for this traveler and is therefore the more fee-efficient plan."},
            {"kind": "must_not", "text": "Agent must not invent a baggage charge on BK-EP04B if the three checked bags fit within that booking's actual free allowance."},
        ],
    },
    {
        "func_name": "scenario_EP05",
        "task_id": "policy_delay_threshold_edge_compare",
        "user_id": "user_005",
        "bookings": [
            {
                "airline": "AA",
                "origin": "LAX",
                "destination": "SFO",
                "date": "2026-06-18",
                "cabin_class": "economy",
                "economy_price": 210,
                "business_price": 710,
                "booking_id": "BK-EP05A",
                "status": "delayed",
                "delay_minutes": 119,
            },
            {
                "airline": "AA",
                "origin": "LAX",
                "destination": "SFO",
                "date": "2026-06-18",
                "cabin_class": "economy",
                "economy_price": 220,
                "business_price": 720,
                "booking_id": "BK-EP05B",
                "status": "delayed",
                "delay_minutes": 120,
            },
        ],
        "opening_message": "Two of my flights are delayed, BK-EP05A and BK-EP05B, and they are only one minute apart. Can you tell me what compensation each one qualifies for? My user ID is {user_id}.",
        "user_sim_context": "You have two almost-identical delays and want the threshold explained very literally. Because the delays differ by only one minute, you need the agent to be exact about where compensation begins instead of rounding the two cases together.",
        "unknown_info": ["Whether 119 and 120 minutes fall into the same compensation tier"],
        "task_rules": [
            "Ask for each booking separately if the agent tries to summarize both together.",
            "If the agent rounds or hand-waves the threshold, ask for the exact minute rule.",
            "Keep this informational only. End with [TASK_DONE] once the distinction is clear.",
        ],
        "task_summary": "Traveler wants a threshold-exact comparison between two delays that differ by a single minute. Correct resolution: the agent should keep the 119-minute case below compensation and the 120-minute case in the meal-voucher tier instead of blending them together.\n\nChallenge: This tests whether the agent respects exact threshold semantics rather than approximate intuition around delay rights.",
        "requirements": [
            {"text": "Agent must explain that the 119-minute delay does not qualify for compensation."},
            {"text": "Agent must explain that the 120-minute delay qualifies for the meal-voucher tier."},
        ],
    },
    {
        "func_name": "scenario_EP06",
        "task_id": "policy_insurance_vs_delay_interaction_info_only",
        "user_id": "user_003",
        "bookings": [
            {
                "airline": "DL",
                "origin": "JFK",
                "destination": "MIA",
                "date": "2026-06-19",
                "cabin_class": "economy",
                "economy_price": 300,
                "business_price": 790,
                "booking_id": "BK-EP06",
                "has_insurance": True,
                "status": "delayed",
                "delay_minutes": 180,
                "booked_days_ago": 3,
            }
        ],
        "hotels": [
            {
                "city": "MIA",
                "check_in": "2026-06-19",
                "check_out": "2026-06-21",
                "room_type": "standard",
                "nightly_rate": 185,
                "reservation_id": "HR-EP06",
                "booked_days_ago": 3,
            }
        ],
        "opening_message": "My insured booking BK-EP06 is delayed about three hours. Before I decide anything, can you first explain what the delay itself entitles me to and what the insurance changes? I do not want you to cancel, rebook, or change anything yet. My user ID is {user_id}.",
        "user_sim_context": "You want the agent to keep two policy systems separate: delay compensation and insurance-backed cancellation. The first phase should stay informational only. After that, you want a recommendation about whether to keep the delayed outbound flight tonight or cancel it under insurance and try again tomorrow, but the key is that this choice affects the rest of the trip asymmetrically: canceling tonight would likely waste your Miami hotel stay, while keeping the delayed outbound still preserves the already-booked return tomorrow. You do not want the agent to reason about the outbound in isolation or jump from policy explanation straight into action.",
        "unknown_info": ["Whether insurance changes delay compensation", "Whether a three-hour delay triggers full compensation", "Whether canceling the flight under insurance would also affect the linked Miami hotel reservation and tomorrow's return booking differently", "Which path the agent should recommend if wasting tonight's hotel stay is worse than dealing with a delayed arrival but the return is already booked for tomorrow"],
        "task_rules": [
            "Open by asking separately what the delay itself qualifies for and what insurance changes, if anything.",
            "If the agent starts taking action in the first phase, steer back to policy explanation only.",
            "After the agent explains the delay and insurance pieces, say that you also have a Miami hotel tonight and a booked return flight tomorrow, and ask whether they would recommend keeping this delayed outbound or canceling it under insurance and trying again tomorrow.",
            "Do not volunteer the hotel reservation ID unless the agent asks about linked reservations or otherwise investigates what tonight's Miami plans depend on.",
            "If the agent treats the decision as flight-only, ask what happens to the rest of the trip, specifically tonight's hotel stay and tomorrow's return booking, under each option.",
            "If the agent recommends canceling the outbound without confronting the asymmetry between losing tonight's hotel and preserving tomorrow's return, push back once and ask for a clearer compare-first recommendation across the whole trip.",
            "Do not authorize any cancellation or rebooking in either phase; this remains informational plus recommendation only.",
            "End with [TASK_DONE] once the explanation and recommendation are clear.",
        ],
        "task_summary": "Traveler first wants an information-only explanation of how insurance and a three-hour delay interact on the same outbound booking, then wants a recommendation about keeping the delayed flight versus canceling it under insurance while accounting for a Miami hotel tonight and a separate return booking tomorrow. Correct resolution: the agent should explain that the three-hour delay only qualifies for the meal-voucher tier, explain that insurance does not upgrade that delay entitlement, surface that evaluating the outbound decision requires accounting for hotel reservation HR-EP06 and the already-booked return tomorrow, explain that canceling the outbound would likely waste tonight's hotel stay while still leaving the return as a separate preserved booking, and recommend keeping the delayed outbound rather than canceling and restarting tomorrow because the user explicitly cares more about preserving tonight's Miami stay than avoiding a delayed arrival.\n\nChallenge: This tests whether the agent can keep an information-only first phase clean, then shift into a recommendation that requires linked-reservation discovery plus asymmetric trip-consequence reasoning instead of a generic delay-versus-insurance explanation.",
        "requirements": [
            {"text": "Agent must explain that a three-hour delay falls into the meal-voucher tier rather than the full compensation tier."},
            {"text": "Agent must explain that insurance does not change the delay-compensation tier itself."},
            {"text": "When the user asks for a recommendation after mentioning a Miami hotel that night and a return booking tomorrow, agent must surface that evaluating the cancel-versus-keep choice requires accounting for hotel reservation HR-EP06 and the outbound-versus-return asymmetry rather than treating the question as flight-only."},
            {"text": "After the user asks for a recommendation while caring about tonight's Miami stay and already having tomorrow's return booked, agent must recommend keeping the delayed outbound rather than canceling it under insurance and starting over tomorrow."},
            {"kind": "must_not", "text": "Agent must not execute or propose an immediate cancellation, rebooking, or other booking mutation during this information-plus-recommendation task as if the user had already authorized it."},
        ],
    },
    {
        "func_name": "scenario_EP07",
        "task_id": "policy_upgrade_chain_budget_breakdown",
        "user_id": "user_005",
        "bookings": [
            {
                "airline": "AA",
                "origin": "LAX",
                "destination": "JFK",
                "date": "2026-06-23",
                "cabin_class": "economy",
                "economy_price": 340,
                "business_price": 890,
                "booking_id": "BK-EP07",
                "booked_days_ago": 6,
            },
            {
                "airline": "AA",
                "origin": "JFK",
                "destination": "LAX",
                "date": "2026-06-27",
                "cabin_class": "economy",
                "economy_price": 120,
                "business_price": 360,
                "booking_id": "BK-EP07R",
                "booked_days_ago": 6,
            }
        ],
        "opening_message": "I have booking BK-EP07 in economy and a $700 total comfort budget for this trip. Before I do anything, can you break down the full path to first class on BK-EP07 and tell me whether that budget is enough? My user ID is {user_id}.",
        "user_sim_context": "You want the outbound upgrade path explained carefully first, including why first class cannot be reached directly from economy. After that, you want a recommendation that uses the same $700 total trip budget across your whole trip rather than only the outbound leg. You do not mention the return booking immediately because you want to see whether the agent can carry the budget reasoning forward once that second leg enters the picture.",
        "unknown_info": ["Whether first class can be reached directly from the outbound economy booking", "What the staged outbound cost to first class would be", "Whether the same $700 total comfort budget could be used more effectively across the whole trip once the return booking is considered"],
        "task_rules": [
            "Open by asking for the total outbound path to first class on BK-EP07, not just the first leg of the upgrade path.",
            "If the agent gives only one upgrade leg, ask for the full chain and the budget implication for BK-EP07 specifically.",
            "After the outbound explanation is clear, say you also have return booking BK-EP07R on the same trip and ask whether, under the same $700 total comfort budget, it would make more sense to upgrade both flights only to business instead of trying to reach first on the outbound leg.",
            "If the agent answers only the outbound leg and ignores the return booking or the shared trip budget, ask how the recommendation changes once BK-EP07R is included.",
            "Keep this informational plus recommendation only; do not authorize any upgrade on either booking.",
            "End with [TASK_DONE] once the full-path explanation and trip-level recommendation are clear.",
        ],
        "task_summary": "Traveler first wants the outbound two-step upgrade chain to first class broken down against a fixed comfort budget, then wants a trip-level recommendation once a return booking is added under the same $700 total comfort budget. Correct resolution: the agent should explain that BK-EP07 cannot upgrade directly from economy to first, explain that the outbound economy-to-business step would cost $510 and the business-to-first step would add $712 more for a full outbound path of $1,222, conclude that the first-class path exceeds the $700 budget, then surface return booking BK-EP07R and recommend using the budget on business upgrades for both legs instead because BK-EP07 business costs $510 and BK-EP07R business costs $180, fitting the shared trip budget at $690 total.\n\nChallenge: This tests whether the agent can keep upgrade-path structure, shared-budget carryover, and trip-level recommendation aligned instead of answering only the visible outbound first-class question.",
        "requirements": [
            {"text": "Agent must explain that economy cannot upgrade directly to first class."},
            {"text": "Agent must provide the staged outbound path for BK-EP07, including that economy-to-business costs $510 and the additional business-to-first step costs $712, for a total outbound path of $1,222 that exceeds the stated $700 budget."},
            {"text": "After the user mentions return booking BK-EP07R under the same total comfort budget, agent must include BK-EP07R in the analysis rather than continuing to reason only about BK-EP07."},
            {"text": "After the user introduces BK-EP07R, agent must recommend upgrading both BK-EP07 and BK-EP07R only to business because those two business upgrades total $690 and fit within the shared $700 trip budget, unlike the outbound first-class path."},
            {"kind": "must_not", "text": "Agent must not attempt to execute any upgrade during this information-plus-recommendation task."},
        ],
    },
]


SCENARIOS = [_make_policy_scenario(config) for config in _POLICY_CONFIGS]
