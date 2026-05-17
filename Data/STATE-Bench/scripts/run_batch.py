"""Run tasks in parallel and optionally score trajectories inline.

By default this generates trajectories only. With scoring flags it also runs
state/task and/or UX metrics immediately after each trajectory is produced and
writes them back to that same trajectory file.

Usage:
    uv run python scripts/run_batch.py --domain travel --num-runs 2
    uv run python scripts/run_batch.py --domain travel --num-runs 2 --score-completion
    uv run python scripts/run_batch.py --domain travel --agent VanillaAgent --score-completion
"""

import argparse
import inspect
import json
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from agents import get_agent_class, list_agents
from agents.base import AgentRuntimeContext
from state_bench.client import PooledLLMClient
from state_bench.domain import DomainConfig, get_domain_config
from state_bench.env_loader import load_task_environment
from state_bench.orchestrator import run_task
from state_bench.schemas import TaskDefinition
from state_bench.scoring import (
    TaskRequirementsJudge,
    UXQualityJudge,
    combine_task_completion,
    evaluate_state_requirements,
)


def _load_agent_config(path: str | None) -> dict:
    if path is None:
        return {}
    return json.loads(Path(path).read_text())


def _run_single(
    task_file: Path,
    client: PooledLLMClient,
    output_dir: Path,
    domain: DomainConfig,
    agent_name: str | None,
    agent_config: dict,
    max_attempts: int,
    task_requirements_judge: TaskRequirementsJudge | None = None,
    ux_judge: UXQualityJudge | None = None,
) -> dict:
    task = TaskDefinition.load(task_file)
    user_id = task.user_id
    if not user_id:
        return {"task_id": task.task_id, "status": "ERR", "error": "no user_id"}

    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            env_data, _env_path = load_task_environment(domain, task)
            agent = None
            env = None
            if agent_name:
                agent_cls = get_agent_class(agent_name)
                system_prompt = domain.agent_system_prompt.format(now=task.now, user_id=user_id)
                env = domain.environment_class(env_data.deep_copy(), now=task.now)
                runtime_context = AgentRuntimeContext(
                    task_id=task.task_id,
                    user_id=user_id,
                    domain=domain.name,
                    now=task.now,
                    output_dir=str(output_dir),
                    task_summary=task.task_summary,
                    state_requirements=task.state_requirements,
                    task_requirements=task.task_requirements,
                    config=agent_config,
                )
                init_params = inspect.signature(agent_cls.__init__).parameters
                if "runtime_context" in init_params:
                    agent = agent_cls(
                        client,
                        system_prompt,
                        domain.tool_schemas,
                        env.tool_handlers,
                        runtime_context=runtime_context,
                    )
                else:
                    agent = agent_cls(client, system_prompt, domain.tool_schemas, env.tool_handlers)

            traj = run_task(task, env_data, user_id, client, domain=domain, agent=agent, env=env)

            tool_calls = []
            for msg in traj.conversation:
                if msg.get("tool_calls"):
                    tool_calls.extend(msg["tool_calls"])

            if task_requirements_judge is not None:
                state_result = evaluate_state_requirements(task, traj.state_diff)
                task_result = task_requirements_judge.evaluate(task, traj.conversation, tool_calls, traj.state_diff)
                traj.state_requirements_score = state_result
                traj.task_requirements_score = task_result
                traj.task_completion_pass = combine_task_completion(state_result, task_result)

            if ux_judge is not None:
                traj.ux_quality = ux_judge.evaluate(task, traj.conversation, tool_calls)

            out_path = output_dir / f"{task.task_id}.json"
            traj.save(out_path)

            result = {"task_id": task.task_id, "status": "OK"}
            if task_requirements_judge is not None:
                result["state_requirements_met"] = (
                    traj.state_requirements_score.score if traj.state_requirements_score is not None else None
                )
                result["task_requirements_met"] = (
                    traj.task_requirements_score.score if traj.task_requirements_score is not None else None
                )
                result["task_completion_pass"] = traj.task_completion_pass
            if ux_judge is not None and traj.ux_quality is not None:
                result["ux_score"] = round(traj.ux_quality.ux_score, 2)
            if traj.token_usage is not None:
                result["token_usage"] = traj.token_usage.to_dict()
                result["cost_usd"] = traj.token_usage.total_cost_usd
            if attempt > 1:
                result["attempts"] = attempt
            return result
        except Exception as e:
            last_error = {
                "task_id": task.task_id,
                "status": "ERR",
                "attempts": attempt,
                "error": str(e)[:200],
                "traceback": "".join(traceback.format_exception(type(e), e, e.__traceback__))[-4000:],
            }
            if attempt < max_attempts:
                time.sleep(min(2 * attempt, 5))

    return last_error or {"task_id": task.task_id, "status": "ERR", "error": "unknown error"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run benchmark tasks")
    parser.add_argument("--domain", type=str, default="travel", help="Domain name (default: travel)")
    parser.add_argument("--workers", type=int, default=None, help="Number of parallel workers (default: all configured deployments)")
    parser.add_argument("--tasks", type=str, default=None, help="Comma-separated task IDs")
    parser.add_argument("--output-dir", type=str, default=None, help="Output directory (default: outputs/<domain>)")
    parser.add_argument("--num-runs", type=int, default=1, help="Number of runs (default: 1)")
    parser.add_argument(
        "--num-runs-idx-start",
        type=int,
        default=1,
        help="Starting run index for output directories (default: 1)",
    )
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
    parser.add_argument(
        "--prompt-append",
        type=str,
        default=None,
        help="Path to a file whose contents are appended to the agent system prompt",
    )
    parser.add_argument("--retry-attempts", type=int, default=3, help="Worker retry attempts for transient runtime errors")
    parser.add_argument("--score-completion", dest="score_completion", action="store_true", help="Score state/task completion in place immediately after each run")
    parser.add_argument("--score-ux", dest="ux_score", action="store_true", help="Score UX quality in place immediately after each run")
    parser.add_argument("--score-all", action="store_true", help="Score state/task checks + UX in place immediately after each run")
    parser.add_argument(
        "--judge-reasoning-effort",
        type=str,
        default="high",
        choices=["low", "medium", "high"],
        help="Judge reasoning effort when --score-completion is used",
    )
    args = parser.parse_args()
    if sum(bool(x) for x in [args.score_completion, args.ux_score, args.score_all]) > 1:
        parser.error("--score-completion, --score-ux, and --score-all are mutually exclusive")
    if args.num_runs < 1:
        parser.error("--num-runs must be >= 1")
    if args.num_runs_idx_start < 1:
        parser.error("--num-runs-idx-start must be >= 1")
    if args.workers is not None and args.workers < 1:
        parser.error("--workers must be >= 1")

    domain = get_domain_config(args.domain)
    tasks_dir = Path(f"domains/{args.domain}/tasks")
    base_output = Path(args.output_dir) if args.output_dir else Path(f"outputs/{args.domain}")

    client = PooledLLMClient()
    deployment_count = len(client.deployments)
    if args.workers is None:
        args.workers = deployment_count
    agent_config = _load_agent_config(args.agent_config)
    if args.workers > deployment_count:
        parser.error(f"--workers must be <= configured deployment count ({deployment_count})")
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

    if args.tasks:
        task_ids = [t.strip() for t in args.tasks.split(",")]
        task_files = [tasks_dir / f"{tid}.json" for tid in task_ids]
    else:
        task_files = sorted(tasks_dir.glob("*.json"))


    if args.prompt_append:
        extra = Path(args.prompt_append).read_text()
        domain.agent_system_prompt = domain.agent_system_prompt + "\n\n" + extra
        print(f"Appended {len(extra)} chars from {args.prompt_append} to agent system prompt")

    agent_label = args.agent or "VanillaAgent"
    print(f"Agent: {agent_label}")
    if args.score_completion or args.ux_score or args.score_all:
        print("Inline scoring enabled via shared deployment pool")

    total_start = time.time()
    run_indices = list(range(args.num_runs_idx_start, args.num_runs_idx_start + args.num_runs))
    run_dirs = {run_idx: base_output / f"run{run_idx}" for run_idx in run_indices}
    for run_dir in run_dirs.values():
        run_dir.mkdir(parents=True, exist_ok=True)

    work_items = [
        (run_idx, tf)
        for run_idx in run_indices
        for tf in task_files
        if tf.exists()
    ]

    print(f"\n{'#' * 60}")
    print(
        f"# Runs {run_indices[0]}..{run_indices[-1]} together — {len(task_files)} tasks/run, "
        f"{len(work_items)} total jobs, {args.workers} workers"
    )
    print(f"# Inline scoring: {'on' if (args.score_completion or args.ux_score or args.score_all) else 'off'}")
    print(f"{'#' * 60}")

    start = time.time()
    results = []
    run_results: dict[int, list[dict]] = {run_idx: [] for run_idx in run_indices}
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(
                _run_single,
                tf,
                client,
                run_dirs[run_idx],
                domain,
                args.agent,
                agent_config,
                args.retry_attempts,
                task_requirements_judge,
                ux_judge,
            ): (run_idx, tf)
            for run_idx, tf in work_items
        }
        for future in as_completed(futures):
            run_idx, _tf = futures[future]
            r = future.result()
            r["run_idx"] = run_idx
            results.append(r)
            run_results[run_idx].append(r)
            suffix = ""
            if "state_requirements_met" in r or "task_requirements_met" in r or "task_completion_pass" in r:
                suffix += f" | state={r.get('state_requirements_met')} | task={r.get('task_requirements_met')} | completion={r.get('task_completion_pass')}"
            if "ux_score" in r:
                suffix += f" | ux={r['ux_score']:.2f}"
            if "cost_usd" in r:
                suffix += f" | cost=${r['cost_usd']:.4f}"
            print(f"  [{len(results)}/{len(futures)}] run{run_idx} {r['task_id']}: {r['status']}{suffix}")

    elapsed = time.time() - start
    for run_idx in run_indices:
        run_items = run_results[run_idx]
        ok = sum(1 for r in run_items if r["status"] == "OK")
        errors = sum(1 for r in run_items if r["status"] == "ERR")
        print(f"\n  Run {run_idx} done — {ok} ok, {errors} err")
        if args.score_completion or args.score_all:
            scored = [r for r in run_items if "task_completion_pass" in r]
            passed = sum(1 for r in scored if r.get("task_completion_pass") == 1)
            print(f"    Scored: {len(scored)} | completion_pass={passed} | completion_fail={len(scored) - passed}")
        if args.ux_score or args.score_all:
            ux_scored = [r for r in run_items if "ux_score" in r]
            if ux_scored:
                mean_ux = sum(r["ux_score"] for r in ux_scored) / len(ux_scored)
                print(f"    UX scored: {len(ux_scored)} | mean_ux={mean_ux:.2f}")
        costed = [r["cost_usd"] for r in run_items if "cost_usd" in r]
        if costed:
            print(f"    Mean cost: ${sum(costed) / len(costed):.4f}")
        if errors:
            for r in run_items:
                if r["status"] == "ERR":
                    print(f"    ERROR {r['task_id']}: {r.get('error', '?')} (attempts={r.get('attempts', '?')})")
                    if r.get("traceback"):
                        print(r["traceback"])

    total_elapsed = time.time() - total_start
    print(f"\nAll runs complete in {total_elapsed:.0f}s (worker wall time {elapsed:.0f}s)")
    print(f"Trajectories in: {base_output}/run*/")
    if not (args.score_completion or args.ux_score or args.score_all):
        print(
            f"Score with: uv run python scripts/rescore.py --domain {args.domain} "
            f"--num-runs {args.num_runs} --num-runs-idx-start {args.num_runs_idx_start}"
        )


if __name__ == "__main__":
    main()
