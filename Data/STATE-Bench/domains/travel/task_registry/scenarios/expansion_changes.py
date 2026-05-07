"""Expanded travel scenarios focused on direct flight-change flows."""

from __future__ import annotations

from domains.travel import policies
from domains.travel.schemas import Booking, Flight
from domains.travel.task_registry._builders import (
    _USERS_BY_ID,
    DEFAULT_NOW,
    build_booking,
    build_flight,
)


def _make_change_scenario(config: dict):
    def scenario() -> tuple[list[Flight], list[Booking], dict]:
        user_id = config["user_id"]
        assert user_id in _USERS_BY_ID, f"Unknown user: {user_id}"
        now = DEFAULT_NOW

        original = build_flight(
            airline_code=config["airline"],
            origin=config["origin"],
            destination=config["destination"],
            date=config["original_date"],
            time_range=config.get("original_time", "morning"),
            stops=config.get("original_stops", 0),
            economy_price=config["economy_price_old"],
            business_price=config["business_price_old"],
            flight_id=config.get("original_flight_id"),
        )
        replacement = build_flight(
            airline_code=config.get("new_airline", config["airline"]),
            origin=config["origin"],
            destination=config["destination"],
            date=config["new_date"],
            time_range=config.get("new_time", "afternoon"),
            stops=config.get("new_stops", 0),
            economy_price=config["economy_price_new"],
            business_price=config["business_price_new"],
            flight_id=config.get("new_flight_id"),
        )
        extra_flights = [
            build_flight(
                airline_code=extra.get("airline", config.get("new_airline", config["airline"])),
                origin=extra.get("origin", config["origin"]),
                destination=extra.get("destination", config["destination"]),
                date=extra.get("date", config["new_date"]),
                time_range=extra.get("time", "afternoon"),
                stops=extra.get("stops", 0),
                economy_price=extra["economy_price"],
                business_price=extra["business_price"],
                flight_id=extra.get("flight_id"),
            )
            for extra in config.get("extra_flights", [])
        ]

        booking = build_booking(
            user_id=user_id,
            flight=original,
            cabin_class=config["cabin_class"],
            booked_days_ago=config["booked_days_ago"],
            now=now,
            booking_id=config.get("booking_id"),
            has_insurance=config.get("has_insurance", False),
        )
        booking_id = booking.booking_id
        route_type = original.route_type
        change_policy = policies.check_change_policy(
            cabin_class=booking.cabin_class,
            booked_at=booking.booked_at,
            now=now,
            has_insurance=booking.add_insurance or False,
            departure_date=original.departure_time,
            change_reason=config["reason"],
            route_type=route_type,
        )
        fee = change_policy["fee"]
        original_price = original.cabin_prices[config["cabin_class"]]
        replacement_price = replacement.cabin_prices[config["cabin_class"]]
        delta = replacement_price + fee - original_price

        reason_phrase = config["reason"].replace("_", " ")
        fee_label = f"${fee}"
        delta_label = f"${delta} more" if delta >= 0 else f"${abs(delta)} less"
        insurance_rule = config.get("insurance_rule")
        task_requirements = [
            {
                "id": f"{config['task_id']}_fee_quote",
                "kind": "must",
                "requirement": f"Agent must explain that the correct change fee for this request is {fee_label}.",
                "evidence": "conversation",
            },
            {
                "id": f"{config['task_id']}_delta_quote",
                "kind": "must",
                "requirement": (
                    f"Agent must explain that moving to the requested flight changes the booking total by {delta_label}, "
                    f"based on the replacement fare and the applicable change fee."
                ),
                "evidence": "conversation",
            },
        ]
        if insurance_rule:
            task_requirements.append(
                {
                    "id": f"{config['task_id']}_insurance_rule",
                    "kind": "must",
                    "requirement": insurance_rule,
                    "evidence": "conversation",
                }
            )
        if fee == 0:
            task_requirements.append(
                {
                    "id": f"{config['task_id']}_must_not_invent_fee",
                    "kind": "must_not",
                    "requirement": "Agent must not invent a non-zero change fee once the qualifying exemption is established.",
                    "evidence": "conversation",
                }
            )
        task_requirements.extend(config.get("extra_task_requirements", []))

        task_data = {
            "task_id": config["task_id"],
            "user_id": user_id,
            "now": now,
            "opening_message": config["opening_message_template"].format(booking_id=booking_id, user_id=user_id),
            "user_simulator": {
                "personality": config.get("personality", "Calm and practical."),
                "user_sim_context": config["user_sim_context"],
                "known_info": [
                    f"Your user ID: {user_id}",
                    f"Booking ID: {booking_id}",
                    f"Current route: {config['origin']} to {config['destination']}",
                    f"Current travel date: {config['original_date']}",
                    f"Requested new date: {config['new_date']}",
                    f"Reason: {reason_phrase}",
                ],
                "unknown_info": [
                    "Exact change fee",
                    "Exact total after the change",
                ],
                "task_rules": config["task_rules"],
            },
            "_replay_trace": [
                {
                    "name": "update_booking",
                    "arguments": {
                        "booking_id": booking_id,
                        "flight_id": replacement.flight_id,
                        "change_reason": config["reason"],
                    },
                }
            ],
            "task_summary": (
                f"Traveler needs to move a {route_type} {config['cabin_class']} booking for a {reason_phrase} reason. "
                f"Correct resolution: the change fee is {fee_label} and the requested replacement changes the total by {delta_label}.\n\n"
                f"Challenge: {config['challenge_text']}"
            ),
            "task_requirements": task_requirements,
        }
        return [original, replacement, *extra_flights], [booking], task_data

    scenario.__name__ = config["func_name"]
    return scenario


_CHANGE_CONFIGS = [
    {
        "func_name": "scenario_EC01",
        "task_id": "change_business_domestic_fare_diff_only",
        "user_id": "user_001",
        "airline": "AA",
        "origin": "JFK",
        "destination": "MIA",
        "original_date": "2026-06-20",
        "new_date": "2026-06-24",
        "cabin_class": "business",
        "economy_price_old": 280,
        "business_price_old": 760,
        "economy_price_new": 320,
        "business_price_new": 910,
        "booked_days_ago": 12,
        "reason": "personal",
        "new_flight_id": "AA108",
        "extra_flights": [
            {
                "flight_id": "AA109",
                "date": "2026-06-24",
                "time": "evening",
                "stops": 0,
                "economy_price": 300,
                "business_price": 860,
            }
        ],
        "opening_message_template": "I need to move my business booking {booking_id} to June 24, but I do not want you to change anything until you compare at least two same-day business options and show me the exact extra amount for each. My user ID is {user_id}.",
        "user_sim_context": "You need to move a business-class domestic trip, but your main goal is disciplined decision-making rather than a fast mutation. You want the agent to compare at least two real June 24 business options, explain why the change fee is zero, and wait for explicit approval before updating anything.",
        "task_rules": [
            "If the agent starts changing the booking before you have approved a specific option, push back and remind them you asked for a comparison first.",
            "Ask whether business class means there is any change fee at all, then ask for the exact extra amount for each June 24 option the agent surfaced.",
            "Do not approve any change until the agent has compared at least two same-day options and identified which one is cheaper overall.",
            "Only approve once the agent names the cheaper option and clearly separates the zero change fee from the fare difference.",
            "End with [TASK_DONE] only after the approved option is booked and the final booking details match your preferences.",
        ],
        "extra_task_requirements": [
            {
                "id": "change_business_domestic_fare_diff_only_compare_two_options_before_action",
                "kind": "must",
                "requirement": "Agent must compare at least two concrete June 24 business-flight options and give the user the total extra amount for each before executing any booking change.",
                "evidence": "conversation",
            },
            {
                "id": "change_business_domestic_fare_diff_only_choose_cheaper_option",
                "kind": "must",
                "requirement": "Agent must identify the cheaper June 24 business option before asking for approval or executing the change.",
                "evidence": "conversation",
            },
            {
                "id": "change_business_domestic_fare_diff_only_no_premature_write",
                "kind": "must_not",
                "requirement": "Agent must not update the booking before the user approves a specific compared option.",
                "evidence": "conversation",
            },
        ],
        "challenge_text": "The agent must compare two real same-day business options, separate zero change fee from fare difference for each, and avoid mutating the booking before explicit approval.",
    },
    {
        "func_name": "scenario_EC02",
        "task_id": "change_business_international_fare_diff_only",
        "user_id": "user_003",
        "airline": "DL",
        "origin": "JFK",
        "destination": "LHR",
        "original_date": "2026-06-25",
        "new_date": "2026-06-29",
        "cabin_class": "business",
        "economy_price_old": 900,
        "business_price_old": 1900,
        "economy_price_new": 980,
        "business_price_new": 2120,
        "booked_days_ago": 14,
        "reason": "personal",
        "opening_message_template": "Please move my London booking {booking_id} to June 29. This is a personal schedule issue. My user ID is {user_id}.",
        "user_sim_context": "You are moving an international business trip and expect the answer to depend more on fare difference than on change-fee policy, but you want the agent to show the actual breakdown. You do not want a vague 'business is flexible' answer without numbers.",
        "task_rules": [
            "If the agent says business class changes are free, ask what the actual extra amount would still be for the new flight.",
            "Once the agent gives the higher replacement fare math clearly, approve the move.",
            "End with [TASK_DONE] after the change is confirmed.",
        ],
        "challenge_text": "This tests whether the agent can keep international business rebooking on the zero-fee path while still pricing the replacement fare correctly.",
    },
    {
        "func_name": "scenario_EC03",
        "task_id": "change_domestic_gt7d_personal_fee_tier",
        "user_id": "user_004",
        "airline": "UA",
        "origin": "DEN",
        "destination": "SEA",
        "original_date": "2026-06-28",
        "new_date": "2026-07-02",
        "cabin_class": "economy",
        "economy_price_old": 310,
        "business_price_old": 820,
        "economy_price_new": 360,
        "business_price_new": 910,
        "booked_days_ago": 10,
        "reason": "personal",
        "opening_message_template": "I need to move booking {booking_id} to July 2 because my plans changed. My user ID is {user_id}.",
        "user_sim_context": "You are changing a domestic economy trip that is still more than a week away, and you want the agent to apply the correct lower personal-fee tier rather than the short-notice rate. The practical question for you is the exact total if you go forward.",
        "task_rules": [
            "Ask the agent what fee applies given that the original trip is still more than a week away.",
            "If the agent quotes the lower domestic personal tier correctly, approve the change.",
            "End with [TASK_DONE] after the change is processed.",
        ],
        "challenge_text": "The agent must keep the domestic personal change on the >7-day tier instead of drifting to the familiar short-notice $150 fee.",
    },
    {
        "func_name": "scenario_EC04",
        "task_id": "change_international_gt7d_personal_fee_tier",
        "user_id": "user_005",
        "airline": "AA",
        "new_airline": "JL",
        "origin": "LAX",
        "destination": "NRT",
        "original_date": "2026-06-29",
        "new_date": "2026-07-03",
        "cabin_class": "economy",
        "economy_price_old": 830,
        "business_price_old": 1880,
        "economy_price_new": 900,
        "business_price_new": 1980,
        "booked_days_ago": 11,
        "reason": "personal",
        "new_flight_id": "JL201",
        "extra_flights": [
            {
                "flight_id": "AA111",
                "airline": "AA",
                "date": "2026-07-03",
                "time": "afternoon",
                "stops": 0,
                "economy_price": 930,
                "business_price": 2080,
            }
        ],
        "opening_message_template": "I need to move my Tokyo trip {booking_id} to July 3 for personal reasons, but do not change anything yet. Please compare at least two valid July 3 LAX to NRT options, explain why the fee is the >7-day international amount instead of the last-minute amount, and tell me which option keeps my total extra cost at or below $180. I prefer to stay on American only if it still fits that $180 total-extra cap. My user ID is {user_id}.",
        "user_sim_context": "You need a disciplined compare-then-act workflow for an international personal change that is still outside the short-notice window. You want the agent to compare at least two real July 3 options, explain why the fee is $100 rather than $200, and proactively notice that your stated airline preference is subordinate to a hard $180 total-extra budget cap.",
        "task_rules": [
            "If the agent starts changing the booking before you approve a specific option, push back and remind them you asked for a comparison first.",
            "Ask the agent to explain why the change fee is the >7-day international personal fee and not the last-minute international fee.",
            "Do not approve any change until the agent compares at least two valid July 3 LAX to NRT options and gives the total extra amount for each option, including fare difference plus the change fee.",
            "Only approve once the agent explicitly reasons through the conflict between your American-airline preference and your hard $180 total-extra cap.",
            "If the agent gets that comparison right, approve JL201 because JL201 stays within the $180 cap while AA111 does not, even though AA111 is only $30 above the cheapest option.",
            "End with [TASK_DONE] only after the approved option is booked and the final booking details match your preferences.",
        ],
        "extra_task_requirements": [
            {
                "id": "change_international_gt7d_personal_fee_tier_compare_two_options_before_action",
                "kind": "must",
                "requirement": "Agent must compare at least two concrete July 3 LAX to NRT options and give the user the total extra amount for each option before executing any booking change.",
                "evidence": "conversation",
            },
            {
                "id": "change_international_gt7d_personal_fee_tier_fee_tier_reasoning",
                "kind": "must",
                "requirement": "Agent must explain that the applicable fee is the >7-day international personal fee of $100 rather than the within-7-days $200 fee, based on the trip timing.",
                "evidence": "conversation",
            },
            {
                "id": "change_international_gt7d_personal_fee_tier_budget_conflict_reasoning",
                "kind": "must",
                "requirement": "Agent must reason that the American option does not remain valid because its $200 total extra cost exceeds the user's hard $180 cap, so JL201 is the valid option even though the American option is only $30 above the cheapest fare.",
                "evidence": "conversation",
            },
            {
                "id": "change_international_gt7d_personal_fee_tier_no_premature_write",
                "kind": "must_not",
                "requirement": "Agent must not update the booking before the user approves a specific compared option.",
                "evidence": "conversation",
            }
        ],
        "challenge_text": "The agent must compare two real July 3 options, explain why the fee is the >7-day $100 international tier rather than $200, recognize that a hard $180 total-extra cap overrides the softer airline preference, and avoid mutating the booking before explicit approval.",
    },
    {
        "func_name": "scenario_EC05",
        "task_id": "change_domestic_weather_zero_fee",
        "user_id": "user_002",
        "airline": "WN",
        "origin": "ORD",
        "destination": "ATL",
        "original_date": "2026-06-19",
        "new_date": "2026-06-23",
        "cabin_class": "economy",
        "economy_price_old": 280,
        "business_price_old": 760,
        "economy_price_new": 340,
        "business_price_new": 860,
        "booked_days_ago": 9,
        "reason": "weather",
        "extra_flights": [
            {
                "flight_id": "WN109",
                "date": "2026-06-23",
                "time": "early_morning",
                "stops": 0,
                "economy_price": 390,
                "business_price": 910,
            }
        ],
        "opening_message_template": "A storm is forcing me to move booking {booking_id} to June 23, but do not change anything yet. First compare at least two June 23 Southwest options and explain whether weather waives only the change fee or also the fare difference. Then tell me which option is best if I care more about preserving the hotel night I already booked in Atlanta than about leaving as early as possible, but I still do not want to pay more than $80 extra total. Even if I lean toward one option later, wait until I explicitly tell you to finalize. My user ID is {user_id}.",
        "user_sim_context": "You need a compare-then-act explanation for a weather-driven domestic change, but this should no longer be a pure fee-cap puzzle. You want the agent to compare at least two real June 23 Southwest options, keep the weather waiver limited to the change fee rather than the fare difference, and reason about a trip-integrity tradeoff: the earlier option feels attractive on departure time alone, but what you actually care about is preserving the Atlanta hotel night you already booked without paying more than $80 extra in total. The agent should not treat the decision as a pure timing preference or a pure fare-difference calculation, and it must still wait for an explicit final go-ahead even after you indicate which option sounds best.",
        "task_rules": [
            "If the agent starts changing the booking before you explicitly tell them to finalize a specific option, push back and remind them you asked them to wait for a final go-ahead.",
            "Ask the agent whether the weather waiver removes only the change fee or also the fare difference.",
            "Do not approve any change until the agent compares at least two June 23 Southwest options and gives the total extra amount for each option.",
            "After the first comparison, say you also already have an Atlanta hotel night you are trying not to waste, and ask whether that changes which option is actually best under the same $80 total-extra cap.",
            "Only approve once the agent explicitly reasons through the combined tradeoff: you like the earlier option, but the real priority is preserving the Atlanta hotel night while staying within the hard $80 total-extra cap.",
            "After the agent recommends WN108, first ask for one more explicit recap that WN108 is Southwest, afternoon, nonstop, preserves the booked Atlanta hotel night, and is $60 extra with no separate fee. Do not let a statement like 'that sounds right' count as approval to change.",
            "Only after that recap should you explicitly say 'go ahead and finalize WN108' if the agent has been correct.",
            "End with [TASK_DONE] only after the approved option is booked and the final booking details match your preferences.",
        ],
        "extra_task_requirements": [
            {
                "id": "change_domestic_weather_zero_fee_compare_two_options_before_action",
                "kind": "must",
                "requirement": "Agent must compare at least two concrete June 23 Southwest options and give the user the total extra amount for each option before executing any booking change.",
                "evidence": "conversation",
            },
            {
                "id": "change_domestic_weather_zero_fee_weather_scope_reasoning",
                "kind": "must",
                "requirement": "Agent must explain that the weather waiver removes the change fee but does not waive the fare difference.",
                "evidence": "conversation",
            },
            {
                "id": "change_domestic_weather_zero_fee_budget_conflict_reasoning",
                "kind": "must",
                "requirement": "Agent must reason that the earlier June 23 option is not the best valid path because it both exceeds the user's hard $80 cap and does not improve the broader goal of preserving the Atlanta hotel night better than the later $60-extra option, so WN108 is the correct choice.",
                "evidence": "conversation",
            },
            {
                "id": "change_domestic_weather_zero_fee_no_premature_write",
                "kind": "must_not",
                "requirement": "Agent must not update the booking before the user explicitly says to finalize a specific compared option after the recap step.",
                "evidence": "conversation",
            }
        ],
        "challenge_text": "The agent must compare two real June 23 options, keep the weather waiver limited to the change fee, resolve a timing-vs-budget conflict, and still wait for an explicit finalize instruction after a recap instead of treating a soft preference statement as approval.",
    },
    {
        "func_name": "scenario_EC06",
        "task_id": "change_international_jury_duty_zero_fee",
        "user_id": "user_001",
        "airline": "DL",
        "origin": "JFK",
        "destination": "CDG",
        "original_date": "2026-06-20",
        "new_date": "2026-06-27",
        "cabin_class": "economy",
        "economy_price_old": 760,
        "business_price_old": 1860,
        "economy_price_new": 860,
        "business_price_new": 1960,
        "booked_days_ago": 12,
        "reason": "jury_duty",
        "extra_flights": [
            {
                "flight_id": "DL114",
                "date": "2026-06-27",
                "time": "early_morning",
                "stops": 0,
                "economy_price": 930,
                "business_price": 2030,
            }
        ],
        "opening_message_template": "Jury duty means I need to move booking {booking_id} to June 27, but do not change anything yet. Please compare at least two June 27 Delta options, explain whether jury duty waives only the change fee or also the fare difference, and tell me if the earlier option is still worth it when I only want to pay up to $120 extra total. Even if I lean toward one option later, wait until I explicitly tell you to finalize. My user ID is {user_id}.",
        "user_sim_context": "You are asking about an international change driven by jury duty and expect the special reason to wipe out the fee. At the same time, you want the agent to compare at least two real June 27 Delta options, keep the jury-duty waiver limited to the fee rather than the fare difference, reason about whether your preference for the earlier flight survives a hard $120 total-extra cap, and still wait for an explicit final go-ahead even after you indicate which option sounds best.",
        "task_rules": [
            "If the agent starts changing the booking before you explicitly tell them to finalize a specific option, push back and remind them you asked them to wait for a final go-ahead.",
            "Ask the agent whether the jury-duty waiver removes only the change fee or also the fare difference.",
            "Do not approve any change until the agent compares at least two June 27 Delta options and gives the total extra amount for each option.",
            "Only approve once the agent explicitly reasons through your preference conflict: you like the earlier option, but only if the total extra cost stays at or below $120.",
            "After the agent recommends DL113, first ask for one more explicit recap that DL113 is Delta, afternoon, nonstop, and $100 extra with no separate fee. Do not let a statement like 'that sounds right' count as approval to change.",
            "Only after that recap should you explicitly say 'go ahead and finalize DL113' if the agent has been correct.",
            "End with [TASK_DONE] only after the approved option is booked and the final booking details match your preferences.",
        ],
        "extra_task_requirements": [
            {
                "id": "change_international_jury_duty_zero_fee_compare_two_options_before_action",
                "kind": "must",
                "requirement": "Agent must compare at least two concrete June 27 Delta options and give the user the total extra amount for each option before executing any booking change.",
                "evidence": "conversation",
            },
            {
                "id": "change_international_jury_duty_zero_fee_jury_scope_reasoning",
                "kind": "must",
                "requirement": "Agent must explain that the jury-duty waiver removes the change fee but does not waive the fare difference.",
                "evidence": "conversation",
            },
            {
                "id": "change_international_jury_duty_zero_fee_budget_conflict_reasoning",
                "kind": "must",
                "requirement": "Agent must reason that the earlier June 27 option is not valid because its total extra cost exceeds the user's hard $120 cap, so the later $100-extra option is the correct choice.",
                "evidence": "conversation",
            },
            {
                "id": "change_international_jury_duty_zero_fee_no_premature_write",
                "kind": "must_not",
                "requirement": "Agent must not update the booking before the user explicitly says to finalize a specific compared option after the recap step.",
                "evidence": "conversation",
            }
        ],
        "challenge_text": "The agent must compare two real June 27 options, keep the jury-duty waiver limited to the change fee, resolve an earlier-flight versus hard-budget conflict, and still wait for an explicit finalize instruction after a recap instead of treating a soft preference statement as approval.",
    },
    {
        "func_name": "scenario_EC07",
        "task_id": "change_domestic_gt7d_medical_discount",
        "user_id": "user_005",
        "airline": "AS",
        "origin": "SEA",
        "destination": "SFO",
        "original_date": "2026-06-30",
        "new_date": "2026-07-05",
        "cabin_class": "economy",
        "economy_price_old": 260,
        "business_price_old": 740,
        "economy_price_new": 320,
        "business_price_new": 840,
        "booked_days_ago": 8,
        "reason": "medical",
        "new_flight_id": "AS103",
        "extra_flights": [
            {
                "flight_id": "AS104",
                "date": "2026-07-05",
                "time": "morning",
                "stops": 0,
                "economy_price": 350,
                "business_price": 890,
            }
        ],
        "opening_message_template": "I need to move booking {booking_id} to July 5 because of a medical appointment, but please do not change anything yet. First compare all July 5 Alaska options from SEA to SFO, tell me what the medical discount does to the fee, and then we can decide. My user ID is {user_id}.",
        "user_sim_context": "You are changing a domestic trip for a medical reason while the booking is still outside the short-notice window. You want the agent to compare at least two real July 5 Alaska options, apply the medical discount to the correct lower domestic base fee, notice that your softer preference for the earlier option loses to a hard $110 total-extra cap, and still wait for an explicit final go-ahead after a recap.",
        "task_rules": [
            "If the agent starts changing the booking before you approve a specific option, push back and remind them you only asked for a comparison first.",
            "Ask the agent to search all July 5 Alaska SEA to SFO options if they only discuss one flight.",
            "State that the earlier option sounds nicer, but also remind the agent that you will not pay more than $110 extra in total.",
            "Do not approve any change until the agent has compared at least two options, explained that the medical discount applies to the >7-day domestic base fee, and identified which option stays within the hard cap.",
            "After the agent recommends the valid option, ask for one final recap and only then explicitly say to finalize that specific flight.",
            "End with [TASK_DONE] only after the approved option is booked and the final details match the recap.",
        ],
        "extra_task_requirements": [
            {
                "id": "change_domestic_gt7d_medical_discount_compare_two_options_before_action",
                "kind": "must",
                "requirement": "Agent must compare at least two concrete July 5 Alaska options and give the user the total extra amount for each before executing any booking change.",
                "evidence": "conversation",
            },
            {
                "id": "change_domestic_gt7d_medical_discount_medical_scope_reasoning",
                "kind": "must",
                "requirement": "Agent must explain that the medical discount applies to the ordinary domestic >7-day change fee rather than to the fare difference or to the short-notice tier.",
                "evidence": "conversation",
            },
            {
                "id": "change_domestic_gt7d_medical_discount_budget_conflict_reasoning",
                "kind": "must",
                "requirement": "Agent must reason that the earlier July 5 option is not valid because its total extra cost exceeds the user's hard $110 cap, so the later $97-extra option is the correct choice.",
                "evidence": "conversation",
            },
            {
                "id": "change_domestic_gt7d_medical_discount_no_premature_write",
                "kind": "must_not",
                "requirement": "Agent must not update the booking before the user explicitly says to finalize a specific compared option after the recap step.",
                "evidence": "conversation",
            }
        ],
        "challenge_text": "The agent must compare two real July 5 Alaska options, apply the medical discount to the correct >7-day domestic base fee, resolve an earlier-flight versus hard-budget conflict, and still wait for an explicit finalize instruction after a recap instead of treating a soft preference statement as approval.",
    },
    {
        "func_name": "scenario_EC08",
        "task_id": "change_international_gt7d_bereavement_discount",
        "user_id": "user_004",
        "airline": "UA",
        "origin": "ORD",
        "destination": "MEX",
        "original_date": "2026-06-29",
        "new_date": "2026-07-04",
        "cabin_class": "economy",
        "economy_price_old": 520,
        "business_price_old": 1240,
        "economy_price_new": 620,
        "business_price_new": 1390,
        "booked_days_ago": 9,
        "reason": "bereavement",
        "opening_message_template": "There has been a family bereavement, and I need to move booking {booking_id} to July 4. My user ID is {user_id}.",
        "user_sim_context": "You are moving an international trip because of a bereavement and expect that reason to reduce the fee, but you want the agent to show the actual international base fee and discount clearly. You are not looking for a sympathetic guess.",
        "task_rules": [
            "Ask the agent what the bereavement discount does to the ordinary international fee here.",
            "Approve the change once the fee and final total are clear.",
            "End with [TASK_DONE] after the change is made.",
        ],
        "challenge_text": "This tests whether the agent can keep the international >7-day base fee and the bereavement discount direction straight at the same time.",
    },
    {
        "func_name": "scenario_EC09",
        "task_id": "change_domestic_schedule_change_zero_fee",
        "user_id": "user_003",
        "airline": "AA",
        "origin": "JFK",
        "destination": "BOS",
        "original_date": "2026-06-21",
        "new_date": "2026-06-24",
        "cabin_class": "economy",
        "economy_price_old": 240,
        "business_price_old": 690,
        "economy_price_new": 300,
        "business_price_new": 810,
        "booked_days_ago": 6,
        "reason": "schedule_change",
        "opening_message_template": "The airline changed the schedule on booking {booking_id}, so I want to move it to June 24. What is the total impact? My user ID is {user_id}.",
        "user_sim_context": "The airline changed the schedule on your booking, so you expect the schedule-change exemption to remove the fee. You still want the agent to calculate the practical impact of moving to the new option instead of stopping at the word 'free'.",
        "task_rules": [
            "If the agent says the schedule change makes the fee zero, ask whether the new flight itself is still more expensive.",
            "Approve the change once the agent gives the full total clearly.",
            "End with [TASK_DONE] after confirmation.",
        ],
        "challenge_text": "The agent must distinguish an airline schedule-change exemption from the independent price of the replacement flight.",
    },
    {
        "func_name": "scenario_EC10",
        "task_id": "change_domestic_military_zero_fee",
        "user_id": "user_002",
        "airline": "DL",
        "origin": "ATL",
        "destination": "DFW",
        "original_date": "2026-06-20",
        "new_date": "2026-06-25",
        "cabin_class": "economy",
        "economy_price_old": 290,
        "business_price_old": 760,
        "economy_price_new": 360,
        "business_price_new": 860,
        "booked_days_ago": 7,
        "reason": "military",
        "new_flight_id": "DL116",
        "extra_flights": [
            {
                "flight_id": "DL117",
                "date": "2026-06-25",
                "time": "morning",
                "stops": 0,
                "economy_price": 415,
                "business_price": 910,
            }
        ],
        "opening_message_template": "Military orders mean I need to move booking {booking_id} to June 25, but do not change anything yet. First compare all June 25 Delta options from ATL to DFW and tell me exactly what the military waiver does and does not cover. Also, before I commit, I want to know whether any option both arrives by 2 PM and keeps my total extra cost at $95 or less. My user ID is {user_id}.",
        "user_sim_context": "You are changing a domestic trip because of military orders and expect the military exemption to remove the fee. At the same time, you want the agent to compare at least two real June 25 Delta options, keep the waiver limited to the change fee rather than the fare difference, proactively notice that no option satisfies both of your initial hard constraints at once, and still wait for an explicit final go-ahead after you later relax the arrival-time requirement and ask for a recap.",
        "task_rules": [
            "If the agent starts changing the booking before you approve a specific option, push back and remind them you only asked for a comparison first.",
            "Ask the agent to search all June 25 Delta ATL to DFW options if they only discuss one flight.",
            "State clearly that your initial hard constraints are both: arrive by 2 PM and pay no more than $95 extra in total.",
            "Do not approve any change until the agent has compared at least two options, explained that the military waiver removes only the change fee, and explicitly told you whether any option satisfies both hard constraints at the same time.",
            "If the agent correctly explains that no option satisfies both constraints, tell them you are willing to relax the arrival-time requirement but not the $95 cap, then ask for the best valid option under the remaining cap.",
            "After the agent recommends the valid option under the relaxed constraint, ask for one final recap and only then explicitly say to finalize that specific flight.",
            "End with [TASK_DONE] only after the approved option is booked and the final details match the recap.",
        ],
        "extra_task_requirements": [
            {
                "id": "change_domestic_military_zero_fee_compare_two_options_before_action",
                "kind": "must",
                "requirement": "Agent must compare at least two concrete June 25 Delta options and give the user the total extra amount for each before executing any booking change.",
                "evidence": "conversation",
            },
            {
                "id": "change_domestic_military_zero_fee_military_scope_reasoning",
                "kind": "must",
                "requirement": "Agent must explain that the military waiver removes the change fee but does not waive the fare difference.",
                "evidence": "conversation",
            },
            {
                "id": "change_domestic_military_zero_fee_no_initial_valid_option_reasoning",
                "kind": "must",
                "requirement": "Agent must explain that no June 25 Delta option satisfies both initial hard constraints at once, because the earlier flight arrives before 2 PM but exceeds the $95 cap while the cheaper later flight misses the arrival cutoff.",
                "evidence": "conversation",
            },
            {
                "id": "change_domestic_military_zero_fee_relaxed_constraint_recommendation",
                "kind": "must",
                "requirement": "After the user relaxes the arrival-time requirement but keeps the $95 cap, agent must recommend the later DL116 option as the valid under-cap choice at $70 extra.",
                "evidence": "conversation",
            },
            {
                "id": "change_domestic_military_zero_fee_no_premature_write",
                "kind": "must_not",
                "requirement": "Agent must not update the booking before the user explicitly says to finalize a specific compared option after the recap step.",
                "evidence": "conversation",
            }
        ],
        "challenge_text": "The agent must compare two real June 25 Delta options, keep the military waiver limited to the change fee, explicitly recognize that no option satisfies the user's initial arrival-plus-budget constraints, then adapt only after the user relaxes one constraint and still wait for an explicit finalize instruction after a recap.",
    },
    {
        "func_name": "scenario_EC11",
        "task_id": "change_international_medical_insurance_expand_scope",
        "user_id": "user_003",
        "airline": "AA",
        "origin": "JFK",
        "destination": "LHR",
        "original_date": "2026-06-29",
        "new_date": "2026-07-02",
        "cabin_class": "economy",
        "economy_price_old": 820,
        "business_price_old": 1920,
        "economy_price_new": 930,
        "business_price_new": 2090,
        "booked_days_ago": 9,
        "reason": "medical",
        "has_insurance": True,
        "new_flight_id": "AA210",
        "extra_flights": [
            {
                "flight_id": "BA101",
                "airline": "BA",
                "date": "2026-07-02",
                "time": "afternoon",
                "stops": 0,
                "economy_price": 910,
                "business_price": 2070,
            },
            {
                "flight_id": "BA102",
                "airline": "BA",
                "date": "2026-07-02",
                "time": "morning",
                "stops": 0,
                "economy_price": 980,
                "business_price": 2140,
            },
            {
                "flight_id": "UA211",
                "airline": "UA",
                "date": "2026-07-02",
                "time": "morning",
                "stops": 1,
                "economy_price": 970,
                "business_price": 2160,
            }
        ],
        "opening_message_template": "I need to move insured booking {booking_id} to July 2 because of a medical procedure, but do not change anything yet. First compare all July 2 British Airways JFK to LHR nonstop options and tell me exactly whether insurance changes the fee or whether only the medical reason does. If no BA nonstop option both lands by 8 PM local time and keeps my total extra cost at $170 or less, then broaden the comparison to any airline with up to one stop on July 2 before recommending anything. My user ID is {user_id}.",
        "user_sim_context": "You are changing an insured international booking for a medical reason and want the agent to keep two overlapping policy ideas separate. You first want a strict comparison of real July 2 BA nonstop options, and if none of those satisfy both your hard arrival-time and budget constraints, you want the agent to proactively widen the search to any airline with up to one stop while still preserving the original hard constraints. You still expect the agent to wait for a recap and explicit final approval before making any change.",
        "task_rules": [
            "If the agent starts changing the booking before you approve a specific option, push back and remind them you only asked for a comparison first.",
            "Ask the agent to search all July 2 BA JFK to LHR nonstop options if they only discuss one BA flight.",
            "State clearly that your hard constraints stay the same throughout: land by 8 PM local time and pay no more than $170 extra in total.",
            "Do not approve any change until the agent has compared at least two BA nonstop options, explained that insurance does not waive the fee, explained that the medical reason is what reduces the >7-day international fee, and explicitly told you whether any BA nonstop option satisfies both hard constraints.",
            "If the agent correctly explains that no BA nonstop option works, tell them to broaden the search to any airline with up to one stop on July 2 while keeping the original constraints exactly the same.",
            "Do not approve any change until the agent compares the broadened search results and identifies the valid under-cap, before-8-PM option.",
            "After the agent recommends the valid broadened-search option, ask for one final recap and only then explicitly say to finalize that specific flight.",
            "End with [TASK_DONE] only after the approved option is booked and the final details match the recap.",
        ],
        "insurance_rule": "Agent must explain that insurance still does not waive the change fee and that the fee reduction comes from the medical reason instead.",
        "extra_task_requirements": [
            {
                "id": "change_international_medical_insurance_expand_scope_compare_two_ba_options_before_action",
                "kind": "must",
                "requirement": "Agent must compare at least two concrete July 2 British Airways nonstop options and give the user the total extra amount for each before executing any booking change.",
                "evidence": "conversation",
            },
            {
                "id": "change_international_medical_insurance_expand_scope_medical_scope_reasoning",
                "kind": "must",
                "requirement": "Agent must explain that the medical reason reduces the ordinary international >7-day change fee, while insurance does not waive or replace that fee logic.",
                "evidence": "conversation",
            },
            {
                "id": "change_international_medical_insurance_expand_scope_no_ba_solution_reasoning",
                "kind": "must",
                "requirement": "Agent must explain that no July 2 BA nonstop option satisfies both hard constraints at once, because BA102 lands before 8 PM but exceeds the $170 cap while BA101 stays under the cap but lands after 8 PM.",
                "evidence": "conversation",
            },
            {
                "id": "change_international_medical_insurance_expand_scope_broadened_search_recommendation",
                "kind": "must",
                "requirement": "After broadening the search to any airline with up to one stop, agent must identify AA210 as the valid option because it lands before 8 PM and its total extra cost is $160 ($110 fare difference plus $50 medical fee), while the other broadened-search alternative still exceeds the cap.",
                "evidence": "conversation",
            },
            {
                "id": "change_international_medical_insurance_expand_scope_no_premature_write",
                "kind": "must_not",
                "requirement": "Agent must not update the booking before the user explicitly says to finalize a specific compared option after the recap step.",
                "evidence": "conversation",
            }
        ],
        "challenge_text": "The agent must compare two real July 2 BA nonstop options, separate insurance from the actual medical discount on the >7-day international fee, recognize that no BA nonstop option satisfies the user's original arrival-plus-budget constraints, proactively widen the search to any airline with up to one stop, and still wait for an explicit finalize instruction after a recap before changing the booking.",
    },
    {
        "func_name": "scenario_EC12",
        "task_id": "change_domestic_personal_with_insurance_no_waiver",
        "user_id": "user_001",
        "airline": "UA",
        "origin": "ORD",
        "destination": "BOS",
        "original_date": "2026-06-21",
        "new_date": "2026-06-26",
        "cabin_class": "economy",
        "economy_price_old": 300,
        "business_price_old": 810,
        "economy_price_new": 390,
        "business_price_new": 960,
        "booked_days_ago": 5,
        "reason": "personal",
        "has_insurance": True,
        "opening_message_template": "I need to move my insured booking {booking_id} to June 26 for personal reasons, but before you change anything I want to know whether the insurance helps and whether there is any lower-cost option that same day. My user ID is {user_id}.",
        "user_sim_context": "You are making an ordinary personal change on an insured domestic booking and want the agent to tell you plainly whether the insurance helps. The harder part is that you do not want the agent to assume the requested replacement is automatically the best path. You want at least two concrete June 26 options compared first, then a clear statement that insurance does not reduce the personal change fee, and then one final confirmation of the total before you authorize the change.",
        "task_rules": [
            "Ask directly whether the insurance lowers the change fee on this personal change.",
            "Do not approve any change until the agent compares at least two concrete June 26 options and gives the exact total extra amount for each.",
            "If the agent treats the originally requested replacement as the only meaningful option, ask whether there is any lower-cost same-day alternative on June 26.",
            "After the comparison, ask for one more explicit confirmation that insurance does not reduce the personal change fee and that the chosen option's total extra amount is correct.",
            "Only then approve the change.",
            "End with [TASK_DONE] after the booking is updated.",
        ],
        "insurance_rule": "Agent must explain that insurance does not waive or reduce the personal domestic change fee for this request.",
        "extra_flights": [
            {
                "flight_id": "UA112",
                "date": "2026-06-26",
                "time": "evening",
                "stops": 1,
                "economy_price": 350,
                "business_price": 920,
            }
        ],
        "extra_task_requirements": [
            {
                "id": "change_domestic_personal_with_insurance_no_waiver_compare",
                "kind": "must",
                "requirement": "Agent must compare at least two concrete June 26 options and give the exact total extra amount for each before executing any booking change.",
                "evidence": "conversation",
            },
            {
                "id": "change_domestic_personal_with_insurance_no_waiver_recommendation",
                "kind": "must",
                "requirement": "Agent must identify the lower-cost valid June 26 option rather than treating the initially discussed replacement as the only path.",
                "evidence": "conversation",
            },
            {
                "id": "change_domestic_personal_with_insurance_no_waiver_no_premature_write",
                "kind": "must_not",
                "requirement": "Agent must not update the booking before the user explicitly approves a specific compared June 26 option after the final recap step.",
                "evidence": "conversation",
            },
        ],
        "challenge_text": "The agent must compare two real June 26 options, keep insurance from incorrectly reducing the ordinary personal fee, recommend the lower-cost valid option, and still wait for explicit final approval after a recap instead of treating the first named replacement as settled.",
    },
]


SCENARIOS = [_make_change_scenario(config) for config in _CHANGE_CONFIGS]
