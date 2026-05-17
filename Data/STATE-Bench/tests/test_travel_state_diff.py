import json
from pathlib import Path

from domains.travel.environment import TravelEnvironment
from domains.travel.schemas import EnvironmentData
from state_bench.schemas import StateDiff


def _env(task_id: str = "13-change_flight_personal", now: str = "2026-06-15T10:00:00") -> TravelEnvironment:
    data = EnvironmentData.load(Path(f"domains/travel/task_envs/{task_id}.json"))
    return TravelEnvironment(data.deep_copy(), now)


def test_state_diff_excludes_runtime_change_helper_fields():
    env = _env("13-change_flight_personal")

    before = env.get_full_snapshot()
    result = env.update_booking(
        {
            "booking_id": "BK-1009",
            "flight_id": "WN105",
            "change_reason": "personal",
            "cabin_class": "economy",
            "seat_type": "window",
            "meal_preference": "standard",
            "add_wifi": False,
            "add_extra_legroom": False,
            "add_insurance": True,
        }
    )
    after = env.get_full_snapshot()
    diff = StateDiff.compute(before, after)

    assert result["status"] == "updated"
    assert hasattr(env.bookings["BK-1009"], "_change_departure")

    changes = diff.modified["bookings"]["BK-1009"]
    assert "flight_id" in changes
    assert "change_fee" in changes
    assert "fare_difference" in changes
    assert "price_paid" in changes
    assert all(not field.startswith("_") for field in changes)


def test_update_booking_delay_compensation_none_does_not_create_state_write():
    env = _env("13-change_flight_personal")

    before = env.get_full_snapshot()
    result = env.update_booking(
        {
            "booking_id": "BK-1009",
            "flight_id": "WN105",
            "change_reason": "personal",
            "cabin_class": "economy",
            "seat_type": "window",
            "meal_preference": "standard",
            "add_wifi": False,
            "add_extra_legroom": False,
            "add_insurance": True,
            "delay_compensation": "none",
        }
    )
    after = env.get_full_snapshot()
    diff = StateDiff.compute(before, after)

    assert result["status"] == "updated"
    changes = diff.modified["bookings"]["BK-1009"]
    assert "delay_compensation" not in changes
    assert env.bookings["BK-1009"].delay_compensation is None


def test_update_booking_delay_compensation_full_is_recorded_when_applicable():
    env = _env("29-cascade_delay_rebook_upgrade")

    before = env.get_full_snapshot()
    result = env.update_booking(
        {
            "booking_id": "BK-MS04",
            "delay_compensation": "full",
        }
    )
    after = env.get_full_snapshot()
    diff = StateDiff.compute(before, after)

    assert result["status"] == "updated"
    changes = diff.modified["bookings"]["BK-MS04"]
    assert changes["delay_compensation"] == {"old": None, "new": "full"}
    assert env.bookings["BK-MS04"].delay_compensation == "full"

def test_ms04_replay_target_matches_within_budget_delta_upgrade_path() -> None:
    from domains.travel.task_registry.scenarios.trip_management import scenario_MS04

    flights, bookings, task_data = scenario_MS04()
    booking = bookings[0]
    replay_steps = task_data["_replay_trace"]

    assert replay_steps[0]["arguments"]["delay_compensation"] == "full"
    target_flight_id = replay_steps[1]["arguments"]["flight_id"]
    assert replay_steps[1]["arguments"]["cabin_class"] == "business"

    original_flight = next(f for f in flights if f.flight_id == booking.flight_id)
    target_flight = next(f for f in flights if f.flight_id == target_flight_id)

    assert target_flight.airline_code == "DL"
    assert target_flight.stops == 0
    assert target_flight.departure_time.startswith("2026-06-15T17:")
    assert target_flight.cabin_prices["economy"] == 264
    assert target_flight.cabin_prices["business"] == 617
    assert target_flight.cabin_prices["business"] - original_flight.cabin_prices["economy"] == 317


def _created_booking_requirement(task: dict, user_id: str) -> dict:
    for requirement in task["state_requirements"]:
        if requirement.get("entity_type") != "bookings":
            continue
        expected_fields = requirement.get("expected_fields")
        if expected_fields and expected_fields.get("user_id") == user_id:
            return requirement
    raise AssertionError(f"No created booking requirement found for {user_id}")


def test_booking_task_ground_truth_uses_profile_defaults_for_inherited_fields():
    env_data = EnvironmentData.load(Path("domains/travel/task_envs/10-book_with_points_full.json"))
    users = {user.user_id: user for user in env_data.users}

    task10 = json.loads(Path("domains/travel/tasks/10-book_with_points_full.json").read_text())
    expected10 = _created_booking_requirement(task10, "user_001")["expected_fields"]
    user10_prefs = users["user_001"].preferences

    assert expected10["meal_preference"] == user10_prefs["meal_preference"]
    assert expected10["add_wifi"] == user10_prefs["add_wifi"]
    assert expected10["add_extra_legroom"] == user10_prefs["add_extra_legroom"]

    task11 = json.loads(Path("domains/travel/tasks/11-book_with_points_partial.json").read_text())
    expected11 = _created_booking_requirement(task11, "user_004")["expected_fields"]
    user11_prefs = users["user_004"].preferences

    assert expected11["meal_preference"] == user11_prefs["meal_preference"]
    assert expected11["add_wifi"] == user11_prefs["add_wifi"]
    assert expected11["add_extra_legroom"] == user11_prefs["add_extra_legroom"]

def test_no_write_travel_tasks_define_explicit_empty_state_requirements():
    task_paths = [
        "domains/travel/tasks/16-policy_insurance_cancel_not_change.json",
        "domains/travel/tasks/17-policy_basic_economy_restrictions.json",
        "domains/travel/tasks/18-policy_24h_vs_48h_window.json",
        "domains/travel/tasks/22-policy_upgrade_path_blocked.json",
        "domains/travel/tasks/25-policy_baggage_loyalty_interaction.json",
        "domains/travel/tasks/36-info_baggage_allowance.json",
        "domains/travel/tasks/37-info_baggage_basic_economy.json",
        "domains/travel/tasks/38-info_cancel_policy_explanation.json",
        "domains/travel/tasks/39-info_change_vs_cancel_tradeoff.json",
        "domains/travel/tasks/40-info_loyalty_points_value.json",
        "domains/travel/tasks/41-info_upgrade_options.json",
        "domains/travel/tasks/43-info_delay_rights.json",
        "domains/travel/tasks/45-adversarial_demand_unauthorized_comp.json",
        "domains/travel/tasks/50-adversarial_mind_change.json",
    ]

    for task_path in task_paths:
        task = json.loads(Path(task_path).read_text())
        assert task["state_requirements"] == [], task_path


def test_selected_state_requirement_tasks_match_replay_derived_requirements():
    from domains.travel import task_registry as registry
    from state_bench.domain import get_domain_config
    from state_bench.replay import derive_state_requirements_from_state_diff, execute_replay_trace

    selected_task_ids = {
        "26-cascade_cancel_rebook_domestic",
        "27-cascade_cancel_rebook_points",
        "28-cascade_cancel_rebook_international",
        "29-cascade_delay_rebook_upgrade",
        "33-cascade_change_and_add_bags",
        "46-adversarial_impatient_booking",
        "52-challenge_insurance_cancel_rebook",
        "53-challenge_bereavement_change_vs_cancel",
        "54-challenge_points_dual_rate",
        "55-challenge_triple_fee_stack",
        "58-challenge_sunk_cost_change_fee",
        "63-challenge_canada_international",
        "69-challenge_insurance_split_strategy",
        "70-challenge_sequential_points_depletion",
        "71-challenge_bereavement_one_booking_only",
        "75-challenge_negative_fare_diff_no_refund",
        "76-challenge_triple_policy_interaction",
        "88-challenge_change_vs_cancel_cheaper_flight",
    }

    registry.reset_counters()
    results = [scenario_fn() for scenario_fn in registry.ALL_SCENARIOS]
    domain = get_domain_config("travel")

    for idx, result in enumerate(results, start=1):
        flights, bookings, task_data = result
        task_id = f"{idx}-{task_data['task_id']}"
        if task_id not in selected_task_ids:
            continue
        env_data = registry.build_task_environment(flights, bookings, task_data)
        env = domain.environment_class(env_data.deep_copy(), now=task_data.get("now", "2026-06-15T10:00:00"))
        replay_trace = task_data.get("_replay_trace", [])
        _steps, diff = execute_replay_trace(env, replay_trace)
        derived = derive_state_requirements_from_state_diff(
            diff,
            replay_trace=replay_trace,
            post_snapshot=env.get_full_snapshot(),
        )
        task = json.loads(Path(f"domains/travel/tasks/{task_id}.json").read_text())
        assert task["state_requirements"] == derived, task_id


def test_update_booking_reprices_from_original_flight_baseline_not_intermediate_total():
    from domains.travel.task_registry.scenarios.trip_planning import scenario_MS08

    env = _env("33-cascade_change_and_add_bags")
    flights, bookings, task_data = scenario_MS08()
    target_flight_id = task_data["_replay_trace"][0]["arguments"]["flight_id"]
    original_flight_id = bookings[0].flight_id
    original_flight = next(f for f in flights if f.flight_id == original_flight_id)
    target_flight = next(f for f in flights if f.flight_id == target_flight_id)

    first = env.update_booking(
        {
            "booking_id": "BK-MS08",
            "flight_id": target_flight_id,
            "change_reason": "medical",
            "cabin_class": "economy",
            "seat_type": "window",
            "meal_preference": "vegetarian",
            "add_wifi": False,
            "add_extra_legroom": False,
            "add_insurance": False,
            "delay_compensation": "none",
        }
    )
    assert first["status"] == "updated"
    assert first["fare_difference"] == target_flight.cabin_prices["economy"] - original_flight.cabin_prices["economy"]
    assert first["price_paid"] == target_flight.cabin_prices["economy"] + 75

    second = env.update_booking(
        {
            "booking_id": "BK-MS08",
            "paid_checked_bags": 2,
        }
    )

    assert second["status"] == "updated"
    assert second["price_paid"] == target_flight.cabin_prices["economy"] + 75 + 70
    booking = env.bookings["BK-MS08"]
    assert booking.flight_id == target_flight_id
    assert booking.change_fee == 75
    assert booking.fare_difference == target_flight.cabin_prices["economy"] - original_flight.cabin_prices["economy"]
    assert booking.price_paid == target_flight.cabin_prices["economy"] + 75 + 70


def test_challenge_53_replay_target_is_cheapest_june_28_paris_change() -> None:
    from domains.travel.task_registry.scenarios.challenge_fee_math import build_challenge_3

    flights, bookings, task_data = build_challenge_3()
    booking = bookings[0]
    replay_target = task_data["_replay_trace"][0]["arguments"]["flight_id"]
    current_flight = next(f for f in flights if f.flight_id == booking.flight_id)
    candidates = [
        f
        for f in flights
        if f.origin == current_flight.origin
        and f.destination == current_flight.destination
        and f.departure_time.startswith("2026-06-28")
    ]
    target = next(f for f in candidates if f.flight_id == replay_target)
    others = [f for f in candidates if f.flight_id != replay_target]

    assert target.cabin_prices["economy"] == 820
    assert others
    assert min(f.cabin_prices["economy"] for f in others) > target.cabin_prices["economy"]


def test_challenge_56_replay_target_is_cheapest_june_24_replacement() -> None:
    from domains.travel.task_registry.scenarios.challenge_fee_math import build_challenge_6

    flights, bookings, task_data = build_challenge_6()
    booking = bookings[0]
    replay_target = task_data["_replay_trace"][0]["arguments"]["flight_id"]
    current_flight = next(f for f in flights if f.flight_id == booking.flight_id)
    candidates = [
        f
        for f in flights
        if f.origin == current_flight.origin
        and f.destination == current_flight.destination
        and f.departure_time.startswith("2026-06-24")
    ]
    target = next(f for f in candidates if f.flight_id == replay_target)
    others = [f for f in candidates if f.flight_id != replay_target]

    assert target.cabin_prices["economy"] == 780
    assert others
    assert min(f.cabin_prices["economy"] for f in others) > target.cabin_prices["economy"]


def test_challenge_58_replay_inventory_has_no_cheaper_direct_change_than_intended_option():
    from domains.travel.task_registry.scenarios.challenge_fee_math import build_challenge_8

    flights, bookings, task_data = build_challenge_8()
    replay_target = task_data['_replay_trace'][1]['arguments']['flight_id']
    booking = bookings[0]
    current_flight = next(f for f in flights if f.flight_id == booking.flight_id)
    same_day_same_route = [
        f
        for f in flights
        if f.origin == current_flight.origin
        and f.destination == current_flight.destination
        and f.departure_time.startswith('2026-06-21')
    ]

    rebook_target = next(f for f in same_day_same_route if f.flight_id == replay_target)
    change_candidates = [f for f in same_day_same_route if f.flight_id != replay_target]

    assert rebook_target.cabin_prices['economy'] == 750
    assert min(f.cabin_prices['economy'] for f in change_candidates) == 850




def test_create_booking_requires_all_persisted_preference_fields() -> None:
    env = _env("7-book_simple_domestic")

    result = env.create_booking(
        {
            "flight_id": "B6200",
            "user_id": "user_005",
            "cabin_class": "economy",
            "seat_type": "aisle",
            "payment_method": "credit_card",
            "meal_preference": "vegan",
            "add_wifi": True,
            "add_extra_legroom": False,
        }
    )

    assert result == {"error": "missing required field: add_insurance"}


def test_update_booking_flight_change_requires_all_persisted_preference_fields() -> None:
    env = _env("13-change_flight_personal")

    result = env.update_booking(
        {
            "booking_id": "BK-1009",
            "flight_id": "WN105",
            "change_reason": "personal",
            "cabin_class": "economy",
            "seat_type": "window",
            "meal_preference": "standard",
            "add_wifi": False,
            "add_extra_legroom": False,
        }
    )

    assert result == {"error": "missing required field: add_insurance"}


def test_same_flight_update_remains_partial_without_required_preference_bundle() -> None:
    env = _env("13-change_flight_personal")

    result = env.update_booking({"booking_id": "BK-1009", "seat_type": "aisle"})

    assert result["status"] == "updated"
    assert env.bookings["BK-1009"].seat_type == "aisle"


def test_replay_trace_preserves_explicit_scenario_authored_booking_preferences() -> None:
    from domains.travel.task_registry._builders import build_task_environment
    from domains.travel.task_registry.scenarios.booking import scenario_P07

    flights, bookings, task_data = scenario_P07()
    task_data["_replay_trace"][0]["arguments"]["add_wifi"] = False

    build_task_environment(flights, bookings, task_data)

    assert task_data["_replay_trace"][0]["arguments"]["add_wifi"] is False


def test_replay_trace_create_booking_backfills_missing_preferences_from_user_profile() -> None:
    from domains.travel.task_registry._builders import build_task_environment
    from domains.travel.task_registry.scenarios.booking import scenario_P07

    flights, bookings, task_data = scenario_P07()
    task_data["_replay_trace"][0]["arguments"].pop("add_wifi", None)
    task_data["_replay_trace"][0]["arguments"].pop("add_extra_legroom", None)
    task_data["_replay_trace"][0]["arguments"].pop("add_insurance", None)

    build_task_environment(flights, bookings, task_data)

    assert task_data["_replay_trace"][0]["arguments"]["add_wifi"] is True
    assert task_data["_replay_trace"][0]["arguments"]["add_extra_legroom"] is False
    assert task_data["_replay_trace"][0]["arguments"]["add_insurance"] is False


def test_replay_trace_flight_change_backfills_missing_preferences_from_existing_booking() -> None:
    from domains.travel.task_registry._builders import build_task_environment
    from domains.travel.task_registry.scenarios.changes import scenario_P13

    flights, bookings, task_data = scenario_P13()
    step_args = task_data["_replay_trace"][0]["arguments"]
    step_args.pop("cabin_class", None)
    step_args.pop("seat_type", None)
    step_args.pop("meal_preference", None)
    step_args.pop("add_wifi", None)
    step_args.pop("add_extra_legroom", None)
    step_args.pop("add_insurance", None)

    build_task_environment(flights, bookings, task_data)

    booking = bookings[0]
    normalized_args = task_data["_replay_trace"][0]["arguments"]
    assert normalized_args["cabin_class"] == booking.cabin_class
    assert normalized_args["seat_type"] == booking.seat_type
    assert normalized_args["meal_preference"] == booking.meal_preference
    assert normalized_args["add_wifi"] == booking.add_wifi
    assert normalized_args["add_extra_legroom"] == booking.add_extra_legroom
    assert normalized_args["add_insurance"] == booking.add_insurance


def test_replay_trace_flight_change_inherits_existing_booking_cabin_class() -> None:
    from domains.travel.task_registry._builders import build_task_environment
    from domains.travel.task_registry.scenarios.changes import scenario_P13

    flights, bookings, task_data = scenario_P13()
    task_data["_replay_trace"][0]["arguments"].pop("cabin_class", None)

    build_task_environment(flights, bookings, task_data)

    assert task_data["_replay_trace"][0]["arguments"]["cabin_class"] == bookings[0].cabin_class


def test_search_intent_derives_known_info_and_disclosure_rule() -> None:
    from domains.travel.task_registry._builders import build_task_environment
    from domains.travel.task_registry.scenarios.booking import scenario_P07

    flights, bookings, task_data = scenario_P07()
    build_task_environment(flights, bookings, task_data)

    sim = task_data["user_simulator"]
    assert "Wants economy class" in sim["known_info"]
    assert "Prefers B6 airline, afternoon departure, nonstop" in sim["known_info"]
    assert "When asked about flight preferences, say economy class, B6 airline, afternoon departure, nonstop." in sim["task_rules"]


def test_simulator_prompt_uses_task_context_for_search_preferences_not_identity_defaults() -> None:
    import json

    from domains.travel.simulator import build_simulator_prompt
    from domains.travel.task_registry._builders import build_task_environment, save_task
    from domains.travel.task_registry.scenarios.booking import scenario_P07
    from state_bench.schemas import TaskDefinition

    flights, bookings, task_data = scenario_P07()
    env_data = build_task_environment(flights, bookings, task_data)
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as tmpdir:
        save_task(task_data, Path(tmpdir))
        task_path = Path(tmpdir) / f"{task_data['task_id']}.json"
        task = TaskDefinition.from_dict(json.loads(task_path.read_text()))
    prompt = build_simulator_prompt(task, env_data, task.user_id)

    assert "## Identity" in prompt
    assert "## Task Context" in prompt
    assert "## Base Rules" in prompt
    assert "## Task-Specific Rules" in prompt
    assert "default to polite and cooperative if not specified" not in prompt
    assert "- Airline:" not in prompt
    assert "- Cabin class:" not in prompt
    assert "- Time:" not in prompt
    assert "- Max stops:" not in prompt
    assert "Task-specific search preferences such as airline, cabin class, departure time, and max stops are provided in the task context below" in prompt
    assert "Prefers B6 airline, afternoon departure, nonstop" in prompt



def test_cross_plan_trip_replay_uses_user_profile_booking_preferences() -> None:
    from domains.travel.task_registry._builders import _USERS_BY_ID, build_task_environment
    from domains.travel.task_registry.scenarios.trip_planning import scenario_MS09, scenario_MS10

    for scenario_fn, user_id in ((scenario_MS09, "user_004"), (scenario_MS10, "user_005")):
        flights, bookings, task_data = scenario_fn()
        build_task_environment(flights, bookings, task_data)
        prefs = _USERS_BY_ID[user_id].preferences
        create_steps = [step for step in task_data["_replay_trace"] if step.get("name") == "create_booking"]
        assert create_steps, scenario_fn.__name__
        for step in create_steps:
            args = step["arguments"]
            assert args["seat_type"] == prefs["seat_type"]
            assert args["meal_preference"] == prefs["meal_preference"]
            assert args["add_wifi"] == prefs["add_wifi"]
            assert args["add_extra_legroom"] == prefs["add_extra_legroom"]
            assert args["add_insurance"] == prefs["add_insurance"]


def test_existing_bookings_match_user_profile_by_default_in_canada_international() -> None:
    from domains.travel.task_registry._builders import _USERS_BY_ID
    from domains.travel.task_registry.scenarios.challenge_discounts import build_challenge_13

    _flights, bookings, _task_data = build_challenge_13()
    prefs = _USERS_BY_ID["user_004"].preferences
    for booking in bookings:
        assert booking.add_insurance == prefs["add_insurance"]


def test_travel_generation_audit_catches_stale_hotel_reservation_reference() -> None:
    from domains.travel.generate_tasks import _audit_task_references
    from domains.travel.task_registry._builders import build_task_environment
    from domains.travel.task_registry.scenarios.trip_management import scenario_MS01

    flights, bookings, task_data = scenario_MS01()
    env_data = build_task_environment(flights, bookings, task_data)
    hotel = env_data.hotels[0]
    task_data["task_id"] = "test-stale-hotel-id"
    task_data["task_requirements"][0]["requirement"] = task_data["task_requirements"][0]["requirement"].replace(
        hotel.reservation_id, "HR-9999"
    )

    issues = _audit_task_references(task_data, env_data)

    assert any("task_requirements[1].requirement references unknown hotel reservation: HR-9999" == issue for issue in issues)

