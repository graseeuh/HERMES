"""
HERMES Ollama Client
Integration with local Ollama LLM for contextual response generation.
"""

from dataclasses import dataclass
from typing import Optional, List

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


@dataclass
class OllamaConfig:
    """Configuration for Ollama client."""
    host: str = "http://localhost:11434"
    model: str = "llama3.2"  # Default model
    timeout: int = 30
    context_window: int = 4096
    temperature: float = 0.7
    system_prompt: str = """You are HERMES, a helpful voice assistant.
Keep responses concise and natural for spoken delivery.
Respond in 1-2 sentences unless more detail is explicitly requested.
Be friendly but efficient."""


@dataclass
class OllamaResponse:
    """Response from Ollama."""
    text: str
    model: str
    done: bool
    context: Optional[List[int]] = None
    error: Optional[str] = None


class OllamaClient:
    """
    Client for local Ollama LLM integration.
    Provides contextual response generation for voice interactions.
    """

    def __init__(self, config: Optional[OllamaConfig] = None):
        self.config = config or OllamaConfig()
        self._available = False
        self._context: Optional[List[int]] = None  # Conversation context

    def check_availability(self) -> bool:
        """Check if Ollama server is running and model is available."""
        if not REQUESTS_AVAILABLE:
            print("Error: requests library not installed. Install with: pip install requests")
            return False

        try:
            response = requests.get(
                f"{self.config.host}/api/tags",
                timeout=5
            )
            if response.status_code == 200:
                models = response.json().get('models', [])
                model_names = [m['name'] for m in models]

                # Check if configured model is available (with or without :latest tag)
                model_base = self.config.model.split(':')[0]
                if any(model_base in name for name in model_names):
                    self._available = True
                    print(f"Ollama available with model: {self.config.model}")
                    return True
                else:
                    print(f"Model '{self.config.model}' not found in Ollama.")
                    if model_names:
                        print(f"Available models: {', '.join(model_names)}")
                    else:
                        print("No models installed. Run: ollama pull llama3.2")
                    return False
            return False
        except requests.exceptions.ConnectionError:
            print("Ollama server not running. Start with: ollama serve")
            return False
        except Exception as e:
            print(f"Ollama check failed: {e}")
            return False

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        maintain_context: bool = True
    ) -> OllamaResponse:
        """
        Generate a response from the LLM.

        Args:
            prompt: User's input/question
            system_prompt: Override system prompt
            maintain_context: Whether to maintain conversation context

        Returns:
            OllamaResponse with generated text
        """
        if not self._available:
            if not self.check_availability():
                return OllamaResponse(
                    text="I'm sorry, but my response system is currently unavailable.",
                    model=self.config.model,
                    done=True,
                    error="Ollama not available"
                )

        payload = {
            "model": self.config.model,
            "prompt": prompt,
            "system": system_prompt or self.config.system_prompt,
            "stream": False,
            "options": {
                "temperature": self.config.temperature,
                "num_ctx": self.config.context_window
            }
        }

        # Include conversation context if maintaining
        if maintain_context and self._context:
            payload["context"] = self._context

        try:
            response = requests.post(
                f"{self.config.host}/api/generate",
                json=payload,
                timeout=self.config.timeout
            )

            if response.status_code == 200:
                data = response.json()

                # Store context for next turn
                if maintain_context:
                    self._context = data.get('context')

                return OllamaResponse(
                    text=data.get('response', '').strip(),
                    model=data.get('model', self.config.model),
                    done=data.get('done', True),
                    context=data.get('context')
                )
            else:
                return OllamaResponse(
                    text="I encountered an error generating a response.",
                    model=self.config.model,
                    done=True,
                    error=f"HTTP {response.status_code}"
                )

        except requests.exceptions.Timeout:
            return OllamaResponse(
                text="Response generation timed out.",
                model=self.config.model,
                done=True,
                error="Timeout"
            )
        except Exception as e:
            return OllamaResponse(
                text="An error occurred while generating a response.",
                model=self.config.model,
                done=True,
                error=str(e)
            )

    def generate_contextual_response(
        self,
        user_input: str,
        task_result: Optional[str] = None,
        task_type: Optional[str] = None
    ) -> str:
        """
        Generate a contextual spoken response based on user input and task result.

        Args:
            user_input: What the user said
            task_result: Result from HERMES task execution
            task_type: Type of task that was executed

        Returns:
            Natural language response suitable for TTS
        """
        # Build contextual prompt
        if task_result:
            prompt = f"""The user said: "{user_input}"

The task was completed with this result:
{task_result}

Generate a brief, natural spoken response summarizing what was done. Keep it under 2 sentences."""
        else:
            prompt = f"""The user said: "{user_input}"

Generate a brief, natural spoken acknowledgment or response. Keep it under 2 sentences."""

        response = self.generate(prompt)
        return response.text

    def chat(self, message: str) -> str:
        """
        Simple chat interface for conversational responses.

        Args:
            message: User's message

        Returns:
            Assistant's response text
        """
        response = self.generate(message)
        return response.text

    def clear_context(self) -> None:
        """Clear conversation context for a fresh start."""
        self._context = None

    @property
    def is_available(self) -> bool:
        return self._available

    @staticmethod
    def requests_available() -> bool:
        """Check if requests library is available."""
        return REQUESTS_AVAILABLE
