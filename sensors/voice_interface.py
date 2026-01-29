"""
HERMES Voice Interface
Speech recognition and voice command processing.
Supports multiple backends: Google Speech-to-Text and local Whisper.
"""

import threading
import queue
from typing import Optional, Callable, List, Tuple
from dataclasses import dataclass
from enum import Enum

import numpy as np

try:
    import speech_recognition as sr
    SR_AVAILABLE = True
except ImportError:
    SR_AVAILABLE = False

try:
    from .whisper_recognizer import WhisperRecognizer, WhisperConfig, WHISPER_AVAILABLE
except ImportError:
    WHISPER_AVAILABLE = False
    WhisperRecognizer = None
    WhisperConfig = None

from .audio_interface import AudioInterface, AudioConfig


class RecognitionBackend(Enum):
    """Available speech recognition backends."""
    GOOGLE = "google"
    WHISPER = "whisper"


class VoiceState(Enum):
    """Voice interface states."""
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"


@dataclass
class VoiceCommand:
    """Recognized voice command."""
    text: str
    confidence: float
    is_wake_word: bool = False


class VoiceInterface:
    """
    Voice recognition interface for HERMES.
    Supports wake words, continuous listening, and command recognition.
    Backends: 'whisper' (local, offline) or 'google' (cloud-based).
    """

    DEFAULT_WAKE_WORDS = ["hermes", "hey hermes", "ok hermes"]

    def __init__(
        self,
        wake_words: Optional[List[str]] = None,
        language: str = "en-US",
        backend: str = "whisper",
        whisper_config: Optional['WhisperConfig'] = None
    ):
        """
        Initialize the voice interface.

        Args:
            wake_words: List of wake words to listen for (None to disable)
            language: Language code for recognition
            backend: Recognition backend - 'whisper' (default) or 'google'
            whisper_config: Configuration for Whisper (if using whisper backend)
        """
        self._check_dependencies()

        self.wake_words = wake_words or self.DEFAULT_WAKE_WORDS
        self.language = language
        self._state = VoiceState.IDLE

        # Initialize speech_recognition (needed for audio capture with both backends)
        if SR_AVAILABLE:
            self.recognizer = sr.Recognizer()
            self.microphone = None
        else:
            self.recognizer = None
            self.microphone = None

        # Initialize recognition backend
        self.backend = RecognitionBackend(backend) if isinstance(backend, str) else backend
        self.whisper: Optional[WhisperRecognizer] = None

        if self.backend == RecognitionBackend.WHISPER:
            if WHISPER_AVAILABLE and WhisperRecognizer is not None:
                # Create config with language matching
                if whisper_config is None:
                    whisper_config = WhisperConfig(language=language.split('-')[0])
                self.whisper = WhisperRecognizer(whisper_config)
                # Pre-load model for faster first recognition
                if not self.whisper.load_model():
                    print("Warning: Whisper model failed to load, falling back to Google")
                    self.backend = RecognitionBackend.GOOGLE
            else:
                print("Warning: Whisper not available, falling back to Google STT")
                self.backend = RecognitionBackend.GOOGLE

        self._command_queue: queue.Queue = queue.Queue()
        self._stop_event = threading.Event()
        self._listen_thread: Optional[threading.Thread] = None
        self._command_callback: Optional[Callable[[VoiceCommand], None]] = None

    def _check_dependencies(self) -> None:
        """Check if required dependencies are available."""
        if not SR_AVAILABLE:
            print("Warning: speech_recognition not available. Voice features disabled.")
            print("Install with: pip install SpeechRecognition")

    @property
    def state(self) -> VoiceState:
        """Current state of the voice interface."""
        return self._state

    def list_microphones(self) -> List[dict]:
        """List available microphones."""
        if not SR_AVAILABLE:
            return []

        mics = []
        for i, name in enumerate(sr.Microphone.list_microphone_names()):
            mics.append({
                'index': i,
                'name': name
            })
        return mics

    def set_microphone(self, device_index: Optional[int] = None) -> bool:
        """
        Set the microphone to use.

        Args:
            device_index: Microphone index (None for default)

        Returns:
            True if microphone set successfully
        """
        if not SR_AVAILABLE:
            return False

        try:
            self.microphone = sr.Microphone(device_index=device_index)
            return True
        except Exception as e:
            print(f"Failed to set microphone: {e}")
            return False

    def calibrate(self, duration: float = 1.0) -> bool:
        """
        Calibrate for ambient noise.

        Args:
            duration: Calibration duration in seconds

        Returns:
            True if calibration successful
        """
        if not SR_AVAILABLE or not self.microphone:
            if not self.set_microphone():
                return False

        try:
            with self.microphone as source:
                print(f"Calibrating for {duration}s... Please be quiet.")
                self.recognizer.adjust_for_ambient_noise(source, duration=duration)
                print("Calibration complete.")
            return True
        except Exception as e:
            print(f"Calibration failed: {e}")
            return False

    def listen_once(self, timeout: float = 5.0) -> Optional[VoiceCommand]:
        """
        Listen for a single voice command.

        Args:
            timeout: Maximum time to wait for speech

        Returns:
            VoiceCommand if recognized, None otherwise
        """
        if not SR_AVAILABLE:
            print("Speech recognition not available")
            return None

        if not self.microphone:
            if not self.set_microphone():
                return None

        self._state = VoiceState.LISTENING

        try:
            with self.microphone as source:
                audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=10)

            self._state = VoiceState.PROCESSING

            # Route to appropriate backend
            if self.backend == RecognitionBackend.WHISPER and self.whisper is not None:
                text, confidence = self._recognize_whisper(audio)
            else:
                text, confidence = self._recognize_google(audio)

            self._state = VoiceState.IDLE

            if text:
                command = VoiceCommand(
                    text=text,
                    confidence=confidence,
                    is_wake_word=self._is_wake_word(text)
                )
                print(f"Recognized: '{text}'")
                return command
            return None

        except sr.WaitTimeoutError:
            self._state = VoiceState.IDLE
            return None
        except sr.UnknownValueError:
            self._state = VoiceState.IDLE
            return None
        except sr.RequestError as e:
            print(f"Recognition service error: {e}")
            self._state = VoiceState.IDLE
            return None
        except Exception as e:
            print(f"Error: {e}")
            self._state = VoiceState.IDLE
            return None

    def _recognize_whisper(self, audio) -> Tuple[str, float]:
        """
        Recognize speech using local Whisper model.

        Args:
            audio: SpeechRecognition AudioData object

        Returns:
            Tuple of (transcribed_text, confidence)
        """
        try:
            # Convert SpeechRecognition audio to numpy array
            audio_data = np.frombuffer(
                audio.get_raw_data(),
                dtype=np.int16
            ).astype(np.float32) / 32768.0

            text, confidence = self.whisper.transcribe(
                audio_data,
                sample_rate=audio.sample_rate
            )
            return (text, confidence)
        except Exception as e:
            print(f"Whisper recognition error: {e}")
            return ("", 0.0)

    def _recognize_google(self, audio) -> Tuple[str, float]:
        """
        Recognize speech using Google Speech-to-Text (cloud).

        Args:
            audio: SpeechRecognition AudioData object

        Returns:
            Tuple of (transcribed_text, confidence)
        """
        try:
            text = self.recognizer.recognize_google(audio, language=self.language)
            return (text, 1.0)  # Google doesn't return confidence
        except sr.UnknownValueError:
            return ("", 0.0)
        except sr.RequestError as e:
            print(f"Google recognition error: {e}")
            return ("", 0.0)
        except Exception as e:
            print(f"Recognition error: {e}")
            return ("", 0.0)

    def _is_wake_word(self, text: str) -> bool:
        """Check if text contains a wake word."""
        text_lower = text.lower()
        return any(wake.lower() in text_lower for wake in self.wake_words)

    def start_continuous_listening(
        self,
        callback: Callable[[VoiceCommand], None],
        require_wake_word: bool = True
    ) -> bool:
        """
        Start continuous listening for voice commands.

        Args:
            callback: Function called when command recognized
            require_wake_word: If True, only trigger callback after wake word

        Returns:
            True if listening started
        """
        if not SR_AVAILABLE:
            return False

        if self._listen_thread and self._listen_thread.is_alive():
            return False

        self._command_callback = callback
        self._stop_event.clear()

        def listen_loop():
            wake_word_active = not require_wake_word

            while not self._stop_event.is_set():
                command = self.listen_once(timeout=3.0)

                if command:
                    if require_wake_word:
                        if command.is_wake_word:
                            wake_word_active = True
                            print("Wake word detected! Listening for command...")
                            # Listen for actual command
                            actual_command = self.listen_once(timeout=5.0)
                            if actual_command:
                                callback(actual_command)
                            wake_word_active = False
                    else:
                        callback(command)

        self._listen_thread = threading.Thread(target=listen_loop, daemon=True)
        self._listen_thread.start()
        self._state = VoiceState.LISTENING
        return True

    def stop_continuous_listening(self) -> None:
        """Stop continuous listening."""
        self._stop_event.set()
        if self._listen_thread:
            self._listen_thread.join(timeout=2.0)
            self._listen_thread = None
        self._state = VoiceState.IDLE

    def recognize_from_audio_data(self, audio_data: bytes, sample_rate: int = 16000) -> Optional[VoiceCommand]:
        """
        Recognize speech from raw audio data.

        Args:
            audio_data: Raw audio bytes
            sample_rate: Sample rate of the audio

        Returns:
            VoiceCommand if recognized
        """
        if not SR_AVAILABLE:
            return None

        try:
            audio = sr.AudioData(audio_data, sample_rate, 2)

            # Route to appropriate backend
            if self.backend == RecognitionBackend.WHISPER and self.whisper is not None:
                text, confidence = self._recognize_whisper(audio)
            else:
                text, confidence = self._recognize_google(audio)

            if text:
                return VoiceCommand(
                    text=text,
                    confidence=confidence,
                    is_wake_word=self._is_wake_word(text)
                )
            return None
        except Exception as e:
            print(f"Recognition failed: {e}")
            return None

    @property
    def current_backend(self) -> str:
        """Return the name of the current recognition backend."""
        return self.backend.value

    def cleanup(self) -> None:
        """Release resources."""
        self.stop_continuous_listening()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
        return False
