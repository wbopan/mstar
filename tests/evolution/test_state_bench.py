"""Tests for mstar.benchmarks.state_bench."""

from __future__ import annotations

import pytest


def _sample_task_dict() -> dict:
    """A minimal but realistic task definition mirroring 1-return_partial_order's shape."""
    return {
        "task_id": "1-return_partial_order",
        "task_summary": (
            "**Task:** The customer wants to return only the headphones from a "
            "discounted three-item order.\n\n"
            "**Challenge:** Agent must redistribute SAVE20 across remaining items, "
            "not refund $249 flat."
        ),
        "task_requirements": [
            {
                "id": "preview_then_confirm",
                "kind": "must",
                "requirement": "Agent must preview before confirming.",
                "evidence": "conversation",
            },
            {
                "id": "no_full_cancel",
                "kind": "must_not",
                "requirement": "Cancel the entire order.",
                "evidence": "tool_calls",
            },
        ],
        "state_requirements": [
            {
                "entity_type": "orders",
                "record_key": "ORD-6001",
                "field": "status",
                "expected_value": "partially_returned",
            },
            {
                "entity_type": "orders",
                "record_key": "ORD-6001",
                "field": "refund_amount",
                "expected_value": 141,
            },
            {
                "entity_type": "orders",
                "record_key": "ORD-6001",
                "field": "restocking_fee",
                "expected_value": 37,
            },
        ],
        "opening_message": "Hi, I'd like to return the headphones from order ORD-6001.",
        "user_simulator": {"personality": "polite"},
    }


def test_render_d_full_contains_task_summary_text():
    from mstar.benchmarks.state_bench import _render_d_full

    out = _render_d_full(_sample_task_dict())
    assert "wants to return only the headphones" in out
    assert "redistribute SAVE20" in out


def test_render_d_full_lists_requirements_with_must_must_not():
    from mstar.benchmarks.state_bench import _render_d_full

    out = _render_d_full(_sample_task_dict())
    assert "MUST" in out
    assert "MUST NOT" in out
    assert "Agent must preview before confirming." in out
    assert "Cancel the entire order." in out


def test_render_d_full_state_lines_are_column_aligned():
    """State-requirement lines should align the `=` column."""
    from mstar.benchmarks.state_bench import _render_d_full

    out = _render_d_full(_sample_task_dict())
    lines = [ln for ln in out.splitlines() if ln.startswith("- orders.ORD-6001")]
    assert len(lines) == 3
    eq_columns = [ln.index("=") for ln in lines]
    assert len(set(eq_columns)) == 1, f"= column drifts across state lines: {eq_columns}"


def test_render_d_full_includes_opening_message():
    from mstar.benchmarks.state_bench import _render_d_full

    out = _render_d_full(_sample_task_dict())
    assert "Hi, I'd like to return the headphones" in out


def test_render_d_full_handles_minimal_task():
    """No requirements, no state — should not raise."""
    from mstar.benchmarks.state_bench import _render_d_full

    minimal = {
        "task_id": "x",
        "task_summary": "**Task:** Do nothing.",
        "task_requirements": [],
        "state_requirements": [],
        "opening_message": "hi",
        "user_simulator": {},
    }
    out = _render_d_full(minimal)
    assert "Do nothing." in out
    assert "hi" in out
