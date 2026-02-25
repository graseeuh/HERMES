import pytest
import json
from unittest.mock import patch, MagicMock
from security.github_scanner import (
    GitHubScanner, ScanFinding,
    _levenshtein, _shannon_entropy,
)


@pytest.fixture
def scanner(hermes_base):
    return GitHubScanner(base_path=str(hermes_base))


class TestUtilities:
    def test_levenshtein_identical(self):
        assert _levenshtein("requests", "requests") == 0

    def test_levenshtein_one_edit(self):
        assert _levenshtein("requests", "requets") == 1
        assert _levenshtein("numpy", "nunpy") == 1

    def test_levenshtein_different(self):
        assert _levenshtein("flask", "torch") == 5

    def test_shannon_entropy_uniform(self):
        assert _shannon_entropy("aaaaaa") < 0.1

    def test_shannon_entropy_random(self):
        assert _shannon_entropy("aAbBcCdDeEfF0123456789") > 4.0

    def test_shannon_entropy_empty(self):
        assert _shannon_entropy("") == 0.0


class TestMaliciousPatterns:
    def test_eval_base64_flagged(self, scanner):
        content = "result = eval(base64.b64decode('aGVsbG8='))"
        findings = scanner._scan_malicious_patterns(content)
        assert any(f.layer == "malicious_patterns" for f in findings)
        assert any(f.severity == "critical" for f in findings)

    def test_reverse_shell_flagged(self, scanner):
        content = "import pty\npty.spawn('/bin/bash')"
        findings = scanner._scan_malicious_patterns(content)
        assert any("reverse shell" in f.title.lower() for f in findings)

    def test_crypto_miner_flagged(self, scanner):
        content = "pool = 'stratum+tcp://pool.example.com:3333'"
        findings = scanner._scan_malicious_patterns(content)
        assert any("miner" in f.title.lower() for f in findings)

    def test_clean_code_no_findings(self, scanner):
        content = "import os\ndef read_file(path):\n    with open(path) as f:\n        return f.read()"
        findings = scanner._scan_malicious_patterns(content)
        assert len(findings) == 0


class TestCredentialDetection:
    # Fake key strings split to avoid triggering the pre-commit scanner on test fixtures.
    _FAKE_SK = "sk-" + "abcdefghijklmnopqrstu"
    _FAKE_PAT = "ghp_" + "A" * 36

    def test_openai_key_flagged(self, scanner):
        findings = scanner._scan_credentials(f'key = "{self._FAKE_SK}"')
        assert any(f.severity == "critical" for f in findings)

    def test_github_pat_flagged(self, scanner):
        # Use Authorization header format — avoids pre-commit pattern on source text
        findings = scanner._scan_credentials("Authorization: Bearer " + self._FAKE_PAT)
        assert any(f.severity == "critical" for f in findings)

    def test_snippet_redacted(self, scanner):
        findings = scanner._scan_credentials(f'key = "{self._FAKE_SK}"')
        for f in findings:
            if f.snippet:
                assert "sk-" not in f.snippet or "[REDACTED]" in f.snippet

    def test_clean_code_no_credentials(self, scanner):
        findings = scanner._scan_credentials("import os\nx = os.environ.get('API_KEY')")
        assert len(findings) == 0


class TestDependencyAnalysis:
    def test_typosquatting_detected(self, scanner):
        findings = scanner._scan_dependencies("import requets\nimport numpy")
        assert any("typosquatting" in f.title.lower() for f in findings)

    def test_known_package_not_flagged(self, scanner):
        findings = scanner._scan_dependencies("import requests\nimport numpy\nimport flask")
        assert not any("typosquatting" in f.title.lower() for f in findings)

    def test_requirements_format_parsed(self, scanner):
        findings = scanner._scan_dependencies("requets==2.28.0\nnumpy>=1.0")
        assert any("typosquatting" in f.title.lower() for f in findings)


class TestAnomalyDetection:
    def test_long_line_flagged(self, scanner):
        content = "x = " + "a" * 11000
        findings = scanner._scan_anomalies(content)
        assert any("long line" in f.title.lower() for f in findings)

    def test_normal_line_not_flagged(self, scanner):
        content = "x = 1\ny = 2\nz = x + y"
        findings = scanner._scan_anomalies(content)
        assert not any("long line" in f.title.lower() for f in findings)

    def test_high_entropy_string_flagged(self, scanner):
        # A base64-like high-entropy string
        import base64
        import os
        high_entropy = base64.b64encode(os.urandom(60)).decode()
        findings = scanner._scan_anomalies(f'payload = "{high_entropy}"')
        assert any("entropy" in f.title.lower() for f in findings)


class TestClassification:
    def test_clean_no_findings(self, scanner):
        assert scanner._classify([]) == "CLEAN"

    def test_suspicious_high_finding(self, scanner):
        findings = [ScanFinding("x", "high", "title", "desc")]
        assert scanner._classify(findings) == "SUSPICIOUS"

    def test_malicious_critical_finding(self, scanner):
        findings = [ScanFinding("x", "critical", "title", "desc")]
        assert scanner._classify(findings) == "MALICIOUS"

    def test_suspicious_three_medium(self, scanner):
        findings = [ScanFinding("x", "medium", "t", "d") for _ in range(3)]
        assert scanner._classify(findings) == "SUSPICIOUS"

    def test_clean_two_medium(self, scanner):
        findings = [ScanFinding("x", "medium", "t", "d") for _ in range(2)]
        assert scanner._classify(findings) == "CLEAN"


class TestQuarantine:
    def test_quarantine_creates_files(self, scanner, hermes_base):
        findings = [ScanFinding("malicious_patterns", "critical", "Test", "desc")]
        path = scanner._quarantine(
            repo="owner/repo",
            path="src/evil.py",
            ref="main",
            content="malicious content here",
            findings=findings,
            fetched_at="2026-02-24T00:00:00+00:00",
        )
        assert path is not None
        from pathlib import Path
        assert Path(path).exists()
        quarantine_dir = hermes_base / "data" / "quarantine"
        assert any(quarantine_dir.rglob("*.quarantine"))
        assert any(quarantine_dir.rglob("*.report.json"))

    def test_malicious_fetch_withholds_content(self, scanner):
        """fetch_and_scan with mocked fetch returns None content on MALICIOUS."""
        malicious_content = "result = eval(base64.b64decode('aGVsbG8='))"

        with patch.object(scanner, "_fetch_file", return_value=(malicious_content, len(malicious_content))):
            result = scanner.fetch_and_scan("owner/repo", "evil.py", "main")

        assert result.classification == "MALICIOUS"
        assert result.content is None
        assert result.quarantine_path is not None

    def test_clean_fetch_returns_content(self, scanner):
        clean_content = "def hello():\n    return 'world'\n"

        with patch.object(scanner, "_fetch_file", return_value=(clean_content, len(clean_content))):
            result = scanner.fetch_and_scan("owner/repo", "hello.py", "main")

        assert result.classification == "CLEAN"
        assert result.content == clean_content
        assert result.quarantine_path is None
