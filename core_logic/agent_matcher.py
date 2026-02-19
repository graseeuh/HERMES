"""
HERMES Agent Matcher
Matches incoming tasks to existing agents for reuse (buffing).
Prevents redundant agent creation by finding compatible existing agents.
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Tuple
from .task_parser import TaskType, SubTask
from .agent_registry import AgentRegistry, AgentRecord, AgentStatus


@dataclass
class MatchResult:
    """Result of attempting to match a task to an agent."""
    matched: bool
    agent: Optional[AgentRecord]
    score: float
    reason: str
    should_buff: bool = False  # True = add to existing, False = spawn new

    @classmethod
    def no_match(cls, reason: str) -> 'MatchResult':
        """Create a no-match result."""
        return cls(
            matched=False,
            agent=None,
            score=0.0,
            reason=reason,
            should_buff=False
        )

    @classmethod
    def match(cls, agent: AgentRecord, score: float, reason: str) -> 'MatchResult':
        """Create a successful match result."""
        return cls(
            matched=True,
            agent=agent,
            score=score,
            reason=reason,
            should_buff=True
        )


class AgentMatcher:
    """
    Matches incoming tasks to existing compatible agents.
    Enables agent "buffing" - adding tasks to existing agents instead of spawning new ones.
    """

    # Weights for scoring different match criteria
    WEIGHTS = {
        'task_type_match': 0.4,      # Primary: Does agent handle this task type?
        'specialization_match': 0.25, # Does agent have relevant specializations?
        'context_overlap': 0.2,       # Do contexts share keywords/files?
        'workload_factor': 0.15       # Is agent not overloaded?
    }

    # Minimum score required to consider a match valid
    MIN_MATCH_SCORE = 0.5

    def __init__(self, registry: AgentRegistry):
        """
        Initialize matcher with an agent registry.

        Args:
            registry: The AgentRegistry to search for compatible agents
        """
        self.registry = registry

    def find_match(self, subtask: SubTask) -> MatchResult:
        """
        Find the best matching agent for a subtask.

        Args:
            subtask: The subtask to match

        Returns:
            MatchResult indicating match status and details
        """
        available_agents = self.registry.get_available_agents()

        if not available_agents:
            return MatchResult.no_match("No available agents in registry")

        # Score each available agent
        scored_agents: List[Tuple[AgentRecord, float, str]] = []

        for agent in available_agents:
            score, reason = self._score_agent(agent, subtask)
            if score >= self.MIN_MATCH_SCORE:
                scored_agents.append((agent, score, reason))

        if not scored_agents:
            return MatchResult.no_match(
                f"No agents meet minimum compatibility score ({self.MIN_MATCH_SCORE})"
            )

        # Sort by score descending and get best match
        scored_agents.sort(key=lambda x: x[1], reverse=True)

        # Defensive check (should always pass due to check above)
        if len(scored_agents) == 0:
            return MatchResult.no_match("No compatible agents found")

        best_agent, best_score, best_reason = scored_agents[0]

        return MatchResult.match(best_agent, best_score, best_reason)

    def find_matches_for_batch(
        self,
        subtasks: List[SubTask]
    ) -> Dict[str, MatchResult]:
        """
        Find matches for a batch of subtasks.

        Args:
            subtasks: List of subtasks to match

        Returns:
            Dict mapping subtask IDs to their match results
        """
        results = {}

        for subtask in subtasks:
            result = self.find_match(subtask)
            results[subtask.id] = result

        return results

    def _score_agent(
        self,
        agent: AgentRecord,
        subtask: SubTask
    ) -> Tuple[float, str]:
        """
        Score how well an agent matches a subtask.

        Args:
            agent: The agent to evaluate
            subtask: The subtask to match against

        Returns:
            Tuple of (score, reason) where score is 0-1
        """
        scores = {}
        reasons = []

        # 1. Task type match (required)
        if subtask.task_type in agent.capability.task_types:
            scores['task_type_match'] = 1.0
            reasons.append(f"handles {subtask.task_type.value} tasks")
        else:
            # Task type mismatch is disqualifying
            return 0.0, f"Agent doesn't handle {subtask.task_type.value} tasks"

        # 2. Specialization match
        spec_score = self._score_specialization(agent, subtask)
        scores['specialization_match'] = spec_score
        if spec_score > 0:
            reasons.append(f"specialization match ({spec_score:.0%})")

        # 3. Context overlap
        context_score = self._score_context_overlap(agent, subtask)
        scores['context_overlap'] = context_score
        if context_score > 0:
            reasons.append(f"context overlap ({context_score:.0%})")

        # 4. Workload factor (prefer less loaded agents)
        workload_score = self._score_workload(agent)
        scores['workload_factor'] = workload_score
        if workload_score < 1.0:
            reasons.append(f"workload: {agent.workload}/{agent.capability.max_concurrent_tasks}")

        # Calculate weighted score
        total_score = sum(
            scores.get(key, 0) * weight
            for key, weight in self.WEIGHTS.items()
        )

        reason_str = "; ".join(reasons) if reasons else "basic compatibility"
        return total_score, reason_str

    def _score_specialization(
        self,
        agent: AgentRecord,
        subtask: SubTask
    ) -> float:
        """Score based on agent specializations matching task content."""
        if not agent.capability.specializations:
            return 0.5  # Neutral - no specializations defined

        task_text = subtask.description.lower()
        matches = sum(
            1 for spec in agent.capability.specializations
            if spec.lower() in task_text
        )

        if not matches:
            return 0.0

        # Score based on proportion of specializations matched
        return min(1.0, matches / len(agent.capability.specializations))

    def _score_context_overlap(
        self,
        agent: AgentRecord,
        subtask: SubTask
    ) -> float:
        """Score based on overlap between agent context and task context."""
        agent_context = agent.context
        task_context = subtask.context

        if not agent_context or not task_context:
            return 0.5  # Neutral - no context to compare

        overlap_score = 0.0
        comparisons = 0

        # Check file overlap
        agent_files = set(agent_context.get('files', []))
        task_files = set(task_context.get('files', []))
        if agent_files and task_files:
            union_size = len(agent_files | task_files)
            if union_size > 0:  # Defensive zero check
                file_overlap = len(agent_files & task_files) / union_size
                overlap_score += file_overlap
                comparisons += 1

        # Check technology overlap
        agent_tech = set(agent_context.get('technologies', []))
        task_tech = set(task_context.get('technologies', []))
        if agent_tech and task_tech:
            union_size = len(agent_tech | task_tech)
            if union_size > 0:  # Defensive zero check
                tech_overlap = len(agent_tech & task_tech) / union_size
                overlap_score += tech_overlap
                comparisons += 1

        # Check keyword overlap in context
        agent_keywords = set(agent.capability.context_keywords)
        task_text = subtask.description.lower()
        if agent_keywords:
            keyword_matches = sum(1 for kw in agent_keywords if kw.lower() in task_text)
            keyword_score = keyword_matches / len(agent_keywords) if agent_keywords else 0
            overlap_score += keyword_score
            comparisons += 1

        if comparisons == 0:
            return 0.5  # Neutral

        return overlap_score / comparisons

    def _score_workload(self, agent: AgentRecord) -> float:
        """Score based on agent's current workload (prefer less busy agents)."""
        max_tasks = agent.capability.max_concurrent_tasks
        current_load = agent.workload

        if current_load >= max_tasks:
            return 0.0  # Full

        # Linear decrease as workload increases
        return 1.0 - (current_load / max_tasks)

    def suggest_agent_type(self, subtask: SubTask) -> str:
        """
        Suggest the Claude Code subagent type for a task.

        Args:
            subtask: The subtask to suggest for

        Returns:
            Suggested subagent_type string
        """
        type_mapping = {
            TaskType.CODE: "general-purpose",
            TaskType.RESEARCH: "Explore",
            TaskType.VISION: "general-purpose",
            TaskType.AUDIO: "general-purpose",
            TaskType.KICAD: "general-purpose",
            TaskType.TOUCHDESIGNER: "general-purpose",
            TaskType.PLAN: "Plan",
            TaskType.CUSTOM: "general-purpose",
            TaskType.SECURITY: "security"
        }
        return type_mapping.get(subtask.task_type, "general-purpose")

    def get_buffing_recommendation(
        self,
        subtask: SubTask
    ) -> Dict[str, Any]:
        """
        Get a recommendation on whether to buff or spawn for a task.

        Args:
            subtask: The subtask to evaluate

        Returns:
            Dict with recommendation details
        """
        match_result = self.find_match(subtask)

        return {
            'task_id': subtask.id,
            'task_type': subtask.task_type.value,
            'recommendation': 'buff' if match_result.should_buff else 'spawn',
            'matched_agent_id': match_result.agent.agent_id if match_result.agent else None,
            'match_score': match_result.score,
            'reason': match_result.reason,
            'suggested_subagent_type': self.suggest_agent_type(subtask)
        }
