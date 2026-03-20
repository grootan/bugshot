#!/bin/bash
# Bugshot — setup (delegates to install.py)
# Run: bash install.sh
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
python3 "$SCRIPT_DIR/install.py"
