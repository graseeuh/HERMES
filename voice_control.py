"""
HERMES Voice Control
Voice-activated interface for HERMES agent orchestration.

Usage:
    python voice_control.py

Say "Hermes" to activate, then speak your command.
"""

import re
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple

from main import HERMES


# ============================================================================
# Input Validation (shared security patterns)
# ============================================================================

MAX_COMMAND_LENGTH = 500

DANGEROUS_PATTERNS = [
    r';\s*(rm|del|format|shutdown|reboot)',
    r'\$\(',
    r'`[^`]+`',
    r'\|\s*(bash|sh|cmd|powershell)',
    r'>\s*/etc/',
    r'>\s*C:\\Windows',
    r'__(import|class|bases|subclasses)__',
    r'eval\s*\(',
    r'exec\s*\(',
    r'os\.(system|popen|exec)',
    r'subprocess\.',
]

_DANGEROUS_REGEX = re.compile('|'.join(DANGEROUS_PATTERNS), re.IGNORECASE)


def validate_command(text: str) -> Tuple[bool, str, str]:
    """Validate voice command for security."""
    if not text or not isinstance(text, str):
        return False, "", "Invalid input"

    if len(text) > MAX_COMMAND_LENGTH:
        return False, "", "Command too long"

    if _DANGEROUS_REGEX.search(text):
        return False, "", "Command contains unsafe patterns"

    sanitized = ''.join(c for c in text if c.isprintable() or c in '\n\t').strip()
    return (True, sanitized, "") if sanitized else (False, "", "Empty after sanitization")


def sanitize_filename(filename: str) -> Optional[str]:
    """Sanitize a filename to prevent path traversal attacks."""
    if not filename:
        return None

    # Remove path separators and parent directory references
    filename = filename.replace('/', '').replace('\\', '').replace('..', '')

    # Allow only safe characters
    sanitized = re.sub(r'[^a-zA-Z0-9_\-.]', '_', filename)

    # Remove leading dots and multiple consecutive dots
    sanitized = sanitized.lstrip('.')
    sanitized = re.sub(r'\.{2,}', '.', sanitized)

    # Limit length
    if len(sanitized) > 100:
        sanitized = sanitized[:100]

    return sanitized if sanitized and sanitized != '.' else None
from sensors.voice_interface import VoiceInterface, VoiceCommand


class VoiceControlledHERMES:
    """
    Voice-controlled interface for HERMES.
    Supports voice commands for file operations, searches, and agent tasks.
    """

    def __init__(self):
        """Initialize voice-controlled HERMES."""
        self.hermes = HERMES()
        self.hermes.set_verbose(True)
        self.voice = VoiceInterface(wake_words=["hermes", "hey hermes"])
        self.running = False

        # Command patterns for special actions
        self.special_commands = {
            'create file': self._handle_create_file,
            'make file': self._handle_create_file,
            'new file': self._handle_create_file,
            'search for': self._handle_search,
            'find': self._handle_search,
            'look for': self._handle_search,
            'stop': self._handle_stop,
            'quit': self._handle_stop,
            'exit': self._handle_stop,
            'status': self._handle_status,
        }

    def start(self) -> None:
        """Start the voice control interface."""
        print("=" * 60)
        print("HERMES Voice Control")
        print("=" * 60)
        print()

        # List microphones
        mics = self.voice.list_microphones()
        print(f"Available microphones: {len(mics)}")
        for m in mics[:5]:
            print(f"  [{m['index']}] {m['name']}")
        if len(mics) > 5:
            print(f"  ... and {len(mics) - 5} more")
        print()

        # Set up microphone
        if not self.voice.set_microphone():
            print("ERROR: Could not initialize microphone")
            return

        # Calibrate for ambient noise
        print("Calibrating for ambient noise...")
        if not self.voice.calibrate(duration=2.0):
            print("WARNING: Calibration failed, continuing anyway")
        print()

        print("=" * 60)
        print("Voice control ready!")
        print("Say 'Hermes' followed by your command, or just speak directly.")
        print("Examples:")
        print("  'Hermes, create a file called notes.txt'")
        print("  'Search for Python files'")
        print("  'Find error handling code'")
        print("  'Write a function to calculate factorial'")
        print()
        print("Say 'stop' or 'quit' to exit.")
        print("=" * 60)
        print()

        self.running = True
        self._listen_loop()

    def _listen_loop(self) -> None:
        """Main listening loop."""
        while self.running:
            try:
                print("\n[Listening... say 'Hermes' or speak a command]")
                command = self.voice.listen_once(timeout=10.0)

                if command:
                    self._process_command(command)

            except KeyboardInterrupt:
                print("\nInterrupted by user")
                self.running = False
                break
            except Exception as e:
                print(f"Error: {e}")

        print("\nVoice control stopped.")

    def _process_command(self, command: VoiceCommand) -> None:
        """Process a voice command with security validation."""
        # Validate input first
        is_valid, validated_text, error = validate_command(command.text)
        if not is_valid:
            print(f"\n⚠️ Invalid command: {error}")
            return

        text = validated_text.lower().strip()
        print(f"\n>> Heard: '{validated_text}'")

        # Remove wake word if present
        for wake in self.voice.wake_words:
            if text.startswith(wake.lower()):
                text = text[len(wake):].strip()
                # Remove common fillers
                for filler in [',', 'please', 'can you', 'could you']:
                    text = text.replace(filler, '').strip()
                break

        if not text:
            print("(No command after wake word)")
            return

        # Check for special commands first
        for trigger, handler in self.special_commands.items():
            if trigger in text:
                handler(text)
                return

        # Otherwise, send to HERMES orchestrator
        print(f"\n[Sending to HERMES: '{text}']")
        self._run_hermes_task(validated_text)  # Use validated text, not raw input

    def _handle_create_file(self, text: str) -> None:
        """Handle file creation commands with security validation."""
        print("\n[FILE CREATION]")

        # Try to extract filename
        raw_filename = None
        for pattern in ['called ', 'named ', 'file ']:
            if pattern in text:
                parts = text.split(pattern)
                if len(parts) > 1 and parts[1].strip():
                    words = parts[1].split()
                    if words:
                        raw_filename = words[0].strip()
                        raw_filename = raw_filename.rstrip('.,!?')
                        break

        if not raw_filename:
            print("I heard you want to create a file, but I couldn't determine the filename.")
            print("Please say something like 'create a file called example.txt'")
            return

        # Security: Sanitize the filename
        filename = sanitize_filename(raw_filename)
        if not filename:
            print(f"❌ Invalid filename '{raw_filename}'.")
            print("Please use only letters, numbers, underscores, and hyphens.")
            return

        # Add .txt extension if no extension
        if '.' not in filename:
            filename += '.txt'

        # Security: Resolve and validate the path
        project_dir = Path.cwd().resolve()
        filepath = (project_dir / filename).resolve()

        # Ensure the file would be created within the project directory
        if not str(filepath).startswith(str(project_dir)):
            print("❌ Security error: Cannot create files outside project directory.")
            return

        # Create the file
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            content = f"# File created by HERMES Voice Control\n# Created: {timestamp}\n\n"

            with open(filepath, 'w') as f:
                f.write(content)

            print(f"✅ Created file: {filepath}")

        except OSError as e:
            print(f"❌ Failed to create file: {e}")

    def _handle_search(self, text: str) -> None:
        """Handle search commands."""
        print("\n[SEARCH]")

        # Extract search term
        search_term = text
        for prefix in ['search for ', 'find ', 'look for ']:
            if prefix in text:
                search_term = text.split(prefix, 1)[1].strip()
                break

        print(f"Searching for: '{search_term}'")

        # Use HERMES to handle the search
        task = f"Search for {search_term} in the current directory and subdirectories"
        self._run_hermes_task(task)

    def _handle_stop(self, text: str) -> None:
        """Handle stop/quit commands."""
        print("\nStopping voice control...")
        self.running = False

    def _handle_status(self, text: str) -> None:
        """Handle status check."""
        print("\n[STATUS]")
        status = self.hermes.status()
        print(f"Templates loaded: {status['templates_loaded']}")
        print(f"Registry stats: {status['registry_stats']}")

    def _run_hermes_task(self, task: str) -> None:
        """Run a task through HERMES."""
        try:
            result = self.hermes.run(task)
            print("\n" + "-" * 40)
            print(result.summary)
            print("-" * 40)

            if result.errors:
                print("Errors occurred:")
                for task_id, error in result.errors.items():
                    print(f"  {task_id}: {error}")

        except Exception as e:
            print(f"HERMES error: {e}")


def main():
    """Main entry point."""
    vc = VoiceControlledHERMES()
    vc.start()


if __name__ == "__main__":
    main()
