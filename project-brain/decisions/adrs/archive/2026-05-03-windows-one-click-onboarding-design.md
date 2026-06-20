---
title: Windows One-Click Onboarding Design
date: 2026-05-03
status: proposed
scope: design
related:
  - 2026-03-23-one-click-onboarding-design.md
  - 2026-04-13-windows-support-strategy-design.md
  - 2026-04-14-daemon-registration-windows-parity-design.md
---

# Windows One-Click Onboarding Design

## Purpose

A non-technical Windows user should be able to start from `augur.run`, copy one onboarding prompt into ChatGPT or Codex, and let Augur finish the core setup with minimal judgment required from the user.

The v1 target is online-first setup for a fresh Windows PC. It is not an offline installer bundle. The setup may use the network, GitHub, `winget`, OpenAI sign-in, and normal Windows permission prompts.

## Problem

Augur already has a native Windows installer, Windows setup documentation, Codex configuration work, one-click onboarding concepts, and a Windows daemon parity design. Those pieces are not yet packaged into a smooth first-run path for a Windows user who does not understand repositories, virtual environments, MCP config, daemon registration, or dashboard verification.

The missing product experience is an agent-guided bootstrap that:

- installs missing prerequisites automatically,
- bootstraps Codex CLI when it is not present,
- hands off setup ownership to repo-owned Augur scripts,
- registers and verifies the daemon,
- configures Codex MCP and plugin surfaces,
- verifies the dashboard and onboarding status,
- reports a simple ready or blocked state.

## Goals

- Support a fresh Windows 10/11 machine as the v1 target.
- Start from a versioned `augur.run` prompt copied into ChatGPT or Codex.
- Use `winget` to install Git, Python, Node.js, and package-manager-supported prerequisites when missing.
- Install Codex CLI automatically through the current official install channel, using `winget` only if that channel is available and current.
- Make setup resumable through explicit checkpoints.
- Keep actual Augur setup logic inside the Augur repo, not inside a giant prompt.
- Configure Codex MCP, plugin-pack registration, and generated command/skill surfaces.
- Register the Augur daemon through the Windows Task Scheduler backend.
- Verify the dashboard in a browser-capable client check, not only with an HTTP response.
- End with a short user-facing readiness report.

## Non-Goals

- Do not build a signed MSI/EXE installer for v1.
- Do not build an offline USB/download bundle for v1.
- Do not require the user to preinstall Git, Python, Node.js, `uv`, or Codex CLI.
- Do not configure local LLM/Ollama support in v1.
- Do not configure personal integrations such as Google, Gmail, Drive, Obsidian, or vault-specific credentials in v1.
- Do not claim success when MCP, daemon, dashboard, or onboarding verification failed.

## Recommended Approach

Use a staged agent bootstrap.

The `augur.run` prompt is the user-facing launcher. It should be short, versioned, and safe to paste into ChatGPT or Codex. It downloads or prints one Windows PowerShell bootstrap command, explains that Windows may ask for permissions, and instructs the agent or user to run the bootstrapper.

The PowerShell bootstrapper owns machine preparation. It checks prerequisites, installs supported tools with `winget`, installs Codex CLI through the current official install channel when missing, clones or updates Augur, writes checkpoints, and prepares the Codex handoff.

Codex owns the repo-specific setup after it exists and the user is signed in. The final Augur setup must run from the installed repo root so it can use current repo scripts, path helpers, MCP writers, generated-surface sync, daemon registration, and verification tools.

This is preferable to a single giant prompt because failures become resumable stages instead of one long opaque agent transcript. It is preferable to an MSI/EXE for v1 because it reuses existing Augur scripts and can ship sooner.

## User Flow

1. The user opens `augur.run` on the new Windows machine.
2. The user copies the Windows onboarding prompt.
3. The user pastes the prompt into ChatGPT or Codex.
4. If the active surface cannot run local commands, the prompt gives one PowerShell command for the user to run.
5. The bootstrapper installs or verifies Git, Python 3.11+, Node.js 20+, `uv`, and Codex CLI.
6. If Codex needs sign-in, the user completes OpenAI authentication.
7. The bootstrapper clones or updates Augur under the configured install directory.
8. Codex is launched or instructed from the Augur repo root with a second, repo-specific handoff prompt.
9. The Augur setup orchestrator runs dependencies, MCP/plugin sync, daemon registration, dashboard verification, and `/onboard --status`.
10. The user receives a final status: `Ready`, `Needs sign-in`, `Needs reopen`, `Needs permission`, or `Blocked`.

## Components

### `augur.run` Prompt

The prompt is the public entrypoint. It should:

- identify itself with a version and date,
- target Windows online setup,
- avoid embedding the full installer logic,
- instruct the local agent to run the bootstrapper,
- fall back to one PowerShell command if the current ChatGPT surface cannot execute local commands,
- explain that sign-in and Windows permission prompts may appear.

### Windows Bootstrapper

The bootstrapper is a PowerShell script designed to be safe to rerun. It should:

- detect Windows version and PowerShell capability,
- check `winget`,
- install Git, Python, Node.js, and package-manager-supported prerequisites when missing,
- install Codex CLI through the current official install channel when missing,
- update PATH for the current process where possible,
- detect when a fresh terminal reopen is required,
- clone or update Augur,
- write checkpoint state after every completed stage,
- write detailed logs to a known local path,
- hand off to Codex from the repo root.

### Codex Handoff

The Codex handoff should happen only after Codex CLI is installed and the user has authenticated. The handoff prompt should be short and deterministic:

- set the repo root as the working directory,
- run the repo-owned setup orchestrator,
- report the final readiness state,
- preserve the detailed log path for troubleshooting.

### Augur Setup Orchestrator

The orchestrator is a repo-owned command or script. It should:

- run `uv sync --group dev --extra windows`,
- run `pnpm install`,
- configure Codex MCP and plugin-pack surfaces through the canonical sync/config writers,
- verify no legacy `augur_mcp` wiring remains,
- register or heal the Windows daemon Task Scheduler task,
- start or verify the daemon,
- start or verify the dashboard,
- verify the dashboard reaches interactive state,
- run `/onboard --status` or the underlying status implementation,
- emit a machine-readable setup report and a short user summary.

### Readiness Report

The readiness report should be short enough for a non-technical user. It should not dump logs unless blocked.

Allowed top-level states:

| State | Meaning |
| --- | --- |
| `Ready` | Core Augur setup passed verification. |
| `Needs sign-in` | Codex is installed but OpenAI authentication is incomplete. |
| `Needs reopen` | PATH or shell state changed and a fresh PowerShell/Codex session is required. |
| `Needs permission` | Windows permission, execution policy, firewall, or package install approval blocked progress. |
| `Blocked` | Automation cannot continue; show the exact next action and log path. |

## Checkpoint State

The bootstrapper should persist state under a platform-native setup path such as:

```text
%LOCALAPPDATA%\Augur\setup\bootstrap-state.json
```

Minimum checkpoint keys:

- `prerequisites_installed`
- `codex_installed`
- `codex_authenticated`
- `repo_ready`
- `dependencies_ready`
- `mcp_configured`
- `daemon_registered`
- `dashboard_verified`
- `onboard_status_clean`

The checkpoint file should be treated as setup state, not user data. It belongs in local application data, not in the repo or vault.

## Error Handling

Setup should fail honestly and resume cleanly.

- Missing prerequisites should be installed automatically with `winget` when possible.
- Codex CLI should be installed automatically through the current official install channel, with the chosen channel logged in the setup report.
- If `winget` is missing or blocked, the user gets a direct install instruction and the state is `Blocked`.
- If a package install changes PATH but the current process cannot see it, the state is `Needs reopen`.
- If Codex is installed but not authenticated, the state is `Needs sign-in`.
- If Windows blocks script execution, package installation, firewall access, or Task Scheduler registration, the state is `Needs permission`.
- If MCP config, daemon registration, dashboard verification, or onboard status fails, the state is not `Ready`.
- Optional features may be reported as unavailable, but core readiness cannot be green unless every core verification passes.

## Verification

V1 is complete only when a fresh Windows machine can reach a verified state.

Core verification includes:

- Git, Python, Node.js, `uv`, and Codex CLI are installed and visible in a fresh PowerShell session.
- Augur repo is cloned or updated.
- `uv sync --group dev --extra windows` succeeds.
- `pnpm install` succeeds.
- Codex MCP config is present and generated by the canonical writer.
- Codex plugin-pack registration is present.
- Generated Codex command/skill surfaces are present.
- Legacy `augur_mcp` runtime wiring is absent.
- Windows daemon Task Scheduler registration exists and points at the current repo and venv.
- Daemon status is healthy.
- Dashboard reaches interactive state in a browser-capable smoke.
- Onboarding status reports core setup ready.

## Success Criteria

The v1 Windows onboarding work is successful when:

- a non-technical user can start from `augur.run` and finish core setup without understanding the codebase,
- setup can install missing prerequisites automatically through `winget` where supported,
- Codex CLI can be installed and authenticated as part of the flow,
- setup can resume after sign-in, terminal reopen, or permission interruption,
- final readiness is based on real checks rather than script completion,
- failures are classified into clear user-facing states,
- detailed logs and checkpoint state are available for support,
- core setup does not require local LLMs or personal integration credentials.

## Risks

### ChatGPT Cannot Execute Local Commands

Plain ChatGPT may not be able to run PowerShell locally. The prompt must detect or explain this boundary and provide one command the user can run manually. Codex becomes the local execution owner after installation and sign-in.

### Codex Authentication Interrupts Automation

OpenAI sign-in may require browser interaction. The setup should classify this as `Needs sign-in` and resume after authentication instead of treating it as a failure.

### PATH Drift After Package Installation

Windows package installers often update PATH for future shells. The bootstrapper must detect when the current process cannot see a newly installed tool and return `Needs reopen`.

### Generated Surface Drift

Prior Codex failures have come from stale runtime config, missing plugin registration, and stale plugin cache surfaces. The setup orchestrator must verify live Codex config and generated surfaces, not only write files.

### Daemon False Positive

Task Scheduler registration alone is not enough. The orchestrator must verify both OS registration and daemon-internal health.

### Dashboard False Positive

HTTP 200 does not prove the dashboard works. The setup must use a browser-capable interactive check for the affected dashboard route.

## Open Implementation Boundary

The design intentionally does not choose the final command names or file names for the bootstrapper and setup orchestrator. The implementation plan should select names that fit existing Augur conventions, likely near `scripts/install.ps1`, `skills/onboard/install.md`, and the existing onboarding/status scripts.
