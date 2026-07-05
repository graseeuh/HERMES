"""Local video/audio transcription using faster-whisper.

No cloud calls, no API keys. The Whisper model is downloaded once from
Hugging Face on first use and cached by faster-whisper itself. Transcripts are
cached to ``transcription/cache`` keyed by a hash of the source file so repeat
queries (subject extraction, Q&A, search) never re-transcribe.
"""

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Video/audio container extensions PyAV can decode.
MEDIA_EXTENSIONS = {
    ".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".m4v", ".wmv", ".mpg", ".mpeg",
    ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wma",
}

VALID_MODEL_SIZES = {"tiny", "base", "small", "medium", "large-v3", "large-v3-turbo"}

_CACHE_DIR = Path(__file__).parent / "cache"


class TranscriptionError(Exception):
    """Raised when a media file cannot be transcribed."""


class VideoTranscriber:
    """Transcribe video/audio to timestamped text, with on-disk caching."""

    def __init__(self, model_size: str = "base", cache_dir: Optional[Path] = None):
        if model_size not in VALID_MODEL_SIZES:
            raise TranscriptionError(
                f"model_size must be one of {sorted(VALID_MODEL_SIZES)}, got {model_size!r}"
            )
        self.model_size = model_size
        self.cache_dir = Path(cache_dir) if cache_dir else _CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._model = None  # lazy — loading a model is expensive

    # -- model -------------------------------------------------------------
    def _load_model(self):
        if self._model is None:
            from faster_whisper import WhisperModel

            # int8 on CPU is the fast/low-memory default; falls back cleanly
            # if no GPU is present.
            self._model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
        return self._model

    # -- cache keys --------------------------------------------------------
    @staticmethod
    def _file_fingerprint(path: Path) -> str:
        """Hash of path + size + mtime — cheap and stable per file version."""
        stat = path.stat()
        raw = f"{path.resolve()}|{stat.st_size}|{int(stat.st_mtime)}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def _cache_path(self, fingerprint: str) -> Path:
        return self.cache_dir / f"{fingerprint}.json"

    # -- public API --------------------------------------------------------
    def transcribe(self, media_path: str, language: Optional[str] = None,
                   force: bool = False) -> dict:
        """Transcribe a media file, using the cache unless ``force`` is set.

        Returns a dict with: name, path, language, duration, text, segments
        (each {start, end, text}), word_count, model_size, cached.
        """
        path = Path(media_path)
        if not path.exists():
            raise TranscriptionError(f"File not found: {media_path}")
        if not path.is_file():
            raise TranscriptionError(f"Not a file: {media_path}")
        if path.suffix.lower() not in MEDIA_EXTENSIONS:
            raise TranscriptionError(
                f"Unsupported extension {path.suffix!r}. "
                f"Supported: {sorted(MEDIA_EXTENSIONS)}"
            )

        fingerprint = self._file_fingerprint(path)
        cache_file = self._cache_path(fingerprint)

        if cache_file.exists() and not force:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            data["cached"] = True
            return data

        model = self._load_model()
        segments_iter, info = model.transcribe(
            str(path), language=language, vad_filter=True,
        )

        segments = []
        text_parts = []
        for seg in segments_iter:  # generator — transcription happens here
            chunk = seg.text.strip()
            segments.append({"start": round(seg.start, 2),
                             "end": round(seg.end, 2),
                             "text": chunk})
            text_parts.append(chunk)

        full_text = " ".join(text_parts).strip()
        data = {
            "name": path.name,
            "path": str(path.resolve()),
            "fingerprint": fingerprint,
            "language": info.language,
            "language_probability": round(info.language_probability, 3),
            "duration": round(info.duration, 2),
            "model_size": self.model_size,
            "transcribed_at": datetime.now(timezone.utc).isoformat(),
            "word_count": len(full_text.split()),
            "segment_count": len(segments),
            "text": full_text,
            "segments": segments,
        }

        # Atomic write (Windows-safe per project convention).
        tmp = cache_file.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, cache_file)

        data["cached"] = False
        return data

    def list_cached(self) -> list:
        """List cached transcripts (metadata only, no full text)."""
        out = []
        for f in sorted(self.cache_dir.glob("*.json")):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            out.append({
                "fingerprint": d.get("fingerprint", f.stem),
                "name": d.get("name"),
                "duration": d.get("duration"),
                "language": d.get("language"),
                "word_count": d.get("word_count"),
                "transcribed_at": d.get("transcribed_at"),
            })
        return out

    def get_cached(self, key: str) -> Optional[dict]:
        """Retrieve a cached transcript by fingerprint or file name."""
        by_fp = self._cache_path(key)
        if by_fp.exists():
            return json.loads(by_fp.read_text(encoding="utf-8"))
        for f in self.cache_dir.glob("*.json"):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if d.get("name") == key:
                return d
        return None

    def search(self, key: str, query: str, window: int = 0) -> list:
        """Return matching segments from a cached transcript.

        Case-insensitive substring match on segment text. ``window`` includes
        N neighbouring segments on each side for context.
        """
        data = self.get_cached(key)
        if data is None:
            raise TranscriptionError(f"No cached transcript for {key!r}")
        segments = data.get("segments", [])
        q = query.lower()
        hits = []
        for i, seg in enumerate(segments):
            if q in seg["text"].lower():
                lo = max(0, i - window)
                hi = min(len(segments), i + window + 1)
                hits.append({
                    "match_index": i,
                    "start": seg["start"],
                    "end": seg["end"],
                    "context": " ".join(s["text"] for s in segments[lo:hi]),
                })
        return hits
