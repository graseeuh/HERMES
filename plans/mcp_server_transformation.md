# HERMES MCP Server Transformation Plan

## Context

HERMES currently runs as a standalone Python orchestration system — tasks come in through voice or CLI, get parsed/routed to subagents, and results come back. The problem: there's no centralized security gateway, no audit trail, and subagents can potentially access anything without oversight.

**Goal**: Transform HERMES into an MCP server that acts as the **single gateway** between Claude Code and all task execution. Everything passes through HERMES — it controls what subagents see, enforces security policies, logs all activity, gates destructive actions on user approval, and scans any external code (GitHub) for malicious content before it enters the system.

```
You (User)
  |
Claude Code
  | (MCP stdio)
HERMES MCP Server  <-- single gateway, full control
  |       |       |
Agent1  Agent2  Agent3  (HERMES-managed subagents)
```

---

## New Files to Create

### 1. `mcp_server.py` — MCP Server Entry Point
The main file Claude Code launches. Defines all MCP tools and resources using FastMCP.

**MCP Tools exposed:**
| Tool | Purpose |
|------|---------|
| `hermes_execute` | Submit task — HERMES orchestrates end-to-end, returns results |
| `hermes_status` | System status: agents, tasks, workload |
| `hermes_approve` | Approve/deny pending destructive action requests |
| `hermes_query_agents` | Query active agents by status/type |
| `hermes_security_audit` | Run security audit or view audit logs |
| `hermes_configure` | Update security policies, templates, settings |
| `hermes_fetch_github` | Fetch GitHub files with mandatory malicious content scanning |

**MCP Resources exposed:**
- `hermes://templates` — list all agent templates
- `hermes://templates/{name}` — get specific template
- `hermes://audit/latest` — recent audit entries
- `hermes://audit/{date}` — audit entries by date
- `hermes://security/policies` — current security config

**Critical**: All logging goes to stderr (not stdout) — stdout is reserved for MCP JSON-RPC.

### 2. `security/__init__.py` — Security package init

### 3. `security/credential_vault.py` — Credential Protection
- Stores secrets encrypted via Fernet (from `cryptography`, already a dependency)
- Encryption key stored in Windows Credential Manager via `keyring` (already a dependency)
- `get_safe_env()` returns environment dict with all sensitive vars stripped
- `redact_secrets_from_text(text)` scrubs any string for leaked credentials
- Policy-based: defines which agent types can access which credentials
- Env blocklist: `ANTHROPIC_API_KEY`, `GITHUB_TOKEN`, `OPENAI_API_KEY`, `AWS_SECRET_ACCESS_KEY`, `DATABASE_URL`, etc.

### 4. `security/pii_detector.py` — PII Detection & Redaction
- Regex-based detection of: emails, phone numbers, SSNs, credit cards, IP addresses, API key patterns
- `detect(text)` returns list of PII matches with types and positions
- `redact(text)` replaces PII with typed placeholders like `[EMAIL_REDACTED]`
- Runs on all I/O before it reaches subagents

### 5. `security/sanitizer.py` — Central I/O Sanitization Pipeline
- **ALL data** entering or leaving HERMES passes through this
- Three levels: MINIMAL (basic cleanup), STANDARD (PII + credential redaction), STRICT (full sanitization for untrusted input like GitHub fetches)
- `sanitize_input(text)` — clean incoming data
- `sanitize_output(text)` — clean outgoing data
- `sanitize_for_agent(text, agent_type)` — agent-specific sanitization (least-privilege)
- Returns `SanitizationResult` with stats: redactions applied, PII found, credentials redacted

### 6. `security/github_scanner.py` — GitHub Fetch + Malicious Content Scanner
Multi-layer scanning before ANY external code enters the system:

**Layer 1 — Malicious pattern matching:**
- Obfuscated code (long hex sequences, chr() chains)
- eval/exec injection (`eval(input(...)`, `exec(request...)`)
- Encoded payloads (base64 decode into exec)
- Reverse shells (socket+connect+dup2, pty.spawn)
- Crypto miners (stratum+tcp, xmrig, coinhive patterns)
- Supply chain attacks (malicious setup.py with subprocess in install)

**Layer 2 — Dependency analysis:**
- Extract imports from fetched code
- Check for typosquatting (Levenshtein distance < 2 from known packages)

**Layer 3 — Credential detection:**
- API keys, tokens, passwords embedded in strings
- AWS/GCP/Azure credential patterns

**Layer 4 — Anomaly detection:**
- Binary content in text files
- Extremely long lines (>10000 chars)
- High-entropy strings (potential encrypted payloads)

**Classification**: Each file gets CLEAN / SUSPICIOUS / MALICIOUS
- CLEAN: content passes through to HERMES
- SUSPICIOUS/MALICIOUS: quarantined to `data/quarantine/YYYYMMDD/{repo}/{path}`, flagged for user review, content NOT allowed into the system

**Fetching**: Uses `gh` CLI (preferred) or GitHub REST API as fallback.

Reuses pattern-matching approach from existing `core_logic/security_agent.py` (`_check_patterns` method, `SECURITY_PATTERNS` dict structure).

### 7. `security/file_acl.py` — File Access Control
- Controls which agents can read/write which files/directories
- Default policies: block `.env`, `credentials.*`, `*.pem`, `*.key` from all agents
- Agent-type overrides (e.g., CODE agents can write to `src/`, RESEARCH agents read-only)
- Glob-based pattern matching

### 8. `audit/__init__.py` — Audit package init

### 9. `audit/audit_logger.py` — Audit Logging System
**Folder structure:**
```
audit/
  2026/
    02/
      10/
        hermes_audit_20260210.jsonl
      11/
        hermes_audit_20260211.jsonl
```

**Log format** (JSON Lines — one JSON object per line):
```json
{
  "timestamp": "2026-02-10T14:30:00.123456",
  "session_id": "sess_a1b2c3d4",
  "event_type": "request",
  "action": "hermes_execute",
  "agent_id": null,
  "task_id": null,
  "sanitized_input": "Build a REST API for user management",
  "sanitized_output": null,
  "security_events": [],
  "metadata": {"tool_name": "hermes_execute", "subtask_count": 3}
}
```

**Event types logged:**
- `request` / `response` — every MCP tool call
- `agent_spawn` / `agent_complete` / `agent_buff` — agent lifecycle
- `security_scan` / `quarantine` / `pii_redaction` / `credential_access` — security events
- `approval_requested` / `approval_granted` / `approval_denied` — gate events
- `github_fetch` — external code fetches
- `config_change` / `error` — system events

**Retention**: 90 days default, cleanup on startup and daily.

### 10. `approval/__init__.py` — Approval package init

### 11. `approval/approval_gate.py` — Destructive Action Approval Gates
**Actions requiring approval** (configurable):
- File delete, git push, git force push
- External API calls, system commands, package installs

**Flow:**
1. Orchestrator detects destructive action via pattern matching on task description
2. `ApprovalGate.request_approval()` creates a pending request with unique ID
3. `hermes_execute` returns response with `"status": "approval_required"` and the pending request details
4. User reviews and calls `hermes_approve(request_id, approved=True/False, reason="...")`
5. Gate resolves — orchestrator continues or aborts
6. All approval events audit-logged
7. Timeout: 5 minutes default — auto-denied if no response

**Detection patterns**: `delete`, `rm`, `git push`, `push --force`, `requests.post`, `os.system`, `subprocess.run`, `pip install`, etc.

### 12. `config/mcp_config.py` — MCP Configuration
Centralized config dataclass for all MCP-mode settings: sanitization level, credential blocklist, PII toggle, approval policies, audit retention, GitHub scanner limits.

### 13. `tests/test_mcp_server.py` — MCP Server Tests
### 14. `tests/test_security.py` — Security Layer Tests

---

## Existing Files to Modify

### `requirements.txt`
Add: `mcp[cli]>=1.2.0`

All other deps already present (`cryptography`, `keyring`, `requests`).

### `core_logic/orchestrator.py`
- Add optional `sanitizer`, `audit_logger`, `approval_gate` params to `__init__`
- In `_execute_subtask`: wrap prompt through `sanitizer.sanitize_for_agent()` before execution
- In `_spawn_agent` / `_buff_agent`: call `audit_logger.log()` on spawn, completion, errors
- Before destructive execution: check `approval_gate.requires_approval()`, create approval request if needed
- Replace all `print()` calls with `logging.getLogger("hermes.orchestrator")` (critical for stdio MCP)

### `core_logic/task_parser.py`
- Add `GITHUB_FETCH = "github_fetch"` to `TaskType` enum
- Add GitHub keywords: `["github", "fetch", "clone", "repo", "repository", "download"]`

### `core_logic/agent_matcher.py`
- Add `TaskType.GITHUB_FETCH` → `"general-purpose"` in `suggest_agent_type()`

### `integration/claude_bridge.py`
- Add `'github_fetch': 'general-purpose'` to `SUBAGENT_MAPPING`
- Replace `print()` with `logging`

### `integration/claude_code_executor.py`
- Add `env_override` param to `execute()` for sanitized env from `CredentialVault.get_safe_env()`
- Replace `print()` with `logging`

### `main.py`
- Add MCP mode: if `--mcp` flag or `HERMES_MODE=mcp` env var, run `mcp_server.main()` instead of interactive CLI

### `config/__init__.py`
- Export `HermesMCPConfig`

### `core_logic/security_agent.py`
- Add `scan_content(content: str, filename: str) -> List[SecurityIssue]` method for scanning strings (not just files on disk) — used by GitHub scanner to share the existing pattern-matching infrastructure

---

## Implementation Order

**Phase 1: Security Foundation** (everything depends on this)
1. `security/credential_vault.py`
2. `security/pii_detector.py`
3. `security/sanitizer.py`
4. `audit/audit_logger.py`
5. `config/mcp_config.py`

**Phase 2: MCP Server Core**
6. `mcp_server.py` — with `hermes_execute` and `hermes_status` tools
7. Modify `core_logic/orchestrator.py` — wire in sanitizer, audit, logging
8. Modify `integration/claude_bridge.py` — logging
9. Modify `integration/claude_code_executor.py` — sanitized env, logging
10. Modify `main.py` — MCP mode entry point
11. Modify `requirements.txt` — add `mcp[cli]`

**Phase 3: Approval Gates**
12. `approval/approval_gate.py`
13. Add `hermes_approve` tool to `mcp_server.py`
14. Wire approval checks into orchestrator

**Phase 4: GitHub Scanner**
15. `security/github_scanner.py`
16. `security/file_acl.py`
17. Add `hermes_fetch_github` tool to `mcp_server.py`
18. Modify `core_logic/task_parser.py` — GITHUB_FETCH type
19. Modify `core_logic/agent_matcher.py` — GITHUB_FETCH mapping
20. Modify `core_logic/security_agent.py` — `scan_content()` method

**Phase 5: Remaining Tools + Resources**
21. Add `hermes_query_agents`, `hermes_security_audit`, `hermes_configure` tools
22. Add MCP resources (templates, audit, policies)

**Phase 6: Testing**
23. `tests/test_security.py`
24. `tests/test_mcp_server.py`
25. Configure Claude Code MCP connection and verify end-to-end

---

## Claude Code MCP Configuration

Add to Claude Code settings (`~/.claude/settings.local.json` or project `.mcp.json`):

```json
{
  "mcpServers": {
    "hermes": {
      "command": "C:\\Users\\<username>\\HERMES\\venv\\Scripts\\python.exe",
      "args": ["C:\\Users\\<username>\\HERMES\\mcp_server.py"],
      "env": {
        "HERMES_MODE": "mcp",
        "PYTHONPATH": "C:\\Users\\<username>\\HERMES"
      }
    }
  }
}
```

---

## Verification

1. `pip install "mcp[cli]"` in HERMES venv
2. Run `python mcp_server.py` — verify no stdout output (only stderr logs)
3. Configure Claude Code MCP config as above
4. Verify HERMES tools appear in Claude Code's tool list
5. Test `hermes_execute` with a simple task — verify orchestration + audit log written
6. Test `hermes_status` and `hermes_query_agents` — verify JSON responses
7. Test approval flow: execute "delete all temp files" → verify approval prompt → approve → verify execution
8. Test GitHub fetch: `hermes_fetch_github` with a known repo → verify scan runs
9. Test malicious content detection: fetch content with embedded `eval(input())` → verify quarantine
10. Check `audit/` folder has organized YYYY/MM/DD entries
11. Verify voice listener still works: `python hermes_listener.py`

---

## Plan Transcript Reference

Full planning session transcript available in local Claude project history.

---

## Status: PARTIALLY IMPLEMENTED
*Saved: 2026-02-10 | Updated: 2026-02-24*

**Completed:** Phase 2 (MCP server core — `mcp_server.py`, 3 tools), Phase 3 (Approval Gates — `approval/`), Inspector General (`inspector/`)
**Pending:** Phase 1 (security/ package), Phase 4 (GitHub scanner), Phase 6 (tests), true parallel execution
