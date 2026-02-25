import pytest
import threading
import time
from core_logic.agent_registry import AgentRegistry, AgentCapability, AgentStatus
from core_logic.task_parser import TaskType


@pytest.fixture
def registry():
    return AgentRegistry()


def make_agent(registry, name="test_agent", task_type=TaskType.CODE):
    cap = AgentCapability(task_types=[task_type])
    return registry.register_agent(
        name=name, capability=cap, prompt="test", subagent_type="general-purpose"
    )


class TestCRUD:
    def test_register_returns_agent(self, registry):
        agent = make_agent(registry)
        assert agent.agent_id.startswith("agent_")
        assert agent.status == AgentStatus.IDLE

    def test_get_agent(self, registry):
        agent = make_agent(registry)
        fetched = registry.get_agent(agent.agent_id)
        assert fetched is not None
        assert fetched.agent_id == agent.agent_id

    def test_get_nonexistent_returns_none(self, registry):
        assert registry.get_agent("agent_doesnotexist") is None

    def test_assign_task_changes_status(self, registry):
        agent = make_agent(registry)
        result = registry.assign_task(agent.agent_id, "task_1")
        assert result is True
        assert registry.get_agent(agent.agent_id).status == AgentStatus.RUNNING

    def test_complete_task_returns_to_idle(self, registry):
        agent = make_agent(registry)
        registry.assign_task(agent.agent_id, "task_1")
        registry.complete_task(agent.agent_id, "task_1", result="done")
        assert registry.get_agent(agent.agent_id).status == AgentStatus.IDLE

    def test_deregister_removes_agent(self, registry):
        agent = make_agent(registry)
        registry.deregister_agent(agent.agent_id)
        assert registry.get_agent(agent.agent_id) is None

    def test_get_registry_stats(self, registry):
        make_agent(registry)
        stats = registry.get_registry_stats()
        assert stats["total_agents"] == 1
        assert stats["idle_agents"] == 1


class TestThreadSafety:
    def test_concurrent_register_and_complete(self, registry):
        errors = []

        def worker(i):
            try:
                cap = AgentCapability(task_types=[TaskType.CODE])
                agent = registry.register_agent(
                    name=f"agent_{i}", capability=cap,
                    prompt="test", subagent_type="general-purpose"
                )
                registry.assign_task(agent.agent_id, f"task_{i}")
                time.sleep(0.005)
                registry.complete_task(agent.agent_id, f"task_{i}", result=f"result_{i}")
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Race condition errors: {errors}"
        stats = registry.get_registry_stats()
        assert stats["total_agents"] == 20
        assert stats["idle_agents"] == 20

    def test_concurrent_queue_task(self, registry):
        """Multiple threads queuing tasks on separate agents."""
        errors = []
        agents = [make_agent(registry, name=f"a_{i}") for i in range(10)]

        def queue_worker(agent, task_id):
            try:
                registry.queue_task(
                    agent.agent_id, task_id, "desc",
                    TaskType.CODE, {}
                )
            except Exception as e:
                errors.append(str(e))

        threads = [
            threading.Thread(target=queue_worker, args=(agents[i], f"task_{i}"))
            for i in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
