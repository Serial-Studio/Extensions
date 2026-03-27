# Creating Plugins

Plugins are external programs that connect to Serial Studio via **gRPC** (port 8888) for high-performance binary frame streaming. They can read live data, compute statistics, and display custom visualizations.

## Architecture

```
Serial Studio                          Plugin (Python/native)
┌──────────┐   gRPC 8888   ┌──────────────────────────┐
│ gRPC     │◄─────────────►│ GRPCClient (streaming)   │
│ Server   │  protobuf      │ DataStore (thread-safe)  │
│          │  binary frames  │ App (tkinter GUI)        │
└──────────┘                └──────────────────────────┘
```

The gRPC server starts automatically when the API server is enabled. Plugins use a `GRPCClient` wrapper that handles connection, reconnection, and frame streaming.

## Minimal Plugin

A complete working plugin with gRPC streaming and a tkinter GUI:

```python
#!/usr/bin/env python3
"""My Plugin — minimal gRPC example."""

import signal, sys, threading, time

try:
    import tkinter as tk
except ImportError:
    sys.exit("tkinter required")

from grpc_client import GRPCClient

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
    client = GRPCClient()
    client.on_frame = store.ingest

    signal.signal(signal.SIGTERM, lambda *_: client.stop())
    signal.signal(signal.SIGINT, lambda *_: client.stop())

    threading.Thread(target=client.run_loop, daemon=True).start()
    App(store, client).run()
    client.stop()

if __name__ == "__main__":
    main()
```

## GRPCClient API

The `grpc_client.py` module provides a drop-in client:

| Property/Method | Description |
|---|---|
| `on_frame` | Callback `(frame_dict) → None`. Set before calling `run_loop()`. |
| `connected` | `bool` — whether the gRPC channel is active. |
| `running` | `bool` — controls the main loop. |
| `run_loop()` | Blocking. Connects, streams frames, auto-reconnects. Run on a thread. |
| `execute(command, params)` | Execute an API command. Returns `(success, result_or_error)`. |
| `stop()` | Gracefully shuts down the client. |

### Executing Commands

```python
success, result = client.execute("io.manager.getStatus")
if success:
    print(result)

success, result = client.execute("io.driver.uart.setBaudRate", {"baudRate": 115200})
```

## Frame Data Format

Frames arrive as Python dicts (converted from protobuf Struct):

```python
{
    "title": "My Project",
    "groups": [
        {
            "title": "Sensors",
            "datasets": [
                {
                    "title": "Temperature",
                    "value": "25.3",
                    "units": "°C",
                    "widgetMin": 0,
                    "widgetMax": 100
                }
            ]
        }
    ]
}
```

Key dataset fields: `title`, `value`, `units`, `widgetMin`, `widgetMax`, `plotMin`, `plotMax`.

## Required Files

```
plugin/my-plugin/
  info.json                    ← metadata
  plugin.py                    ← Python entry point
  grpc_client.py               ← gRPC client wrapper
  serialstudio_pb2.py          ← generated protobuf stubs
  serialstudio_pb2_grpc.py     ← generated gRPC stubs
  run.sh                       ← Unix launcher (venv + pip)
  run.cmd                      ← Windows launcher (venv + pip)
  icon.svg                     ← icon for start menu / toolbar
```

### run.sh

Creates a venv and auto-installs grpcio on first run:

```sh
#!/bin/sh
cd "$(dirname "$0")"

VENV_DIR=".venv"
if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
fi

. "$VENV_DIR/bin/activate"
python3 -c "import grpc" 2>/dev/null || pip install --quiet grpcio protobuf

exec python3 plugin.py "$@"
```

### run.cmd

```cmd
@echo off
cd /d "%~dp0"

if not exist ".venv" python -m venv .venv
call .venv\Scripts\activate.bat
python -c "import grpc" 2>nul || pip install --quiet grpcio protobuf

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
  "grpc": true,
  "dependencies": [
    {
      "name": "Python 3",
      "executables": ["python3", "python"],
      "url": "https://www.python.org/downloads/"
    }
  ],
  "files": [
    "info.json",
    "plugin.py",
    "grpc_client.py",
    "serialstudio_pb2.py",
    "serialstudio_pb2_grpc.py",
    "icon.svg"
  ],
  "platforms": {
    "darwin/*":  { "entry": "run.sh",  "runtime": "", "files": ["run.sh"] },
    "linux/*":   { "entry": "run.sh",  "runtime": "", "files": ["run.sh"] },
    "windows/*": { "entry": "run.cmd", "runtime": "", "files": ["run.cmd"] }
  }
}
```

**Key fields:**
- `"grpc": true` — tells Serial Studio this plugin requires the gRPC server.
- `dependencies` — only list system-level executables (Python). Pip packages are handled by the venv.
- `files` — include the gRPC stubs so they're installed with the plugin.

## Generating gRPC Stubs

If you need to regenerate the Python stubs (e.g. after a Serial Studio API update):

1. Export the `.proto` from Serial Studio: **Preferences → Export Protobuf File**
2. Generate stubs:
   ```bash
   pip install grpcio-tools
   python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. serialstudio.proto
   ```
3. Copy `serialstudio_pb2.py` and `serialstudio_pb2_grpc.py` to your plugin directory.

## macOS tkinter Rules

These rules are critical. Violating them causes invisible widgets or white artifacts:

1. **Use `ttk.Treeview` for tables.** Never use `tk.Canvas` with embedded Frames.
2. **Hide scrollbars on macOS.** Use `if sys.platform != "darwin": vsb.pack(...)`.
3. **Use `tk.Label` for buttons.** `tk.Button` ignores styling on macOS.
4. **Avoid `ttk.Combobox`** in dark themes. The dropdown is always white.

See [CLAUDE.md](../CLAUDE.md) for detailed patterns and code examples.

## Next Steps

- [Plugin State Persistence](04-plugin-state.md)
- [Platform Support](05-platform-support.md)
