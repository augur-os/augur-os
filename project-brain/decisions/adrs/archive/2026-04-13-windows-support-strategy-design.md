# Windows Support Strategy Design

**Date:** 2026-04-13  
**Status:** Proposed  
**Scope:** official Windows support model for Augur, including runtime strategy, file UX expectations, and WSL fallback boundaries

## Goal

Define how Augur should support Windows users without compromising the product's core file-based workflow model.

Augur is not only a CLI. Users are expected to work with ordinary folders, drag files into tracked locations, let AI clients modify configs outside the repo, and treat project, vault, and documents directories as normal desktop-visible storage. The Windows support strategy must preserve that experience.

## Problem

There are two plausible ways to support Windows:

- run Augur through `WSL2` and treat Windows as the host OS
- make Augur run natively on Windows and treat Windows as a real runtime target

`WSL2` is attractive because Augur already contains many Unix-oriented assumptions. However, the product's normal workflows depend on file manipulation in user-visible folders and Windows-native AI clients. That makes runtime boundaries visible to the user.

The decision is therefore not just about engineering effort. It is about whether the supported Windows experience should feel like:

- a Linux tool running on a Windows machine, or
- a Windows product that happens to be cross-platform internally

## Goals

- Support Augur for real Windows end users, not just contributors.
- Preserve normal Windows file workflows for project, vault, and documents directories.
- Keep AI client configuration and MCP wiring understandable and supportable on Windows.
- Minimize long-term support confusion around path ownership and file locations.
- Allow limited fallbacks for dependency-heavy features without making them the default product story.

## Non-Goals

- Making every Windows-specific integration feature-complete in the first release.
- Preserving a `WSL2`-first architecture as the official user path.
- Supporting multiple equally primary Windows runtime models.
- Solving every optional dependency in v1 of Windows support.

## User Constraints Captured During Brainstorming

- Windows support is intended for users, not just developers.
- Shipping sooner with lower maintenance matters more than a perfectly polished Windows-native shell experience.
- Moderate setup friction is acceptable if it is cleanly documented.
- The first release does not need deep Windows-only integration.
- Normal Windows app and folder usage is the primary target:
  - Explorer-visible folders
  - Windows AI clients such as Cursor and Claude Desktop
  - drag-and-drop into tracked folders
  - project, vault, and documents directories behaving like ordinary Windows locations

These constraints rule out a runtime model that makes file ownership or path translation feel ambiguous to the user.

## Approaches Considered

### 1. Native Windows first-class runtime

Run Augur natively on Windows and treat Windows as an official runtime target.

Pros:

- Best match for Augur's file-centric product model.
- Project, vault, and documents folders behave like ordinary Windows folders.
- Windows AI clients can point at native Windows commands and paths.
- Avoids persistent confusion about whether the canonical file lives in Windows or WSL.
- Stronger long-term support story if Windows is advertised as supported.

Cons:

- Requires more engineering work up front.
- Needs real Windows CI, documentation, and regression coverage.
- Forces cleanup of Unix assumptions in setup scripts and runtime helpers.

### 2. Hybrid: native Windows baseline with optional WSL fallback

Make native Windows the official path, but allow WSL for isolated features or power-user flows where Linux tooling is easier.

Pros:

- Preserves the correct product story for normal Windows usage.
- Gives an escape hatch for specific tools that remain Linux-friendlier.
- Allows phased rollout without blocking Windows support on every optional dependency.

Cons:

- Increases support surface area if fallback boundaries are unclear.
- Risks gradual drift into two partially-supported worlds unless tightly scoped.

### 3. WSL2-first official Windows support

Run Augur inside WSL and treat Windows mostly as the UI shell around it.

Pros:

- Lowest short-term engineering cost.
- Best reuse of current Unix-oriented assumptions.

Cons:

- Misaligned with Augur's normal file workflows.
- Introduces path translation and runtime-boundary complexity directly into onboarding and support.
- Makes AI client config generation more fragile because Windows apps often need `wsl.exe` bridging and cross-boundary command handling.
- Creates user confusion around drag-and-drop, folder ownership, and "where the real files are."

## Recommendation

Recommend **native Windows first-class support** as the official Windows model.

`WSL2` should remain an optional fallback only for narrowly-scoped dependency cases, not as the base runtime story.

This is the best fit for Augur because the product assumes that users and AI clients interact with real folders and real configs outside the repo. Once those locations are part of the user experience, a cross-boundary runtime becomes product friction rather than hidden implementation detail.

## Support Model

Official Windows support means:

- Augur runs natively on Windows 10/11.
- Project, vault, documents, runtime, and client config paths resolve to normal Windows locations.
- Supported Windows AI clients are configured using native Windows paths and commands.
- Windows users do not need `WSL2` for baseline setup, MCP wiring, dashboard use, or normal file workflows.
- `WSL2` is allowed only as an explicit fallback for isolated features that are genuinely easier or only available there.

## Platform Strategy

Windows should be treated as a real target platform, not a compatibility wrapper.

The implementation model should be:

- keep the core logic cross-platform in Python and Node where possible
- isolate OS-specific behavior behind small adapters
- route all user-facing paths through `src.config.paths`
- centralize process launch and client-config writing so Windows-specific behavior is explicit and testable

Windows-specific concerns that must be handled as first-class design inputs:

- path resolution
- command quoting
- virtual environment executable resolution
- file locking and rename semantics
- client config locations for Windows-native AI apps
- dashboard and MCP startup from Windows shells

## Why WSL Is Not The Primary Recommendation

`WSL2` can technically read and write Windows-side files, including AI client config files under `%APPDATA%` and `%LOCALAPPDATA%`. That means raw access is not the blocker.

The blocker is support coherence:

- Windows apps need stable launch commands, often through `wsl.exe`
- config generation has to translate path and runtime boundaries correctly
- users still think in Windows folders and Windows apps, not Linux mounts
- file-centric workflows become harder to explain when storage and execution live on different sides of the boundary

For a tool whose value depends on moving files around visible folders, that cost is too close to the product surface.

## Rollout Phases

### Phase 1: Native baseline

Deliver the minimum official Windows support contract:

- native install/bootstrap path
- native path resolution for project, vault, documents, and runtime
- native MCP startup
- native AI client config writers for the main supported clients
- dashboard runs locally on Windows
- standard file workflows work in ordinary Windows folders

### Phase 2: Compatibility hardening

Add supportability and regression protection:

- Windows CI coverage
- smoke tests for path handling, config generation, and MCP startup
- locked-file and rename edge-case testing
- quoting, Unicode, spaced-path, and long-path verification
- refreshed Windows docs that reflect the actual repo layout

### Phase 3: Optional enhancements

Add polish after the baseline is stable:

- Windows launcher improvements
- better shell integration
- optional WSL fallback docs for specific features only
- targeted native integrations that are valuable but not required for baseline support

## Key Risks

### 1. Tooling drift

Some code already has Windows-aware branches, but the current docs and scripts indicate that parts of the support story are stale. Superficial platform checks are not the same as supported runtime behavior.

### 2. Boundary leaks

Native Windows support fails if even one key bootstrap or config path still assumes Unix layout or process semantics.

### 3. Documentation credibility

The current Windows installation guide references locations that no longer exist in the current repo layout. If Windows support is made official, stale docs will produce avoidable support failure immediately.

### 4. Test gap

Without Windows CI and smoke coverage, regressions will likely recur in path handling, subprocess launch, and AI client configuration.

## Mitigations

- Define a narrow v1 Windows support contract and enforce it.
- Audit setup scripts, adapters, and client config writers that touch Windows paths or commands.
- Centralize platform-sensitive runtime helpers instead of scattering one-off checks.
- Add Windows smoke tests before expanding the supported feature surface.
- Keep `WSL2` explicitly secondary and feature-scoped so documentation never implies two equal primary paths.

## User-Facing Outcome

After this strategy is implemented, a Windows user should be able to:

- install Augur without needing WSL
- keep Augur folders in normal Windows-visible locations
- drag files into tracked folders from Explorer
- let supported AI clients use Augur through native Windows configuration
- use the dashboard and common file-based workflows without path-boundary confusion

If a specific optional feature still needs Linux-friendly tooling, that should appear as a clearly documented exception, not the definition of Windows support.

## Decision Summary

- Official Windows support model: `native Windows`
- `WSL2` role: optional fallback only
- Primary reason: Augur's product model depends on normal Windows folder and AI-client behavior
- First-release scope: baseline native runtime, file workflows, and client wiring; defer nonessential deep integrations
