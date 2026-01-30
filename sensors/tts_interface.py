"""
HERMES Text-to-Speech Interface
Unified TTS wrapper supporting multiple backends.
"""

import logging
from dataclasses import dataclass
from typing import Optional, List, Dict
import threading

# Set up logger for TTS debugging
logger = logging.getLogger(__name__)

try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False


@dataclass
class TTSConfig:
    """Configuration for TTS."""
    rate: int = 150       # Words per minute
    volume: float = 1.0   # 0.0 to 1.0
    voice_id: Optional[str] = None  # Specific voice ID


class TTSInterface:
    """
    Text-to-Speech interface for HERMES.
    Provides spoken output capability.
    """

    def __init__(self, config: Optional[TTSConfig] = None):
        self.config = config or TTSConfig()
        self._engine = None
        self._lock = threading.Lock()
        self._initialized = False

    def initialize(self) -> bool:
        """Initialize the TTS engine."""
        if self._initialized:
            return True

        if not PYTTSX3_AVAILABLE:
            print("Warning: pyttsx3 not available. TTS disabled.")
            print("Install with: pip install pyttsx3")
            return False

        try:
            self._engine = pyttsx3.init()
            self._engine.setProperty('rate', self.config.rate)
            self._engine.setProperty('volume', self.config.volume)

            # Set specific voice if configured
            if self.config.voice_id:
                self._engine.setProperty('voice', self.config.voice_id)

            self._initialized = True
            return True
        except (RuntimeError, OSError) as e:
            # RuntimeError: pyttsx3 engine initialization failure
            # OSError: Audio device issues
            logger.error(f"TTS initialization failed: {e}")
            print(f"TTS initialization failed: {e}")
            return False

    def speak(self, text: str, block: bool = True) -> bool:
        """
        Speak the given text.

        Args:
            text: Text to speak
            block: Whether to wait for speech to complete

        Returns:
            True if speech started/completed successfully
        """
        if not self._initialized:
            if not self.initialize():
                print(f"[TTS unavailable] {text}")
                return False

        with self._lock:
            try:
                self._engine.say(text)
                if block:
                    self._engine.runAndWait()
                return True
            except RuntimeError as e:
                # Engine busy or audio device issues
                logger.warning(f"TTS speak error: {e}")
                print(f"TTS error: {e}")
                return False

    def speak_async(self, text: str) -> None:
        """Speak text without blocking."""
        thread = threading.Thread(
            target=self.speak,
            args=(text, True),
            daemon=True
        )
        thread.start()

    def stop(self) -> None:
        """Stop any ongoing speech."""
        if self._engine:
            try:
                self._engine.stop()
            except RuntimeError as e:
                # Engine may already be stopped or not running
                logger.debug(f"TTS stop() - engine not running: {e}")

    def list_voices(self) -> List[Dict]:
        """List available voices."""
        if not self._initialized:
            self.initialize()

        if self._engine:
            try:
                voices = self._engine.getProperty('voices')
                return [
                    {
                        'id': v.id,
                        'name': v.name,
                        'languages': getattr(v, 'languages', []),
                        'gender': getattr(v, 'gender', None)
                    }
                    for v in voices
                ]
            except (RuntimeError, AttributeError) as e:
                logger.warning(f"Failed to list TTS voices: {e}")
        return []

    def set_voice(self, voice_id: str) -> bool:
        """Set the voice to use."""
        if self._engine:
            try:
                self._engine.setProperty('voice', voice_id)
                return True
            except (RuntimeError, ValueError) as e:
                logger.warning(f"Failed to set TTS voice '{voice_id}': {e}")
                return False
        return False

    def set_rate(self, rate: int) -> bool:
        """Set the speaking rate (words per minute)."""
        if self._engine:
            try:
                self._engine.setProperty('rate', rate)
                self.config.rate = rate
                return True
            except (RuntimeError, ValueError) as e:
                logger.warning(f"Failed to set TTS rate to {rate}: {e}")
                return False
        return False

    def set_volume(self, volume: float) -> bool:
        """Set the volume (0.0 to 1.0)."""
        if self._engine:
            try:
                volume = max(0.0, min(1.0, volume))
                self._engine.setProperty('volume', volume)
                self.config.volume = volume
                return True
            except (RuntimeError, ValueError) as e:
                logger.warning(f"Failed to set TTS volume to {volume}: {e}")
                return False
        return False

    def cleanup(self) -> None:
        """Clean up TTS resources."""
        self.stop()
        self._engine = None
        self._initialized = False

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @staticmethod
    def is_available() -> bool:
        """Check if TTS is available."""
        return PYTTSX3_AVAILABLE

    def __enter__(self):
        self.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
        return False
