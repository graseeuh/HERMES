"""Local video/audio transcription for HERMES.

Standalone package: transcribes media to text with faster-whisper and caches
results to disk. Independent of the three oversight layers (Approval Gate,
Security Gate, Inspector General) — no imports to or from them.
"""

from .transcriber import VideoTranscriber, TranscriptionError
from .frames import FrameExtractor, FrameExtractionError

__all__ = [
    "VideoTranscriber",
    "TranscriptionError",
    "FrameExtractor",
    "FrameExtractionError",
]
