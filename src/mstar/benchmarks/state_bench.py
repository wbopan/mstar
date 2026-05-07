"""STATE-Bench benchmark — multi-turn task completion through STATE-Bench v0.4.0.

Renders task annotations into a deterministic D-full `raw_text` (zero LLM cost,
ground truth included) and runs each item through STATE-Bench's pure-Python
orchestrator with a custom `MstarKBAgent` whose `prepare_conversation` hook
injects the mstar KB result.
"""

from __future__ import annotations

import concurrent.futures
import json
import random
import sys
import threading
import traceback
from pathlib import Path
from typing import Any

from mstar.datasets import register_dataset
from mstar.evolution.evaluator import RuntimeViolationError
from mstar.evolution.types import DataItem, Dataset

DEFAULT_DATA_DIR = "Data/STATE-Bench"
DEFAULT_DOMAINS = ("customer_support", "travel", "shopping_assistant")

_INIT_LOCK = threading.Lock()
_INITIALIZED = False
_DEFAULT_JUDGE_REASONING = "low"


class StateBenchInfraError(RuntimeViolationError):
    """Infrastructure failure during a STATE-Bench task (proxy/network/Azure).

    MUST inherit RuntimeViolationError so the evaluator's existing infra-error
    handling (evaluator.py:552, 666) catches it. Subclassing RuntimeError
    directly will crash the evolution run.
    """


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

    return Dataset(
        train=train_items,
        val=val_items,
        test=test_items,
        compare_fn=None,
        val_scorer=StateBenchValScorer(),
    )


def _ensure_state_bench_initialized() -> None:
    """Idempotent: append vendored Data/STATE-Bench to sys.path + load .env once.

    Double-checked locking: cheap fast-path read, locked slow-path init. Safe
    under threads (we run tasks via ThreadPoolExecutor).
    """
    global _INITIALIZED
    if _INITIALIZED:
        return
    with _INIT_LOCK:
        if _INITIALIZED:
            return
        vendor_root = Path(DEFAULT_DATA_DIR).resolve()
        if str(vendor_root) not in sys.path:
            sys.path.insert(0, str(vendor_root))

        env_path = vendor_root / ".env"
        if env_path.exists():
            try:
                from dotenv import load_dotenv
            except ImportError as exc:
                raise StateBenchInfraError(
                    "python-dotenv is required for STATE-Bench. "
                    "Install with: uv sync --extra state-bench"
                ) from exc
            load_dotenv(env_path, override=False)
        _INITIALIZED = True


def _looks_like_infra_error(exc: BaseException) -> bool:
    """True if the exception is an openai/network/proxy infrastructure issue."""
    try:
        import openai
    except ImportError:
        return False
    return isinstance(
        exc,
        (
            openai.APIConnectionError,
            openai.APITimeoutError,
            openai.RateLimitError,
            openai.InternalServerError,
        ),
    )


def _build_pooled_client() -> Any:
    """Construct a STATE-Bench PooledLLMClient. Surfaces infra failures cleanly."""
    try:
        from state_bench.client import PooledLLMClient
    except ImportError as exc:
        raise StateBenchInfraError(f"STATE-Bench import failed: {exc}") from exc
    try:
        return PooledLLMClient()
    except Exception as exc:
        if _looks_like_infra_error(exc):
            raise StateBenchInfraError(f"PooledLLMClient init failed: {exc}") from exc
        raise


def _extract_tool_calls(conversation: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pull tool_calls list from a STATE-Bench conversation.

    The conversation is the Responses API input array — function_call items
    appear as raw output items in the conversation. The orchestrator's run_task
    builds these as dicts; we mirror scripts/run_task.py's extraction.
    """
    out: list[dict[str, Any]] = []
    for msg in conversation:
        if isinstance(msg, dict):
            tc = msg.get("tool_calls")
            if tc:
                out.extend(tc)
    return out


def _run_single_task(
    item: DataItem,
    kb_text: str,
    task_model: str,  # noqa: ARG001 — STATE-Bench routes via PooledLLMClient + AZURE_OPENAI_DEPLOYMENTS env
    reasoning_effort: str | None,
) -> tuple[str, float, str]:
    """Run one STATE-Bench task and return (transcript, score, rationale).

    Score: ``state_pass@1 ∧ task_requirements_pass@1`` -> 1.0 or 0.0.
    Infra exceptions become ``StateBenchInfraError``; other exceptions bubble
    up to the scorer which records them as model failures.
    """
    _ensure_state_bench_initialized()

    try:
        from state_bench.domain import get_domain_config
        from state_bench.env_loader import load_task_environment
        from state_bench.orchestrator import run_task
        from state_bench.schemas import TaskDefinition
        from state_bench.scoring import (
            TaskRequirementsJudge,
            combine_task_completion,
            evaluate_state_requirements,
        )
        from agents.base import AgentRuntimeContext
        from agents.mstar_kb_agent import MstarKBAgent
    except ImportError as exc:
        raise StateBenchInfraError(f"STATE-Bench import failed: {exc}") from exc

    try:
        task_path = Path(item.metadata["task_path"])
        domain_name = item.metadata["domain"]
        task = TaskDefinition.load(task_path)
        domain = get_domain_config(domain_name)
        env_data, _env_path = load_task_environment(domain, task)

        client = _build_pooled_client()

        agent_system_prompt = domain.agent_system_prompt.format(
            now=task.now, user_id=task.user_id
        )
        env = domain.environment_class(env_data.deep_copy(), now=task.now)

        runtime_ctx = AgentRuntimeContext(
            task_id=task.task_id,
            user_id=task.user_id,
            domain=domain.name,
            now=task.now,
            task_summary=task.task_summary,
            state_requirements=task.state_requirements,
            task_requirements=task.task_requirements,
        )

        agent = MstarKBAgent(
            client=client,
            system_prompt=agent_system_prompt,
            tools=domain.tool_schemas,
            tool_handlers=env.tool_handlers,
            runtime_context=runtime_ctx,
            kb_text=kb_text,
        )

        trajectory = run_task(
            task,
            env_data,
            task.user_id,
            client,
            domain=domain,
            agent=agent,
            env=env,
        )

        # Score state (deterministic) + task requirements (LLM judge)
        trajectory.state_requirements_score = evaluate_state_requirements(task, trajectory.state_diff)
        tool_calls = _extract_tool_calls(trajectory.conversation)
        judge = TaskRequirementsJudge(
            client=client,
            prompts_dir=domain.prompts_dir,
            system_prompt=domain.judge_system_prompt,
            reasoning_effort=reasoning_effort or _DEFAULT_JUDGE_REASONING,
        )
        trajectory.task_requirements_score = judge.evaluate(
            task, trajectory.conversation, tool_calls, trajectory.state_diff
        )
        trajectory.task_completion_pass = combine_task_completion(
            trajectory.state_requirements_score, trajectory.task_requirements_score
        )

        score = 1.0 if trajectory.task_completion_pass == 1 else 0.0
        transcript = json.dumps(trajectory.conversation, indent=2, default=str)
        state_pass = (
            trajectory.state_requirements_score.score
            if trajectory.state_requirements_score
            else None
        )
        reqs_pass = (
            trajectory.task_requirements_score.score
            if trajectory.task_requirements_score
            else None
        )
        rationale = (
            f"state_pass={state_pass} task_reqs_pass={reqs_pass} "
            f"completion={trajectory.task_completion_pass}"
        )
        return (transcript, score, rationale)
    except StateBenchInfraError:
        raise
    except Exception as exc:
        if _looks_like_infra_error(exc):
            raise StateBenchInfraError(
                f"infra failure during task {item.metadata.get('task_id')}: {exc}"
            ) from exc
        raise


class StateBenchValScorer:
    """val_scorer for STATE-Bench. One thread per task with bounded timeout.

    Concurrency uses ``ThreadPoolExecutor`` with a try/finally + ``shutdown(wait=False,
    cancel_futures=True)`` exit. Do NOT use ``with`` — ``__exit__`` calls
    ``shutdown(wait=True)`` and hangs forever on a stuck Azure thread.
    """

    def __init__(self, max_workers: int = 8, task_timeout: float = 600.0) -> None:
        self.max_workers = max_workers
        self.task_timeout = task_timeout

    def score_batch(
        self,
        items: list[DataItem],
        retrieved: list[str],
        task_model: str,
        instruction_response: str,  # noqa: ARG002 — required by ValScorer protocol, unused
        always_on_knowledge: str = "",  # noqa: ARG002 — same
        *,
        reasoning_effort: str | None = None,
    ) -> list[tuple[str, float, str]]:
        if not items:
            return []
        workers = min(self.max_workers, len(items))
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=workers)
        results: list[tuple[str, float, str] | None] = [None] * len(items)
        try:
            futures = {
                executor.submit(_run_single_task, item, retrieved[i], task_model, reasoning_effort): i
                for i, item in enumerate(items)
            }
            for fut in concurrent.futures.as_completed(futures, timeout=None):
                idx = futures[fut]
                try:
                    results[idx] = fut.result(timeout=self.task_timeout)
                except StateBenchInfraError:
                    raise
                except concurrent.futures.TimeoutError:
                    results[idx] = (
                        f"task timed out after {self.task_timeout}s",
                        0.0,
                        f"STATE-Bench task. Hit per-task timeout ({self.task_timeout}s).",
                    )
                except Exception as exc:
                    tb = traceback.format_exc()
                    results[idx] = (
                        f"task crashed: {exc}\n{tb}",
                        0.0,
                        f"STATE-Bench task. Model-side exception: {exc}",
                    )
        finally:
            # Do NOT use `with ThreadPoolExecutor(...)` — its __exit__ calls
            # shutdown(wait=True) which hangs forever on stuck Azure threads.
            executor.shutdown(wait=False, cancel_futures=True)

        return [
            r if r is not None else ("missing result", 0.0, "scorer bug: result not populated")
            for r in results
        ]
