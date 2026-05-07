from pathlib import Path

from domains.shopping_assistant.environment import ShoppingAssistantEnvironment
from domains.shopping_assistant.schemas import SAEnvironmentData
from domains.travel.environment import TravelEnvironment
from domains.travel.schemas import EnvironmentData
from state_bench.replay import (
    ReplayError,
    compute_replay_trace_hash,
    derive_state_requirements_from_state_diff,
    execute_replay_trace,
)
from state_bench.schemas import StateDiff


def _env(task_id: str = "13-change_flight_personal", now: str = "2026-06-15T10:00:00") -> TravelEnvironment:
    data = EnvironmentData.load(Path(f"domains/travel/task_envs/{task_id}.json"))
    return TravelEnvironment(data.deep_copy(), now)


def test_empty_trace_produces_empty_state_diff():
    _steps, diff = execute_replay_trace(_env(), [])
    assert diff == StateDiff(created={}, modified={}, deleted={})


def test_single_update_trace_produces_modified_diff():
    _steps, diff = execute_replay_trace(
        _env(),
        [{
            "name": "update_booking",
            "arguments": {
                "booking_id": "BK-1009",
                "flight_id": "WN105",
                "change_reason": "personal",
                "cabin_class": "economy",
                "seat_type": "window",
                "meal_preference": "standard",
                "add_wifi": False,
                "add_extra_legroom": False,
                "add_insurance": True,
            },
        }],
    )
    assert diff.modified["bookings"]["BK-1009"]["flight_id"]["new"] == "WN105"


def test_create_trace_produces_created_record_requirements():
    _steps, diff = execute_replay_trace(
        _env("10-book_with_points_full"),
        [{
            "name": "create_booking",
            "arguments": {
                "flight_id": "DL106",
                "user_id": "user_001",
                "cabin_class": "economy",
                "seat_type": "aisle",
                "meal_preference": "kosher",
                "add_wifi": True,
                "add_extra_legroom": True,
                "add_insurance": False,
                "payment_method": "points",
                "points_used": 50000,
            },
        }],
    )
    requirements = derive_state_requirements_from_state_diff(diff)
    created = [r for r in requirements if "match_fields" in r]
    assert len(created) == 1
    assert created[0]["match_fields"]["user_id"] == "user_001"
    assert created[0]["expected_fields"]["flight_id"] == "DL106"
    assert all(req.get("field") != "__deleted__" for req in requirements)


def test_shopping_created_record_matching_uses_semantics_not_generated_id() -> None:
    data = SAEnvironmentData.load(Path("domains/shopping_assistant/task_envs/1-recommend_college_laptop.json"))
    env = ShoppingAssistantEnvironment(data.deep_copy(), now="2026-06-12T10:00:00")
    _steps, diff = execute_replay_trace(
        env,
        [{"name": "add_to_cart", "arguments": {"customer_id": "shop_002", "product_id": "SP-1001"}}],
    )
    requirements = derive_state_requirements_from_state_diff(diff)
    created = [req for req in requirements if req.get("entity_type") == "cart_items"]
    assert len(created) == 1
    assert created[0]["match_fields"] == {
        "customer_id": "shop_002",
        "product_id": "SP-1001",
        "gift_wrap": False,
        "quantity": 1,
    }
    assert created[0]["expected_fields"] == {}


def test_replay_fails_on_tool_error():
    try:
        execute_replay_trace(_env(), [{"name": "update_booking", "arguments": {"booking_id": "DOES-NOT-EXIST"}}])
    except ReplayError as exc:
        assert "returned error" in str(exc)
    else:
        raise AssertionError("Expected ReplayError")


def test_hash_changes_with_trace():
    snapshot = EnvironmentData.load(Path("domains/travel/task_envs/13-change_flight_personal.json")).to_dict()
    h1 = compute_replay_trace_hash("1-task", "2026-06-15T10:00:00", [], snapshot)
    h2 = compute_replay_trace_hash("1-task", "2026-06-15T10:00:00", [{"name": "cancel_booking", "arguments": {"booking_id": "BK-1000", "confirm": True}}], snapshot)
    assert h1 != h2
