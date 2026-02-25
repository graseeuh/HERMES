# HERMES - Hierarchical Executable Reasoning and Management Execution System

A voice-activated, multi-agent orchestration system with independent oversight.
Accepts natural language commands, routes tasks to specialized agents, enforces
approval gates on destructive actions, and audits all results through an
independent Inspector General.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Running HERMES](#running-hermes)
3. [MCP Server Mode](#mcp-server-mode)
4. [MCP Tools Reference](#mcp-tools-reference)
5. [Architecture](#architecture)
6. [Oversight System](#oversight-system)
7. [Agent Types](#agent-types)
8. [Agent Buffing](#agent-buffing)
9. [Voice Commands](#voice-commands)
10. [Python API](#python-api)
11. [Configuration](#configuration)
12. [Security](#security)
13. [File Structure](#file-structure)

---

## Quick Start

```bash
# Activate virtual environment
.\venv\Scripts\activate

# MCP server mode (Claude Code integration)
python main.py --mcp

# Voice-controlled mode
python hermes_listener.py

# Interactive text mode
python main.py
```

---

## Running HERMES

### Option 1: MCP Server (Claude Code Integration)

Exposes HERMES as an MCP server over stdio. Claude Code connects to it and
can call HERMES tools directly.

```bash
python main.py --mcp
# or
HERMES_MODE=mcp python main.py
```

Configure in `.mcp.json` or `~/.claude/settings.local.json`:
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

### Option 2: Always-On Voice Listener

Continuously listens for "Hey Hermes" wake word:

```bash
python hermes_listener.py
# With specific microphone:
python hermes_listener.py --mic 1
```

### Option 3: Interactive Text Mode

```bash
python main.py
```

### Option 4: Python API

```python
from main import HERMES

hermes = HERMES()
result = hermes.run("Analyze the codebase for unused imports")
print(result.summary)
```

---

## MCP Server Mode

HERMES exposes 6 tools when running as an MCP server:

### Normal Task Execution

```
hermes_execute("analyze all Python files for security issues")
→ runs through orchestrator + inspector
← { status, summary, results, inspector: { passed, flags, confidence } }
```

### Destructive Task Flow

Tasks matching destructive patterns (delete, git push, pip install, etc.)
require explicit approval before execution:

```
hermes_execute("delete all log files older than 30 days")
← { status: "approval_required", request_id: "req_a1b2c3d4", matched_patterns: [...] }

hermes_approve("req_a1b2c3d4", approved=True, reason="confirmed cleanup")
← { status: "completed", approved_by_user: true, results: {...}, inspector: {...} }
```

---

## MCP Tools Reference

| Tool | Description |
|------|-------------|
| `hermes_execute(task)` | Execute a natural-language task. Returns `approval_required` for destructive tasks. |
| `hermes_approve(request_id, approved, reason)` | Approve or deny a pending destructive action. If approved, executes and returns result. |
| `hermes_list_pending()` | List all approval requests currently waiting for confirmation. |
| `hermes_status()` | Orchestrator status: agent counts, templates loaded, executor availability. |
| `hermes_query_agents(status_filter, task_type_filter)` | Query the agent registry. Filter by status or task type. |
| `hermes_inspector_report(days)` | Inspector General behavioral stats and recent audit log entries. |

---

## Architecture

```
You (voice / text / Claude Code MCP)
              |
      ┌───────┴────────┐
      │  Approval Gate  │  ← checks BEFORE execution
      │  (approval/)    │    destructive tasks require your OK
      └───────┬────────┘
              │ approved
      ┌───────┴────────┐
      │  Orchestrator   │  ← does the work
      │  (core_logic/)  │    parses, routes, executes agents
      │                 │    runs mandatory security gate last
      └───────┬────────┘
              │ raw result
      ┌───────┴────────┐
      │  Inspector      │  ← audits AFTER execution
      │  General        │    independent — orchestrator cannot
      │  (inspector/)   │    call, bypass, or write to it
      └───────┬────────┘
              │ annotated result
             You
```

### Execution Flow

```
1. Approval Gate checks task for destructive patterns
   → if matched: return approval_required (stop here)
   → if safe: continue

2. Orchestrator parses task into subtasks
3. Detects dependencies, groups independent subtasks
4. For each subtask:
   - Check for compatible existing agent (BUFF) or spawn new one
   - Generate prompt from template
   - Execute via Claude Code executor
5. Run mandatory security gate on all outputs
6. Return ExecutionResult

7. Inspector General (independent) receives raw result:
   - Verifies security gate ran
   - Checks timing plausibility
   - Detects error suppression
   - Validates file path claims
   - Tracks behavioral patterns across sessions
   - Writes to its own immutable audit log
8. Inspector verdict attached to response
```

---

## Oversight System

HERMES has three independent oversight layers, each structurally isolated from the others.

### Approval Gate (`approval/`)

Intercepts tasks **before** they execute. Cannot be bypassed by the orchestrator — it runs at the MCP boundary before the orchestrator is ever called.

**Destructive patterns detected:**
- File/data deletion: `delete`, `remove`, `erase`, `wipe`, `drop table`, `truncate`, `rm`
- Git remote operations: `git push`, `deploy`, `force push`
- Package installation: `pip install`, `npm install`, `apt install`
- External communications: `send email`, `post to`, `webhook`, `call API`
- System operations: `kill process`, `shutdown`, `restart service`, `format disk`
- Overwrite operations: `overwrite`, `replace all`, `rewrite entire`

Pending approvals persist across MCP server restarts (5-minute timeout).

### Security Gate (inside `core_logic/orchestrator.py`)

Mandatory final step after every task execution. Runs a security agent over all
outputs before results are returned. Always adds a `security_gate` key to results.

### Inspector General (`inspector/`)

Independent auditor that runs **after** the orchestrator returns. The orchestrator
has zero import paths to the inspector — it cannot call, skip, or write to it.

**Checks run on every result:**
| Check | Flag |
|-------|------|
| Security gate absent from results | `SECURITY_GATE_ABSENT` |
| Sub-100ms execution of completed task | `IMPLAUSIBLE_EXECUTION_TIME` |
| Completed status but empty results | `COMPLETED_WITH_NO_RESULTS` |
| Errors present but summary claims success | `ERROR_SUPPRESSION_DETECTED` |
| Results exist but no agents claimed | `NO_AGENTS_CLAIMED_BUT_RESULTS_EXIST` |
| Claimed file path doesn't exist on disk | `CLAIMED_FILE_NOT_FOUND: <path>` |
| Malformed result entry structure | `MALFORMED_RESULT_ENTRY: <id>` |

**Behavioral monitoring** (cross-session, persisted to `inspector/state/`):
- Tracks success rate, flag rate, security gate skip rate
- Detects anomalies: success rate drop >20% from baseline, gate skip rate >10%, flag rate >30%

**Audit log** (`inspector/logs/inspector_YYYYMMDD.jsonl`):
- Append-only JSONL, one entry per execution
- The orchestrator has no write path to this file

---

## Agent Types

| Type | Purpose | Template | Keywords |
|------|---------|----------|---------|
| CODE | Write, debug, refactor code | `code_agent.json` | write, implement, build, fix, debug, refactor |
| RESEARCH | Explore codebase, analyze | `research_agent.json` | find, search, explore, analyze, review |
| VISION | MediaPipe/OpenCV processing | `vision_agent.json` | webcam, camera, detect, hand, face, pose |
| AUDIO | sounddevice audio tasks | `audio_agent.json` | audio, sound, microphone, speech, frequency |
| KICAD | PCB design, schematics | `kicad_agent.json` | kicad, pcb, schematic, footprint, gerber |
| TOUCHDESIGNER | Realtime visuals, GLSL | `touchdesigner_agent.json` | touchdesigner, glsl, generative, realtime |
| PLAN | Design, architect systems | — | plan, design, architect, strategy |
| SECURITY | Security audit, review | `security_agent.json` | security, audit, vulnerability, owasp |
| CUSTOM | User-defined prompts | Custom | — |

---

## Agent Buffing

Buffing = reusing an existing agent instead of spawning a new one.

```
New Task Arrives
      │
      ▼
Agent Matcher checks registry
      │
  Compatible?
   /       \
YES         NO
 │           │
BUFF       SPAWN
(reuse)    (new)
```

**Match scoring:**
- Task type match: 40%
- Specialization match: 25%
- Context overlap: 20%
- Workload factor: 15%
- Minimum score to buff: 50%

---

## Voice Commands

### Wake Words

| Say | Action |
|-----|--------|
| "Hey Hermes" | Activates listening |
| "Hermes" | Activates listening |
| "Ok Hermes" | Activates listening |

### Built-in Commands

| Say | What Happens |
|-----|--------------|
| "Status" | Shows HERMES system status |
| "Help" | Lists available commands |
| "Stop listening" / "Quit" | Exits HERMES |

### Task Commands

Any command not matching built-ins is routed to the orchestrator:

```
"Write a function to validate emails"  → CODE agent
"Analyze the project structure"        → RESEARCH agent
"Detect hand gestures from webcam"     → VISION agent
"Design a PCB for an ESP32"            → KICAD agent
"Create a generative particle system"  → TOUCHDESIGNER agent
```

---

## Python API

```python
from main import HERMES

hermes = HERMES()
hermes.set_verbose(True)

# Execute a task
result = hermes.run("Search for error handling patterns and write a utility")
print(result.summary)
print(f"Status: {result.status.value}")
print(f"Time: {result.execution_time:.2f}s")

# Analyze without executing
analysis = hermes.analyze("Build a REST API with authentication")
for st in analysis['subtasks']:
    print(f"  [{st['type']}] {st['description']}")

# Plan then execute
plan = hermes.plan("Your task here")
result = hermes.execute(plan)

# System status
print(hermes.status())
```

---

## Configuration

### Knowledge Base

```
knowledge_base/
├── prompts/          # Saved generated prompts (auto-created)
└── templates/        # Agent prompt templates
    ├── code_agent.json
    ├── research_agent.json
    ├── vision_agent.json
    ├── audio_agent.json
    ├── security_agent.json
    ├── kicad_agent.json
    └── touchdesigner_agent.json
```

### Template Format

```json
{
  "name": "code_agent",
  "task_type": "code",
  "base_prompt": "You are a HERMES Code Agent...\n\n## Your Task\n{task_description}",
  "specializations": ["python", "debugging", "refactoring"],
  "context_keywords": ["implement", "write", "code"],
  "variables": ["task_description", "context", "files", "technologies"]
}
```

### Runtime State (not committed to git)

```
inspector/
├── logs/             # Inspector audit logs (YYYYMMDD.jsonl)
└── state/            # Behavioral monitor state (behavioral_state.json)

approval/
└── state/            # Pending approval requests (pending_approvals.json)
```

---

## Security

### Pre-commit Hook

Scans all staged files for PII and secrets before every commit:

```bash
python scripts/pre_commit_scan.py
```

### Security Audit

```bash
python run_security_audit.py
python run_security_audit.py --verbose
```

Checks: command injection, SQL injection, path traversal, hardcoded secrets,
bare excepts, missing input validation, unclosed resources.

### Inspector Report

Query the Inspector General's independent audit log:

```
hermes_inspector_report(days=7)
← { behavioral_report: { success_rate, flag_rate, anomalies_detected, ... },
    recent_log_entries: [...] }
```

---

## File Structure

```
HERMES/
├── main.py                      # Entry point — CLI and MCP mode
├── mcp_server.py                # FastMCP server (6 tools)
├── hermes_listener.py           # Always-on voice listener
├── voice_control.py             # Interactive voice control
├── run_security_audit.py        # Security audit runner
├── requirements.txt
├── README.md
│
├── core_logic/
│   ├── orchestrator.py          # Coordination engine, security gate
│   ├── task_parser.py           # NL parsing, subtask extraction
│   ├── agent_registry.py        # Agent tracking and state
│   ├── agent_matcher.py         # Buffing logic, compatibility scoring
│   ├── prompt_generator.py      # Template loading, prompt creation
│   └── security_agent.py        # Security scanning patterns
│
├── inspector/                   # Inspector General (independent auditor)
│   ├── inspector_general.py     # Main class, InspectorVerdict dataclass
│   ├── claim_verifier.py        # 7 stateless result checks
│   ├── behavioral_monitor.py    # Cross-session behavioral tracking
│   └── inspector_log.py         # Append-only JSONL audit log
│
├── approval/                    # Approval Gate (pre-execution)
│   └── approval_gate.py         # Pattern detection, request lifecycle
│
├── integration/
│   ├── claude_bridge.py         # Claude Code Task tool interface
│   ├── claude_code_executor.py  # Claude CLI subprocess executor
│   └── claude_llm_client.py     # Direct LLM client
│
├── sensors/
│   ├── voice_interface.py       # Speech recognition
│   ├── audio_interface.py       # sounddevice wrapper
│   ├── vision_interface.py      # MediaPipe/OpenCV
│   ├── face_recognition_interface.py
│   └── tts_interface.py         # Text-to-speech
│
├── knowledge_base/
│   └── templates/               # Agent prompt templates
│
├── scripts/
│   ├── pre_commit_scan.py       # PII/secrets pre-commit hook
│   ├── enroll_face.py           # Face recognition enrollment
│   └── setup_autostart.py       # Windows autostart setup
│
├── config/
│   └── voice_config.py          # Voice recognition settings
│
└── plans/
    └── mcp_server_transformation.md  # Architecture roadmap
```

---

## Dependencies

```bash
pip install -r requirements.txt
```

Key dependencies: `mcp[cli]`, `anthropic`, `openai`, `mediapipe`, `opencv-python`,
`sounddevice`, `SpeechRecognition`, `face_recognition`, `cryptography`, `keyring`

---

## License

Internal use only.
