"""
HERMES Orchestrator
The main coordination engine that receives tasks, manages agents, and aggregates results.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
from enum import Enum

from .task_parser import TaskParser, ParsedTask, SubTask, TaskType
from .agent_registry import AgentRegistry, AgentRecord, AgentCapability, AgentStatus
from .agent_matcher import AgentMatcher, MatchResult
from .prompt_generator import PromptGenerator, GeneratedPrompt

# Import Claude Code executor for real task execution
try:
    from integration.claude_code_executor import ClaudeCodeExecutor
    EXECUTOR_AVAILABLE = True
except ImportError:
    EXECUTOR_AVAILABLE = False


class ExecutionStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"  # Some tasks completed, some failed


@dataclass
class ExecutionPlan:
    """Plan for executing a parsed task."""
    parsed_task: ParsedTask
    execution_groups: List[List[SubTask]]
    agent_assignments: Dict[str, str]  # subtask_id -> agent_id
    buff_decisions: Dict[str, bool]  # subtask_id -> True if buffed
    prompts: Dict[str, GeneratedPrompt]  # subtask_id -> prompt


@dataclass
class ExecutionResult:
    """Result of executing a task through the orchestrator."""
    status: ExecutionStatus
    original_input: str
    results: Dict[str, Any]  # subtask_id -> result
    errors: Dict[str, str]  # subtask_id -> error message
    execution_time: float
    agents_used: List[str]
    agents_buffed: List[str]
    summary: str


class Orchestrator:
    """
    The brain of HERMES - coordinates task parsing, agent management, and execution.
    """

    def __init__(
        self,
        knowledge_base_path: str,
        claude_bridge: Optional[Any] = None  # Will be ClaudeBridge instance
    ):
        """
        Initialize the orchestrator.

        Args:
            knowledge_base_path: Path to the knowledge_base directory
            claude_bridge: Bridge to Claude Code for spawning agents (optional for testing)
        """
        self.task_parser = TaskParser()
        self.registry = AgentRegistry()
        self.matcher = AgentMatcher(self.registry)
        self.prompt_generator = PromptGenerator(knowledge_base_path)
        self.claude_bridge = claude_bridge

        # Claude Code executor for real task execution
        self.executor = None
        if EXECUTOR_AVAILABLE:
            self.executor = ClaudeCodeExecutor(working_directory=knowledge_base_path)
            if self.executor.is_available():
                print("Claude Code executor: ENABLED (real execution)")
            else:
                print("Claude Code executor: NOT AVAILABLE (claude CLI not found)")
                self.executor = None
        else:
            print("Claude Code executor: NOT INSTALLED")

        # Execution callbacks (for integration)
        self._on_agent_spawn: Optional[Callable] = None
        self._on_agent_complete: Optional[Callable] = None
        self._on_task_complete: Optional[Callable] = None

    def set_claude_bridge(self, bridge: Any) -> None:
        """Set the Claude bridge after initialization."""
        self.claude_bridge = bridge

    def set_callbacks(
        self,
        on_agent_spawn: Optional[Callable] = None,
        on_agent_complete: Optional[Callable] = None,
        on_task_complete: Optional[Callable] = None
    ) -> None:
        """Set execution callbacks for monitoring."""
        self._on_agent_spawn = on_agent_spawn
        self._on_agent_complete = on_agent_complete
        self._on_task_complete = on_task_complete

    def process_request(self, user_input: str) -> ExecutionPlan:
        """
        Process a user request into an execution plan.

        Args:
            user_input: Natural language task description

        Returns:
            ExecutionPlan ready for execution
        """
        # Parse the input
        parsed = self.task_parser.parse(user_input)

        # Get execution groups (respecting dependencies)
        execution_groups = parsed.get_parallel_groups()

        # Plan agent assignments
        agent_assignments = {}
        buff_decisions = {}
        prompts = {}

        for subtask in parsed.subtasks:
            # Check for existing agent match (buffing)
            match_result = self.matcher.find_match(subtask)

            if match_result.should_buff and match_result.agent:
                # Buff existing agent
                agent_assignments[subtask.id] = match_result.agent.agent_id
                buff_decisions[subtask.id] = True
            else:
                # Will spawn new agent - assignment happens at execution
                agent_assignments[subtask.id] = None
                buff_decisions[subtask.id] = False

            # Generate prompt for the subtask
            prompt = self.prompt_generator.generate_prompt(
                subtask,
                additional_context=parsed.global_context
            )
            prompts[subtask.id] = prompt

            # Save prompt for reuse
            self.prompt_generator.save_prompt(prompt)

        return ExecutionPlan(
            parsed_task=parsed,
            execution_groups=execution_groups,
            agent_assignments=agent_assignments,
            buff_decisions=buff_decisions,
            prompts=prompts
        )

    def execute_plan(self, plan: ExecutionPlan) -> ExecutionResult:
        """
        Execute an execution plan.

        Args:
            plan: The ExecutionPlan to execute

        Returns:
            ExecutionResult with all results and status
        """
        start_time = datetime.now()
        results = {}
        errors = {}
        agents_used = []
        agents_buffed = []

        # Execute each group (groups can run in parallel, tasks within group are independent)
        for group_idx, group in enumerate(plan.execution_groups):
            group_results = self._execute_group(
                group,
                plan,
                results  # Pass previous results for context
            )

            for subtask_id, result in group_results.items():
                if 'error' in result:
                    errors[subtask_id] = result['error']
                else:
                    results[subtask_id] = result.get('result')

                # Track agents
                agent_id = plan.agent_assignments.get(subtask_id)
                if agent_id and agent_id not in agents_used:
                    agents_used.append(agent_id)
                    if plan.buff_decisions.get(subtask_id):
                        agents_buffed.append(agent_id)

        # Determine overall status
        if not errors:
            status = ExecutionStatus.COMPLETED
        elif not results:
            status = ExecutionStatus.FAILED
        else:
            status = ExecutionStatus.PARTIAL

        execution_time = (datetime.now() - start_time).total_seconds()

        # Generate summary
        summary = self._generate_summary(plan, results, errors)

        result = ExecutionResult(
            status=status,
            original_input=plan.parsed_task.original_input,
            results=results,
            errors=errors,
            execution_time=execution_time,
            agents_used=agents_used,
            agents_buffed=agents_buffed,
            summary=summary
        )

        if self._on_task_complete:
            self._on_task_complete(result)

        return result

    def _execute_group(
        self,
        group: List[SubTask],
        plan: ExecutionPlan,
        previous_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a group of independent subtasks (can run in parallel)."""
        group_results = {}

        # In a real implementation, these would run in parallel
        # For now, execute sequentially but structure supports parallel execution
        for subtask in group:
            result = self._execute_subtask(subtask, plan, previous_results)
            group_results[subtask.id] = result

        return group_results

    def _execute_subtask(
        self,
        subtask: SubTask,
        plan: ExecutionPlan,
        previous_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a single subtask."""
        prompt = plan.prompts.get(subtask.id)
        is_buffed = plan.buff_decisions.get(subtask.id, False)
        assigned_agent_id = plan.agent_assignments.get(subtask.id)

        # Add context from previous tasks if there are dependencies
        enhanced_context = dict(subtask.context)
        for dep_id in subtask.dependencies:
            if dep_id in previous_results:
                enhanced_context[f'result_from_{dep_id}'] = previous_results[dep_id]

        try:
            if is_buffed and assigned_agent_id:
                # Add task to existing agent (buff)
                result = self._buff_agent(
                    assigned_agent_id,
                    subtask,
                    prompt,
                    enhanced_context
                )
            else:
                # Spawn new agent
                result = self._spawn_agent(
                    subtask,
                    prompt,
                    enhanced_context,
                    plan
                )

            return {'result': result}

        except Exception as e:
            return {'error': str(e)}

    def _spawn_agent(
        self,
        subtask: SubTask,
        prompt: GeneratedPrompt,
        context: Dict[str, Any],
        plan: ExecutionPlan
    ) -> Any:
        """Spawn a new agent for a subtask."""
        # Determine capability based on task type
        capability = AgentCapability(
            task_types=[subtask.task_type],
            specializations=self._get_specializations_for_type(subtask.task_type),
            context_keywords=list(context.get('technologies', []))
        )

        # Determine subagent type
        subagent_type = self.matcher.suggest_agent_type(subtask)

        # Register the agent
        agent = self.registry.register_agent(
            name=f"{subtask.task_type.value}_agent_{subtask.id}",
            capability=capability,
            prompt=prompt.rendered_prompt,
            subagent_type=subagent_type,
            context=context
        )

        # Update plan with assignment
        plan.agent_assignments[subtask.id] = agent.agent_id

        # Assign the task
        self.registry.assign_task(agent.agent_id, subtask.id)

        if self._on_agent_spawn:
            self._on_agent_spawn(agent, subtask)

        # Execute via Claude Code executor (real execution) if available
        if self.executor:
            exec_result = self.executor.execute(
                task=prompt.rendered_prompt,
                timeout=120,
                max_turns=5
            )
            result = {
                'agent_id': agent.agent_id,
                'task_id': subtask.id,
                'status': 'completed' if exec_result.success else 'failed',
                'output': exec_result.output,
                'error': exec_result.error
            }
        elif self.claude_bridge:
            # Fallback to bridge (for testing/simulation)
            result = self.claude_bridge.spawn_agent(
                prompt=prompt.rendered_prompt,
                subagent_type=subagent_type,
                description=subtask.description[:50]
            )
        else:
            # Mock result for testing
            result = {
                'agent_id': agent.agent_id,
                'task_id': subtask.id,
                'status': 'simulated',
                'message': f"Would execute: {subtask.description[:100]}"
            }

        # Mark task complete
        self.registry.complete_task(agent.agent_id, subtask.id, result)

        if self._on_agent_complete:
            self._on_agent_complete(agent, subtask, result)

        return result

    def _buff_agent(
        self,
        agent_id: str,
        subtask: SubTask,
        prompt: GeneratedPrompt,
        context: Dict[str, Any]
    ) -> Any:
        """Add a task to an existing agent (buff)."""
        agent = self.registry.get_agent(agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")

        # Update agent context with new task info
        self.registry.update_agent_context(agent_id, context)

        # Queue the task
        self.registry.queue_task(
            agent_id,
            subtask.id,
            subtask.description,
            subtask.task_type,
            context
        )

        if self._on_agent_spawn:
            self._on_agent_spawn(agent, subtask)

        # Execute via Claude Code executor (real execution) if available
        if self.executor:
            # For buffing, include context about the continuation
            continuation_prompt = f"Continuing previous work.\n\n{prompt.rendered_prompt}"
            exec_result = self.executor.execute(
                task=continuation_prompt,
                timeout=120,
                max_turns=5
            )
            result = {
                'agent_id': agent_id,
                'task_id': subtask.id,
                'status': 'completed' if exec_result.success else 'failed',
                'output': exec_result.output,
                'error': exec_result.error
            }
        elif self.claude_bridge:
            # Fallback to bridge (for testing/simulation)
            result = self.claude_bridge.add_task_to_agent(
                agent_id=agent_id,
                prompt=prompt.rendered_prompt,
                task_description=subtask.description
            )
        else:
            # Mock result for testing
            result = {
                'agent_id': agent_id,
                'task_id': subtask.id,
                'status': 'buffed',
                'message': f"Added to existing agent: {subtask.description[:100]}"
            }

        # Mark task complete
        self.registry.complete_task(agent_id, subtask.id, result)

        if self._on_agent_complete:
            self._on_agent_complete(agent, subtask, result)

        return result

    def _get_specializations_for_type(self, task_type: TaskType) -> List[str]:
        """Get default specializations for a task type."""
        specializations = {
            TaskType.CODE: ['python', 'implementation', 'debugging'],
            TaskType.RESEARCH: ['exploration', 'analysis', 'documentation'],
            TaskType.VISION: ['mediapipe', 'opencv', 'image processing'],
            TaskType.AUDIO: ['sounddevice', 'audio processing'],
            TaskType.PLAN: ['architecture', 'design'],
            TaskType.CUSTOM: []
        }
        return specializations.get(task_type, [])

    def _generate_summary(
        self,
        plan: ExecutionPlan,
        results: Dict[str, Any],
        errors: Dict[str, str]
    ) -> str:
        """Generate a human-readable summary of execution."""
        lines = []
        lines.append(f"Execution Summary for: {plan.parsed_task.original_input[:50]}...")
        lines.append(f"Total subtasks: {len(plan.parsed_task.subtasks)}")
        lines.append(f"Completed: {len(results)}")
        lines.append(f"Failed: {len(errors)}")

        buffed_count = sum(1 for v in plan.buff_decisions.values() if v)
        lines.append(f"Agents buffed (reused): {buffed_count}")
        lines.append(f"New agents spawned: {len(plan.parsed_task.subtasks) - buffed_count}")

        if errors:
            lines.append("\nErrors:")
            for task_id, error in errors.items():
                lines.append(f"  - {task_id}: {error}")

        return '\n'.join(lines)

    def get_status(self) -> Dict[str, Any]:
        """Get current orchestrator status."""
        return {
            'registry_stats': self.registry.get_registry_stats(),
            'templates_loaded': self.prompt_generator.list_templates(),
            'has_claude_bridge': self.claude_bridge is not None
        }

    def process_and_execute(self, user_input: str) -> ExecutionResult:
        """
        Convenience method to process and execute in one call.

        Args:
            user_input: Natural language task description

        Returns:
            ExecutionResult with all results and status
        """
        plan = self.process_request(user_input)
        return self.execute_plan(plan)
