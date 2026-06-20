---
title: Augur Threat Model
status: customer-review
date: 2026-05-12
owner: platform-admin
adr: ADR-725
---

# Threat Model

This threat model covers the local Augur repository, project-brain skills, private vault integration, dashboard, MCP servers, daemon automation, and install/update paths. It does not certify a hardened enterprise mode; it records the current system and the gaps that must be closed before a restricted enterprise deployment.

## Assets

| Asset | Location | Sensitivity | Notes |
| --- | --- | --- | --- |
| User vault | `get_vault_dir()`, configured in `project.yaml` | High | Personal notes, wiki pages, skill data, and user-editable memory live outside the repo. |
| Documents | `get_documents_dir()`, configured in `project.yaml` | High | External collateral, PDFs, exports, and binaries. |
| Runtime state | `get_runtime_dir()` | Medium to high | Daemon status, task state, IPC files, generated runtime metadata. |
| Logs | `get_logs_dir()` | Medium | Can include process health, errors, tool metadata, and operational traces. |
| Cache | `get_cache_dir()` | Medium | Generated artifacts, temporary files, and backups. |
| Shared skills | `project-brain/capabilities/skills/` | Medium | Team-owned executable skill logic and dashboard/page metadata. |
| Private skills | configured vault `skills/` | High | User-owned executable and data-bearing skill logic. |
| AI client configuration | Client-specific config dirs | Medium | MCP server registration and environment variables. |
| Secrets | Environment variables, private config | Critical | API keys should be referenced by environment variable name, not committed into repo config. |

## Actors

| Actor | Capability | Trust assumption |
| --- | --- | --- |
| Local user | Runs installers, slash commands, AI clients, and dashboard. | Trusted to approve local automation on their device. |
| AI client session | Calls MCP tools and writes files through agent workflows. | Semi-trusted; must follow repository rules and user approvals. |
| Skill code | Can define tools, scripts, docs, generated dashboard pages, and automation. | Trusted only after source review or allowlisting. |
| Dashboard | Presents UI and calls MCP routes. | Must not bypass MCP with direct local execution. |
| Daemon | Runs background checks and scheduled automation. | Trusted only within configured schedule and approval boundaries. |
| External provider | Receives optional AI/OCR/OAuth/update requests. | Untrusted network boundary. |
| Enterprise admin | Manages device policy, network allowlists, and audit collection. | Trusted operator. |

## Trust Boundaries

1. Repository to user data: code lives in the repo; user data lives in vault/documents/runtime/log/cache roots resolved by `src.config.paths`.
2. Dashboard to local system: dashboard code must cross MCP and cannot call local scripts directly.
3. AI client to MCP server: AI clients start Python MCP servers over stdio from `config/system/mcp_servers.yaml`.
4. Skill source to execution: skills are executable units; current policy relies on repository review and agent rules rather than a runtime enterprise allowlist.
5. Local machine to network: dependency installation, update checks, OAuth, optional AI providers, and optional OCR/cloud flows cross the network.
6. Foreground session to daemon: the daemon can persist beyond the current shell as a LaunchAgent or Scheduled Task.

## Surface Review

### Network Egress

Current egress is classifiable, not absent. Installers call GitHub and Astral, dependency managers call package registries, and optional provider flows can call configured model/OAuth endpoints. Runtime local-only mode should show only loopback traffic, but the current codebase does not yet have a single enforced egress allowlist. See [Network Egress Proof](network-egress-proof.md).

Risk: a reviewer may assume "local-first" means no egress. That is not the current claim.

Control: document each egress category, run static inventory, and capture runtime TCP snapshots for the target deployment.

Gap: admin-configurable egress allowlist and airgap fail-closed mode are follow-up work.

### MCP Trust Boundary

`config/system/mcp_servers.yaml` registers `augur-core`, `augur-framework`, `augur-vault`, and `augur-ingest` as local Python module commands with `PYTHONPATH` scoped to the repo, shared vault, and MCP package. The manifest does not define an inbound MCP listener.

Risk: MCP tools can bridge AI-client instructions to local file and script operations.

Control: keep MCP topology source-controlled, route dashboard actions through `POST /api/mcp/tool`, and expose broad capabilities through CLI surfaces rather than an unbounded direct client tool list.

Gap: runtime policy labels and per-tool enterprise allow/deny enforcement are proposed by ADR-735.

### Code Execution

Augur intentionally orchestrates local scripts: slash commands, auto-loops, skill tools, daemon jobs, setup scripts, and installers all execute code. The current repository rules require command discipline and user-visible verification, but there is no enterprise runtime mode that disables auto-discovered scripts by default.

Operations that should require explicit user approval or prior allowlisting in enterprise mode:

- Installing or updating the repo.
- Running dependency managers (`uv`, `pnpm`, `corepack`, `npm`, Homebrew, apt).
- Starting persistent background services.
- Running auto-fix loops or adaptive remediation.
- Running skill scripts from private vault skills.
- Calling external AI/OCR/OAuth endpoints.
- Dispatching agent CLI subprocesses from daemon attention workflows.

Risk: a compromised or unreviewed skill can gain local execution within the user's account.

Control: repository reviews, git hooks, skill placement rules, and manual verification gates.

Gap: ADR-735 proposes `--enterprise` policy mode with a skill allowlist, disabled auto-discovered script execution, report-only automation defaults, and SIEM-forwardable audit events.

### Daemon And Persistence

The unified daemon is installed as:

- Windows Scheduled Task: `com.augur.daemon`
- macOS LaunchAgent: `~/Library/LaunchAgents/com.augur.daemon.plist`

The label derives from `project.yaml` through `service_healer.py`. The daemon status command reports whether the installed task matches the current checkout.

Risk: a stale or mismatched task can keep running old code after repo movement or upgrade.

Control: `service_healer.py status`, `heal`, and `uninstall`; scheduled task and LaunchAgent inspection commands in the deployment guide.

Gap: enterprise deployment should require a clean daemon status before pilot approval.

### Install And Supply Chain

Install flows fetch from GitHub, Astral, package registries, and platform package managers. `uv.lock` and `apps/dashboard/pnpm-lock.yaml` are the source lockfiles. As of the ADR-725 review, `corepack pnpm audit --prod` from `apps/dashboard` reported no known dashboard production vulnerabilities. A first local installed-environment Python audit found stale `urllib3 2.6.3` even though `uv.lock` pins `urllib3 2.7.0`; after `uv sync`, `pip-audit --path` reported no known third-party vulnerabilities. Installed environment drift must still be checked separately from source posture.

Risk: dependency drift or stale venvs can leave patched source locks but vulnerable local environments.

Control: run `uv sync` from a supported Python version before auditing installed site-packages; treat private editable packages as source-reviewed rather than PyPI-audited.

Gap: enterprise install should produce a machine-readable dependency attestation.

## Abuse Cases

| Abuse case | Impact | Current mitigation | Follow-up |
| --- | --- | --- | --- |
| Unreviewed private skill runs arbitrary script | Data exposure or local code execution | Skill placement rules, agent rules, user approval | ADR-735 allowlist and script policy |
| Dashboard route bypasses MCP and spawns a process | UI-triggered local execution outside MCP audit path | Repository rule forbids this; lint/review should catch it | Route-level execution guard |
| Stale daemon task runs old checkout | Unexpected persistence and old code execution | `service_healer.py status` detects mismatch | Enterprise preflight gate |
| Optional provider sends content to cloud | Confidential data leaves device | Airplane/local model settings for some flows; explicit provider config | Egress allowlist and airgap mode |
| Stale venv has vulnerable dependency | Known CVE present despite lockfile fix | Installed-env audit exposes drift | Install/update sync gate |

## Security Decision Log

- Current documentation can support an enterprise review, but it does not claim enterprise lockdown.
- The minimum acceptable enterprise pilot requires: clean daemon status, clean production dependency audit, static egress inventory, runtime network snapshot, and a reviewed list of enabled skills.
- Enterprise lockdown needs implementation work tracked by ADR-735 and future egress/classification ADRs.
