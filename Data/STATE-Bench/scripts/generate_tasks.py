"""Generate tasks and task-local environments for any domain."""

import argparse
import importlib
import json
import shutil
from pathlib import Path

from state_bench.domain import get_domain_config
from state_bench.env_loader import load_task_environment
from state_bench.generation import finalize_generated_task, save_task_json, serialize_task_payload
from state_bench.schemas import TaskDefinition


def _get_registry(domain: str):
    return importlib.import_module(f"domains.{domain}.task_registry")


def _get_domain_hooks(domain: str):
    return importlib.import_module(f"domains.{domain}.generate_tasks")


def _render_saved_task_payload(task_data: dict) -> dict:
    return serialize_task_payload(task_data)


def _check_generated_tasks(tasks_dir: Path, generated_tasks: list[dict]) -> bool:
    ok = True
    for task_data in generated_tasks:
        task_path = tasks_dir / f"{task_data['task_id']}.json"
        if not task_path.exists():
            print(f"MISSING: {task_path}")
            ok = False
            continue
        checked_in = json.loads(task_path.read_text())
        rendered_generated = _render_saved_task_payload(task_data)
        if checked_in != rendered_generated:
            print(f"MISMATCH: {task_data['task_id']}")
            ok = False
    return ok


def _check_task_envs(task_env_dir: Path, generated_task_envs: dict[str, object]) -> bool:
    ok = True
    for task_id, env_data in generated_task_envs.items():
        env_path = task_env_dir / f"{task_id}.json"
        if not env_path.exists():
            print(f"MISSING: {env_path}")
            ok = False
            continue
        checked_env = json.loads(env_path.read_text())
        if checked_env != env_data.to_dict():
            print(f"MISMATCH: {env_path}")
            ok = False
    return ok


def _dump_sim_prompts(domain: str, tasks_dir: Path) -> None:
    output_dir = Path(f"outputs/{domain}/user_sim_prompts")
    output_dir.mkdir(parents=True, exist_ok=True)

    domain_config = get_domain_config(domain)
    for task_path in sorted(tasks_dir.glob("*.json")):
        task = TaskDefinition.load(task_path)
        env_data, _ = load_task_environment(domain_config, task)
        prompt = domain_config.build_simulator_prompt(task, env_data, task.user_id)
        (output_dir / f"{task.task_id}.md").write_text(prompt)

    print(f"User simulator prompts -> {output_dir}")


def _parse_task_id_filter(raw: str | None) -> set[int] | None:
    if raw is None:
        return None
    values: set[int] = set()
    for part in raw.split(","):
        token = part.strip()
        if not token:
            continue
        if "-" in token:
            start_raw, end_raw = token.split("-", 1)
            start = int(start_raw)
            end = int(end_raw)
            if end < start:
                start, end = end, start
            values.update(range(start, end + 1))
        else:
            values.add(int(token))
    return values


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate tasks and task-local environments for a domain")
    parser.add_argument(
        "--domain",
        type=str,
        required=True,
        choices=["travel", "customer_support", "shopping_assistant"],
        help="Domain name",
    )
    parser.add_argument("--check", action="store_true", help="Verify generated tasks match checked-in JSON without rewriting files")
    parser.add_argument(
        "--task-ids",
        type=str,
        help="Optional 1-based scenario indices to regenerate/check, e.g. '1,2,5-8'",
    )
    args = parser.parse_args()

    domain = args.domain
    registry = _get_registry(domain)
    hooks = _get_domain_hooks(domain)
    if not hasattr(hooks, "get_generation_adapter"):
        raise ValueError(f"Domain {domain!r} must provide get_generation_adapter()")

    adapter = hooks.get_generation_adapter(registry)
    domain_config = get_domain_config(domain)

    tasks_dir = Path(f"domains/{domain}/tasks")
    task_env_dir = Path(f"domains/{domain}/task_envs")

    task_id_filter = _parse_task_id_filter(args.task_ids)
    indexed_scenarios = adapter.enumerate(task_id_filter)
    selected_count = len(indexed_scenarios)
    print(f"Generating {selected_count} {domain} tasks...")

    generated_tasks: list[dict] = []
    generated_task_envs: dict[str, object] = {}
    audit_issues: list[tuple[str, str]] = []

    for idx, scenario in indexed_scenarios:
        built = adapter.build(idx, scenario)
        finalized = finalize_generated_task(domain_config, built)
        generated_tasks.append(finalized.task_data)
        generated_task_envs[finalized.task_data["task_id"]] = finalized.task_env
        audit_issues.extend((finalized.task_data["task_id"], issue) for issue in finalized.audit_issues)

    if audit_issues:
        for task_id, issue in audit_issues:
            print(f"INVALID: {task_id}: {issue}")
        raise SystemExit(1)

    if args.check:
        ok = _check_generated_tasks(tasks_dir, generated_tasks)
        ok = _check_task_envs(task_env_dir, generated_task_envs) and ok
        if ok:
            print("Check passed.")
        raise SystemExit(0 if ok else 1)

    precheck_ok = _check_generated_tasks(tasks_dir, generated_tasks)
    task_envs_ok = _check_task_envs(task_env_dir, generated_task_envs)

    if precheck_ok and task_envs_ok:
        print("Checked-in tasks and environments already match generated output.")
    else:
        print("Pre-write check detected drift; regenerating checked-in tasks and environments.")

    if task_id_filter is None:
        if tasks_dir.exists():
            shutil.rmtree(tasks_dir)
        tasks_dir.mkdir(parents=True, exist_ok=True)

        if task_env_dir.exists():
            shutil.rmtree(task_env_dir)
        task_env_dir.mkdir(parents=True, exist_ok=True)
    else:
        tasks_dir.mkdir(parents=True, exist_ok=True)
        task_env_dir.mkdir(parents=True, exist_ok=True)

    for task_data in generated_tasks:
        save_task_json(task_data, tasks_dir)
    for task_id, task_env in generated_task_envs.items():
        task_env.save(task_env_dir / f"{task_id}.json")

    print(f"Generated {len(generated_tasks)} tasks -> {tasks_dir}")
    print(f"Task environments -> {task_env_dir}")

    _dump_sim_prompts(domain, tasks_dir)

    postcheck_ok = _check_generated_tasks(tasks_dir, generated_tasks)
    task_envs_ok = _check_task_envs(task_env_dir, generated_task_envs)
    if not postcheck_ok or not task_envs_ok:
        raise SystemExit(1)
    print("Post-generate check passed.")


if __name__ == "__main__":
    main()
