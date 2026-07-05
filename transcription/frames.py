"""Local video frame extraction using PyAV (no cloud, no ffmpeg binary).

Samples frames from a video and writes them as JPEGs so a multimodal model can
*see* what is on screen. Frame count is scaled to video duration to keep the
visual budget sane, mirroring a sensible "watch the video" strategy.
"""

import hashlib
import shutil
from pathlib import Path
from typing import Optional

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".m4v", ".wmv",
                    ".mpg", ".mpeg"}

_FRAMES_DIR = Path(__file__).parent / "frames"

# Hard ceilings (match a "watch any video" budget).
MAX_FRAMES_CEILING = 100
MAX_FPS = 2.0


class FrameExtractionError(Exception):
    """Raised when frames cannot be extracted from a video."""


def _budget_for_duration(seconds: float) -> int:
    """Duration-scaled default frame count."""
    if seconds <= 30:
        return 30
    if seconds <= 60:
        return 40
    if seconds <= 180:
        return 60
    if seconds <= 600:
        return 80
    return MAX_FRAMES_CEILING


class FrameExtractor:
    """Sample JPEG frames from a video at duration-scaled intervals."""

    def __init__(self, frames_dir: Optional[Path] = None):
        self.frames_dir = Path(frames_dir) if frames_dir else _FRAMES_DIR
        self.frames_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _fingerprint(path: Path, start, end, resolution, max_frames) -> str:
        stat = path.stat()
        raw = f"{path.resolve()}|{stat.st_size}|{int(stat.st_mtime)}|{start}|{end}|{resolution}|{max_frames}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def extract(self, media_path: str, start: Optional[float] = None,
                end: Optional[float] = None, max_frames: Optional[int] = None,
                resolution: int = 512, force: bool = False) -> dict:
        """Extract frames and return their paths + timestamps.

        Args:
            media_path: Path to a local video file.
            start, end: Optional clip window in seconds.
            max_frames: Override the duration-scaled default (capped at 100).
            resolution: JPEG width in px (height keeps aspect). Default 512.
            force:      Re-extract even if a frame set already exists.
        """
        import av

        path = Path(media_path)
        if not path.exists() or not path.is_file():
            raise FrameExtractionError(f"File not found: {media_path}")
        if path.suffix.lower() not in VIDEO_EXTENSIONS:
            raise FrameExtractionError(
                f"Unsupported video extension {path.suffix!r}. "
                f"Supported: {sorted(VIDEO_EXTENSIONS)}"
            )

        fingerprint = self._fingerprint(path, start, end, resolution, max_frames)
        out_dir = self.frames_dir / fingerprint

        if out_dir.exists() and not force:
            existing = sorted(out_dir.glob("frame_*.jpg"))
            if existing:
                manifest = (out_dir / "manifest.txt")
                ts = _read_manifest(manifest, existing)
                return {
                    "name": path.name, "fingerprint": fingerprint,
                    "frame_dir": str(out_dir), "frame_count": len(existing),
                    "resolution": resolution, "cached": True,
                    "frames": [{"index": i, "timestamp": ts[i], "path": str(p)}
                               for i, p in enumerate(existing)],
                }

        if out_dir.exists():
            shutil.rmtree(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        try:
            container = av.open(str(path))
        except Exception as exc:  # PyAV raises various decode errors
            raise FrameExtractionError(f"Could not open video: {exc}") from exc

        try:
            if not container.streams.video:
                raise FrameExtractionError("File has no video stream (audio-only?).")
            stream = container.streams.video[0]
            stream.thread_type = "AUTO"

            duration = float(container.duration / av.time_base) if container.duration else 0.0
            if duration <= 0 and stream.duration and stream.time_base:
                duration = float(stream.duration * stream.time_base)
            if duration <= 0:
                duration = (end or 0) or 1.0

            win_start = max(0.0, start) if start else 0.0
            win_end = min(end, duration) if end else duration
            if win_end <= win_start:
                win_end = duration
            window = max(win_end - win_start, 0.001)

            budget = max_frames or _budget_for_duration(window)
            budget = min(budget, MAX_FRAMES_CEILING)
            # Respect the fps ceiling.
            budget = min(budget, max(1, int(window * MAX_FPS)))

            targets = [win_start + (window * (i + 0.5) / budget) for i in range(budget)]

            frames_meta = []
            time_base = stream.time_base
            for idx, t in enumerate(targets):
                seek_ts = int(t / time_base)
                container.seek(seek_ts, stream=stream, backward=True, any_frame=False)
                # Seek lands on the nearest keyframe <= t; decode forward until
                # we reach the target time so frames aren't duplicated per GOP.
                grabbed = None
                for frame in container.decode(stream):
                    grabbed = frame
                    if frame.time is not None and frame.time >= t:
                        break
                if grabbed is None:
                    continue
                img = grabbed.to_image()
                if img.width > resolution:
                    h = int(img.height * (resolution / img.width))
                    img = img.resize((resolution, h))
                fp = out_dir / f"frame_{idx:03d}.jpg"
                img.save(fp, "JPEG", quality=80)
                actual_t = round(float(grabbed.pts * time_base), 2) if grabbed.pts is not None else round(t, 2)
                frames_meta.append({"index": idx, "timestamp": actual_t, "path": str(fp)})
        finally:
            container.close()

        if not frames_meta:
            raise FrameExtractionError("No frames could be decoded from the video.")

        # Manifest maps frame file -> timestamp for cached reloads.
        (out_dir / "manifest.txt").write_text(
            "\n".join(f"{Path(m['path']).name}\t{m['timestamp']}" for m in frames_meta),
            encoding="utf-8",
        )

        return {
            "name": path.name, "fingerprint": fingerprint,
            "frame_dir": str(out_dir), "frame_count": len(frames_meta),
            "resolution": resolution, "cached": False, "frames": frames_meta,
        }


def _read_manifest(manifest: Path, existing) -> list:
    """Return timestamps aligned to ``existing`` frame files."""
    mapping = {}
    if manifest.exists():
        for line in manifest.read_text(encoding="utf-8").splitlines():
            if "\t" in line:
                name, ts = line.split("\t", 1)
                try:
                    mapping[name] = float(ts)
                except ValueError:
                    mapping[name] = None
    return [mapping.get(p.name) for p in existing]
