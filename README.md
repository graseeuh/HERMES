# HERMES - Hierarchical Executable Reasoning and Management Execution System

A voice-activated, multi-agent orchestration system that accepts natural language commands, intelligently routes tasks to specialized agents, and supports agent reuse (buffing) for efficiency.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Running HERMES](#running-hermes)
3. [Voice Commands](#voice-commands)
4. [Python API](#python-api)
5. [Architecture](#architecture)
6. [Agent Types](#agent-types)
7. [Agent Buffing](#agent-buffing)
8. [Configuration](#configuration)
9. [Security Audit](#security-audit)
10. [File Structure](#file-structure)

---

## Quick Start

```bash
# Navigate to project
cd .\HERMES

# Activate virtual environment
.\venv\Scripts\activate

# Run voice-controlled HERMES
python hermes_listener.py
```

---

## Running HERMES

### Option 1: Always-On Voice Listener (Recommended)

Continuously listens for "Hey Hermes" wake word:

```bash
python hermes_listener.py
```

With specific microphone:
```bash
python hermes_listener.py --mic 1
```

### Option 2: Interactive Voice Control

Manual voice control session:

```bash
python voice_control.py
```

### Option 3: Interactive Text Mode

Command-line text interface:

```bash
python main.py
```

### Option 4: Python Import

```python
from main import HERMES

hermes = HERMES()
result = hermes.run("Your task description here")
print(result.summary)
```

### Option 5: Test Voice Recognition

Test your microphone setup:

```bash
python test_voice.py
```

---

## Voice Commands

### Activation

| Wake Word | Action |
|-----------|--------|
| "Hey Hermes" | Activates listening mode |
| "Hermes" | Activates listening mode |
| "Ok Hermes" | Activates listening mode |

### Built-in Commands

| Say | What Happens |
|-----|--------------|
| "Create a file called [name]" | Creates a new file |
| "Make a file named [name]" | Creates a new file |
| "Search for [term]" | Searches the codebase |
| "Find [something]" | Searches for files/code |
| "Status" | Shows HERMES system status |
| "Help" | Lists available commands |
| "What time is it" | Tells current time |
| "Stop listening" | Exits HERMES |
| "Quit" / "Exit" | Exits HERMES |

### Task Commands (Sent to Orchestrator)

Any command not matching built-in commands is sent to the HERMES orchestrator:

| Example | Processing |
|---------|------------|
| "Write a function to validate emails" | Spawns CODE agent |
| "Analyze the project structure" | Spawns RESEARCH agent |
| "Detect hand gestures from webcam" | Spawns VISION agent |
| "Monitor audio levels" | Spawns AUDIO agent |
| "Plan the authentication system" | Spawns PLAN agent |

---

## Python API

### Basic Usage

```python
from main import HERMES

# Initialize
hermes = HERMES()
hermes.set_verbose(True)  # Enable detailed output

# Run a task
result = hermes.run("Search for error handling patterns and write a utility")
print(result.summary)
print(f"Status: {result.status.value}")
print(f"Execution time: {result.execution_time}s")
```

### Analyze Without Executing

```python
# See what HERMES would do without running
analysis = hermes.analyze("Complex multi-step task description")

print(f"Subtasks: {len(analysis['subtasks'])}")
for st in analysis['subtasks']:
    print(f"  [{st['type']}] {st['description']}")

print(f"Execution groups: {analysis['execution_groups']}")
print(f"Buff decisions: {analysis['buff_decisions']}")
```

### Plan Then Execute

```python
# Create plan
plan = hermes.plan("Your task here")

# Review plan
for subtask in plan.parsed_task.subtasks:
    print(f"{subtask.id}: {subtask.task_type.value}")

# Execute when ready
result = hermes.execute(plan)
```

### Check System Status

```python
status = hermes.status()
print(f"Templates loaded: {status['templates_loaded']}")
print(f"Registry stats: {status['registry_stats']}")
```

---

## Architecture

```
User Input (Voice/Text)
        |
        v
+-------------------+
|   Task Parser     |  Analyzes natural language
|   (task_parser)   |  Extracts subtasks & dependencies
+-------------------+
        |
        v
+-------------------+
|  Agent Matcher    |  Checks for existing compatible agents
|  (agent_matcher)  |  Decides: BUFF existing or SPAWN new
+-------------------+
        |
        v
+-------------------+
| Prompt Generator  |  Loads templates from knowledge_base
| (prompt_generator)|  Creates customized agent prompts
+-------------------+
        |
        v
+-------------------+
|   Orchestrator    |  Coordinates execution
|  (orchestrator)   |  Manages parallel/sequential groups
+-------------------+
        |
        v
+-------------------+
|  Claude Bridge    |  Interface to Claude Code Task tool
| (claude_bridge)   |  Spawns subagents
+-------------------+
        |
        v
+-------------------+
|  Agent Registry   |  Tracks all agents
| (agent_registry)  |  Stores results & state
+-------------------+
```

### Execution Flow

```
1. Parse task into subtasks
2. Detect dependencies between subtasks
3. Group independent subtasks (can run parallel)
4. For each subtask:
   - Check if existing agent can handle (BUFF)
   - If not, generate prompt and spawn new agent
5. Execute groups sequentially, tasks within groups in parallel
6. Aggregate results
7. Return unified response
```

---

## Agent Types

| Type | Purpose | Template | Claude Subagent |
|------|---------|----------|-----------------|
| CODE | Write, debug, refactor code | `code_agent.json` | general-purpose |
| RESEARCH | Explore codebase, analyze | `research_agent.json` | Explore |
| VISION | MediaPipe/OpenCV processing | `vision_agent.json` | general-purpose |
| AUDIO | sounddevice audio tasks | `audio_agent.json` | general-purpose |
| PLAN | Design, architect systems | - | Plan |
| SECURITY | Security audit, review | `security_agent.json` | general-purpose |
| CUSTOM | User-defined prompts | Custom | general-purpose |

### Task Type Detection Keywords

**CODE**: write, code, implement, create function, build, develop, program, fix, debug, refactor

**RESEARCH**: find, search, look for, explore, investigate, understand, analyze, review, check

**VISION**: webcam, camera, image, video, detect, recognize, hand, face, pose, gesture, mediapipe, opencv

**AUDIO**: audio, sound, microphone, listen, voice, speech, record, sounddevice, frequency

**PLAN**: plan, design, architect, strategy, approach, outline, structure

---

## Agent Buffing

Buffing = reusing existing agents instead of spawning new ones.

### How It Works

```
New Task Arrives
      |
      v
+------------------+
|  Agent Matcher   |
+--------+---------+
         |
    Compatible agent?
        /    \
      YES     NO
       |       |
       v       v
    BUFF     SPAWN
   (reuse)   (new)
```

### Match Scoring

Agents are scored on:
- **Task type match** (40%): Does agent handle this task type?
- **Specialization match** (25%): Relevant specializations?
- **Context overlap** (20%): Shared files/technologies?
- **Workload factor** (15%): Agent not overloaded?

Minimum score for buffing: **0.5** (50%)

### Example

```python
# First task spawns a CODE agent
hermes.run("Write a validation function")
# Agent: code_agent_task_1 (NEW)

# Second similar task BUFFS the existing agent
hermes.run("Write another utility function")
# Agent: code_agent_task_1 (BUFFED - reused!)
```

---

## Configuration

### Knowledge Base Structure

```
knowledge_base/
├── prompts/          # Saved generated prompts (JSON)
│   └── prompt_*.json
└── templates/        # Agent prompt templates
    ├── code_agent.json
    ├── research_agent.json
    ├── vision_agent.json
    ├── audio_agent.json
    └── security_agent.json
```

### Template Format

```json
{
  "name": "code_agent",
  "task_type": "code",
  "base_prompt": "You are a HERMES Code Agent...\n\n## Your Task\n{task_description}\n\n## Context\n{context}",
  "specializations": ["python", "debugging", "refactoring"],
  "context_keywords": ["implement", "write", "code", "function"],
  "variables": ["task_description", "context", "files", "technologies"]
}
```

### Available Template Variables

| Variable | Description |
|----------|-------------|
| `{task_description}` | The user's task |
| `{task_type}` | code, research, vision, etc. |
| `{task_id}` | Unique task identifier |
| `{context}` | Extracted context (JSON) |
| `{files}` | Mentioned file paths |
| `{technologies}` | Detected technologies |
| `{additional_context}` | Extra context passed |

---

## Security Audit

Run before deploying:

```bash
python run_security_audit.py
```

Verbose mode:
```bash
python run_security_audit.py --verbose
```

### What It Checks

| Category | Checks |
|----------|--------|
| **Security** | Command injection, SQL injection, path traversal, hardcoded secrets |
| **Edge Cases** | None checks, empty collections, division by zero |
| **Efficiency** | Nested loops, repeated computations, string concatenation in loops |
| **Error Handling** | Bare except, silent pass, missing finally |
| **Input Validation** | User input sanitization |
| **Resources** | File handles, connections properly closed |

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | PASS - Safe to run |
| 1 | WARN - High severity issues |
| 2 | FAIL - Critical issues found |

---

## File Structure

```
HERMES_Project/
├── main.py                    # Main entry point, HERMES class
├── hermes_listener.py         # Always-on voice listener
├── voice_control.py           # Interactive voice control
├── test_voice.py              # Microphone test utility
├── run_security_audit.py      # Security audit runner
├── requirements.txt           # Python dependencies
├── README.md                  # This file
│
├── core_logic/
│   ├── __init__.py
│   ├── orchestrator.py        # Main coordination engine
│   ├── task_parser.py         # NL parsing, subtask extraction
│   ├── agent_registry.py      # Agent tracking, state management
│   ├── agent_matcher.py       # Buffing logic, compatibility scoring
│   ├── prompt_generator.py    # Template loading, prompt creation
│   └── security_agent.py      # Security scanning
│
├── integration/
│   ├── __init__.py
│   └── claude_bridge.py       # Claude Code Task tool interface
│
├── sensors/
│   ├── __init__.py
│   ├── vision_interface.py    # MediaPipe/OpenCV wrapper
│   ├── audio_interface.py     # sounddevice wrapper
│   └── voice_interface.py     # Speech recognition wrapper
│
├── knowledge_base/
│   ├── __init__.py
│   ├── prompts/               # Saved prompts
│   └── templates/             # Agent templates
│       ├── code_agent.json
│       ├── research_agent.json
│       ├── vision_agent.json
│       ├── audio_agent.json
│       └── security_agent.json
│
└── venv/                      # Python virtual environment
```

---

## Dependencies

```
absl-py==2.3.1
cffi==2.0.0
flatbuffers==25.12.19
mediapipe==0.10.31
numpy==2.2.6
opencv-python==4.12.0.88
pycparser==2.23
sounddevice==0.5.3
SpeechRecognition
PyAudio
```

Install all:
```bash
pip install -r requirements.txt
pip install SpeechRecognition PyAudio
```

---

## Troubleshooting

### Voice not detected
1. Check microphone in Windows Sound Settings
2. Run `python test_voice.py` to test
3. Try different mic index: `python hermes_listener.py --mic 1`

### Low audio levels
- Increase microphone volume in Windows Settings
- Check microphone isn't muted
- Try a different microphone

### Import errors
```bash
# Ensure venv is activated
.\venv\Scripts\activate

# Reinstall dependencies
pip install -r requirements.txt
```

### Security audit fails
```bash
# Run verbose to see issues
python run_security_audit.py --verbose

# Fix issues, then re-run
```

---

## Quick Reference Card

```
ACTIVATION:
  "Hey Hermes" / "Hermes" / "Ok Hermes"

FILE OPERATIONS:
  "Create a file called notes.txt"
  "Make a file named config.json"

SEARCH:
  "Search for error handling"
  "Find Python files"
  "Look for authentication code"

CODING:
  "Write a function to validate emails"
  "Fix the bug in main.py"
  "Refactor the user class"

ANALYSIS:
  "Analyze the project structure"
  "Review the security of auth.py"

SYSTEM:
  "Status" - Show system status
  "Help" - List commands
  "Stop listening" - Exit
```

---

## License

Internal use only.
