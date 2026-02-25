"""
HERMES Inspector General — Independent post-execution auditor.

Instantiated once as a singleton at the MCP server boundary.  The
orchestrator has no import path to this module and cannot call, bypass,
or write to it.

The public inspect() method never raises.  All internal errors produce a
degraded verdict rather than propagating upward.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4

from core_logic.orchestrator import ExecutionResult

logger = logging.getLogger("hermes.inspector.general")

# Total number of checks ClaimVerifier can run — used for confidence scoring.
_TOTAL_CHECKS = 7


@dataclass
class InspectorVerdict:
    """Outcome of a single Inspector General audit of an ExecutionResult."""

    passed: bool
    flags: List[str]
    warnings: List[str]
    confidence: float
    checks_run: List[str]
    session_id: str
    task_hash: str
    inspected_at: str
    behavioral_summary: Dict[str, Any]
    degraded: bool = False


class InspectorGeneral:
    """
    Top-level coordinator for the Inspector General subsystem.

    Wires together ClaimVerifier, BehavioralMonitor, and InspectorLog.
    Designed to be instantiated once per process at the MCP boundary.
    """

    def __init__(self, base_path: str) -> None:
        """
        Set up directory structure and sub-components.

        Args:
            base_path: Absolute path to the root of the HERMES project
                       (the directory that contains mcp_server.py).
        """
        root = Path(base_path)
        self._log_dir = root / "inspector" / "logs"
        self._state_dir = root / "inspector" / "state"

        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._state_dir.mkdir(parents=True, exist_ok=True)

        # Lazy imports here keep inspector/ isolated from core_logic imports
        # that happen at module load time — the verifier and monitor both
        # import from core_logic, but only when InspectorGeneral is actually
        # instantiated (i.e. from mcp_server.py, never from core_logic/).
        from .claim_verifier import ClaimVerifier
        from .behavioral_monitor import BehavioralMonitor
        from .inspector_log import InspectorLog

        self._verifier = ClaimVerifier()
        self._monitor = BehavioralMonitor(
            state_path=self._state_dir / "behavioral_state.json"
        )
        self._log = InspectorLog(log_dir=self._log_dir)

    # ------------------------------------------------------------------
    # Primary public API
    # ------------------------------------------------------------------

    def inspect(self, result: ExecutionResult, raw_input: str) -> InspectorVerdict:
        """
        Audit an ExecutionResult at the MCP boundary.

        This method never raises.  Any internal exception causes a degraded
        verdict to be returned instead of propagating to the caller.

        Args:
            result:    The ExecutionResult produced by the orchestrator.
            raw_input: The original user-supplied task string.

        Returns:
            An InspectorVerdict (possibly degraded if an internal error occurred).
        """
        session_id = str(uuid4())
        task_hash = self._compute_task_hash(raw_input)
        inspected_at = datetime.now(timezone.utc).isoformat()

        try:
            # Step 1: Run claim verifier
            verifier_result = self._verifier.verify(result, raw_input)
            flags = verifier_result.flags
            warnings = verifier_result.warnings
            checks_run = verifier_result.checks_run

            # Step 2: Confidence — penalise 1/7 per unrun check
            unrun = _TOTAL_CHECKS - len(checks_run)
            confidence = max(0.0, 1.0 - (unrun / _TOTAL_CHECKS))

            # Step 3: Behavioural tracking
            behavioral_report = self._monitor.record(result, flags, raw_input)
            behavioral_summary: Dict[str, Any] = {
                "total_invocations": behavioral_report.total_invocations,
                "success_rate": behavioral_report.success_rate,
                "flag_rate": behavioral_report.flag_rate,
                "security_gate_skip_rate": behavioral_report.security_gate_skip_rate,
                "avg_execution_time": behavioral_report.avg_execution_time,
                "recent_flags": behavioral_report.recent_flags[-5:],
                "anomalies_detected": behavioral_report.anomalies_detected,
            }

            # Step 4: Build verdict
            verdict = InspectorVerdict(
                passed=len(flags) == 0,
                flags=flags,
                warnings=warnings,
                confidence=confidence,
                checks_run=checks_run,
                session_id=session_id,
                task_hash=task_hash,
                inspected_at=inspected_at,
                behavioral_summary=behavioral_summary,
                degraded=False,
            )

            # Step 5: Persist audit log (best-effort — never raise from here)
            try:
                self._log.append(verdict, result.status.value)
            except Exception as log_err:
                logger.error("Inspector log write failed: %s", log_err)

            return verdict

        except Exception as exc:
            logger.exception("Inspector internal error")
            return self._build_degraded_verdict(session_id, task_hash, str(exc))

    # ------------------------------------------------------------------
    # Reporting helpers
    # ------------------------------------------------------------------

    def get_behavioral_report(self, days: int = 7) -> Dict[str, Any]:
        """
        Return the current behavioural statistics as a plain dict.

        Args:
            days: Included for API symmetry with get_recent_log_entries;
                  the behavioural monitor state is not day-partitioned.

        Returns:
            Dict representation of BehavioralReport.
        """
        report = self._monitor.get_report()
        return {
            "total_invocations": report.total_invocations,
            "success_rate": report.success_rate,
            "flag_rate": report.flag_rate,
            "security_gate_skip_rate": report.security_gate_skip_rate,
            "avg_execution_time": report.avg_execution_time,
            "recent_flags": report.recent_flags,
            "anomalies_detected": report.anomalies_detected,
            "baseline_success_rate": report.baseline_success_rate,
            "last_updated": report.last_updated,
        }

    def get_recent_log_entries(self, days: int = 7, limit: int = 50) -> List[Dict]:
        """
        Return recent audit log entries from the JSONL logs.

        Args:
            days:  Number of calendar days to look back.
            limit: Maximum number of entries to return.

        Returns:
            List of log-record dicts, newest last.
        """
        return self._log.read_recent(days=days, limit=limit)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_degraded_verdict(
        self, session_id: str, task_hash: str, error_msg: str
    ) -> InspectorVerdict:
        """
        Build a minimal degraded verdict used when inspect() itself errors.

        Args:
            session_id: The session UUID already generated for this call.
            task_hash:  The task hash already computed for this call.
            error_msg:  String representation of the caught exception.

        Returns:
            An InspectorVerdict with degraded=True and confidence=0.0.
        """
        return InspectorVerdict(
            passed=False,
            flags=[f"INSPECTOR_INTERNAL_ERROR: {error_msg[:100]}"],
            warnings=[],
            confidence=0.0,
            checks_run=[],
            session_id=session_id,
            task_hash=task_hash,
            inspected_at=datetime.now(timezone.utc).isoformat(),
            behavioral_summary={},
            degraded=True,
        )

    @staticmethod
    def _compute_task_hash(raw_input: str) -> str:
        """
        Compute a short deterministic hash of the task input.

        Args:
            raw_input: The original user task string.

        Returns:
            First 16 hex characters of the SHA-256 digest of the first 256
            bytes of the encoded input.
        """
        return hashlib.sha256(raw_input[:256].encode()).hexdigest()[:16]

    @staticmethod
    def _to_dict(verdict: InspectorVerdict) -> Dict[str, Any]:
        """
        Convert an InspectorVerdict to a plain dict.

        Args:
            verdict: The InspectorVerdict to serialise.

        Returns:
            Plain dict representation.
        """
        from dataclasses import asdict

        return asdict(verdict)
