# Live Data Table

A clean, sortable table view of all current dataset values with sparkline history.

## What it Does

Fills the gap between Serial Studio's visual widget dashboard (gauges, plots, compass) and the raw console output. When you have many data channels and just need to see every value at once — like a rack of lab multimeters — this is the plugin for you.

## Features

- **All fields in one view** — Every dataset field shown in a single table
- **Live values** — Updates every 200ms
- **Sparkline history** — Text-based sparkline (`▁▂▃▄▅▆▇█`) showing recent value trends
- **Min/Max tracking** — Running minimum and maximum for each field
- **Units display** — Shows units from your project configuration

## Requirements

- Python 3.6+
- Serial Studio API Server enabled (port 7777)
- Tkinter (optional, for GUI)

## Use Cases

- **Quick overview** — See all telemetry channels at a glance during development
- **Multi-sensor monitoring** — Monitor 20+ channels simultaneously without dashboard setup
- **Spot-checking** — Verify all values are in expected ranges during hardware bring-up
