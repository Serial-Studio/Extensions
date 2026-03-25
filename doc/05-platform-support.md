# Platform Support

Plugins can target specific operating systems and CPU architectures using the `platforms` field in `info.json`.

## Python Plugins

Python plugins need shell wrapper scripts to avoid tkinter issues when launched from Serial Studio's QProcess:

### run.sh (macOS + Linux)

```sh
#!/bin/sh
cd "$(dirname "$0")"
exec python3 plugin.py "$@"
```

### run.cmd (Windows)

```cmd
@echo off
cd /d "%~dp0"
python plugin.py %*
```

### info.json

```json
{
  "entry": "plugin.py",
  "runtime": "python3",
  "files": ["info.json", "plugin.py"],
  "platforms": {
    "darwin/*":  { "entry": "run.sh", "runtime": "", "files": ["run.sh"] },
    "linux/*":   { "entry": "run.sh", "runtime": "", "files": ["run.sh"] },
    "windows/*": { "entry": "run.cmd", "runtime": "", "files": ["run.cmd"] }
  }
}
```

## Native Binaries

For compiled plugins (Pro feature), provide separate binaries per platform:

```json
{
  "entry": "plugin.py",
  "runtime": "python3",
  "files": ["info.json"],
  "platforms": {
    "darwin/*":      { "entry": "bin/macos/plugin",       "runtime": "", "files": ["bin/macos/plugin"] },
    "linux/x86_64":  { "entry": "bin/linux-x64/plugin",   "runtime": "", "files": ["bin/linux-x64/plugin"] },
    "linux/arm64":   { "entry": "bin/linux-arm64/plugin",  "runtime": "", "files": ["bin/linux-arm64/plugin"] },
    "windows/x86_64":{ "entry": "bin/win-x64/plugin.exe",  "runtime": "", "files": ["bin/win-x64/plugin.exe"] }
  }
}
```

## Platform Keys

| Key | OS | Architecture |
|-----|-----|-------------|
| `darwin/*` | macOS | Universal (always) |
| `linux/x86_64` | Linux | Intel/AMD 64-bit |
| `linux/arm64` | Linux | ARM 64-bit (RPi, etc.) |
| `linux/*` | Linux | Any architecture |
| `windows/x86_64` | Windows | Intel/AMD 64-bit |
| `windows/*` | Windows | Any architecture |
| `*` | Any | Any |

## Fallback Order

1. Exact match: `darwin/arm64`
2. OS wildcard: `darwin/*`
3. Universal wildcard: `*`
4. Top-level `entry`/`runtime`/`files` fields

## Notes

- macOS always uses `darwin/*` — no need to separate arm64/x86_64 (universal builds)
- Linux may need separate arm64/x86_64 for native binaries
- `runtime: ""` means the entry point is directly executable (native binary or shell script)
- Native binaries get `chmod +x` automatically on Unix
- Platform-specific `files` are merged with the base `files` during installation
- If a plugin has no platform match, the Install button is disabled and an "Unavailable" badge is shown
