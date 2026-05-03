#!/usr/bin/env python3
"""Extract GEPA search call counts from existing output artifacts.

This script intentionally uses only files already present under outputs/gepa-*.
It reports metric calls from summary.json and evaluator batch sizes from
run_log.txt. It also estimates search dollars by extrapolating evaluator costs
from matching t1-* baseline runs with recorded usage and reflection costs from
the mean recorded t1-*-ours reflector call.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path

KNOWN_DATASETS = [
    "alfworld-unseen",
    "alfworld-seen",
    "hb-data-tasks",
    "hb-emergency",
    "pr-finance",
    "pr-legal",
    "locomo",
]

DATASET_DISPLAY = {
    "locomo": "LoCoMo",
    "alfworld-unseen": "ALFWorld (Unseen)",
    "alfworld-seen": "ALFWorld (Seen)",
    "hb-emergency": "HB-Emergency",
    "hb-data-tasks": "HB-DataTasks",
    "pr-legal": "PR-Legal",
    "pr-finance": "PR-Finance",
}

MODEL_PRICING: dict[str, tuple[float, float]] = {
    "gpt-5.4-mini": (0.75, 4.50),
    "gpt-5.3-codex": (1.75, 14.00),
    "gpt-5.4": (6.00, 36.00),
    "deepseek-v3": (0.30, 0.88),
    "gpt-5.1-codex-mini": (0.25, 2.00),
}


@dataclass
class GEPACallCounts:
    run: str
    dataset: str
    config: str
    metric_calls: int
    proposals: int
    candidates: int
    eval_batches: int
    full_val_evals: int
    train_item_evals: int
    val_item_evals: int
    search_task_calls_lower_bound: int
    estimated_eval_cost_usd: float | None
    estimated_reflection_cost_usd: float | None
    estimated_total_cost_usd: float | None
    cost_reference_run: str | None
    final_score: float | None


@dataclass
class ReferenceCost:
    run: str
    train_cost_per_item: float
    val_cost_per_item: float
    train_items: int
    val_items: int
    total_cost: float


def _price_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    for key, (input_per_1m, output_per_1m) in MODEL_PRICING.items():
        if key in model:
            return prompt_tokens * input_per_1m / 1_000_000 + completion_tokens * output_per_1m / 1_000_000
    return 0.0


def _parse_run_name(name: str) -> tuple[str, str]:
    stem = name.removeprefix("gepa-")
    config = "GEPA + Vector Search"
    if stem.endswith("-no-memory"):
        stem = stem.removesuffix("-no-memory")
        config = "GEPA"
    for dataset in KNOWN_DATASETS:
        if stem == dataset:
            return dataset, config
    return stem, config


def _load_summary(run_dir: Path) -> dict:
    summary_path = run_dir / "summary.json"
    if not summary_path.exists():
        return {}
    return json.loads(summary_path.read_text(encoding="utf-8"))


def _record_cost(record: dict) -> float:
    usage = record.get("usage") or {}
    return _price_usd(
        str(record.get("model", "")),
        int(usage.get("prompt_tokens") or 0),
        int(usage.get("completion_tokens") or 0),
    )


def _classify_reference_call(record: dict) -> str:
    user_messages = [
        str(message.get("content", "")) for message in record.get("messages", []) if message.get("role") == "user"
    ]
    joined = "\n\n".join(user_messages)

    if "rubric item" in joined and "criteria_met" in joined:
        return "judge"
    if "Admissible actions" in joined:
        return "val_response"
    if "<retrieved_memory>" in joined or "Retrieved information:" in joined or "Based on the above knowledge" in joined:
        return "val_response"
    if "The query must be a JSON object matching this schema" in joined:
        return "val_query"
    if "The KnowledgeItem must conform" in joined:
        return "train_ki"
    return "other"


def _reference_run_name(dataset: str, config: str) -> str:
    suffix = "vanilla-rag" if config == "GEPA + Vector Search" else "no-memory"
    return f"t1-{dataset}-{suffix}"


def load_reference_cost(outputs_dir: Path, dataset: str, config: str) -> ReferenceCost | None:
    run_name = _reference_run_name(dataset, config)
    llm_dir = outputs_dir / run_name / "llm_calls"
    if not llm_dir.exists():
        return None

    costs_by_kind: dict[str, float] = {}
    counts_by_kind: dict[str, int] = {}
    total_cost = 0.0

    for json_path in llm_dir.rglob("*.json"):
        if json_path.name == "failed_cases.json":
            continue
        try:
            record = json.loads(json_path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(record, dict):
            continue

        kind = _classify_reference_call(record)
        cost = _record_cost(record)
        counts_by_kind[kind] = counts_by_kind.get(kind, 0) + 1
        costs_by_kind[kind] = costs_by_kind.get(kind, 0.0) + cost
        total_cost += cost

    train_items = counts_by_kind.get("train_ki", 0)
    val_items = max(
        counts_by_kind.get("val_query", 0),
        counts_by_kind.get("val_response", 0),
        1,
    )
    if train_items == 0:
        return None

    train_cost = costs_by_kind.get("train_ki", 0.0)
    val_cost = total_cost - train_cost
    return ReferenceCost(
        run=run_name,
        train_cost_per_item=train_cost / train_items,
        val_cost_per_item=val_cost / val_items,
        train_items=train_items,
        val_items=val_items,
        total_cost=total_cost,
    )


def average_recorded_reflection_cost(outputs_dir: Path) -> float | None:
    costs: list[float] = []
    for json_path in outputs_dir.glob("t1-*-ours/llm_calls/**/reflect_*.json"):
        try:
            record = json.loads(json_path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        cost = _record_cost(record)
        if cost > 0:
            costs.append(cost)
    if not costs:
        return None
    return sum(costs) / len(costs)


def _pipeline_pairs(log_text: str) -> list[tuple[int, int]]:
    return [
        (int(train), int(val))
        for train, val in re.findall(
            r"Pipeline: offline \(batch KI ingestion\), train=(\d+), val=(\d+)",
            log_text,
        )
    ]


def scan_run(run_dir: Path, *, reflection_cost_per_proposal: float | None) -> GEPACallCounts:
    dataset, config = _parse_run_name(run_dir.name)
    summary = _load_summary(run_dir)
    gepa = summary.get("gepa") or {}
    final_eval = summary.get("final_evaluation") or {}
    candidates = final_eval.get("candidates") or []
    final_score = candidates[0].get("final_score") if candidates else None

    log_path = run_dir / "run_log.txt"
    log_text = log_path.read_text(encoding="utf-8", errors="ignore") if log_path.exists() else ""
    pairs = _pipeline_pairs(log_text)
    train_item_evals = sum(train for train, _val in pairs)
    val_item_evals = sum(val for _train, val in pairs)
    proposals = len(re.findall(r"Proposed new text for", log_text))
    full_val_evals = len(re.findall(r"Base program full valset|Valset score for new program", log_text))

    metric_calls = int(gepa.get("total_metric_calls") or summary.get("total_iterations") or val_item_evals or 0)
    candidate_count = int(gepa.get("candidates_explored") or summary.get("pool_size") or 0)

    # Lower bound: every offline evaluation emits one knowledge-item generation
    # call per train item and one query-generation call per val item. Default QA
    # and rubric scorers add response/judge calls; ALFWorld adds action calls.
    search_task_calls_lower_bound = train_item_evals + val_item_evals
    reference = load_reference_cost(run_dir.parent, dataset, config)
    estimated_eval_cost_usd = None
    estimated_reflection_cost_usd = None
    estimated_total_cost_usd = None
    cost_reference_run = None
    if reference is not None:
        estimated_eval_cost_usd = (
            train_item_evals * reference.train_cost_per_item + val_item_evals * reference.val_cost_per_item
        )
        cost_reference_run = reference.run
    if reflection_cost_per_proposal is not None:
        estimated_reflection_cost_usd = proposals * reflection_cost_per_proposal
    if estimated_eval_cost_usd is not None and estimated_reflection_cost_usd is not None:
        estimated_total_cost_usd = estimated_eval_cost_usd + estimated_reflection_cost_usd

    return GEPACallCounts(
        run=run_dir.name,
        dataset=dataset,
        config=config,
        metric_calls=metric_calls,
        proposals=proposals,
        candidates=candidate_count,
        eval_batches=len(pairs),
        full_val_evals=full_val_evals,
        train_item_evals=train_item_evals,
        val_item_evals=val_item_evals,
        search_task_calls_lower_bound=search_task_calls_lower_bound,
        estimated_eval_cost_usd=estimated_eval_cost_usd,
        estimated_reflection_cost_usd=estimated_reflection_cost_usd,
        estimated_total_cost_usd=estimated_total_cost_usd,
        cost_reference_run=cost_reference_run,
        final_score=final_score,
    )


def _sort_key(row: GEPACallCounts) -> tuple[int, int]:
    dataset_order = {name: i for i, name in enumerate(KNOWN_DATASETS)}
    config_order = {"GEPA + Vector Search": 0, "GEPA": 1}
    return (dataset_order.get(row.dataset, 99), config_order.get(row.config, 99))


def print_markdown(rows: list[GEPACallCounts]) -> None:
    print(
        "| Benchmark | Config | Proposals | Candidates | Metric calls | Eval batches | "
        "Full-val evals | Train item evals | Val item evals | Search task calls >= | "
        "Est. eval $ | Est. refl. $ | Est. total $ | Final score |"
    )
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for row in rows:
        score = "" if row.final_score is None else f"{row.final_score:.3f}"
        eval_cost = "" if row.estimated_eval_cost_usd is None else f"${row.estimated_eval_cost_usd:.2f}"
        reflection_cost = (
            "" if row.estimated_reflection_cost_usd is None else f"${row.estimated_reflection_cost_usd:.2f}"
        )
        total_cost = "" if row.estimated_total_cost_usd is None else f"${row.estimated_total_cost_usd:.2f}"
        print(
            f"| {DATASET_DISPLAY.get(row.dataset, row.dataset)} | {row.config} | "
            f"{row.proposals} | {row.candidates} | {row.metric_calls} | {row.eval_batches} | "
            f"{row.full_val_evals} | {row.train_item_evals} | {row.val_item_evals} | "
            f"{row.search_task_calls_lower_bound} | {eval_cost} | {reflection_cost} | {total_cost} | {score} |"
        )


def print_latex(rows: list[GEPACallCounts]) -> None:
    print(r"\begin{tabular}{llrrrrrrrrr}")
    print(r"\toprule")
    print(
        r"\textbf{Benchmark} & \textbf{Config} & \textbf{Prop.} & \textbf{Cand.} & "
        r"\textbf{Metric} & \textbf{Eval} & \textbf{Full-val} & \textbf{Train} & \textbf{Val} & "
        r"\textbf{Est. \$} \\"
    )
    print(r"\midrule")
    for row in rows:
        total_cost = "---" if row.estimated_total_cost_usd is None else f"\\${row.estimated_total_cost_usd:.2f}"
        print(
            f"{DATASET_DISPLAY.get(row.dataset, row.dataset)} & {row.config} & "
            f"{row.proposals} & {row.candidates} & {row.metric_calls} & "
            f"{row.eval_batches} & {row.full_val_evals} & {row.train_item_evals} & {row.val_item_evals} & "
            f"{total_cost} \\\\"
        )
    print(r"\bottomrule")
    print(r"\end{tabular}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outputs-dir", type=Path, default=Path("outputs"))
    parser.add_argument("--format", choices=["markdown", "latex"], default="markdown")
    parser.add_argument(
        "--reflection-cost-per-proposal",
        type=float,
        default=None,
        help=(
            "Estimated cost per GEPA reflection proposal. Defaults to the mean recorded "
            "t1-*-ours reflector call cost under --outputs-dir."
        ),
    )
    args = parser.parse_args()

    run_dirs = sorted(d for d in args.outputs_dir.glob("gepa-*") if d.is_dir())
    reflection_cost = args.reflection_cost_per_proposal
    if reflection_cost is None:
        reflection_cost = average_recorded_reflection_cost(args.outputs_dir)
    rows = sorted(
        (scan_run(d, reflection_cost_per_proposal=reflection_cost) for d in run_dirs),
        key=_sort_key,
    )

    if args.format == "latex":
        print_latex(rows)
    else:
        print_markdown(rows)


if __name__ == "__main__":
    main()
