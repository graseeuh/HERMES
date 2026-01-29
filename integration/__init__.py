# HERMES Integration Module
# Interface between HERMES and Claude Code

from .claude_bridge import ClaudeBridge
from .ollama_client import OllamaClient, OllamaConfig, OllamaResponse
from .claude_llm_client import ClaudeLLMClient, ClaudeLLMConfig, ClaudeResponse

__all__ = [
    'ClaudeBridge',
    'OllamaClient', 'OllamaConfig', 'OllamaResponse',
    'ClaudeLLMClient', 'ClaudeLLMConfig', 'ClaudeResponse'
]
