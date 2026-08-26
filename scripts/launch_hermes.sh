#!/usr/bin/env bash
# macOS/Linux equivalent of launch_hermes.bat
cd "$(dirname "$0")/.." || exit 1
source venv/bin/activate
exec claude
