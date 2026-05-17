import json
import tempfile
from pathlib import Path

from domains.shopping_assistant.generate_tasks import get_generation_adapter
from state_bench.domain import get_domain_config
from state_bench.generation import finalize_generated_task


def test_shopping_adapter_enumerates_all_scenarios() -> None:
    from domains.shopping_assistant import task_registry as registry

    adapter = get_generation_adapter(registry)
    indexed = adapter.enumerate({1, 10, 81})
    assert [idx for idx, _ in indexed] == [1, 10, 81]


def test_shopping_task_registry_covers_all_checked_in_tasks() -> None:
    import importlib

    from domains.shopping_assistant import task_registry as registry

    expected = []
    for path in Path("domains/shopping_assistant/tasks").glob("*.json"):
        idx = int(path.stem.split("-", 1)[0])
        expected.append((idx, path.stem))
    expected.sort()

    actual = []
    for idx, module_path in enumerate(registry.ALL_SCENARIOS, start=1):
        mod = importlib.import_module(module_path)
        task_json = getattr(mod, "TASK_JSON")
        actual.append((idx, f"{idx}-{task_json['task_id'].split('-', 1)[1]}"))

    assert actual == expected


def test_shopping_pilot_task_derives_replay_requirements() -> None:
    from domains.shopping_assistant import task_registry as registry

    adapter = get_generation_adapter(registry)
    idx, scenario = adapter.enumerate({1})[0]
    built = adapter.build(idx, scenario)
    finalized = finalize_generated_task(get_domain_config("shopping_assistant"), built)
    assert finalized.task_data["_replay_trace"]
    assert finalized.task_data["task_type"] == "product_search_discovery"
    assert finalized.task_data["replay_trace_hash"]
    assert finalized.task_data["state_requirements"]
    created = [req for req in finalized.task_data["state_requirements"] if req["entity_type"] == "cart_items"]
    assert created
    assert created[0]["match_fields"]["customer_id"] == "shop_002"
    assert created[0]["match_fields"]["product_id"] == "SP-1001"
    legacy = built.task_data["_legacy_state_requirements"]
    current_keys = {(req.get("entity_type"), str(req)) for req in finalized.task_data["state_requirements"]}
    for req in legacy:
        assert any(item[0] == req.get("entity_type") for item in current_keys)


def test_shopping_task_93_records_reviewed_legacy_customer_balance_exception() -> None:
    from domains.shopping_assistant import task_registry as registry

    adapter = get_generation_adapter(registry)
    idx, scenario = adapter.enumerate({93})[0]
    built = adapter.build(idx, scenario)
    finalized = finalize_generated_task(get_domain_config("shopping_assistant"), built)

    assert finalized.task_data["_replay_trace"] == [
        {"name": "update_cart_item", "arguments": {"customer_id": "shop_005", "product_id": "SP-1002", "quantity": 1}},
        {"name": "update_cart_item", "arguments": {"customer_id": "shop_005", "product_id": "SP-1002", "quantity": 2}},
    ]
    assert {
        "entity_type": "cart_items",
        "match_fields": {
            "cart_item_id": "CI-A1",
            "customer_id": "shop_005",
            "product_id": "SP-1002",
        },
        "expected_fields": {
            "quantity": 2,
            "gift_wrap": False,
        },
    } in finalized.task_data["state_requirements"]
    assert {"entity_type": "carts", "record_key": "CART-shop_005", "field": "subtotal", "expected_value": 1998} in finalized.task_data["state_requirements"]
    assert {"entity_type": "carts", "record_key": "CART-shop_005", "field": "loyalty_discount", "expected_value": 499} in finalized.task_data["state_requirements"]
    assert {"entity_type": "customers", "record_key": "shop_005", "field": "loyalty_points", "expected_value": 54100} in built.task_data["_legacy_state_requirement_exceptions"]
    assert {"entity_type": "customers", "record_key": "shop_005", "field": "loyalty_points", "expected_value": 54100} not in finalized.task_data["state_requirements"]


def test_shopping_no_write_pilot_keeps_empty_state_requirements() -> None:
    from domains.shopping_assistant import task_registry as registry

    adapter = get_generation_adapter(registry)
    idx, scenario = adapter.enumerate({81})[0]
    built = adapter.build(idx, scenario)
    finalized = finalize_generated_task(get_domain_config("shopping_assistant"), built)

    assert finalized.task_data["_replay_trace"] == []
    assert finalized.task_data["replay_trace_hash"]
    assert finalized.task_data["state_requirements"] == []


def test_shopping_task_70_preserves_verified_seeded_subtotal_requirement() -> None:
    from domains.shopping_assistant import task_registry as registry

    adapter = get_generation_adapter(registry)
    idx, scenario = adapter.enumerate({70})[0]
    built = adapter.build(idx, scenario)
    finalized = finalize_generated_task(get_domain_config("shopping_assistant"), built)

    assert {"entity_type": "carts", "record_key": "CART-shop_004", "field": "subtotal", "expected_value": 999} in finalized.task_data["state_requirements"]
    assert {"entity_type": "carts", "record_key": "CART-shop_004", "field": "discount_amount", "expected_value": 0} in finalized.task_data["state_requirements"]
    assert {"entity_type": "carts", "record_key": "CART-shop_004", "field": "total", "expected_value": 999} in finalized.task_data["state_requirements"]


def test_shopping_task_99_records_reviewed_legacy_customer_balance_exception() -> None:
    from domains.shopping_assistant import task_registry as registry

    adapter = get_generation_adapter(registry)
    idx, scenario = adapter.enumerate({99})[0]
    built = adapter.build(idx, scenario)
    finalized = finalize_generated_task(get_domain_config("shopping_assistant"), built)

    assert {"entity_type": "carts", "record_key": "CART-shop_003", "field": "subtotal", "expected_value": 149} in finalized.task_data["state_requirements"]
    assert {"entity_type": "carts", "record_key": "CART-shop_003", "field": "loyalty_discount", "expected_value": 74} in finalized.task_data["state_requirements"]
    assert {"entity_type": "customers", "record_key": "shop_003", "field": "loyalty_points", "expected_value": 11100} in built.task_data["_legacy_state_requirement_exceptions"]
    assert {"entity_type": "customers", "record_key": "shop_003", "field": "loyalty_points", "expected_value": 11100} not in finalized.task_data["state_requirements"]


def test_shopping_task_75_preserves_verified_seeded_cart_item_requirement() -> None:
    from domains.shopping_assistant import task_registry as registry

    adapter = get_generation_adapter(registry)
    idx, scenario = adapter.enumerate({75})[0]
    built = adapter.build(idx, scenario)
    finalized = finalize_generated_task(get_domain_config("shopping_assistant"), built)

    assert {
        "entity_type": "cart_items",
        "match_fields": {
            "cart_item_id": "CI-A1",
            "customer_id": "shop_004",
            "product_id": "SP-2006",
        },
        "expected_fields": {
            "quantity": 3,
            "gift_wrap": False,
        },
    } in finalized.task_data["state_requirements"]
    assert {
        "entity_type": "cart_items",
        "match_fields": {
            "cart_item_id": "CI-A2",
            "customer_id": "shop_004",
            "product_id": "SP-2005",
        },
        "expected_fields": {
            "quantity": 2,
            "gift_wrap": False,
        },
    } in finalized.task_data["state_requirements"]
    assert {"entity_type": "carts", "record_key": "CART-shop_004", "field": "shipping_cost", "expected_value": 0} in finalized.task_data["state_requirements"]


def test_shopping_task_40_reviewed_legacy_exception_allows_known_baseline_gt_bug() -> None:
    from domains.shopping_assistant import task_registry as registry

    adapter = get_generation_adapter(registry)
    idx, scenario = adapter.enumerate({40})[0]
    built = adapter.build(idx, scenario)
    finalized = finalize_generated_task(get_domain_config("shopping_assistant"), built)

    assert finalized.task_data["state_requirements"] == [
        {"entity_type": "carts", "record_key": "CART-shop_004", "field": "item_ids", "expected_value": ["CI-0002"]},
        {"entity_type": "carts", "record_key": "CART-shop_004", "field": "subtotal", "expected_value": 79},
        {"entity_type": "carts", "record_key": "CART-shop_004", "field": "total", "expected_value": 79},
    ]
    assert finalized.task_data["_legacy_state_requirement_exceptions"] == [
        {"entity_type": "carts", "record_key": "CART-shop_004", "field": "subtotal", "expected_value": 89},
        {"entity_type": "carts", "record_key": "CART-shop_004", "field": "total", "expected_value": 89},
    ]

def test_customer_support_non_default_scenario_now_round_trips() -> None:
    import importlib

    registry = importlib.import_module("domains.customer_support.task_registry")
    hooks = importlib.import_module("domains.customer_support.generate_tasks")
    adapter = hooks.get_generation_adapter(registry)
    domain_config = get_domain_config("customer_support")

    for idx, scenario in adapter.enumerate({63, 64, 67, 77, 81}):
        built = adapter.build(idx, scenario)
        finalized = finalize_generated_task(domain_config, built)

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            from state_bench.generation import save_task_json
            save_task_json(finalized.task_data, tmp_path)
            rendered = json.loads((tmp_path / f"{finalized.task_data['task_id']}.json").read_text())

        checked_in = json.loads(Path(f"domains/customer_support/tasks/{finalized.task_data['task_id']}.json").read_text())
        assert rendered == checked_in


def test_travel_filtered_generation_round_trips_later_cross_domain_task() -> None:
    import importlib

    registry = importlib.import_module("domains.travel.task_registry")
    hooks = importlib.import_module("domains.travel.generate_tasks")
    adapter = hooks.get_generation_adapter(registry)
    domain_config = get_domain_config("travel")

    finalized = None
    for idx, scenario in adapter.enumerate():
        built = adapter.build(idx, scenario)
        if idx != 30:
            continue
        finalized = finalize_generated_task(domain_config, built)
        break

    assert finalized is not None

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        from state_bench.generation import save_task_json
        save_task_json(finalized.task_data, tmp_path)
        rendered = json.loads((tmp_path / f"{finalized.task_data['task_id']}.json").read_text())

    checked_in = json.loads(Path(f"domains/travel/tasks/{finalized.task_data['task_id']}.json").read_text())
    checked_env = json.loads(Path(f"domains/travel/task_envs/{finalized.task_data['task_id']}.json").read_text())
    assert rendered == checked_in
    assert finalized.task_env.to_dict() == checked_env


def test_travel_generation_assigns_task_type_for_all_scenario_families() -> None:
    import importlib

    from domains.travel.generate_tasks import SCENARIO_FAMILY_TO_TASK_TYPE, TRAVEL_TASK_TYPES

    registry = importlib.import_module("domains.travel.task_registry")
    hooks = importlib.import_module("domains.travel.generate_tasks")
    adapter = hooks.get_generation_adapter(registry)
    domain_config = get_domain_config("travel")

    seen_families = set()
    for idx, scenario in adapter.enumerate():
        built = adapter.build(idx, scenario)
        finalized = finalize_generated_task(domain_config, built)
        family = scenario.__module__.rsplit(".", 1)[-1]
        seen_families.add(family)
        assert finalized.task_data["task_type"] == SCENARIO_FAMILY_TO_TASK_TYPE[family]
        assert finalized.task_data["task_type"] in TRAVEL_TASK_TYPES

    assert seen_families == set(SCENARIO_FAMILY_TO_TASK_TYPE)
