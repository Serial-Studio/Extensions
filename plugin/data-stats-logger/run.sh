#!/bin/sh
cd "$(dirname "$0")"
exec python3 stats_logger.py "$@"
