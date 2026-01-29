"""
HERMES Audio Interface
Wrapper for sounddevice for audio capture and processing.
"""

import numpy as np
from typing import Optional, Callable, List, Tuple
from dataclasses import dataclass
from enum import Enum
import threading
import queue

try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    SOUNDDEVICE_AVAILABLE = False


class AudioState(Enum):
    """Audio interface states."""
    IDLE = "idle"
    RECORDING = "recording"
    PLAYING = "playing"
    STREAMING = "streaming"


@dataclass
class AudioConfig:
    """Audio configuration settings."""
    sample_rate: int = 44100
    channels: int = 1
    dtype: str = 'float32'
    blocksize: int = 1024
    device: Optional[int] = None  # None for default device


@dataclass
class AudioAnalysis:
    """Results of audio analysis."""
    rms_volume: float  # Root mean square volume (0-1)
    peak_volume: float  # Peak amplitude (0-1)
    dominant_frequency: Optional[float]  # Hz
    is_silent: bool
    duration: float  # seconds


class AudioInterface:
    """
    Interface for audio capture and processing using sounddevice.
    """

    # Volume threshold for silence detection
    SILENCE_THRESHOLD = 0.01

    def __init__(self, config: Optional[AudioConfig] = None):
        """
        Initialize the audio interface.

        Args:
            config: Audio configuration (uses defaults if None)
        """
        self.config = config or AudioConfig()
        self._state = AudioState.IDLE
        self._stream: Optional[sd.InputStream] = None
        self._recording_buffer: List[np.ndarray] = []
        self._audio_queue: queue.Queue = queue.Queue()
        self._callback: Optional[Callable] = None
        self._stop_event = threading.Event()

        self._check_dependencies()

    def _check_dependencies(self) -> None:
        """Check if required dependencies are available."""
        if not SOUNDDEVICE_AVAILABLE:
            print("Warning: sounddevice not available. Audio features limited.")

    @property
    def state(self) -> AudioState:
        """Current state of the audio interface."""
        return self._state

    def list_devices(self) -> List[dict]:
        """
        List available audio devices.

        Returns:
            List of device info dictionaries
        """
        if not SOUNDDEVICE_AVAILABLE:
            return []

        devices = sd.query_devices()
        return [
            {
                'index': i,
                'name': d['name'],
                'channels': d['max_input_channels'],
                'sample_rate': d['default_samplerate'],
                'is_input': d['max_input_channels'] > 0,
                'is_output': d['max_output_channels'] > 0
            }
            for i, d in enumerate(devices)
        ]

    def get_default_device(self) -> Optional[dict]:
        """Get the default input device info."""
        if not SOUNDDEVICE_AVAILABLE:
            return None

        try:
            default_devices = sd.default.device
            # Check if default devices are available
            if default_devices is None or not hasattr(default_devices, '__getitem__'):
                return None
            if isinstance(default_devices, (list, tuple)) and len(default_devices) == 0:
                return None

            device_id = default_devices[0]  # Input device
            if device_id is None or device_id < 0:
                return None

            device = sd.query_devices(device_id)
            return {
                'index': device_id,
                'name': device['name'],
                'channels': device['max_input_channels'],
                'sample_rate': device['default_samplerate']
            }
        except (IndexError, KeyError, TypeError, Exception):
            return None

    def start_recording(self, duration: Optional[float] = None) -> bool:
        """
        Start recording audio.

        Args:
            duration: Recording duration in seconds (None for continuous)

        Returns:
            True if recording started successfully
        """
        if not SOUNDDEVICE_AVAILABLE:
            return False

        if self._state != AudioState.IDLE:
            return False

        self._recording_buffer = []
        self._stop_event.clear()

        def callback(indata, frames, time, status):
            if status:
                print(f"Audio status: {status}")
            self._recording_buffer.append(indata.copy())

            if self._callback:
                self._callback(indata)

        try:
            self._stream = sd.InputStream(
                samplerate=self.config.sample_rate,
                channels=self.config.channels,
                dtype=self.config.dtype,
                blocksize=self.config.blocksize,
                device=self.config.device,
                callback=callback
            )
            self._stream.start()
            self._state = AudioState.RECORDING

            if duration:
                # Schedule stop after duration
                timer = threading.Timer(duration, self.stop_recording)
                timer.start()

            return True

        except Exception as e:
            print(f"Failed to start recording: {e}")
            return False

    def stop_recording(self) -> Optional[np.ndarray]:
        """
        Stop recording and return the recorded audio.

        Returns:
            Recorded audio as numpy array, or None if not recording
        """
        if self._state != AudioState.RECORDING:
            return None

        self._stop_event.set()

        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        self._state = AudioState.IDLE

        if self._recording_buffer:
            return np.concatenate(self._recording_buffer)
        return None

    def record_blocking(self, duration: float) -> Optional[np.ndarray]:
        """
        Record audio for a specific duration (blocking).

        Args:
            duration: Recording duration in seconds

        Returns:
            Recorded audio as numpy array
        """
        if not SOUNDDEVICE_AVAILABLE:
            return None

        try:
            frames = int(duration * self.config.sample_rate)
            recording = sd.rec(
                frames,
                samplerate=self.config.sample_rate,
                channels=self.config.channels,
                dtype=self.config.dtype,
                device=self.config.device
            )
            sd.wait()
            return recording
        except Exception as e:
            print(f"Recording failed: {e}")
            return None

    def play_audio(self, audio: np.ndarray, blocking: bool = True) -> bool:
        """
        Play audio data.

        Args:
            audio: Audio data as numpy array
            blocking: Whether to wait for playback to complete

        Returns:
            True if playback started successfully
        """
        if not SOUNDDEVICE_AVAILABLE:
            return False

        try:
            self._state = AudioState.PLAYING
            sd.play(
                audio,
                samplerate=self.config.sample_rate,
                device=self.config.device
            )
            if blocking:
                sd.wait()
            self._state = AudioState.IDLE
            return True
        except Exception as e:
            print(f"Playback failed: {e}")
            self._state = AudioState.IDLE
            return False

    def start_stream(
        self,
        callback: Callable[[np.ndarray], None]
    ) -> bool:
        """
        Start a continuous audio stream with callback.

        Args:
            callback: Function called with each audio chunk

        Returns:
            True if stream started successfully
        """
        if not SOUNDDEVICE_AVAILABLE:
            return False

        if self._state != AudioState.IDLE:
            return False

        self._callback = callback
        self._stop_event.clear()

        def stream_callback(indata, frames, time, status):
            if status:
                print(f"Stream status: {status}")
            callback(indata.copy())

        try:
            self._stream = sd.InputStream(
                samplerate=self.config.sample_rate,
                channels=self.config.channels,
                dtype=self.config.dtype,
                blocksize=self.config.blocksize,
                device=self.config.device,
                callback=stream_callback
            )
            self._stream.start()
            self._state = AudioState.STREAMING
            return True
        except Exception as e:
            print(f"Failed to start stream: {e}")
            return False

    def stop_stream(self) -> None:
        """Stop the audio stream."""
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        self._callback = None
        self._state = AudioState.IDLE

    def analyze_audio(self, audio: np.ndarray) -> AudioAnalysis:
        """
        Analyze audio data.

        Args:
            audio: Audio data as numpy array

        Returns:
            AudioAnalysis with volume, frequency, etc.
        """
        # Ensure 1D array
        if audio.ndim > 1:
            audio = audio.flatten()

        # Calculate RMS volume
        rms = np.sqrt(np.mean(audio ** 2))

        # Calculate peak volume
        peak = np.max(np.abs(audio))

        # Check for silence
        is_silent = rms < self.SILENCE_THRESHOLD

        # Calculate dominant frequency using FFT
        dominant_freq = None
        if not is_silent:
            dominant_freq = self._get_dominant_frequency(audio)

        # Calculate duration (with zero check for sample_rate)
        sample_rate = self.config.sample_rate
        duration = len(audio) / sample_rate if sample_rate > 0 else 0.0

        return AudioAnalysis(
            rms_volume=float(rms),
            peak_volume=float(peak),
            dominant_frequency=dominant_freq,
            is_silent=is_silent,
            duration=duration
        )

    def _get_dominant_frequency(self, audio: np.ndarray) -> Optional[float]:
        """Calculate the dominant frequency using FFT."""
        try:
            # Apply FFT
            fft = np.fft.fft(audio)
            freqs = np.fft.fftfreq(len(audio), 1 / self.config.sample_rate)

            # Get magnitude of positive frequencies
            positive_mask = freqs > 0
            magnitudes = np.abs(fft[positive_mask])
            positive_freqs = freqs[positive_mask]

            # Find dominant frequency
            if len(magnitudes) > 0:
                dominant_idx = np.argmax(magnitudes)
                return float(positive_freqs[dominant_idx])

            return None
        except Exception:
            return None

    def get_volume_level(self, audio: np.ndarray) -> float:
        """
        Get volume level as a simple 0-1 value.

        Args:
            audio: Audio data

        Returns:
            Volume level (0-1)
        """
        if audio.ndim > 1:
            audio = audio.flatten()

        rms = np.sqrt(np.mean(audio ** 2))
        # Normalize to 0-1 range (assuming typical audio levels)
        return min(1.0, rms * 10)

    def detect_clap(
        self,
        audio: np.ndarray,
        threshold: float = 0.3,
        min_duration: float = 0.01,
        max_duration: float = 0.1
    ) -> bool:
        """
        Simple clap detection based on sudden volume spike.

        Args:
            audio: Audio data
            threshold: Volume threshold for clap detection
            min_duration: Minimum clap duration in seconds
            max_duration: Maximum clap duration in seconds

        Returns:
            True if clap detected
        """
        analysis = self.analyze_audio(audio)

        # Check for sudden loud sound
        if analysis.peak_volume < threshold:
            return False

        # Check duration is clap-like
        if analysis.duration < min_duration or analysis.duration > max_duration:
            return False

        return True

    def cleanup(self) -> None:
        """Release all resources."""
        self.stop_stream()
        self.stop_recording()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.cleanup()
        return False
