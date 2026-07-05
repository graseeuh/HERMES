"""
HERMES MCP Server
Exposes HERMES orchestration capabilities as MCP tools and resources
for Claude Code integration over stdio.
"""

import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Optional

_GITHUB_REPO_RE = re.compile(r"^[A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+$")
_GITHUB_PATH_RE = re.compile(r"^[A-Za-z0-9_.\-/]+$")
_GITHUB_REF_RE = re.compile(r"^[A-Za-z0-9_.\-/]+$")

from mcp.server.fastmcp import FastMCP

# Configure logging to stderr (stdout is reserved for MCP JSON-RPC)
logging.basicConfig(
    level=logging.INFO,
    format="[HERMES] %(levelname)s %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("hermes.mcp")

# ---------------------------------------------------------------------------
# Lazy-initialized orchestrator singleton
# ---------------------------------------------------------------------------
_orchestrator = None
_inspector = None
_approval_gate = None
_github_scanner = None


def get_orchestrator():
    """Lazy-initialize and return the Orchestrator singleton."""
    global _orchestrator
    if _orchestrator is None:
        from core_logic.orchestrator import Orchestrator

        kb_path = str(Path(__file__).parent / "knowledge_base")
        _orchestrator = Orchestrator(knowledge_base_path=kb_path)
        logger.info("Orchestrator initialized (kb=%s)", kb_path)
    return _orchestrator


def get_inspector():
    """Lazy-initialize and return the InspectorGeneral singleton."""
    global _inspector
    if _inspector is None:
        from inspector import InspectorGeneral

        base_path = str(Path(__file__).parent)
        _inspector = InspectorGeneral(base_path=base_path)
        logger.info("InspectorGeneral initialized (base=%s)", base_path)
    return _inspector


def get_approval_gate():
    """Lazy-initialize and return the ApprovalGate singleton."""
    global _approval_gate
    if _approval_gate is None:
        from approval import ApprovalGate

        base_path = str(Path(__file__).parent)
        _approval_gate = ApprovalGate(base_path=base_path)
        logger.info("ApprovalGate initialized (base=%s)", base_path)
    return _approval_gate


def get_github_scanner():
    """Lazy-initialize and return the GitHubScanner singleton."""
    global _github_scanner
    if _github_scanner is None:
        from security import GitHubScanner

        base_path = str(Path(__file__).parent)
        _github_scanner = GitHubScanner(base_path=base_path)
        logger.info("GitHubScanner initialized (base=%s)", base_path)
    return _github_scanner


# ---------------------------------------------------------------------------
# FastMCP server
# ---------------------------------------------------------------------------
mcp = FastMCP(
    "hermes",
    instructions=(
        "HERMES - Hierarchical Executable Reasoning and Management Execution System. "
        "Orchestrates specialized agents for code, research, vision, audio, KiCad, "
        "and TouchDesigner tasks."
    ),
)


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------
@mcp.tool()
def hermes_execute(task: str) -> str:
    """Execute a natural-language task through the HERMES orchestrator.

    HERMES parses the task, selects or spawns the right agents, and returns
    aggregated results.  Use this for any multi-step or specialist task:
    code generation, research, PCB design, TouchDesigner projects, etc.

    Args:
        task: Natural-language description of what to do.
    """
    logger.info("hermes_execute called: %s", task[:120])
    try:
        # --- Approval gate ---
        gate = get_approval_gate()
        gate.cleanup_expired()
        matched = gate.requires_approval(task)
        if matched:
            approval = gate.create_request(task, matched)
            logger.info(
                "Approval required: request_id=%s patterns=%s",
                approval.request_id,
                matched,
            )
            return json.dumps(
                {
                    "status": "approval_required",
                    "request_id": approval.request_id,
                    "message": (
                        "This task requires your approval before execution. "
                        "Call hermes_approve() to proceed or deny."
                    ),
                    "task_preview": task[:200],
                    "matched_patterns": matched,
                    "expires_at": approval.expires_at,
                },
                indent=2,
            )
        # ---------------------

        orch = get_orchestrator()
        result = orch.process_and_execute(task)

        # --- Inspector General boundary ---
        # Independent auditor at the MCP boundary.
        # The orchestrator cannot call, bypass, or write to the Inspector.
        inspector = get_inspector()
        verdict = inspector.inspect(result, raw_input=task)
        logger.info(
            "Inspector verdict: passed=%s flags=%s confidence=%.2f",
            verdict.passed,
            verdict.flags,
            verdict.confidence,
        )
        # ----------------------------------

        return json.dumps(
            {
                "status": result.status.value,
                "summary": result.summary,
                "results": _safe_serialise(result.results),
                "errors": result.errors,
                "agents_used": result.agents_used,
                "execution_time": result.execution_time,
                "inspector": {
                    "passed": verdict.passed,
                    "flags": verdict.flags,
                    "warnings": verdict.warnings,
                    "confidence": verdict.confidence,
                    "checks_run": verdict.checks_run,
                    "session_id": verdict.session_id,
                    "degraded": verdict.degraded,
                    "behavioral_summary": verdict.behavioral_summary,
                },
            },
            indent=2,
        )
    except Exception as exc:
        logger.exception("hermes_execute failed")
        return json.dumps({"status": "error", "error": str(exc)})


@mcp.tool()
def hermes_approve(request_id: str, approved: bool, reason: str = "") -> str:
    """Approve or deny a pending HERMES task that requires confirmation.

    When hermes_execute returns status='approval_required', use this tool to
    approve (which triggers full execution and returns the result) or deny
    (which cancels the task with no side effects).

    Args:
        request_id: The request_id returned by hermes_execute.
        approved:   True to approve and execute, False to deny.
        reason:     Optional reason for the decision.
    """
    logger.info(
        "hermes_approve called: request_id=%s approved=%s reason=%.80s",
        request_id,
        approved,
        reason,
    )
    try:
        gate = get_approval_gate()
        gate.cleanup_expired()

        approval = gate.get_request(request_id)
        if approval is None:
            return json.dumps(
                {"status": "error", "error": f"No approval request found with id={request_id!r}"}
            )
        if approval.status != "pending":
            return json.dumps(
                {
                    "status": "error",
                    "error": (
                        f"Request {request_id!r} is not pending "
                        f"(current status: {approval.status!r}). "
                        "It may have already been resolved or expired."
                    ),
                }
            )

        gate.resolve(request_id, approved, reason)

        if not approved:
            logger.info("Task denied: request_id=%s", request_id)
            return json.dumps(
                {
                    "status": "denied",
                    "request_id": request_id,
                    "message": "Task was denied. No actions were taken.",
                    "reason": reason,
                    "task_preview": approval.task[:200],
                },
                indent=2,
            )

        # Approved — execute
        logger.info("Task approved, executing: request_id=%s task=%.80s", request_id, approval.task)
        orch = get_orchestrator()
        result = orch.process_and_execute(approval.task)

        inspector = get_inspector()
        verdict = inspector.inspect(result, raw_input=approval.task)
        logger.info(
            "Inspector verdict (approved task): passed=%s flags=%s confidence=%.2f",
            verdict.passed,
            verdict.flags,
            verdict.confidence,
        )

        return json.dumps(
            {
                "status": result.status.value,
                "approved_by_user": True,
                "request_id": request_id,
                "approval_reason": reason,
                "summary": result.summary,
                "results": _safe_serialise(result.results),
                "errors": result.errors,
                "agents_used": result.agents_used,
                "execution_time": result.execution_time,
                "inspector": {
                    "passed": verdict.passed,
                    "flags": verdict.flags,
                    "warnings": verdict.warnings,
                    "confidence": verdict.confidence,
                    "checks_run": verdict.checks_run,
                    "session_id": verdict.session_id,
                    "degraded": verdict.degraded,
                    "behavioral_summary": verdict.behavioral_summary,
                },
            },
            indent=2,
        )
    except Exception as exc:
        logger.exception("hermes_approve failed")
        return json.dumps({"status": "error", "error": str(exc)})


@mcp.tool()
def hermes_list_pending() -> str:
    """List all HERMES approval requests currently waiting for user confirmation.

    Use this to see what tasks are pending before calling hermes_approve().
    Returns requests sorted oldest-first. Expired requests are cleaned up first.
    """
    logger.info("hermes_list_pending called")
    try:
        gate = get_approval_gate()
        gate.cleanup_expired()
        pending = gate.list_pending()

        return json.dumps(
            {
                "status": "ok",
                "pending_count": len(pending),
                "pending_requests": [
                    {
                        "request_id": a.request_id,
                        "task_preview": a.task[:200],
                        "matched_patterns": a.matched_patterns,
                        "created_at": a.created_at,
                        "expires_at": a.expires_at,
                    }
                    for a in pending
                ],
            },
            indent=2,
        )
    except Exception as exc:
        logger.exception("hermes_list_pending failed")
        return json.dumps({"status": "error", "error": str(exc)})


@mcp.tool()
def hermes_fetch_github(repo: str, path: str, ref: str = "main") -> str:
    """Fetch a file from GitHub with mandatory 4-layer malicious content scanning.

    Scans for: obfuscated code, eval/exec injections, encoded payloads, reverse
    shells, crypto miners, supply-chain hooks, typosquatted dependencies,
    hardcoded credentials, null bytes, long lines, and high-entropy strings.

    CLEAN files: content is returned.
    SUSPICIOUS or MALICIOUS files: quarantined to disk, content withheld.

    Args:
        repo: GitHub repository in "owner/name" format (e.g. "psf/requests").
        path: File path within the repo (e.g. "requests/api.py").
        ref:  Branch, tag, or commit SHA (default: "main").
    """
    logger.info("hermes_fetch_github called: repo=%s path=%s ref=%s", repo, path, ref)
    try:
        # Strict input validation to prevent URL manipulation / SSRF
        if not _GITHUB_REPO_RE.match(repo):
            return json.dumps({"status": "error", "error": "repo must be in 'owner/name' format (alphanumeric, hyphens, dots, underscores only)"})
        if ".." in path or not _GITHUB_PATH_RE.match(path):
            return json.dumps({"status": "error", "error": "path contains invalid characters"})
        if not _GITHUB_REF_RE.match(ref):
            return json.dumps({"status": "error", "error": "ref contains invalid characters"})

        scanner = get_github_scanner()
        # Optionally pass a GitHub token from environment (never log it)
        github_token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        result = scanner.fetch_and_scan(repo=repo, path=path, ref=ref, github_token=github_token)

        response = {
            "classification": result.classification,
            "repo": result.repo,
            "path": result.path,
            "ref": result.ref,
            "fetched_at": result.fetched_at,
            "file_size": result.file_size,
            "layers_run": result.layers_run,
            "findings_count": len(result.findings),
            "findings": [
                {
                    "layer": f.layer,
                    "severity": f.severity,
                    "title": f.title,
                    "description": f.description,
                    "line_number": f.line_number,
                    "snippet": f.snippet,
                }
                for f in result.findings
            ],
        }

        if result.classification == "CLEAN":
            response["content"] = result.content
            response["message"] = "File passed all security scans."
        else:
            response["content"] = None
            response["quarantine_path"] = Path(result.quarantine_path).name if result.quarantine_path else None
            response["message"] = (
                f"File classified as {result.classification}. "
                "Content has been quarantined and is not available. "
                "Review findings before proceeding."
            )

        return json.dumps(response, indent=2)

    except Exception as exc:
        logger.exception("hermes_fetch_github failed")
        return json.dumps({"status": "error", "error": str(exc)})


@mcp.tool()
def hermes_status() -> str:
    """Return the current HERMES orchestrator status.

    Includes registry statistics (agent counts by state), loaded templates,
    and executor availability.
    """
    logger.info("hermes_status called")
    try:
        orch = get_orchestrator()
        status = orch.get_status()
        status["executor_available"] = orch.executor is not None
        return json.dumps(_safe_serialise(status), indent=2)
    except Exception as exc:
        logger.exception("hermes_status failed")
        return json.dumps({"status": "error", "error": str(exc)})


@mcp.tool()
def hermes_query_agents(
    status_filter: Optional[str] = None,
    task_type_filter: Optional[str] = None,
) -> str:
    """Query the HERMES agent registry.

    Returns a JSON list of agents, optionally filtered by status or task type.

    Args:
        status_filter:    Filter by agent status (idle, running, completed, failed, buffered).
        task_type_filter: Filter by task type (code, research, vision, audio, kicad, touchdesigner, plan, custom).
    """
    logger.info(
        "hermes_query_agents called (status=%s, type=%s)",
        status_filter,
        task_type_filter,
    )
    try:
        orch = get_orchestrator()
        agents = orch.registry.get_all_agents()

        # Apply filters
        if status_filter:
            agents = [a for a in agents if a.status.value == status_filter]
        if task_type_filter:
            from core_logic.task_parser import TaskType

            try:
                tt = TaskType(task_type_filter)
                agents = [a for a in agents if tt in a.capability.task_types]
            except ValueError:
                return json.dumps(
                    {"error": f"Unknown task type: {task_type_filter}"}
                )

        result = [
            {
                "id": a.agent_id,
                "name": a.name,
                "status": a.status.value,
                "workload": a.workload,
                "specializations": a.capability.specializations,
            }
            for a in agents
        ]
        return json.dumps(result, indent=2)
    except Exception as exc:
        logger.exception("hermes_query_agents failed")
        return json.dumps({"status": "error", "error": str(exc)})


@mcp.tool()
def hermes_inspector_report(days: int = 7) -> str:
    """Return Inspector General behavioral statistics and recent audit log entries.

    The Inspector General is an independent auditor at the MCP boundary that
    the orchestrator cannot bypass or write to. This tool queries its own
    separate audit log to report on orchestrator behavioral patterns,
    flag rates, and any detected anomalies.

    Args:
        days: Number of days to look back in the audit log (1–30, default: 7).
    """
    logger.info("hermes_inspector_report called (days=%d)", days)
    try:
        days = max(1, min(days, 30))
        inspector = get_inspector()
        report = inspector.get_behavioral_report(days=days)
        recent_log = inspector.get_recent_log_entries(days=days, limit=50)
        return json.dumps(
            {
                "behavioral_report": report,
                "recent_log_entries": recent_log,
                "log_entries_returned": len(recent_log),
                "days_queried": days,
            },
            indent=2,
        )
    except Exception as exc:
        logger.exception("hermes_inspector_report failed")
        return json.dumps({"status": "error", "error": str(exc)})


# ---------------------------------------------------------------------------
# Video / audio transcription (local, free — faster-whisper)
# ---------------------------------------------------------------------------
_transcribers = {}


def get_transcriber(model_size: str = "base"):
    """Lazy-initialize and cache a VideoTranscriber per model size."""
    if model_size not in _transcribers:
        from transcription import VideoTranscriber

        _transcribers[model_size] = VideoTranscriber(model_size=model_size)
        logger.info("VideoTranscriber initialized (model=%s)", model_size)
    return _transcribers[model_size]


@mcp.tool()
def hermes_transcribe_video(
    media_path: str,
    model_size: str = "base",
    language: Optional[str] = None,
    force: bool = False,
) -> str:
    """Transcribe a local video or audio file to text, fully offline.

    Uses faster-whisper locally (no cloud, no API key). The first run downloads
    the Whisper model once; results are cached on disk so repeat calls on the
    same file are instant. After calling this, read the returned transcript to
    extract the subject, summarize, or answer questions about the video.

    Args:
        media_path: Absolute path to a video/audio file (mp4, mkv, mov, mp3, wav, ...).
        model_size: tiny | base | small | medium | large-v3 | large-v3-turbo.
                    Larger = more accurate but slower. Default 'base'.
        language:   ISO code (e.g. 'en') to skip auto-detection. Optional.
        force:      Re-transcribe even if a cached result exists.
    """
    logger.info("hermes_transcribe_video called: %s (model=%s)", media_path, model_size)
    try:
        from transcription import TranscriptionError

        try:
            transcriber = get_transcriber(model_size)
        except TranscriptionError as exc:
            return json.dumps({"status": "error", "error": str(exc)})

        try:
            data = transcriber.transcribe(media_path, language=language, force=force)
        except TranscriptionError as exc:
            return json.dumps({"status": "error", "error": str(exc)})

        return json.dumps({"status": "ok", **data}, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.exception("hermes_transcribe_video failed")
        return json.dumps({"status": "error", "error": str(exc)})


@mcp.tool()
def hermes_list_transcripts() -> str:
    """List all cached video/audio transcripts (metadata only, no full text).

    Use this to see what has already been transcribed before re-running, or to
    find the fingerprint/name to pass to hermes_get_transcript.
    """
    logger.info("hermes_list_transcripts called")
    try:
        transcriber = get_transcriber()
        items = transcriber.list_cached()
        return json.dumps({"status": "ok", "count": len(items), "transcripts": items},
                          ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.exception("hermes_list_transcripts failed")
        return json.dumps({"status": "error", "error": str(exc)})


@mcp.tool()
def hermes_get_transcript(key: str, query: Optional[str] = None, window: int = 1) -> str:
    """Retrieve a cached transcript for follow-up Q&A and search.

    Pass a fingerprint or file name (from hermes_list_transcripts). Without a
    query, returns the full cached transcript so you can answer questions about
    it. With a query, returns only the matching timestamped segments.

    Args:
        key:    Transcript fingerprint or original file name.
        query:  Optional substring to search for within the transcript.
        window: Neighbouring segments of context to include per match (default 1).
    """
    logger.info("hermes_get_transcript called: key=%s query=%s", key, query)
    try:
        from transcription import TranscriptionError

        transcriber = get_transcriber()
        if query:
            try:
                hits = transcriber.search(key, query, window=window)
            except TranscriptionError as exc:
                return json.dumps({"status": "error", "error": str(exc)})
            return json.dumps(
                {"status": "ok", "key": key, "query": query,
                 "match_count": len(hits), "matches": hits},
                ensure_ascii=False, indent=2,
            )

        data = transcriber.get_cached(key)
        if data is None:
            return json.dumps({"status": "error",
                               "error": f"No cached transcript for {key!r}. "
                                        "Call hermes_list_transcripts to see available ones."})
        return json.dumps({"status": "ok", **data}, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.exception("hermes_get_transcript failed")
        return json.dumps({"status": "error", "error": str(exc)})


_frame_extractor = None


def get_frame_extractor():
    """Lazy-initialize and return the FrameExtractor singleton."""
    global _frame_extractor
    if _frame_extractor is None:
        from transcription import FrameExtractor

        _frame_extractor = FrameExtractor()
        logger.info("FrameExtractor initialized")
    return _frame_extractor


@mcp.tool()
def hermes_extract_frames(
    media_path: str,
    start: Optional[float] = None,
    end: Optional[float] = None,
    max_frames: Optional[int] = None,
    resolution: int = 512,
    force: bool = False,
) -> str:
    """Extract still frames from a local video so they can be visually inspected.

    Samples JPEG frames at duration-scaled intervals and returns their file
    paths with timestamps. Read those image paths to actually SEE what is on
    screen (UI state, slides, objects, on-screen text). Fully local — no cloud.

    Args:
        media_path: Absolute path to a local video file (mp4, mkv, mov, webm, ...).
        start:      Optional clip start in seconds (focus the frame budget).
        end:        Optional clip end in seconds.
        max_frames: Override the duration-scaled default (hard cap 100).
        resolution: JPEG width in px, height keeps aspect (default 512).
        force:      Re-extract even if a cached frame set exists.
    """
    logger.info("hermes_extract_frames called: %s (start=%s end=%s)", media_path, start, end)
    try:
        from transcription import FrameExtractionError

        extractor = get_frame_extractor()
        try:
            data = extractor.extract(media_path, start=start, end=end,
                                     max_frames=max_frames, resolution=resolution,
                                     force=force)
        except FrameExtractionError as exc:
            return json.dumps({"status": "error", "error": str(exc)})

        data["hint"] = "Read each frame path to view it, then describe what is shown."
        return json.dumps({"status": "ok", **data}, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.exception("hermes_extract_frames failed")
        return json.dumps({"status": "error", "error": str(exc)})


@mcp.tool()
def hermes_watch_video(
    media_path: str,
    start: Optional[float] = None,
    end: Optional[float] = None,
    max_frames: Optional[int] = None,
    resolution: int = 512,
    model_size: str = "base",
    language: Optional[str] = None,
) -> str:
    """Watch a local video: extract frames AND transcribe audio in one call.

    Returns timestamped frame paths plus the full transcript so you can both
    SEE what is displayed and HEAR what is said, then answer questions about
    the video. Fully local and free (PyAV frames + faster-whisper). Read the
    returned frame paths to view them.

    Args:
        media_path: Absolute path to a local video file.
        start, end: Optional clip window in seconds (focuses frames + is noted).
        max_frames: Override duration-scaled frame count (hard cap 100).
        resolution: Frame JPEG width in px (default 512).
        model_size: Whisper model: tiny|base|small|medium|large-v3|large-v3-turbo.
        language:   ISO code (e.g. 'en') to skip auto-detection.
    """
    logger.info("hermes_watch_video called: %s", media_path)
    try:
        from transcription import FrameExtractionError, TranscriptionError

        response = {"status": "ok", "media_path": media_path}

        # Visual track
        try:
            frames = get_frame_extractor().extract(
                media_path, start=start, end=end, max_frames=max_frames,
                resolution=resolution,
            )
            response["frames"] = frames
        except FrameExtractionError as exc:
            response["frames_error"] = str(exc)

        # Audio track
        try:
            transcript = get_transcriber(model_size).transcribe(
                media_path, language=language,
            )
            response["transcript"] = transcript
        except TranscriptionError as exc:
            response["transcript_error"] = str(exc)

        if "frames" not in response and "transcript" not in response:
            return json.dumps({"status": "error",
                               "error": "Could not extract frames or transcript.",
                               "frames_error": response.get("frames_error"),
                               "transcript_error": response.get("transcript_error")})

        response["hint"] = ("Read each frame path to view it; combine what you see "
                            "with the transcript to answer questions about the video.")
        return json.dumps(response, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.exception("hermes_watch_video failed")
        return json.dumps({"status": "error", "error": str(exc)})


# ---------------------------------------------------------------------------
# Mothers Day card server (one-shot local HTTP)
# ---------------------------------------------------------------------------
_card_server = None
_card_server_port = None


@mcp.tool()
def hermes_open_card(port: int = 8989) -> str:
    """Serve the Mother's Day card on the local network.

    Starts a one-time HTTP server so any device on the same WiFi can open the
    card in a browser.  Call once; subsequent calls return the existing URL.

    Args:
        port: Local port to serve on (default: 8989).
    """
    import socket
    import threading
    from http.server import SimpleHTTPRequestHandler, HTTPServer

    global _card_server, _card_server_port

    card_path = Path(__file__).parent / "mothers_day_card.html"
    if not card_path.exists():
        return json.dumps({"status": "error", "error": "mothers_day_card.html not found in HERMES directory"})

    if _card_server is not None:
        local_ip = socket.gethostbyname(socket.gethostname())
        return json.dumps({
            "status": "already_running",
            "url": f"http://{local_ip}:{_card_server_port}/mothers_day_card.html",
            "local_url": f"http://localhost:{_card_server_port}/mothers_day_card.html",
        })

    serve_dir = str(Path(__file__).parent)

    class QuietHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=serve_dir, **kwargs)

        def log_message(self, fmt, *args):
            logger.debug("HTTP: " + fmt, *args)

    try:
        server = HTTPServer(("", port), QuietHandler)
    except OSError as exc:
        return json.dumps({"status": "error", "error": f"Could not bind port {port}: {exc}"})

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    _card_server = server
    _card_server_port = port

    try:
        local_ip = socket.gethostbyname(socket.gethostname())
    except Exception:
        local_ip = "localhost"

    logger.info("Card server started on port %d", port)
    return json.dumps({
        "status": "started",
        "url": f"http://{local_ip}:{port}/mothers_day_card.html",
        "local_url": f"http://localhost:{port}/mothers_day_card.html",
        "tip": "Share the 'url' with Mom — she can open it on her phone while on the same WiFi.",
    }, indent=2)


# ---------------------------------------------------------------------------
# MCP Resources
# ---------------------------------------------------------------------------
@mcp.resource("hermes://templates")
def list_templates() -> str:
    """List all available HERMES prompt templates."""
    orch = get_orchestrator()
    names = orch.prompt_generator.list_templates()
    return json.dumps(names, indent=2)


@mcp.resource("hermes://templates/{name}")
def get_template(name: str) -> str:
    """Get the full definition of a HERMES prompt template."""
    orch = get_orchestrator()
    tmpl = orch.prompt_generator.get_template(name)
    if tmpl is None:
        return json.dumps({"error": f"Template '{name}' not found"})
    return json.dumps(
        {
            "name": tmpl.name,
            "task_type": tmpl.task_type.value,
            "base_prompt": tmpl.base_prompt,
            "specializations": tmpl.specializations,
            "context_keywords": tmpl.context_keywords,
            "variables": tmpl.variables,
        },
        indent=2,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _safe_serialise(obj):
    """Recursively convert an object to JSON-safe types."""
    if isinstance(obj, dict):
        return {k: _safe_serialise(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_safe_serialise(v) for v in obj]
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    return str(obj)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    """Run the HERMES MCP server over stdio."""
    logger.info("Starting HERMES MCP Server (stdio)")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
