"""
HERMES GitHub Scanner
Fetches files from GitHub with mandatory 4-layer malicious content scanning.
SUSPICIOUS and MALICIOUS content is quarantined — never passed to the caller.
"""
from __future__ import annotations

import base64
import json
import logging
import math
import os
import re
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("hermes.security.github_scanner")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ScanFinding:
    layer: str           # "malicious_patterns" | "dependency_analysis" | "credential_detection" | "anomaly_detection"
    severity: str        # "critical" | "high" | "medium" | "low"
    title: str
    description: str
    line_number: Optional[int] = None
    snippet: Optional[str] = None


@dataclass
class ScanResult:
    classification: str          # "CLEAN" | "SUSPICIOUS" | "MALICIOUS"
    repo: str
    path: str
    ref: str
    fetched_at: str              # ISO 8601 UTC
    file_size: int
    content: Optional[str]       # None if quarantined
    findings: List[ScanFinding]
    quarantine_path: Optional[str]  # set if quarantined
    layers_run: List[str]


# ---------------------------------------------------------------------------
# Known packages for typosquatting detection
# ---------------------------------------------------------------------------

_KNOWN_PACKAGES = {
    "requests", "numpy", "pandas", "scipy", "matplotlib", "flask", "django",
    "fastapi", "sqlalchemy", "pillow", "boto3", "cryptography", "paramiko",
    "celery", "redis", "pymongo", "psycopg2", "aiohttp", "httpx", "pydantic",
    "click", "pytest", "setuptools", "pip", "wheel", "poetry", "urllib3",
    "certifi", "charset_normalizer", "idna", "packaging", "six", "attrs",
    "PyYAML", "toml", "tomli", "typing_extensions", "importlib_metadata",
}

# Normalise to lowercase for matching
_KNOWN_PACKAGES_LOWER = {p.lower().replace("-", "_") for p in _KNOWN_PACKAGES}


# ---------------------------------------------------------------------------
# Scanning pattern dictionaries  (same structure as SecurityAgent.SECURITY_PATTERNS)
# ---------------------------------------------------------------------------

_MALICIOUS_PATTERNS: Dict[str, dict] = {
    "obfuscated_hex_sequence": {
        "patterns": [
            r"\\x[0-9a-fA-F]{2}(?:\\x[0-9a-fA-F]{2}){19,}",
        ],
        "severity": "critical",
        "title": "Long hex-encoded string (likely obfuscated payload)",
    },
    "chr_chain": {
        "patterns": [
            r"chr\s*\(\s*\d+\s*\)(?:\s*\+\s*chr\s*\(\s*\d+\s*\)){9,}",
        ],
        "severity": "critical",
        "title": "chr() chain (character-code obfuscation)",
    },
    "dynamic_dangerous_import": {
        "patterns": [
            r"__import__\s*\([\"']\s*(?:os|subprocess|socket|pty)\s*[\"']",
        ],
        "severity": "high",
        "title": "Dynamic import of dangerous module",
    },
    "eval_of_external_input": {
        "patterns": [
            r"eval\s*\(\s*(?:input\s*\(|request\.|open\s*\(|base64\.|decode)",
            r"exec\s*\(\s*(?:request\.|open\s*\(|base64\.|urllib|decode)",
        ],
        "severity": "critical",
        "title": "eval/exec of external or dynamic content",
    },
    "base64_exec_payload": {
        "patterns": [
            r"base64\.(?:b64decode|decodebytes)\s*\([^)]+\).*exec",
            r"exec\s*\(.*base64",
            r"zlib\.decompress\s*\(.*base64",
        ],
        "severity": "critical",
        "title": "Base64-encoded executable payload",
    },
    "reverse_shell": {
        "patterns": [
            r"socket\.socket[^#\n]*\n[^\n]*connect[^#\n]*\n[^\n]*dup2",
            r"pty\.spawn\s*\(",
            r"/bin/(?:bash|sh)\s+-i\s+>&",
            r"nc\s+-[el][^#\n]{0,30}\d{2,5}",
        ],
        "severity": "critical",
        "title": "Reverse shell pattern",
    },
    "crypto_miner": {
        "patterns": [
            r"stratum\+tcp://",
            r"\b(?:xmrig|coinhive|cryptonight|monero)\b",
            r"mining\.pool\.|pool\.mining\.",
        ],
        "severity": "critical",
        "title": "Cryptocurrency miner",
    },
    "supply_chain_attack": {
        "patterns": [
            r"(?:install_requires|setup\.py)[^\n]*\n[^\n]*subprocess\.[^\n]*(?:call|run|Popen)",
            r"__import__[^\n]*os[^\n]*system[^\n]*pip\s+install",
            r"urllib[^\n]*(?:urlopen|urlretrieve)[^\n]*\n[^\n]*exec",
        ],
        "severity": "critical",
        "title": "Supply-chain attack pattern (malicious install hook)",
    },
}

_CREDENTIAL_PATTERNS: List[Tuple[str, str, str]] = [
    # (regex, severity, title)
    (r"(?:api[_\-]?key|apikey)\s*[:=]\s*[\"'][A-Za-z0-9]{16,}[\"']",       "high",     "Hardcoded API key"),
    (r"(?:secret|password|passwd|pwd|token)\s*[:=]\s*[\"'][^\"']{8,}[\"']",  "high",     "Hardcoded secret/password"),
    (r"sk-[A-Za-z0-9]{20,}",                                                  "critical", "OpenAI/Stripe secret key"),
    (r"ghp_[A-Za-z0-9]{36,}",                                                 "critical", "GitHub personal access token"),
    (r"AKIA[0-9A-Z]{16}",                                                      "critical", "AWS access key ID"),
    (r"-----BEGIN\s+(?:RSA\s+|EC\s+)?PRIVATE\s+KEY-----",                     "critical", "Private key material"),
    (r"eyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,}",  "high",     "JWT token"),
]


# ---------------------------------------------------------------------------
# Main scanner class
# ---------------------------------------------------------------------------

class GitHubScanner:
    """
    Fetches a single file from GitHub and scans it through 4 independent layers.
    Quarantines SUSPICIOUS and MALICIOUS files; clean files are returned to caller.
    """

    GITHUB_API_BASE = "https://api.github.com"
    MAX_FILE_SIZE_BYTES = 1_000_000   # 1 MB — refuse to scan larger files
    HIGH_ENTROPY_THRESHOLD = 4.8      # Shannon entropy threshold
    HIGH_ENTROPY_MIN_LENGTH = 30      # Minimum string length for entropy check
    LONG_LINE_THRESHOLD = 10_000      # Characters

    def __init__(self, base_path: str) -> None:
        """
        Args:
            base_path: Root of the HERMES project. Quarantine dir is created under
                       base_path/data/quarantine/
        """
        self._quarantine_root = Path(base_path) / "data" / "quarantine"
        self._quarantine_root.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_and_scan(
        self,
        repo: str,
        path: str,
        ref: str = "main",
        github_token: Optional[str] = None,
    ) -> ScanResult:
        """
        Fetch a file from GitHub and run all 4 scanning layers.

        Args:
            repo:         "owner/name" e.g. "anthropics/anthropic-sdk-python"
            path:         File path within repo e.g. "src/client.py"
            ref:          Branch, tag, or commit SHA (default: "main")
            github_token: Optional GitHub PAT for private repos / higher rate limits.
                          Passed as Authorization header — never logged.

        Returns:
            ScanResult.  content is None if classification is SUSPICIOUS or MALICIOUS.
        """
        fetched_at = datetime.now(timezone.utc).isoformat()
        findings: List[ScanFinding] = []
        layers_run: List[str] = []

        # --- Fetch ---
        try:
            raw_content, file_size = self._fetch_file(repo, path, ref, github_token)
        except Exception as exc:
            logger.error("GitHub fetch failed for %s/%s@%s: %s", repo, path, ref, exc)
            return ScanResult(
                classification="MALICIOUS",
                repo=repo, path=path, ref=ref,
                fetched_at=fetched_at,
                file_size=0,
                content=None,
                findings=[ScanFinding(
                    layer="fetch",
                    severity="critical",
                    title="Fetch failed",
                    description=str(exc),
                )],
                quarantine_path=None,
                layers_run=[],
            )

        if file_size > self.MAX_FILE_SIZE_BYTES:
            return ScanResult(
                classification="SUSPICIOUS",
                repo=repo, path=path, ref=ref,
                fetched_at=fetched_at,
                file_size=file_size,
                content=None,
                findings=[ScanFinding(
                    layer="fetch",
                    severity="high",
                    title="File too large to scan",
                    description=f"File size {file_size} bytes exceeds limit {self.MAX_FILE_SIZE_BYTES}",
                )],
                quarantine_path=None,
                layers_run=[],
            )

        # --- Layer 1: Malicious patterns ---
        layer1 = self._scan_malicious_patterns(raw_content)
        findings.extend(layer1)
        layers_run.append("malicious_patterns")

        # --- Layer 2: Dependency analysis (Python only) ---
        if path.endswith(".py") or path.endswith(".txt") or "requirements" in path.lower():
            layer2 = self._scan_dependencies(raw_content)
            findings.extend(layer2)
            layers_run.append("dependency_analysis")

        # --- Layer 3: Credential detection ---
        layer3 = self._scan_credentials(raw_content)
        findings.extend(layer3)
        layers_run.append("credential_detection")

        # --- Layer 4: Anomaly detection ---
        layer4 = self._scan_anomalies(raw_content)
        findings.extend(layer4)
        layers_run.append("anomaly_detection")

        # --- Classify ---
        classification = self._classify(findings)
        logger.info(
            "Scan complete: %s/%s@%s → %s (%d findings)",
            repo, path, ref, classification, len(findings),
        )

        # --- Quarantine if not clean ---
        quarantine_path: Optional[str] = None
        content: Optional[str] = raw_content

        if classification in ("SUSPICIOUS", "MALICIOUS"):
            quarantine_path = self._quarantine(repo, path, ref, raw_content, findings, fetched_at)
            content = None  # Never return quarantined content
            logger.warning(
                "Quarantined %s %s/%s@%s → %s",
                classification, repo, path, ref, quarantine_path,
            )

        return ScanResult(
            classification=classification,
            repo=repo, path=path, ref=ref,
            fetched_at=fetched_at,
            file_size=file_size,
            content=content,
            findings=findings,
            quarantine_path=quarantine_path,
            layers_run=layers_run,
        )

    # ------------------------------------------------------------------
    # Fetching
    # ------------------------------------------------------------------

    def _fetch_file(
        self,
        repo: str,
        path: str,
        ref: str,
        token: Optional[str],
    ) -> Tuple[str, int]:
        """
        Fetch file content via GitHub API.
        Returns (decoded_text_content, file_size_bytes).
        Raises on HTTP errors or non-text content.
        """
        url = f"{self.GITHUB_API_BASE}/repos/{repo}/contents/{path}?ref={ref}"
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "HERMES/1.0"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"GitHub API HTTP {exc.code}: {exc.reason} for {url}") from exc

        if isinstance(data, list):
            raise RuntimeError(f"{path!r} is a directory, not a file")

        encoding = data.get("encoding", "")
        file_size = data.get("size", 0)
        raw = data.get("content", "")

        if encoding == "base64":
            try:
                decoded_bytes = base64.b64decode(raw)
            except Exception as exc:
                raise RuntimeError(f"Failed to decode base64 content: {exc}") from exc

            # Reject binary files
            if b"\x00" in decoded_bytes:
                raise RuntimeError("Binary file — text scanning not applicable")

            try:
                text = decoded_bytes.decode("utf-8")
            except UnicodeDecodeError:
                try:
                    text = decoded_bytes.decode("latin-1")
                except Exception as exc:
                    raise RuntimeError(f"Cannot decode file as text: {exc}") from exc
        elif encoding == "":
            # Large file — use download_url
            download_url = data.get("download_url")
            if not download_url:
                raise RuntimeError("No download_url and no inline content")
            dl_req = urllib.request.Request(download_url, headers={"User-Agent": "HERMES/1.0"})
            with urllib.request.urlopen(dl_req, timeout=30) as resp:
                raw_bytes = resp.read()
            if b"\x00" in raw_bytes:
                raise RuntimeError("Binary file — text scanning not applicable")
            text = raw_bytes.decode("utf-8", errors="replace")
        else:
            raise RuntimeError(f"Unknown encoding: {encoding!r}")

        return text, file_size

    # ------------------------------------------------------------------
    # Layer 1: Malicious pattern matching
    # ------------------------------------------------------------------

    def _scan_malicious_patterns(self, content: str) -> List[ScanFinding]:
        findings: List[ScanFinding] = []
        lines = content.splitlines()

        for check_name, check in _MALICIOUS_PATTERNS.items():
            for pattern in check["patterns"]:
                try:
                    for match in re.finditer(pattern, content, re.MULTILINE | re.DOTALL):
                        line_num = content[: match.start()].count("\n") + 1
                        snippet = lines[line_num - 1].strip()[:120] if line_num <= len(lines) else None
                        findings.append(ScanFinding(
                            layer="malicious_patterns",
                            severity=check["severity"],
                            title=check["title"],
                            description=f"Pattern matched: {check_name}",
                            line_number=line_num,
                            snippet=snippet,
                        ))
                        break  # One finding per check per file is enough
                except re.error:
                    pass

        return findings

    # ------------------------------------------------------------------
    # Layer 2: Dependency / typosquatting analysis
    # ------------------------------------------------------------------

    def _scan_dependencies(self, content: str) -> List[ScanFinding]:
        findings: List[ScanFinding] = []

        # Extract import names from Python source
        import_names: List[str] = []
        for match in re.finditer(r"^\s*import\s+([A-Za-z0-9_]+)", content, re.MULTILINE):
            import_names.append(match.group(1).lower().replace("-", "_"))
        for match in re.finditer(r"^\s*from\s+([A-Za-z0-9_]+)\s+import", content, re.MULTILINE):
            import_names.append(match.group(1).lower().replace("-", "_"))

        # Extract package names from requirements files
        for match in re.finditer(r"^([A-Za-z0-9_\-]+)\s*(?:[>=<!]=?|$)", content, re.MULTILINE):
            import_names.append(match.group(1).lower().replace("-", "_"))

        for name in set(import_names):
            if name in _KNOWN_PACKAGES_LOWER:
                continue  # Legitimate package
            # Check Levenshtein distance = 1 against any known package
            for known in _KNOWN_PACKAGES_LOWER:
                if _levenshtein(name, known) == 1:
                    findings.append(ScanFinding(
                        layer="dependency_analysis",
                        severity="high",
                        title="Potential typosquatting",
                        description=f"Package {name!r} is 1 edit away from known package {known!r}",
                    ))
                    break

        return findings

    # ------------------------------------------------------------------
    # Layer 3: Credential detection
    # ------------------------------------------------------------------

    def _scan_credentials(self, content: str) -> List[ScanFinding]:
        findings: List[ScanFinding] = []
        lines = content.splitlines()

        for pattern, severity, title in _CREDENTIAL_PATTERNS:
            try:
                for match in re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE):
                    line_num = content[: match.start()].count("\n") + 1
                    snippet = lines[line_num - 1].strip()[:80] if line_num <= len(lines) else None
                    # Redact the actual secret from the snippet before storing
                    if snippet:
                        snippet = re.sub(r"[A-Za-z0-9+/=]{12,}", "[REDACTED]", snippet)
                    findings.append(ScanFinding(
                        layer="credential_detection",
                        severity=severity,
                        title=title,
                        description="Credential pattern matched in fetched content",
                        line_number=line_num,
                        snippet=snippet,
                    ))
                    break  # One finding per pattern per file
            except re.error:
                pass

        return findings

    # ------------------------------------------------------------------
    # Layer 4: Anomaly detection
    # ------------------------------------------------------------------

    def _scan_anomalies(self, content: str) -> List[ScanFinding]:
        findings: List[ScanFinding] = []
        lines = content.splitlines()

        # Null bytes (binary content in a text file)
        if "\x00" in content:
            findings.append(ScanFinding(
                layer="anomaly_detection",
                severity="high",
                title="Null bytes in text file",
                description="File contains null bytes — may be a binary file disguised as text",
            ))

        # Extremely long lines
        for i, line in enumerate(lines, 1):
            if len(line) > self.LONG_LINE_THRESHOLD:
                findings.append(ScanFinding(
                    layer="anomaly_detection",
                    severity="medium",
                    title="Extremely long line",
                    description=f"Line {i} is {len(line)} characters (threshold: {self.LONG_LINE_THRESHOLD})",
                    line_number=i,
                    snippet=line[:80] + "...",
                ))
                break  # Flag once

        # High-entropy strings (potential encrypted payloads or tokens)
        for match in re.finditer(r"[A-Za-z0-9+/=_\-]{%d,}" % self.HIGH_ENTROPY_MIN_LENGTH, content):
            segment = match.group(0)
            entropy = _shannon_entropy(segment)
            if entropy >= self.HIGH_ENTROPY_THRESHOLD:
                line_num = content[: match.start()].count("\n") + 1
                findings.append(ScanFinding(
                    layer="anomaly_detection",
                    severity="medium",
                    title="High-entropy string",
                    description=f"String of length {len(segment)} has Shannon entropy {entropy:.2f} (threshold: {self.HIGH_ENTROPY_THRESHOLD})",
                    line_number=line_num,
                    snippet="[REDACTED — high entropy]",
                ))
                break  # Flag once per file

        return findings

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    def _classify(self, findings: List[ScanFinding]) -> str:
        """
        MALICIOUS:  any critical finding
        SUSPICIOUS: any high finding, or 3+ medium findings
        CLEAN:      everything else
        """
        if any(f.severity == "critical" for f in findings):
            return "MALICIOUS"
        high_count = sum(1 for f in findings if f.severity == "high")
        medium_count = sum(1 for f in findings if f.severity == "medium")
        if high_count >= 1 or medium_count >= 3:
            return "SUSPICIOUS"
        return "CLEAN"

    # ------------------------------------------------------------------
    # Quarantine
    # ------------------------------------------------------------------

    def _quarantine(
        self,
        repo: str,
        path: str,
        ref: str,
        content: str,
        findings: List[ScanFinding],
        fetched_at: str,
    ) -> str:
        """
        Write content + scan report to the quarantine directory.
        Returns the absolute path of the quarantined file.
        """
        date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        repo_slug = repo.replace("/", "_")
        safe_path = re.sub(r"[^\w.\-/]", "_", path)

        quarantine_dir = self._quarantine_root / date_str / repo_slug
        quarantine_dir.mkdir(parents=True, exist_ok=True)

        base_name = safe_path.replace("/", "__")
        content_file = quarantine_dir / f"{base_name}.quarantine"
        report_file = quarantine_dir / f"{base_name}.report.json"

        try:
            content_file.write_text(content, encoding="utf-8")
        except Exception as exc:
            logger.error("Failed to write quarantine content: %s", exc)

        report = {
            "repo": repo,
            "path": path,
            "ref": ref,
            "fetched_at": fetched_at,
            "quarantined_at": datetime.now(timezone.utc).isoformat(),
            "findings": [
                {
                    "layer": f.layer,
                    "severity": f.severity,
                    "title": f.title,
                    "description": f.description,
                    "line_number": f.line_number,
                    "snippet": f.snippet,
                }
                for f in findings
            ],
        }
        try:
            report_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.error("Failed to write quarantine report: %s", exc)

        return str(content_file)


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def _levenshtein(a: str, b: str) -> int:
    """Compute Levenshtein edit distance between two strings."""
    if a == b:
        return 0
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i]
        for j, cb in enumerate(b, 1):
            curr.append(min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = curr
    return prev[-1]


def _shannon_entropy(s: str) -> float:
    """Shannon entropy of a string (bits per character)."""
    if not s:
        return 0.0
    freq: Dict[str, int] = {}
    for c in s:
        freq[c] = freq.get(c, 0) + 1
    n = len(s)
    return -sum((count / n) * math.log2(count / n) for count in freq.values())
