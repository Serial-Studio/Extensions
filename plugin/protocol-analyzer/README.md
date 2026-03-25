# Protocol Analyzer

A mini protocol analyzer for debugging serial data frames.

## What it Does

Captures raw data events from the Serial Studio API and presents them in a Wireshark-style interface. When Serial Studio's console isn't enough to debug frame timing, binary content, or parsing issues, this plugin gives you the low-level visibility you need.

## Features

- **Frame list.** Scrolling table showing frame number, timestamp, size, inter-frame delta, field count, and data preview.
- **Hex dump.** Click any frame to see a formatted hex + ASCII dump.
- **Decoded fields.** Per-field decoded values for the selected frame.
- **Timing analysis.** Inter-frame timing (delta in milliseconds) for spotting dropped frames or jitter.
- **Statistics.** Frame rate, byte rate, and average inter-frame delta in the header.

## Requirements

- Python 3.6+
- Serial Studio API Server enabled (port 7777)
- Tkinter (optional, for GUI)

## Use Cases

- **Protocol debugging.** See raw bytes when frames aren't parsing correctly.
- **Timing analysis.** Identify dropped frames, jitter, or baud rate mismatches.
- **Frame size verification.** Confirm frame lengths match your protocol specification.
- **Integration testing.** Verify data integrity between embedded device and Serial Studio.
