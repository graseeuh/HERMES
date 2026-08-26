# HERMES Project Instructions

## Quick Reference
Cross-platform: developed on Windows 11, currently running on macOS. venv at `venv/`.
Substitute `<py>` below with the interpreter for your platform:

| | macOS/Linux | Windows |
|---|---|---|
| `<py>` | `venv/bin/python` | `venv\Scripts\python.exe` |
| Activate | `source venv/bin/activate` | `.\venv\Scripts\activate` |

- Setup (either platform): `python scripts/setup.py`
- Test: `<py> -m pytest tests/ -v`
- MCP server: `<py> main.py --mcp`
- `mcp` must stay pinned `<2` — v2 renamed `FastMCP` to `MCPServer` and `mcp_server.py` uses the v1 API

## Architecture — Three-Layer Oversight
```
Approval Gate → Orchestrator + Security Gate → Inspector General
```
These three layers are **structurally isolated**. Never add cross-calls between them.
- Approval Gate (`approval/`) — pre-execution, MCP boundary
- Security Gate (`core_logic/security_agent.py`) — runs inside orchestrator
- Inspector General (`inspector/`) — post-execution auditor, MCP boundary

Do not refactor these into a shared module or add imports between layers.

`transcription/` is a standalone package (not part of the oversight stack) —
local video/audio comprehension via faster-whisper + PyAV. Exposed as 5 MCP
tools in `mcp_server.py` (`hermes_transcribe_video`, `hermes_list_transcripts`,
`hermes_get_transcript`, `hermes_extract_frames`, `hermes_watch_video`).

## Portability Notes
The repo must keep working on **both macOS and Windows**. Conventions:
- Build every path with `pathlib` and the `/` operator — never string-concatenate separators
- Use `os.replace(tmp, dest)` for atomic file writes — `Path.rename()` raises FileExistsError on Windows if dest exists
- Never hardcode `venv/bin` or `venv/Scripts`; derive it (see `scripts/setup.py:venv_python`)
- CLI entry points call `_force_utf8_stdout()` before printing — report output contains `•`/`—`, which are
  undefined in cp437/cp850/cp932/cp949. Wrap `reconfigure` in try/except; it is absent on replaced streams.
- `tempfile.NamedTemporaryFile` needs `delete=False` + explicit unlink — Windows can't reopen an open temp file
- Test fixture credential strings must be split across variables to avoid pre-commit false positives

## Code Style
- Minimal — no unnecessary abstractions, no unsolicited refactoring
- No docstrings/comments on code you didn't change
- Stdlib preferred over new dependencies when practical

## What Not to Touch
- `inspector/logs/`, `inspector/state/`, `approval/state/` — runtime data, never commit
- `docs/`, `projects/`, `tools/` — non-core, excluded from git

## Testing
- 91 tests, 0 failures — run full suite after any change to core_logic/ or inspector/
- Test files: `test_claim_verifier.py` (18), `test_inspector.py` (13), `test_approval.py` (19), `test_github_scanner.py` (27), `test_registry.py` (9), `test_orchestrator.py` (4)

## Compact Instructions
When compacting, preserve: code changes with file paths, test results, errors/blockers, and any user decisions made during the conversation. Drop verbose tool output and intermediate exploration.
