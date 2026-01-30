"""
HERMES Subagent Test Suite
Comprehensive tests for agent registry, matcher, orchestrator, and bridge components.
Run with: python test_subagent.py
"""

import unittest
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core_logic.task_parser import TaskParser, TaskType, SubTask, ParsedTask
from core_logic.agent_registry import (
    AgentRegistry, AgentRecord, AgentCapability, AgentStatus, QueuedTask
)
from core_logic.agent_matcher import AgentMatcher, MatchResult
from core_logic.orchestrator import Orchestrator, ExecutionStatus
from integration.claude_bridge import ClaudeBridge, SubagentType


class TestTaskParser(unittest.TestCase):
    """Tests for TaskParser component."""

    def setUp(self):
        self.parser = TaskParser()

    def test_parse_simple_task(self):
        """Test parsing a simple single task."""
        result = self.parser.parse("write a function to calculate fibonacci")
        self.assertIsInstance(result, ParsedTask)
        self.assertEqual(len(result.subtasks), 1)
        self.assertEqual(result.subtasks[0].task_type, TaskType.CODE)

    def test_parse_research_task(self):
        """Test parsing a research-type task."""
        result = self.parser.parse("find all files that handle user authentication")
        self.assertEqual(result.subtasks[0].task_type, TaskType.RESEARCH)

    def test_parse_vision_task(self):
        """Test parsing a vision-type task."""
        result = self.parser.parse("use the webcam to detect hand gestures with mediapipe")
        self.assertEqual(result.subtasks[0].task_type, TaskType.VISION)

    def test_parse_audio_task(self):
        """Test parsing an audio-type task."""
        result = self.parser.parse("listen to the microphone and detect voice commands")
        self.assertEqual(result.subtasks[0].task_type, TaskType.AUDIO)

    def test_parse_plan_task(self):
        """Test parsing a planning task."""
        result = self.parser.parse("design the architecture for a new authentication system")
        self.assertEqual(result.subtasks[0].task_type, TaskType.PLAN)

    def test_parse_multiple_tasks(self):
        """Test parsing multiple tasks separated by 'and'."""
        result = self.parser.parse("find the config files and then update the settings")
        self.assertGreaterEqual(len(result.subtasks), 1)

    def test_extract_file_context(self):
        """Test extraction of file paths from input."""
        result = self.parser.parse("review the code in main.py and config.json")
        self.assertIn('files', result.global_context)

    def test_extract_technology_context(self):
        """Test extraction of technology mentions."""
        result = self.parser.parse("use opencv and mediapipe to process images")
        self.assertIn('technologies', result.global_context)
        self.assertIn('opencv', result.global_context['technologies'])
        self.assertIn('mediapipe', result.global_context['technologies'])

    def test_empty_input_raises_error(self):
        """Test that empty input raises ValueError."""
        with self.assertRaises(ValueError):
            self.parser.parse("")

    def test_invalid_input_type_raises_error(self):
        """Test that non-string input raises TypeError."""
        with self.assertRaises(TypeError):
            self.parser.parse(123)

    def test_parallel_groups(self):
        """Test parallel group generation."""
        result = self.parser.parse("search for auth code, implement login, create tests")
        groups = result.get_parallel_groups()
        self.assertIsInstance(groups, list)
        self.assertGreater(len(groups), 0)


class TestAgentRegistry(unittest.TestCase):
    """Tests for AgentRegistry component."""

    def setUp(self):
        self.registry = AgentRegistry()
        self.test_capability = AgentCapability(
            task_types=[TaskType.CODE],
            specializations=['python', 'testing'],
            max_concurrent_tasks=3
        )

    def test_register_agent(self):
        """Test registering a new agent."""
        agent = self.registry.register_agent(
            name="test_agent",
            capability=self.test_capability,
            prompt="Test prompt",
            subagent_type="general-purpose"
        )
        self.assertIsInstance(agent, AgentRecord)
        self.assertTrue(agent.agent_id.startswith("agent_"))
        self.assertEqual(agent.status, AgentStatus.IDLE)

    def test_get_agent(self):
        """Test retrieving an agent by ID."""
        agent = self.registry.register_agent(
            name="test_agent",
            capability=self.test_capability,
            prompt="Test prompt",
            subagent_type="general-purpose"
        )
        retrieved = self.registry.get_agent(agent.agent_id)
        self.assertEqual(retrieved.agent_id, agent.agent_id)

    def test_get_nonexistent_agent(self):
        """Test retrieving a nonexistent agent returns None."""
        result = self.registry.get_agent("nonexistent_id")
        self.assertIsNone(result)

    def test_assign_task(self):
        """Test assigning a task to an agent."""
        agent = self.registry.register_agent(
            name="test_agent",
            capability=self.test_capability,
            prompt="Test prompt",
            subagent_type="general-purpose"
        )
        success = self.registry.assign_task(agent.agent_id, "task_1")
        self.assertTrue(success)
        self.assertEqual(agent.status, AgentStatus.RUNNING)
        self.assertIn("task_1", agent.current_tasks)

    def test_complete_task(self):
        """Test completing a task."""
        agent = self.registry.register_agent(
            name="test_agent",
            capability=self.test_capability,
            prompt="Test prompt",
            subagent_type="general-purpose"
        )
        self.registry.assign_task(agent.agent_id, "task_1")
        success = self.registry.complete_task(agent.agent_id, "task_1", result="success")
        self.assertTrue(success)
        self.assertEqual(agent.status, AgentStatus.IDLE)
        self.assertNotIn("task_1", agent.current_tasks)

    def test_queue_task(self):
        """Test queuing a task for buffered execution."""
        agent = self.registry.register_agent(
            name="test_agent",
            capability=self.test_capability,
            prompt="Test prompt",
            subagent_type="general-purpose"
        )
        success = self.registry.queue_task(
            agent.agent_id, "task_1", "Test task", TaskType.CODE, {}
        )
        self.assertTrue(success)
        self.assertEqual(agent.status, AgentStatus.BUFFERED)
        self.assertEqual(len(agent.task_queue), 1)

    def test_get_available_agents(self):
        """Test getting available agents."""
        agent1 = self.registry.register_agent(
            name="agent1",
            capability=self.test_capability,
            prompt="Test",
            subagent_type="general-purpose"
        )
        available = self.registry.get_available_agents()
        self.assertIn(agent1, available)

    def test_get_agents_by_type(self):
        """Test getting agents by task type."""
        self.registry.register_agent(
            name="code_agent",
            capability=AgentCapability(task_types=[TaskType.CODE]),
            prompt="Test",
            subagent_type="general-purpose"
        )
        self.registry.register_agent(
            name="research_agent",
            capability=AgentCapability(task_types=[TaskType.RESEARCH]),
            prompt="Test",
            subagent_type="Explore"
        )
        code_agents = self.registry.get_agents_by_type(TaskType.CODE)
        self.assertEqual(len(code_agents), 1)
        self.assertEqual(code_agents[0].name, "code_agent")

    def test_deregister_agent(self):
        """Test removing an agent from registry."""
        agent = self.registry.register_agent(
            name="test_agent",
            capability=self.test_capability,
            prompt="Test",
            subagent_type="general-purpose"
        )
        success = self.registry.deregister_agent(agent.agent_id)
        self.assertTrue(success)
        self.assertIsNone(self.registry.get_agent(agent.agent_id))

    def test_registry_stats(self):
        """Test registry statistics."""
        self.registry.register_agent(
            name="agent1",
            capability=self.test_capability,
            prompt="Test",
            subagent_type="general-purpose"
        )
        stats = self.registry.get_registry_stats()
        self.assertEqual(stats['total_agents'], 1)
        self.assertEqual(stats['idle_agents'], 1)

    def test_agent_workload_limit(self):
        """Test that agents respect max concurrent tasks."""
        capability = AgentCapability(
            task_types=[TaskType.CODE],
            max_concurrent_tasks=2
        )
        agent = self.registry.register_agent(
            name="test_agent",
            capability=capability,
            prompt="Test",
            subagent_type="general-purpose"
        )
        self.registry.assign_task(agent.agent_id, "task_1")
        self.registry.assign_task(agent.agent_id, "task_2")
        # Should fail - at capacity
        success = self.registry.assign_task(agent.agent_id, "task_3")
        self.assertFalse(success)


class TestAgentMatcher(unittest.TestCase):
    """Tests for AgentMatcher component."""

    def setUp(self):
        self.registry = AgentRegistry()
        self.matcher = AgentMatcher(self.registry)

    def test_no_match_when_empty(self):
        """Test that no match is found when registry is empty."""
        subtask = SubTask(
            id="task_1",
            description="write some code",
            task_type=TaskType.CODE
        )
        result = self.matcher.find_match(subtask)
        self.assertFalse(result.matched)
        self.assertIsNone(result.agent)

    def test_match_by_task_type(self):
        """Test matching by task type."""
        self.registry.register_agent(
            name="code_agent",
            capability=AgentCapability(task_types=[TaskType.CODE]),
            prompt="Test",
            subagent_type="general-purpose"
        )
        subtask = SubTask(
            id="task_1",
            description="implement a function",
            task_type=TaskType.CODE
        )
        result = self.matcher.find_match(subtask)
        self.assertTrue(result.matched)
        self.assertIsNotNone(result.agent)

    def test_no_match_wrong_type(self):
        """Test no match when task type doesn't match."""
        self.registry.register_agent(
            name="code_agent",
            capability=AgentCapability(task_types=[TaskType.CODE]),
            prompt="Test",
            subagent_type="general-purpose"
        )
        subtask = SubTask(
            id="task_1",
            description="explore the codebase",
            task_type=TaskType.RESEARCH
        )
        result = self.matcher.find_match(subtask)
        self.assertFalse(result.matched)

    def test_suggest_agent_type(self):
        """Test subagent type suggestion."""
        subtask_code = SubTask(id="t1", description="code", task_type=TaskType.CODE)
        subtask_research = SubTask(id="t2", description="research", task_type=TaskType.RESEARCH)
        subtask_plan = SubTask(id="t3", description="plan", task_type=TaskType.PLAN)

        self.assertEqual(self.matcher.suggest_agent_type(subtask_code), "general-purpose")
        self.assertEqual(self.matcher.suggest_agent_type(subtask_research), "Explore")
        self.assertEqual(self.matcher.suggest_agent_type(subtask_plan), "Plan")

    def test_buffing_recommendation(self):
        """Test buffing recommendation generation."""
        subtask = SubTask(
            id="task_1",
            description="implement feature",
            task_type=TaskType.CODE
        )
        recommendation = self.matcher.get_buffing_recommendation(subtask)
        self.assertIn('recommendation', recommendation)
        self.assertIn('suggested_subagent_type', recommendation)

    def test_match_with_specialization(self):
        """Test matching considers specializations."""
        self.registry.register_agent(
            name="python_agent",
            capability=AgentCapability(
                task_types=[TaskType.CODE],
                specializations=['python', 'testing']
            ),
            prompt="Test",
            subagent_type="general-purpose"
        )
        subtask = SubTask(
            id="task_1",
            description="write python tests for the module",
            task_type=TaskType.CODE
        )
        result = self.matcher.find_match(subtask)
        self.assertTrue(result.matched)
        self.assertGreater(result.score, 0.5)


class TestClaudeBridge(unittest.TestCase):
    """Tests for ClaudeBridge component."""

    def setUp(self):
        self.bridge = ClaudeBridge()

    def test_spawn_agent(self):
        """Test spawning a new agent."""
        result = self.bridge.spawn_agent(
            prompt="Test prompt",
            subagent_type="general-purpose",
            description="Test task"
        )
        self.assertIn('agent_id', result)
        self.assertIn('task_tool_params', result)
        self.assertEqual(result['status'], 'ready_to_spawn')

    def test_spawn_agent_with_model(self):
        """Test spawning with specific model."""
        result = self.bridge.spawn_agent(
            prompt="Test prompt",
            subagent_type="general-purpose",
            description="Test task",
            model="haiku"
        )
        self.assertEqual(result['task_tool_params']['model'], 'haiku')

    def test_spawn_agent_background(self):
        """Test spawning in background."""
        result = self.bridge.spawn_agent(
            prompt="Test prompt",
            subagent_type="general-purpose",
            description="Test task",
            run_in_background=True
        )
        self.assertTrue(result['task_tool_params']['run_in_background'])

    def test_spawn_parallel_agents(self):
        """Test spawning multiple agents."""
        requests = [
            {'prompt': 'Task 1', 'subagent_type': 'general-purpose', 'description': 'Task 1'},
            {'prompt': 'Task 2', 'subagent_type': 'Explore', 'description': 'Task 2'}
        ]
        results = self.bridge.spawn_parallel_agents(requests)
        self.assertEqual(len(results), 2)
        self.assertNotEqual(results[0]['agent_id'], results[1]['agent_id'])

    def test_add_task_to_agent(self):
        """Test adding task to existing agent (buffing)."""
        spawn_result = self.bridge.spawn_agent(
            prompt="Initial task",
            subagent_type="general-purpose",
            description="Initial"
        )
        buff_result = self.bridge.add_task_to_agent(
            agent_id=spawn_result['agent_id'],
            prompt="Additional task",
            task_description="Continue work"
        )
        self.assertEqual(buff_result['status'], 'ready_to_buff')
        self.assertTrue(buff_result['is_continuation'])

    def test_add_task_to_nonexistent_agent(self):
        """Test adding task to nonexistent agent fails."""
        result = self.bridge.add_task_to_agent(
            agent_id="nonexistent",
            prompt="Task",
            task_description="Test"
        )
        self.assertEqual(result['status'], 'failed')

    def test_record_and_get_result(self):
        """Test recording and retrieving agent results."""
        spawn_result = self.bridge.spawn_agent(
            prompt="Test",
            subagent_type="general-purpose",
            description="Test"
        )
        self.bridge.record_result(
            agent_id=spawn_result['agent_id'],
            output="Success output"
        )
        result = self.bridge.get_result(spawn_result['agent_id'])
        self.assertIsNotNone(result)
        self.assertEqual(result.status, 'completed')
        self.assertEqual(result.output, "Success output")

    def test_record_error_result(self):
        """Test recording error result."""
        spawn_result = self.bridge.spawn_agent(
            prompt="Test",
            subagent_type="general-purpose",
            description="Test"
        )
        self.bridge.record_result(
            agent_id=spawn_result['agent_id'],
            output="",
            error="Something went wrong"
        )
        result = self.bridge.get_result(spawn_result['agent_id'])
        self.assertEqual(result.status, 'failed')
        self.assertEqual(result.error, "Something went wrong")

    def test_get_active_agents(self):
        """Test getting list of active agents."""
        self.bridge.spawn_agent("Test1", "general-purpose", "Task1")
        self.bridge.spawn_agent("Test2", "general-purpose", "Task2")
        active = self.bridge.get_active_agents()
        self.assertEqual(len(active), 2)

    def test_get_subagent_type_mapping(self):
        """Test task type to subagent type mapping."""
        self.assertEqual(self.bridge.get_subagent_type('code'), 'general-purpose')
        self.assertEqual(self.bridge.get_subagent_type('research'), 'Explore')
        self.assertEqual(self.bridge.get_subagent_type('plan'), 'Plan')
        self.assertEqual(self.bridge.get_subagent_type('unknown'), 'general-purpose')

    def test_clear(self):
        """Test clearing all agents."""
        self.bridge.spawn_agent("Test", "general-purpose", "Task")
        self.bridge.clear()
        self.assertEqual(len(self.bridge.get_active_agents()), 0)


class TestOrchestrator(unittest.TestCase):
    """Tests for Orchestrator component."""

    def setUp(self):
        # Use the actual knowledge_base path
        kb_path = Path(__file__).parent / "knowledge_base"
        self.orchestrator = Orchestrator(str(kb_path))

    def test_process_request(self):
        """Test processing a user request into execution plan."""
        plan = self.orchestrator.process_request("implement a fibonacci function")
        self.assertIsNotNone(plan)
        self.assertGreater(len(plan.parsed_task.subtasks), 0)

    def test_execute_plan_simulated(self):
        """Test executing a plan (simulated without Claude bridge)."""
        plan = self.orchestrator.process_request("write a hello world function")
        result = self.orchestrator.execute_plan(plan)
        self.assertEqual(result.status, ExecutionStatus.COMPLETED)
        self.assertGreater(len(result.agents_used), 0)

    def test_process_and_execute(self):
        """Test convenience method for process and execute."""
        result = self.orchestrator.process_and_execute("create a simple calculator")
        self.assertIsNotNone(result)
        self.assertIn(result.status, [ExecutionStatus.COMPLETED, ExecutionStatus.PARTIAL])

    def test_get_status(self):
        """Test getting orchestrator status."""
        status = self.orchestrator.get_status()
        self.assertIn('registry_stats', status)
        self.assertIn('has_claude_bridge', status)

    def test_callbacks(self):
        """Test that callbacks are called during execution."""
        spawned_agents = []
        completed_agents = []

        def on_spawn(agent, subtask):
            spawned_agents.append(agent.agent_id)

        def on_complete(agent, subtask, result):
            completed_agents.append(agent.agent_id)

        self.orchestrator.set_callbacks(
            on_agent_spawn=on_spawn,
            on_agent_complete=on_complete
        )

        self.orchestrator.process_and_execute("write a test function")

        self.assertGreater(len(spawned_agents), 0)
        self.assertGreater(len(completed_agents), 0)

    def test_with_claude_bridge(self):
        """Test orchestrator with ClaudeBridge attached."""
        bridge = ClaudeBridge()
        self.orchestrator.set_claude_bridge(bridge)
        self.assertTrue(self.orchestrator.get_status()['has_claude_bridge'])


class TestIntegration(unittest.TestCase):
    """Integration tests for the complete agent system."""

    def setUp(self):
        kb_path = Path(__file__).parent / "knowledge_base"
        self.orchestrator = Orchestrator(str(kb_path))
        self.bridge = ClaudeBridge()
        self.orchestrator.set_claude_bridge(self.bridge)

    def test_full_workflow(self):
        """Test complete workflow from input to result."""
        # Process request
        plan = self.orchestrator.process_request(
            "explore the codebase structure and then implement error handling"
        )

        # Verify plan structure
        self.assertGreater(len(plan.parsed_task.subtasks), 0)
        self.assertIsNotNone(plan.execution_groups)

        # Execute
        result = self.orchestrator.execute_plan(plan)

        # Verify result
        self.assertIn(result.status, [
            ExecutionStatus.COMPLETED,
            ExecutionStatus.PARTIAL
        ])
        self.assertIsInstance(result.summary, str)

    def test_multi_task_parallel_grouping(self):
        """Test that independent tasks are grouped for parallel execution."""
        plan = self.orchestrator.process_request(
            "check the config, review the tests, and update documentation"
        )
        groups = plan.parsed_task.get_parallel_groups()
        # Should have at least one group
        self.assertGreater(len(groups), 0)

    def test_agent_reuse_buffing(self):
        """Test that agents can be reused (buffed) for similar tasks."""
        # First task creates an agent
        result1 = self.orchestrator.process_and_execute("implement feature A")

        # Second similar task should potentially reuse
        result2 = self.orchestrator.process_and_execute("implement feature B")

        # Both should complete
        self.assertIn(result1.status, [ExecutionStatus.COMPLETED, ExecutionStatus.PARTIAL])
        self.assertIn(result2.status, [ExecutionStatus.COMPLETED, ExecutionStatus.PARTIAL])


class TestAgentHealthCheck(unittest.TestCase):
    """Health checks to ensure agents are working correctly."""

    def test_registry_health(self):
        """Verify registry maintains consistency."""
        registry = AgentRegistry()

        # Register multiple agents
        agents = []
        for i in range(5):
            agent = registry.register_agent(
                name=f"agent_{i}",
                capability=AgentCapability(task_types=[TaskType.CODE]),
                prompt=f"Prompt {i}",
                subagent_type="general-purpose"
            )
            agents.append(agent)

        # Verify all are tracked
        self.assertEqual(len(registry.get_all_agents()), 5)

        # Assign tasks
        for i, agent in enumerate(agents[:3]):
            registry.assign_task(agent.agent_id, f"task_{i}")

        # Verify status updates
        active = registry.get_active_agents()
        self.assertEqual(len(active), 3)

        # Complete tasks
        for i, agent in enumerate(agents[:3]):
            registry.complete_task(agent.agent_id, f"task_{i}")

        # Verify all idle
        idle_count = len([a for a in registry.get_all_agents()
                         if a.status == AgentStatus.IDLE])
        self.assertEqual(idle_count, 5)

    def test_matcher_consistency(self):
        """Verify matcher produces consistent results."""
        registry = AgentRegistry()
        matcher = AgentMatcher(registry)

        # Register agent
        registry.register_agent(
            name="code_agent",
            capability=AgentCapability(
                task_types=[TaskType.CODE],
                specializations=['python']
            ),
            prompt="Test",
            subagent_type="general-purpose"
        )

        # Same subtask should produce same result
        subtask = SubTask(
            id="task_1",
            description="write python code",
            task_type=TaskType.CODE
        )

        result1 = matcher.find_match(subtask)
        result2 = matcher.find_match(subtask)

        self.assertEqual(result1.score, result2.score)
        self.assertEqual(result1.matched, result2.matched)

    def test_bridge_agent_tracking(self):
        """Verify bridge correctly tracks agent lifecycle."""
        bridge = ClaudeBridge()

        # Spawn agents
        agent_ids = []
        for i in range(3):
            result = bridge.spawn_agent(f"Task {i}", "general-purpose", f"Task {i}")
            agent_ids.append(result['agent_id'])

        # All should be active
        self.assertEqual(len(bridge.get_active_agents()), 3)

        # Complete one
        bridge.record_result(agent_ids[0], "Done")

        # Should have 2 active
        self.assertEqual(len(bridge.get_active_agents()), 2)

        # Result should be retrievable
        result = bridge.get_result(agent_ids[0])
        self.assertIsNotNone(result)
        self.assertEqual(result.status, 'completed')


def run_tests(verbosity=2):
    """Run all tests with specified verbosity."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    test_classes = [
        TestTaskParser,
        TestAgentRegistry,
        TestAgentMatcher,
        TestClaudeBridge,
        TestOrchestrator,
        TestIntegration,
        TestAgentHealthCheck
    ]

    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)

    # Run tests
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)

    return result


def run_quick_health_check():
    """Run a quick health check on critical components."""
    print("=" * 60)
    print("HERMES SUBAGENT HEALTH CHECK")
    print("=" * 60)

    checks = []

    # Check 1: Task Parser
    try:
        parser = TaskParser()
        result = parser.parse("test task")
        checks.append(("TaskParser", "OK", "Can parse tasks"))
    except Exception as e:
        checks.append(("TaskParser", "FAIL", str(e)))

    # Check 2: Agent Registry
    try:
        registry = AgentRegistry()
        agent = registry.register_agent(
            name="test",
            capability=AgentCapability(task_types=[TaskType.CODE]),
            prompt="test",
            subagent_type="general-purpose"
        )
        registry.assign_task(agent.agent_id, "task_1")
        registry.complete_task(agent.agent_id, "task_1")
        checks.append(("AgentRegistry", "OK", "Can manage agents"))
    except Exception as e:
        checks.append(("AgentRegistry", "FAIL", str(e)))

    # Check 3: Agent Matcher
    try:
        registry = AgentRegistry()
        matcher = AgentMatcher(registry)
        subtask = SubTask(id="t1", description="test", task_type=TaskType.CODE)
        matcher.find_match(subtask)
        checks.append(("AgentMatcher", "OK", "Can match tasks"))
    except Exception as e:
        checks.append(("AgentMatcher", "FAIL", str(e)))

    # Check 4: Claude Bridge
    try:
        bridge = ClaudeBridge()
        result = bridge.spawn_agent("test", "general-purpose", "test")
        bridge.record_result(result['agent_id'], "done")
        checks.append(("ClaudeBridge", "OK", "Can spawn agents"))
    except Exception as e:
        checks.append(("ClaudeBridge", "FAIL", str(e)))

    # Check 5: Orchestrator
    try:
        kb_path = Path(__file__).parent / "knowledge_base"
        orchestrator = Orchestrator(str(kb_path))
        plan = orchestrator.process_request("test task")
        checks.append(("Orchestrator", "OK", "Can process requests"))
    except Exception as e:
        checks.append(("Orchestrator", "FAIL", str(e)))

    # Print results
    print()
    all_passed = True
    for component, status, message in checks:
        symbol = "[+]" if status == "OK" else "[-]"
        print(f"{symbol} {component}: {status} - {message}")
        if status != "OK":
            all_passed = False

    print()
    print("=" * 60)
    if all_passed:
        print("All health checks PASSED")
    else:
        print("Some health checks FAILED")
    print("=" * 60)

    return all_passed


if __name__ == "__main__":
    import argparse

    arg_parser = argparse.ArgumentParser(description="HERMES Subagent Test Suite")
    arg_parser.add_argument(
        "--quick",
        action="store_true",
        help="Run quick health check only"
    )
    arg_parser.add_argument(
        "-v", "--verbose",
        action="count",
        default=2,
        help="Increase verbosity (can be used multiple times)"
    )

    args = arg_parser.parse_args()

    if args.quick:
        success = run_quick_health_check()
        sys.exit(0 if success else 1)
    else:
        result = run_tests(verbosity=args.verbose)
        sys.exit(0 if result.wasSuccessful() else 1)
