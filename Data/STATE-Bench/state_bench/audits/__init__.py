"""Unified audit framework for all benchmark domains.

Public API:
    run_pre_audit(domain, single_task=None) -> AuditReport
    run_post_audit(domain, num_runs=3, single_task=None, runs_dir=None) -> AuditReport
    get_domain_audit_config(domain) -> DomainAuditConfig
"""

from __future__ import annotations

from pathlib import Path

from state_bench.audits._types import AuditReport, DomainAuditConfig


def get_domain_audit_config(name: str) -> DomainAuditConfig:
    """Factory — lazy-imports domain audit config to avoid circular imports."""
    if name == "travel":
        from domains.travel.audit_config import get_audit_config

        return get_audit_config()
    if name == "customer_support":
        from domains.customer_support.audit_config import get_audit_config

        return get_audit_config()
    if name == "shopping_assistant":
        from domains.shopping_assistant.audit_config import get_audit_config

        return get_audit_config()
    raise ValueError(f"Unknown domain: {name!r}. Available: travel, customer_support, shopping_assistant")


def run_pre_audit(domain: str, single_task: str | None = None) -> AuditReport:
    """Run all pre-run audit checks for a domain."""
    from state_bench.audits.pre import run_pre_checks

    cfg = get_domain_audit_config(domain)
    return run_pre_checks(domain, cfg, single_task=single_task)


def run_post_audit(
    domain: str,
    num_runs: int = 3,
    single_task: str | None = None,
    runs_dir: Path | None = None,
    llm_review: bool = False,
    max_llm_tasks: int | None = None,
    failure_attribution: bool = False,
) -> AuditReport:
    """Run all post-run audit checks for a domain."""
    from state_bench.audits.post import run_post_checks

    cfg = get_domain_audit_config(domain)
    return run_post_checks(
        domain,
        cfg,
        num_runs=num_runs,
        single_task=single_task,
        runs_dir=runs_dir,
        llm_review=llm_review,
        max_llm_tasks=max_llm_tasks,
        failure_attribution=failure_attribution,
    )
