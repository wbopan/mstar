"""Re-score existing trajectories with the current metric judges.

Reads trajectory JSONs, re-runs only the selected completion and/or UX judges,
and updates the same trajectory files in place by default. Does not re-run agents.

Usage:
    uv run python scripts/rescore.py --domain travel --num-runs 5 --judge-type task_completion
    uv run python scripts/rescore.py --domain travel --num-runs 5 --judge-type all --reasoning-effort high
"""

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from state_bench.client import PooledLLMClient
from state_bench.domain import get_domain_config
from state_bench.schemas import StateDiff, TaskDefinition
from state_bench.scoring import (
    TaskRequirementsJudge,
    UXQualityJudge,
    combine_task_completion,
    evaluate_state_requirements,
)


def rescore_one(
    traj_path: Path,
    tasks_dir: Path,
    task_requirements_judge: TaskRequirementsJudge | None,
    ux_judge: UXQualityJudge | None,
    output_path: Path,
) -> dict:
    """Re-score a single trajectory using selected metric judges."""
    traj = json.loads(traj_path.read_text())
    tid = traj["task_id"]

    # Load the task definition
    task_file = tasks_dir / f"{tid}.json"
    if not task_file.exists():
        return {"task_id": tid, "status": "ERR", "error": "task file not found"}
    task = TaskDefinition.load(task_file)

    # Reconstruct state_diff from trajectory
    sd_raw = traj.get("state_diff")
    if sd_raw is None:
        state_diff = StateDiff(created={}, modified={}, deleted={})
    elif isinstance(sd_raw, dict) and {"created", "modified", "deleted"}.issubset(sd_raw):
        state_diff = StateDiff(
            created=sd_raw.get("created", {}),
            modified=sd_raw.get("modified", {}),
            deleted=sd_raw.get("deleted", {}),
        )
    else:
        return {"task_id": tid, "status": "ERR", "error": "malformed state_diff in trajectory"}

    # Reconstruct tool_calls from conversation
    tool_calls = []
    for msg in traj.get("conversation", []):
        if msg.get("tool_calls"):
            tool_calls.extend(msg["tool_calls"])

    if task_requirements_judge is not None:
        state_result = evaluate_state_requirements(task, state_diff)
        task_result = task_requirements_judge.evaluate(task, traj["conversation"], tool_calls, state_diff)

        traj["state_requirements_met"] = state_result.score if state_result else None
        traj["state_requirements_reasoning"] = state_result.reasoning if state_result else None
        traj["task_requirements_met"] = task_result.score if task_result else None
        traj["task_requirements_reasoning"] = task_result.reasoning if task_result else None
        traj["task_requirements_details"] = task_result.details if task_result else None
        traj["task_completion_pass"] = combine_task_completion(state_result, task_result)

    if ux_judge is not None:
        ux_result = ux_judge.evaluate(task, traj["conversation"], tool_calls)
        if ux_result is None:
            return {"task_id": tid, "status": "ERR", "error": "ux judge returned None"}
        traj["ux_consent"] = ux_result.consent
        traj["ux_ease"] = ux_result.ease
        traj["ux_discovery"] = ux_result.discovery
        traj["ux_information_quality"] = ux_result.information_quality
        traj["ux_disambiguation"] = ux_result.disambiguation
        traj["ux_score"] = round(ux_result.ux_score, 2)
        traj["ux_reasoning"] = ux_result.reasoning

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(traj, indent=2, ensure_ascii=False) + "\n")

    out = {"task_id": tid, "status": "OK"}
    if ux_judge is not None:
        out["ux_score"] = traj.get("ux_score")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Re-score trajectories with a different judge prompt")
    parser.add_argument("--domain", type=str, required=True)
    parser.add_argument("--num-runs", type=int, default=5)
    parser.add_argument(
        "--num-runs-idx-start",
        type=int,
        default=1,
        help="Starting run index to rescore (default: 1)",
    )
    parser.add_argument("--judge-type", type=str, default="task_completion", choices=["task_completion", "ux_quality", "all"], help="Which metric(s) to rescore")
    parser.add_argument("--source-dir", type=str, default=None, help="Source results dir (default: outputs/<domain>)")
    parser.add_argument("--output-dir", type=str, default=None, help="Optional alternate output dir. Default: overwrite files in --source-dir in place.")
    parser.add_argument("--reasoning-effort", type=str, default=None, choices=["low", "medium", "high"])
    parser.add_argument("--workers", type=int, default=25)
    args = parser.parse_args()
    if args.num_runs < 1:
        parser.error("--num-runs must be >= 1")
    if args.num_runs_idx_start < 1:
        parser.error("--num-runs-idx-start must be >= 1")
    if args.workers < 1:
        parser.error("--workers must be >= 1")

    domain = get_domain_config(args.domain)
    tasks_dir = Path(f"domains/{args.domain}/tasks")
    source_dir = Path(args.source_dir) if args.source_dir else Path(f"outputs/{args.domain}")

    output_dir = Path(args.output_dir) if args.output_dir else source_dir

    # Judges use the shared pooled client
    judge_client = PooledLLMClient()

    # Default reasoning effort for shared judge traffic
    reasoning_effort = args.reasoning_effort or "high"

    task_requirements_judge = None
    ux_judge = None
    if args.judge_type in {"task_completion", "all"}:
        task_requirements_judge = TaskRequirementsJudge(
            client=judge_client,
            prompts_dir=domain.prompts_dir,
            system_prompt=domain.judge_system_prompt,
            reasoning_effort=reasoning_effort,
        )
    if args.judge_type in {"ux_quality", "all"}:
        ux_judge = UXQualityJudge(
            client=judge_client,
            prompts_dir=domain.prompts_dir,
            system_prompt=domain.judge_system_prompt,
            reasoning_effort=reasoning_effort,
        )

    total_start = time.time()
    run_indices = list(range(args.num_runs_idx_start, args.num_runs_idx_start + args.num_runs))
    for run_idx in run_indices:
        run_dir = source_dir / f"run{run_idx}"
        if not run_dir.exists():
            print(f"WARNING: {run_dir} not found, skipping")
            continue

        out_run = output_dir / f"run{run_idx}"
        traj_files = sorted(run_dir.glob("*.json"))
        print(f"\nRun {run_idx}: re-scoring {len(traj_files)} trajectories...")

        results = []
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {
                executor.submit(rescore_one, tf, tasks_dir, task_requirements_judge, ux_judge, out_run / tf.name): tf
                for tf in traj_files
            }
            for future in as_completed(futures):
                r = future.result()
                results.append(r)
                score_str = ""
                if "ux_score" in r:
                    score_str += f" (ux={r['ux_score']})"
                print(f"  [{len(results)}/{len(futures)}] {r['task_id']}: {r['status']}{score_str}")

        errors = sum(1 for r in results if r["status"] == "ERR")
        task_completion_scored = sum(1 for r in results if r.get("status") == "OK" and task_requirements_judge is not None)
        ux_scored = [r for r in results if "ux_score" in r]
        summary = [f"err={errors}"]
        if task_completion_scored:
            summary.append(f"task_completion_scored={task_completion_scored}")
        if ux_scored:
            mean_ux = sum(r["ux_score"] for r in ux_scored) / len(ux_scored)
            summary.append(f"ux_scored={len(ux_scored)}")
            summary.append(f"mean_ux={mean_ux:.2f}")
        print(f"  Run {run_idx}: " + ", ".join(summary))

    elapsed = time.time() - total_start
    print(f"\nDone in {elapsed:.0f}s. Updated results in: {output_dir}/")
    print(
        f"Run: uv run python scripts/compute_metrics.py --results-dir {output_dir} "
        f"--num-runs {args.num_runs} --num-runs-idx-start {args.num_runs_idx_start}"
    )


if __name__ == "__main__":
    main()
