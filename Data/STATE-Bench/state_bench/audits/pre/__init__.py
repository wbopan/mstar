"""Pre-run audit orchestrator."""

from __future__ import annotations

from state_bench.audits._loader import load_finalized_generation_results, load_task_environment_jsons, load_tasks
from state_bench.audits._types import AuditReport, DomainAuditConfig
from state_bench.audits.pre import crossref, distribution, solvability, structural


def run_pre_checks(
    domain: str,
    cfg: DomainAuditConfig,
    single_task: str | None = None,
) -> AuditReport:
    """Run all pre-run audit checks for a domain."""
    tasks = load_tasks(domain, single_task)
    task_envs = load_task_environment_jsons(tasks)
    env_indexes_by_task = {task_id: cfg.build_env_index(raw) for task_id, raw in task_envs.items()}

    report = AuditReport(domain=domain, phase="pre")

    if single_task is None:
        report.checks.append(structural.check_file_count(tasks, cfg))
    report.checks.append(structural.check_schema(tasks, cfg))
    report.checks.append(structural.check_duplicate_ids(tasks, cfg))
    report.checks.append(structural.check_placeholders(tasks, cfg))
    report.checks.append(structural.check_task_done(tasks, cfg))
    report.checks.append(structural.check_task_summary_completeness(tasks, cfg))

    report.checks.append(crossref.check_user_ids(tasks, env_indexes_by_task, cfg))
    report.checks.append(crossref.check_entity_crossrefs(tasks, env_indexes_by_task, cfg))
    report.checks.append(crossref.check_entity_ownership(tasks, env_indexes_by_task, cfg))

    if single_task is None:
        report.checks.append(distribution.check_family_coverage(tasks, cfg))
        report.checks.append(distribution.check_category_distribution(tasks, cfg))

    finalized = load_finalized_generation_results(domain, single_task=single_task)
    if finalized:
        report.checks.append(solvability.check_info_path(tasks, finalized, env_indexes_by_task, cfg))
        report.checks.append(solvability.check_replay_sequence(tasks, finalized, cfg))
        if cfg.policy_gate_map:
            report.checks.append(solvability.check_policy_gate(tasks, finalized, cfg))
        report.checks.append(solvability.check_simulator_info(tasks, finalized, cfg))

    if cfg.policy_math_verifier:
        report.checks.append(cfg.policy_math_verifier())

    return report
