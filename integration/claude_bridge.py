"""
HERMES Claude Bridge
Interface between HERMES and Claude Code's Task tool for spawning and managing agents.

This module provides the bridge to Claude Code's subagent system.
When used within Claude Code, it generates the appropriate Task tool calls.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from enum import Enum


class SubagentType(Enum):
    """Available Claude Code subagent types."""
    GENERAL_PURPOSE = "general-purpose"
    EXPLORE = "Explore"
    PLAN = "Plan"


@dataclass
class AgentSpawnRequest:
    """Request to spawn a new agent."""
    prompt: str
    subagent_type: str
    description: str
    run_in_background: bool = False
    model: Optional[str] = None  # sonnet, opus, haiku


@dataclass
class AgentSpawnResult:
    """Result from spawning an agent."""
    agent_id: str
    status: str
    output: Optional[str] = None
    error: Optional[str] = None


class ClaudeBridge:
    """
    Bridge to Claude Code's Task tool system.

    This class provides methods that map to Claude Code's agent spawning capabilities.
    In actual use within Claude Code, the orchestrator would use this to construct
    proper Task tool invocations.

    Usage: The spawn_agent method returns a dict that can be used to construct
    a Task tool call with the appropriate parameters (prompt, subagent_type, description).
    """

    # Mapping from HERMES task types to Claude Code subagent types
    SUBAGENT_MAPPING = {
        'code': SubagentType.GENERAL_PURPOSE.value,
        'research': SubagentType.EXPLORE.value,
        'vision': SubagentType.GENERAL_PURPOSE.value,
        'audio': SubagentType.GENERAL_PURPOSE.value,
        'kicad': SubagentType.GENERAL_PURPOSE.value,
        'touchdesigner': SubagentType.GENERAL_PURPOSE.value,
        'plan': SubagentType.PLAN.value,
        'custom': SubagentType.GENERAL_PURPOSE.value
    }

    def __init__(self):
        """Initialize the Claude bridge."""
        self._active_agents: Dict[str, AgentSpawnRequest] = {}
        self._agent_results: Dict[str, AgentSpawnResult] = {}
        self._agent_counter = 0

    def spawn_agent(
        self,
        prompt: str,
        subagent_type: str,
        description: str,
        run_in_background: bool = False,
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Spawn a new Claude Code agent.

        This method constructs the parameters needed for a Task tool call.

        Args:
            prompt: The task/prompt for the agent
            subagent_type: Claude Code subagent type (general-purpose, Explore, Plan)
            description: Short description of the task (3-5 words)
            run_in_background: Whether to run asynchronously
            model: Optional model override (sonnet, opus, haiku)

        Returns:
            Dict containing the Task tool parameters and a local agent_id
        """
        self._agent_counter += 1
        agent_id = f"hermes_agent_{self._agent_counter}"

        request = AgentSpawnRequest(
            prompt=prompt,
            subagent_type=subagent_type,
            description=description[:50],  # Ensure short description
            run_in_background=run_in_background,
            model=model
        )

        self._active_agents[agent_id] = request

        # Return the parameters for a Task tool call
        task_params = {
            'prompt': prompt,
            'subagent_type': subagent_type,
            'description': description[:50]
        }

        if run_in_background:
            task_params['run_in_background'] = True

        if model:
            task_params['model'] = model

        return {
            'agent_id': agent_id,
            'task_tool_params': task_params,
            'status': 'ready_to_spawn'
        }

    def spawn_parallel_agents(
        self,
        requests: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Prepare multiple agents to be spawned in parallel.

        In Claude Code, parallel spawning is done by including multiple
        Task tool calls in a single message.

        Args:
            requests: List of dicts with 'prompt', 'subagent_type', 'description'

        Returns:
            List of spawn results with agent_ids and task parameters
        """
        results = []
        for req in requests:
            result = self.spawn_agent(
                prompt=req['prompt'],
                subagent_type=req.get('subagent_type', 'general-purpose'),
                description=req.get('description', 'HERMES task'),
                run_in_background=req.get('run_in_background', False),
                model=req.get('model')
            )
            results.append(result)

        return results

    def add_task_to_agent(
        self,
        agent_id: str,
        prompt: str,
        task_description: str
    ) -> Dict[str, Any]:
        """
        Add a task to an existing agent (buffing).

        In Claude Code, this would use the 'resume' parameter of the Task tool
        to continue an existing agent with additional context.

        Args:
            agent_id: The HERMES agent ID (maps to Claude Code agent ID)
            prompt: Additional prompt/task to add
            task_description: Description of the new task

        Returns:
            Dict with buffing parameters
        """
        if agent_id not in self._active_agents:
            return {
                'error': f'Agent {agent_id} not found',
                'status': 'failed'
            }

        original_request = self._active_agents[agent_id]

        # For Claude Code, resuming uses the original agent's ID
        # The new prompt is appended to continue the conversation
        return {
            'agent_id': agent_id,
            'task_tool_params': {
                'prompt': prompt,
                'subagent_type': original_request.subagent_type,
                'description': f"Continue: {task_description[:40]}",
                # In actual use, would include 'resume': claude_agent_id
            },
            'status': 'ready_to_buff',
            'is_continuation': True
        }

    def record_result(
        self,
        agent_id: str,
        output: str,
        error: Optional[str] = None
    ) -> None:
        """
        Record the result from an agent execution.

        Args:
            agent_id: The agent that completed
            output: The agent's output
            error: Any error that occurred
        """
        status = 'failed' if error else 'completed'

        self._agent_results[agent_id] = AgentSpawnResult(
            agent_id=agent_id,
            status=status,
            output=output,
            error=error
        )

    def get_result(self, agent_id: str) -> Optional[AgentSpawnResult]:
        """Get the result for an agent."""
        return self._agent_results.get(agent_id)

    def get_active_agents(self) -> List[str]:
        """Get list of active agent IDs."""
        completed = set(self._agent_results.keys())
        return [aid for aid in self._active_agents if aid not in completed]

    def get_subagent_type(self, task_type: str) -> str:
        """
        Get the appropriate Claude Code subagent type for a HERMES task type.

        Args:
            task_type: HERMES task type (code, research, vision, etc.)

        Returns:
            Claude Code subagent type string
        """
        return self.SUBAGENT_MAPPING.get(task_type, SubagentType.GENERAL_PURPOSE.value)

    def format_task_tool_call(self, params: Dict[str, Any]) -> str:
        """
        Format parameters as a Task tool call representation.

        This is useful for debugging and logging.

        Args:
            params: Task tool parameters

        Returns:
            String representation of the tool call
        """
        lines = ["Task tool call:"]
        lines.append(f"  prompt: {params.get('prompt', '')[:100]}...")
        lines.append(f"  subagent_type: {params.get('subagent_type', 'general-purpose')}")
        lines.append(f"  description: {params.get('description', '')}")

        if params.get('run_in_background'):
            lines.append("  run_in_background: true")
        if params.get('model'):
            lines.append(f"  model: {params.get('model')}")
        if params.get('resume'):
            lines.append(f"  resume: {params.get('resume')}")

        return '\n'.join(lines)

    def clear(self) -> None:
        """Clear all tracked agents and results."""
        self._active_agents.clear()
        self._agent_results.clear()
        self._agent_counter = 0
