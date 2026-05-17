import json
from pathlib import Path

TASKS_DIR = Path("domains/customer_support/tasks")


def test_customer_support_tasks_keep_migrated_fields() -> None:
    task_files = sorted(TASKS_DIR.glob("*.json"))

    assert len(task_files) == 100

    for task_file in task_files:
        data = json.loads(task_file.read_text())
        assert "task_env_path" in data, task_file.name
        assert isinstance(data["task_env_path"], str) and data["task_env_path"], task_file.name
        assert "task_summary" in data, task_file.name
        assert isinstance(data["task_summary"], str), task_file.name
        assert "task_requirements" in data, task_file.name
        assert isinstance(data["task_requirements"], list), task_file.name
        assert "state_requirements" in data, task_file.name
        assert isinstance(data["state_requirements"], list), task_file.name
