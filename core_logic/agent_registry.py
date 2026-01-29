"""
HERMES Agent Registry
Tracks active agents, their capabilities, states, and results.
Enables agent reuse through capability profiles.
"""

import uuid
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
from .task_parser import TaskType


class AgentStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BUFFERED = "buffered"  # Has queued tasks waiting


@dataclass
class AgentCapability:
    """Defines what an agent can do."""
    task_types: List[TaskType]
    specializations: List[str] = field(default_factory=list)
    max_concurrent_tasks: int = 3
    context_keywords: List[str] = field(default_factory=list)


@dataclass
class QueuedTask:
    """A task waiting to be processed by a buffered agent."""
    task_id: str
    description: str
    task_type: TaskType
    context: Dict[str, Any]
    queued_at: datetime = field(default_factory=datetime.now)


@dataclass
class AgentRecord:
    """Record of a registered agent."""
    agent_id: str
    name: str
    capability: AgentCapability
    status: AgentStatus
    prompt: str
    subagent_type: str  # Claude Code subagent type
    created_at: datetime = field(default_factory=datetime.now)
    current_tasks: List[str] = field(default_factory=list)
    task_queue: List[QueuedTask] = field(default_factory=list)
    results: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    @property
    def is_available(self) -> bool:
        """Check if agent can accept more tasks."""
        total_tasks = len(self.current_tasks) + len(self.task_queue)
        return (self.status in [AgentStatus.IDLE, AgentStatus.RUNNING, AgentStatus.BUFFERED]
                and total_tasks < self.capability.max_concurrent_tasks)

    @property
    def workload(self) -> int:
        """Current number of tasks (active + queued)."""
        return len(self.current_tasks) + len(self.task_queue)


class AgentRegistry:
    """
    Central registry for managing HERMES agents.
    Tracks agent lifecycle, capabilities, and enables task buffing.
    """

    def __init__(self):
        self._agents: Dict[str, AgentRecord] = {}
        self._task_to_agent: Dict[str, str] = {}  # task_id -> agent_id mapping

    def register_agent(
        self,
        name: str,
        capability: AgentCapability,
        prompt: str,
        subagent_type: str,
        context: Optional[Dict[str, Any]] = None
    ) -> AgentRecord:
        """
        Register a new agent in the registry.

        Args:
            name: Human-readable agent name
            capability: What the agent can do
            prompt: The agent's system prompt
            subagent_type: Claude Code subagent type (e.g., 'general-purpose', 'Explore')
            context: Optional initial context

        Returns:
            The created AgentRecord
        """
        agent_id = f"agent_{uuid.uuid4().hex[:8]}"

        record = AgentRecord(
            agent_id=agent_id,
            name=name,
            capability=capability,
            status=AgentStatus.IDLE,
            prompt=prompt,
            subagent_type=subagent_type,
            context=context or {}
        )

        self._agents[agent_id] = record
        return record

    def get_agent(self, agent_id: str) -> Optional[AgentRecord]:
        """Get an agent by ID."""
        return self._agents.get(agent_id)

    def get_all_agents(self) -> List[AgentRecord]:
        """Get all registered agents."""
        return list(self._agents.values())

    def get_active_agents(self) -> List[AgentRecord]:
        """Get all agents that are currently running or have buffered tasks."""
        return [a for a in self._agents.values()
                if a.status in [AgentStatus.RUNNING, AgentStatus.BUFFERED]]

    def get_available_agents(self) -> List[AgentRecord]:
        """Get all agents that can accept new tasks."""
        return [a for a in self._agents.values() if a.is_available]

    def get_agents_by_type(self, task_type: TaskType) -> List[AgentRecord]:
        """Get all agents capable of handling a specific task type."""
        return [a for a in self._agents.values()
                if task_type in a.capability.task_types]

    def assign_task(self, agent_id: str, task_id: str) -> bool:
        """
        Assign a task to an agent.

        Args:
            agent_id: The agent to assign to
            task_id: The task being assigned

        Returns:
            True if assignment successful
        """
        agent = self._agents.get(agent_id)
        if not agent or not agent.is_available:
            return False

        agent.current_tasks.append(task_id)
        agent.status = AgentStatus.RUNNING
        self._task_to_agent[task_id] = agent_id
        return True

    def queue_task(
        self,
        agent_id: str,
        task_id: str,
        description: str,
        task_type: TaskType,
        context: Dict[str, Any]
    ) -> bool:
        """
        Queue a task for buffered execution on an existing agent.

        Args:
            agent_id: The agent to queue on
            task_id: The task ID
            description: Task description
            task_type: Type of task
            context: Task context

        Returns:
            True if queuing successful
        """
        agent = self._agents.get(agent_id)
        if not agent or not agent.is_available:
            return False

        queued = QueuedTask(
            task_id=task_id,
            description=description,
            task_type=task_type,
            context=context
        )

        agent.task_queue.append(queued)
        agent.status = AgentStatus.BUFFERED
        self._task_to_agent[task_id] = agent_id
        return True

    def get_next_queued_task(self, agent_id: str) -> Optional[QueuedTask]:
        """Get and remove the next queued task for an agent."""
        agent = self._agents.get(agent_id)
        if not agent or not agent.task_queue:
            return None

        return agent.task_queue.pop(0)

    def complete_task(
        self,
        agent_id: str,
        task_id: str,
        result: Any = None,
        error: Optional[str] = None
    ) -> bool:
        """
        Mark a task as completed.

        Args:
            agent_id: The agent that completed the task
            task_id: The completed task
            result: Task result (if successful)
            error: Error message (if failed)

        Returns:
            True if completion recorded successfully
        """
        agent = self._agents.get(agent_id)
        if not agent:
            return False

        if task_id in agent.current_tasks:
            agent.current_tasks.remove(task_id)

        if error:
            agent.results[task_id] = {'error': error}
        else:
            agent.results[task_id] = {'result': result}

        # Update agent status
        if agent.task_queue:
            agent.status = AgentStatus.BUFFERED
        elif agent.current_tasks:
            agent.status = AgentStatus.RUNNING
        else:
            agent.status = AgentStatus.IDLE

        return True

    def update_agent_context(self, agent_id: str, context: Dict[str, Any]) -> bool:
        """Update an agent's context with new information."""
        agent = self._agents.get(agent_id)
        if not agent:
            return False

        agent.context.update(context)
        return True

    def get_agent_for_task(self, task_id: str) -> Optional[AgentRecord]:
        """Get the agent assigned to a specific task."""
        agent_id = self._task_to_agent.get(task_id)
        if agent_id:
            return self._agents.get(agent_id)
        return None

    def get_task_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get the result of a completed task."""
        agent_id = self._task_to_agent.get(task_id)
        if not agent_id:
            return None

        agent = self._agents.get(agent_id)
        if not agent:
            return None

        return agent.results.get(task_id)

    def deregister_agent(self, agent_id: str) -> bool:
        """Remove an agent from the registry."""
        if agent_id not in self._agents:
            return False

        agent = self._agents[agent_id]

        # Clean up task mappings
        for task_id in agent.current_tasks:
            self._task_to_agent.pop(task_id, None)
        for queued in agent.task_queue:
            self._task_to_agent.pop(queued.task_id, None)

        del self._agents[agent_id]
        return True

    def get_registry_stats(self) -> Dict[str, Any]:
        """Get statistics about the registry."""
        agents = list(self._agents.values())
        return {
            'total_agents': len(agents),
            'active_agents': len([a for a in agents if a.status == AgentStatus.RUNNING]),
            'buffered_agents': len([a for a in agents if a.status == AgentStatus.BUFFERED]),
            'idle_agents': len([a for a in agents if a.status == AgentStatus.IDLE]),
            'completed_agents': len([a for a in agents if a.status == AgentStatus.COMPLETED]),
            'failed_agents': len([a for a in agents if a.status == AgentStatus.FAILED]),
            'total_tasks_tracked': len(self._task_to_agent),
            'agents_by_type': {
                task_type.value: len(self.get_agents_by_type(task_type))
                for task_type in TaskType
            }
        }

    def clear(self) -> None:
        """Clear all agents from the registry."""
        self._agents.clear()
        self._task_to_agent.clear()
