"""
HERMES cross-platform setup.

Creates the virtual environment, installs dependencies, and prints the
MCP registration command for the current platform.

Usage:
    python scripts/setup.py
"""

import os
import subprocess
import sys
import venv
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VENV_DIR = PROJECT_ROOT / "venv"
IS_WINDOWS = os.name == "nt"


def venv_python(venv_dir: Path) -> Path:
    """Interpreter path inside a venv (Scripts/ on Windows, bin/ elsewhere)."""
    return venv_dir / ("Scripts" if IS_WINDOWS else "bin") / ("python.exe" if IS_WINDOWS else "python")


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass

    print(f"HERMES setup - {sys.platform} (Python {sys.version.split()[0]})")
    print(f"Project root: {PROJECT_ROOT}")

    py = venv_python(VENV_DIR)
    if py.exists():
        print(f"venv already present: {py}")
    else:
        print(f"Creating venv at {VENV_DIR} ...")
        venv.EnvBuilder(with_pip=True).create(VENV_DIR)
        if not py.exists():
            print(f"ERROR: venv created but interpreter missing at {py}")
            return 1

    print("Installing requirements ...")
    result = subprocess.run(
        [str(py), "-m", "pip", "install", "-r", str(PROJECT_ROOT / "requirements.txt")],
        cwd=str(PROJECT_ROOT),
    )
    if result.returncode != 0:
        print("ERROR: dependency install failed")
        return result.returncode

    print("Running test suite ...")
    result = subprocess.run([str(py), "-m", "pytest", "tests/", "-q"], cwd=str(PROJECT_ROOT))
    if result.returncode != 0:
        print("WARNING: tests did not pass cleanly")

    print()
    print("Setup complete. Register the MCP server with:")
    print()
    if IS_WINDOWS:
        print(f'  claude mcp add hermes -e HERMES_MODE=mcp -e PYTHONPATH={PROJECT_ROOT} '
              f'-- {py} {PROJECT_ROOT / "mcp_server.py"}')
    else:
        print(f'  claude mcp add hermes \\\n'
              f'    -e HERMES_MODE=mcp -e PYTHONPATH={PROJECT_ROOT} \\\n'
              f'    -- {py} {PROJECT_ROOT / "mcp_server.py"}')
    print()
    activate = VENV_DIR / ("Scripts\\activate" if IS_WINDOWS else "bin/activate")
    print(f"Activate the venv with: {'' if IS_WINDOWS else 'source '}{activate}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
