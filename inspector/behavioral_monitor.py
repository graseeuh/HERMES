"""
HERMES Inspector General — Cross-session behavioural state tracker.

State is persisted to inspector/state/behavioral_state.json and updated
atomically on every record() call (write to .tmp then rename).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from core_logic.hermes_types import ExecutionResult, ExecutionStatus

logger = logging.getLogger("hermes.inspector.behavioral_monitor")


@dataclass
class BehavioralSnapshot:
    """Mutable cross-session state persisted to disk."""

    total_invocations: int = 0
    total_completed: int = 0
    total_failed: int = 0
    total_partial: int = 0
    total_flagged: int = 0
    total_security_gate_missing: int = 0
    execution_times: List[float] = field(default_factory=list)   # rolling last 100
    flag_history: List[str] = field(default_factory=list)        # rolling last 100
    baseline_success_rate: Optional[float] = None
    last_updated: str = ""


@dataclass
class BehavioralReport:
    """Read-only view returned to callers."""

    total_invocations: int
    success_rate: float
    flag_rate: float
    security_gate_skip_rate: float
    avg_execution_time: float
    recent_flags: List[str]          # last 20
    anomalies_detected: List[str]
    baseline_success_rate: Optional[float]
    last_updated: str


class BehavioralMonitor:
    """Tracks cross-session behavioural statistics for the Inspector General."""

    ROLLING_WINDOW_SIZE = 100
    BASELINE_MIN_SAMPLES = 10
    SUCCESS_RATE_DROP_THRESHOLD = 0.20

    def __init__(self, state_path: Path) -> None:
        """
        Initialize the monitor.

        Args:
            state_path: Full path to the JSON state file
                        (e.g. inspector/state/behavioral_state.json).
        """
        self._state_path = state_path
        self._state_path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record(
        self, result: ExecutionResult, flags: List[str], raw_input: str
    ) -> BehavioralReport:
        """
        Update state with the outcome of one orchestrator invocation and
        return a BehavioralReport reflecting the updated statistics.

        State is saved atomically: written to a .tmp file, then renamed
        to the real state path (atomic on NTFS).

        Args:
            result:    The ExecutionResult from the orchestrator.
            flags:     Flags raised by ClaimVerifier for this invocation.
            raw_input: Original user task string (reserved for future use).

        Returns:
            BehavioralReport with current statistics and any anomalies.
        """
        snapshot = self._load_state()

        # Increment counters
        snapshot.total_invocations += 1
        if result.status == ExecutionStatus.COMPLETED:
            snapshot.total_completed += 1
        elif result.status == ExecutionStatus.FAILED:
            snapshot.total_failed += 1
        elif result.status == ExecutionStatus.PARTIAL:
            snapshot.total_partial += 1

        if flags:
            snapshot.total_flagged += 1

        if "SECURITY_GATE_ABSENT" in flags:
            snapshot.total_security_gate_missing += 1

        # Rolling execution time
        snapshot.execution_times.append(result.execution_time)
        if len(snapshot.execution_times) > self.ROLLING_WINDOW_SIZE:
            snapshot.execution_times = snapshot.execution_times[-self.ROLLING_WINDOW_SIZE:]

        # Rolling flag history
        snapshot.flag_history.extend(flags)
        if len(snapshot.flag_history) > self.ROLLING_WINDOW_SIZE:
            snapshot.flag_history = snapshot.flag_history[-self.ROLLING_WINDOW_SIZE:]

        # Update baseline (set once, never changed after)
        self._update_baseline(snapshot)

        # Detect anomalies
        anomalies = self._detect_anomalies(snapshot)

        snapshot.last_updated = datetime.now(timezone.utc).isoformat()
        self._save_state(snapshot)

        return self._build_report(snapshot, anomalies, recent_n=20)

    def get_report(self, recent_n: int = 20) -> BehavioralReport:
        """
        Return a BehavioralReport from the current persisted state without
        modifying it.

        Args:
            recent_n: Number of recent flags to include in the report.

        Returns:
            BehavioralReport reflecting the last saved state.
        """
        snapshot = self._load_state()
        anomalies = self._detect_anomalies(snapshot)
        return self._build_report(snapshot, anomalies, recent_n=recent_n)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_state(self) -> BehavioralSnapshot:
        """Load and deserialise state from disk, or return a fresh snapshot."""
        if not self._state_path.exists():
            return BehavioralSnapshot()
        try:
            with self._state_path.open("r", encoding="utf-8") as fh:
                data: Dict[str, Any] = json.load(fh)
            snapshot = BehavioralSnapshot(
                total_invocations=data.get("total_invocations", 0),
                total_completed=data.get("total_completed", 0),
                total_failed=data.get("total_failed", 0),
                total_partial=data.get("total_partial", 0),
                total_flagged=data.get("total_flagged", 0),
                total_security_gate_missing=data.get("total_security_gate_missing", 0),
                execution_times=data.get("execution_times", []),
                flag_history=data.get("flag_history", []),
                baseline_success_rate=data.get("baseline_success_rate"),
                last_updated=data.get("last_updated", ""),
            )
            return snapshot
        except Exception as exc:
            logger.warning(
                "Could not load behavioral state from %s: %s — starting fresh",
                self._state_path,
                exc,
            )
            return BehavioralSnapshot()

    def _save_state(self, snapshot: BehavioralSnapshot) -> None:
        """
        Persist snapshot to disk atomically using a .tmp rename.

        Args:
            snapshot: The BehavioralSnapshot to persist.
        """
        data = {
            "total_invocations": snapshot.total_invocations,
            "total_completed": snapshot.total_completed,
            "total_failed": snapshot.total_failed,
            "total_partial": snapshot.total_partial,
            "total_flagged": snapshot.total_flagged,
            "total_security_gate_missing": snapshot.total_security_gate_missing,
            "execution_times": snapshot.execution_times,
            "flag_history": snapshot.flag_history,
            "baseline_success_rate": snapshot.baseline_success_rate,
            "last_updated": snapshot.last_updated,
        }
        tmp_path = Path(str(self._state_path) + ".tmp")
        try:
            with tmp_path.open("w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
            import os
            os.replace(tmp_path, self._state_path)
        except Exception as exc:
            logger.error("BehavioralMonitor._save_state failed: %s", exc)
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass

    def _update_baseline(self, snapshot: BehavioralSnapshot) -> None:
        """
        Set baseline_success_rate once we have enough samples; never update
        it again after that.

        Args:
            snapshot: The mutable BehavioralSnapshot being updated.
        """
        if (
            snapshot.baseline_success_rate is None
            and snapshot.total_invocations >= self.BASELINE_MIN_SAMPLES
        ):
            rate = (
                snapshot.total_completed / snapshot.total_invocations
                if snapshot.total_invocations
                else 0.0
            )
            snapshot.baseline_success_rate = rate

    def _detect_anomalies(self, snapshot: BehavioralSnapshot) -> List[str]:
        """
        Check for three predefined anomaly conditions.

        Args:
            snapshot: The current BehavioralSnapshot.

        Returns:
            List of anomaly description strings (may be empty).
        """
        anomalies: List[str] = []
        n = snapshot.total_invocations
        if n == 0:
            return anomalies

        success_rate = snapshot.total_completed / n
        flag_rate = snapshot.total_flagged / n
        security_skip_rate = snapshot.total_security_gate_missing / n

        # 1. Success rate drop vs baseline
        if (
            snapshot.baseline_success_rate is not None
            and (snapshot.baseline_success_rate - success_rate)
            > self.SUCCESS_RATE_DROP_THRESHOLD
        ):
            anomalies.append(
                f"SUCCESS_RATE_DROP: current={success_rate:.1%} "
                f"baseline={snapshot.baseline_success_rate:.1%}"
            )

        # 2. High security gate skip rate
        if security_skip_rate > 0.10:
            anomalies.append(
                f"HIGH_SECURITY_GATE_SKIP_RATE: {security_skip_rate:.1%}"
            )

        # 3. High flag rate
        if flag_rate > 0.30:
            anomalies.append(f"HIGH_FLAG_RATE: {flag_rate:.1%}")

        return anomalies

    def _build_report(
        self,
        snapshot: BehavioralSnapshot,
        anomalies: List[str],
        recent_n: int,
    ) -> BehavioralReport:
        """
        Construct a BehavioralReport from a snapshot and detected anomalies.

        Args:
            snapshot:  Current state snapshot.
            anomalies: List of anomaly strings from _detect_anomalies.
            recent_n:  How many recent flag entries to include.

        Returns:
            A populated BehavioralReport.
        """
        n = snapshot.total_invocations
        success_rate = snapshot.total_completed / n if n else 0.0
        flag_rate = snapshot.total_flagged / n if n else 0.0
        security_skip_rate = snapshot.total_security_gate_missing / n if n else 0.0
        avg_exec = (
            sum(snapshot.execution_times) / len(snapshot.execution_times)
            if snapshot.execution_times
            else 0.0
        )

        return BehavioralReport(
            total_invocations=n,
            success_rate=success_rate,
            flag_rate=flag_rate,
            security_gate_skip_rate=security_skip_rate,
            avg_execution_time=avg_exec,
            recent_flags=snapshot.flag_history[-recent_n:],
            anomalies_detected=anomalies,
            baseline_success_rate=snapshot.baseline_success_rate,
            last_updated=snapshot.last_updated,
        )
