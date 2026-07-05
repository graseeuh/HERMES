"""
HERMES Claude Code Executor
Executes tasks through the Claude Code CLI using your Pro subscription.
No API key needed - uses your existing Claude Pro/Claude Code access.
"""

import subprocess
import shutil
import json
import logging
import re
from dataclasses import dataclass
from typing import Optional, List
from pathlib import Path

logger = logging.getLogger(__name__)

# Patterns that attempt to override Claude Code's role or permissions.
_INJECTION_RE = re.compile(
    r"(?i)(ignore\s+(all\s+)?(previous|prior|above)\s+instructions?"
    r"|system\s+override"
    r"|you\s+are\s+now"
    r"|disregard\s+(all\s+)?instructions?"
    r"|forget\s+(all\s+)?(previous|prior|everything)"
    r"|<\s*/?(?:system|assistant|user)\s*>)"
)
_MAX_PROMPT_LENGTH = 20_000


def _sanitize_prompt(text: str) -> str:
    """Truncate and log-warn on detected injection patterns before subprocess hand-off."""
    if len(text) > _MAX_PROMPT_LENGTH:
        text = text[:_MAX_PROMPT_LENGTH]
    if _INJECTION_RE.search(text):
        logger.warning(
            "Possible prompt injection pattern detected in executor prompt (first 120 chars): %.120s",
            text,
        )
    return text


@dataclass
class ExecutionResult:
    """Result from Claude Code execution."""
    success: bool
    output: str
    error: Optional[str] = None
    tokens_used: Optional[int] = None


class ClaudeCodeExecutor:
    """
    Executes tasks through Claude Code CLI.

    This uses your Claude Pro subscription - no additional API costs.
    Claude Code has full capabilities: file access, code execution, subagents, etc.
    """

    def __init__(self, working_directory: Optional[str] = None):
        """
        Initialize the executor.

        Args:
            working_directory: Directory to run claude commands in (default: current)
        """
        self.working_directory = working_directory or str(Path.cwd())
        self._claude_path = self._find_claude_cli()

    def _find_claude_cli(self) -> Optional[str]:
        """Find the claude CLI executable."""
        # Check if claude is in PATH
        claude_path = shutil.which('claude')
        if claude_path:
            return claude_path

        # Common installation locations on Windows
        common_paths = [
            Path.home() / '.claude' / 'claude.exe',
            Path.home() / 'AppData' / 'Local' / 'Programs' / 'claude' / 'claude.exe',
            Path(r'C:\Program Files\Claude\claude.exe'),
        ]

        for path in common_paths:
            if path.exists():
                return str(path)

        return None

    def is_available(self) -> bool:
        """Check if Claude Code CLI is available."""
        if not self._claude_path:
            return False

        try:
            result = subprocess.run(
                [self._claude_path, '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, OSError):
            return False

    def execute(
        self,
        task: str,
        context: Optional[str] = None,
        max_turns: int = 5,
        timeout: int = 120
    ) -> ExecutionResult:
        """
        Execute a task through Claude Code.

        Args:
            task: The task description to execute
            context: Optional additional context
            max_turns: Maximum conversation turns (limits runaway executions)
            timeout: Timeout in seconds

        Returns:
            ExecutionResult with output or error
        """
        if not self._claude_path:
            return ExecutionResult(
                success=False,
                output="",
                error="Claude Code CLI not found. Is Claude Code installed?"
            )

        # Build the prompt and sanitize before handing off to subprocess
        prompt = task
        if context:
            prompt = f"{context}\n\nTask: {task}"
        prompt = _sanitize_prompt(prompt)

        # Build command
        # --print: Output response directly (non-interactive)
        # -p: Pass prompt as argument
        cmd = [
            self._claude_path,
            '--print',  # Non-interactive, print output
            '--max-turns', str(max_turns),  # Limit turns
            '-p', prompt  # The prompt/task
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.working_directory
            )

            if result.returncode == 0:
                # Clean up the output (remove any ANSI codes, etc.)
                output = self._clean_output(result.stdout)
                return ExecutionResult(
                    success=True,
                    output=output
                )
            else:
                return ExecutionResult(
                    success=False,
                    output=result.stdout,
                    error=result.stderr or f"Exit code: {result.returncode}"
                )

        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                output="",
                error=f"Task timed out after {timeout} seconds"
            )
        except OSError as e:
            return ExecutionResult(
                success=False,
                output="",
                error=f"Failed to run Claude Code: {e}"
            )

    def execute_with_files(
        self,
        task: str,
        files: List[str],
        timeout: int = 120
    ) -> ExecutionResult:
        """
        Execute a task that involves specific files.

        Args:
            task: The task description
            files: List of file paths to include as context
            timeout: Timeout in seconds

        Returns:
            ExecutionResult with output
        """
        # Build context with file references
        file_context = "Files involved:\n"
        for f in files:
            file_context += f"- {f}\n"

        return self.execute(task, context=file_context, timeout=timeout)

    def search_codebase(self, query: str, timeout: int = 60) -> ExecutionResult:
        """
        Search the codebase for something.

        Args:
            query: What to search for
            timeout: Timeout in seconds

        Returns:
            ExecutionResult with search results
        """
        task = f"Search the codebase for: {query}. Summarize what you find in 2-3 sentences."
        return self.execute(task, timeout=timeout, max_turns=3)

    def explain_code(self, file_path: str, timeout: int = 60) -> ExecutionResult:
        """
        Explain what a file does.

        Args:
            file_path: Path to the file
            timeout: Timeout in seconds

        Returns:
            ExecutionResult with explanation
        """
        task = f"Read {file_path} and explain what it does in 2-3 sentences."
        return self.execute(task, timeout=timeout, max_turns=2)

    def quick_task(self, task: str, timeout: int = 30) -> ExecutionResult:
        """
        Execute a quick, simple task.

        Args:
            task: Simple task description
            timeout: Timeout in seconds

        Returns:
            ExecutionResult
        """
        # Append instruction to keep response brief
        prompt = f"{task}\n\nKeep your response brief (1-2 sentences) as it will be spoken aloud."
        return self.execute(prompt, timeout=timeout, max_turns=2)

    def _clean_output(self, output: str) -> str:
        """Clean up CLI output for voice/display."""
        # Remove ANSI escape codes
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        output = ansi_escape.sub('', output)

        # Remove excessive whitespace
        output = re.sub(r'\n{3,}', '\n\n', output)

        # Strip leading/trailing whitespace
        output = output.strip()

        return output

    def get_voice_summary(self, result: ExecutionResult) -> str:
        """
        Get a voice-friendly summary of the result.

        Args:
            result: The execution result

        Returns:
            Short summary suitable for TTS
        """
        if not result.success:
            if result.error:
                return f"Sorry, there was an error: {result.error[:100]}"
            return "Sorry, I couldn't complete that task."

        output = result.output

        # If output is too long, truncate for voice
        if len(output) > 300:
            # Try to find a natural break point
            sentences = output.split('.')
            summary = ""
            for sentence in sentences:
                if len(summary) + len(sentence) < 280:
                    summary += sentence + "."
                else:
                    break
            return summary if summary else output[:280] + "..."

        return output


def test_executor():
    """Test the Claude Code executor."""
    print("Testing Claude Code Executor...")
    print("=" * 50)

    executor = ClaudeCodeExecutor()

    # Check availability
    if not executor.is_available():
        print("Claude Code CLI not found!")
        print("Make sure Claude Code is installed and 'claude' is in your PATH")
        return False

    print("Claude Code CLI: Available")
    print(f"Path: {executor._claude_path}")
    print()

    # Test a simple task
    print("Testing simple task...")
    result = executor.quick_task("What is 2 + 2? Answer in one word.")

    if result.success:
        print(f"Result: {result.output}")
        print("Test PASSED!")
        return True
    else:
        print(f"Error: {result.error}")
        print("Test FAILED")
        return False


if __name__ == "__main__":
    test_executor()
