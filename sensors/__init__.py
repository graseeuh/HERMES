# HERMES Sensors Module
# Wrappers for MediaPipe, OpenCV, audio, and voice interfaces

from .vision_interface import VisionInterface
from .audio_interface import AudioInterface
from .voice_interface import VoiceInterface, VoiceCommand, RecognitionBackend
from .face_recognition_interface import FaceRecognitionInterface
from .tts_interface import TTSInterface, TTSConfig
from .whisper_recognizer import WhisperRecognizer, WhisperConfig, WHISPER_AVAILABLE

__all__ = [
    'VisionInterface',
    'AudioInterface',
    'VoiceInterface',
    'VoiceCommand',
    'RecognitionBackend',
    'FaceRecognitionInterface',
    'TTSInterface',
    'TTSConfig',
    'WhisperRecognizer',
    'WhisperConfig',
    'WHISPER_AVAILABLE'
]
