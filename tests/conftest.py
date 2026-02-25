import pytest
from pathlib import Path
from core_logic.orchestrator import ExecutionResult, ExecutionStatus


@pytest.fixture
def hermes_base(tmp_path):
    """Temporary HERMES base directory with required subdirs."""
    (tmp_path / "inspector" / "logs").mkdir(parents=True)
    (tmp_path / "inspector" / "state").mkdir(parents=True)
    (tmp_path / "approval" / "state").mkdir(parents=True)
    (tmp_path / "data" / "quarantine").mkdir(parents=True)
    return tmp_path


@pytest.fixture
def clean_result():
    """A well-formed completed ExecutionResult that should pass all checks."""
    return ExecutionResult(
        status=ExecutionStatus.COMPLETED,
        original_input="analyze the codebase",
        results={
            "task_1": {"agent_id": "a1", "task_id": "task_1", "status": "completed", "output": "done"},
            "security_gate": {"agent_id": "sg", "task_id": "security_gate", "status": "completed", "output": "clean"},
        },
        errors={},
        execution_time=5.0,
        agents_used=["a1"],
        agents_buffed=[],
        summary="Execution Summary for: analyze the codebase...",
    )


@pytest.fixture
def partial_result():
    """A partial result with some errors."""
    return ExecutionResult(
        status=ExecutionStatus.PARTIAL,
        original_input="build something",
        results={"security_gate": {"status": "completed", "output": "clean"}},
        errors={"task_1": "subprocess timeout"},
        execution_time=10.0,
        agents_used=["a1"],
        agents_buffed=[],
        summary="Execution Summary for: build something...",
    )
