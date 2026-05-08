"""One-off: rewrite the bloated `output` fields in an mstar state.json + iter_*/failed_cases.json
into compact transcripts, so a partially-completed evolution run can resume without
hauling 9 KB Responses-API JSON dumps into the reflect prompt.

Usage:
    uv run python scripts/_compact_state_outputs.py <output_dir>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

from mstar.benchmarks.state_bench import _build_compact_transcript


def _compact_output(question: str, output: str) -> str:
    """Re-render a full-JSON `output` field as a compact transcript.

    Falls back to a hard char-truncation if the output isn't parseable JSON
    (e.g. it's already a compact transcript or a short error message).
    """
    if not output or len(output) < 1000:
        return output  # already compact or trivially small
    try:
        conversation = json.loads(output)
    except json.JSONDecodeError:
        return output[:2000]
    if not isinstance(conversation, list):
        return output[:2000]
    # Question shape from _render_question: "[<task_id>] ..."
    task_id = "<unknown>"
    if isinstance(question, str) and question.startswith("[") and "]" in question:
        task_id = question[1 : question.index("]")]
    task = SimpleNamespace(task_id=task_id)
    trajectory = SimpleNamespace(conversation=conversation)
    return _build_compact_transcript(task, trajectory)


def _process_failed_cases(cases: list[dict]) -> tuple[int, int]:
    """Mutate cases in place; return (before_total, after_total) char counts."""
    before = sum(len(c.get("output") or "") for c in cases)
    for c in cases:
        c["output"] = _compact_output(c.get("question") or "", c.get("output") or "")
    after = sum(len(c.get("output") or "") for c in cases)
    return before, after


def main() -> None:
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    out_dir = Path(sys.argv[1])
    state_path = out_dir / "state.json"
    if not state_path.exists():
        print(f"No state.json at {state_path}", file=sys.stderr)
        sys.exit(1)

    state = json.loads(state_path.read_text())
    total_before = total_after = 0
    for entry in state.get("pool", []):
        for key in ("eval_result", "reflection_result"):
            er = entry.get(key)
            if er and "failed_cases" in er:
                b, a = _process_failed_cases(er["failed_cases"])
                total_before += b
                total_after += a
    state_path.write_text(json.dumps(state))
    print(f"state.json: rewrote {total_before:,} -> {total_after:,} chars in failed_cases output fields")

    for fc_path in (out_dir / "llm_calls").rglob("failed_cases.json"):
        cases = json.loads(fc_path.read_text())
        if isinstance(cases, list):
            b, a = _process_failed_cases(cases)
            fc_path.write_text(json.dumps(cases, indent=2))
            print(f"{fc_path}: {b:,} -> {a:,} chars")


if __name__ == "__main__":
    main()
