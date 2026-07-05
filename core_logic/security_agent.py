"""
HERMES Security & Quality Assurance Agent
Validates code for security vulnerabilities, edge cases, and efficiency.
"""

import logging
import os
import re
import ast
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class SeverityLevel(Enum):
    """Severity levels for issues."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class IssueCategory(Enum):
    """Categories of issues."""
    SECURITY = "security"
    EDGE_CASE = "edge_case"
    EFFICIENCY = "efficiency"
    ERROR_HANDLING = "error_handling"
    INPUT_VALIDATION = "input_validation"
    RESOURCE_MANAGEMENT = "resource_management"
    CODE_QUALITY = "code_quality"


@dataclass
class SecurityIssue:
    """Represents a security or quality issue."""
    category: IssueCategory
    severity: SeverityLevel
    file_path: str
    line_number: Optional[int]
    title: str
    description: str
    recommendation: str
    code_snippet: Optional[str] = None


@dataclass
class FileAudit:
    """Audit results for a single file."""
    file_path: str
    file_size: int
    line_count: int
    function_count: int
    class_count: int
    import_count: int
    issues: List[SecurityIssue] = field(default_factory=list)
    complexity_score: float = 0.0


@dataclass
class AuditReport:
    """Complete audit report."""
    timestamp: str
    total_files: int
    total_lines: int
    total_issues: int
    critical_issues: int
    high_issues: int
    medium_issues: int
    low_issues: int
    file_audits: List[FileAudit] = field(default_factory=list)
    summary: str = ""


class SecurityAgent:
    """
    Security and quality assurance agent for HERMES.
    Scans code for vulnerabilities, edge cases, and efficiency issues.
    """

    # PII patterns - names, emails, and personal identifiers that must never be committed
    # Load from config file if available, otherwise use defaults
    PII_PATTERNS = {
        'real_names': [],       # populated at runtime from .hermes_security.json
        'email_addresses': [],  # populated at runtime from .hermes_security.json
    }

    # Dangerous patterns to check for
    SECURITY_PATTERNS = {
        'command_injection': {
            'patterns': [
                r'os\.system\s*\(',
                r'subprocess\.call\s*\([^)]*shell\s*=\s*True',
                r'subprocess\.Popen\s*\([^)]*shell\s*=\s*True',
                r'eval\s*\(',
                r'exec\s*\(',
            ],
            'severity': SeverityLevel.CRITICAL,
            'description': 'Potential command injection vulnerability',
            'recommendation': 'Use subprocess with shell=False and pass arguments as list'
        },
        'sql_injection': {
            'patterns': [
                r'execute\s*\(\s*["\'].*%s.*["\'].*%',
                r'execute\s*\(\s*f["\']',
                r'execute\s*\([^)]*\+[^)]*\)',
            ],
            'severity': SeverityLevel.CRITICAL,
            'description': 'Potential SQL injection vulnerability',
            'recommendation': 'Use parameterized queries instead of string formatting'
        },
        'path_traversal': {
            'patterns': [
                r'open\s*\([^)]*\+[^)]*\)',
                r'Path\s*\([^)]*\+[^)]*\)',
            ],
            'severity': SeverityLevel.HIGH,
            'description': 'Potential path traversal vulnerability',
            'recommendation': 'Validate and sanitize file paths, use Path.resolve()'
        },
        'hardcoded_secrets': {
            'patterns': [
                r'password\s*=\s*["\'][^"\']+["\']',
                r'api_key\s*=\s*["\'][^"\']+["\']',
                r'secret\s*=\s*["\'][^"\']+["\']',
                r'token\s*=\s*["\'][A-Za-z0-9]{20,}["\']',
            ],
            'severity': SeverityLevel.HIGH,
            'description': 'Potential hardcoded secret or credential',
            'recommendation': 'Use environment variables or secure credential storage'
        },
        'insecure_deserialization': {
            'patterns': [
                r'pickle\.loads?\s*\(',
                r'yaml\.load\s*\([^)]*\)',  # without Loader argument
            ],
            'severity': SeverityLevel.HIGH,
            'description': 'Insecure deserialization',
            'recommendation': 'Use safe loaders (yaml.safe_load) or avoid pickle for untrusted data'
        }
    }

    # Edge case patterns
    EDGE_CASE_PATTERNS = {
        'missing_none_check': {
            'patterns': [
                r'\.get\s*\([^)]+\)\.',  # chaining after .get() without None check
            ],
            'severity': SeverityLevel.MEDIUM,
            'description': 'Potential None value not handled',
            'recommendation': 'Add None check before accessing attributes'
        },
        'empty_collection': {
            'patterns': [
                r'(?<!\[)\[0\](?!\s*[=:])',  # index access [0] but not slice [:0] or dict key
            ],
            'severity': SeverityLevel.LOW,
            'description': 'Index access without empty check',
            'recommendation': 'Check collection length before index access',
            'exclude_contexts': ['if ', 'while ', 'and ', 'or ', 'len(', '> 0', '>= 1', '!= 0']
        },
        'division_by_zero': {
            'patterns': [
                # Match numeric division: number/var or var/var but NOT Path / (path concat)
                r'(?<![Pp]ath[\(\)\s])(?<!["\'/\w])\s+/\s+(?!/)([a-zA-Z_][a-zA-Z0-9_]*)\s*(?!["\'])',
            ],
            'severity': SeverityLevel.MEDIUM,
            'description': 'Potential division by zero',
            'recommendation': 'Add zero check before division',
            'exclude_contexts': [
                'Path', 'path', 'os.path', 'pathlib',  # Path operations
                '# ', '"""', "'''",  # Comments/docstrings
                'if ', '> 0', '>= 1', '!= 0', '== 0',  # Zero checks
                ' if ', 'else 0', 'else 0.0',  # Ternary zero checks
                '_size', '_count', '_len', 'total_'  # Named variables that are typically checked
            ]
        }
    }

    # Efficiency patterns
    EFFICIENCY_PATTERNS = {
        'nested_loops': {
            'patterns': [
                r'for\s+\w+\s+in\s+.*:\s*\n\s+for\s+\w+\s+in',
            ],
            'severity': SeverityLevel.INFO,
            'description': 'Nested loops detected',
            'recommendation': 'Consider if nested loops can be optimized'
        },
        'repeated_computation': {
            'patterns': [
                r'len\s*\([^)]+\)\s*.*len\s*\(\1\)',  # repeated len() calls
            ],
            'severity': SeverityLevel.LOW,
            'description': 'Repeated computation in loop',
            'recommendation': 'Cache computed values outside loops'
        },
        'string_concatenation_loop': {
            'patterns': [
                r'for\s+.*:\s*\n\s+\w+\s*\+=\s*["\']',
            ],
            'severity': SeverityLevel.LOW,
            'description': 'String concatenation in loop',
            'recommendation': 'Use list and join() for better performance'
        }
    }

    # Error handling patterns to check
    ERROR_HANDLING_PATTERNS = {
        'bare_except': {
            'patterns': [
                r'except\s*:',
            ],
            'severity': SeverityLevel.MEDIUM,
            'description': 'Bare except clause catches all exceptions',
            'recommendation': 'Catch specific exceptions instead of bare except'
        },
        'pass_in_except': {
            'patterns': [
                r'except.*:\s*\n\s+pass',
            ],
            'severity': SeverityLevel.MEDIUM,
            'description': 'Exception silently ignored',
            'recommendation': 'Log or handle the exception appropriately'
        },
        'missing_finally': {
            'patterns': [
                r'try\s*:.*open\s*\((?!.*finally)',
            ],
            'severity': SeverityLevel.LOW,
            'description': 'Resource opened without finally/context manager',
            'recommendation': 'Use context manager (with statement) for resources'
        }
    }

    def __init__(self, project_path: str):
        """
        Initialize the security agent.

        Args:
            project_path: Root path of the project to audit
        """
        self.project_path = Path(project_path)
        self.issues: List[SecurityIssue] = []
        self.file_audits: List[FileAudit] = []
        self._load_pii_config()

    def _load_pii_config(self):
        """Load PII patterns from .hermes_security.json config file."""
        import json
        config_path = self.project_path / '.hermes_security.json'
        if config_path.exists():
            with open(config_path, 'r') as f:
                config = json.load(f)
            self.PII_PATTERNS = {
                'real_names': config.get('blocked_names', []),
                'email_addresses': config.get('blocked_emails', []),
                'blocked_strings': config.get('blocked_strings', []),
            }

    def check_staged_content(self, content: str, filename: str = "<staged>") -> List[SecurityIssue]:
        """
        Scan a string of content for PII and secrets. Used by the pre-commit hook.

        Returns:
            List of SecurityIssue objects found in the content.
        """
        issues = []
        lines = content.split('\n')

        # Check PII patterns
        for name in self.PII_PATTERNS.get('real_names', []):
            if not name:
                continue
            pattern = re.compile(re.escape(name), re.IGNORECASE)
            for i, line in enumerate(lines, 1):
                if pattern.search(line):
                    issues.append(SecurityIssue(
                        category=IssueCategory.SECURITY,
                        severity=SeverityLevel.CRITICAL,
                        file_path=filename,
                        line_number=i,
                        title="PII: Blocked name detected",
                        description=f"Found blocked name in content",
                        recommendation="Remove personal name before committing",
                        code_snippet=line.strip()[:80]
                    ))

        for email in self.PII_PATTERNS.get('email_addresses', []):
            if not email:
                continue
            pattern = re.compile(re.escape(email), re.IGNORECASE)
            for i, line in enumerate(lines, 1):
                if pattern.search(line):
                    issues.append(SecurityIssue(
                        category=IssueCategory.SECURITY,
                        severity=SeverityLevel.CRITICAL,
                        file_path=filename,
                        line_number=i,
                        title="PII: Blocked email detected",
                        description=f"Found blocked email address in content",
                        recommendation="Remove personal email before committing",
                        code_snippet=line.strip()[:80]
                    ))

        for blocked in self.PII_PATTERNS.get('blocked_strings', []):
            if not blocked:
                continue
            pattern = re.compile(re.escape(blocked), re.IGNORECASE)
            for i, line in enumerate(lines, 1):
                if pattern.search(line):
                    issues.append(SecurityIssue(
                        category=IssueCategory.SECURITY,
                        severity=SeverityLevel.CRITICAL,
                        file_path=filename,
                        line_number=i,
                        title="PII: Blocked string detected",
                        description=f"Found blocked content in file",
                        recommendation="Remove blocked content before committing",
                        code_snippet=line.strip()[:80]
                    ))

        # Also check for common secret patterns in the content
        secret_patterns = [
            (r'(?:api[_-]?key|apikey)\s*[:=]\s*["\'][A-Za-z0-9]{16,}["\']', "API key"),
            (r'(?:secret|token|password|passwd|pwd)\s*[:=]\s*["\'][^"\']{8,}["\']', "Hardcoded secret"),
            (r'sk-[A-Za-z0-9]{20,}', "OpenAI/Stripe secret key"),
            (r'ghp_[A-Za-z0-9]{36,}', "GitHub personal access token"),
            (r'-----BEGIN (?:RSA |EC )?PRIVATE KEY-----', "Private key"),
        ]

        for pat, label in secret_patterns:
            for i, line in enumerate(lines, 1):
                if re.search(pat, line, re.IGNORECASE):
                    issues.append(SecurityIssue(
                        category=IssueCategory.SECURITY,
                        severity=SeverityLevel.CRITICAL,
                        file_path=filename,
                        line_number=i,
                        title=f"Secret: {label}",
                        description=f"Potential {label} found in staged content",
                        recommendation="Remove secrets and use environment variables",
                        code_snippet=line.strip()[:80]
                    ))

        issues.extend(self._run_bandit_on_content(content, filename))
        return issues

    def run_full_audit(self, exclude_dirs: List[str] = None) -> AuditReport:
        """
        Run a complete security and quality audit.

        Args:
            exclude_dirs: Directories to exclude (e.g., ['venv', '__pycache__'])

        Returns:
            Complete AuditReport
        """
        exclude_dirs = exclude_dirs or ['venv', '__pycache__', '.git', 'node_modules']
        exclude_set = set(exclude_dirs)

        self.issues = []
        self.file_audits = []

        # Find all Python files
        python_files = self._find_python_files(exclude_set)

        # Audit each file
        for file_path in python_files:
            audit = self._audit_file(file_path)
            self.file_audits.append(audit)
            self.issues.extend(audit.issues)

        # Generate report
        return self._generate_report()

    def _find_python_files(self, exclude_dirs: Set[str]) -> List[Path]:
        """Find all Python files in the project."""
        python_files = []

        for root, dirs, files in os.walk(self.project_path):
            # Remove excluded directories
            dirs[:] = [d for d in dirs if d not in exclude_dirs]

            for file in files:
                if file.endswith('.py'):
                    python_files.append(Path(root) / file)

        return python_files

    def _audit_file(self, file_path: Path) -> FileAudit:
        """Audit a single Python file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
        except Exception as e:
            logger.warning("Could not audit file %s: %s", file_path, e)
            return FileAudit(
                file_path=str(file_path),
                file_size=0,
                line_count=0,
                function_count=0,
                class_count=0,
                import_count=0,
                issues=[SecurityIssue(
                    category=IssueCategory.CODE_QUALITY,
                    severity=SeverityLevel.LOW,
                    file_path=str(file_path),
                    line_number=None,
                    title="File read error",
                    description=str(e),
                    recommendation="Check file encoding and permissions"
                )]
            )

        # Basic metrics
        file_size = file_path.stat().st_size
        line_count = len(lines)

        # Parse AST for metrics
        function_count, class_count, import_count, complexity = self._analyze_ast(content, file_path)

        # Find issues
        issues = []
        issues.extend(self._check_patterns(content, lines, file_path, self.SECURITY_PATTERNS, IssueCategory.SECURITY))
        issues.extend(self._check_patterns(content, lines, file_path, self.EDGE_CASE_PATTERNS, IssueCategory.EDGE_CASE))
        issues.extend(self._check_patterns(content, lines, file_path, self.EFFICIENCY_PATTERNS, IssueCategory.EFFICIENCY))
        issues.extend(self._check_patterns(content, lines, file_path, self.ERROR_HANDLING_PATTERNS, IssueCategory.ERROR_HANDLING))
        issues.extend(self._check_input_validation(content, lines, file_path))
        issues.extend(self._check_resource_management(content, lines, file_path))
        issues.extend(self._run_bandit_on_file(file_path))

        return FileAudit(
            file_path=str(file_path),
            file_size=file_size,
            line_count=line_count,
            function_count=function_count,
            class_count=class_count,
            import_count=import_count,
            issues=issues,
            complexity_score=complexity
        )

    def _analyze_ast(self, content: str, file_path: Path) -> tuple:
        """Analyze AST for metrics."""
        try:
            tree = ast.parse(content)

            functions = sum(1 for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)))
            classes = sum(1 for node in ast.walk(tree) if isinstance(node, ast.ClassDef))
            imports = sum(1 for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom)))

            # Simple complexity score based on control flow
            complexity = sum(1 for node in ast.walk(tree) if isinstance(node, (
                ast.If, ast.For, ast.While, ast.Try, ast.ExceptHandler,
                ast.With, ast.Assert, ast.Raise
            )))

            return functions, classes, imports, complexity

        except SyntaxError:
            return 0, 0, 0, 0

    def _check_patterns(
        self,
        content: str,
        lines: List[str],
        file_path: Path,
        patterns_dict: Dict,
        category: IssueCategory
    ) -> List[SecurityIssue]:
        """Check content against pattern dictionary."""
        issues = []

        for issue_name, issue_info in patterns_dict.items():
            exclude_contexts = issue_info.get('exclude_contexts', [])

            for pattern in issue_info['patterns']:
                try:
                    matches = list(re.finditer(pattern, content, re.MULTILINE))
                    for match in matches:
                        # Find line number
                        line_num = content[:match.start()].count('\n') + 1
                        code_snippet = lines[line_num - 1].strip() if line_num <= len(lines) else None

                        # Check for exclude contexts (false positive filtering)
                        if code_snippet and exclude_contexts:
                            should_skip = any(
                                exc.lower() in code_snippet.lower()
                                for exc in exclude_contexts
                            )
                            if should_skip:
                                continue

                        issues.append(SecurityIssue(
                            category=category,
                            severity=issue_info['severity'],
                            file_path=str(file_path),
                            line_number=line_num,
                            title=issue_name.replace('_', ' ').title(),
                            description=issue_info['description'],
                            recommendation=issue_info['recommendation'],
                            code_snippet=code_snippet
                        ))
                except re.error as e:
                    # Log regex errors for debugging but continue scanning
                    issues.append(SecurityIssue(
                        category=IssueCategory.CODE_QUALITY,
                        severity=SeverityLevel.INFO,
                        file_path=str(file_path),
                        line_number=None,
                        title="Security Pattern Error",
                        description=f"Invalid regex pattern for {issue_name}: {e}",
                        recommendation="Review security agent pattern configuration"
                    ))

        return issues

    def _check_input_validation(self, content: str, lines: List[str], file_path: Path) -> List[SecurityIssue]:
        """Check for input validation issues."""
        issues = []

        # Check for functions that take user input without validation
        user_input_patterns = [
            (r'input\s*\(', 'User input not validated'),
            (r'request\.(get|post|args|form|json)', 'HTTP input not validated'),
            (r'sys\.argv\[', 'Command line argument not validated'),
        ]

        for pattern, description in user_input_patterns:
            matches = list(re.finditer(pattern, content, re.MULTILINE | re.IGNORECASE))
            for match in matches:
                line_num = content[:match.start()].count('\n') + 1

                # Check if there's validation nearby (simple heuristic)
                context_start = max(0, match.start() - 200)
                context_end = min(len(content), match.end() + 200)
                context = content[context_start:context_end]

                validation_indicators = ['if ', 'try:', 'validate', 'check', 'sanitize', 'strip()', 'int(', 'float(']
                has_validation = any(ind in context for ind in validation_indicators)

                if not has_validation:
                    issues.append(SecurityIssue(
                        category=IssueCategory.INPUT_VALIDATION,
                        severity=SeverityLevel.MEDIUM,
                        file_path=str(file_path),
                        line_number=line_num,
                        title="Missing Input Validation",
                        description=description,
                        recommendation="Validate and sanitize all external input",
                        code_snippet=lines[line_num - 1].strip() if line_num <= len(lines) else None
                    ))

        return issues

    def _run_bandit_on_file(self, file_path: Path) -> List[SecurityIssue]:
        """Run bandit on a Python file and return findings as SecurityIssue objects."""
        import subprocess
        import json
        import sys

        severity_map = {
            "HIGH": SeverityLevel.HIGH,
            "MEDIUM": SeverityLevel.MEDIUM,
            "LOW": SeverityLevel.LOW,
        }
        try:
            result = subprocess.run(
                [sys.executable, "-m", "bandit", "-f", "json", "-q", str(file_path)],
                capture_output=True, text=True, timeout=30
            )
            if not result.stdout:
                return []
            data = json.loads(result.stdout)
        except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
            return []

        issues = []
        for finding in data.get("results", []):
            sev = severity_map.get(finding.get("issue_severity", "LOW"), SeverityLevel.LOW)
            issues.append(SecurityIssue(
                category=IssueCategory.SECURITY,
                severity=sev,
                file_path=str(file_path),
                line_number=finding.get("line_number"),
                title=f"Bandit [{finding.get('test_id', '')}]: {finding.get('test_name', '')}",
                description=finding.get("issue_text", ""),
                recommendation=f"Bandit rule {finding.get('test_id', '')} — see bandit.readthedocs.io",
                code_snippet=finding.get("code", "").strip()[:80] if finding.get("code") else None,
            ))
        return issues

    def _run_bandit_on_content(self, content: str, filename: str) -> List[SecurityIssue]:
        """Run bandit on staged string content via a temp file."""
        import subprocess
        import json
        import sys
        import tempfile
        import os as _os

        if not filename.endswith(".py"):
            return []

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False, encoding="utf-8"
            ) as tmp:
                tmp.write(content)
                tmp_path = tmp.name

            result = subprocess.run(
                [sys.executable, "-m", "bandit", "-f", "json", "-q", tmp_path],
                capture_output=True, text=True, timeout=30
            )
            if not result.stdout:
                return []
            data = json.loads(result.stdout)
        except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
            return []
        finally:
            if tmp_path:
                try:
                    _os.unlink(tmp_path)
                except OSError:
                    pass

        severity_map = {
            "HIGH": SeverityLevel.HIGH,
            "MEDIUM": SeverityLevel.MEDIUM,
            "LOW": SeverityLevel.LOW,
        }
        issues = []
        for finding in data.get("results", []):
            sev = severity_map.get(finding.get("issue_severity", "LOW"), SeverityLevel.LOW)
            issues.append(SecurityIssue(
                category=IssueCategory.SECURITY,
                severity=sev,
                file_path=filename,
                line_number=finding.get("line_number"),
                title=f"Bandit [{finding.get('test_id', '')}]: {finding.get('test_name', '')}",
                description=finding.get("issue_text", ""),
                recommendation=f"Bandit rule {finding.get('test_id', '')} — see bandit.readthedocs.io",
                code_snippet=finding.get("code", "").strip()[:80] if finding.get("code") else None,
            ))
        return issues

    def _check_resource_management(self, content: str, lines: List[str], file_path: Path) -> List[SecurityIssue]:
        """Check for resource management issues."""
        issues = []

        # Check for resources opened without context manager
        resource_patterns = [
            (r'(\w+)\s*=\s*open\s*\(', 'File handle'),
            (r'(\w+)\s*=\s*socket\.socket\s*\(', 'Socket'),
            (r'(\w+)\s*=\s*\w+\.connect\s*\(', 'Database connection'),
        ]

        for pattern, resource_type in resource_patterns:
            matches = list(re.finditer(pattern, content, re.MULTILINE))
            for match in matches:
                line_num = content[:match.start()].count('\n') + 1

                # Check if it's within a 'with' statement
                line_start = content.rfind('\n', 0, match.start()) + 1
                line_content = content[line_start:match.end()]

                if 'with ' not in line_content:
                    # Check for .close() call
                    var_name = match.group(1)
                    if f'{var_name}.close()' not in content:
                        issues.append(SecurityIssue(
                            category=IssueCategory.RESOURCE_MANAGEMENT,
                            severity=SeverityLevel.MEDIUM,
                            file_path=str(file_path),
                            line_number=line_num,
                            title=f"{resource_type} Not Properly Managed",
                            description=f"{resource_type} opened without context manager",
                            recommendation="Use 'with' statement for automatic resource cleanup",
                            code_snippet=lines[line_num - 1].strip() if line_num <= len(lines) else None
                        ))

        return issues

    def _generate_report(self) -> AuditReport:
        """Generate the final audit report."""
        critical = sum(1 for i in self.issues if i.severity == SeverityLevel.CRITICAL)
        high = sum(1 for i in self.issues if i.severity == SeverityLevel.HIGH)
        medium = sum(1 for i in self.issues if i.severity == SeverityLevel.MEDIUM)
        low = sum(1 for i in self.issues if i.severity == SeverityLevel.LOW)

        total_lines = sum(fa.line_count for fa in self.file_audits)

        # Generate summary
        summary_lines = [
            "=" * 60,
            "HERMES SECURITY AUDIT REPORT",
            "=" * 60,
            f"Timestamp: {datetime.now().isoformat()}",
            f"Files scanned: {len(self.file_audits)}",
            f"Total lines: {total_lines}",
            f"Total issues: {len(self.issues)}",
            "",
            "Issue Breakdown:",
            f"  CRITICAL: {critical}",
            f"  HIGH: {high}",
            f"  MEDIUM: {medium}",
            f"  LOW: {low}",
            "=" * 60,
        ]

        if critical > 0:
            summary_lines.append("\n[!!] CRITICAL ISSUES FOUND - Address immediately!")
        elif high > 0:
            summary_lines.append("\n[!] High severity issues found - Review recommended")
        elif medium > 0:
            summary_lines.append("\n[*] No critical issues. Some improvements suggested.")
        else:
            summary_lines.append("\n[OK] Code passes security audit!")

        return AuditReport(
            timestamp=datetime.now().isoformat(),
            total_files=len(self.file_audits),
            total_lines=total_lines,
            total_issues=len(self.issues),
            critical_issues=critical,
            high_issues=high,
            medium_issues=medium,
            low_issues=low,
            file_audits=self.file_audits,
            summary='\n'.join(summary_lines)
        )

    def print_report(self, report: AuditReport, verbose: bool = False) -> None:
        """Print a formatted audit report."""
        print(report.summary)

        if report.total_issues > 0:
            print("\n" + "-" * 60)
            print("ISSUES FOUND:")
            print("-" * 60)

            # Group by severity
            for severity in [SeverityLevel.CRITICAL, SeverityLevel.HIGH, SeverityLevel.MEDIUM, SeverityLevel.LOW]:
                severity_issues = [i for i in self.issues if i.severity == severity]
                if severity_issues:
                    print(f"\n[{severity.value.upper()}]")
                    for issue in severity_issues:
                        rel_path = os.path.relpath(issue.file_path, self.project_path)
                        print(f"  • {issue.title}")
                        print(f"    File: {rel_path}:{issue.line_number}")
                        print(f"    {issue.description}")
                        if verbose and issue.code_snippet:
                            print(f"    Code: {issue.code_snippet[:60]}...")
                        print(f"    Fix: {issue.recommendation}")
                        print()

        # File metrics
        if verbose:
            print("\n" + "-" * 60)
            print("FILE METRICS:")
            print("-" * 60)
            for fa in sorted(self.file_audits, key=lambda x: x.line_count, reverse=True)[:10]:
                rel_path = os.path.relpath(fa.file_path, self.project_path)
                print(f"  {rel_path}")
                print(f"    Lines: {fa.line_count}, Functions: {fa.function_count}, Classes: {fa.class_count}")
                print(f"    Complexity: {fa.complexity_score}, Issues: {len(fa.issues)}")
