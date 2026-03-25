# Threshold Alerts

Real-time threshold monitoring with visual and audio alerts.

## What it Does

Monitors all data fields and triggers alerts when values exceed configurable high/low thresholds. Perfect for unattended testing, environmental monitoring, and safety-critical data watchdog scenarios.

## Features

- **Per-field thresholds** — Set independent high and low limits for each data field
- **Double-click to configure** — Click the Low or High column to set a threshold
- **Color-coded status** — Green (OK), Red (HIGH/LOW exceeded)
- **System bell** — Audio notification on threshold breach
- **Alert log** — Timestamped log of all triggered events with field name, value, and direction
- **Alert counter** — Per-field alert count for identifying noisy channels

## Requirements

- Python 3.6+
- Serial Studio API Server enabled (port 7777)
- Tkinter (optional, for GUI)

## Use Cases

- **Burn-in testing** — Leave running overnight, check alert log in the morning
- **Environmental monitoring** — Alert when temperature/humidity/pressure leaves safe range
- **Safety watchdog** — Catch out-of-range values in real-time during active testing
- **Quality control** — Monitor production test limits across multiple measurement points
