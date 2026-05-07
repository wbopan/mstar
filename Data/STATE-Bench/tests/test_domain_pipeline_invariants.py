import json
from pathlib import Path

from domains.customer_support.generate_tasks import CUSTOMER_SUPPORT_TASK_TYPES
from domains.shopping_assistant.generate_tasks import SHOPPING_TASK_TYPES
from domains.travel.generate_tasks import TRAVEL_TASK_TYPES


def _domain_tasks(domain: str) -> list[Path]:
    return sorted(Path(f"domains/{domain}/tasks").glob("*.json"))


def _domain_envs(domain: str) -> list[Path]:
    return sorted(Path(f"domains/{domain}/task_envs").glob("*.json"))


def test_all_domains_have_task_env_and_state_requirements_metadata() -> None:
    for domain in ("travel", "customer_support", "shopping_assistant"):
        for task_path in _domain_tasks(domain):
            task = json.loads(task_path.read_text())
            assert task.get("task_env_path") == f"domains/{domain}/task_envs/{task_path.stem}.json", task_path.name
            assert "state_requirements" in task, task_path.name
            assert task["state_requirements"] is not None, task_path.name


def test_all_domains_have_matching_task_and_env_sets() -> None:
    for domain in ("travel", "customer_support", "shopping_assistant"):
        task_ids = [path.stem for path in _domain_tasks(domain)]
        env_ids = [path.stem for path in _domain_envs(domain)]
        assert task_ids == env_ids, domain


def test_all_domains_have_contiguous_numbered_task_prefixes() -> None:
    for domain in ("travel", "customer_support", "shopping_assistant"):
        task_numbers = sorted(int(path.stem.split("-", 1)[0]) for path in _domain_tasks(domain))
        assert task_numbers == list(range(1, len(task_numbers) + 1)), domain


def test_customer_support_tasks_have_allowed_task_type() -> None:
    for task_path in _domain_tasks("customer_support"):
        task = json.loads(task_path.read_text())
        assert task.get("task_type") in CUSTOMER_SUPPORT_TASK_TYPES, task_path.name


def test_shopping_tasks_have_allowed_task_type() -> None:
    for task_path in _domain_tasks("shopping_assistant"):
        task = json.loads(task_path.read_text())
        assert task.get("task_type") in SHOPPING_TASK_TYPES, task_path.name


def test_travel_tasks_have_allowed_task_type() -> None:
    for task_path in _domain_tasks("travel"):
        task = json.loads(task_path.read_text())
        assert task.get("task_type") in TRAVEL_TASK_TYPES, task_path.name


def test_split_manifests_match_task_metadata() -> None:
    for domain in ("travel", "customer_support", "shopping_assistant"):
        manifest = json.loads(Path(f"domains/{domain}/splits/train_test_v1.json").read_text())
        task_ids = {path.stem for path in _domain_tasks(domain)}
        train = manifest["splits"]["train"]
        test = manifest["splits"]["test"]
        metadata = manifest["task_metadata"]

        assert manifest["domain"] == domain
        assert "taxonomy" not in manifest
        assert "scenario_family_to_task_type" not in manifest
        assert len(train) == 100
        assert len(test) == 50
        assert set(train).isdisjoint(test)
        assert set(train) | set(test) == task_ids
        assert set(metadata) == task_ids

        train_task_types = {metadata[task_id]["task_type"] for task_id in train}
        train_families = {metadata[task_id]["scenario_family"] for task_id in train}

        for task_path in _domain_tasks(domain):
            task = json.loads(task_path.read_text())
            task_id = task_path.stem
            item = metadata[task_id]
            assert item["task_type"] == task["task_type"], task_id
            assert item["split"] == ("test" if task_id in test else "train"), task_id
            assert item["scenario_family"], task_id
            if task_id in test:
                assert item["task_type"] in train_task_types, task_id
                assert item["scenario_family"] in train_families, task_id
