"""Stateful travel environment with tool handlers.

The TravelEnvironment holds the in-memory database and provides tool handler
methods as bound functions. Each evaluation run gets a fresh deep copy.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from domains.travel import policies
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
from state_bench.environment import BaseEnvironment

# City name → airport code mapping for hotel/car searches.
# Allows agents to search by city name (e.g., "Toronto") instead of airport code ("YYZ").
_CITY_ALIASES: dict[str, str] = {
    "toronto": "YYZ",
    "paris": "CDG",
    "london": "LHR",
    "miami": "MIA",
    "san francisco": "SFO",
    "los angeles": "LAX",
    "denver": "DEN",
    "chicago": "ORD",
    "new york": "JFK",
    "atlanta": "ATL",
    "dallas": "DFW",
    "seattle": "SEA",
    "boston": "BOS",
}


def _normalize_city(city: str) -> str:
    """Normalize a city name or airport code to uppercase airport code."""
    return _CITY_ALIASES.get(city.lower().strip(), city).upper()


class TravelEnvironment(BaseEnvironment):
    """Stateful environment wrapping flights, bookings, users, hotels, car rentals and policy engine."""

    def __init__(self, env_data: EnvironmentData, now: str):
        super().__init__(env_data, now)
        # Index everything for fast lookup
        self.flights: dict[str, Flight] = {f.flight_id: f for f in env_data.flights}
        self.bookings: dict[str, Booking] = {b.booking_id: b for b in env_data.bookings}
        self.users: dict[str, User] = {u.user_id: u for u in env_data.users}
        self.hotel_inventory: dict[str, HotelInventoryItem] = {h.hotel_id: h for h in env_data.hotel_inventory}
        self.hotels: dict[str, HotelReservation] = {h.reservation_id: h for h in env_data.hotels}
        self.car_inventory: dict[str, CarInventoryItem] = {c.car_id: c for c in env_data.car_inventory}
        self.car_rentals: dict[str, CarRental] = {c.rental_id: c for c in env_data.car_rentals}
        # Track which bookings have had a cancellation preview (advisory — two-step still works but not enforced)
        self._cancel_previewed: set[str] = set()
        self._hotel_cancel_previewed: set[str] = set()
        self._car_cancel_previewed: set[str] = set()

    def get_full_snapshot(self) -> dict[str, dict[str, dict[str, Any]]]:
        """Return a full snapshot of all entities for assertion checking."""
        return {
            "bookings": {bid: b.to_dict() for bid, b in self.bookings.items()},
            "users": {uid: u.to_dict() for uid, u in self.users.items()},
            "hotel_inventory": {hid: h.to_dict() for hid, h in self.hotel_inventory.items()},
            "hotels": {rid: h.to_dict() for rid, h in self.hotels.items()},
            "car_inventory": {cid: c.to_dict() for cid, c in self.car_inventory.items()},
            "car_rentals": {rid: c.to_dict() for rid, c in self.car_rentals.items()},
        }

    # -------------------------------------------------------------------
    # READ tools
    # -------------------------------------------------------------------

    def search_flights(self, params: dict[str, Any]) -> dict[str, Any]:
        """Search available flights matching criteria. Returns multiple results."""
        origin = params.get("origin", "")
        destination = params.get("destination", "")
        date = params.get("date", "")
        airline = params.get("airline")
        max_stops = params.get("max_stops")
        max_price = params.get("max_price")
        time_range = params.get("time_range")

        results = []
        for f in self.flights.values():
            # Only show scheduled or delayed flights (not cancelled)
            if f.status == "cancelled":
                continue
            # Match criteria
            if origin and f.origin != origin.upper():
                continue
            if destination and f.destination != destination.upper():
                continue
            if date and not f.departure_time.startswith(date):
                continue
            if airline and f.airline_code != airline.upper():
                continue
            if max_stops is not None:
                try:
                    if f.stops > int(max_stops):
                        continue
                except (ValueError, TypeError):
                    pass
            if max_price is not None:
                try:
                    price_limit = int(max_price)
                    # Include flight if ANY cabin price is within the limit
                    if price_limit >= 0 and f.cabin_prices and min(f.cabin_prices.values()) > price_limit:
                        continue
                except (ValueError, TypeError):
                    pass
            if time_range:
                dep_hour = datetime.fromisoformat(f.departure_time).hour
                if not _matches_time_range(dep_hour, time_range):
                    continue

            # Filter out flights that depart before 'now'
            now_dt = datetime.fromisoformat(self.now)
            dep_dt = datetime.fromisoformat(f.departure_time)
            if dep_dt < now_dt:
                continue

            results.append(
                {
                    "flight_id": f.flight_id,
                    "airline_code": f.airline_code,
                    "origin": f.origin,
                    "destination": f.destination,
                    "departure_time": f.departure_time,
                    "arrival_time": f.arrival_time,
                    "duration_minutes": f.duration_minutes,
                    "stops": f.stops,
                    "cabin_prices": f.cabin_prices,
                    "status": f.status,
                    "route_type": f.route_type,
                }
            )

        # Sort by departure time
        results.sort(key=lambda x: x["departure_time"])

        if not results:
            return {"flights": [], "message": "No flights found matching your criteria."}
        return {"flights": results[:10]}  # cap at 10 results

    def get_user_details(self, params: dict[str, Any]) -> dict[str, Any]:
        """Look up a customer's account details."""
        user_id = params.get("user_id", "")
        user = self.users.get(user_id)
        if not user:
            return {"error": f"User {user_id} not found."}
        return {
            "user_id": user.user_id,
            "name": user.name,
            "email": user.email,
            "loyalty_tier": user.loyalty_tier,
            "loyalty_points": user.loyalty_points,
        }

    def get_user_reservations(self, params: dict[str, Any]) -> dict[str, Any]:
        """List all reservation IDs for a customer."""
        user_id = params.get("user_id", "")
        if user_id not in self.users:
            return {"error": f"User {user_id} not found."}

        booking_ids = [b.booking_id for b in self.bookings.values() if b.user_id == user_id]
        hotel_ids = [h.reservation_id for h in self.hotels.values() if h.user_id == user_id]
        car_rental_ids = [c.rental_id for c in self.car_rentals.values() if c.user_id == user_id]

        return {
            "user_id": user_id,
            "booking_ids": booking_ids,
            "hotel_ids": hotel_ids,
            "car_rental_ids": car_rental_ids,
        }

    def get_booking(self, params: dict[str, Any]) -> dict[str, Any]:
        """Look up a booking by ID."""
        booking_id = params.get("booking_id", "")
        booking = self.bookings.get(booking_id)
        if not booking:
            return {"error": f"Booking {booking_id} not found."}

        result = booking.to_dict()
        # Include flight route info so agent can search for alternatives
        flight = self.flights.get(booking.flight_id)
        if flight:
            result["origin"] = flight.origin
            result["destination"] = flight.destination
            result["departure_time"] = flight.departure_time
            result["route_type"] = flight.route_type
        return result

    def get_flight_status(self, params: dict[str, Any]) -> dict[str, Any]:
        """Check the status of a flight."""
        flight_id = params.get("flight_id", "")
        flight = self.flights.get(flight_id)
        if not flight:
            return {"error": f"Flight {flight_id} not found."}
        result: dict[str, Any] = {
            "flight_id": flight.flight_id,
            "status": flight.status,
            "origin": flight.origin,
            "destination": flight.destination,
            "scheduled_departure": flight.departure_time,
            "scheduled_arrival": flight.arrival_time,
        }
        if flight.status == "delayed":
            result["delay_minutes"] = flight.delay_minutes
            dep = datetime.fromisoformat(flight.departure_time)
            new_dep = dep + timedelta(minutes=flight.delay_minutes)
            result["estimated_departure"] = new_dep.isoformat()
        return result

    def get_policies(self, params: dict[str, Any]) -> dict[str, Any]:
        """Look up airline policies for cancel/change/baggage/delay/loyalty/upgrade."""
        topic = params.get("topic", "")
        cabin_class = params.get("cabin_class", "economy")
        loyalty_tier = params.get("loyalty_tier", "basic")
        route_type = params.get("route_type", "domestic")

        if topic == "cancel" or topic == "cancellation":
            rules: dict[str, str] = {
                "free_cancellation_window": (
                    "Full refund within 24 hours (domestic) or 48 hours (international) of booking"
                ),
                "basic_economy": "Not cancellable after free window (unless insured)",
                "economy_domestic": "Cancellation fee: max($50, 15% of ticket price)",
                "economy_international": "Cancellation fee: max($75, 20% of ticket price)",
                "business_domestic": "Cancellation fee: 5% of ticket price",
                "business_international": "Cancellation fee: 8% of ticket price",
                "first": "Free cancellation",
                "insurance": "Travel insurance covers cancellation regardless of cabin class",
                "route_type_matters": "Fees differ by route type (domestic vs international). Check flight route_type.",
            }
            return {
                "topic": "cancellation",
                "rules": rules,
                "applicable_cabin_class": cabin_class,
                "applicable_route_type": route_type,
            }
        elif topic == "change":
            return {
                "topic": "change",
                "rules": {
                    "free_change_window": (
                        "Free changes within 24 hours (domestic) or 48 hours (international) of booking"
                    ),
                    "basic_economy": "Not changeable after free window",
                    "economy_domestic_personal": (
                        "Domestic change fee: $75 if departure >7 days, $150 if ≤7 days. Fare difference also applies."
                    ),
                    "economy_international_personal": (
                        "International change fee: $100 if departure >7 days, $200 if ≤7 days. Fare difference also applies."
                    ),
                    "economy_medical": "Medical changes: 50% discount on standard fee (requires change_reason='medical')",
                    "economy_bereavement": (
                        "Bereavement changes: 75% discount on standard fee (requires change_reason='bereavement')"
                    ),
                    "jury_duty": "Jury duty: free change (change_reason='jury_duty')",
                    "military": "Military deployment: free change (change_reason='military')",
                    "schedule_change": "Airline schedule changes: free, no fee (change_reason='schedule_change')",
                    "weather": "Weather-related changes: free, no fee (change_reason='weather')",
                    "business": "Free changes (fare difference still applies)",
                    "first": "Free changes (fare difference still applies)",
                    "change_reason_required": (
                        "Pass change_reason parameter: 'personal', 'medical', 'bereavement', "
                        "'jury_duty', 'military', 'schedule_change', or 'weather'"
                    ),
                    "route_type_matters": "Fees differ by route type. Check flight route_type.",
                },
                "applicable_cabin_class": cabin_class,
                "applicable_route_type": route_type,
            }
        elif topic == "baggage":
            return policies.get_baggage_allowance(cabin_class, loyalty_tier)
        elif topic == "delay_compensation":
            return {
                "topic": "delay_compensation",
                "rules": {
                    "under_2_hours": "No compensation",
                    "2_to_4_hours": "$25 meal voucher",
                    "over_4_hours": "Rebooking + $25 meal voucher + hotel (if overnight)",
                    "overnight_delay": "If delay causes overnight stay, hotel voucher + $50 incidentals provided",
                },
            }
        elif topic == "loyalty" or topic == "points":
            return {
                "topic": "loyalty_points",
                "rules": {
                    "minimum_redemption": "1,000 points minimum to redeem",
                    "domestic_rate": "1 point = $0.01 (100 points = $1)",
                    "international_rate": "1 point = $0.015 (100 points = $1.50)",
                    "rounding": "Points used are rounded to the nearest 100",
                    "max_coverage": "Points can cover up to 100% of flight price",
                },
                "applicable_loyalty_tier": loyalty_tier,
                "applicable_route_type": route_type,
            }
        elif topic == "upgrade":
            return {
                "topic": "upgrade",
                "rules": {
                    "economy_to_business": "Upgrade fee = 2.5x base price minus amount already paid",
                    "business_to_first": "Upgrade fee = 1.8x base price minus amount already paid",
                    "economy_to_first": "Not available directly (must upgrade to business first)",
                    "basic_economy": "Not eligible for upgrades",
                },
                "applicable_cabin_class": cabin_class,
            }
        elif topic == "hotel_cancel":
            return {
                "topic": "hotel_cancellation",
                "rules": {
                    "standard_room_48h_plus": "Free cancellation if 48+ hours before check-in",
                    "standard_room_24_48h": "50% of first night charge if 24-48 hours before check-in",
                    "standard_room_under_24h": "Full first night charge if <24 hours before check-in",
                    "suite": "Suite bookings are non-refundable (full charge regardless of timing)",
                },
            }
        elif topic == "car_rental_cancel":
            return {
                "topic": "car_rental_cancellation",
                "rules": {
                    "24h_plus": "Free cancellation if 24+ hours before pickup",
                    "under_24h": "One day charge if <24 hours before pickup",
                    "luxury_suv_surcharge": "Luxury and SUV rentals incur an additional $50 cancellation surcharge at all times",
                },
            }
        else:
            return {"error": f"Unknown policy topic: {topic}."}

    # -------------------------------------------------------------------
    # WRITE tools
    # -------------------------------------------------------------------

    def _missing_booking_preference_field(self, params: dict[str, Any]) -> str | None:
        for field in (
            "meal_preference",
            "cabin_class",
            "seat_type",
            "add_wifi",
            "add_extra_legroom",
            "add_insurance",
        ):
            if field not in params:
                return field
        return None

    def create_booking(self, params: dict[str, Any]) -> dict[str, Any]:
        """Create a new booking with explicit persisted booking preferences.

        Required persisted booking fields: meal_preference, cabin_class, seat_type,
        add_wifi, add_extra_legroom, and add_insurance. Runtime never infers these
        from the user profile.
        """
        flight_id = params.get("flight_id", "")
        flight = self.flights.get(flight_id)
        if not flight:
            return {"error": f"Flight {flight_id} not found."}
        if flight.status == "cancelled":
            return {"error": f"Flight {flight_id} is cancelled and cannot be booked."}

        user_id = params.get("user_id", "unknown")
        user = self.users.get(user_id)

        # Require cabin_class
        cabin_class = params.get("cabin_class")
        if not cabin_class:
            available = ", ".join(sorted(flight.cabin_prices.keys())) if flight.cabin_prices else "none"
            return {"error": f"cabin_class is required. Available cabins for this flight: {available}."}
        if cabin_class not in flight.cabin_prices:
            available = ", ".join(sorted(flight.cabin_prices.keys())) if flight.cabin_prices else "none"
            return {
                "error": f"Cabin class '{cabin_class}' not available on flight {flight_id}. Available: {available}."
            }

        cabin_price = flight.cabin_prices[cabin_class]

        # Require seat_type
        seat_type = params.get("seat_type")
        if not seat_type:
            return {"error": "seat_type is required. Must be one of: window, middle, aisle."}
        if seat_type not in ("window", "middle", "aisle"):
            return {"error": f"Invalid seat_type '{seat_type}'. Must be one of: window, middle, aisle."}

        # Require payment_method
        payment_method = params.get("payment_method")
        if not payment_method:
            return {"error": "payment_method is required. Must be one of: credit_card, points, points_plus_cash."}
        if payment_method not in ("credit_card", "points", "points_plus_cash"):
            return {
                "error": f"Invalid payment_method '{payment_method}'. Must be one of: credit_card, points, points_plus_cash."
            }

        missing_pref = self._missing_booking_preference_field(params)
        if missing_pref is not None:
            return {"error": f"missing required field: {missing_pref}"}

        meal_preference = params["meal_preference"]
        add_wifi = self.parse_bool(params["add_wifi"])
        add_extra_legroom = self.parse_bool(params["add_extra_legroom"])
        add_insurance = self.parse_bool(params["add_insurance"])

        # Payment method handling (already validated above)
        points_used = 0
        cash_amount = cabin_price

        if payment_method in ("points", "points_plus_cash"):
            if not user:
                return {"error": f"User {user_id} not found. Cannot process points payment."}

            redemption = policies.check_loyalty_point_redemption(
                loyalty_tier=user.loyalty_tier,
                loyalty_points=user.loyalty_points,
                flight_price=cabin_price,
                route_type=flight.route_type,
            )
            if not redemption["eligible"]:
                return {"error": f"Points redemption not eligible: {redemption['reason']}"}

            points_used = redemption["points_used"]
            cash_amount = int(redemption["remaining_cash_payment"])

            # Require points_used for any points payment
            provided_points = params.get("points_used")
            if provided_points is None:
                return {"error": "points_used is required for points payments."}
            try:
                provided_points = int(provided_points)
            except (ValueError, TypeError):
                return {"error": f"Invalid points_used: {provided_points}. Must be an integer."}
            if provided_points != points_used:
                return {"error": "Incorrect points_used value."}

            # Reject payment_method="points" if points don't fully cover the flight
            if payment_method == "points" and cash_amount > 0:
                return {"error": "Insufficient points for full payment."}

            # Require cash_amount for points_plus_cash
            if payment_method == "points_plus_cash":
                provided_cash = params.get("cash_amount")
                if provided_cash is None:
                    return {"error": "cash_amount is required for points_plus_cash payments."}
                try:
                    provided_cash = int(provided_cash)
                except (ValueError, TypeError):
                    return {"error": f"Invalid cash_amount: {provided_cash}. Must be an integer (USD)."}
                if provided_cash != cash_amount:
                    return {"error": "Incorrect cash_amount value."}

            user.loyalty_points -= points_used

        # Extra baggage handling
        num_extra_bags = params.get("paid_checked_bags", 0)
        baggage_fee = 0
        if num_extra_bags and isinstance(num_extra_bags, int) and num_extra_bags > 0:
            # Use domestic rate as default
            baggage_fee = num_extra_bags * 35

        # Generate booking ID (handle non-numeric suffixes like BK-PR01, BK-A06a)
        existing_nums = []
        for bid in self.bookings:
            if bid.startswith("BK-"):
                try:
                    existing_nums.append(int(bid.split("-")[1]))
                except ValueError:
                    pass
        next_num = max(existing_nums, default=0) + 1
        booking_id = f"BK-{next_num:04d}"

        booking = Booking(
            booking_id=booking_id,
            user_id=user_id,
            flight_id=flight_id,
            status="confirmed",
            seat_type=params.get("seat_type"),
            cabin_class=cabin_class,
            meal_preference=meal_preference,
            add_wifi=add_wifi,
            add_extra_legroom=add_extra_legroom,
            add_insurance=add_insurance,
            price_paid=cash_amount + baggage_fee,
            payment_method=payment_method,
            points_used=points_used,
            cash_amount=cash_amount,
            booked_at=self.now,
            paid_checked_bags=num_extra_bags if isinstance(num_extra_bags, int) else 0,
        )
        self.bookings[booking_id] = booking

        result: dict[str, Any] = {
            "status": "confirmed",
            "booking_id": booking_id,
            "flight_id": flight_id,
            "cabin_class": cabin_class,
            "price": cabin_price,
            "payment_method": payment_method,
        }
        if points_used > 0:
            result["points_used"] = points_used
            result["cash_charged"] = cash_amount
        if baggage_fee > 0:
            result["baggage_fee"] = baggage_fee
            result["extra_bags"] = num_extra_bags

        return result

    def update_booking(self, params: dict[str, Any]) -> dict[str, Any]:
        """Update an existing booking. Only passed fields are changed."""
        booking_id = params.get("booking_id", "")
        booking = self.bookings.get(booking_id)
        if not booking:
            return {"error": f"Booking {booking_id} not found."}
        if booking.status == "cancelled":
            return {"error": f"Booking {booking_id} is cancelled and cannot be updated."}

        original_flight_id = booking.flight_id
        requested_cabin = params.get("cabin_class")
        flight_changed = bool(params.get("flight_id") and params.get("flight_id") != original_flight_id)

        # If changing flight, check change policy.
        new_flight_id = params.get("flight_id")
        if flight_changed and new_flight_id:
            orig_flight = self.flights.get(original_flight_id)
            current_bag_fee = booking.paid_checked_bags * 35
            baseline_departure = getattr(booking, "_change_fee_departure", None)
            baseline_route_type = getattr(booking, "_change_fee_route_type", None)
            departure_date = baseline_departure or (orig_flight.departure_time if orig_flight else "")
            route_type = baseline_route_type or (orig_flight.route_type if orig_flight else "domestic")
            baseline_flight_price = getattr(booking, "_change_base_flight_price", None)
            if baseline_flight_price is None:
                baseline_flight_price = booking.price_paid - (booking.change_fee or 0) - current_bag_fee
                booking._change_base_flight_price = baseline_flight_price

            missing_pref = self._missing_booking_preference_field(params)
            if missing_pref is not None:
                return {"error": f"missing required field: {missing_pref}"}

            # Get change reason (personal, medical, schedule_change, weather)
            change_reason = params.get("change_reason", "personal")
            policy = policies.check_change_policy(
                cabin_class=booking.cabin_class,
                booked_at=booking.booked_at,
                now=self.now,
                has_insurance=booking.add_insurance or False,
                departure_date=departure_date,
                change_reason=change_reason,
                route_type=route_type,
            )
            if not policy["eligible"]:
                return {"status": "rejected", "reason": policy["reason"]}

            new_flight = self.flights.get(new_flight_id)
            if not new_flight:
                return {"error": f"Flight {new_flight_id} not found."}
            if new_flight.status == "cancelled":
                return {"error": f"Flight {new_flight_id} is cancelled."}

            # Waive change fee only for severe delays; 120-239 minute delays still incur normal change fees.
            delay_rebooking = orig_flight is not None and orig_flight.status == "delayed" and orig_flight.delay_minutes >= 240
            change_fee = 0 if delay_rebooking else policy["fee"]

            # If the call changes both flight and cabin, price the final requested cabin directly.
            target_cabin = requested_cabin or booking.cabin_class or "economy"
            if target_cabin not in new_flight.cabin_prices:
                available = ", ".join(sorted(new_flight.cabin_prices.keys())) if new_flight.cabin_prices else "none"
                return {
                    "error": f"Cabin class '{target_cabin}' not available on flight {new_flight_id}. Available: {available}."
                }
            new_flight_price = new_flight.cabin_prices[target_cabin]

            fare_difference = new_flight_price - baseline_flight_price
            booking.flight_id = new_flight_id
            booking.cabin_class = target_cabin
            booking.price_paid = new_flight_price + change_fee + current_bag_fee
            booking.change_fee = change_fee
            booking.fare_difference = fare_difference
            # Store visible changed-trip details for auditing, and separate fee context for retroactive reason changes.
            booking._change_departure = new_flight.departure_time
            booking._change_route_type = new_flight.route_type
            booking._change_fee_departure = departure_date
            booking._change_fee_route_type = route_type

        # If change_reason is provided on an already-changed booking (flight was changed in a prior call),
        # recalculate the change fee with the new reason. This handles the case where the agent processes
        # a flight change first, then the user reveals a fee-exempt reason (e.g., jury_duty, medical).
        change_reason = params.get("change_reason")
        flight_changed_this_call = flight_changed
        if change_reason and not flight_changed_this_call and booking.change_fee is not None:
            # Use the original change context (departure date and route type from when the
            # flight was first changed) so the retroactive reason gets the same base fee tier.
            retro_departure = getattr(booking, "_change_fee_departure", None)
            retro_route = getattr(booking, "_change_fee_route_type", None)
            current_flight = self.flights.get(booking.flight_id)
            if current_flight:
                policy = policies.check_change_policy(
                    cabin_class=booking.cabin_class,
                    booked_at=booking.booked_at,
                    now=self.now,
                    has_insurance=booking.add_insurance or False,
                    departure_date=retro_departure or current_flight.departure_time,
                    change_reason=change_reason,
                    route_type=retro_route or current_flight.route_type,
                )
                old_fee = booking.change_fee
                new_fee = policy["fee"]
                if new_fee != old_fee:
                    booking.change_fee = new_fee
                    # Adjust price_paid: remove old fee, add new fee
                    booking.price_paid = booking.price_paid - old_fee + new_fee

        # If upgrading cabin class on same flight
        new_cabin = params.get("cabin_class")
        if new_cabin and new_cabin != booking.cabin_class and not flight_changed:
            flight = self.flights.get(booking.flight_id)
            if not flight:
                return {"error": f"Flight {booking.flight_id} not found."}

            # Validate target cabin exists on this flight
            if new_cabin not in flight.cabin_prices:
                available = ", ".join(sorted(flight.cabin_prices.keys())) if flight.cabin_prices else "none"
                return {
                    "error": f"Cabin class '{new_cabin}' not available on flight {booking.flight_id}. Available: {available}."
                }

            upgrade = policies.check_upgrade_eligibility(
                current_cabin=booking.cabin_class or "economy",
                target_cabin=new_cabin,
                cabin_class=booking.cabin_class,
                flight_price=booking.price_paid,
            )
            if not upgrade["eligible"]:
                return {"status": "rejected", "reason": upgrade["reason"]}

            # Use cabin_prices for upgrade fee: new cabin price - amount already paid
            new_cabin_price = flight.cabin_prices[new_cabin]
            upgrade_fee = new_cabin_price - booking.price_paid
            booking.cabin_class = new_cabin
            booking.fare_difference = upgrade_fee
            booking.price_paid = new_cabin_price

        # Update other fields if provided
        if "seat_type" in params:
            booking.seat_type = params["seat_type"]
        if "meal_preference" in params:
            booking.meal_preference = params["meal_preference"]
        if "add_wifi" in params:
            booking.add_wifi = self.parse_bool(params["add_wifi"])
        if "add_extra_legroom" in params:
            booking.add_extra_legroom = self.parse_bool(params["add_extra_legroom"])
        if "add_insurance" in params:
            booking.add_insurance = self.parse_bool(params["add_insurance"])
        if "paid_checked_bags" in params:
            num_bags = params["paid_checked_bags"]
            if isinstance(num_bags, int) and num_bags >= 0:
                old_bag_fee = booking.paid_checked_bags * 35
                booking.paid_checked_bags = num_bags
                new_bag_fee = num_bags * 35
                booking.price_paid += new_bag_fee - old_bag_fee

        # Delay compensation — validate against actual flight delay
        if "delay_compensation" in params:
            comp = params["delay_compensation"]
            valid_values = ("none", "meal_voucher", "full")
            if comp not in valid_values:
                return {"error": f"Invalid delay_compensation '{comp}'. Must be one of: {', '.join(valid_values)}."}
            flight = self.flights.get(booking.flight_id)
            if flight and flight.status == "delayed":
                expected = policies.check_delay_compensation(flight.delay_minutes)
                expected_comp = expected["compensation"]
                if comp != expected_comp:
                    return {"error": f"Incorrect delay_compensation '{comp}'."}
            booking.delay_compensation = None if comp == "none" else comp

        booking.status = "confirmed"

        result: dict[str, Any] = {
            "status": "updated",
            "booking_id": booking_id,
            "changes_applied": [k for k in params if k != "booking_id"],
            "price_paid": booking.price_paid,
        }
        if hasattr(booking, "change_fee") and booking.change_fee is not None:
            result["change_fee"] = booking.change_fee
            result["fare_difference"] = booking.fare_difference
        return result

    def cancel_booking(self, params: dict[str, Any]) -> dict[str, Any]:
        """Cancel a booking if eligible per policy.

        TWO-STEP PROCESS (advisory):
        1. First call: without confirm=true — returns a preview of cancellation terms.
        2. Second call: with confirm=true — executes the cancellation.

        If the agent skips the preview and calls with confirm=true directly, the cancellation still executes.
        """
        booking_id = params.get("booking_id", "")
        booking = self.bookings.get(booking_id)
        if not booking:
            return {"error": f"Booking {booking_id} not found."}
        if booking.status == "cancelled":
            return {"error": f"Booking {booking_id} is already cancelled."}

        # Check if the airline cancelled the flight or delay >= 240 min (free cancellation)
        flight = self.flights.get(booking.flight_id)
        airline_cancelled = flight is not None and flight.status == "cancelled"
        severe_delay = flight is not None and flight.status == "delayed" and flight.delay_minutes >= 240

        policy = policies.check_cancellation_policy(
            cabin_class=booking.cabin_class,
            booked_at=booking.booked_at,
            now=self.now,
            has_insurance=booking.add_insurance or False,
            airline_cancelled=airline_cancelled or severe_delay,
            price_paid=booking.price_paid,
            route_type=flight.route_type if flight else "domestic",
        )

        if not policy["eligible"]:
            return {"status": "rejected", "reason": policy["reason"]}

        confirm = self.parse_bool(params.get("confirm"))
        if not confirm:
            # Return preview — do NOT actually cancel
            refund = booking.price_paid - policy["fee"]
            self._cancel_previewed.add(booking_id)
            return {
                "status": "preview",
                "booking_id": booking_id,
                "cancellation_fee": policy["fee"],
                "refund_amount": refund,
                "reason": policy["reason"],
            }

        # Two-step is advisory: execute even if preview was skipped
        booking.status = "cancelled"
        booking.cancellation_fee = policy["fee"]
        refund = booking.price_paid - policy["fee"]

        # Refund loyalty points if booking was paid entirely with points. Keep cash refund at $0.
        if booking.payment_method == "points" and booking.points_used and booking.points_used > 0:
            refund = 0
            booking.points_refunded = booking.points_used

        booking.refund_amount = refund
        refund = booking.refund_amount

        # Refund loyalty points if booking was paid with points
        if booking.payment_method == "points" and booking.points_used and booking.points_used > 0:
            user = self.users.get(booking.user_id)
            if user:
                user.loyalty_points += booking.points_used

        return {
            "status": "cancelled",
            "booking_id": booking_id,
            "refund_amount": refund,
            "cancellation_fee": policy["fee"],
            "reason": policy["reason"],
        }

    # -------------------------------------------------------------------
    # Hotel tools
    # -------------------------------------------------------------------

    def search_hotels(self, params: dict[str, Any]) -> dict[str, Any]:
        """Search available hotels by city, dates, room type, and max price."""
        city = _normalize_city(params.get("city", "")) if params.get("city") else ""
        room_type = params.get("room_type")
        max_price = params.get("max_price")

        results = []
        check_in = params.get("check_in")
        check_out = params.get("check_out")

        for h in self.hotel_inventory.values():
            if city and h.city.upper() != city:
                continue
            if check_in and h.check_in != check_in:
                continue
            if check_out and h.check_out != check_out:
                continue
            if room_type and h.room_type != room_type:
                continue
            if max_price is not None:
                try:
                    price_limit = int(max_price)
                    if price_limit >= 0 and h.nightly_rate > price_limit:
                        continue
                except (ValueError, TypeError):
                    pass
            results.append(
                {
                    "hotel_id": h.hotel_id,
                    "hotel_name": h.hotel_name,
                    "city": h.city,
                    "check_in": h.check_in,
                    "check_out": h.check_out,
                    "room_type": h.room_type,
                    "nightly_rate": h.nightly_rate,
                    "total_price": h.total_price,
                }
            )

        if not results:
            return {"hotels": [], "message": "No hotels found matching your criteria."}
        return {"hotels": results[:10]}

    def book_hotel(self, params: dict[str, Any]) -> dict[str, Any]:
        """Create a hotel reservation from a searchable hotel inventory item."""
        hotel_id = params.get("hotel_id", "")
        hotel = self.hotel_inventory.get(hotel_id)
        if not hotel:
            return {"error": f"Hotel option {hotel_id} not found."}

        user_id = params.get("user_id", "")
        if user_id not in self.users:
            return {"error": f"User {user_id} not found."}

        existing_nums = []
        for rid in self.hotels:
            if rid.startswith("HR-"):
                try:
                    existing_nums.append(int(rid.split("-")[1]))
                except ValueError:
                    pass
        next_num = max(existing_nums, default=0) + 1
        reservation_id = f"HR-{next_num:04d}"

        reservation = HotelReservation(
            reservation_id=reservation_id,
            user_id=user_id,
            hotel_id=hotel.hotel_id,
            hotel_name=hotel.hotel_name,
            city=hotel.city,
            check_in=hotel.check_in,
            check_out=hotel.check_out,
            room_type=hotel.room_type,
            nightly_rate=hotel.nightly_rate,
            total_price=hotel.total_price,
            status="confirmed",
            booked_at=self.now,
        )
        self.hotels[reservation_id] = reservation

        return {
            "status": "confirmed",
            "reservation_id": reservation_id,
            "hotel_id": hotel.hotel_id,
            "hotel_name": hotel.hotel_name,
            "total_price": hotel.total_price,
            "room_type": hotel.room_type,
        }

    def get_hotel_reservation(self, params: dict[str, Any]) -> dict[str, Any]:
        """Look up a hotel reservation by ID."""
        reservation_id = params.get("reservation_id", "")
        hotel = self.hotels.get(reservation_id)
        if not hotel:
            return {"error": f"Hotel reservation {reservation_id} not found."}
        return hotel.to_dict()

    def cancel_hotel_reservation(self, params: dict[str, Any]) -> dict[str, Any]:
        """Cancel a hotel reservation. Two-step: preview then confirm (advisory — skipping preview still executes)."""
        reservation_id = params.get("reservation_id", "")
        hotel = self.hotels.get(reservation_id)
        if not hotel:
            return {"error": f"Hotel reservation {reservation_id} not found."}
        if hotel.status == "cancelled":
            return {"error": f"Hotel reservation {reservation_id} is already cancelled."}

        policy = policies.check_hotel_cancellation_policy(
            room_type=hotel.room_type,
            check_in=hotel.check_in,
            now=self.now,
            nightly_rate=hotel.nightly_rate,
            total_price=hotel.total_price,
        )

        confirm = self.parse_bool(params.get("confirm"))
        if not confirm:
            self._hotel_cancel_previewed.add(reservation_id)
            return {
                "status": "preview",
                "reservation_id": reservation_id,
                "cancellation_fee": policy["fee"],
                "refund_amount": policy["refund"],
                "reason": policy["reason"],
            }

        if reservation_id not in self._hotel_cancel_previewed:
            # Advisory: log that preview was skipped but proceed anyway
            pass

        hotel.status = "cancelled"
        hotel.cancellation_fee = policy["fee"]
        hotel.refund_amount = policy["refund"]

        return {
            "status": "cancelled",
            "reservation_id": reservation_id,
            "cancellation_fee": policy["fee"],
            "refund_amount": policy["refund"],
            "reason": policy["reason"],
        }

    # -------------------------------------------------------------------
    # Car rental tools
    # -------------------------------------------------------------------

    def search_car_rentals(self, params: dict[str, Any]) -> dict[str, Any]:
        """Search available car rentals by location, dates, class, and max daily rate."""
        pickup_location = _normalize_city(params.get("pickup_location", "")) if params.get("pickup_location") else ""
        car_class = params.get("car_class")
        max_daily_rate = params.get("max_daily_rate")

        results = []
        pickup_date = params.get("pickup_date")
        dropoff_date = params.get("dropoff_date")

        for c in self.car_inventory.values():
            if pickup_location and c.pickup_location.upper() != pickup_location:
                continue
            if pickup_date and c.pickup_date != pickup_date:
                continue
            if dropoff_date and c.dropoff_date != dropoff_date:
                continue
            if car_class and c.car_class != car_class:
                continue
            if max_daily_rate is not None:
                try:
                    rate_limit = int(max_daily_rate)
                    if rate_limit >= 0 and c.daily_rate > rate_limit:
                        continue
                except (ValueError, TypeError):
                    pass
            results.append(
                {
                    "car_id": c.car_id,
                    "company": c.company,
                    "pickup_location": c.pickup_location,
                    "dropoff_location": c.dropoff_location,
                    "pickup_date": c.pickup_date,
                    "dropoff_date": c.dropoff_date,
                    "car_class": c.car_class,
                    "daily_rate": c.daily_rate,
                    "total_price": c.total_price,
                    "insurance_included": c.insurance_included,
                }
            )

        if not results:
            return {"car_rentals": [], "message": "No car rentals found matching your criteria."}
        return {"car_rentals": results[:10]}

    def book_car_rental(self, params: dict[str, Any]) -> dict[str, Any]:
        """Create a car rental reservation from searchable car inventory."""
        car_id = params.get("car_id", "")
        car = self.car_inventory.get(car_id)
        if not car:
            return {"error": f"Car rental option {car_id} not found."}

        user_id = params.get("user_id", "")
        if user_id not in self.users:
            return {"error": f"User {user_id} not found."}

        existing_nums = []
        for rid in self.car_rentals:
            if rid.startswith("CR-"):
                try:
                    existing_nums.append(int(rid.split("-")[1]))
                except ValueError:
                    pass
        next_num = max(existing_nums, default=0) + 1
        rental_id = f"CR-{next_num:04d}"

        rental = CarRental(
            rental_id=rental_id,
            user_id=user_id,
            car_id=car.car_id,
            company=car.company,
            pickup_location=car.pickup_location,
            dropoff_location=car.dropoff_location,
            pickup_date=car.pickup_date,
            dropoff_date=car.dropoff_date,
            car_class=car.car_class,
            daily_rate=car.daily_rate,
            total_price=car.total_price,
            status="confirmed",
            insurance_included=car.insurance_included,
            booked_at=self.now,
        )
        self.car_rentals[rental_id] = rental

        return {
            "status": "confirmed",
            "rental_id": rental_id,
            "car_id": car.car_id,
            "company": car.company,
            "car_class": car.car_class,
            "total_price": car.total_price,
        }

    def get_car_rental(self, params: dict[str, Any]) -> dict[str, Any]:
        """Look up a car rental by ID."""
        rental_id = params.get("rental_id", "")
        car = self.car_rentals.get(rental_id)
        if not car:
            return {"error": f"Car rental {rental_id} not found."}
        return car.to_dict()

    def cancel_car_rental(self, params: dict[str, Any]) -> dict[str, Any]:
        """Cancel a car rental. Two-step: preview then confirm (advisory — skipping preview still executes)."""
        rental_id = params.get("rental_id", "")
        car = self.car_rentals.get(rental_id)
        if not car:
            return {"error": f"Car rental {rental_id} not found."}
        if car.status == "cancelled":
            return {"error": f"Car rental {rental_id} is already cancelled."}

        policy = policies.check_car_rental_cancellation_policy(
            car_class=car.car_class,
            pickup_date=car.pickup_date,
            now=self.now,
            daily_rate=car.daily_rate,
            total_price=car.total_price,
        )

        confirm = self.parse_bool(params.get("confirm"))
        if not confirm:
            self._car_cancel_previewed.add(rental_id)
            return {
                "status": "preview",
                "rental_id": rental_id,
                "cancellation_fee": policy["fee"],
                "refund_amount": policy["refund"],
                "reason": policy["reason"],
            }

        if rental_id not in self._car_cancel_previewed:
            # Advisory: log that preview was skipped but proceed anyway
            pass

        car.status = "cancelled"
        car.cancellation_fee = policy["fee"]
        car.refund_amount = policy["refund"]

        return {
            "status": "cancelled",
            "rental_id": rental_id,
            "cancellation_fee": policy["fee"],
            "refund_amount": policy["refund"],
            "reason": policy["reason"],
        }

    # -------------------------------------------------------------------
    # Tool handler registry
    # -------------------------------------------------------------------

    @property
    def tool_handlers(self) -> dict[str, Any]:
        return {
            "search_flights": self.search_flights,
            "get_user_details": self.get_user_details,
            "get_user_reservations": self.get_user_reservations,
            "get_booking": self.get_booking,
            "get_flight_status": self.get_flight_status,
            "get_policies": self.get_policies,
            "create_booking": self.create_booking,
            "update_booking": self.update_booking,
            "cancel_booking": self.cancel_booking,
            "search_hotels": self.search_hotels,
            "book_hotel": self.book_hotel,
            "get_hotel_reservation": self.get_hotel_reservation,
            "cancel_hotel_reservation": self.cancel_hotel_reservation,
            "search_car_rentals": self.search_car_rentals,
            "book_car_rental": self.book_car_rental,
            "get_car_rental": self.get_car_rental,
            "cancel_car_rental": self.cancel_car_rental,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TIME_RANGES = {
    "early_morning": (5, 8),
    "morning": (8, 12),
    "afternoon": (12, 17),
    "evening": (17, 21),
    "red_eye": (21, 5),
}


def _matches_time_range(hour: int, time_range: str) -> bool:
    bounds = _TIME_RANGES.get(time_range)
    if not bounds:
        return True
    start, end = bounds
    if start < end:
        return start <= hour < end
    else:  # wraps around midnight
        return hour >= start or hour < end
