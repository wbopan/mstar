"""V5 Task Registry — scenario builders for 50 travel benchmark tasks.

Each scenario builder returns (flights, bookings, task_data) plus optional
_hotels and _car_rentals in task_data for cross-domain tasks.
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from domains.travel.schemas import (
    Booking,
    CarInventoryItem,
    CarRental,
    EnvironmentData,
    Flight,
    HotelInventoryItem,
    HotelReservation,
    User,
)
from domains.travel.task_registry._task_summaries import TASK_SUMMARIES
from domains.travel.task_registry._user_sim_contexts import USER_SIM_CONTEXTS
from state_bench.replay import BOOKING_PERSISTED_PREFERENCE_FIELDS

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_NOW = "2026-06-15T10:00:00"

DOMESTIC_AIRPORTS = ["ORD", "SFO", "LAX", "JFK", "MIA", "SEA", "DEN", "DFW", "BOS", "ATL"]
INTERNATIONAL_AIRPORTS = ["LHR", "NRT", "CDG", "YYZ", "GRU", "MEX", "FRA"]
AIRPORTS = DOMESTIC_AIRPORTS + INTERNATIONAL_AIRPORTS

ALL_AIRLINES = ["AA", "UA", "DL", "WN", "AS", "B6"]

TIME_RANGE_HOURS = {
    "early_morning": (5, 7),
    "morning": (8, 11),
    "afternoon": (12, 16),
    "evening": (17, 20),
    "red_eye": (21, 23),
}

# Cabin price ranges for generating realistic pricing
CABIN_PRICE_RANGES = {
    "economy": (200, 500),
    "business": (600, 1300),
    "first": (1200, 2500),
}

# ---------------------------------------------------------------------------
# Users (V5 — budget + preferences)
# ---------------------------------------------------------------------------

USERS = [
    User(
        user_id="user_001",
        name="Emma Smith",
        email="emma.smith@example.com",
        loyalty_tier="gold",
        loyalty_points=75000,
        budget=1500,
        preferences={
            "meal_preference": "kosher",
            "seat_type": "aisle",
            "add_wifi": True,
            "add_extra_legroom": True,
            "add_insurance": False,
        },
    ),
    User(
        user_id="user_002",
        name="Liam Johnson",
        email="liam.johnson@example.com",
        loyalty_tier="basic",
        loyalty_points=5000,
        budget=800,
        preferences={
            "meal_preference": "vegetarian",
            "seat_type": "window",
            "add_wifi": False,
            "add_extra_legroom": False,
            "add_insurance": False,
        },
    ),
    User(
        user_id="user_003",
        name="Olivia Williams",
        email="olivia.williams@example.com",
        loyalty_tier="platinum",
        loyalty_points=120000,
        budget=2000,
        preferences={
            "meal_preference": "standard",
            "seat_type": "aisle",
            "add_wifi": True,
            "add_extra_legroom": True,
            "add_insurance": True,
        },
    ),
    User(
        user_id="user_004",
        name="Noah Brown",
        email="noah.brown@example.com",
        loyalty_tier="silver",
        loyalty_points=15000,
        budget=600,
        preferences={
            "meal_preference": "standard",
            "seat_type": "window",
            "add_wifi": False,
            "add_extra_legroom": False,
            "add_insurance": True,
        },
    ),
    User(
        user_id="user_005",
        name="Ava Garcia",
        email="ava.garcia@example.com",
        loyalty_tier="basic",
        loyalty_points=12000,
        budget=700,
        preferences={
            "meal_preference": "vegan",
            "seat_type": "aisle",
            "add_wifi": True,
            "add_extra_legroom": False,
            "add_insurance": False,
        },
    ),
]

_USERS_BY_ID = {u.user_id: u for u in USERS}

SEARCH_STAGE_PREFERENCE_FIELDS = ("airline", "time_range", "max_stops", "cabin_class")
BOOKING_WRITE_TOOL_NAMES = {"create_booking", "update_booking"}
BOOKING_PREFERENCE_PUSHBACK_ORDER = (
    "cabin_class",
    "seat_type",
    "meal_preference",
    "add_wifi",
    "add_extra_legroom",
    "add_insurance",
)

AUTO_DERIVED_REPLAY_PREFERENCE_FIELDS = (
    "seat_type",
    "meal_preference",
    "add_wifi",
    "add_extra_legroom",
    "add_insurance",
)


def _format_max_stops(max_stops: int | None) -> str | None:
    if max_stops is None:
        return None
    if max_stops == 0:
        return "nonstop"
    if max_stops == 1:
        return "up to 1 stop"
    return f"up to {max_stops} stops"


def _search_intent_known_info_items(search_intent: dict[str, Any]) -> list[str]:
    items: list[str] = []
    cabin_class = search_intent.get("cabin_class")
    if cabin_class:
        items.append(f"Wants {cabin_class} class")

    airline = search_intent.get("airline")
    time_range = search_intent.get("time_range")
    max_stops = _format_max_stops(search_intent.get("max_stops"))
    preference_parts = []
    if airline:
        preference_parts.append(f"{airline} airline")
    if time_range:
        preference_parts.append(f"{time_range} departure")
    if max_stops:
        preference_parts.append(max_stops)
    if preference_parts:
        items.append("Prefers " + ", ".join(preference_parts))
    return items


def _search_intent_disclosure_rule(search_intent: dict[str, Any]) -> str | None:
    parts: list[str] = []
    cabin_class = search_intent.get("cabin_class")
    airline = search_intent.get("airline")
    time_range = search_intent.get("time_range")
    max_stops = search_intent.get("max_stops")

    if cabin_class:
        parts.append(f"{cabin_class} class")
    if airline:
        parts.append(f"{airline} airline")
    if time_range:
        parts.append(f"{time_range} departure")
    if max_stops is not None:
        parts.append("nonstop" if max_stops == 0 else f"up to {max_stops} stop(s)")

    if not parts:
        return None
    return "When asked about flight preferences, say " + ", ".join(parts) + "."


def _booking_preferences_for_user(user_id: str) -> dict[str, Any]:
    user = _USERS_BY_ID[user_id]
    return {field: user.preferences[field] for field in BOOKING_PERSISTED_PREFERENCE_FIELDS}


def _auto_derived_replay_preferences_for_user(user_id: str) -> dict[str, Any]:
    user = _USERS_BY_ID[user_id]
    return {field: user.preferences[field] for field in AUTO_DERIVED_REPLAY_PREFERENCE_FIELDS}


def _booking_preferences_from_existing_booking(booking: Booking | None) -> dict[str, Any]:
    if booking is None:
        return {}
    return {
        "cabin_class": booking.cabin_class,
        "seat_type": booking.seat_type,
        "meal_preference": booking.meal_preference,
        "add_wifi": booking.add_wifi,
        "add_extra_legroom": booking.add_extra_legroom,
        "add_insurance": booking.add_insurance,
    }


def _normalize_replay_trace(task_data: dict[str, Any], bookings: list[Booking] | None = None) -> list[dict[str, Any]]:
    user_id = task_data.get("user_id")
    replay_trace = task_data.get("_replay_trace", [])
    if not user_id or not replay_trace:
        return replay_trace

    user_booking_prefs = _auto_derived_replay_preferences_for_user(user_id)
    bookings_by_id = {booking.booking_id: booking for booking in (bookings or [])}
    normalized: list[dict[str, Any]] = []
    for step in replay_trace:
        if not isinstance(step, dict):
            normalized.append(step)
            continue
        name = step.get("name")
        arguments = dict(step.get("arguments", {}))
        if name == "create_booking":
            for field, value in user_booking_prefs.items():
                arguments.setdefault(field, value)
        elif name == "update_booking" and "flight_id" in arguments:
            booking_id = arguments.get("booking_id")
            existing = bookings_by_id.get(booking_id)
            existing_booking_prefs = _booking_preferences_from_existing_booking(existing)
            for field, value in existing_booking_prefs.items():
                if value is not None:
                    arguments.setdefault(field, value)
            for field, value in user_booking_prefs.items():
                arguments.setdefault(field, value)
        normalized.append({"name": name, "arguments": arguments})
    return normalized


def _booking_write_contract_rules() -> list[str]:
    return [
        "For any booking creation or flight change, all booking preferences must end up correct before you accept completion.",
        "Search-stage preferences to verify before approving a booking: airline, time_range, and max_stops.",
        "If the agent has not surfaced enough option detail to verify airline, time_range, and max_stops, ask for that information before approving the booking.",
        "Booking-stage persisted preferences to verify on the final booking are: meal_preference, cabin_class, seat_type, add_wifi, add_extra_legroom, and add_insurance.",
        "If the agent asks about one of those booking-stage preferences, answer directly using your profile preferences.",
        "If the agent books with any wrong booking-stage preference, correct exactly one preference at a time in this order: cabin_class, seat_type, meal_preference, add_wifi, add_extra_legroom, add_insurance.",
        "Do not try to verify raw flight_id. Budget remains a hard constraint.",
        "Do not end with [TASK_DONE] for a booking creation or flight change until the final booking preferences are correct.",
    ]


def _augment_user_simulator_rules(task_data: dict[str, Any]) -> None:
    sim = task_data.get("user_simulator")
    if not isinstance(sim, dict):
        return

    search_intent = task_data.get("_search_intent")
    if isinstance(search_intent, dict):
        known_info = list(sim.get("known_info", []))
        for item in _search_intent_known_info_items(search_intent):
            if item not in known_info:
                known_info.append(item)
        sim["known_info"] = known_info

        disclosure_rule = _search_intent_disclosure_rule(search_intent)
        if disclosure_rule:
            task_rules = list(sim.get("task_rules", []))
            if disclosure_rule not in task_rules:
                task_rules.append(disclosure_rule)
            sim["task_rules"] = task_rules

    replay_trace = task_data.get("_replay_trace", [])
    needs_booking_contract = any(
        isinstance(step, dict)
        and step.get("name") in BOOKING_WRITE_TOOL_NAMES
        and (step.get("name") == "create_booking" or "flight_id" in step.get("arguments", {}))
        for step in replay_trace
    )
    if not needs_booking_contract:
        return

    task_rules = list(sim.get("task_rules", []))
    budget_not_constraint = any(
        isinstance(rule, str) and "budget is NOT the constraint" in rule
        for rule in task_rules
    )
    for rule in _booking_write_contract_rules():
        if budget_not_constraint and rule == "Do not try to verify raw flight_id. Budget remains a hard constraint.":
            continue
        if rule not in task_rules:
            task_rules.append(rule)
    sim["task_rules"] = task_rules

# ---------------------------------------------------------------------------
# ID generators
# ---------------------------------------------------------------------------

_used_flight_ids: set[str] = set()
_flight_counter: dict[str, int] = {}

_used_booking_ids: set[str] = set()
_booking_counter = 1000

_hotel_counter = 100
_hotel_inventory_counter = 1
_car_counter = 100
_car_inventory_counter = 1
_DEFAULT_GENERATION_SEED = 20260414


def reset_counters() -> None:
    """Reset all ID counters. Call before generating a new task set."""
    global _booking_counter, _hotel_counter, _hotel_inventory_counter, _car_counter, _car_inventory_counter
    random.seed(_DEFAULT_GENERATION_SEED)
    _used_flight_ids.clear()
    _flight_counter.clear()
    _used_booking_ids.clear()
    _booking_counter = 1000
    _hotel_counter = 100
    _hotel_inventory_counter = 1
    _car_counter = 100
    _car_inventory_counter = 1


def _next_flight_id(airline_code: str) -> str:
    if airline_code not in _flight_counter:
        _flight_counter[airline_code] = 100
    while True:
        fid = f"{airline_code}{_flight_counter[airline_code]}"
        _flight_counter[airline_code] += 1
        if fid not in _used_flight_ids:
            _used_flight_ids.add(fid)
            return fid


def _next_booking_id() -> str:
    global _booking_counter
    while True:
        bid = f"BK-{_booking_counter}"
        _booking_counter += 1
        if bid not in _used_booking_ids:
            _used_booking_ids.add(bid)
            return bid


def _next_hotel_id() -> str:
    global _hotel_counter
    hid = f"HR-{_hotel_counter:04d}"
    _hotel_counter += 1
    return hid


def _next_hotel_inventory_id() -> str:
    global _hotel_inventory_counter
    hid = f"HOTEL-{_hotel_inventory_counter:04d}"
    _hotel_inventory_counter += 1
    return hid


def _next_car_id() -> str:
    global _car_counter
    cid = f"CR-{_car_counter:04d}"
    _car_counter += 1
    return cid


def _next_car_inventory_id() -> str:
    global _car_inventory_counter
    cid = f"CAR-{_car_inventory_counter:04d}"
    _car_inventory_counter += 1
    return cid


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def classify_route_type(origin: str, destination: str) -> str:
    domestic = set(DOMESTIC_AIRPORTS)
    if origin in domestic and destination in domestic:
        return "domestic"
    return "international"


def _pick_other(options: list[str], exclude: str) -> str:
    choices = [o for o in options if o != exclude]
    return random.choice(choices)


# ---------------------------------------------------------------------------
# Build functions (V5 — Flight has cabin_prices dict)
# ---------------------------------------------------------------------------


def build_flight(
    airline_code: str,
    origin: str,
    destination: str,
    date: str,
    time_range: str,
    stops: int = 0,
    economy_price: int | None = None,
    business_price: int | None = None,
    status: str = "scheduled",
    delay_minutes: int = 0,
    flight_id: str | None = None,
) -> Flight:
    """Build a single flight with cabin pricing map."""
    if flight_id is None:
        flight_id = _next_flight_id(airline_code)
    else:
        _used_flight_ids.add(flight_id)

    hour_range = TIME_RANGE_HOURS.get(time_range, (8, 11))
    hour = random.randint(hour_range[0], hour_range[1])
    minute = random.choice([0, 15, 30, 45])
    dep = datetime.fromisoformat(f"{date}T{hour:02d}:{minute:02d}:00")

    duration = random.randint(150, 360)
    arr = dep + timedelta(minutes=duration)

    # Generate cabin prices
    if economy_price is None:
        economy_price = random.randint(*CABIN_PRICE_RANGES["economy"])
    if business_price is None:
        business_price = random.randint(*CABIN_PRICE_RANGES["business"])

    cabin_prices = {"economy": economy_price, "business": business_price}

    return Flight(
        flight_id=flight_id,
        airline_code=airline_code,
        origin=origin,
        destination=destination,
        departure_time=dep.isoformat(),
        arrival_time=arr.isoformat(),
        duration_minutes=duration,
        stops=stops,
        cabin_prices=cabin_prices,
        status=status,
        delay_minutes=delay_minutes,
        route_type=classify_route_type(origin, destination),
    )


def build_route_flights(
    origin: str,
    destination: str,
    date: str,
    target_airline: str,
    target_time: str,
    target_stops: int = 0,
    target_economy_price: int | None = None,
    target_business_price: int | None = None,
    target_status: str = "scheduled",
    target_delay: int = 0,
    target_flight_id: str | None = None,
    num_distractors: int = 3,
    seed: int | None = None,
) -> tuple[Flight, list[Flight]]:
    """Build a target flight + distractors for a route/date.

    Returns (target_flight, [target + distractors]).
    """
    if seed is not None:
        random.seed(seed)

    target = build_flight(
        airline_code=target_airline,
        origin=origin,
        destination=destination,
        date=date,
        time_range=target_time,
        stops=target_stops,
        economy_price=target_economy_price,
        business_price=target_business_price,
        status=target_status,
        delay_minutes=target_delay,
        flight_id=target_flight_id,
    )

    distractors: list[Flight] = []
    variations = [
        {"airline_code": _pick_other(ALL_AIRLINES, target_airline)},
        {"time_range": _pick_other(list(TIME_RANGE_HOURS.keys()), target_time)},
        {"stops": target_stops + 1},
    ]

    for overrides in variations[:num_distractors]:
        kwargs: dict[str, Any] = {
            "airline_code": overrides.get("airline_code", target_airline),
            "origin": origin,
            "destination": destination,
            "date": date,
            "time_range": overrides.get("time_range", target_time),
            "stops": overrides.get("stops", target_stops),
        }
        distractors.append(build_flight(**kwargs))

    return target, [target] + distractors


def build_booking(
    user_id: str,
    flight: Flight,
    cabin_class: str = "economy",
    booked_days_ago: int = 3,
    now: str = "2026-06-15T10:00:00",
    booking_id: str | None = None,
    has_insurance: bool | None = None,
) -> Booking:
    """Build a booking for a user on a given flight."""
    if booking_id is None:
        booking_id = _next_booking_id()
    else:
        _used_booking_ids.add(booking_id)

    user = _USERS_BY_ID.get(user_id)
    booked_at = datetime.fromisoformat(now) - timedelta(days=booked_days_ago)

    insurance = has_insurance
    if insurance is None and user:
        insurance = user.preferences.get("add_insurance", False)

    price = flight.cabin_prices.get(cabin_class, 0)

    seat_type = None
    meal_preference = None
    add_wifi = None
    add_extra_legroom = None
    if user:
        seat_type = user.preferences.get("seat_type")
        meal_preference = user.preferences.get("meal_preference")
        add_wifi = user.preferences.get("add_wifi")
        add_extra_legroom = user.preferences.get("add_extra_legroom")

    return Booking(
        booking_id=booking_id,
        user_id=user_id,
        flight_id=flight.flight_id,
        status="confirmed",
        cabin_class=cabin_class,
        seat_type=seat_type,
        meal_preference=meal_preference,
        add_wifi=add_wifi,
        add_extra_legroom=add_extra_legroom,
        add_insurance=insurance,
        price_paid=price,
        booked_at=booked_at.isoformat(),
    )


def build_hotel(
    user_id: str,
    city: str,
    check_in: str,
    check_out: str,
    room_type: str = "standard",
    nightly_rate: int = 150,
    reservation_id: str | None = None,
    booked_days_ago: int = 5,
    now: str = "2026-06-15T10:00:00",
) -> HotelReservation:
    """Build a hotel reservation."""
    if reservation_id is None:
        reservation_id = _next_hotel_id()

    nights = (datetime.fromisoformat(check_out) - datetime.fromisoformat(check_in)).days
    total_price = nightly_rate * max(nights, 1)
    booked_at = datetime.fromisoformat(now) - timedelta(days=booked_days_ago)

    return HotelReservation(
        reservation_id=reservation_id,
        user_id=user_id,
        hotel_id=None,
        hotel_name=f"{city} {'Grand Suite' if room_type == 'suite' else 'Inn'}",
        city=city,
        check_in=check_in,
        check_out=check_out,
        room_type=room_type,
        nightly_rate=nightly_rate,
        total_price=total_price,
        status="confirmed",
        booked_at=booked_at.isoformat(),
    )


def build_hotel_inventory(
    city: str,
    check_in: str,
    check_out: str,
    room_type: str = "standard",
    nightly_rate: int = 150,
    hotel_id: str | None = None,
    hotel_name: str | None = None,
) -> HotelInventoryItem:
    """Build a hotel inventory record used by search_hotels."""
    if hotel_id is None:
        hotel_id = _next_hotel_inventory_id()

    nights = (datetime.fromisoformat(check_out) - datetime.fromisoformat(check_in)).days
    total_price = nightly_rate * max(nights, 1)

    return HotelInventoryItem(
        hotel_id=hotel_id,
        hotel_name=hotel_name or f"{city} {'Grand Suite' if room_type == 'suite' else 'Inn'}",
        city=city,
        check_in=check_in,
        check_out=check_out,
        room_type=room_type,
        nightly_rate=nightly_rate,
        total_price=total_price,
    )


def build_car_rental(
    user_id: str,
    pickup_location: str,
    pickup_date: str,
    dropoff_date: str,
    car_class: str = "economy",
    daily_rate: int = 50,
    rental_id: str | None = None,
    booked_days_ago: int = 5,
    now: str = "2026-06-15T10:00:00",
) -> CarRental:
    """Build a car rental."""
    if rental_id is None:
        rental_id = _next_car_id()

    days = (datetime.fromisoformat(dropoff_date) - datetime.fromisoformat(pickup_date)).days
    total_price = daily_rate * max(days, 1)
    booked_at = datetime.fromisoformat(now) - timedelta(days=booked_days_ago)

    return CarRental(
        rental_id=rental_id,
        user_id=user_id,
        car_id=None,
        company=random.choice(["Hertz", "Enterprise", "Avis"]),
        pickup_location=pickup_location,
        dropoff_location=pickup_location,
        pickup_date=pickup_date,
        dropoff_date=dropoff_date,
        car_class=car_class,
        daily_rate=daily_rate,
        total_price=total_price,
        status="confirmed",
        insurance_included=False,
        booked_at=booked_at.isoformat(),
    )


def build_car_inventory(
    pickup_location: str,
    pickup_date: str,
    dropoff_date: str,
    car_class: str = "economy",
    daily_rate: int = 50,
    company: str | None = None,
    car_id: str | None = None,
) -> CarInventoryItem:
    """Build a car rental inventory record used by search_car_rentals."""
    if car_id is None:
        car_id = _next_car_inventory_id()

    days = (datetime.fromisoformat(dropoff_date) - datetime.fromisoformat(pickup_date)).days
    total_price = daily_rate * max(days, 1)

    return CarInventoryItem(
        car_id=car_id,
        company=company or random.choice(["Hertz", "Enterprise", "Avis"]),
        pickup_location=pickup_location,
        dropoff_location=pickup_location,
        pickup_date=pickup_date,
        dropoff_date=dropoff_date,
        car_class=car_class,
        daily_rate=daily_rate,
        total_price=total_price,
        insurance_included=False,
    )


# ---------------------------------------------------------------------------
# Environment builder
# ---------------------------------------------------------------------------


def build_task_environment(
    flights: list[Flight],
    bookings: list[Booking],
    task_data: dict[str, Any],
) -> EnvironmentData:
    """Build an isolated per-task environment snapshot from one scenario result."""
    task_data["_replay_trace"] = _normalize_replay_trace(task_data, bookings)
    _augment_user_simulator_rules(task_data)
    return EnvironmentData(
        flights=list(flights),
        bookings=list(bookings),
        users=list(USERS),
        hotel_inventory=list(task_data.get("_hotel_inventory", [])),
        hotels=list(task_data.get("_hotels", [])),
        car_inventory=list(task_data.get("_car_inventory", [])),
        car_rentals=list(task_data.get("_car_rentals", [])),
    )


def save_task(task_data: dict, tasks_dir: Path) -> None:
    """Save a task definition to JSON."""
    public_task_data = {k: v for k, v in task_data.items() if not k.startswith("_")}
    if "task_info" in public_task_data:
        raise ValueError(f"{public_task_data['task_id']} still contains legacy task_info")

    user_simulator = public_task_data.setdefault("user_simulator", {})
    task_slug = str(public_task_data.get("task_id", ""))
    if "-" in task_slug:
        task_slug = task_slug.split("-", 1)[1]
    authored_context = USER_SIM_CONTEXTS.get(task_slug)
    inline_context = user_simulator.get("user_sim_context")
    if isinstance(authored_context, str) and authored_context.strip():
        user_simulator["user_sim_context"] = authored_context.strip()
    elif isinstance(inline_context, str) and inline_context.strip():
        user_simulator["user_sim_context"] = inline_context.strip()
    else:
        raise ValueError(f"{public_task_data['task_id']} is missing authored user_sim_context")

    task_summary = TASK_SUMMARIES.get(task_slug)
    inline_summary = public_task_data.get("task_summary")
    if isinstance(task_summary, str) and task_summary.strip():
        public_task_data["task_summary"] = task_summary.strip()
    elif isinstance(inline_summary, str) and inline_summary.strip():
        public_task_data["task_summary"] = inline_summary.strip()
    else:
        raise ValueError(f"{public_task_data['task_id']} is missing authored task_summary")

    path = tasks_dir / f"{public_task_data['task_id']}.json"
    with open(path, "w") as f:
        json.dump(public_task_data, f, indent=2, ensure_ascii=False)
