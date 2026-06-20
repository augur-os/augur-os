---
status: Implemented
date: '2025-01-15 (Updated: 2026-01-15 for Windows support)'
deciders:
- Core team
related: []
hub: null
tags:
- centralized
- permissions
- dashboard
superseded_by: null
---

# ADR-009: Centralized Permissions Dashboard

## Context

Augur integrates deeply with operating system capabilities:
- **Voice recording** requires Microphone and Screen Recording permissions
- **Calendar integration** requires Calendar access
- **Inbox processing** requires Apple Notes and Mail automation
- **App detection** requires Accessibility permission
- **OCR** requires Tesseract installation

Previously, these permissions were handled ad-hoc:
- Users discovered permission needs only when features failed
- Error messages referenced "Terminal" or IDE names, not "Augur"
- No central place to see what permissions were granted or missing
- Instructions for fixing permissions were scattered across documentation

This created a poor user experience, especially during onboarding.

## Decision

Implement a **centralized Permissions Dashboard** under Settings that:

### 1. Permission Status API
Single endpoint (`/api/permissions/status`) that checks all required permissions:

#### macOS Permissions
| Permission | Check Method |
|------------|--------------|
| Screen Recording | CoreGraphics `CGPreflightScreenCaptureAccess` |
| Microphone | AVFoundation `authorizationStatus` |
| Accessibility | `AXIsProcessTrusted()` |
| Calendar | osascript to Calendar.app |
| Apple Notes | osascript to Notes.app |
| Apple Mail | osascript to Mail.app |
| Email/IMAP | Config file + env var check |
| Tesseract OCR | `which tesseract` |

#### Windows Permissions
| Permission | Check Method |
|------------|--------------|
| Microphone | PowerShell registry check (`CapabilityAccessManager\ConsentStore\microphone`) |
| Camera | PowerShell registry check (`CapabilityAccessManager\ConsentStore\webcam`) |
| Location | PowerShell registry check (`CapabilityAccessManager\ConsentStore\location`) |
| Calendar | PowerShell registry check (`CapabilityAccessManager\ConsentStore\appointments`) |
| Notifications | PowerShell registry check (`PushNotifications\ToastEnabled`) |
| Email/IMAP | Config file + env var check |
| Tesseract OCR | `where tesseract` or common install paths |

### 2. Permission Categories
Permissions grouped into logical categories:
- **macOS System Permissions**: Screen Recording, Microphone, Accessibility
- **Windows System Permissions**: Microphone, Camera, Location, Calendar, Notifications
- **Email & Calendar**: Calendar, Apple Notes, Apple Mail, Email/IMAP
- **System Dependencies**: Tesseract OCR

### 3. Status Indicators
Four permission states with visual indicators:
- `granted` (green) - Permission available
- `denied` (red) - Permission explicitly denied
- `unknown` (amber) - Cannot determine status
- `not_configured` (gray) - Requires setup, not a system permission

### 4. Actionable UI
- **Tooltips on hover**: Every permission shows setup instructions
- **"Open Settings" buttons**: Deep links to exact System Settings pane
- **"How to fix" sections**: Expanded instructions for denied permissions

### 5. Branded App Bundle
Create `Augur.app` bundle so macOS permission dialogs show "Augur" with proper icon instead of "Terminal".

## Implementation

### Files Created
```
src/dashboard/app/api/permissions/status/route.ts   # Permission status API
src/dashboard/app/settings/tabs/PermissionsTab.tsx  # UI component
src/dashboard/app/settings/permissions/page.tsx     # Page wrapper
src/native/Augur.app/                           # macOS app bundle
src/native/icon.svg                                 # Source icon
src/native/generate_icon.sh                         # Icon generator
```

### Deep Links
System Settings deep links for one-click navigation:

#### macOS Deep Links
```typescript
const MACOS_DEEP_LINKS = {
  screen_recording: 'x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture',
  microphone: 'x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone',
  accessibility: 'x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility',
  calendar: 'x-apple.systempreferences:com.apple.preference.security?Privacy_Calendars',
  apple_notes: 'x-apple.systempreferences:com.apple.preference.security?Privacy_Automation',
  apple_mail: 'x-apple.systempreferences:com.apple.preference.security?Privacy_Automation',
};
```

#### Windows Deep Links (ms-settings: URIs)
```typescript
const WINDOWS_DEEP_LINKS = {
  microphone: 'ms-settings:privacy-microphone',
  camera: 'ms-settings:privacy-webcam',
  location: 'ms-settings:privacy-location',
  calendar: 'ms-settings:privacy-calendar',
  notifications: 'ms-settings:notifications',
};
```

## Consequences

### Positive

- **Better onboarding**: Users see all required permissions in one place
- **Self-service troubleshooting**: Clear instructions reduce support burden
- **Professional branding**: "Augur" appears in permission dialogs
- **Feature discovery**: Users learn about capabilities they haven't enabled
- **Graceful degradation**: Features can check permission status before attempting operations

### Negative

- **Platform-specific code**: Permission checking APIs differ between macOS and Windows
- **App bundle maintenance**: Need to keep Augur.app updated (macOS)
- **Not real-time**: Status is snapshot; user must refresh after granting permissions
- **Deep link fragility**: OS vendors may change URL schemes in future versions
- **Windows registry access**: PowerShell permission checks require appropriate access

### Neutral

- Unsupported platforms (Linux, etc.) see "Unsupported Platform" message
- Permission checks run asynchronously on page load (~100ms)
- No automatic permission request flows (user must grant manually)
- Windows and macOS have different permission sets based on OS capabilities

## Alternatives Considered

### Alternative 1: Per-Feature Permission Checks

Check permissions only when features are used. Rejected because:
- Poor discoverability
- Repeated failure messages
- No centralized view of system state

### Alternative 2: Automatic Permission Request Flows

Trigger macOS permission dialogs from the dashboard. Rejected because:
- Many permissions can't be requested programmatically
- Creates security concerns
- macOS restricts automated permission grants

### Alternative 3: Electron/Tauri Wrapper

Package entire app as native macOS app. Rejected (for now) because:
- Significant increase in complexity
- Larger distribution size
- Current web-based approach works well
- Can revisit if more native integration needed

## References

- [ADR-006](./ADR-006-local-first.md) - Local-first architecture (why we need local permissions)
- [Apple TCC Documentation](https://developer.apple.com/documentation/security/app_sandbox) - macOS permission system
- [System Settings URL Schemes](https://support.apple.com/guide/shortcuts/url-schemes-apda74c51edc/ios) - macOS deep link reference
- [Windows ms-settings URIs](https://docs.microsoft.com/en-us/windows/uwp/launch-resume/launch-settings-app) - Windows Settings deep links
- [Windows Privacy Settings](https://docs.microsoft.com/en-us/windows/privacy/) - Windows permission system
