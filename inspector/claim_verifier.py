"""
HERMES Inspector General — Stateless per-invocation claim verifier.

Runs 7 independent checks against an ExecutionResult and aggregates
flags, warnings, and check names.  Each check is isolated in its own
try/except so one failure cannot skip the others.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import List, NamedTuple, Tuple

from core_logic.hermes_types import ExecutionResult, ExecutionStatus

logger = logging.getLogger("hermes.inspector.claim_verifier")

# Creation-verb keywords used in _check_file_path_claims
_CREATION_VERBS = re.compile(
    r"\b(?:created|wrote|saved|generated|output|written)\b", re.IGNORECASE
)

# File path patterns
_WIN_PATH = re.compile(r"[A-Za-z]:\\[^\s\"'<>|?*\x00-\x1f]+")
_UNIX_PATH = re.compile(r"/\w[^\s\"'<>|?*\x00-\x1f]*")
_REL_PATH = re.compile(
    r"[\w./\\-]+\.(?:py|ts|json|txt|md|csv|kicad_pcb|kicad_sch|toe|tox|wav|png|jpg)"
)


class VerifierResult(NamedTuple):
    """Aggregated output from all claim checks."""

    flags: List[str]
    warnings: List[str]
    checks_run: List[str]


class ClaimVerifier:
    """Runs all 7 structural and behavioural checks on an ExecutionResult."""

    IMPLAUSIBLE_EXECUTION_TIME_SECONDS: float = 0.1
    VERY_FAST_EXECUTION_SECONDS: float = 0.5

    def verify(self, result: ExecutionResult, raw_input: str) -> VerifierResult:
        """
        Run all 7 checks and aggregate their outputs.

        Each check is wrapped in its own try/except.  A failing check is
        omitted from checks_run (reducing confidence in InspectorGeneral)
        but does not prevent the remaining checks from running.

        Args:
            result:    The ExecutionResult produced by the orchestrator.
            raw_input: The original user-supplied task string.

        Returns:
            VerifierResult with aggregated flags, warnings, and check names.
        """
        all_flags: List[str] = []
        all_warnings: List[str] = []
        checks_run: List[str] = []

        checks = [
            ("security_gate_present", self._check_security_gate_present),
            ("execution_time_plausibility", self._check_execution_time_plausibility),
            ("status_content_consistency", self._check_status_content_consistency),
            ("error_suppression", self._check_error_suppression),
            ("agent_count_consistency", self._check_agent_count_consistency),
            ("file_path_claims", self._check_file_path_claims),
            ("result_dict_structure", self._check_result_dict_structure),
        ]

        for check_name, check_fn in checks:
            try:
                flags, warnings = check_fn(result)
                all_flags.extend(flags)
                all_warnings.extend(warnings)
                checks_run.append(check_name)
            except Exception as exc:
                logger.error(
                    "ClaimVerifier check '%s' raised an unexpected error: %s",
                    check_name,
                    exc,
                )
                # Intentionally omitted from checks_run to reduce confidence

        return VerifierResult(
            flags=all_flags,
            warnings=all_warnings,
            checks_run=checks_run,
        )

    # ------------------------------------------------------------------
    # Check 1 — Security gate presence
    # ------------------------------------------------------------------

    def _check_security_gate_present(
        self, result: ExecutionResult
    ) -> Tuple[List[str], List[str]]:
        """
        FLAG if the security_gate key is absent from both results and errors.
        WARN if security_gate errored.
        """
        flags: List[str] = []
        warnings: List[str] = []

        in_results = "security_gate" in result.results
        in_errors = "security_gate" in result.errors

        if not in_results and not in_errors:
            flags.append("SECURITY_GATE_ABSENT")
        if in_errors:
            warnings.append("SECURITY_GATE_ERRORED")

        return flags, warnings

    # ------------------------------------------------------------------
    # Check 2 — Execution time plausibility
    # ------------------------------------------------------------------

    def _check_execution_time_plausibility(
        self, result: ExecutionResult
    ) -> Tuple[List[str], List[str]]:
        """
        FLAG if execution_time is impossibly short (<0.1 s).
        WARN if execution_time is suspiciously short (<0.5 s but >=0.1 s).
        Only applies to COMPLETED or PARTIAL status.
        """
        flags: List[str] = []
        warnings: List[str] = []

        applicable = result.status in (ExecutionStatus.COMPLETED, ExecutionStatus.PARTIAL)
        if not applicable:
            return flags, warnings

        t = result.execution_time
        if t < self.IMPLAUSIBLE_EXECUTION_TIME_SECONDS:
            flags.append("IMPLAUSIBLE_EXECUTION_TIME")
        elif t < self.VERY_FAST_EXECUTION_SECONDS:
            warnings.append("VERY_FAST_EXECUTION")

        return flags, warnings

    # ------------------------------------------------------------------
    # Check 3 — Status / content consistency
    # ------------------------------------------------------------------

    def _check_status_content_consistency(
        self, result: ExecutionResult
    ) -> Tuple[List[str], List[str]]:
        """
        Only applies when status is COMPLETED.
        FLAG if results dict is empty.
        WARN if all values in results are None.
        """
        flags: List[str] = []
        warnings: List[str] = []

        if result.status != ExecutionStatus.COMPLETED:
            return flags, warnings

        if not result.results:
            flags.append("COMPLETED_WITH_NO_RESULTS")
        elif all(v is None for v in result.results.values()):
            warnings.append("COMPLETED_WITH_ALL_NONE_RESULTS")

        return flags, warnings

    # ------------------------------------------------------------------
    # Check 4 — Error suppression
    # ------------------------------------------------------------------

    def _check_error_suppression(
        self, result: ExecutionResult
    ) -> Tuple[List[str], List[str]]:
        """
        WARN if status==COMPLETED but errors dict is non-empty.
        FLAG if errors exist AND the summary contains a "no errors" style phrase.
        """
        flags: List[str] = []
        warnings: List[str] = []

        errors_present = bool(result.errors)

        if result.status == ExecutionStatus.COMPLETED and errors_present:
            warnings.append("ERRORS_PRESENT_IN_COMPLETED")

        if errors_present:
            summary_lower = (result.summary or "").lower()
            suppression_phrases = [
                "completed successfully",
                "no errors",
                "all tasks succeeded",
                "successfully completed",
            ]
            if any(phrase in summary_lower for phrase in suppression_phrases):
                flags.append("ERROR_SUPPRESSION_DETECTED")

        return flags, warnings

    # ------------------------------------------------------------------
    # Check 5 — Agent count consistency
    # ------------------------------------------------------------------

    def _check_agent_count_consistency(
        self, result: ExecutionResult
    ) -> Tuple[List[str], List[str]]:
        """
        FLAG if no agents are listed but non-security-gate results exist.
        WARN if results vastly outnumber agents (ratio > 10).
        """
        flags: List[str] = []
        warnings: List[str] = []

        non_gate_results = [k for k in result.results if k != "security_gate"]
        agents_used = result.agents_used or []

        if not agents_used and non_gate_results:
            flags.append("NO_AGENTS_CLAIMED_BUT_RESULTS_EXIST")

        results_count = len(result.results)
        ratio = (results_count - 1) / max(len(agents_used), 1)
        if ratio > 10:
            warnings.append("AGENT_RESULT_COUNT_DISCREPANCY")

        return flags, warnings

    # ------------------------------------------------------------------
    # Check 6 — File path claims
    # ------------------------------------------------------------------

    def _check_file_path_claims(
        self, result: ExecutionResult
    ) -> Tuple[List[str], List[str]]:
        """
        Extract file paths from result output strings.  For each path that
        appears within 50 characters of a creation verb, check whether the
        file actually exists on disk.  WARN for each missing claimed file.
        """
        flags: List[str] = []
        warnings: List[str] = []

        output_strings: List[str] = []
        for v in result.results.values():
            if isinstance(v, str):
                output_strings.append(v)
            elif isinstance(v, dict):
                for dv in v.values():
                    if isinstance(dv, str):
                        output_strings.append(dv)

        checked: set = set()
        for text in output_strings:
            # Find all creation verb positions
            verb_positions = [m.start() for m in _CREATION_VERBS.finditer(text)]
            if not verb_positions:
                continue

            # Collect all candidate paths in the text
            candidate_paths: List[Tuple[int, str]] = []
            for pattern in (_WIN_PATH, _UNIX_PATH, _REL_PATH):
                for m in pattern.finditer(text):
                    candidate_paths.append((m.start(), m.group()))

            for path_pos, path_str in candidate_paths:
                if path_str in checked:
                    continue
                # Check if any verb is within 50 chars of this path
                near_verb = any(
                    abs(path_pos - vpos) <= 50 for vpos in verb_positions
                )
                if not near_verb:
                    continue
                checked.add(path_str)
                # Reject UNC paths and device paths — Path.exists() on these
                # can trigger network I/O or block on Windows device handles.
                if path_str.startswith("\\\\") or path_str.startswith("//") or len(path_str) > 512:
                    continue
                try:
                    if not Path(path_str).exists():
                        warnings.append(f"CLAIMED_FILE_NOT_FOUND: {path_str}")
                except (OSError, ValueError):
                    pass  # Invalid path — skip silently

        return flags, warnings

    # ------------------------------------------------------------------
    # Check 7 — Result dict structure
    # ------------------------------------------------------------------

    def _check_result_dict_structure(
        self, result: ExecutionResult
    ) -> Tuple[List[str], List[str]]:
        """
        For each dict-valued entry in result.results, warn if it has none
        of the expected HERMES result keys.
        """
        flags: List[str] = []
        warnings: List[str] = []

        expected_keys = {
            "agent_id",
            "task_id",
            "status",
            "output",
            "message",
            "result",
            "error",
        }

        for subtask_id, value in result.results.items():
            if not isinstance(value, dict):
                continue
            if value is None:
                continue
            if not expected_keys.intersection(value.keys()):
                warnings.append(f"MALFORMED_RESULT_ENTRY: {subtask_id}")

        return flags, warnings
