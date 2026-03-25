# Getting Started with Serial Studio Extensions

## What are Extensions?

Extensions add functionality to Serial Studio without modifying the core application. There are four types:

| Type | Description | Example |
|------|-------------|---------|
| **Theme** | Custom color palette for the entire UI | Solarized Dark, Midnight |
| **Frame Parser** | JavaScript decoder for custom protocols | NMEA GPS, Binary TLV |
| **Project Template** | Pre-configured `.ssproj` project file | 6-DOF IMU, PID Controller |
| **Plugin** | External program with its own UI | Digital Indicator, Custom Gauge |

## Installing Extensions

1. Open Serial Studio and click **Extensions** in the toolbar
2. Browse the catalog — extensions are grouped by type
3. Click a card to see details, then click **Install**
4. Themes appear in Preferences, plugins can be launched from the detail view or the dashboard Start Menu

## Creating Your First Extension

Every extension needs:

1. A directory under the correct type folder (`theme/`, `plugin/`, etc.)
2. An `info.json` file with metadata
3. The extension files (theme JSON, Python script, etc.)
4. A `README.md` describing the extension

### Minimal info.json

```json
{
  "id": "my-extension",
  "type": "theme",
  "title": "My Extension",
  "description": "What it does.",
  "author": "Your Name",
  "version": "1.0.0",
  "license": "MIT",
  "category": "Dark",
  "files": ["info.json", "my-theme.json", "code-editor/my-theme.xml"]
}
```

### Adding to a Repository

Add the path to your extension's `info.json` in the repository's `manifest.json`:

```json
{
  "version": 1,
  "repository": "My Extensions",
  "extensions": [
    "theme/my-extension/info.json"
  ]
}
```

### Testing Locally

In Serial Studio Pro, open Extensions → Repos → Browse and select your repository folder. Extensions appear immediately for installation and testing.

## Next Steps

- [Creating Themes](02-creating-themes.md)
- [Creating Plugins](03-creating-plugins.md)
- [Plugin State Persistence](04-plugin-state.md)
- [Platform Support](05-platform-support.md)
