"""
HERMES Pre-Commit Security Scanner
Called by .git/hooks/pre-commit to scan staged files for PII and secrets.

Usage:
    python scripts/pre_commit_scan.py <file1> <file2> ...
"""

import subprocess
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core_logic.security_agent import SecurityAgent, SeverityLevel


def get_staged_content(filepath: str) -> str:
    """Get the staged version of a file (what will actually be committed)."""
    result = subprocess.run(
        ["git", "show", f":{filepath}"],
        capture_output=True, text=True, cwd=str(project_root)
    )
    return result.stdout


def main():
    files = sys.argv[1:]
    if not files:
        sys.exit(0)

    agent = SecurityAgent(str(project_root))
    all_issues = []

    # Binary file extensions to skip
    skip_extensions = {
        '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.svg',
        '.woff', '.woff2', '.ttf', '.eot', '.otf',
        '.zip', '.tar', '.gz', '.bz2', '.7z',
        '.exe', '.dll', '.so', '.dylib',
        '.pyc', '.pyo', '.pkl', '.npz',
        '.tflite', '.onnx', '.pb', '.h5',
        '.mp3', '.mp4', '.wav', '.avi', '.mov',
        '.pdf', '.doc', '.docx', '.xls', '.xlsx',
        '.toe', '.tox',
    }

    for filepath in files:
        ext = Path(filepath).suffix.lower()
        if ext in skip_extensions:
            continue

        content = get_staged_content(filepath)
        if not content:
            continue

        issues = agent.check_staged_content(content, filepath)
        all_issues.extend(issues)

    if not all_issues:
        print("[HERMES Security] Pre-commit scan passed.")
        sys.exit(0)

    # Report issues
    critical_count = sum(1 for i in all_issues if i.severity == SeverityLevel.CRITICAL)
    high_count = sum(1 for i in all_issues if i.severity == SeverityLevel.HIGH)

    print(f"\n[HERMES Security] Found {len(all_issues)} issue(s) in staged files:\n")

    for issue in all_issues:
        severity_tag = issue.severity.value.upper()
        print(f"  [{severity_tag}] {issue.title}")
        print(f"    File: {issue.file_path}:{issue.line_number}")
        print(f"    {issue.description}")
        if issue.code_snippet:
            print(f"    Line: {issue.code_snippet}")
        print(f"    Fix: {issue.recommendation}")
        print()

    # Block on critical or high issues
    if critical_count > 0 or high_count > 0:
        sys.exit(1)

    # Warn but allow on medium/low
    print("[HERMES Security] Warnings found but commit is allowed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
