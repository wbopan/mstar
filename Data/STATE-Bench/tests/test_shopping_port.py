from pathlib import Path

from domains.shopping_assistant.schemas import SAEnvironmentData
from domains.shopping_assistant.simulator import build_simulator_prompt
from scripts.generate_tasks import _dump_sim_prompts
from state_bench.schemas import TaskDefinition, UserSimulatorConfig


def test_user_simulator_config_round_trips_user_sim_context() -> None:
    payload = {
        "personality": "calm",
        "user_sim_context": "Customer has a hidden constraint.",
        "known_info": ["known"],
        "unknown_info": ["unknown"],
        "task_rules": ["rule"],
    }

    config = UserSimulatorConfig.from_dict(payload)

    assert config.user_sim_context == "Customer has a hidden constraint."
    assert config.to_dict()["user_sim_context"] == "Customer has a hidden constraint."


def test_shopping_build_simulator_prompt_includes_user_sim_context() -> None:
    task = TaskDefinition(
        task_id="shopping-test",
        task_summary="Task summary.",
        user_id="shop_001",
        opening_message="hello",
        user_simulator=UserSimulatorConfig(
            personality="thoughtful",
            user_sim_context="The customer remembers they travel a lot.",
            known_info=["Knows their budget"],
            unknown_info=["Does not know exact prices"],
            task_rules=["Keep replies short."],
        ),
        task_env_path="domains/shopping_assistant/task_envs/1-recommend_college_laptop.json",
    )
    env_data = SAEnvironmentData.load(Path(task.task_env_path))

    prompt = build_simulator_prompt(task, env_data, task.user_id)

    assert "## Task Context" in prompt
    assert "The customer remembers they travel a lot." in prompt
    assert "Keep replies short." in prompt


def test_shopping_dump_sim_prompts_writes_prompt_files(tmp_path: Path) -> None:
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir(parents=True)

    task = {
        "task_id": "1-recommend_college_laptop",
        "task_summary": "Task summary.",
        "user_id": "shop_002",
        "now": "2026-06-12T10:00:00",
        "opening_message": "hello",
        "user_simulator": {
            "personality": "cooperative",
            "user_sim_context": "Context text.",
            "known_info": ["Known fact"],
            "unknown_info": ["Unknown fact"],
            "task_rules": ["Rule text."],
        },
        "task_env_path": "domains/shopping_assistant/task_envs/1-recommend_college_laptop.json",
        "state_requirements": [],
        "task_requirements": [],
    }
    (tasks_dir / "1-recommend_college_laptop.json").write_text(__import__("json").dumps(task))

    _dump_sim_prompts("shopping_assistant", tasks_dir)

    prompt_path = Path("outputs/shopping_assistant/user_sim_prompts/1-recommend_college_laptop.md")
    assert prompt_path.exists()
    prompt = prompt_path.read_text()
    assert "Context text." in prompt
    assert "Rule text." in prompt
