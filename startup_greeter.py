"""
HERMES Startup Greeter
Runs facial recognition on boot, greets the user by name, then starts voice assistant.

Usage:
    python startup_greeter.py
    python startup_greeter.py --timeout 30
    python startup_greeter.py --camera 0 --timeout 15
"""

import argparse
import sys
import time
from pathlib import Path

import cv2
import pyttsx3

from sensors.face_recognition_interface import FaceRecognitionInterface
from hermes_listener import HermesListener


class StartupGreeter:
    """
    Handles facial recognition greeting on system startup.
    After greeting, transitions to the HERMES voice assistant.
    """

    def __init__(
        self,
        camera_index: int = 0,
        timeout: float = 30.0,
        mic_index: int = None
    ):
        """
        Initialize the startup greeter.

        Args:
            camera_index: Which camera to use for face recognition
            timeout: How long to attempt recognition before giving up (seconds)
            mic_index: Microphone index for voice assistant (None for default)
        """
        self.camera_index = camera_index
        self.timeout = timeout
        self.mic_index = mic_index

        # Initialize TTS engine
        self.tts = pyttsx3.init()
        self.tts.setProperty('rate', 150)  # Speaking rate

        # Initialize face recognition
        self.face_rec = FaceRecognitionInterface()

        # Camera will be initialized when needed
        self.cap = None

    def _init_camera(self) -> bool:
        """Initialize the camera."""
        self.cap = cv2.VideoCapture(self.camera_index)

        if not self.cap.isOpened():
            print(f"Error: Could not open camera {self.camera_index}")
            return False

        # Set camera properties
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        return True

    def _release_camera(self) -> None:
        """Release the camera."""
        if self.cap is not None:
            self.cap.release()
            self.cap = None

    def speak(self, text: str) -> None:
        """Speak text using TTS."""
        print(f"[TTS] {text}")
        self.tts.say(text)
        self.tts.runAndWait()

    def run_recognition(self) -> str:
        """
        Run the face recognition loop.

        Returns:
            Name of recognized person, or None if timeout/no match
        """
        if not self._init_camera():
            return None

        enrolled = self.face_rec.get_enrolled_names()
        if not enrolled:
            print("No faces enrolled. Run: python scripts/enroll_face.py --name \"YourName\"")
            self._release_camera()
            return None

        print(f"Looking for: {', '.join(enrolled)}")
        print(f"Timeout: {self.timeout}s")
        print("Press Q to skip recognition...")

        start_time = time.time()
        recognized_name = None

        try:
            while time.time() - start_time < self.timeout:
                ret, frame = self.cap.read()
                if not ret:
                    print("Error reading camera frame")
                    time.sleep(0.1)
                    continue

                # Convert BGR to RGB for face_recognition
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # Try to recognize
                name = self.face_rec.recognize_face(rgb_frame)

                if name:
                    recognized_name = name
                    break

                # Show preview window
                elapsed = time.time() - start_time
                remaining = self.timeout - elapsed

                # Add status overlay
                display = frame.copy()
                cv2.putText(
                    display, f"HERMES - Looking for you... ({remaining:.1f}s)",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2
                )
                cv2.putText(
                    display, "Press Q to skip",
                    (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1
                )

                cv2.imshow("HERMES Startup", display)

                # Check for Q key
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    print("\nSkipping recognition...")
                    break

                # Small delay to reduce CPU usage
                time.sleep(0.1)

        finally:
            self._release_camera()
            cv2.destroyAllWindows()

        return recognized_name

    def greet(self, name: str) -> None:
        """Greet the recognized user."""
        greeting = f"Hello {name}"
        self.speak(greeting)

    def run(self) -> None:
        """
        Main entry point - runs recognition, greeting, and starts voice assistant.
        """
        print()
        print("  H E R M E S")
        print("  Startup Greeter")
        print()

        # Run face recognition
        print("Starting facial recognition...")
        recognized = self.run_recognition()

        if recognized:
            print(f"\nRecognized: {recognized}")
            self.greet(recognized)
        else:
            print("\nNo face recognized within timeout")
            self.speak("Hello")

        # Transition to voice assistant
        print("\nStarting voice assistant...")
        time.sleep(0.5)

        listener = HermesListener(mic_index=self.mic_index)
        listener.start()


def main():
    parser = argparse.ArgumentParser(description="HERMES Startup Greeter")
    parser.add_argument(
        "--camera",
        type=int,
        default=0,
        help="Camera index to use (default: 0)"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Recognition timeout in seconds (default: 30)"
    )
    parser.add_argument(
        "--mic",
        type=int,
        default=None,
        help="Microphone index for voice assistant"
    )
    args = parser.parse_args()

    greeter = StartupGreeter(
        camera_index=args.camera,
        timeout=args.timeout,
        mic_index=args.mic
    )
    greeter.run()


if __name__ == "__main__":
    main()
