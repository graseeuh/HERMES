"""
HERMES Inspector General — Append-only JSONL audit log.

One file per calendar day (UTC):  inspector/logs/inspector_YYYYMMDD.jsonl
Each line is one JSON object with a fixed schema (schema_version "1").
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from .inspector_general import InspectorVerdict

logger = logging.getLogger("hermes.inspector.log")


class InspectorLog:
    """Append-only JSONL writer for Inspector General audit records."""

    def __init__(self, log_dir: Path) -> None:
        """
        Initialize the log writer, creating the log directory if missing.

        Args:
            log_dir: Directory that will contain daily JSONL log files.
        """
        self._log_dir = log_dir
        self._log_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def append(self, verdict: Any, result_status: str) -> None:
        """
        Append one audit record (one JSON line) to today's log file.

        Opens the file in append mode, writes exactly one line, then closes.
        Never raises — all exceptions are swallowed and logged.

        Args:
            verdict:       The InspectorVerdict dataclass instance.
            result_status: The orchestrator's ExecutionStatus string value.
        """
        try:
            behavioral_summary = getattr(verdict, "behavioral_summary", {})
            record = {
                "schema_version": "1",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "session_id": verdict.session_id,
                "task_hash": verdict.task_hash,
                "orchestrator_status": result_status,
                "inspector_passed": verdict.passed,
                "inspector_degraded": verdict.degraded,
                "confidence": verdict.confidence,
                "flags": verdict.flags,
                "warnings": verdict.warnings,
                "checks_run": verdict.checks_run,
                "execution_time_reported": behavioral_summary.get("avg_execution_time"),
                "agents_used_count": behavioral_summary.get("total_invocations"),
                "results_key_count": None,
                "behavioral_summary": {
                    "total_invocations": behavioral_summary.get("total_invocations"),
                    "success_rate": behavioral_summary.get("success_rate"),
                    "flag_rate": behavioral_summary.get("flag_rate"),
                    "security_gate_skip_rate": behavioral_summary.get(
                        "security_gate_skip_rate"
                    ),
                    "avg_execution_time": behavioral_summary.get("avg_execution_time"),
                    "anomalies_detected": behavioral_summary.get(
                        "anomalies_detected", []
                    ),
                },
            }
            log_path = self._log_file_path()
            with log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record) + "\n")
        except Exception as exc:
            logger.error("InspectorLog.append failed: %s", exc)

    def read_recent(self, days: int = 7, limit: int = 500) -> List[Dict]:
        """
        Read log entries from the last N calendar days (UTC).

        Skips corrupt or unparseable lines silently.  Returns entries in
        chronological order (oldest first, newest last), capped at `limit`.

        Args:
            days:  Number of calendar days to look back (inclusive of today).
            limit: Maximum total number of entries to return.

        Returns:
            List of parsed log-record dicts, newest last.
        """
        entries: List[Dict] = []
        today = datetime.now(timezone.utc).date()
        for delta in range(days - 1, -1, -1):
            day = today - timedelta(days=delta)
            path = self._log_file_path(date_utc=day)
            if not path.exists():
                continue
            try:
                with path.open("r", encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            logger.warning(
                                "Skipping corrupt log line in %s", path.name
                            )
            except Exception as exc:
                logger.warning("Could not read log file %s: %s", path, exc)

        # Trim to limit (keep newest, which are at the end)
        if len(entries) > limit:
            entries = entries[-limit:]
        return entries

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _log_file_path(self, date_utc: Optional[date] = None) -> Path:
        """
        Return the Path for the JSONL log file for the given UTC date.

        Args:
            date_utc: The calendar date (UTC).  Defaults to today (UTC).

        Returns:
            Absolute Path to the daily JSONL log file.
        """
        if date_utc is None:
            date_utc = datetime.now(timezone.utc).date()
        filename = f"inspector_{date_utc.strftime('%Y%m%d')}.jsonl"
        return self._log_dir / filename
