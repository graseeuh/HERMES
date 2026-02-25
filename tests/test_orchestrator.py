import pytest
import time
from unittest.mock import MagicMock, patch
from core_logic.orchestrator import Orchestrator, ExecutionPlan, ExecutionStatus
from core_logic.task_parser import SubTask, TaskType, ParsedTask
from core_logic.prompt_generator import GeneratedPrompt


def make_subtask(task_id, task_type=TaskType.CODE, deps=None):
    return SubTask(
        id=task_id,
        description=f"Test task {task_id}",
        task_type=task_type,
        dependencies=deps or [],
        context={},
    )


def make_prompt(task_id):
    return GeneratedPrompt(
        prompt_id=f"p_{task_id}",
        template_name="code_agent",
        task_type="code",
        rendered_prompt=f"Do task {task_id}",
        variables_used={},
        created_at="2026-01-01T00:00:00",
        task_hash="abc123",
    )


@pytest.fixture
def orchestrator(tmp_path):
    kb = str(tmp_path / "knowledge_base")
    import os
    os.makedirs(kb, exist_ok=True)
    return Orchestrator(knowledge_base_path=kb)


class TestExecuteGroup:
    def test_single_task_fast_path(self, orchestrator):
        """Single-task group skips ThreadPoolExecutor."""
        subtask = make_subtask("t1")
        plan = ExecutionPlan(
            parsed_task=ParsedTask(original_input="test", subtasks=[subtask]),
            execution_groups=[[subtask]],
            agent_assignments={"t1": None},
            buff_decisions={"t1": False},
            prompts={"t1": make_prompt("t1")},
        )

        with patch.object(orchestrator, "_execute_subtask", return_value={"result": "ok"}) as mock:
            result = orchestrator._execute_group([subtask], plan, {})

        mock.assert_called_once_with(subtask, plan, {})
        assert result == {"t1": {"result": "ok"}}

    def test_parallel_tasks_all_complete(self, orchestrator):
        """Multiple tasks in a group all get results."""
        subtasks = [make_subtask(f"t{i}") for i in range(3)]
        plan = ExecutionPlan(
            parsed_task=ParsedTask(original_input="test", subtasks=subtasks),
            execution_groups=[subtasks],
            agent_assignments={s.id: None for s in subtasks},
            buff_decisions={s.id: False for s in subtasks},
            prompts={s.id: make_prompt(s.id) for s in subtasks},
        )

        def slow_subtask(subtask, *args):
            time.sleep(0.05)
            return {"result": f"done_{subtask.id}"}

        with patch.object(orchestrator, "_execute_subtask", side_effect=slow_subtask):
            start = time.time()
            result = orchestrator._execute_group(subtasks, plan, {})
            elapsed = time.time() - start

        assert len(result) == 3
        assert all(r.get("result") for r in result.values())
        # 3 tasks x 0.05s each: parallel should finish in ~0.05-0.15s, not 0.15s+
        assert elapsed < 0.14, f"Parallel execution took {elapsed:.2f}s — may not be running in parallel"

    def test_one_task_failure_does_not_kill_group(self, orchestrator):
        """An exception in one subtask is caught; others still return results."""
        subtasks = [make_subtask("t1"), make_subtask("t2"), make_subtask("t3")]
        plan = ExecutionPlan(
            parsed_task=ParsedTask(original_input="test", subtasks=subtasks),
            execution_groups=[subtasks],
            agent_assignments={s.id: None for s in subtasks},
            buff_decisions={s.id: False for s in subtasks},
            prompts={s.id: make_prompt(s.id) for s in subtasks},
        )

        def flaky(subtask, *args):
            if subtask.id == "t2":
                raise RuntimeError("task t2 exploded")
            return {"result": f"ok_{subtask.id}"}

        with patch.object(orchestrator, "_execute_subtask", side_effect=flaky):
            result = orchestrator._execute_group(subtasks, plan, {})

        assert "error" in result["t2"]
        assert result["t1"].get("result") == "ok_t1"
        assert result["t3"].get("result") == "ok_t3"

    def test_max_parallel_agents_respected(self, orchestrator):
        """No more than max_parallel_agents threads run simultaneously."""
        orchestrator._max_parallel_agents = 2
        concurrent_count = [0]
        max_seen = [0]

        subtasks = [make_subtask(f"t{i}") for i in range(4)]
        plan = ExecutionPlan(
            parsed_task=ParsedTask(original_input="test", subtasks=subtasks),
            execution_groups=[subtasks],
            agent_assignments={s.id: None for s in subtasks},
            buff_decisions={s.id: False for s in subtasks},
            prompts={s.id: make_prompt(s.id) for s in subtasks},
        )

        import threading
        lock = threading.Lock()

        def tracked(subtask, *args):
            with lock:
                concurrent_count[0] += 1
                max_seen[0] = max(max_seen[0], concurrent_count[0])
            time.sleep(0.05)
            with lock:
                concurrent_count[0] -= 1
            return {"result": "ok"}

        with patch.object(orchestrator, "_execute_subtask", side_effect=tracked):
            orchestrator._execute_group(subtasks, plan, {})

        assert max_seen[0] <= 2, f"Max concurrent was {max_seen[0]}, limit is 2"
