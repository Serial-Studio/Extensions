# Creating Themes

## Required Files

```
theme/my-theme/
  info.json                    ← metadata
  my-theme.json                ← color palette (~80 color keys)
  code-editor/my-theme.xml     ← syntax highlighting for JS editor
  README.md                    ← description with color table
```

## Theme JSON Structure

```json
{
  "title": "My Theme",
  "parameters": {
    "code-editor-theme": "my-theme",
    "start-icon": "qrc:/rcc/logo/start-dark.svg"
  },
  "translations": {
    "en_US": "My Theme",
    "es_MX": "Mi Tema"
  },
  "colors": {
    "groupbox_border": "#3a3d42",
    "groupbox_background": "#202326",
    ...
  }
}
```

### Parameters

- `code-editor-theme`: must match the XML filename (without `.xml`)
- `start-icon`: use `start-dark.svg` for dark themes, `start.svg` for light themes

### Color Key Groups

| Group | Prefix | Controls |
|-------|--------|----------|
| Groupbox | `groupbox_*` | Panel borders and backgrounds |
| Pane | `pane_*` | Content area and section headers |
| Toolbar | `toolbar_*` | Main toolbar gradient and buttons |
| Console | `console_*` | Terminal/console widget |
| Widget | `widget_*` | Dashboard widget controls |
| Window | `window_*` | Window chrome and title bars |
| Taskbar | `taskbar_*` | Dashboard taskbar |
| Start Menu | `start_menu_*` | Dashboard start menu |
| Table | `table_*` | Data grid tables |
| Plot 3D | `plot3d_*` | 3D visualization |
| Polar | `polar_*` | Polar/compass widgets |

Plus: `widget_colors` (array of 20 hex colors) and `device_colors` (array of 10 `{top, bottom}` gradient pairs).

### Reference

Use any built-in theme as a starting point. The `default.json` in the Serial Studio repo (`app/rcc/themes/`) has the complete key list.

## Code Editor XML

```xml
<?xml version="1.0" encoding="UTF-8"?>
<style-scheme version="1.0" name="My Theme">
  <style name="Text" foreground="#c9d1d9" background="#0d1117"/>
  <style name="Keyword" foreground="#ff7b72" bold="true"/>
  <style name="String" foreground="#a5d6ff"/>
  <style name="Comment" foreground="#8b949e" italic="true"/>
  <style name="Number" foreground="#79c0ff"/>
  <!-- ... see existing themes for all style names -->
</style-scheme>
```

## Tips

### Dark Themes
- Separators need ~15-20% contrast against adjacent surfaces
- Console text should be a different color than code keywords
- Pane caption: darker top → lighter bottom for depth

### Light Themes
- Toolbar should be noticeably darker than content area
- Borders in warm gray range (e.g., `#B8B098` for Solarized)
- Widget borders darker than widget backgrounds

## info.json for Themes

```json
{
  "id": "my-theme",
  "type": "theme",
  "title": "My Theme",
  "description": "A short, evocative description.",
  "author": "Your Name",
  "version": "1.0.0",
  "license": "MIT",
  "category": "Dark",
  "files": [
    "info.json",
    "my-theme.json",
    "code-editor/my-theme.xml"
  ]
}
```
