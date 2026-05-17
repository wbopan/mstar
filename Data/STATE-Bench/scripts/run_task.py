"""Run one or more tasks and optionally score them inline.

Usage:
    uv run python scripts/run_task.py --task 1-cancel_economy_domestic
    uv run python scripts/run_task.py --task 1-cancel_economy_domestic --score-completion
    uv run python scripts/run_task.py --task 1-cancel_economy_domestic 2-cancel_business_international --workers 2
    uv run python scripts/run_task.py --task 1-cancel_economy_domestic,2-cancel_business_international --workers 2
"""

import argparse
import inspect
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from agents import get_agent_class, list_agents
from agents.base import AgentRuntimeContext
from state_bench.client import PooledLLMClient
from state_bench.domain import get_domain_config
from state_bench.env_loader import load_task_environment
from state_bench.orchestrator import run_task
from state_bench.schemas import TaskDefinition
from state_bench.scoring import (
    TaskRequirementsJudge,
    UXQualityJudge,
    combine_task_completion,
    evaluate_state_requirements,
)


def _build_agent(agent_name: str | None, client, system_prompt: str, domain, env, runtime_context: AgentRuntimeContext):
    """Build an agent instance. Returns None to use default VanillaAgent."""
    if agent_name is None:
        return None
    agent_cls = get_agent_class(agent_name)
    init_params = inspect.signature(agent_cls.__init__).parameters
    if "runtime_context" in init_params:
        return agent_cls(client, system_prompt, domain.tool_schemas, env.tool_handlers, runtime_context=runtime_context)
    return agent_cls(client, system_prompt, domain.tool_schemas, env.tool_handlers)


def _parse_task_ids(raw_values: list[str]) -> list[str]:
    task_ids: list[str] = []
    for value in raw_values:
        task_ids.extend(part.strip() for part in value.split(",") if part.strip())
    return task_ids


def _load_requested_tasks(tasks_dir: Path, task_ids: list[str]) -> list[TaskDefinition]:
    missing: list[str] = []
    tasks: list[TaskDefinition] = []
    for task_id in task_ids:
        task_path = tasks_dir / f"{task_id}.json"
        if not task_path.exists():
            missing.append(task_id)
            continue
        tasks.append(TaskDefinition.load(task_path))
    if missing:
        available = sorted(f.stem for f in tasks_dir.glob("*.json"))
        print(f"Task(s) not found: {', '.join(missing)}")
        print(f"Available ({len(available)}):")
        for task_id in available:
            print(f"  {task_id}")
        raise SystemExit(1)
    return tasks


def _load_agent_config(path: str | None) -> dict:
    if path is None:
        return {}
    return json.loads(Path(path).read_text())


def _run_single_task(
    task: TaskDefinition,
    run_idx: int,
    user_override: str | None,
    client: PooledLLMClient,
    domain,
    output_dir: Path,
    agent_name: str | None,
    task_requirements_judge: TaskRequirementsJudge | None,
    ux_judge: UXQualityJudge | None,
    agent_config: dict,
) -> dict:
    user_id = user_override or task.user_id
    if not user_id:
        return {"task_id": task.task_id, "run_idx": run_idx, "status": "ERR", "error": "no user_id"}

    try:
        env_data, env_path = load_task_environment(domain, task)
    except FileNotFoundError:
        return {
            "task_id": task.task_id,
            "run_idx": run_idx,
            "status": "ERR",
            "error": (
                f"environment not found; run: uv run python scripts/generate_tasks.py --domain {domain.name}"
            ),
        }

    agent = None
    env = None
    if agent_name:
        agent_system_prompt = domain.agent_system_prompt.format(now=task.now, user_id=user_id)
        env = domain.environment_class(env_data.deep_copy(), now=task.now)
        runtime_context = AgentRuntimeContext(
            task_id=task.task_id,
            user_id=user_id,
            domain=domain.name,
            now=task.now,
            output_dir=str(output_dir),
            run_idx=run_idx,
            task_summary=task.task_summary,
            state_requirements=task.state_requirements,
            task_requirements=task.task_requirements,
            config=agent_config,
        )
        agent = _build_agent(agent_name, client, agent_system_prompt, domain, env, runtime_context)

    trajectory = run_task(task, env_data, user_id, client, domain=domain, agent=agent, env=env)

    tool_calls = []
    for msg in trajectory.conversation:
        if msg.get("tool_calls"):
            tool_calls.extend(msg["tool_calls"])

    if task_requirements_judge is not None:
        trajectory.state_requirements_score = evaluate_state_requirements(task, trajectory.state_diff)
        trajectory.task_requirements_score = task_requirements_judge.evaluate(
            task,
            trajectory.conversation,
            tool_calls,
            trajectory.state_diff,
        )
        trajectory.task_completion_pass = combine_task_completion(
            trajectory.state_requirements_score,
            trajectory.task_requirements_score,
        )

    if ux_judge is not None:
        trajectory.ux_quality = ux_judge.evaluate(task, trajectory.conversation, tool_calls)

    output_path = output_dir / f"{task.task_id}.json"
    trajectory.save(output_path)
    result = {
        "task_id": task.task_id,
        "run_idx": run_idx,
        "status": "OK",
        "output_path": str(output_path),
        "env_path": str(env_path),
        "task_summary": task.task_summary,
    }
    if trajectory.state_requirements_score is not None:
        result["state_requirements_met"] = trajectory.state_requirements_score.score
    if trajectory.task_requirements_score is not None:
        result["task_requirements_met"] = trajectory.task_requirements_score.score
    if trajectory.task_completion_pass is not None:
        result["task_completion_pass"] = trajectory.task_completion_pass
    if trajectory.ux_quality is not None:
        result["ux_score"] = trajectory.ux_quality.ux_score
    if trajectory.efficiency:
        result["efficiency"] = {
            "turns": trajectory.efficiency.turns,
            "tool_calls": trajectory.efficiency.tool_calls,
            "tool_errors": trajectory.efficiency.tool_errors,
            "redundant_calls": trajectory.efficiency.redundant_calls,
        }
    if trajectory.token_usage is not None:
        result["token_usage"] = trajectory.token_usage.to_dict()
        result["cost_usd"] = trajectory.token_usage.total_cost_usd
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one or more benchmark tasks")
    parser.add_argument(
        "--task",
        type=str,
        nargs="+",
        required=True,
        help="One or more task IDs. Supports space-separated values and comma-separated lists.",
    )
    parser.add_argument("--user", type=str, default=None, help="Override user ID (default: from task definition)")
    parser.add_argument("--domain", type=str, default="travel", help="Domain name (default: travel)")
    parser.add_argument("--output-dir", type=str, default=None, help="Output directory (default: outputs/<domain>)")
    parser.add_argument("--num-runs", type=int, default=1, help="Number of runs (default: 1)")
    parser.add_argument(
        "--num-runs-idx-start",
        type=int,
        default=1,
        help="Starting run index for output directories (default: 1)",
    )
    parser.add_argument("--workers", type=int, default=None, help="Parallel workers for multi-task execution (default: serial for one job, else min(total_jobs, 25))")
    parser.add_argument(
        "--agent",
        type=str,
        default=None,
        help=f"Agent class name (default: VanillaAgent). Available: {', '.join(list_agents())}",
    )
    parser.add_argument(
        "--agent-config",
        type=str,
        default=None,
        help="Path to a JSON file passed through to custom agents as runtime_context.config",
    )
    parser.add_argument("--score-completion", dest="score_completion", action="store_true", help="Score state/task completion immediately after the run")
    parser.add_argument("--score-ux", dest="ux_score", action="store_true", help="Score UX quality immediately after the run")
    parser.add_argument("--score-all", action="store_true", help="Score state/task checks + UX immediately after the run")
    parser.add_argument(
        "--judge-reasoning-effort",
        type=str,
        default="high",
        choices=["low", "medium", "high"],
        help="Judge reasoning effort when completion or UX scoring is enabled",
    )
    args = parser.parse_args()
    if sum(bool(x) for x in [args.score_completion, args.ux_score, args.score_all]) > 1:
        parser.error("--score-completion, --score-ux, and --score-all are mutually exclusive")
    if args.num_runs < 1:
        parser.error("--num-runs must be >= 1")
    if args.num_runs_idx_start < 1:
        parser.error("--num-runs-idx-start must be >= 1")

    domain = get_domain_config(args.domain)
    tasks_dir = Path(f"domains/{args.domain}/tasks")
    base_output = Path(args.output_dir) if args.output_dir else Path(f"outputs/{args.domain}")

    print("Initializing LLM client...")
    client = PooledLLMClient()
    deployment_count = len(client.deployments)
    agent_config = _load_agent_config(args.agent_config)

    task_ids = _parse_task_ids(args.task)
    tasks = _load_requested_tasks(tasks_dir, task_ids)
    work_items = [
        (run_idx, task)
        for run_idx in range(args.num_runs_idx_start, args.num_runs_idx_start + args.num_runs)
        for task in tasks
    ]
    worker_count = args.workers or (1 if len(work_items) == 1 else min(len(work_items), 25))
    if worker_count < 1:
        parser.error("--workers must be >= 1")
    if worker_count > deployment_count:
        parser.error(
            f"--workers must be <= configured deployment count ({deployment_count})"
        )

    print(f"Loaded {len(tasks)} task(s):")
    for task in tasks:
        print(f"  {task.task_id}: {task.task_summary.splitlines()[0]}")

    task_requirements_judge = None
    ux_judge = None
    if args.score_completion or args.ux_score or args.score_all:
        judge_client = client
        if args.score_completion or args.score_all:
            task_requirements_judge = TaskRequirementsJudge(
                client=judge_client,
                prompts_dir=domain.prompts_dir,
                system_prompt=domain.judge_system_prompt,
                reasoning_effort=args.judge_reasoning_effort,
            )
        if args.ux_score or args.score_all:
            ux_judge = UXQualityJudge(
                client=judge_client,
                prompts_dir=domain.prompts_dir,
                system_prompt=domain.judge_system_prompt,
                reasoning_effort=args.judge_reasoning_effort,
            )

    agent_label = args.agent or "VanillaAgent"
    print(f"Agent: {agent_label}")
    if args.score_completion or args.ux_score or args.score_all:
        print("Inline scoring enabled via shared deployment pool")

    run_indices = list(range(args.num_runs_idx_start, args.num_runs_idx_start + args.num_runs))
    run_dirs = {run_idx: base_output / f"run{run_idx}" for run_idx in run_indices}
    for run_dir in run_dirs.values():
        run_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'#' * 60}")
    print(
        f"# Running {len(tasks)} task(s) across run indices {run_indices[0]}..{run_indices[-1]}"
        f" => {len(work_items)} total job(s) with {worker_count} worker(s)"
    )
    print(f"# Inline scoring: {'on' if (args.score_completion or args.ux_score or args.score_all) else 'off'}")
    print(f"{'#' * 60}")

    results: list[dict] = []
    if worker_count == 1:
        for run_idx, task in work_items:
            print(f"\n{'=' * 60}")
            print(f"Running: {task.task_id} | User: {args.user or task.user_id} | Run index {run_idx}")
            print(f"{'=' * 60}")
            result = _run_single_task(
                task,
                run_idx,
                args.user,
                client,
                domain,
                run_dirs[run_idx],
                args.agent,
                task_requirements_judge,
                ux_judge,
                agent_config,
            )
            results.append(result)
    else:
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(
                    _run_single_task,
                    task,
                    run_idx,
                    args.user,
                    client,
                    domain,
                    run_dirs[run_idx],
                    args.agent,
                    task_requirements_judge,
                    ux_judge,
                    agent_config,
                ): (run_idx, task)
                for run_idx, task in work_items
            }
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                suffix = ""
                if "state_requirements_met" in result or "task_requirements_met" in result or "task_completion_pass" in result:
                    suffix += (
                        f" | state={result.get('state_requirements_met')}"
                        f" | task={result.get('task_requirements_met')}"
                        f" | completion={result.get('task_completion_pass')}"
                    )
                if "ux_score" in result:
                    suffix += f" | ux={result['ux_score']:.2f}"
                print(f"  [done] run{result['run_idx']} {result['task_id']}: {result['status']}{suffix}")

    results.sort(key=lambda item: (item["run_idx"], item["task_id"]))
    for result in results:
        print(f"\nTrajectory saved: {result.get('output_path', '<none>')}")
        if result["status"] != "OK":
            print(f"Run failed: {result.get('error', 'unknown error')}")
            continue
        print(f"  Task: {result['task_id']} | Run index {result['run_idx']}")
        print(f"  Environment: {result['env_path']}")
        if "state_requirements_met" in result:
            print(f"  State check: {result['state_requirements_met']}/1")
        if "task_requirements_met" in result:
            print(f"  Task requirements: {result['task_requirements_met']}/1")
        if "task_completion_pass" in result:
            print(f"  Task completion: {result['task_completion_pass']}/1")
        if "ux_score" in result:
            print(f"  UX score: {result['ux_score']:.2f}/5")
        if "efficiency" in result:
            efficiency = result["efficiency"]
            print(
                "  Efficiency: "
                f"{efficiency['turns']} turns, "
                f"{efficiency['tool_calls']} tool calls, "
                f"{efficiency['tool_errors']} errors, "
                f"{efficiency['redundant_calls']} redundant"
            )
        if "token_usage" in result:
            usage = result["token_usage"]
            print(
                "  Tokens: "
                f"input={usage['input_tokens']}, "
                f"cached_input={usage['cached_input_tokens']}, "
                f"output={usage['output_tokens']}, "
                f"cost=${usage['total_cost_usd']:.4f}"
            )
            print(
                "  Cost breakdown: "
                f"agent=${usage.get('agent_turn_cost_usd', 0.0):.4f}, "
                f"memory_ingest=${usage.get('memory_ingestion_cost_usd', 0.0):.4f}, "
                f"memory_retrieval=${usage.get('memory_retrieval_cost_usd', 0.0):.4f}, "
                f"embedding=${usage.get('embedding_cost_usd', 0.0):.4f}"
            )

    if not (args.score_completion or args.ux_score or args.score_all):
        print(
            f"\nScore with: uv run python scripts/rescore.py --domain {args.domain} "
            f"--num-runs {args.num_runs} --num-runs-idx-start {args.num_runs_idx_start}"
        )


if __name__ == "__main__":
    main()
