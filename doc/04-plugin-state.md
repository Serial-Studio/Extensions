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
success, _ = client.execute("extensions.saveState", {
    "pluginId": "my-plugin",
    "state": {
        "windows": [
            {"key": "f0", "label": "Temperature", "color": "#58a6ff"},
            {"key": "f1", "label": "Pressure", "color": "#3fb950"}
        ],
        "settings": {"auto_range": True}
    }
})
```

### Load State

```python
success, result = client.execute("extensions.loadState", {
    "pluginId": "my-plugin"
})
if success:
    state = result  # dict with saved state, or {} if none
```

## Recommended Lifecycle

```
Plugin starts
  │
  ├─► loadState() → restore windows from saved config
  │
  ├─► User interacts (opens windows, changes settings)
  │
  ├─► Periodic auto-save (optional, e.g. every 30s)
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
        self.client.execute("extensions.saveState", {
            "pluginId": "my-plugin",
            "state": {"windows": windows}
        })

    def _restore_state(self):
        def _try():
            success, result = self.client.execute(
                "extensions.loadState", {"pluginId": "my-plugin"})
            if not success or not result:
                return

            state = result if isinstance(result, dict) else {}
            for wc in state.get("windows", []):
                # Recreate window from saved config
                ...

        # Run on a background thread to avoid blocking tkinter
        threading.Thread(target=_try, daemon=True).start()

    def _quit(self):
        self._save_state()
        # ... cleanup
```

### 3. Wire in main()

```python
def main():
    store = DataStore()
    client = GRPCClient()
    client.on_frame = store.ingest

    threading.Thread(target=client.run_loop, daemon=True).start()

    app = App(store, client)
    app._restore_state()
    app.run()
    client.stop()
```

## Auto-Launch

Plugins that were running when Serial Studio closed are automatically relaunched on the next startup. The ExtensionManager saves the list of running plugin IDs to QSettings and restores them after the extension catalog loads.

No plugin-side code is needed for this. It's handled entirely by the ExtensionManager.

## Important Notes

- State is only saved when a project file is loaded (`operationMode == ProjectFile`)
- The `_restore_state` should run on a background thread since `client.execute()` blocks
- Never hold the data lock while creating tkinter widgets — this causes deadlocks
- State objects must be JSON-serializable (dicts, lists, strings, numbers, bools)
