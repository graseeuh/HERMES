"""
HERMES Background Listener
Continuously listens for "Hey Hermes" wake word, then processes commands.
Enhanced with local Whisper STT, Ollama LLM responses, and TTS output.

Usage:
    python hermes_listener.py
    python hermes_listener.py --no-tts      # Disable spoken responses
    python hermes_listener.py --no-llm      # Disable LLM response generation
    python hermes_listener.py --backend google  # Use Google STT instead of Whisper

Runs in background, always listening. Say "Hey Hermes" to activate.
"""

import re
import sys
import time
from datetime import datetime
from typing import Optional, Tuple

from main import HERMES


# ============================================================================
# Input Validation for Voice Commands
# ============================================================================

# Maximum allowed command length (prevents buffer overflow attacks)
MAX_COMMAND_LENGTH = 500

# Patterns that might indicate malicious input
DANGEROUS_PATTERNS = [
    r';\s*(rm|del|format|shutdown|reboot)',  # Command chaining with dangerous commands
    r'\$\(',  # Command substitution
    r'`[^`]+`',  # Backtick command substitution
    r'\|\s*(bash|sh|cmd|powershell)',  # Piping to shells
    r'>\s*/etc/',  # Writing to system directories (Unix)
    r'>\s*C:\\Windows',  # Writing to system directories (Windows)
    r'__(import|class|bases|subclasses)__',  # Python introspection attacks
    r'eval\s*\(',  # Eval injection
    r'exec\s*\(',  # Exec injection
    r'os\.(system|popen|exec)',  # OS command execution
    r'subprocess\.',  # Subprocess calls
]

# Compiled patterns for efficiency
_DANGEROUS_REGEX = re.compile('|'.join(DANGEROUS_PATTERNS), re.IGNORECASE)


def validate_voice_input(text: str) -> Tuple[bool, str, str]:
    """
    Validate voice command input for security.

    Args:
        text: The raw voice command text

    Returns:
        Tuple of (is_valid, sanitized_text, error_message)
        If is_valid is False, error_message explains why
    """
    if not text:
        return False, "", "Empty command"

    if not isinstance(text, str):
        return False, "", "Invalid input type"

    # Check length
    if len(text) > MAX_COMMAND_LENGTH:
        return False, "", f"Command too long ({len(text)} > {MAX_COMMAND_LENGTH} chars)"

    # Check for dangerous patterns
    if _DANGEROUS_REGEX.search(text):
        return False, "", "Command contains potentially unsafe patterns"

    # Basic sanitization - remove control characters but keep printable text
    sanitized = ''.join(char for char in text if char.isprintable() or char in '\n\t')
    sanitized = sanitized.strip()

    if not sanitized:
        return False, "", "Command empty after sanitization"

    return True, sanitized, ""
from sensors.voice_interface import VoiceInterface, VoiceCommand
from sensors.tts_interface import TTSInterface, TTSConfig
from integration.claude_llm_client import ClaudeLLMClient, ClaudeLLMConfig


class HermesListener:
    """
    Always-on listener for HERMES.
    Waits for wake word, then processes voice commands.
    Enhanced with TTS output and LLM-powered contextual responses.
    """

    WAKE_WORDS = ["hey hermes", "hermes", "hey hermès", "ok hermes"]

    def __init__(
        self,
        mic_index: int = None,
        enable_tts: bool = True,
        enable_llm: bool = True,
        stt_backend: str = "whisper"
    ):
        """
        Initialize the listener.

        Args:
            mic_index: Microphone index to use (None for default)
            enable_tts: Enable text-to-speech responses
            enable_llm: Enable LLM-powered contextual responses
            stt_backend: Speech recognition backend ('whisper' or 'google')
        """
        print("Initializing HERMES...")
        self.hermes = HERMES()
        self.voice = VoiceInterface(wake_words=self.WAKE_WORDS, backend=stt_backend)
        self.mic_index = mic_index
        self.running = False

        # TTS integration
        self.enable_tts = enable_tts
        self.tts: Optional[TTSInterface] = None
        if enable_tts:
            print("Initializing TTS...")
            self.tts = TTSInterface()
            if not self.tts.initialize():
                print("Warning: TTS initialization failed. Spoken responses disabled.")
                self.enable_tts = False

        # Claude LLM integration (with usage limits to prevent overage)
        self.enable_llm = enable_llm
        self.llm: Optional[ClaudeLLMClient] = None
        if enable_llm:
            print("Checking Claude API availability...")
            self.llm = ClaudeLLMClient()
            if not self.llm.check_availability():
                print("Warning: Claude API not available. Contextual responses disabled.")
                self.enable_llm = False
            else:
                print(self.llm.get_usage_summary())

        # Special commands
        self.exit_commands = ["stop listening", "goodbye", "exit", "quit", "stop"]

    def start(self) -> None:
        """Start the always-on listener."""
        self._print_banner()

        # Set up microphone
        if self.mic_index is not None:
            self.voice.set_microphone(self.mic_index)
            print(f"Using microphone index: {self.mic_index}")
        else:
            self.voice.set_microphone()
            print("Using default microphone")

        # Calibrate
        print("\nCalibrating for ambient noise (stay quiet)...")
        self.voice.calibrate(duration=2.0)

        print("\n" + "=" * 50)
        print("HERMES is now listening!")
        print(f"  STT Backend: {self.voice.current_backend}")
        print(f"  TTS Enabled: {self.enable_tts}")
        print(f"  LLM Enabled: {self.enable_llm}")
        print("Say 'Hey Hermes' followed by your command.")
        print("Say 'Stop listening' to exit.")
        print("=" * 50 + "\n")

        self.running = True
        self._listen_loop()

    def _speak(self, text: str) -> None:
        """Speak text if TTS is enabled."""
        if self.tts and self.enable_tts:
            self.tts.speak(text)
        else:
            print(f"[Would say] {text}")

    def _generate_response(self, user_input: str, task_result: str = None) -> Optional[str]:
        """Generate contextual response using Claude API."""
        if self.llm and self.enable_llm:
            return self.llm.generate_contextual_response(user_input, task_result)
        return None

    def _print_banner(self) -> None:
        """Print startup banner."""
        print()
        print("  H E R M E S")
        print("  Voice-Activated Assistant")
        print()

    def _listen_loop(self) -> None:
        """Main listening loop - always on."""
        while self.running:
            try:
                # Listen for wake word (short timeout, keeps checking)
                self._wait_for_wake_word()

                if not self.running:
                    break

                # Wake word detected - now listen for command
                print("\n🎤 Yes? I'm listening...")
                command = self.voice.listen_once(timeout=5.0)

                if command:
                    should_exit = self._process_command(command)
                    if should_exit:
                        break
                else:
                    print("I didn't catch that. Say 'Hey Hermes' to try again.")

                print()  # Blank line before next listen cycle

            except KeyboardInterrupt:
                print("\n\nInterrupted. Shutting down...")
                break
            except Exception as e:
                print(f"Error: {e}")
                time.sleep(1)  # Prevent rapid error loops

        self._shutdown()

    def _wait_for_wake_word(self) -> None:
        """Listen until wake word is detected."""
        while self.running:
            # Show subtle indicator that we're listening
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"\r[{timestamp}] Waiting for 'Hey Hermes'...", end="", flush=True)

            result = self.voice.listen_once(timeout=3.0)

            if result and self._contains_wake_word(result.text):
                print()  # New line after the waiting message
                self._speak("Yes?")  # Acknowledge wake word
                return

    def _contains_wake_word(self, text: str) -> bool:
        """Check if text contains wake word."""
        text_lower = text.lower()
        for wake in self.WAKE_WORDS:
            if wake in text_lower:
                return True
        return False

    def _process_command(self, command: VoiceCommand) -> bool:
        """
        Process a voice command.

        Args:
            command: The recognized command

        Returns:
            True if should exit, False otherwise
        """
        # Validate and sanitize input
        is_valid, text, error = validate_voice_input(command.text)
        if not is_valid:
            print(f"⚠️ Invalid command: {error}")
            self._speak("Sorry, I couldn't process that command.")
            return False

        text_lower = text.lower()

        print(f"Heard: \"{text}\"")

        # Check for exit commands
        for exit_cmd in self.exit_commands:
            if exit_cmd in text_lower:
                self._speak("Goodbye!")
                self.running = False
                return True

        # Handle special commands
        if self._handle_special_command(text_lower, text):
            return False

        # Send to HERMES orchestrator
        print(f"\nProcessing with HERMES...")
        result = self._execute_hermes_task(text)

        # Generate and speak contextual response
        if result:
            response = self._generate_response(text, result.summary)
            if response:
                self._speak(response)
            else:
                # Fallback simple acknowledgment
                self._speak("Task completed.")

        return False

    def _handle_special_command(self, text_lower: str, original_text: str) -> bool:
        """
        Handle special commands.

        Returns:
            True if handled, False if should pass to HERMES
        """
        # File creation
        if any(phrase in text_lower for phrase in ["create file", "make file", "new file"]):
            self._create_file(text_lower)
            return True

        # Status check
        if "status" in text_lower:
            self._show_status()
            return True

        # Time
        if "what time" in text_lower or "current time" in text_lower:
            now = datetime.now().strftime("%I:%M %p")
            print(f"The time is {now}")
            self._speak(f"The time is {now}")
            return True

        # Help
        if "help" in text_lower or "what can you do" in text_lower:
            self._show_help()
            return True

        return False

    def _sanitize_filename(self, filename: str) -> Optional[str]:
        """
        Sanitize a filename for security.

        Args:
            filename: Raw filename from voice input

        Returns:
            Sanitized filename or None if invalid
        """
        if not filename:
            return None

        # Remove any path separators (prevent directory traversal)
        filename = filename.replace('/', '').replace('\\', '')
        filename = filename.replace('..', '')

        # Remove other dangerous characters
        # Allow only alphanumeric, underscore, hyphen, dot
        sanitized = re.sub(r'[^a-zA-Z0-9_\-.]', '_', filename)

        # Remove leading dots (hidden files) and multiple dots
        sanitized = sanitized.lstrip('.')
        sanitized = re.sub(r'\.{2,}', '.', sanitized)

        # Limit length
        if len(sanitized) > 100:
            sanitized = sanitized[:100]

        # Must have something left
        if not sanitized or sanitized == '.':
            return None

        return sanitized

    def _create_file(self, text: str) -> None:
        """Create a file from voice command with security validation."""
        from pathlib import Path

        # Extract filename
        filename = None
        for pattern in ['called ', 'named ', 'file ']:
            if pattern in text:
                parts = text.split(pattern)
                if len(parts) > 1 and parts[1].strip():
                    words = parts[1].split()
                    if words:
                        filename = words[0].strip()
                        filename = filename.rstrip('.,!?')
                        break

        if not filename:
            print("❓ What should I name the file?")
            response = self.voice.listen_once(timeout=5.0)
            if response:
                filename = response.text.strip().replace(" ", "_")
            else:
                print("Didn't catch the filename. Please try again.")
                return

        # Security: Sanitize the filename
        filename = self._sanitize_filename(filename)
        if not filename:
            print("❌ Invalid filename. Please use only letters, numbers, and underscores.")
            self._speak("That filename isn't valid. Please try again.")
            return

        # Add extension if needed
        if '.' not in filename:
            filename += '.txt'

        # Security: Resolve path and verify it's within current directory
        project_dir = Path.cwd().resolve()
        filepath = (project_dir / filename).resolve()

        # Verify the file would be created within the project directory
        if not str(filepath).startswith(str(project_dir)):
            print("❌ Security error: Cannot create files outside project directory.")
            self._speak("I can't create files outside the project folder.")
            return

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        try:
            with open(filepath, 'w') as f:
                f.write(f"# Created by HERMES Voice Control\n")
                f.write(f"# {timestamp}\n\n")

            print(f"✅ Created: {filepath}")
            self._speak(f"Created file {filename}")
        except OSError as e:
            print(f"❌ Failed to create file: {e}")
            self._speak("Sorry, I couldn't create that file.")

    def _show_status(self) -> None:
        """Show HERMES status."""
        status = self.hermes.status()
        print("\n📊 HERMES Status:")
        print(f"   Templates: {', '.join(status['templates_loaded'])}")
        stats = status['registry_stats']
        print(f"   Agents: {stats['total_agents']} total, {stats['active_agents']} active")

    def _show_help(self) -> None:
        """Show help information."""
        print("\n📖 I can help you with:")
        print("   • 'Create a file called [name]' - Make a new file")
        print("   • 'Search for [something]' - Search the codebase")
        print("   • 'Find [something]' - Find files or code")
        print("   • 'Write [code description]' - Generate code")
        print("   • 'Status' - Show system status")
        print("   • 'Stop listening' - Exit HERMES")

    def _execute_hermes_task(self, task: str):
        """
        Execute a task through HERMES.

        Returns:
            ExecutionResult or None if error occurred
        """
        try:
            result = self.hermes.run(task)

            print("\n" + "-" * 40)
            print(result.summary)
            print("-" * 40)

            if result.agents_buffed:
                print(f"Reused {len(result.agents_buffed)} existing agent(s)")

            return result

        except Exception as e:
            print(f"Error: {e}")
            self._speak("Sorry, I encountered an error processing that request.")
            return None

    def _shutdown(self) -> None:
        """Clean shutdown."""
        print("\nShutting down HERMES listener...")
        self.voice.cleanup()
        if self.tts:
            self.tts.cleanup()
        if self.llm:
            print(self.llm.get_usage_summary())
        print("Done.")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="HERMES Voice Listener")
    parser.add_argument(
        "--mic",
        type=int,
        default=None,
        help="Microphone index to use (run test_voice.py to see available)"
    )
    parser.add_argument(
        "--no-tts",
        action="store_true",
        help="Disable text-to-speech responses"
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Disable LLM-powered contextual responses"
    )
    parser.add_argument(
        "--backend",
        type=str,
        choices=["whisper", "google"],
        default="whisper",
        help="Speech recognition backend (default: whisper)"
    )
    args = parser.parse_args()

    listener = HermesListener(
        mic_index=args.mic,
        enable_tts=not args.no_tts,
        enable_llm=not args.no_llm,
        stt_backend=args.backend
    )
    listener.start()


if __name__ == "__main__":
    main()
