"""Format audit reports as text or JSON."""

from __future__ import annotations

import json

from state_bench.audits._types import AuditReport, Severity


def print_text_report(report: AuditReport) -> None:
    """Print a human-readable audit report to stdout."""
    phase_label = "pre-run" if report.phase == "pre" else "post-run"

    print("=" * 72)
    print(f"AUDIT REPORT — {report.domain} ({phase_label})")
    print("=" * 72)
    print()
    print(f"{'CHECK':<40} {'STATUS':<10} {'ISSUES':>8}")
    print("-" * 72)

    total_c = total_m = total_w = total_i = 0

    for i, check in enumerate(report.checks, 1):
        c_count = sum(1 for f in check.findings if f.severity == Severity.CRITICAL)
        m_count = sum(1 for f in check.findings if f.severity == Severity.MODERATE)
        w_count = sum(1 for f in check.findings if f.severity == Severity.MINOR)
        i_count = sum(1 for f in check.findings if f.severity == Severity.INFO)
        total_c += c_count
        total_m += m_count
        total_w += w_count
        total_i += i_count

        if c_count > 0:
            status = "FAIL"
        elif m_count > 0:
            status = "WARN"
        elif w_count > 0:
            status = "WARN"
        else:
            status = "PASS"

        issue_count = len(check.findings)
        print(f"  {i:>2}. {check.check_name:<36} {status:<10} {issue_count:>8}")

    print("-" * 72)
    print(f"  {'TOTAL':<39} {'':10} C={total_c} M={total_m} W={total_w} I={total_i}")
    print("=" * 72)

    # Details for any findings
    all_findings = report.all_findings
    if all_findings:
        print(f"\nDetails ({len(all_findings)} issues):\n")
        for f in all_findings:
            label = f"[{f.task_id}]" if f.task_id else "[global]"
            print(f"  [{f.severity.value}] {label:<35} {f.message}")

    print()
    if report.passed:
        print("AUDIT PASSED.")
    else:
        crit_count = sum(1 for f in all_findings if f.severity == Severity.CRITICAL)
        print(f"AUDIT FAILED — {crit_count} critical issue(s) found.")


def print_json_report(report: AuditReport) -> None:
    """Print machine-readable JSON audit report to stdout."""
    print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
