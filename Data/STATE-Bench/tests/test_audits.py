from state_bench.audits import get_domain_audit_config
from state_bench.audits._types import (
    DEFAULT_REQUIRED_SIMULATOR_FIELDS,
    DEFAULT_REQUIRED_TOP_FIELDS,
)
from state_bench.audits.pre.distribution import check_family_coverage
from state_bench.audits.pre.solvability import check_policy_gate


def test_domain_audit_configs_use_shared_structural_defaults() -> None:
    for domain in ("travel", "customer_support", "shopping_assistant"):
        cfg = get_domain_audit_config(domain)
        assert cfg.required_top_fields == DEFAULT_REQUIRED_TOP_FIELDS
        assert cfg.required_simulator_fields == DEFAULT_REQUIRED_SIMULATOR_FIELDS


def test_travel_and_shopping_audit_configs_load_scenarios() -> None:
    for domain in ("travel", "shopping_assistant"):
        cfg = get_domain_audit_config(domain)
        assert cfg.load_scenarios is not None
        scenarios = cfg.load_scenarios()
        assert scenarios
        sample_task_id = sorted(scenarios)[0]
        assert scenarios[sample_task_id]["task_id"]


def test_customer_support_policy_gate_uses_canonical_replay_step_labels() -> None:
    cfg = get_domain_audit_config("customer_support")
    tasks = [{"task_id": "1-sample"}]
    scenarios = {
        "1-sample": {
            "replay_trace": [
                {"name": "get_policies", "label": "refund"},
                {"name": "process_refund", "label": "Issue refund"},
            ]
        }
    }

    result = check_policy_gate(tasks, scenarios, cfg)
    assert result.findings == []


def test_customer_support_policy_gate_fails_without_required_policy_topic() -> None:
    cfg = get_domain_audit_config("customer_support")
    tasks = [{"task_id": "1-sample"}]
    scenarios = {
        "1-sample": {
            "replay_trace": [
                {"name": "get_policies", "label": "warranty"},
                {"name": "process_refund", "label": "Issue refund"},
            ]
        }
    }

    result = check_policy_gate(tasks, scenarios, cfg)
    assert len(result.findings) == 1
    assert "process_refund" in result.findings[0].message
    assert "refund" in result.findings[0].message


def test_shopping_distribution_checks_cleanly_opt_out() -> None:
    cfg = get_domain_audit_config("shopping_assistant")
    result = check_family_coverage([], cfg)
    assert result.findings == []
