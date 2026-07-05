"""
HERMES Task Parser
Analyzes natural language task descriptions and extracts structured task breakdowns.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum


class TaskType(Enum):
    CODE = "code"
    RESEARCH = "research"
    VISION = "vision"
    AUDIO = "audio"
    KICAD = "kicad"
    TOUCHDESIGNER = "touchdesigner"
    PLAN = "plan"
    CUSTOM = "custom"
    SECURITY = "security"


@dataclass
class SubTask:
    """Represents a single subtask extracted from user input."""
    id: str
    description: str
    task_type: TaskType
    dependencies: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    priority: int = 1

    def can_run_parallel(self, other: 'SubTask') -> bool:
        """Check if this subtask can run in parallel with another."""
        return (self.id not in other.dependencies and
                other.id not in self.dependencies)


@dataclass
class ParsedTask:
    """Result of parsing a natural language task."""
    original_input: str
    subtasks: List[SubTask]
    global_context: Dict[str, Any] = field(default_factory=dict)

    def get_parallel_groups(self) -> List[List[SubTask]]:
        """Group subtasks into parallel execution batches."""
        if not self.subtasks:
            return []

        groups = []
        remaining = list(self.subtasks)
        completed_ids = set()

        while remaining:
            # Find all tasks whose dependencies are satisfied
            ready = [t for t in remaining
                    if all(dep in completed_ids for dep in t.dependencies)]

            if not ready:
                # Circular dependency or error - take first remaining if available
                if remaining:
                    ready = [remaining[0]]
                else:
                    break  # Safety: exit if no remaining tasks

            groups.append(ready)
            for task in ready:
                remaining.remove(task)
                completed_ids.add(task.id)

        return groups


class TaskParser:
    """Parses natural language task descriptions into structured subtasks."""

    # Keywords that indicate specific task types
    TASK_KEYWORDS = {
        TaskType.CODE: [
            'write', 'code', 'implement', 'create function', 'build',
            'develop', 'program', 'fix', 'debug', 'refactor', 'add feature'
        ],
        TaskType.RESEARCH: [
            'find', 'search', 'look for', 'explore', 'investigate',
            'understand', 'analyze', 'review', 'check', 'examine'
        ],
        TaskType.VISION: [
            'webcam', 'camera', 'image', 'video', 'vision', 'detect',
            'recognize', 'hand', 'face', 'pose', 'gesture', 'mediapipe',
            'opencv', 'visual', 'see', 'watch', 'track'
        ],
        TaskType.AUDIO: [
            'audio', 'sound', 'microphone', 'listen', 'voice', 'speech',
            'record', 'hear', 'sounddevice', 'frequency', 'volume'
        ],
        TaskType.KICAD: [
            'kicad', 'pcb', 'schematic', 'circuit', 'footprint', 'symbol',
            'gerber', 'trace', 'routing', 'copper', 'solder', 'component',
            'capacitor', 'resistor', 'inductor', 'microcontroller', 'connector',
            'eeschema', 'pcbnew', 'board layout', 'netlist', 'bom',
            'drc', 'erc', 'drill', 'via', 'pad', 'silkscreen',
            'fabrication', 'electronics', 'eda', 'solder mask'
        ],
        TaskType.TOUCHDESIGNER: [
            'touchdesigner', 'touch designer', 'derivative', 'chop', 'top',
            'sop', 'dat', 'comp', 'tox', 'glsl', 'shader',
            'projection mapping', 'generative', 'audio reactive',
            'interactive installation', 'ndi', 'dmx', 'art-net', 'spout',
            'syphon', 'pixel mapping', 'perform mode', 'realtime visuals',
            'motion graphics', 'led wall', 'texture operator',
            'channel operator', 'surface operator'
        ],
        TaskType.PLAN: [
            'plan', 'design', 'architect', 'strategy', 'approach',
            'outline', 'structure', 'organize'
        ],
        TaskType.SECURITY: [
            'security', 'audit', 'vulnerability', 'secure', 'penetration',
            'owasp', 'sanitize', 'validate input', 'injection', 'xss',
            'csrf', 'authentication', 'authorization', 'encrypt', 'pentest'
        ]
    }

    # Patterns that indicate task boundaries
    TASK_SEPARATORS = [
        r'\band\b',
        r'\bthen\b',
        r'\bafter that\b',
        r'\bnext\b',
        r'\bfinally\b',
        r'\balso\b',
        r',\s*(?=\w)',
        r';\s*'
    ]

    # Dependency indicators
    DEPENDENCY_PATTERNS = [
        (r'after\s+(\w+ing)', 'after'),
        (r'once\s+(\w+)', 'once'),
        (r'when\s+(\w+)', 'when'),
        (r'using\s+(?:the\s+)?results?\s+(?:from|of)', 'using_results'),
        (r'based\s+on', 'based_on'),
        (r'with\s+(?:the\s+)?(?:context|info|information)\s+from', 'with_context')
    ]

    def __init__(self):
        self._task_counter = 0

    def parse(self, user_input: str) -> ParsedTask:
        """
        Parse natural language input into structured tasks.

        Args:
            user_input: Natural language task description from user

        Returns:
            ParsedTask with extracted subtasks and context
        """
        self._task_counter = 0

        # Validate input
        if not user_input:
            raise ValueError("User input cannot be empty")
        if not isinstance(user_input, str):
            raise TypeError("User input must be a string")

        # Sanitize input - remove potentially dangerous characters
        user_input = user_input.strip()
        if len(user_input) > 10000:
            user_input = user_input[:10000]  # Limit input length

        # Normalize input
        normalized = self._normalize_input(user_input)

        # Extract global context (entities, files, etc.)
        global_context = self._extract_global_context(normalized)

        # Split into potential subtasks
        task_segments = self._split_into_segments(normalized)

        # Classify and create subtasks
        subtasks = []
        for segment in task_segments:
            if segment.strip():
                subtask = self._create_subtask(segment, global_context)
                subtasks.append(subtask)

        # If no subtasks found, create a single task from entire input
        if not subtasks:
            subtasks = [self._create_subtask(normalized, global_context)]

        # Detect dependencies between subtasks
        self._detect_dependencies(subtasks, normalized)

        return ParsedTask(
            original_input=user_input,
            subtasks=subtasks,
            global_context=global_context
        )

    def _normalize_input(self, text: str) -> str:
        """Normalize input text for parsing."""
        # Lowercase for matching (keep original for display)
        text = text.strip()
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        return text

    def _extract_global_context(self, text: str) -> Dict[str, Any]:
        """Extract global context like file names, technologies, etc."""
        context = {}

        # Extract file paths — validate to relative paths only, no traversal sequences
        raw_paths = re.findall(r'[\w./\\]+\.\w{1,5}', text)
        safe_paths = [
            p for p in raw_paths
            if '..' not in p
            and not p.startswith(('\\\\', '//'))
            and len(p) <= 260
        ]
        if safe_paths:
            context['files'] = safe_paths

        # Extract quoted strings (often specific names/identifiers)
        quoted = re.findall(r'["\']([^"\']+)["\']', text)
        if quoted:
            context['quoted_terms'] = quoted

        # Detect technologies mentioned
        tech_keywords = [
            'mediapipe', 'opencv', 'numpy', 'python', 'sounddevice',
            'kicad', 'pcbnew', 'eeschema', 'gerber', 'spice',
            'touchdesigner', 'glsl', 'osc', 'midi', 'ndi', 'dmx', 'art-net'
        ]
        mentioned_tech = [t for t in tech_keywords if t in text.lower()]
        if mentioned_tech:
            context['technologies'] = mentioned_tech

        return context

    def _split_into_segments(self, text: str) -> List[str]:
        """Split text into potential task segments."""
        # Try to split on task separators
        combined_pattern = '|'.join(f'({p})' for p in self.TASK_SEPARATORS)

        # Split but keep meaningful chunks
        parts = re.split(combined_pattern, text, flags=re.IGNORECASE)

        # Clean up and filter
        segments = []
        current_segment = []

        for part in parts:
            if part is None:
                continue
            part = part.strip()
            if not part:
                continue

            # Check if this is a separator
            is_separator = any(re.match(p, part, re.IGNORECASE)
                              for p in self.TASK_SEPARATORS)

            if is_separator:
                if current_segment:
                    segments.append(' '.join(current_segment))
                    current_segment = []
            else:
                current_segment.append(part)

        if current_segment:
            segments.append(' '.join(current_segment))

        # If we only got one segment or none, just return the original
        if len(segments) <= 1:
            return [text]

        return segments

    def _classify_task_type(self, text: str) -> TaskType:
        """Determine the type of task from text content."""
        text_lower = text.lower()

        scores = {task_type: 0 for task_type in TaskType}

        for task_type, keywords in self.TASK_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    scores[task_type] += 1

        # Get highest scoring type
        best_type = max(scores, key=scores.get)

        # Default to CODE if no clear match
        if scores[best_type] == 0:
            return TaskType.CODE

        return best_type

    def _create_subtask(self, segment: str, global_context: Dict[str, Any]) -> SubTask:
        """Create a SubTask from a text segment."""
        self._task_counter += 1
        task_id = f"task_{self._task_counter}"

        task_type = self._classify_task_type(segment)

        # Extract task-specific context
        task_context = dict(global_context)
        task_context['segment'] = segment

        return SubTask(
            id=task_id,
            description=segment,
            task_type=task_type,
            context=task_context
        )

    def _detect_dependencies(self, subtasks: List[SubTask], full_text: str) -> None:
        """Detect dependencies between subtasks based on text patterns."""
        full_text_lower = full_text.lower()

        for i, subtask in enumerate(subtasks):
            # Check for explicit dependency patterns
            for pattern, dep_type in self.DEPENDENCY_PATTERNS:
                if re.search(pattern, subtask.description, re.IGNORECASE):
                    # This task depends on previous tasks
                    if i > 0:
                        subtask.dependencies.append(subtasks[i-1].id)

            # Check for implicit sequential indicators
            sequential_words = ['then', 'after', 'next', 'finally']
            if any(word in subtask.description.lower() for word in sequential_words):
                if i > 0 and subtasks[i-1].id not in subtask.dependencies:
                    subtask.dependencies.append(subtasks[i-1].id)

            # Code tasks often depend on research tasks
            if subtask.task_type == TaskType.CODE:
                for prev in subtasks[:i]:
                    if prev.task_type == TaskType.RESEARCH:
                        if prev.id not in subtask.dependencies:
                            subtask.dependencies.append(prev.id)

            # Security tasks always run last — depend on every preceding subtask
            if subtask.task_type == TaskType.SECURITY:
                for prev in subtasks[:i]:
                    if prev.id not in subtask.dependencies:
                        subtask.dependencies.append(prev.id)

    def get_task_summary(self, parsed: ParsedTask) -> str:
        """Generate a human-readable summary of parsed tasks."""
        lines = [f"Parsed {len(parsed.subtasks)} subtask(s):"]

        for subtask in parsed.subtasks:
            deps = f" (depends on: {', '.join(subtask.dependencies)})" if subtask.dependencies else ""
            lines.append(f"  - [{subtask.task_type.value}] {subtask.description[:50]}...{deps}")

        groups = parsed.get_parallel_groups()
        lines.append(f"\nExecution groups: {len(groups)}")
        for i, group in enumerate(groups):
            task_ids = [t.id for t in group]
            lines.append(f"  Group {i+1}: {', '.join(task_ids)} (parallel)")

        return '\n'.join(lines)
