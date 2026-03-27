#!/bin/sh
cd "$(dirname "$0")"

VENV_DIR=".venv"
if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
fi

. "$VENV_DIR/bin/activate"
python3 -c "import grpc" 2>/dev/null || pip install --quiet grpcio protobuf

exec python3 live_table.py "$@"
