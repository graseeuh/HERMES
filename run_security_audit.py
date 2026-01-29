"""
Run HERMES Security Audit
Scans the entire HERMES project for security issues, edge cases, and efficiency problems.

Usage:
    python run_security_audit.py [--verbose]
"""

import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from core_logic.security_agent import SecurityAgent, SeverityLevel


def main():
    verbose = '--verbose' in sys.argv or '-v' in sys.argv

    print("=" * 60)
    print("HERMES Security & Quality Audit")
    print("=" * 60)
    print()

    # Initialize security agent
    project_path = Path(__file__).parent
    agent = SecurityAgent(str(project_path))

    print(f"Scanning: {project_path}")
    print("Excluding: venv, __pycache__, .git")
    print()

    # Run audit
    print("Running audit...")
    report = agent.run_full_audit(exclude_dirs=['venv', '__pycache__', '.git', 'node_modules'])

    # Print report
    agent.print_report(report, verbose=verbose)

    # Print file summary
    print("\n" + "=" * 60)
    print("FILE SUMMARY")
    print("=" * 60)
    print(f"{'File':<45} {'Lines':<8} {'Funcs':<8} {'Issues':<8}")
    print("-" * 60)

    for fa in sorted(report.file_audits, key=lambda x: x.line_count, reverse=True):
        rel_path = str(Path(fa.file_path).relative_to(project_path))
        if len(rel_path) > 44:
            rel_path = "..." + rel_path[-41:]
        print(f"{rel_path:<45} {fa.line_count:<8} {fa.function_count:<8} {len(fa.issues):<8}")

    print("-" * 60)
    print(f"{'TOTAL':<45} {report.total_lines:<8} {'-':<8} {report.total_issues:<8}")

    # Exit code based on severity
    if report.critical_issues > 0:
        print("\n[FAIL] CRITICAL issues found. Please fix before running.")
        sys.exit(2)
    elif report.high_issues > 0:
        print("\n[WARN] High severity issues found. Review recommended.")
        sys.exit(1)
    else:
        print("\n[PASS] Audit passed. Safe to run.")
        sys.exit(0)


if __name__ == "__main__":
    main()
