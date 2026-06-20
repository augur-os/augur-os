---
status: Implemented
date: 2026-04-13
deciders:
  - Gur Sannikov
related: []
hub: null
tags:
  - windows
  - platform
  - paths
  - mcp
superseded_by: null
---

# ADR-584: Windows Support Strategy

## Context

Augur needs to support Windows users, not only contributors. The product is not just a CLI — users work with ordinary folders, drag files into tracked locations, let AI clients modify configs outside the repo, and treat project, vault, and documents directories as normal desktop-visible storage. Windows AI clients (Cursor, Claude Desktop) run natively and expect native paths and commands.

Two runtime models are plausible: run Augur through `WSL2` and treat Windows as the host OS, or run Augur natively and treat Windows as a real runtime target. `WSL2` is attractive because Augur contains many Unix-oriented assumptions, but it forces path translation and runtime-boundary handling onto the user surface — exactly where Augur's file-centric workflow assumes ordinary Windows folders. The blocker is not raw access (`WSL2` can read/write `%APPDATA%`) but support coherence: Windows apps need stable launch commands, config generation has to translate paths correctly, and users still think in Windows folders rather than Linux mounts.

The current code has scattered Windows branches in some places, but parts of the support story are stale (the installation guide references locations that no longer exist), and there is no Windows CI or smoke coverage to prevent regression.

## Decision

Adopt **native Windows first-class support** as the official runtime model. `WSL2` remains an optional fallback only for narrowly-scoped dependency cases, never as the base runtime story.

Implementation contract:

1. **Path resolution:** centralize Windows directory helpers (`_windows_roaming_dir`, `_windows_local_dir`) in `src/config/paths.py`. Route all user-facing paths through these helpers. Claude Desktop runtime resolves to `%APPDATA%/Claude` on Windows, `~/Library/Application Support/Claude` on macOS, `$XDG_CONFIG_HOME/Claude` (or `~/.config/Claude`) on Linux. Python executable resolution prefers `.venv/Scripts/python.exe` on Windows.
2. **MCP config writers:** `scripts/mcp_ide_config.py` expands `%APPDATA%`-style variables alongside POSIX `$VAR` syntax. `scripts/configure_mcp.py` becomes the single MCP wiring entry point; `setup_cursor_mcp.py` becomes a thin wrapper that invokes it. Client adapters (`claude_desktop`, `cowork`) consume `get_client_runtime_dir(...)` instead of bespoke Windows path logic.
3. **Bootstrap:** `scripts/install.ps1` aligns with the native runtime contract — references current `scripts/configure_mcp.py`, drops legacy `src/lib/dashboard` and `.claude/skills/knowledge/tests` paths, runs `configure_mcp.py --client cursor --auto` after install.
4. **CI smoke:** `.github/workflows/ci-cross-platform.yml` runs real native checks on Windows runners (path resolution import, `configure_mcp.py --check --verbose`).
5. **Docs:** `docs/guides/installation-windows.md`, `README.md`, and `skills/onboard/references/mode-default.md` / `mode-connect.md` describe the native install path; WSL is mentioned only as an explicit fallback.

Cross-platform core logic stays in Python and Node where possible; Windows-specific behavior lives behind small adapters and is exercised by tests before code lands.

## Consequences

### Positive
- Windows users install Augur without WSL; folders and AI clients behave like ordinary Windows experiences.
- Single shared `src/config/paths.py` helper surface prevents per-script Windows branches from drifting.
- MCP config wiring funnels through one entry point (`configure_mcp.py`); client adapters stop reinventing Windows path logic.
- CI smoke coverage on real Windows runners catches regressions in path handling, subprocess launch, and config generation before release.
- Stale Windows install docs are corrected; soft-launch positioning credible for Windows users.

### Negative
- Native-first means engineering work up front: setup-script cleanup, real Windows CI, regression coverage.
- Windows-specific edge cases (file locking, rename semantics, long paths, Unicode quoting) become first-class design inputs and must be handled, not deferred.
- Phase 1 ships a baseline; deeper Windows-only integrations (launcher polish, shell integration) are deferred to Phase 3.
- Two scheduling/runtime models (native primary, WSL fallback) need crisp boundaries to avoid drifting into two partially-supported worlds.

### Neutral
- macOS and Linux behavior unchanged; this is additive native support, not a rewrite.
- WSL fallback continues to work for specific feature exceptions, but is not advertised as the default path.
- Existing path helpers (`get_project_root`, `get_python_executable`) gain Windows branches but keep their public API.

## Alternatives Considered

### Alternative 1: WSL2-first official Windows support
Run Augur inside WSL and treat Windows as the UI shell around it. Rejected because Augur's value depends on moving files around visible folders; cross-boundary execution makes drag-and-drop, folder ownership, and "where the real files are" confusing — exactly the questions a file-centric product cannot afford.

### Alternative 2: Hybrid with WSL and native as equal primary paths
Document both as supported. Rejected because two equally primary paths multiply the support surface and produce gradual drift into two partially-supported worlds; soft launch cannot afford ambiguous platform stories.

### Alternative 3: Defer Windows support entirely
Ship macOS/Linux first, treat Windows as future work. Rejected because Windows users are part of the target audience now, and stale Windows docs already produce avoidable support failure.

### Alternative 4: Native baseline with no CI coverage
Skip Phase 2 hardening to ship faster. Rejected because past path-handling and subprocess-launch regressions already happened without CI; adding Windows as official without smoke coverage repeats the bug.

## References
- Plan: docs/superpowers/plans/2026-04-13-windows-support-strategy.md
- Spec: docs/superpowers/specs/2026-04-13-windows-support-strategy-design.md
