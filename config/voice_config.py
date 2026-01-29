"""
HERMES Voice Configuration
Centralized settings for voice recognition, TTS, and LLM.
"""

from dataclasses import dataclass
from typing import Tuple
import os


@dataclass
class HermesVoiceConfig:
    """Complete voice system configuration."""

    # Speech Recognition
    stt_backend: str = "whisper"  # "whisper" or "google"
    whisper_model: str = "base"   # tiny, base, small, medium, large-v3
    whisper_device: str = "cpu"   # "cpu" or "cuda"
    language: str = "en"

    # Text-to-Speech
    tts_enabled: bool = True
    tts_rate: int = 150
    tts_volume: float = 1.0

    # Ollama LLM
    llm_enabled: bool = True
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    ollama_timeout: int = 30

    # Wake Words
    wake_words: Tuple[str, ...] = ("hey hermes", "hermes", "ok hermes")

    @classmethod
    def from_env(cls) -> 'HermesVoiceConfig':
        """Load configuration from environment variables."""
        return cls(
            stt_backend=os.getenv('HERMES_STT_BACKEND', 'whisper'),
            whisper_model=os.getenv('HERMES_WHISPER_MODEL', 'base'),
            whisper_device=os.getenv('HERMES_WHISPER_DEVICE', 'cpu'),
            language=os.getenv('HERMES_LANGUAGE', 'en'),
            tts_enabled=os.getenv('HERMES_TTS_ENABLED', 'true').lower() == 'true',
            tts_rate=int(os.getenv('HERMES_TTS_RATE', '150')),
            llm_enabled=os.getenv('HERMES_LLM_ENABLED', 'true').lower() == 'true',
            ollama_host=os.getenv('HERMES_OLLAMA_HOST', 'http://localhost:11434'),
            ollama_model=os.getenv('HERMES_OLLAMA_MODEL', 'llama3.2'),
            ollama_timeout=int(os.getenv('HERMES_OLLAMA_TIMEOUT', '30')),
        )

    @classmethod
    def minimal(cls) -> 'HermesVoiceConfig':
        """Create minimal configuration (no LLM, basic STT)."""
        return cls(
            stt_backend='whisper',
            whisper_model='tiny',  # Fastest, least accurate
            tts_enabled=True,
            llm_enabled=False
        )

    @classmethod
    def full(cls) -> 'HermesVoiceConfig':
        """Create full configuration with all features enabled."""
        return cls(
            stt_backend='whisper',
            whisper_model='base',
            tts_enabled=True,
            llm_enabled=True
        )
