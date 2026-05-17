from pathlib import Path

from domains.travel.environment import TravelEnvironment
from domains.travel.schemas import EnvironmentData


def _env(task_id: str, now: str = "2026-06-15T10:00:00") -> TravelEnvironment:
    data = EnvironmentData.load(Path(f"domains/travel/task_envs/{task_id}.json"))
    return TravelEnvironment(data.deep_copy(), now)


def test_search_hotels_returns_inventory_items_without_reservation_ids():
    env = _env("8-book_with_addons")

    result = env.search_hotels({"city": "MIA", "check_in": "2026-06-20", "check_out": "2026-06-24"})

    assert result["hotels"]
    first = result["hotels"][0]
    assert "hotel_id" in first
    assert "reservation_id" not in first


def test_book_hotel_creates_reservation_visible_to_user():
    env = _env("8-book_with_addons")

    option = env.search_hotels({"city": "MIA", "check_in": "2026-06-20", "check_out": "2026-06-24", "room_type": "standard"})["hotels"][0]
    booked = env.book_hotel({"hotel_id": option["hotel_id"], "user_id": "user_003"})

    assert booked["status"] == "confirmed"
    reservation = env.get_hotel_reservation({"reservation_id": booked["reservation_id"]})
    assert reservation["user_id"] == "user_003"
    assert reservation["hotel_id"] == option["hotel_id"]

    user_res = env.get_user_reservations({"user_id": "user_003"})
    assert booked["reservation_id"] in user_res["hotel_ids"]


def test_search_car_rentals_returns_inventory_items_without_rental_ids():
    env = _env("35-cross_plan_trip_international")

    result = env.search_car_rentals({"pickup_location": "YYZ", "pickup_date": "2026-06-21", "dropoff_date": "2026-06-24"})

    assert result["car_rentals"]
    first = result["car_rentals"][0]
    assert "car_id" in first
    assert "rental_id" not in first


def test_book_car_rental_creates_rental_visible_to_user():
    env = _env("35-cross_plan_trip_international")

    option = env.search_car_rentals({"pickup_location": "YYZ", "pickup_date": "2026-06-21", "dropoff_date": "2026-06-24", "car_class": "economy"})["car_rentals"][0]
    booked = env.book_car_rental({"car_id": option["car_id"], "user_id": "user_005"})

    assert booked["status"] == "confirmed"
    rental = env.get_car_rental({"rental_id": booked["rental_id"]})
    assert rental["user_id"] == "user_005"
    assert rental["car_id"] == option["car_id"]

    user_res = env.get_user_reservations({"user_id": "user_005"})
    assert booked["rental_id"] in user_res["car_rental_ids"]
