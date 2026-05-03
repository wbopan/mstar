#!/usr/bin/env python3
"""Audit paper appendix numbers against local experiment artifacts.

The script is intentionally conservative.
It reports source values, role counts, token totals, and known paper-value
conflicts without trying to decide author intent.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PAPER = ROOT / "paper"
OUT = ROOT / "outputs"
GENERATED = PAPER / "generated"


MAIN_RUNS = {
    "locomo": "t1-locomo-ours",
    "alfworld_unseen": "t1-alfworld-unseen-ours",
    "alfworld_seen": "t1-alfworld-seen-ours",
    "healthbench_data": "t1-hb-data-tasks-ours",
    "healthbench_emergency": "t1-hb-emergency-ours",
    "prbench_legal": "t1-pr-legal-ours",
    "prbench_finance": "t1-pr-finance-ours",
}

BASELINE_RUNS = {
    "locomo_vector_search": "t1-locomo-vanilla-rag",
    "locomo_no_memory": "t1-locomo-no-memory",
    "alfworld_unseen_vector_search": "t1-alfworld-unseen-vanilla-rag",
    "alfworld_unseen_no_memory": "t1-alfworld-unseen-no-memory",
    "alfworld_seen_vector_search": "t1-alfworld-seen-vanilla-rag",
    "alfworld_seen_no_memory": "t1-alfworld-seen-no-memory",
    "healthbench_emergency_vector_search": "t1-hb-emergency-vanilla-rag",
    "healthbench_emergency_no_memory": "t1-hb-emergency-no-memory",
    "healthbench_data_vector_search": "t1-hb-data-tasks-vanilla-rag",
    "healthbench_data_no_memory": "t1-hb-data-tasks-no-memory",
    "prbench_legal_vector_search": "t1-pr-legal-vanilla-rag",
    "prbench_legal_no_memory": "t1-pr-legal-no-memory",
    "prbench_finance_vector_search": "t1-pr-finance-vanilla-rag",
    "prbench_finance_no_memory": "t1-pr-finance-no-memory",
}

STABILITY_RUNS = {
    "locomo": [
        "t1-locomo-ours",
        "stability-locomo-eseed1",
        "stability-locomo-eseed2",
        "stability-locomo-eseed3",
        "stability-locomo-eseed4",
    ],
    "healthbench_data": [
        "t1-hb-data-tasks-ours",
        "stability-hb-data-eseed1",
        "stability-hb-data-eseed2",
        "stability-hb-data-eseed3",
        "stability-hb-data-eseed4",
    ],
    "prbench_finance": [
        "t1-pr-finance-ours",
        "stability-pr-finance-eseed1",
        "stability-pr-finance-eseed2",
        "stability-pr-finance-eseed3",
        "stability-pr-finance-eseed4",
    ],
}

PAPER_VALUES = {
    "main_results": {
        "locomo_f1": 0.459,
        "locomo_llm_judge": 0.610,
        "alfworld_unseen": 0.881,
        "alfworld_seen": 0.700,
        "healthbench_data": 0.390,
        "healthbench_emergency": 0.493,
        "prbench_legal": 0.660,
        "prbench_finance": 0.586,
    },
    "appendix_structural": {
        "locomo": 0.408,
        "alfworld_unseen": 0.881,
        "healthbench_emergency": 0.493,
        "healthbench_data": 0.390,
        "prbench_legal": 0.660,
        "prbench_finance": 0.586,
    },
}

MODEL_PRICES = {
    "gpt-5.4-mini": (0.75, 4.50),
    "azure/gpt-5.4-mini": (0.75, 4.50),
    "gpt-5.3-codex": (1.75, 14.00),
    "azure/gpt-5.3-codex": (1.75, 14.00),
}


def load_json(path: Path) -> Any:
    with path.open() as f:
        return json.load(f)


def final_score(summary: dict[str, Any]) -> float | None:
    final_evaluation = summary.get("final_evaluation") or {}
    candidates = final_evaluation.get("candidates", [])
    best_hash = summary.get("best_program_hash")
    for candidate in candidates:
        if candidate.get("hash") == best_hash:
            return candidate.get("final_score")
    if candidates:
        return candidates[0].get("final_score")
    test_evaluation = summary.get("test_evaluation") or {}
    if "score" in test_evaluation:
        return test_evaluation.get("score")
    if "best_score" in summary and summary.get("total_iterations") == 0:
        return summary.get("best_score")
    return None


def best_extra_metrics(summary: dict[str, Any]) -> dict[str, Any]:
    best_hash = summary.get("best_program_hash")
    final_evaluation = summary.get("final_evaluation") or {}
    metrics = final_evaluation.get("extra_metrics", {})
    return metrics.get(best_hash, {})


def best_category_scores(summary: dict[str, Any]) -> dict[str, Any]:
    best_hash = summary.get("best_program_hash")
    final_evaluation = summary.get("final_evaluation") or {}
    metrics = final_evaluation.get("category_scores", {})
    return metrics.get(best_hash, {})


def read_run(run_name: str, *, include_cost: bool = False) -> dict[str, Any]:
    run_dir = OUT / run_name
    if not run_dir.exists():
        return {"run": run_name, "missing": True}
    config = load_json(run_dir / "config.json") if (run_dir / "config.json").exists() else {}
    summary = load_json(run_dir / "summary.json") if (run_dir / "summary.json").exists() else {}
    return {
        "run": run_name,
        "path": str(run_dir.relative_to(ROOT)),
        "config": {
            "dataset": config.get("dataset"),
            "iterations": config.get("iterations"),
            "test_size": config.get("test_size"),
            "eval_static_size": config.get("eval_static_size"),
            "eval_rotate_size": config.get("eval_rotate_size"),
            "eval_train_ratio": config.get("eval_train_ratio"),
            "seed": config.get("seed"),
            "evolution_seed": config.get("evolution_seed"),
            "dataset_kwargs": config.get("dataset_kwargs"),
            "task_model": config.get("task_model"),
            "reflect_model": config.get("reflect_model"),
            "toolkit_model": config.get("toolkit_model"),
            "judge_model": config.get("judge_model"),
        },
        "summary": {
            "best_validation_score": summary.get("best_score"),
            "best_program_hash": summary.get("best_program_hash"),
            "best_program_generation": summary.get("best_program_generation"),
            "final_score": final_score(summary),
            "extra_metrics": best_extra_metrics(summary),
            "category_scores": best_category_scores(summary),
            "score_history_len": len(summary.get("score_history", [])),
        },
        "program": summarize_program(summary.get("best_program_source", "")),
        "cost": summarize_llm_calls(run_dir) if include_cost else {"skipped": True},
    }


def summarize_program(source: str) -> dict[str, Any]:
    if not source:
        return {}
    logic_lines = []
    in_logic = False
    for line in source.splitlines():
        if re.match(r"\s+def (write|read)\(", line):
            in_logic = True
        elif in_logic and re.match(r"\s+def \w+\(", line):
            in_logic = False
        if in_logic and line.strip() and not line.lstrip().startswith("#"):
            logic_lines.append(line)
    knowledge_match = re.search(r"class\s+KnowledgeItem\b([\s\S]*?)\n\n(?:@dataclass\n)?class\s+Query\b", source)
    schema_fields = (
        len(re.findall(r"^\s{4}[A-Za-z_][A-Za-z0-9_]*\s*:", knowledge_match.group(1), re.M))
        if knowledge_match
        else None
    )
    return {
        "total_lines": len(source.splitlines()),
        "logic_lines_approx": len(logic_lines),
        "uses_sqlite": "sqlite" in source.lower() or "toolkit.db" in source,
        "uses_chromadb": "chroma" in source.lower(),
        "llm_in_read": bool(
            re.search(r"def read[\s\S]*?(toolkit\.llm_completion|self\.toolkit\.llm_completion)", source)
        ),
        "schema_fields": schema_fields,
    }


def iter_llm_raw(run_dir: Path):
    calls_dir = run_dir / "llm_calls"
    if not calls_dir.exists():
        return
    for path in calls_dir.rglob("*.json"):
        try:
            text = path.read_text(errors="replace")
        except Exception:
            continue
        yield path, text


def raw_json_string(text: str, key: str) -> str:
    m = re.search(rf'"{re.escape(key)}"\s*:\s*"([^"]*)"', text)
    return m.group(1) if m else ""


def raw_json_int(text: str, key: str) -> int:
    m = re.search(rf'"{re.escape(key)}"\s*:\s*(\d+)', text)
    return int(m.group(1)) if m else 0


def classify_role(path: Path, text: str) -> str:
    stripped = text.lstrip()
    if stripped.startswith("["):
        return "failed_case_log"
    phase = raw_json_string(text, "phase")
    model = raw_json_string(text, "model")
    lowered = text.lower()
    name = path.name.lower()
    if phase == "reflect" or "codex" in model:
        return "reflector"
    if "rubric item" in lowered or "score the last turn" in lowered or "criteria" in name:
        return "judge"
    if "bge-m3" in model or "embedding" in model:
        return "embedding"
    if "you are controlling a text-based alfworld environment" in lowered:
        return "task_agent"
    if "the knowledgeitem must conform" in lowered:
        return "task_agent"
    if "the query must conform" in lowered:
        return "task_agent"
    if "based on the above knowledge" in lowered:
        return "task_agent"
    if "synthesize memory retrieval" in lowered or "retrieved memories" in lowered:
        return "toolkit"
    if phase == "train":
        return "unclassified_train"
    return "unclassified"


def usage_tokens(text: str) -> tuple[int, int, int]:
    prompt = raw_json_int(text, "prompt_tokens") or raw_json_int(text, "input_tokens")
    completion = raw_json_int(text, "completion_tokens") or raw_json_int(text, "output_tokens")
    total = raw_json_int(text, "total_tokens") or prompt + completion
    return prompt, completion, total


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    prices = MODEL_PRICES.get(model)
    if prices is None:
        return 0.0
    in_price, out_price = prices
    return (prompt_tokens / 1_000_000) * in_price + (completion_tokens / 1_000_000) * out_price


def summarize_llm_calls(run_dir: Path) -> dict[str, Any]:
    role_counts: Counter[str] = Counter()
    role_usage = defaultdict(lambda: {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
    model_counts: Counter[str] = Counter()
    model_usage = defaultdict(
        lambda: {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "estimated_cost": 0.0}
    )
    no_usage = 0
    list_logs = 0
    total_logs = 0
    for path, text in iter_llm_raw(run_dir) or []:
        total_logs += 1
        if text.lstrip().startswith("["):
            list_logs += 1
            role_counts["failed_case_log"] += 1
            continue
        role = classify_role(path, text)
        role_counts[role] += 1
        model = raw_json_string(text, "model") or "unknown"
        model_counts[model] += 1
        prompt, completion, total = usage_tokens(text)
        if total == 0:
            no_usage += 1
        role_usage[role]["prompt_tokens"] += prompt
        role_usage[role]["completion_tokens"] += completion
        role_usage[role]["total_tokens"] += total
        model_usage[model]["prompt_tokens"] += prompt
        model_usage[model]["completion_tokens"] += completion
        model_usage[model]["total_tokens"] += total
        model_usage[model]["estimated_cost"] += estimate_cost(model, prompt, completion)
    return {
        "total_logs": total_logs,
        "call_logs": total_logs - list_logs,
        "failed_case_logs": list_logs,
        "no_usage_logs": no_usage,
        "role_counts": dict(sorted(role_counts.items())),
        "role_usage": dict(sorted(role_usage.items())),
        "model_counts": dict(sorted(model_counts.items())),
        "model_usage": {
            model: {
                **usage,
                "estimated_cost": round(usage["estimated_cost"], 4),
            }
            for model, usage in sorted(model_usage.items())
        },
        "estimated_cost": round(sum(v["estimated_cost"] for v in model_usage.values()), 4),
    }


def stability_summary() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, runs in STABILITY_RUNS.items():
        scores = []
        rows = []
        missing = []
        for run_name in runs:
            path = OUT / run_name / "summary.json"
            if not path.exists():
                missing.append(run_name)
                rows.append({"run": run_name, "missing": True})
                continue
            summary = load_json(path)
            score = final_score(summary)
            scores.append(score)
            rows.append(
                {
                    "run": run_name,
                    "best_validation_score": summary.get("best_score"),
                    "final_score": score,
                    "best_program_hash": summary.get("best_program_hash"),
                }
            )
        valid_scores = [s for s in scores if s is not None]
        mean = sum(valid_scores) / len(valid_scores) if valid_scores else None
        std = (
            math.sqrt(sum((s - mean) ** 2 for s in valid_scores) / len(valid_scores))
            if valid_scores and mean is not None
            else None
        )
        cv = (std / mean * 100) if mean else None
        out[key] = {
            "runs": rows,
            "missing_runs": missing,
            "mean": mean,
            "std": std,
            "cv_percent": cv,
        }
    return out


def find_locomo_0459() -> dict[str, Any]:
    hits = []
    patterns = ["0.459", "0.458", "0.460"]
    for path in OUT.rglob("summary.json"):
        try:
            text = path.read_text()
        except Exception:
            continue
        for pattern in patterns:
            if pattern in text:
                hits.append(str(path.relative_to(ROOT)))
                break
    return {"summary_hits": hits}


def warnings(report: dict[str, Any]) -> list[str]:
    result = []
    locomo_output = report["main_runs"]["locomo"]["summary"]["final_score"]
    locomo_paper = PAPER_VALUES["main_results"]["locomo_f1"]
    if locomo_output is not None and round(locomo_output, 3) != round(locomo_paper, 3):
        result.append(
            f"LoCoMo main-table value {locomo_paper:.3f} differs from output final score {locomo_output:.3f}."
        )
    if report["stability"]["prbench_finance"]["missing_runs"]:
        result.append(
            "PRBench Finance stability table uses five seeds, but local outputs are missing: "
            + ", ".join(report["stability"]["prbench_finance"]["missing_runs"])
            + "."
        )
    alf_seen_categories = report["main_runs"]["alfworld_seen"]["summary"]["category_scores"]
    if alf_seen_categories and "pick_and_place_with_movable_recep" not in alf_seen_categories:
        result.append(
            "ALFWorld Seen final summary has no movable-receptacle category; appendix category table should explain the 46/50 displayed count."
        )
    seen_no_memory = report["baseline_runs"].get("alfworld_seen_no_memory", {})
    embedding_tokens = (
        seen_no_memory.get("cost", {}).get("model_usage", {}).get("openrouter/baai/bge-m3", {}).get("prompt_tokens", 0)
    )
    if embedding_tokens:
        result.append(
            f"ALFWorld Seen No Memory includes {embedding_tokens:,} BGE-M3 embedding input tokens; separate these from priced GPT tokens."
        )
    elif seen_no_memory.get("cost", {}).get("skipped"):
        result.append("Cost scan skipped in quick mode; run with --with-cost before regenerating the cost table.")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--with-cost", action="store_true", help="Scan llm_calls directories. This is slower.")
    args = parser.parse_args()
    report: dict[str, Any] = {
        "main_runs": {key: read_run(run, include_cost=args.with_cost) for key, run in MAIN_RUNS.items()},
        "baseline_runs": {key: read_run(run, include_cost=args.with_cost) for key, run in BASELINE_RUNS.items()},
        "stability": stability_summary(),
        "paper_values": PAPER_VALUES,
        "locomo_0459_search": find_locomo_0459(),
        "cost_scan": "full" if args.with_cost else "skipped",
    }
    report["warnings"] = warnings(report)
    GENERATED.mkdir(parents=True, exist_ok=True)
    out_path = GENERATED / "appendix_audit.json"
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")

    print(f"Wrote {out_path.relative_to(ROOT)}")
    print("\nMain run final scores:")
    for key, run in report["main_runs"].items():
        score = run.get("summary", {}).get("final_score")
        val = run.get("summary", {}).get("best_validation_score")
        print(f"  {key:22s} final={score!r} validation={val!r}")
    print("\nWarnings:")
    for item in report["warnings"]:
        print(f"  - {item}")


if __name__ == "__main__":
    main()
