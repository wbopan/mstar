"""STATE-Bench benchmark — multi-turn task completion through STATE-Bench v0.4.0.

Renders task annotations into a deterministic D-full `raw_text` (zero LLM cost,
ground truth included) and runs each item through STATE-Bench's pure-Python
orchestrator with a custom `MstarKBAgent` whose `prepare_conversation` hook
injects the mstar KB result.
"""

from __future__ import annotations

from typing import Any


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
