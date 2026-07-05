"""
HERMES Approval Gate
Pre-execution approval gate for destructive tasks.
Lives entirely at the MCP layer — the orchestrator is never modified.
"""
from __future__ import annotations

import json
import logging
import os
import re
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger("hermes.approval.gate")

APPROVAL_TIMEOUT_SECONDS = 300  # 5 minutes

_DESTRUCTIVE_PATTERNS = [
    (
        r'\b(?:delete|remove|erase|wipe|drop\s+table|truncate|rm\b)',
        "File/data deletion (delete, remove, erase, wipe, drop table, truncate, rm)"
    ),
    (
        r'\b(?:git\s+push|push\s+to\s+remote|force\s+push|push\s+--force|deploy\b)',
        "Git remote operation (git push, push to remote, deploy, force push)"
    ),
    (
        r'\b(?:pip\s+install|npm\s+install|apt(?:-get)?\s+install|brew\s+install|yarn\s+add)',
        "Package installation (pip install, npm install, apt install)"
    ),
    (
        r'\b(?:send\s+(?:an?\s+)?email|post\s+to|webhook|call\s+(?:an?\s+)?api|http\s+post|curl\b)',
        "External communication (send email, post to, webhook, call API, HTTP POST)"
    ),
    (
        r'\b(?:kill\s+process|shutdown|restart\s+service|format\s+disk|reboot)',
        "System operation (kill process, shutdown, restart service, format disk)"
    ),
    (
        r'\b(?:overwrite|replace\s+all|rewrite\s+(?:the\s+)?entire)',
        "Overwrite operation (overwrite, replace all, rewrite entire)"
    ),
]


@dataclass
class PendingApproval:
    request_id: str
    task: str
    matched_patterns: List[str]
    status: str              # "pending" | "approved" | "denied" | "expired"
    created_at: str          # ISO 8601 UTC
    expires_at: str          # ISO 8601 UTC
    resolved_at: Optional[str]
    reason: str


class ApprovalGate:
    """
    Pre-execution approval gate for destructive tasks.
    Instantiated once as a singleton in mcp_server.py.
    State persisted to approval/state/pending_approvals.json.
    """

    def __init__(self, base_path: str) -> None:
        root = Path(base_path)
        self._state_dir = root / "approval" / "state"
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._state_file = self._state_dir / "pending_approvals.json"
        self._patterns = [
            (re.compile(pat, re.IGNORECASE), desc)
            for pat, desc in _DESTRUCTIVE_PATTERNS
        ]

    def requires_approval(self, task: str) -> List[str]:
        """Return list of matched pattern descriptions. Empty = safe to execute."""
        matched = []
        for compiled, description in self._patterns:
            if compiled.search(task):
                matched.append(description)
        return matched

    def create_request(self, task: str, patterns: List[str]) -> PendingApproval:
        """Create and persist a new pending approval request."""
        now = datetime.now(timezone.utc)
        expires = datetime.fromtimestamp(
            now.timestamp() + APPROVAL_TIMEOUT_SECONDS, tz=timezone.utc
        )
        request_id = "req_" + uuid.uuid4().hex[:8]

        approval = PendingApproval(
            request_id=request_id,
            task=task[:5000],
            matched_patterns=patterns,
            status="pending",
            created_at=now.isoformat(),
            expires_at=expires.isoformat(),
            resolved_at=None,
            reason="",
        )

        state = self._load_state()
        state[request_id] = asdict(approval)
        self._save_state(state)
        logger.info("Approval request created: %s patterns=%s task=%.80s", request_id, patterns, task)
        return approval

    def resolve(self, request_id: str, approved: bool, reason: str) -> PendingApproval:
        """Resolve a pending approval request. Raises KeyError/ValueError if invalid."""
        state = self._load_state()
        if request_id not in state:
            raise KeyError(f"Approval request not found: {request_id}")

        record = state[request_id]
        if record["status"] != "pending":
            raise ValueError(
                f"Request {request_id!r} is not pending (status={record['status']!r})"
            )

        record["status"] = "approved" if approved else "denied"
        record["resolved_at"] = datetime.now(timezone.utc).isoformat()
        record["reason"] = reason
        state[request_id] = record
        self._save_state(state)

        approval = self._dict_to_approval(record)
        logger.info("Approval request resolved: %s status=%s", request_id, approval.status)
        return approval

    def get_request(self, request_id: str) -> Optional[PendingApproval]:
        """Return a single approval request by ID, or None if not found."""
        state = self._load_state()
        record = state.get(request_id)
        return self._dict_to_approval(record) if record is not None else None

    def list_pending(self) -> List[PendingApproval]:
        """Return all requests with status='pending', sorted by created_at ascending."""
        state = self._load_state()
        pending = [
            self._dict_to_approval(v)
            for v in state.values()
            if v.get("status") == "pending"
        ]
        pending.sort(key=lambda a: a.created_at)
        return pending

    def cleanup_expired(self) -> int:
        """Mark timed-out pending requests as 'expired'. Returns count changed."""
        now = datetime.now(timezone.utc)
        state = self._load_state()
        count = 0

        for record in state.values():
            if record.get("status") != "pending":
                continue
            if now >= datetime.fromisoformat(record["expires_at"]):
                record["status"] = "expired"
                record["resolved_at"] = now.isoformat()
                count += 1

        if count > 0:
            self._save_state(state)
            logger.info("Expired %d approval request(s)", count)

        return count

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_state(self) -> Dict:
        if not self._state_file.exists():
            return {}
        try:
            with self._state_file.open("r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception as exc:
            logger.warning("Could not load approval state: %s — starting fresh", exc)
            return {}

    def _save_state(self, state: Dict) -> None:
        tmp_path = Path(str(self._state_file) + ".tmp")
        try:
            with tmp_path.open("w", encoding="utf-8") as fh:
                json.dump(state, fh, indent=2)
            os.replace(tmp_path, self._state_file)
        except Exception as exc:
            logger.error("ApprovalGate._save_state failed: %s", exc)
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass

    @staticmethod
    def _dict_to_approval(record: Dict) -> PendingApproval:
        return PendingApproval(
            request_id=record["request_id"],
            task=record["task"],
            matched_patterns=record["matched_patterns"],
            status=record["status"],
            created_at=record["created_at"],
            expires_at=record["expires_at"],
            resolved_at=record.get("resolved_at"),
            reason=record.get("reason", ""),
        )
