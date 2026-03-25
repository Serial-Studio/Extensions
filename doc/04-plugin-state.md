# Plugin State Persistence

Plugin state is saved in the project file (`.ssproj`) alongside widget layout data. This means different projects can have different plugin configurations. The same plugin shows different gauges or indicators depending on which project is loaded.

## How It Works

```
Project File (.ssproj)
└── widgetSettings
    ├── layout:0              ← widget layout data
    ├── layout:1
    ├── __plugin__:custom-gauge     ← gauge plugin state
    └── __plugin__:digital-indicator ← indicator plugin state
```

## API Commands

### Save State

```python
client._send("extensions.saveState", {
    "pluginId": "my-plugin",
    "state": {
        "windows": [
            {"key": "f0", "label": "Temperature", "color": "#58a6ff"},
            {"key": "f1", "label": "Pressure", "color": "#3fb950"}
        ],
        "settings": {"auto_range": true}
    }
})
```

### Load State

```python
client._send("extensions.loadState", {"pluginId": "my-plugin"})
resp = client._read_response()
state = resp["result"]["state"]  # {} if no saved state
```

## Recommended Lifecycle

```
Plugin starts
  │
  ├─► loadState() → restore windows from saved config
  │
  ├─► User interacts (opens windows, changes settings)
  │
  ├─► {"event": "disconnected"} → saveState()
  │
  ├─► {"event": "connected"} → loadState() (project may have changed)
  │
  └─► Plugin quits → saveState() (final save)
```

## Implementation Pattern

### 1. Add to_dict() to your window class

```python
class MyWindow:
    def to_dict(self):
        return {
            "key": self.dataset_key,
            "label": self.label,
            "settings": {"min": self.min_val, "max": self.max_val}
        }
```

### 2. Add save/restore to your App class

```python
class App:
    def _save_state(self):
        windows = [w.to_dict() for w in self.windows if w.alive]
        if self.client.connected:
            self.client.save_state("my-plugin", {"windows": windows})

    def _restore_state(self):
        if not self.client.connected:
            return
        state = self.client.load_state("my-plugin")
        if not state:
            return

        def try_restore():
            # Wait for data fields to be available
            with self.store.lock:
                if not self.store.fields:
                    self.root.after(500, try_restore)
                    return

            for wc in state.get("windows", []):
                # Recreate window from saved config
                ...

        self.root.after(500, try_restore)

    def _on_event(self, event_name):
        if event_name == "disconnected":
            self._save_state()
        elif event_name == "connected":
            self._restore_state()

    def _quit(self):
        self._save_state()
        # ... cleanup
```

### 3. Wire in main()

```python
def main():
    store = DataStore()
    client = APIClient()
    client.on_frame = store.ingest

    client.connect()
    threading.Thread(target=client.run_loop, daemon=True).start()

    app = App(store, client)
    client.on_event = app._on_event
    app._restore_state()
    app.run()
```

## Auto-Launch

Plugins that were running when Serial Studio closed are automatically relaunched on the next startup. The ExtensionManager saves the list of running plugin IDs to QSettings and restores them after the extension catalog loads.

No plugin-side code is needed for this. It's handled entirely by the ExtensionManager.

## Important Notes

- State is only saved when a project file is loaded (`operationMode == ProjectFile`)
- The `_restore_state` must wait for data fields to arrive before creating windows (use `root.after(500, try_restore)` retry pattern)
- Never hold the data lock while creating tkinter widgets. This causes deadlocks.
- State objects should be JSON-serializable (dicts, lists, strings, numbers, bools)
