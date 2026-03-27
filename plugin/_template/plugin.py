#!/usr/bin/env python3
"""
My Plugin — Template

A minimal Serial Studio plugin using gRPC for real-time frame streaming.
Displays live dataset values in a tkinter window.

Replace this with your own logic: custom widgets, data analysis, file export,
alerting, or anything else you need.
"""

import signal
import sys
import threading
import time

try:
    import tkinter as tk
    from tkinter import ttk
except ImportError:
    sys.exit("[Plugin] tkinter is required but not installed")

from grpc_client import GRPCClient

# ── Theme ────────────────────────────────────────────────────────────────────

BG      = "#0d1117"
SURFACE = "#161b22"
TEXT    = "#e6edf3"
DIM     = "#8b949e"
ACCENT  = "#58a6ff"

MONO = "Menlo" if sys.platform == "darwin" else \
       "Consolas" if sys.platform == "win32" else "Monospace"
SANS = "Helvetica Neue" if sys.platform == "darwin" else \
       "Segoe UI" if sys.platform == "win32" else "Sans"

# ── Data Store ───────────────────────────────────────────────────────────────

IDLE_SEC = 3

class DataStore:
    """Thread-safe store for the latest values from each dataset."""

    def __init__(self):
        self.lock = threading.Lock()
        self.fields = {}
        self.frame_count = 0
        self.last_frame_time = None

    @property
    def is_active(self):
        return (self.last_frame_time is not None
                and (time.time() - self.last_frame_time) < IDLE_SEC)

    def ingest(self, frame):
        with self.lock:
            self.frame_count += 1
            self.last_frame_time = time.time()
            for group in frame.get("groups", []):
                group_title = group.get("title", "")
                for ds in group.get("datasets", []):
                    title = ds.get("title", "")
                    units = ds.get("units", "")
                    key = f"{group_title}/{title}"
                    try:
                        value = float(ds.get("value", ""))
                    except (ValueError, TypeError):
                        continue
                    self.fields[key] = (value, units)


# ── Application ──────────────────────────────────────────────────────────────

class App:
    def __init__(self, store, client):
        self.store = store
        self.client = client

        # Window
        self.root = tk.Tk()
        self.root.title("My Plugin")
        self.root.configure(bg=BG)
        self.root.geometry("400x300")
        self.root.protocol("WM_DELETE_WINDOW", self._quit)

        # Status bar
        self.status = tk.Label(
            self.root, text="Connecting...",
            font=(SANS, 10), fg=DIM, bg=BG, anchor="w")
        self.status.pack(fill="x", padx=8, pady=(8, 0))

        # Data display
        self.text = tk.Text(
            self.root, font=(MONO, 11), fg=TEXT, bg=SURFACE,
            relief="flat", state="disabled", wrap="none",
            padx=8, pady=8)
        self.text.pack(fill="both", expand=True, padx=8, pady=8)

        self._tick()

    def _tick(self):
        """Update the display every 200ms."""
        with self.store.lock:
            lines = []
            for key, (value, units) in sorted(self.store.fields.items()):
                suffix = f" {units}" if units else ""
                lines.append(f"{key:30s}  {value:>12.4f}{suffix}")
            count = self.store.frame_count
            active = self.store.is_active

        # Update status
        if not self.client.connected:
            self.status.config(text="Disconnected — waiting for gRPC server...")
        elif not active:
            self.status.config(text=f"Connected — waiting for data ({count} frames)")
        else:
            self.status.config(text=f"Streaming — {count} frames received")

        # Update text
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(lines) if lines else "No data yet")
        self.text.config(state="disabled")

        self.root.after(200, self._tick)

    def _quit(self):
        self.client.stop()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


# ── Entry Point ──────────────────────────────────────────────────────────────

def main():
    store = DataStore()
    client = GRPCClient()
    client.on_frame = store.ingest

    signal.signal(signal.SIGTERM, lambda *_: client.stop())
    signal.signal(signal.SIGINT, lambda *_: client.stop())

    threading.Thread(target=client.run_loop, daemon=True).start()

    app = App(store, client)
    app.run()
    client.stop()

if __name__ == "__main__":
    main()
