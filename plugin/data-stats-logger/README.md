# Data Statistics Logger

Real-time statistical analysis plugin for Serial Studio data streams.

## What it Does

Connects to Serial Studio's API server and monitors all incoming data frames. For each numeric field, it computes running statistics using [Welford's online algorithm](https://en.wikipedia.org/wiki/Algorithms_for_calculating_variance#Welford's_online_algorithm):

- **Sample count**
- **Minimum / Maximum**
- **Running mean**
- **Standard deviation**

## GUI Dashboard

When Tkinter is available, a live dashboard window shows all fields in a sortable table with real-time updates (250ms refresh). The dashboard uses Serial Studio's dark theme colors.

If Tkinter is not available (headless systems), the plugin falls back to console output every 5 seconds.

## HTML Report

On shutdown, the plugin generates a styled HTML report saved to your Serial Studio workspace folder (`~/Documents/Serial Studio/`). The report includes all computed statistics and session metadata (duration, frame count, frame rate).

## Requirements

- Python 3.6+
- Serial Studio API Server enabled (port 7777)
- Tkinter (optional, for GUI — included with most Python installations)

## Use Cases

- **Post-session analysis** — Get min/max/mean/stdev for every channel after a test run
- **Data validation** — Verify sensor outputs are within expected ranges
- **Performance monitoring** — Track frame rates and data throughput
