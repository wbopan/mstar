"""STATE-Bench benchmark — multi-turn task completion through STATE-Bench v0.4.0.

Renders task annotations into a deterministic D-full `raw_text` (zero LLM cost,
ground truth included) and runs each item through STATE-Bench's pure-Python
orchestrator with a custom `MstarKBAgent` whose `prepare_conversation` hook
injects the mstar KB result.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from mstar.datasets import register_dataset
from mstar.evolution.types import DataItem, Dataset

DEFAULT_DATA_DIR = "Data/STATE-Bench"
DEFAULT_DOMAINS = ("customer_support", "travel", "shopping_assistant")


def _render_d_full(task: dict[str, Any]) -> str:
    """Render a STATE-Bench task definition into the D-full template.

    D-full is a deterministic flat string with:
    - Header line `# Task: <task_id>`
    - The full `task_summary` markdown text (already includes `**Task:**` /
      `**Challenge:**` sections in upstream files)
    - MUST / MUST NOT requirement lists from `task_requirements`
    - State requirement lines `- <entity_type>.<record_key>.<field><pad> = <value>`
      with a per-task computed pad so the `=` column aligns
    - opening_message

    Returns a single string suitable for use as `DataItem.raw_text`.
    """
    parts: list[str] = []
    parts.append(f"# Task: {task.get('task_id', '<unknown>')}")
    parts.append("")

    summary = task.get("task_summary") or ""
    if summary:
        parts.append(summary.strip())
        parts.append("")

    reqs = task.get("task_requirements") or []
    musts = [r for r in reqs if (r.get("kind") or "").lower() == "must"]
    must_nots = [r for r in reqs if (r.get("kind") or "").lower() == "must_not"]

    if musts:
        parts.append("MUST:")
        for r in musts:
            parts.append(f"- {r.get('requirement', '')}")
        parts.append("")
    if must_nots:
        parts.append("MUST NOT:")
        for r in must_nots:
            parts.append(f"- {r.get('requirement', '')}")
        parts.append("")

    state = task.get("state_requirements") or []
    if state:
        # Per-task computed padding so `=` aligns across lines.
        keys = [
            f"{s.get('entity_type', '')}.{s.get('record_key', '')}.{s.get('field', '')}"
            for s in state
        ]
        pad = max((len(k) for k in keys), default=0)
        parts.append("Final state:")
        for s, full_key in zip(state, keys, strict=True):
            value = s.get("expected_value", "")
            parts.append(f"- {full_key}{' ' * (pad - len(full_key))} = {value!r}")
        parts.append("")

    opening = task.get("opening_message")
    if opening:
        parts.append(f"User opens with: {opening}")

    return "\n".join(parts).rstrip() + "\n"


def _render_question(task: dict[str, Any]) -> str:
    """Render the question string used as `DataItem.question`.

    Deterministic; includes task_id (so failed-case logs are easy to grep) and
    the opening_message (or task_summary as fallback) so the agent has the
    starting context the orchestrator will inject.
    """
    task_id = task.get("task_id", "<unknown>")
    opening = (task.get("opening_message") or "").strip()
    if not opening:
        opening = (task.get("task_summary") or "").strip()
    return f"[{task_id}] {opening}"


def _stratified_half_split(items: list, seed: int = 0) -> tuple[list, list]:
    """Deterministic 50/50 split. Returns (a, b) preserving original order within each half."""
    rng = random.Random(seed)
    indices = list(range(len(items)))
    rng.shuffle(indices)
    half = len(indices) // 2
    a_idx = sorted(indices[:half])
    b_idx = sorted(indices[half:])
    return [items[i] for i in a_idx], [items[i] for i in b_idx]


def _load_task_dict(task_path: Path) -> dict[str, Any]:
    return json.loads(task_path.read_text())


def _build_data_item(task: dict[str, Any], *, domain: str, task_path: Path) -> DataItem:
    return DataItem(
        raw_text=_render_d_full(task),
        question=_render_question(task),
        expected_answer="",  # state_bench has no string answer; scoring is state+requirements based
        metadata={
            "task_id": task.get("task_id"),
            "domain": domain,
            "task_path": str(task_path),
        },
    )


def _read_split_ids(splits_path: Path) -> tuple[list[str], list[str]]:
    """Parse a STATE-Bench splits/train_test_v1.json file.

    Splits live nested under the `splits` key:
        {"domain": ..., "version": ..., "splits": {"train": [...], "test": [...]}, ...}
    """
    raw = json.loads(splits_path.read_text())
    splits = raw.get("splits", {})
    return list(splits.get("train", [])), list(splits.get("test", []))


@register_dataset("state_bench")
def load_state_bench(
    *,
    data_dir: str | Path = DEFAULT_DATA_DIR,
    domain: str | None = None,
    seed: int = 0,
    category: str | None = None,  # noqa: ARG001 — accepted for API compatibility, unused
) -> Dataset:
    """Load STATE-Bench tasks as an mstar Dataset.

    Splits: official 100 train -> 50 train + 50 val (deterministic by seed).
            official 50 test  -> kept as-is.
    Set ``domain`` to restrict to one of customer_support / travel / shopping_assistant.
    """
    data_root = Path(data_dir)
    domains: tuple[str, ...] = (domain,) if domain else DEFAULT_DOMAINS

    train_items: list[DataItem] = []
    val_items: list[DataItem] = []
    test_items: list[DataItem] = []

    for d in domains:
        dom_root = data_root / "domains" / d
        splits_path = dom_root / "splits" / "train_test_v1.json"
        if not splits_path.exists():
            raise FileNotFoundError(
                f"STATE-Bench splits file not found: {splits_path}. "
                f"Did Task 0 (vendor + extract) complete?"
            )
        official_train, official_test = _read_split_ids(splits_path)
        train_ids, val_ids = _stratified_half_split(official_train, seed=seed)

        for tid in train_ids:
            tp = dom_root / "tasks" / f"{tid}.json"
            train_items.append(_build_data_item(_load_task_dict(tp), domain=d, task_path=tp))
        for tid in val_ids:
            tp = dom_root / "tasks" / f"{tid}.json"
            val_items.append(_build_data_item(_load_task_dict(tp), domain=d, task_path=tp))
        for tid in official_test:
            tp = dom_root / "tasks" / f"{tid}.json"
            test_items.append(_build_data_item(_load_task_dict(tp), domain=d, task_path=tp))

    # val_scorer wired in Task 6/7. Loader returns None for now so this task is
    # testable in isolation.
    return Dataset(
        train=train_items,
        val=val_items,
        test=test_items,
        compare_fn=None,
        val_scorer=None,
    )
