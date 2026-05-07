from state_bench.audits.post.attribution import (
    TaskAudit,
    _attribute_trajectory,
    _audit_state_requirement_references,
    _check_policy_and_preview_sequence,
)
from state_bench.audits import get_domain_audit_config


def _task(state_requirements=None, task_requirements=None):
    return {
        "task_id": "1-return_partial_order",
        "task_summary": "Task: return one item and refund it.",
        "task_requirements": task_requirements or [],
        "user_id": "cust_002",
        "now": "2026-06-12T10:00:00",
        "opening_message": "Return item ITEM-9001 from order ORD-6001.",
        "user_simulator": {
            "personality": "polite",
            "user_sim_context": "Customer wants a return.",
            "known_info": [],
            "unknown_info": [],
            "task_rules": [],
        },
        "task_env_path": "domains/customer_support/task_envs/1-return_partial_order.json",
        "state_requirements": state_requirements or [],
    }


def test_policy_and_preview_sequence_flags_confirm_before_preview():
    cfg = get_domain_audit_config("customer_support")
    issues = _check_policy_and_preview_sequence(
        [
            {"name": "get_policies", "arguments": {"topic": "return"}},
            {
                "name": "process_return",
                "arguments": {"item_id": "ITEM-9001", "reason": "changed_mind", "confirm": True},
                "result": {"error": "Must preview return before confirming."},
            },
        ],
        cfg,
    )

    assert any("confirm=true called before preview" in issue for issue in issues)
    assert any("returned error/rejected" in issue for issue in issues)


def test_cancel_preview_key_matches_order_level_preview():
    cfg = get_domain_audit_config("customer_support")
    issues = _check_policy_and_preview_sequence(
        [
            {"name": "get_policies", "arguments": {"topic": "cancellation"}},
            {"name": "cancel_order", "arguments": {"order_id": "ORD-1", "item_ids": [], "confirm": False}},
            {
                "name": "cancel_order",
                "arguments": {"order_id": "ORD-1", "item_ids": ["ITEM-1"], "confirm": True},
            },
        ],
        cfg,
    )

    assert not issues


def test_created_replay_record_is_valid_state_requirement_reference():
    audit = TaskAudit("exchange")
    _audit_state_requirement_references(
        {
            "state_requirements": [
                {
                    "entity_type": "order_items",
                    "record_key": "ITEM-2",
                    "field": "item_status",
                    "expected_value": "confirmed",
                }
            ]
        },
        {"order_items": [{"item_id": "ITEM-1"}]},
        audit,
        {"order_items": {"ITEM-2"}},
    )

    assert audit.valid


def test_missing_write_on_failed_action_task_is_agent_error():
    cfg = get_domain_audit_config("customer_support")
    state_requirements = [
        {
            "entity_type": "orders",
            "record_key": "ORD-6001",
            "field": "status",
            "expected_value": "partially_returned",
        },
        {
            "entity_type": "order_items",
            "record_key": "ITEM-9001",
            "field": "item_status",
            "expected_value": "returned",
        },
        {
            "entity_type": "order_items",
            "record_key": "ITEM-9001",
            "field": "return_reason",
            "expected_value": "changed_mind",
        },
        {
            "entity_type": "order_items",
            "record_key": "ITEM-9001",
            "field": "restocking_fee",
            "expected_value": 37,
        },
        {
            "entity_type": "order_items",
            "record_key": "ITEM-9001",
            "field": "refund_amount",
            "expected_value": 141,
        },
        {
            "entity_type": "order_items",
            "record_key": "ITEM-9001",
            "field": "refund_method",
            "expected_value": "original_payment",
        },
    ]
    task = _task(state_requirements=state_requirements)
    traj = {
        "task_id": "1-return_partial_order",
        "_run": "run1",
        "task_completion_pass": 0,
        "state_requirements_met": 0,
        "task_requirements_met": 1,
        "state_diff": {"created": {}, "modified": {}, "deleted": {}},
        "conversation": [],
        "task_requirements_reasoning": "Agent did not process the return.",
    }

    result = _attribute_trajectory(
        "customer_support",
        cfg,
        traj,
        {"1-return_partial_order": task},
        {"1-return_partial_order": TaskAudit("1-return_partial_order")},
    )

    assert result.label == "AGENT_ERROR"
    assert any("did not call any write tool" in reason for reason in result.reasons)


def test_invalid_task_short_circuits_to_task_bug():
    cfg = get_domain_audit_config("customer_support")
    task = _task()
    audit = TaskAudit("1-return_partial_order")
    audit.add_issue("state requirements", "canonical replay mismatch", "Fix expected state.")

    result = _attribute_trajectory(
        "customer_support",
        cfg,
        {
            "task_id": "1-return_partial_order",
            "_run": "run1",
            "task_completion_pass": 0,
            "state_requirements_met": 0,
            "task_requirements_met": 0,
            "state_diff": {"created": {}, "modified": {}, "deleted": {}},
            "conversation": [],
        },
        {"1-return_partial_order": task},
        {"1-return_partial_order": audit},
    )

    assert result.label == "TASK_BUG"
    assert result.fix_recommendation == "Fix expected state."


def test_passing_action_without_write_is_false_pass():
    cfg = get_domain_audit_config("customer_support")
    task = _task(task_requirements=[{"id": "x", "type": "must", "requirement": "Agent must process a refund."}])

    result = _attribute_trajectory(
        "customer_support",
        cfg,
        {
            "task_id": "1-return_partial_order",
            "_run": "run1",
            "task_completion_pass": 1,
            "state_requirements_met": 1,
            "task_requirements_met": 1,
            "state_diff": {"created": {}, "modified": {}, "deleted": {}},
            "conversation": [],
        },
        {"1-return_partial_order": task},
        {"1-return_partial_order": TaskAudit("1-return_partial_order")},
    )

    assert result.label == "FALSE_PASS"
    assert any("without any write tool" in reason for reason in result.reasons)


def test_passing_task_with_tool_sequence_issue_remains_pass():
    cfg = get_domain_audit_config("customer_support")
    state_requirements = [
        {
            "entity_type": "orders",
            "record_key": "ORD-6001",
            "field": "status",
            "expected_value": "partially_returned",
        },
        {
            "entity_type": "order_items",
            "record_key": "ITEM-9001",
            "field": "item_status",
            "expected_value": "returned",
        },
        {
            "entity_type": "order_items",
            "record_key": "ITEM-9001",
            "field": "return_reason",
            "expected_value": "changed_mind",
        },
        {
            "entity_type": "order_items",
            "record_key": "ITEM-9001",
            "field": "restocking_fee",
            "expected_value": 37,
        },
        {
            "entity_type": "order_items",
            "record_key": "ITEM-9001",
            "field": "refund_amount",
            "expected_value": 141,
        },
        {
            "entity_type": "order_items",
            "record_key": "ITEM-9001",
            "field": "refund_method",
            "expected_value": "original_payment",
        },
    ]
    task = _task(state_requirements=state_requirements)

    result = _attribute_trajectory(
        "customer_support",
        cfg,
        {
            "task_id": "1-return_partial_order",
            "_run": "run1",
            "task_completion_pass": 1,
            "state_requirements_met": 1,
            "task_requirements_met": 1,
            "state_diff": {
                "created": {},
                "modified": {
                    "orders": {
                        "ORD-6001": {
                            "status": {"old": "delivered", "new": "partially_returned"},
                        }
                    },
                    "order_items": {
                        "ITEM-9001": {
                            "item_status": {"old": "delivered", "new": "returned"},
                            "return_reason": {"old": None, "new": "changed_mind"},
                            "restocking_fee": {"old": None, "new": 37},
                            "refund_amount": {"old": None, "new": 141},
                            "refund_method": {"old": None, "new": "original_payment"},
                        }
                    }
                },
                "deleted": {},
            },
            "conversation": [
                {
                    "role": "assistant",
                    "tool_calls": [
                        {"name": "get_policies", "arguments": {"topic": "return"}, "result": {"topic": "return"}},
                        {
                            "name": "process_return",
                            "arguments": {"item_id": "ITEM-9001", "reason": "changed_mind", "confirm": True},
                            "result": {"error": "Must preview return before confirming. Call without confirm first."},
                        },
                        {
                            "name": "process_return",
                            "arguments": {"item_id": "ITEM-9001", "reason": "changed_mind", "confirm": False},
                            "result": {"status": "preview", "item_id": "ITEM-9001"},
                        },
                        {
                            "name": "process_return",
                            "arguments": {"item_id": "ITEM-9001", "reason": "changed_mind", "confirm": True},
                            "result": {"status": "returned", "item_id": "ITEM-9001"},
                        },
                    ],
                }
            ],
        },
        {"1-return_partial_order": task},
        {"1-return_partial_order": TaskAudit("1-return_partial_order")},
    )

    assert result.label == "PASS"
    assert result.deterministic_checks["tool_sequence_issues"]


def test_passing_denial_without_state_or_write_is_not_false_pass():
    cfg = get_domain_audit_config("customer_support")
    task = _task(task_requirements=[{"id": "x", "type": "must", "requirement": "Agent must explain no action needed."}])
    task["task_summary"] = "Customer asks to cancel an already cancelled order; no action needed."

    result = _attribute_trajectory(
        "customer_support",
        cfg,
        {
            "task_id": "1-return_partial_order",
            "_run": "run1",
            "task_completion_pass": 1,
            "state_requirements_met": 1,
            "task_requirements_met": 1,
            "state_diff": {"created": {}, "modified": {}, "deleted": {}},
            "conversation": [],
        },
        {"1-return_partial_order": task},
        {"1-return_partial_order": TaskAudit("1-return_partial_order")},
    )

    assert result.label == "PASS"
