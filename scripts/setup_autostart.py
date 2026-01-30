"""
HERMES Auto-Start Setup
Creates a Windows Task Scheduler task to run HERMES on login.

Usage:
    python scripts/setup_autostart.py
    python scripts/setup_autostart.py --remove

Requires administrator privileges to create the scheduled task.
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path


TASK_NAME = "HERMES_Startup_Greeter"

# Security: Pattern to detect potentially dangerous characters in paths
UNSAFE_PATH_PATTERN = re.compile(r'[;&|`$<>]')


def validate_path(path: str, description: str) -> bool:
    """
    Validate a path for security.

    Args:
        path: The path to validate
        description: Description for error messages

    Returns:
        True if valid, raises ValueError if invalid
    """
    if UNSAFE_PATH_PATTERN.search(path):
        raise ValueError(f"Invalid {description}: contains unsafe characters")

    # Ensure path is absolute and normalized
    resolved = Path(path).resolve()
    if not resolved.exists():
        raise ValueError(f"Invalid {description}: path does not exist")

    return True


def get_python_path() -> str:
    """Get the path to pythonw.exe (runs without console window) from venv."""
    # Check for venv in HERMES directory - use pythonw.exe for background execution
    project_root = Path(__file__).parent.parent
    venv_pythonw = project_root / "venv" / "Scripts" / "pythonw.exe"

    if venv_pythonw.exists():
        return str(venv_pythonw)

    # Try regular python.exe from venv as fallback
    venv_python = project_root / "venv" / "Scripts" / "python.exe"
    if venv_python.exists():
        print("Warning: pythonw.exe not found, using python.exe (console will be visible)")
        return str(venv_python)

    # Fall back to current interpreter's directory
    current_dir = Path(sys.executable).parent
    pythonw = current_dir / "pythonw.exe"
    if pythonw.exists():
        return str(pythonw)

    print("Warning: pythonw.exe not found, using python.exe (console will be visible)")
    return sys.executable


def get_script_path() -> str:
    """Get the path to startup_greeter.py."""
    project_root = Path(__file__).parent.parent
    return str(project_root / "startup_greeter.py")


def get_working_directory() -> str:
    """Get the HERMES project directory."""
    return str(Path(__file__).parent.parent)


def create_task(delay_seconds: int = 30) -> bool:
    """
    Create a Windows Task Scheduler task for HERMES startup.

    Args:
        delay_seconds: Delay after login before starting (default: 30)

    Returns:
        True if successful, False otherwise
    """
    python_path = get_python_path()
    script_path = get_script_path()
    working_dir = get_working_directory()

    # Security: Validate all paths before using in subprocess
    try:
        validate_path(python_path, "Python path")
        validate_path(script_path, "script path")
        validate_path(working_dir, "working directory")
    except ValueError as e:
        print(f"Security error: {e}")
        return False

    print(f"Python: {python_path}")
    print(f"Script: {script_path}")
    print(f"Working Directory: {working_dir}")
    print(f"Delay: {delay_seconds}s after login")
    print()

    # Create the scheduled task using schtasks
    # The task will run on user logon with a delay
    cmd = [
        "schtasks", "/create",
        "/tn", TASK_NAME,
        "/tr", f'"{python_path}" "{script_path}"',
        "/sc", "onlogon",
        "/delay", f"0000:{delay_seconds // 60:02d}:{delay_seconds % 60:02d}",
        "/f",  # Force overwrite if exists
        "/rl", "highest",  # Run with highest privileges
    ]

    print(f"Creating scheduled task '{TASK_NAME}'...")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            shell=False  # Secure: prevents command injection
        )

        if result.returncode == 0:
            print("Task created successfully!")
            print()
            print("The task will run automatically on login.")
            print("To test it manually, run:")
            print(f"  schtasks /run /tn {TASK_NAME}")
            print()
            print("To view the task:")
            print(f"  schtasks /query /tn {TASK_NAME}")
            return True
        else:
            print(f"Error creating task: {result.stderr}")
            if "Access is denied" in result.stderr:
                print("\nTry running this script as Administrator.")
            return False

    except (OSError, subprocess.SubprocessError) as e:
        print(f"Error running schtasks: {e}")
        return False


def remove_task() -> bool:
    """
    Remove the HERMES startup task.

    Returns:
        True if successful, False otherwise
    """
    cmd = ["schtasks", "/delete", "/tn", TASK_NAME, "/f"]

    print(f"Removing scheduled task '{TASK_NAME}'...")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            shell=False  # Secure: prevents command injection
        )

        if result.returncode == 0:
            print("Task removed successfully!")
            return True
        else:
            if "cannot find" in result.stderr.lower() or "does not exist" in result.stderr.lower():
                print("Task does not exist.")
            else:
                print(f"Error removing task: {result.stderr}")
            return False

    except (OSError, subprocess.SubprocessError) as e:
        print(f"Error running schtasks: {e}")
        return False


def check_task() -> bool:
    """
    Check if the HERMES startup task exists.

    Returns:
        True if task exists, False otherwise
    """
    cmd = ["schtasks", "/query", "/tn", TASK_NAME]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            shell=False  # Secure: prevents command injection
        )
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError) as e:
        print(f"Error checking task: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Setup HERMES to run on Windows login"
    )
    parser.add_argument(
        "--remove",
        action="store_true",
        help="Remove the startup task instead of creating it"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if the task exists"
    )
    parser.add_argument(
        "--delay",
        type=int,
        default=30,
        help="Delay in seconds after login (default: 30)"
    )
    args = parser.parse_args()

    print()
    print("  ╦ ╦╔═╗╦═╗╔╦╗╔═╗╔═╗")
    print("  ╠═╣║╣ ╠╦╝║║║║╣ ╚═╗")
    print("  ╩ ╩╚═╝╩╚═╩ ╩╚═╝╚═╝")
    print("  Auto-Start Setup")
    print()

    if args.check:
        if check_task():
            print(f"Task '{TASK_NAME}' exists.")
            return 0
        else:
            print(f"Task '{TASK_NAME}' does not exist.")
            return 1

    if args.remove:
        success = remove_task()
        return 0 if success else 1

    # Check prerequisites
    print("Checking prerequisites...")

    python_path = get_python_path()
    if not Path(python_path).exists():
        print(f"Error: Python not found at {python_path}")
        return 1
    print(f"  Python: OK")

    script_path = get_script_path()
    if not Path(script_path).exists():
        print(f"Error: startup_greeter.py not found at {script_path}")
        return 1
    print(f"  Script: OK")

    # Check if face encodings exist
    from sensors.face_recognition_interface import FaceRecognitionInterface
    face_rec = FaceRecognitionInterface()
    enrolled = face_rec.get_enrolled_names()
    if not enrolled:
        print()
        print("Warning: No faces enrolled yet!")
        print("Run this first: python scripts/enroll_face.py --name \"YourName\"")
        print()

        response = input("Continue anyway? (y/n): ").lower().strip()
        if response != 'y':
            print("Aborted.")
            return 1
    else:
        print(f"  Enrolled faces: {', '.join(enrolled)}")

    print()

    # Create the task
    success = create_task(delay_seconds=args.delay)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
