#!/bin/sh
cd "$(dirname "$0")"
exec python3 live_table.py "$@"
