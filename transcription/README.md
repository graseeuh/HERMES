# HERMES Video Comprehension

Local, free, offline video and audio understanding for HERMES. HERMES can now
both **hear** a video (audio to text) and **see** a video (sampled frames),
then answer questions about it. No cloud, no API keys. Everything runs on this
machine.

Last worked on: 2026-06-14. Status below reflects that session.

## Status: working and tested

| Capability | State |
|------------|-------|
| Audio transcription (Whisper, local) | Done, tested end to end |
| Transcript caching + search | Done, tested |
| Frame extraction (PyAV, local) | Done, tested (frames verified viewable) |
| Combined "watch" (frames + transcript) | Done |
| Remote URL ingestion (YouTube, Loom, etc.) | NOT built (see Pending) |

## MCP tools (in `mcp_server.py`)

1. `hermes_transcribe_video(media_path, model_size="base", language=None, force=False)`
   Transcribes a local video or audio file to timestamped text. Caches the
   result. After calling, read the returned `text` to extract subject/summary.
2. `hermes_list_transcripts()`
   Lists cached transcripts (metadata only).
3. `hermes_get_transcript(key, query=None, window=1)`
   Retrieves a cached transcript by fingerprint or file name. With a `query`,
   returns only matching timestamped segments (Q&A / search).
4. `hermes_extract_frames(media_path, start=None, end=None, max_frames=None, resolution=512, force=False)`
   Samples JPEG frames at duration scaled intervals. Returns frame paths +
   timestamps. Read each path to SEE what is on screen.
5. `hermes_watch_video(media_path, start=None, end=None, max_frames=None, resolution=512, model_size="base", language=None)`
   The headline tool. Extracts frames AND transcribes audio in one call so you
   can see and hear, then answer questions.

## Files

- `transcription/transcriber.py` ... `VideoTranscriber` (faster-whisper wrapper, caching, search)
- `transcription/frames.py` ........ `FrameExtractor` (PyAV frame sampling, Pillow JPEG)
- `transcription/__init__.py` ...... exports both classes
- `mcp_server.py` .................. 5 MCP tools wired in (lazy singletons)
- `.gitignore` .................... ignores `transcription/cache/` and `transcription/frames/`

## How it works

- **Transcription**: faster-whisper runs a Whisper model on the CPU (int8). Audio
  is decoded straight from the video container by PyAV, so no separate ffmpeg
  binary is needed. Results cache to `transcription/cache/<fingerprint>.json`
  keyed by file path + size + mtime, so repeat queries never re-transcribe.
- **Frames**: PyAV seeks to evenly spaced timestamps, decodes forward to the
  target time (so frames are not duplicated per keyframe group), resizes with
  Pillow, and writes JPEGs to `transcription/frames/<fingerprint>/`. Frame count
  scales with duration (30 for short clips up to a 100 frame ceiling, 2 fps cap).

## Dependencies (already installed in venv)

- `faster-whisper` (pulls in `ctranslate2`, `av`, `onnxruntime`, `tokenizers`, `huggingface-hub`)
- `Pillow` (was already present)

These are NOT yet in `requirements.txt` (see Pending).

## How to use

1. Restart the HERMES MCP server so it registers the new tools:
   `venv/Scripts/python.exe main.py --mcp`
2. Ask, for example: "Watch `C:\path\to\demo.mp4` and tell me what is shown and said."
3. First real video triggers a one time Whisper model download (~145MB for
   `base`). Cached by faster-whisper after that.

Supported local formats: mp4, mkv, mov, avi, webm, m4v, wmv, mpg, mpeg (video);
mp3, wav, m4a, aac, flac, ogg, opus, wma (audio only, transcription).

Tip: bump `model_size` to `small` or `medium` for noisy or accented audio.
`base` was accurate in testing.

## Pending (pick back up here)

1. **Remote URL ingestion**: add `yt-dlp` so a YouTube / TikTok / Loom URL can be
   pointed at directly, not just local files. This is the only capability
   `claude-video` has that HERMES does not. Plan: download to a temp dir with
   `yt-dlp`, then feed the local file into the existing tools.
2. **`requirements.txt`**: add `faster-whisper` and `Pillow`.
3. **`CLAUDE.md`**: note the new `transcription/` package and its tools under
   architecture, and add a line to the test section if tests get written.
4. (Optional) Unit tests for `VideoTranscriber` and `FrameExtractor`.

## Why this design over alternatives

We compared against `github.com/bradautomates/claude-video`. That project also
sees and hears, but uses cloud Whisper (Groq/OpenAI), `yt-dlp`, and an external
ffmpeg binary, and it does not cache. HERMES does the same see + hear locally,
free, offline, with caching and search. The deliberate gap is remote URLs,
listed in Pending above.
