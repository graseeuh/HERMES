# HERMES Project Instructions

## Quick Reference
- Python 3.14, Windows 11, venv at `venv/`
- Run: `venv/Scripts/python.exe`
- Test: `venv/Scripts/python.exe -m pytest tests/ -v`
- MCP server: `venv/Scripts/python.exe main.py --mcp`

## Architecture — Three-Layer Oversight
```
Approval Gate → Orchestrator + Security Gate → Inspector General
```
These three layers are **structurally isolated**. Never add cross-calls between them.
- Approval Gate (`approval/`) — pre-execution, MCP boundary
- Security Gate (`core_logic/security_agent.py`) — runs inside orchestrator
- Inspector General (`inspector/`) — post-execution auditor, MCP boundary

Do not refactor these into a shared module or add imports between layers.

## Windows Gotchas
- Use `os.replace(tmp, dest)` for atomic file writes — `Path.rename()` raises FileExistsError on Windows if dest exists
- Force UTF-8 stdout when using Unicode symbols: `sys.stdout.reconfigure(encoding='utf-8', errors='replace')`
- Test fixture credential strings must be split across variables to avoid pre-commit false positives

## Code Style
- Minimal — no unnecessary abstractions, no unsolicited refactoring
- No docstrings/comments on code you didn't change
- Stdlib preferred over new dependencies when practical

## What Not to Touch
- `inspector/logs/`, `inspector/state/`, `approval/state/` — runtime data, never commit
- `docs/`, `projects/`, `viccia_ai/`, `tools/` — sensitive or non-core, excluded from git

## Testing
- 91 tests, 0 failures — run full suite after any change to core_logic/ or inspector/
- Test files: `test_claim_verifier.py` (18), `test_inspector.py` (13), `test_approval.py` (19), `test_github_scanner.py` (27), `test_registry.py` (9), `test_orchestrator.py` (4)

## Compact Instructions
When compacting, preserve: code changes with file paths, test results, errors/blockers, and any user decisions made during the conversation. Drop verbose tool output and intermediate exploration.
