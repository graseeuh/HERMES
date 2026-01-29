"""
HERMES Voice Control
Voice-activated interface for HERMES agent orchestration.

Usage:
    python voice_control.py

Say "Hermes" to activate, then speak your command.
"""

import os
import sys
from pathlib import Path
from datetime import datetime

from main import HERMES
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
        """Process a voice command."""
        text = command.text.lower().strip()
        print(f"\n>> Heard: '{command.text}'")

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
        self._run_hermes_task(command.text)

    def _handle_create_file(self, text: str) -> None:
        """Handle file creation commands."""
        print("\n[FILE CREATION]")

        # Try to extract filename
        filename = None
        for pattern in ['called ', 'named ', 'file ']:
            if pattern in text:
                parts = text.split(pattern)
                if len(parts) > 1 and parts[1].strip():
                    # Get the word after the pattern
                    words = parts[1].split()
                    if words:
                        filename = words[0].strip()
                        # Clean up common artifacts
                        filename = filename.rstrip('.,!?')
                        break

        if not filename:
            print("I heard you want to create a file, but I couldn't determine the filename.")
            print("Please say something like 'create a file called example.txt'")
            return

        # Add .txt extension if no extension
        if '.' not in filename:
            filename += '.txt'

        filepath = Path.cwd() / filename

        # Create the file
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            content = f"# File created by HERMES Voice Control\n# Created: {timestamp}\n\n"

            with open(filepath, 'w') as f:
                f.write(content)

            print(f"Created file: {filepath}")
            print("File created successfully!")

        except Exception as e:
            print(f"Failed to create file: {e}")

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
