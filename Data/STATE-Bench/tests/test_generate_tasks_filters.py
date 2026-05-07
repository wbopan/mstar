from scripts.generate_tasks import _parse_task_id_filter


def test_parse_task_id_filter_supports_lists_and_ranges() -> None:
    assert _parse_task_id_filter(None) is None
    assert _parse_task_id_filter("1,3,5-7") == {1, 3, 5, 6, 7}
    assert _parse_task_id_filter("7-5,2") == {2, 5, 6, 7}

def test_travel_generation_adapter_enumerate_honors_filter() -> None:
    import importlib

    registry = importlib.import_module("domains.travel.task_registry")
    hooks = importlib.import_module("domains.travel.generate_tasks")
    adapter = hooks.get_generation_adapter(registry)

    indexed = adapter.enumerate({30})

    assert [idx for idx, _ in indexed] == [30]


def test_customer_support_generation_adapter_enumerate_honors_filter() -> None:
    import importlib

    registry = importlib.import_module("domains.customer_support.task_registry")
    hooks = importlib.import_module("domains.customer_support.generate_tasks")
    adapter = hooks.get_generation_adapter(registry)

    indexed = adapter.enumerate({63, 81})

    assert [idx for idx, _ in indexed] == [63, 81]

