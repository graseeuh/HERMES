"""
HERMES - Hierarchical Executable Reasoning and Management Execution System

A meta-agent orchestration system that accepts natural language task descriptions,
generates appropriate agent prompts, and spawns/coordinates multiple Claude Code
subagents in parallel.

Usage:
    from main import HERMES

    hermes = HERMES()
    result = hermes.run("Analyze the webcam feed and detect hand gestures")
    print(result.summary)
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any

from core_logic.orchestrator import Orchestrator, ExecutionPlan, ExecutionResult
from core_logic.task_parser import TaskParser, ParsedTask
from core_logic.agent_registry import AgentRegistry
from core_logic.agent_matcher import AgentMatcher
from core_logic.prompt_generator import PromptGenerator
from integration.claude_bridge import ClaudeBridge


class HERMES:
    """
    HERMES - Hierarchical Executable Reasoning and Management Execution System

    Main entry point for the agent orchestration system.
    """

    def __init__(
        self,
        knowledge_base_path: Optional[str] = None,
        auto_execute: bool = True
    ):
        """
        Initialize HERMES.

        Args:
            knowledge_base_path: Path to knowledge_base directory (defaults to ./knowledge_base)
            auto_execute: If True, automatically execute plans after creation
        """
        # Set up paths
        self.base_path = Path(__file__).parent
        self.kb_path = knowledge_base_path or str(self.base_path / "knowledge_base")

        # Initialize components
        self.claude_bridge = ClaudeBridge()
        self.orchestrator = Orchestrator(
            knowledge_base_path=self.kb_path,
            claude_bridge=self.claude_bridge
        )

        self.auto_execute = auto_execute

        # Set up callbacks for monitoring
        self.orchestrator.set_callbacks(
            on_agent_spawn=self._on_agent_spawn,
            on_agent_complete=self._on_agent_complete,
            on_task_complete=self._on_task_complete
        )

        self._verbose = False

    def set_verbose(self, verbose: bool) -> None:
        """Enable or disable verbose output."""
        self._verbose = verbose

    def run(self, task_description: str) -> ExecutionResult:
        """
        Process and execute a natural language task.

        Args:
            task_description: Natural language description of what to do

        Returns:
            ExecutionResult with results and status
        """
        if self._verbose:
            print(f"[HERMES] Received task: {task_description[:100]}...")

        return self.orchestrator.process_and_execute(task_description)

    def plan(self, task_description: str) -> ExecutionPlan:
        """
        Create an execution plan without executing.

        Args:
            task_description: Natural language description of what to do

        Returns:
            ExecutionPlan ready for execution
        """
        if self._verbose:
            print(f"[HERMES] Planning task: {task_description[:100]}...")

        return self.orchestrator.process_request(task_description)

    def execute(self, plan: ExecutionPlan) -> ExecutionResult:
        """
        Execute a previously created plan.

        Args:
            plan: ExecutionPlan to execute

        Returns:
            ExecutionResult with results and status
        """
        if self._verbose:
            print(f"[HERMES] Executing plan with {len(plan.parsed_task.subtasks)} subtasks...")

        return self.orchestrator.execute_plan(plan)

    def analyze(self, task_description: str) -> Dict[str, Any]:
        """
        Analyze a task without executing - useful for understanding what HERMES will do.

        Args:
            task_description: Natural language description

        Returns:
            Dict with analysis details
        """
        plan = self.plan(task_description)

        return {
            'original_input': task_description,
            'subtasks': [
                {
                    'id': st.id,
                    'description': st.description,
                    'type': st.task_type.value,
                    'dependencies': st.dependencies
                }
                for st in plan.parsed_task.subtasks
            ],
            'execution_groups': [
                [st.id for st in group]
                for group in plan.execution_groups
            ],
            'buff_decisions': plan.buff_decisions,
            'prompts_generated': list(plan.prompts.keys())
        }

    def status(self) -> Dict[str, Any]:
        """Get current HERMES status."""
        return self.orchestrator.get_status()

    def _on_agent_spawn(self, agent, subtask) -> None:
        """Callback when an agent is spawned."""
        if self._verbose:
            buff_status = "BUFFED" if agent.status.value == "buffered" else "NEW"
            print(f"[HERMES] Agent {buff_status}: {agent.name} for {subtask.task_type.value} task")

    def _on_agent_complete(self, agent, subtask, result) -> None:
        """Callback when an agent completes."""
        if self._verbose:
            print(f"[HERMES] Agent completed: {agent.name}")

    def _on_task_complete(self, result: ExecutionResult) -> None:
        """Callback when entire task completes."""
        if self._verbose:
            print(f"[HERMES] Task complete: {result.status.value}")
            print(f"[HERMES] Agents used: {len(result.agents_used)}, Buffed: {len(result.agents_buffed)}")


def main():
    """Main entry point for command-line usage."""
    import sys

    print("=" * 60)
    print("HERMES - Agent Orchestration System")
    print("=" * 60)

    hermes = HERMES()
    hermes.set_verbose(True)

    if len(sys.argv) > 1:
        # Task provided as argument
        task = ' '.join(sys.argv[1:])
    else:
        # Interactive mode
        print("\nEnter a task description (or 'quit' to exit):")
        print("Example: 'Find all Python files and analyze their imports'\n")

        while True:
            try:
                task = input("HERMES> ").strip()
                if task.lower() in ['quit', 'exit', 'q']:
                    print("Goodbye!")
                    break
                if not task:
                    continue

                # Analyze first
                print("\n[Analysis]")
                analysis = hermes.analyze(task)
                print(f"Subtasks identified: {len(analysis['subtasks'])}")
                for st in analysis['subtasks']:
                    print(f"  - [{st['type']}] {st['description'][:60]}...")

                print(f"\nExecution groups: {len(analysis['execution_groups'])}")
                for i, group in enumerate(analysis['execution_groups']):
                    print(f"  Group {i+1}: {group} (parallel)")

                # Execute
                print("\n[Execution]")
                result = hermes.run(task)

                print("\n[Result]")
                print(result.summary)
                print(f"\nExecution time: {result.execution_time:.2f}s")
                print("-" * 40)

            except KeyboardInterrupt:
                print("\nInterrupted. Type 'quit' to exit.")
            except Exception as e:
                print(f"Error: {e}")

        return

    # Single task mode
    result = hermes.run(task)
    print("\n" + result.summary)


if __name__ == "__main__":
    main()
