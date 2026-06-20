---
status: Implemented
date: '2026-02-06'
deciders:
- Augur Team
related: []
hub: null
tags:
- zero
- technical
- onboarding
- macos
- first
superseded_by: null
---

# ADR-049: Zero-Technical Onboarding (macOS First, Windows Later)

## Context

The current installer (`scripts/install.sh`) assumes the user already has:
- **Git** installed and configured
- **Python 3.11+** installed
- **npm/Node.js** installed (for the dashboard)
- **Homebrew** (macOS) or **apt** (Linux)
- Comfort running terminal commands

This blocks the entire non-developer audience. A designer, entrepreneur, or knowledge worker who wants a "second brain" should not need to install Xcode CLI tools, debug Python version conflicts, or learn what `source .venv/bin/activate` means.

**Windows is completely unsupported** — `install.sh` is bash-only, and system dependency installation (`brew install`, `apt-get`) has no Windows path.

The vision of Augur as a personal knowledge/automation system for everyone requires an onboarding path where:
1. The user downloads ONE thing (or runs ONE command)
2. Answers ONE question: "Which AI provider?" (OAuth sign-in or local Ollama)
3. Everything else is handled automatically — git, Python, Node.js, system deps, data dirs

## Decision

Build a **macOS-native installer** first that bundles all dependencies and eliminates technical prerequisites. Windows support is deferred to a later phase — macOS is the launch platform. The user never touches a terminal unless they choose to.

### Rollout Strategy: macOS First

| Phase | Platform | Cost | Rationale |
|-------|----------|------|-----------|
| **Now** | macOS | $99/yr (Apple Developer) | Primary target audience, single signing cost, bash-compatible for src/lib installer logic |
| **Later** | Windows | +$200-400/yr (EV cert) | Added only after macOS installer is proven and user demand validates the investment |

This cuts initial signing costs from ~$300-500/yr to **$99/yr** and halves the CI/build pipeline scope.

### Guiding Principle: Zero Prerequisites

The only thing the user needs is:
- **macOS**: The ability to download and open a `.dmg` file
- **Power users**: A one-liner for terminal-based install (current flow, improved)
- **Windows**: Deferred — tracked as future phase

### Installation Flow

```
┌──────────────────────────────────────────────────┐
│  User downloads Augur.dmg                        │
│  or runs: curl ... | bash  (power users)         │
└──────────────────┬───────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────┐
│  Step 1: Welcome Screen                          │
│  "Welcome to Augur — your second brain"          │
│  [Get Started]                                   │
└──────────────────┬───────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────┐
│  Step 2: Choose AI Provider                      │
│                                                  │
│  ┌─────────────┐  ┌─────────────┐               │
│  │  Claude      │  │  OpenAI     │               │
│  │  (OAuth)     │  │  (OAuth)    │               │
│  └─────────────┘  └─────────────┘               │
│  ┌─────────────┐  ┌─────────────┐               │
│  │  Google      │  │  Ollama     │               │
│  │  Gemini      │  │  (Local)    │               │
│  │  (OAuth)     │  │             │               │
│  └─────────────┘  └─────────────┘               │
│                                                  │
│  OAuth: Opens browser → user signs in → token    │
│  Ollama: Installer downloads & configures it     │
└──────────────────┬───────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────┐
│  Step 3: Installing... (progress bar)            │
│                                                  │
│  ✓ Setting up runtime environment                │
│  ✓ Installing AI engine                          │
│  ▶ Preparing your workspace...                   │
│    Configuring dashboard                         │
│                                                  │
│  (User sees friendly labels, not "pip install")  │
└──────────────────┬───────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────┐
│  Step 4: Ready!                                  │
│  "Augur is ready. Opening your dashboard..."     │
│  [Open Augur]                                    │
└──────────────────────────────────────────────────┘
```

### What "Installing..." Does Behind the Scenes

The installer handles everything the user currently does manually — but silently:

| Step | What It Does | User Sees |
|------|-------------|-----------|
| 1. Embedded runtime | Bundles Python 3.12 + Node.js 20 LTS (no system install) | "Setting up runtime..." |
| 2. Clone/extract repo | `git` bundled via embedded binary or archive extraction | "Downloading Augur..." |
| 3. Virtual environment | Creates `.venv`, installs Python deps | "Installing components..." |
| 4. npm install + build | Installs dashboard dependencies, runs build | "Preparing dashboard..." |
| 5. System deps | Bundles tesseract, poppler, etc. (platform-specific) | "Installing AI engine..." |
| 6. OAuth / Ollama | Stores token in secure keychain / downloads Ollama | "Connecting AI provider..." |
| 7. Data directories | Creates `~/Augur/` (simplified from `~/Projects/augur-data`) | "Creating workspace..." |
| 8. Launch | Starts dashboard, opens browser | "Opening Augur..." |

### Platform-Specific Implementation

#### macOS: `.dmg` with Setup App

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Installer app | Swift/SwiftUI or Electron | Native feel, notarization support |
| Python runtime | Embedded Python.framework (python.org relocatable) | No Homebrew dependency |
| Node.js runtime | Embedded node binary (from nodejs.org) | No nvm/brew dependency |
| Git | Embedded `git` binary or libgit2 | No Xcode CLI tools needed |
| System deps | Pre-compiled universal binaries in app bundle | No `brew install` step |
| Code signing | Apple Developer ID + notarization | Gatekeeper approval, no scary warnings |
| Auto-update | Sparkle framework or custom updater | Silent background updates |

**Alternative — Homebrew Cask** (for semi-technical users):
```bash
brew install --cask augur
```
This would still bundle everything but use Homebrew as distribution channel.

#### Windows: Deferred (Future Phase)

Windows installer will be built only after macOS is validated. When prioritized:
- Inno Setup or NSIS `.exe` installer
- Embeddable Python + portable git + Node.js bundled
- EV code signing certificate ($200-400/yr) for instant SmartScreen trust
- Pre-compiled `.dll` bundles for system deps

**Trigger to start Windows phase**: macOS installer stable + measurable Windows user demand (website analytics, waitlist requests).

#### Linux: Maintained as terminal-first (current `install.sh`, improved)

Linux users are assumed technical. The current `install.sh` is improved to:
1. Auto-install Python/Node if missing (via system package manager)
2. Add the OAuth/Ollama provider selection step
3. Offer an AppImage for GUI-first users (future)

### AI Provider Authentication

| Provider | Auth Method | Token Storage | Fallback |
|----------|------------|---------------|----------|
| Claude (Anthropic) | OAuth 2.0 PKCE | macOS Keychain | Manual API key entry |
| OpenAI | OAuth 2.0 PKCE | macOS Keychain | Manual API key entry |
| Google Gemini | Google OAuth 2.0 | macOS Keychain | Manual API key entry |
| Ollama (local) | No auth needed | N/A — local inference | Auto-download if not present |

**OAuth flow**: Installer opens system browser → user signs in → callback to `localhost:PORT` → token captured and stored securely. No API key copy-paste needed.

**Ollama flow**: If user selects Ollama and it's not installed, the installer downloads and installs it automatically, then pulls a default model (e.g., `llama3.2`).

### Directory Structure (Simplified for End Users)

Current developer layout (`~/Projects/augur` + `~/Projects/augur-data`) is confusing for non-developers.

| Audience | Install Location | Data Location |
|----------|-----------------|---------------|
| End user (installer) | `/Applications/Augur.app` (macOS) | `~/Augur/` |
| Developer (terminal) | `~/Projects/augur` (unchanged) | `~/Projects/augur-data` (unchanged) |

Both map to the same internal structure — the installer just uses friendlier default paths.

### Build & Distribution Pipeline

```
GitHub Actions CI
├── macOS (Phase 2)
│   ├── Build Swift/Electron installer app
│   ├── Bundle Python 3.12 + Node 20 + git
│   ├── Bundle system deps (universal binaries)
│   ├── Code sign (Developer ID) — $99/yr
│   ├── Notarize with Apple
│   └── Output: Augur-{version}.dmg
├── Windows (Future — Phase 3+)
│   ├── Build Inno Setup / NSIS installer
│   ├── Bundle embeddable Python + Node + portable git
│   ├── Bundle system deps (.dlls)
│   ├── Code sign (EV certificate) — $200-400/yr added only when needed
│   └── Output: AugurSetup-{version}.exe
└── Release
    ├── Upload to GitHub Releases
    ├── Update Homebrew Cask formula (macOS)
    └── Update website download links
```

### Implementation Phases

| Phase | Scope | Deliverable |
|-------|-------|-------------|
| **Phase 1: Core installer logic** | Cross-platform Python installer script with embedded dependency management | `scripts/installer/` with platform detection, bundled runtime extraction, OAuth wizard |
| **Phase 2: macOS app** | Native `.dmg` with SwiftUI setup wizard wrapping Phase 1 logic | `Augur.dmg` on GitHub Releases |
| **Phase 3: macOS auto-update** | Background update checker, in-app notification | Sparkle framework integration |
| **Phase 4: Homebrew Cask** | `brew install --cask augur` | Formula in homebrew-cask |
| **Phase 5: Windows installer** *(demand-gated)* | Inno Setup `.exe` wrapping Phase 1 logic + EV code signing | `AugurSetup.exe` — only when Windows demand justifies the cost |

## Consequences

### Positive

- **Massive audience expansion** — anyone who can download an app can use Augur
- **No "install Python" support tickets** — runtime is bundled
- **No git knowledge required** — repo management is invisible
- **OAuth removes API key friction** — users sign in, not paste tokens
- **Low initial cost** — macOS-first means only $99/yr to start, Windows cost deferred
- **Professional appearance** — signed, notarized macOS installer builds trust
- **Consistent environment** — bundled runtimes eliminate "works on my machine" issues

### Negative

- **Large installer size** — bundling Python + Node + git + system deps may reach 300-500MB
- **Build pipeline complexity** — CI must build, sign, and notarize for macOS
- **Update lag** — bundled runtimes need explicit updates (security patches)
- **Two install paths to maintain** — installer + developer terminal flow
- **Code signing cost** — Apple Developer Program at $99/yr (Windows EV cert deferred)
- **Windows users left out initially** — must use terminal install or wait for Phase 5
- **Ollama binary size** — if bundled, adds ~1GB+ with a default model

### Neutral

- Developer onboarding path (`install.sh`) remains unchanged — this is additive
- Internal architecture is not affected — only the entry point changes
- Dashboard, skills, and plugins work identically regardless of install method

## Alternatives Considered

### Alternative 1: Docker-based installer

Package everything in a Docker container — user installs Docker Desktop, then runs `docker run augur`.

**Rejected because**:
- Docker Desktop itself requires installation (defeats the "zero prereqs" goal)
- Docker Desktop is 1GB+ and resource-heavy
- Networking (localhost access for dashboard) is confusing for non-developers
- Docker Desktop licensing has commercial restrictions
- macOS and Windows Docker performance is worse than native

### Alternative 2: Electron-only app (no native installers)

Ship Augur as a single Electron app that bundles everything including the dashboard.

**Rejected because**:
- Electron adds 200MB+ baseline before any Augur code
- Dashboard is already a Next.js app — wrapping it in Electron adds complexity without benefit
- System deps (tesseract, Python scripts) still need native execution
- Could revisit for Phase 2 macOS installer as the wrapper, but not as the whole strategy

### Alternative 3: Web-only SaaS (no local install)

Host Augur as a web service — user just opens a URL.

**Rejected because**:
- Augur's value proposition is a *personal*, *local* knowledge system
- User data sovereignty is core to the vision
- Local LLM support (Ollama) requires local execution
- Hosting costs scale per user
- Contradicts the "second brain you own" philosophy

### Alternative 4: Improve `install.sh` only (no native installers)

Make the existing shell script smarter — auto-install Python, Node, git via package managers.

**Rejected as the sole approach because**:
- Still requires terminal comfort (intimidating for target audience)
- Windows has no native bash (WSL adds another prereq layer)
- Package manager installation (Homebrew, Chocolatey) is itself a technical step
- Cannot achieve true "download and double-click" experience

**Retained as the Linux/developer path** — improved `install.sh` is Phase 1 and serves technical users on all platforms.

## Test Plan

Terminal-executable verification commands for the OAuth wizard (Phase 1 deliverable).

### Quick Smoke Test (One-Liner)

```bash
python3 plugins/dev/skills/devops/scripts/oauth_wizard.py --list && echo "PASS" || echo "FAIL"
```

### Full Test Suite

Run each command sequentially. Expected results noted inline.

```bash
# 1. List providers (should show configured providers or "No providers configured")
python3 plugins/dev/skills/devops/scripts/oauth_wizard.py --list

# 2. OAuth flow — Glama (opens browser, completes OAuth, stores key)
python3 plugins/dev/skills/devops/scripts/oauth_wizard.py --provider glama

# 3. Verify Glama connection (should report model count)
python3 plugins/dev/skills/devops/scripts/oauth_wizard.py --verify glama

# 4. Check credential file permissions (should be 600)
stat -f '%Lp' data/core/config/.oauth-keys.json

# 5. Check remote_providers.yaml updated (glama: enabled: true, hasApiKey: true)
grep -A4 'glama:' config/integrations/remote_providers.yaml

# 6. Check llm.yaml has remote profile
grep -A4 'remote:' config/system/llm.yaml

# 7. Manual key flow — Anthropic (prompts for masked key input)
python3 plugins/dev/skills/devops/scripts/oauth_wizard.py --provider anthropic

# 8. Ollama flow (detects install, checks running, lists models)
python3 plugins/dev/skills/devops/scripts/oauth_wizard.py --provider ollama

# 9. PKCE unit check (verifier + challenge generation)
python3 -c "
from plugins.crew.skills.devops.scripts.lib.oauth_pkce import generate_code_verifier, generate_code_challenge, generate_state
v = generate_code_verifier()
c = generate_code_challenge(v)
s = generate_state()
assert len(v) == 64, f'verifier length {len(v)}'
assert len(c) > 0, 'empty challenge'
assert len(s) == 64, f'state length {len(s)}'
print(f'PKCE OK: verifier={len(v)}chars challenge={len(c)}chars state={len(s)}chars')
"

# 10. Interactive menu (run manually, press 0 to exit)
python3 plugins/dev/skills/devops/scripts/oauth_wizard.py

# 11. Dashboard compatibility — start dashboard, check Settings > AI > Providers
cd src/dashboard && npm run dev
# Open http://localhost:3000/settings → AI → Providers → Glama should show connected
```

### Expected Final State

| File | Expected Content |
|------|-----------------|
| `data/core/config/.oauth-keys.json` | Provider keys, file mode 0600 |
| `config/integrations/remote_providers.yaml` | Tested providers show `enabled: true`, `hasApiKey: true`, `lastTested: <timestamp>` |
| `config/system/llm.yaml` | `remote:` profile with `base_url` matching configured provider |

## Hardening Features

Security, reliability, and edge-case handling required for production readiness.

### Security

| Feature | Status | Details |
|---------|--------|---------|
| PKCE S256 flow | Done | `oauth_pkce.py` — code_challenge = SHA256(verifier), base64url |
| CSRF state validation | Done | Random state param verified on callback |
| Callback server localhost-only | Done | `callback_server.py` binds `127.0.0.1`, not `0.0.0.0` |
| Credential file permissions | Done | `.oauth-keys.json` chmod 0o600 on every write |
| Keys never printed/logged | Done | `getpass` for manual input, no key echo |
| YAML stores env var names only | Done | Actual keys only in `.oauth-keys.json` |
| Token refresh / expiry handling | Future | Detect expired tokens, prompt re-auth |
| Rate limiting on callback server | Future | Reject rapid repeated requests |
| Custom URL input sanitization | Future | Validate scheme, host, reject private IPs |

### Reliability

| Feature | Status | Details |
|---------|--------|---------|
| Port fallback (18492-18500) | Done | `callback_server.py` scans ports if primary busy |
| Callback timeout (5 min) | Done | Auto-shutdown if no callback received |
| Verification timeout (10s) | Done | `provider_verifier.py` per-request timeout |
| Ollama pull timeout (10 min) | Done | `ollama_checker.py` subprocess timeout |
| Graceful Ctrl+C handling | Future | SIGINT handler to clean up callback server |
| Retry on transient network errors | Future | 1 retry with backoff on code exchange failure |
| Graceful degradation without `requests` | Future | ImportError → clear message with install instructions |

### Edge Cases

| Scenario | Current Behavior | Hardening Needed |
|----------|-----------------|------------------|
| Browser doesn't open (SSH/headless) | `webbrowser.open()` fails silently | Print auth URL to terminal as fallback |
| Multiple OAuth tabs opened | Last callback wins | Validate state param rejects stale callbacks |
| Ollama installed but not running | Detected, shows instructions | Auto-start via `ollama serve` (done in `ollama_checker.py`) |
| Ollama running, no models | Detected, shows pull command | Auto-pull default model with progress |
| Existing credentials for provider | Silently overwrites | Prompt "Glama already configured. Overwrite?" |
| Corrupt `.oauth-keys.json` | Returns empty dict | Log warning, recreate file |
| Corrupt `remote_providers.yaml` | Returns default config | Log warning, rebuild from defaults |
| Disk full on credential write | Unhandled exception | Catch `OSError`, show clear error message |

### Observability (Future)

| Feature | Description |
|---------|-------------|
| `--verbose` flag | Debug output for OAuth flow steps (URLs, ports, timing) |
| Structured exit codes | 0 = success, 1 = user abort, 2 = auth failure, 3 = network error |
| Audit log | Append provider config events to `runtime/logs/oauth.log` |

## References

- Current installer: `scripts/install.sh`
- ADR-047: Operation Mode Chatbot Experience (audience alignment)
- ADR-045: Launch Plan & Go-To-Market (distribution strategy)
- Python embeddable plugins: https://docs.python.org/3/using/windows.html#the-embeddable-package
- Apple notarization: https://developer.apple.com/documentation/security/notarizing_macos_software_before_distribution
- Inno Setup: https://jrsoftware.org/isinfo.php
- Sparkle framework: https://sparkle-project.org/
