# Creating Plugins

Plugins are external programs that connect to Serial Studio's API server (TCP port 7777) to read live data and display custom visualizations.

## Architecture

```
Serial Studio                          Plugin (Python/native)
┌──────────┐    TCP 7777    ┌──────────────────────────┐
│ API      │◄──────────────►│ APIClient (socket)       │
│ Server   │  JSON-RPC 2.0  │ DataStore (thread-safe)  │
│          │  + broadcasts   │ App (tkinter GUI)        │
└──────────┘                └──────────────────────────┘
```

## Minimal Plugin

```python
#!/usr/bin/env python3
import json, socket, signal, sys, threading, time

try:
    import tkinter as tk
except ImportError:
    sys.exit("tkinter required")

class APIClient:
    def __init__(self, host="localhost", port=7777):
        self.host, self.port = host, port
        self.sock = None
        self.buffer = b""
        self.req_id = 0
        self.running = True
        self.connected = False
        self.on_frame = None
        self.on_event = None

    def connect(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2.0)
            s.connect((self.host, self.port))
            self.sock, self.buffer, self.connected = s, b"", True
            self.req_id += 1
            self.sock.sendall((json.dumps({
                "jsonrpc": "2.0", "id": self.req_id,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "clientInfo": {"name": "My Plugin", "version": "1.0.0"},
                    "capabilities": {},
                },
            }) + "\n").encode())
            return True
        except (ConnectionRefusedError, OSError):
            self.connected = False
            return False

    def run_loop(self):
        while self.running:
            if not self.connected:
                time.sleep(2); self.connect(); continue
            self.sock.settimeout(1.0)
            try:
                chunk = self.sock.recv(8192)
            except socket.timeout:
                continue
            except OSError:
                self.connected = False; continue
            if not chunk:
                self.connected = False; continue
            self.buffer += chunk
            while b"\n" in self.buffer:
                line, self.buffer = self.buffer.split(b"\n", 1)
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if "frames" in msg and self.on_frame:
                    for fw in msg["frames"]:
                        d = fw.get("data")
                        if d: self.on_frame(d)
                if "event" in msg and self.on_event:
                    self.on_event(msg["event"])

class DataStore:
    def __init__(self):
        self.lock = threading.Lock()
        self.current = {}
        self.frame_count = 0

    def ingest(self, frame):
        with self.lock:
            self.frame_count += 1
            for group in frame.get("groups", []):
                for ds in group.get("datasets", []):
                    title = ds.get("title", "")
                    try:
                        self.current[title] = float(ds.get("value", ""))
                    except (ValueError, TypeError):
                        pass

class App:
    def __init__(self, store, client):
        self.store, self.client = store, client
        self.root = tk.Tk()
        self.root.title("My Plugin")
        self.root.geometry("300x200")
        self.label = tk.Label(self.root, text="Waiting for data...")
        self.label.pack(expand=True)
        self._tick()

    def _tick(self):
        with self.store.lock:
            text = "\n".join(f"{k}: {v:.4f}" for k, v in self.store.current.items())
        self.label.config(text=text or "Waiting for data...")
        self.root.after(200, self._tick)

    def run(self):
        self.root.mainloop()

def main():
    store = DataStore()
    client = APIClient()
    client.on_frame = store.ingest

    signal.signal(signal.SIGTERM, lambda *_: setattr(client, "running", False))
    signal.signal(signal.SIGINT, lambda *_: setattr(client, "running", False))

    client.connect()
    threading.Thread(target=client.run_loop, daemon=True).start()
    App(store, client).run()

    client.running = False
    if client.sock: client.sock.close()

if __name__ == "__main__":
    main()
```

## Frame Data Format

```json
{"frames": [{"data": {"title": "...", "groups": [
    {"title": "Sensors", "datasets": [
        {"title": "Temperature", "value": "25.3", "units": "°C",
         "widgetMin": 0, "widgetMax": 100, "plotMin": 0, "plotMax": 150}
    ]}
]}}]}
```

Key dataset fields: `title`, `value`, `units`, `widgetMin`, `widgetMax`, `plotMin`, `plotMax`.

## Required Files

```
plugin/my-plugin/
  info.json       ← metadata
  plugin.py       ← Python entry point
  run.sh          ← Unix launcher (required for macOS)
  run.cmd          ← Windows launcher
  icon.svg        ← icon for start menu / toolbar
  README.md       ← description
```

### run.sh (required)

```sh
#!/bin/sh
cd "$(dirname "$0")"
exec python3 plugin.py "$@"
```

### run.cmd

```cmd
@echo off
cd /d "%~dp0"
python plugin.py %*
```

### info.json

```json
{
  "id": "my-plugin",
  "type": "plugin",
  "title": "My Plugin",
  "description": "What it does.",
  "author": "Your Name",
  "version": "1.0.0",
  "license": "MIT",
  "category": "Visualization",
  "icon": "icon.svg",
  "entry": "plugin.py",
  "runtime": "python3",
  "terminal": false,
  "files": ["info.json", "plugin.py", "icon.svg"],
  "platforms": {
    "darwin/*":  { "entry": "run.sh", "runtime": "", "files": ["run.sh"] },
    "linux/*":   { "entry": "run.sh", "runtime": "", "files": ["run.sh"] },
    "windows/*": { "entry": "run.cmd", "runtime": "", "files": ["run.cmd"] }
  }
}
```

## macOS tkinter Rules

These are critical — violating them causes invisible widgets or white artifacts:

1. **Use `ttk.Treeview` for tables** — never `tk.Canvas` with embedded Frames
2. **Hide scrollbars on macOS** — `if sys.platform != "darwin": vsb.pack(...)`
3. **Use `tk.Label` for buttons** — `tk.Button` ignores styling on macOS
4. **Avoid `ttk.Combobox`** in dark themes — dropdown is always white

See [CLAUDE.md](../CLAUDE.md) for detailed patterns and code examples.

## Lifecycle Events

The API broadcasts events when connection state changes:

```json
{"event": "connected"}
{"event": "disconnected"}
```

Listen for these alongside frame data in your `run_loop`.

## Next Steps

- [Plugin State Persistence](04-plugin-state.md)
- [Platform Support](05-platform-support.md)
