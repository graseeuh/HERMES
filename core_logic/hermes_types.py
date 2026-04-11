"""
Shared data-transfer objects for HERMES.

Both core_logic and inspector need ExecutionResult / ExecutionStatus.
Defining them here keeps the three architectural layers structurally
isolated — neither layer imports from the other.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List


class ExecutionStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass
class ExecutionResult:
    """Result of executing a task through the orchestrator."""
    status: ExecutionStatus
    original_input: str
    results: Dict[str, Any]
    errors: Dict[str, str]
    execution_time: float
    agents_used: List[str]
    agents_buffed: List[str]
    summary: str
