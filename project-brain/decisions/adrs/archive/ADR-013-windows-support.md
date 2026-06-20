---
status: Implemented
date: '2026-01-15'
deciders:
- Core team
related: []
hub: null
tags:
- windows
- platform
- support
superseded_by: null
---

# ADR-009: Windows Platform Support

## Context

Augur was originally built for macOS with platform-specific dependencies:

- **Installation**: Bash scripts (`install.sh`)
- **Notifications**: AppleScript via `osascript`
- **IDE Detection**: macOS `.app` bundle paths and Info.plist parsing
- **Voice Recording**: Swift app using ScreenCaptureKit, AVFoundation, AppKit
- **Scheduled Tasks**: LaunchAgent plist files
- **OCR Pipeline**: Shell script with Homebrew paths

Users requested Windows support for broader adoption. Key challenges:
- No equivalent to ScreenCaptureKit on Windows (requires different audio API)
- Different path conventions (`%USERPROFILE%` vs `~`)
- Different process names for IDEs (`.exe` suffixes)
- Different notification APIs (Toast vs AppleScript)

## Decision

Implement **staged Windows support** using cross-platform abstractions and Python-based replacements for platform-specific code.

### Stage 1: Core Installation
- Create `install.ps1` PowerShell installer
- Use cross-platform `pathlib.Path` consistently
- Data location: `%USERPROFILE%\Projects\augur-data` (matches macOS structure)

### Stage 2: MCP & Claude Integration
- Fix venv path detection (`Scripts` vs `bin` on Windows)
- Verify subprocess spawning works cross-platform

### Stage 3: IDE Detection
```python
# Platform-specific paths in ide_detector.py
if self._system == "Windows":
    return [
        Path(local_app_data) / "Programs" / "cursor" / "Cursor.exe",
        Path(program_files) / "Microsoft VS Code" / "Code.exe",
    ]
```
- Add Windows Registry lookup for installed applications
- Add PowerShell-based version detection

### Stage 4: Notifications
```python
def _send_notification(self, title: str, message: str):
    if sys.platform == 'darwin':
        self._send_macos(title, message)
    elif sys.platform == 'win32':
        self._send_windows(title, message)  # plyer + BurntToast fallback
    elif sys.platform.startswith('linux'):
        self._send_linux(title, message)  # notify-send
```

### Stage 5: Scheduled Tasks
- Create `setup_scheduled_task.ps1` for Windows Task Scheduler
- Replaces macOS LaunchAgent plist

### Stage 6: OCR Pipeline
- Create `safe_ocr.py` (cross-platform Python replacement for bash script)
- Auto-detect platform-specific binary paths

### Stage 7: Voice Recording (Python Cross-Platform Recorder)

Replace Swift-only meeting recorder with Python implementation:

```
meeting-recorder-py/
├── __init__.py
├── config.py              # Meeting app patterns per platform
├── recorder.py            # Main orchestrator
├── meeting_detector.py    # psutil-based process monitoring
├── tray_icon.py           # pystray system tray UI
├── audio_capture/
│   ├── __init__.py
│   ├── microphone.py      # sounddevice (cross-platform)
│   └── system_audio.py    # WASAPI (Windows), PulseAudio (Linux)
└── requirements.txt
```

**Platform-specific audio capture**:
- Windows: WASAPI loopback via `soundcard` library
- Linux: PulseAudio monitor via `sounddevice`
- macOS: Delegates to existing Swift app (ScreenCaptureKit required)

**Meeting detection patterns**:
```python
MEETING_APPS = {
    "Windows": {
        "Zoom.exe": {"name": "Zoom"},
        "Teams.exe": {"name": "Microsoft Teams"},
        "slack.exe": {"name": "Slack"},
    },
    "Darwin": {
        "zoom.us": {"name": "Zoom"},
        "Microsoft Teams": {"name": "Microsoft Teams"},
    },
}
```

### Stage 8: Alternative Integrations (Future)

Apple-specific features that won't work on Windows:
- Apple Notes → Local markdown files
- iMessage → Not applicable
- iCal → Outlook/Google Calendar APIs

## Consequences

### Positive

- **Broader adoption**: Users can run Augur on Windows and Linux
- **Cross-platform codebase**: Abstractions benefit all platforms
- **Unified voice recording**: Single codebase for mic capture on all platforms
- **CI/CD coverage**: Can test on multiple platforms in GitHub Actions

### Negative

- **macOS voice quality**: Python recorder captures all system audio vs app-specific (Swift uses ScreenCaptureKit for app isolation)
- **Additional dependencies**: `plyer`, `pystray`, `soundcard`, `psutil` added
- **Testing complexity**: Need to test on 3 platforms
- **Feature parity gap**: Some Apple-specific features won't have Windows equivalents

### Neutral

- WSL not supported (native Windows only)
- Same data directory structure across platforms
- IDE detection returns different paths but same data model
- Meeting recorder has consistent API across platforms despite different implementations

## Alternatives Considered

### Alternative 1: WSL-Only Windows Support

Run everything via Windows Subsystem for Linux. Rejected because:
- Poor user experience (can't use native Windows apps)
- No system tray integration
- Voice recording wouldn't work (no audio device access)
- Notification support would be limited

### Alternative 2: Electron Wrapper

Bundle Augur in Electron for cross-platform GUI. Rejected because:
- Heavy dependency (300MB+ runtime)
- Already have dashboard for GUI needs
- Meeting recorder needs native audio access
- Overkill for the features needed

### Alternative 3: Keep macOS-Only

Continue with macOS-exclusive features. Rejected because:
- Limits adoption
- Misses Windows/Linux developer market
- Python already handles most cross-platform needs
- Only voice recording needed significant rework

### Alternative 4: Virtual Audio Cable on Windows

Require users to install VB-Audio or similar. Rejected because:
- Requires third-party software installation
- Complex user setup
- WASAPI loopback provides similar capability natively
- Poor UX

## Implementation

### Files Created

| File | Purpose |
|------|---------|
| `install.ps1` | PowerShell Windows installer |
| `docs/installation-windows.md` | Installation guide |
| `.github/scripts/setup_scheduled_task.ps1` | Task Scheduler setup |
| `plugins/ai/skills/knowledge/scripts/safe_ocr.py` | Cross-platform OCR |
| voice meeting-recorder-py/* | Python recorder (8 files) <!-- voice skill removed --> |

### Files Modified

| File | Changes |
|------|---------|
| `.github/scripts/configure_mcp.py` | Fixed Windows venv path (`Scripts` not `bin`) |
| `src/llm/ide_detector.py` | Added Windows paths and Registry lookup |
| `plugins/observability/skills/daemon/scripts/notification_service.py` | Added Windows/Linux support |

### Testing Strategy

Cross-platform CI workflow tests:
1. Unit tests with mocked audio/system APIs
2. Integration tests for path resolution
3. Matrix testing: Windows, macOS, Linux
4. Codecov for coverage tracking

## References

- [WASAPI Loopback Recording](https://docs.microsoft.com/en-us/windows/win32/coreaudio/loopback-recording)
- [soundcard library](https://github.com/bastibe/SoundCard)
- [pystray documentation](https://pystray.readthedocs.io/)
- [Windows Toast Notifications](https://docs.microsoft.com/en-us/windows/apps/design/shell/tiles-and-notifications/toast-notifications-overview)
- voice meeting-recorder-py/ - Python recorder implementation <!-- voice skill removed -->
- `docs/installation-windows.md` - Windows installation guide
