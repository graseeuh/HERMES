"""
HERMES Whisper Speech Recognizer
Local offline speech recognition using faster-whisper.
"""

from dataclasses import dataclass
from typing import Optional, Tuple
from enum import Enum
import numpy as np
import io
import wave

try:
    from faster_whisper import WhisperModel
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False


class WhisperModelSize(Enum):
    """Available Whisper model sizes."""
    TINY = "tiny"       # ~39M params, fastest, least accurate
    BASE = "base"       # ~74M params, good balance for always-on
    SMALL = "small"     # ~244M params, better accuracy
    MEDIUM = "medium"   # ~769M params, high accuracy
    LARGE = "large-v3"  # ~1.5B params, best accuracy, slowest


@dataclass
class WhisperConfig:
    """Configuration for Whisper recognizer."""
    model_size: str = "base"  # Recommended for real-time voice control
    device: str = "cpu"       # "cpu" or "cuda"
    compute_type: str = "int8"  # "int8" for CPU, "float16" for GPU
    language: str = "en"      # Target language
    beam_size: int = 5        # Beam search size
    vad_filter: bool = True   # Voice Activity Detection filter


class WhisperRecognizer:
    """
    Local speech recognition using faster-whisper.
    Provides offline transcription capability.
    """

    def __init__(self, config: Optional[WhisperConfig] = None):
        self.config = config or WhisperConfig()
        self.model: Optional[WhisperModel] = None
        self._loaded = False

    def load_model(self) -> bool:
        """Load the Whisper model. Call once at startup."""
        if not WHISPER_AVAILABLE:
            print("Error: faster-whisper not installed. Install with: pip install faster-whisper")
            return False

        try:
            print(f"Loading Whisper model '{self.config.model_size}'...")
            self.model = WhisperModel(
                self.config.model_size,
                device=self.config.device,
                compute_type=self.config.compute_type
            )
            self._loaded = True
            print("Whisper model loaded successfully.")
            return True
        except Exception as e:
            print(f"Failed to load Whisper model: {e}")
            return False

    def transcribe(
        self,
        audio_data: np.ndarray,
        sample_rate: int = 16000
    ) -> Tuple[str, float]:
        """
        Transcribe audio data to text.

        Args:
            audio_data: Audio as numpy array (mono, float32)
            sample_rate: Sample rate of audio

        Returns:
            Tuple of (transcribed_text, confidence)
        """
        if not self._loaded:
            if not self.load_model():
                return ("", 0.0)

        # Convert to format expected by Whisper
        audio = self._prepare_audio(audio_data, sample_rate)

        segments, info = self.model.transcribe(
            audio,
            language=self.config.language,
            beam_size=self.config.beam_size,
            vad_filter=self.config.vad_filter
        )

        # Collect all segments
        full_text = ""
        total_confidence = 0.0
        segment_count = 0

        for segment in segments:
            full_text += segment.text
            total_confidence += segment.avg_logprob
            segment_count += 1

        # Calculate average confidence (convert log prob to probability)
        avg_confidence = 0.0
        if segment_count > 0:
            avg_logprob = total_confidence / segment_count
            # Normalize log prob to 0-1 range (typical range is -1 to 0)
            avg_confidence = min(1.0, max(0.0, (avg_logprob + 1.0)))

        return (full_text.strip(), avg_confidence)

    def transcribe_from_wav_bytes(self, wav_bytes: bytes) -> Tuple[str, float]:
        """Transcribe from WAV file bytes."""
        with io.BytesIO(wav_bytes) as wav_io:
            with wave.open(wav_io, 'rb') as wav_file:
                sample_rate = wav_file.getframerate()
                audio_data = np.frombuffer(
                    wav_file.readframes(wav_file.getnframes()),
                    dtype=np.int16
                ).astype(np.float32) / 32768.0

        return self.transcribe(audio_data, sample_rate)

    def _prepare_audio(self, audio: np.ndarray, sample_rate: int) -> np.ndarray:
        """Prepare audio for Whisper (16kHz mono float32)."""
        # Ensure mono
        if audio.ndim > 1:
            audio = audio.mean(axis=1)

        # Resample to 16kHz if needed
        if sample_rate != 16000:
            try:
                from scipy import signal
                num_samples = int(len(audio) * 16000 / sample_rate)
                audio = signal.resample(audio, num_samples)
            except ImportError:
                print("Warning: scipy not available for resampling. Using nearest-neighbor.")
                ratio = 16000 / sample_rate
                indices = (np.arange(int(len(audio) * ratio)) / ratio).astype(int)
                indices = np.clip(indices, 0, len(audio) - 1)
                audio = audio[indices]

        # Ensure float32
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)

        return audio

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @staticmethod
    def is_available() -> bool:
        """Check if Whisper is available."""
        return WHISPER_AVAILABLE
