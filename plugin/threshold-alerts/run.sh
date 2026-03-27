#!/bin/sh
cd "$(dirname "$0")"

# Use a local venv to avoid system/homebrew Python restrictions
VENV_DIR=".venv"
if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
fi

# Activate venv and ensure grpcio is installed
. "$VENV_DIR/bin/activate"
python3 -c "import grpc" 2>/dev/null || pip install --quiet grpcio protobuf

exec python3 alerts.py "$@"
