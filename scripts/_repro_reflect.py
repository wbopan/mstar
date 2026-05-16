"""Reproduce a single reflect call from a saved state.json checkpoint, with timing
and prompt-size instrumentation. Used to diagnose why the production reflect was
hanging while standalone gpt-5.1 probes returned in seconds.

Usage:
    uv run python scripts/_repro_reflect.py <output_dir>
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    out_dir = Path(sys.argv[1])

    # Configure mstar exactly like __main__ does
    from mstar.cache import configure_cache
    from mstar.evolution.azure_config import configure_azure_auth

    configure_cache("disk")
    configure_azure_auth(
        models=["azure/gpt-5.1", "azure/gpt-5.4-mini"],
        azure_api_base="http://127.0.0.1:4000",
        azure_api_version="2025-03-01-preview",
    )

    # Load state
    state = json.loads((out_dir / "state.json").read_text())
    pool_entries = state["pool"]
    # Pick best entry as parent (matches softmax selection ~most likely pick)
    parent_entry = max(pool_entries, key=lambda e: e.get("eval_result", {}).get("score", 0))
    parent_score = parent_entry["eval_result"]["score"]
    parent_name = parent_entry["name"]
    parent_code_path = out_dir / "programs" / f"{parent_name}.py"
    parent_code = parent_code_path.read_text()
    eval_result = parent_entry["eval_result"]

    print(f"Parent score: {parent_score}")
    print(f"Parent code length: {len(parent_code):,} chars")
    print(f"Failed cases: {len(eval_result['failed_cases'])}")
    print(f"Train examples: {len(eval_result.get('train_examples') or [])}")

    # Build the reflection prompt the same way reflector.py does
    from mstar.evolution.prompts import ReflectionPromptConfig, build_reflection_user_prompt

    failed_dicts = [
        {
            "question": fc["question"],
            "output": fc["output"],
            "rationale": fc["rationale"],
            "score": fc["score"],
            "conversation_history": fc.get("conversation_history") or [],
            "memory_logs": fc.get("memory_logs") or [],
        }
        for fc in eval_result["failed_cases"][:3]  # reflection_max_failed_cases=3
    ]
    success_dicts = [
        {
            "question": sc["question"],
            "output": sc["output"],
            "rationale": sc["rationale"],
            "score": sc["score"],
            "conversation_history": sc.get("conversation_history") or [],
            "memory_logs": sc.get("memory_logs") or [],
        }
        for sc in (eval_result.get("success_cases") or [])[:3]
    ]
    # train_examples in build_reflection_user_prompt is unused when None or empty;
    # easier to skip than reconstruct the dataclass shape.
    train_examples = None

    user_prompt = build_reflection_user_prompt(
        code=parent_code,
        score=parent_score,
        failed_cases=failed_dicts,
        iteration=1,
        train_examples=train_examples,
        config=ReflectionPromptConfig(),
        success_cases=success_dicts,
        references=None,
        lineage_log=None,
    )

    print(f"\n=== Reflect prompt size: {len(user_prompt):,} chars ===")
    print(f"First 200 chars:\n{user_prompt[:200]!r}")
    print(f"Last 200 chars:\n{user_prompt[-200:]!r}")

    print(f"\n=== Calling completion_with_retry (reflect_model=azure/gpt-5.1, reasoning=high) ===")
    from mstar.evolution.toolkit import completion_with_retry

    t0 = time.monotonic()
    response = completion_with_retry(
        model="azure/gpt-5.1",
        messages=[
            {"role": "system", "content": " "},
            {"role": "user", "content": user_prompt},
        ],
        caching=True,
        reasoning_effort="high",
    )
    dt = time.monotonic() - t0
    out_text = response.choices[0].message.content or ""
    print(f"\n=== Done in {dt:.1f}s ===")
    print(f"Output length: {len(out_text):,} chars")
    print(f"Output first 200:\n{out_text[:200]!r}")


if __name__ == "__main__":
    main()
