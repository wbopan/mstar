"""Post-run audit orchestrator."""

from __future__ import annotations

from pathlib import Path

from state_bench.audits._loader import load_task_jsons_by_id, load_trajectories
from state_bench.audits._types import AuditReport, DomainAuditConfig
from state_bench.audits.post import classification, efficiency, trajectory


def run_post_checks(
    domain: str,
    cfg: DomainAuditConfig,
    num_runs: int = 3,
    single_task: str | None = None,
    runs_dir: Path | None = None,
    llm_review: bool = False,
    max_llm_tasks: int | None = None,
    failure_attribution: bool = False,
) -> AuditReport:
    """Run all post-run audit checks for a domain."""
    trajectories = load_trajectories(domain, runs_dir=runs_dir, num_runs=num_runs, single_task=single_task)
    task_jsons = load_task_jsons_by_id(domain, single_task)

    report = AuditReport(domain=domain, phase="post")

    if not trajectories:
        from state_bench.audits._types import AuditFinding, CheckResult, Severity

        result = CheckResult(check_name="Trajectory loading")
        result.findings.append(AuditFinding(Severity.MINOR, "Trajectory loading", None, "No trajectory files found"))
        report.checks.append(result)
        return report

    # Phase 1: Trajectory structure validation
    report.checks.append(trajectory.check_trajectory_structure(trajectories, cfg))
    report.checks.append(trajectory.check_termination(trajectories, cfg))
    report.checks.append(trajectory.check_state_diff_consistency(trajectories, task_jsons, cfg))
    report.checks.append(trajectory.check_task_summary_vs_state_diff(trajectories, task_jsons, cfg))

    # Phase 2: False pass / false fail classification
    report.checks.append(classification.check_false_passes(trajectories, task_jsons, cfg))
    report.checks.append(classification.check_false_fails(trajectories, task_jsons, cfg))

    # Phase 3: Efficiency (optional)
    if cfg.optimal_baselines:
        report.checks.append(efficiency.check_efficiency(trajectories, cfg))

    if failure_attribution:
        from state_bench.audits.post.attribution import run_failure_attribution_audit

        report.checks.append(
            run_failure_attribution_audit(
                domain=domain,
                cfg=cfg,
                trajectories=trajectories,
                task_jsons=task_jsons,
                runs_dir=runs_dir,
                attribution_date="4_24_2026" if domain == "customer_support" else None,
            )
        )

    # Phase 4: LLM-based trajectory review (optional, expensive)
    # Collect deterministic mismatches flagged for LLM classification
    if llm_review:
        from state_bench.audits.post.llm_review import check_llm_review

        deterministic_flags: dict[str, list[str]] = {}
        for check in report.checks:
            for finding in check.findings:
                if finding.details.get("needs_llm_review") and finding.task_id:
                    deterministic_flags.setdefault(finding.task_id, []).append(finding.message)

        report.checks.append(
            check_llm_review(
                trajectories,
                task_jsons,
                cfg,
                max_tasks=max_llm_tasks,
                deterministic_flags=deterministic_flags,
            )
        )

    return report
