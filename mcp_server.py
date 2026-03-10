"""
HERMES MCP Server
Exposes HERMES orchestration capabilities as MCP tools and resources
for Claude Code integration over stdio.
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

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
        # Basic input validation
        if "/" not in repo or len(repo.split("/")) != 2:
            return json.dumps({"status": "error", "error": "repo must be in 'owner/name' format"})

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
            response["quarantine_path"] = result.quarantine_path
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
    """Run the HERMES MCP server.

    Default: stdio transport (for Claude Code on desktop — unchanged behaviour).
    iPhone:  SSE transport so the Claude iOS app can connect over your local
             Wi-Fi network.

    To start the iPhone-accessible SSE server:

        python mcp_server.py --sse

    Or with environment variables:

        HERMES_TRANSPORT=sse python mcp_server.py
        HERMES_TRANSPORT=sse HERMES_SSE_PORT=7778 python mcp_server.py

    Then in the Claude iOS app → Settings → MCP Servers → Add Server:
        URL:  http://<your-desktop-ip>:7778/sse
        Name: HERMES
    """
    import sys

    use_sse = "--sse" in sys.argv or os.environ.get("HERMES_TRANSPORT", "").lower() == "sse"

    if use_sse:
        port = int(os.environ.get("HERMES_SSE_PORT", "7778"))
        logger.info(
            "Starting HERMES MCP Server (SSE on 0.0.0.0:%d) — "
            "connect from Claude iOS app at http://<this-machine-ip>:%d/sse",
            port,
            port,
        )
        mcp.run(transport="sse", host="0.0.0.0", port=port)
    else:
        logger.info("Starting HERMES MCP Server (stdio)")
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
