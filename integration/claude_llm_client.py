"""
HERMES Claude LLM Client
Integration with Anthropic's Claude API for contextual response generation.
Includes usage tracking to prevent exceeding monthly limits.
"""

import os
import json
from dataclasses import dataclass, field
from datetime import datetime, date
from pathlib import Path
from typing import Optional

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


@dataclass
class UsageStats:
    """Track API usage to prevent overage."""
    input_tokens_today: int = 0
    output_tokens_today: int = 0
    input_tokens_month: int = 0
    output_tokens_month: int = 0
    last_reset_date: str = ""
    last_reset_month: str = ""

    def to_dict(self) -> dict:
        return {
            "input_tokens_today": self.input_tokens_today,
            "output_tokens_today": self.output_tokens_today,
            "input_tokens_month": self.input_tokens_month,
            "output_tokens_month": self.output_tokens_month,
            "last_reset_date": self.last_reset_date,
            "last_reset_month": self.last_reset_month
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'UsageStats':
        return cls(**data)


@dataclass
class ClaudeLLMConfig:
    """Configuration for Claude LLM client."""
    api_key: Optional[str] = None  # If None, uses ANTHROPIC_API_KEY env var
    model: str = "claude-sonnet-4-20250514"  # Fast and cost-effective
    max_tokens: int = 150  # Keep responses short for voice
    temperature: float = 0.7

    # Usage limits (conservative defaults for free tier / low usage)
    daily_input_token_limit: int = 50000  # ~50k input tokens/day
    daily_output_token_limit: int = 10000  # ~10k output tokens/day
    monthly_input_token_limit: int = 500000  # ~500k input tokens/month
    monthly_output_token_limit: int = 100000  # ~100k output tokens/month

    # System prompt optimized for voice responses
    system_prompt: str = """You are HERMES, a helpful voice assistant.
Keep responses concise and natural for spoken delivery.
Respond in 1-2 short sentences. Be helpful but brief.
Never use markdown, lists, or formatting - just plain spoken text."""


@dataclass
class ClaudeResponse:
    """Response from Claude API."""
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    error: Optional[str] = None
    limit_reached: bool = False


class ClaudeLLMClient:
    """
    Client for Claude API integration.
    Provides contextual response generation with usage tracking.
    """

    USAGE_FILE = Path.home() / ".hermes" / "claude_usage.json"

    def __init__(self, config: Optional[ClaudeLLMConfig] = None):
        self.config = config or ClaudeLLMConfig()
        self._client: Optional[anthropic.Anthropic] = None
        self._available = False
        self._usage = UsageStats()
        self._load_usage()

    def _load_usage(self) -> None:
        """Load usage stats from file."""
        try:
            if self.USAGE_FILE.exists():
                with open(self.USAGE_FILE, 'r') as f:
                    data = json.load(f)
                    self._usage = UsageStats.from_dict(data)
            self._check_reset_usage()
        except Exception as e:
            print(f"Warning: Could not load usage stats: {e}")
            self._usage = UsageStats()

    def _save_usage(self) -> None:
        """Save usage stats to file."""
        try:
            self.USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(self.USAGE_FILE, 'w') as f:
                json.dump(self._usage.to_dict(), f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save usage stats: {e}")

    def _check_reset_usage(self) -> None:
        """Reset daily/monthly counters if needed."""
        today = date.today().isoformat()
        month = date.today().strftime("%Y-%m")

        # Reset daily counters
        if self._usage.last_reset_date != today:
            self._usage.input_tokens_today = 0
            self._usage.output_tokens_today = 0
            self._usage.last_reset_date = today

        # Reset monthly counters
        if self._usage.last_reset_month != month:
            self._usage.input_tokens_month = 0
            self._usage.output_tokens_month = 0
            self._usage.last_reset_month = month

        self._save_usage()

    def _check_limits(self) -> tuple[bool, str]:
        """Check if usage limits have been reached."""
        self._check_reset_usage()

        if self._usage.input_tokens_today >= self.config.daily_input_token_limit:
            return False, "Daily input token limit reached"
        if self._usage.output_tokens_today >= self.config.daily_output_token_limit:
            return False, "Daily output token limit reached"
        if self._usage.input_tokens_month >= self.config.monthly_input_token_limit:
            return False, "Monthly input token limit reached"
        if self._usage.output_tokens_month >= self.config.monthly_output_token_limit:
            return False, "Monthly output token limit reached"

        return True, ""

    def _update_usage(self, input_tokens: int, output_tokens: int) -> None:
        """Update usage counters."""
        self._usage.input_tokens_today += input_tokens
        self._usage.output_tokens_today += output_tokens
        self._usage.input_tokens_month += input_tokens
        self._usage.output_tokens_month += output_tokens
        self._save_usage()

    def check_availability(self) -> bool:
        """Check if Claude API is available."""
        if not ANTHROPIC_AVAILABLE:
            print("Error: anthropic library not installed. Install with: pip install anthropic")
            return False

        api_key = self.config.api_key or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            print("Error: ANTHROPIC_API_KEY not set. Set it in environment or config.")
            return False

        try:
            self._client = anthropic.Anthropic(api_key=api_key)
            self._available = True
            print(f"Claude API available (model: {self.config.model})")
            return True
        except Exception as e:
            print(f"Claude API initialization failed: {e}")
            return False

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None
    ) -> ClaudeResponse:
        """
        Generate a response from Claude.

        Args:
            prompt: User's input/question
            system_prompt: Override system prompt

        Returns:
            ClaudeResponse with generated text
        """
        # Check limits first
        within_limits, limit_msg = self._check_limits()
        if not within_limits:
            return ClaudeResponse(
                text="I've reached my usage limit for now. Try again later.",
                limit_reached=True,
                error=limit_msg
            )

        if not self._available:
            if not self.check_availability():
                return ClaudeResponse(
                    text="I'm sorry, but my response system is currently unavailable.",
                    error="Claude API not available"
                )

        try:
            message = self._client.messages.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                system=system_prompt or self.config.system_prompt,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            # Extract response text
            text = ""
            for block in message.content:
                if hasattr(block, 'text'):
                    text += block.text

            # Update usage
            input_tokens = message.usage.input_tokens
            output_tokens = message.usage.output_tokens
            self._update_usage(input_tokens, output_tokens)

            return ClaudeResponse(
                text=text.strip(),
                input_tokens=input_tokens,
                output_tokens=output_tokens
            )

        except anthropic.RateLimitError:
            return ClaudeResponse(
                text="I'm being rate limited. Please wait a moment.",
                error="Rate limited"
            )
        except anthropic.APIError as e:
            return ClaudeResponse(
                text="I encountered an API error.",
                error=str(e)
            )
        except Exception as e:
            return ClaudeResponse(
                text="An error occurred while generating a response.",
                error=str(e)
            )

    def generate_contextual_response(
        self,
        user_input: str,
        task_result: Optional[str] = None,
        task_type: Optional[str] = None
    ) -> str:
        """
        Generate a contextual spoken response.

        Args:
            user_input: What the user said
            task_result: Result from HERMES task execution
            task_type: Type of task that was executed

        Returns:
            Natural language response suitable for TTS
        """
        if task_result:
            # Truncate long results to save tokens
            if len(task_result) > 500:
                task_result = task_result[:500] + "..."

            prompt = f"""User said: "{user_input}"
Task result: {task_result}
Give a brief spoken summary of what was done."""
        else:
            prompt = f"""User said: "{user_input}"
Give a brief spoken response."""

        response = self.generate(prompt)
        return response.text

    def chat(self, message: str) -> str:
        """Simple chat interface."""
        response = self.generate(message)
        return response.text

    def get_usage_summary(self) -> str:
        """Get a summary of current usage."""
        self._check_reset_usage()
        return f"""Usage Today: {self._usage.input_tokens_today:,}/{self.config.daily_input_token_limit:,} input, {self._usage.output_tokens_today:,}/{self.config.daily_output_token_limit:,} output
Usage This Month: {self._usage.input_tokens_month:,}/{self.config.monthly_input_token_limit:,} input, {self._usage.output_tokens_month:,}/{self.config.monthly_output_token_limit:,} output"""

    @property
    def is_available(self) -> bool:
        return self._available

    @staticmethod
    def anthropic_available() -> bool:
        return ANTHROPIC_AVAILABLE
