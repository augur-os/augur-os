---
title: Enterprise Readiness Packet
status: customer-review
date: 2026-05-12
owner: platform-admin
adr: ADR-725
---

# Enterprise Readiness Packet

This packet is the Phase 0 and Phase 1 enterprise review summary for Augur. It gives security reviewers a compact control map and identifies the difference between documented current posture and future hardening work.

## Executive Summary

Augur is suitable for a controlled single-user enterprise pilot only after the local deployment passes the checks in this packet. It is not yet suitable for a locked-down enterprise rollout where unreviewed skills, all egress, and all local script execution must be fail-closed by policy.

Current strengths:

- Local-first storage model with path helpers for vault, documents, runtime, logs, and cache.
- Source-controlled MCP topology.
- Dashboard execution contract routes through MCP instead of direct local execution.
- Explicit daemon service manager with install/status/uninstall paths.
- Lockfile-backed Python and dashboard dependencies.
- Documented network egress proof procedure.

Current gaps:

- No enforced enterprise skill allowlist.
- No global runtime egress allowlist or airgap fail-closed mode.
- No machine-readable vault classification policy.
- Installed Python environments can drift from source lockfiles if `uv sync` is not run.
- Daemon task health must be verified per machine.

## Review Evidence

| Evidence | Command or file | Expected result |
| --- | --- | --- |
| Repo status | `git status --short --branch` | Approved branch and clean worktree. |
| Storage roots | `project.yaml`, `src/config/paths.py` | Vault/documents/runtime/log/cache roots are explicit and path-helper based. |
| MCP topology | `config/system/mcp_servers.yaml` | Only approved local MCP servers are registered. |
| Dashboard dependency audit | `corepack pnpm audit --prod` in `apps/dashboard` | No known production vulnerabilities. |
| Python dependency audit | `pip-audit --path .venv\Lib\site-packages` after `uv sync` | No known vulnerabilities in installed third-party packages. |
| Daemon status | `service_healer.py status` | Healthy service or intentionally uninstalled daemon. |
| Runtime network | `Get-NetTCPConnection` filtered by Augur PIDs | No unexplained non-loopback established connections. |
| Skill allowlist | shared and private skill directory review | Only reviewed skills enabled. |

## CIS Control Mapping Skeleton

### CIS Control 1: Inventory and Control of Enterprise Assets

Augur review requires inventorying the target workstation, checkout path, vault path, documents path, daemon registration, and AI clients configured to launch MCP servers.

Evidence: `project.yaml`, `schtasks /query`, `launchctl print`, client MCP config.

### CIS Control 2: Inventory and Control of Software Assets

Source code, shared skills, private skills, Python packages, Node packages, and optional OCR/system packages must be inventoried.

Evidence: `git rev-parse HEAD`, `Get-ChildItem project-brain\capabilities\skills`, `uv.lock`, `apps/dashboard/pnpm-lock.yaml`.

### CIS Control 3: Data Protection

User data should remain in approved vault and documents roots. Classified data should not be ingested until a classification policy exists.

Evidence: `project.yaml`, path helper review, future classification policy ADR.

### CIS Control 4: Secure Configuration of Enterprise Assets and Software

MCP topology, daemon registration, provider config, and dashboard settings should be reviewed before pilot.

Evidence: `config/system/mcp_servers.yaml`, `config/system/llm.yaml`, daemon status output.

### CIS Control 5: Account Management

Augur runs as the local user by default. Enterprise review should identify which user account owns the scheduled task or LaunchAgent.

Evidence: Windows `Run As User` field; macOS `gui/$(id -u)` service scope.

### CIS Control 6: Access Control Management

Skill execution and provider access currently depend on repo review and user/admin approval. Enforced allowlisting is future work.

Evidence: skill inventory and ADR-735.

### CIS Control 7: Continuous Vulnerability Management

Run dependency audits after synchronizing environments.

Evidence: `corepack pnpm audit --prod` from `apps/dashboard`; `pip-audit --path .venv\Lib\site-packages`; lockfile review.

### CIS Control 8: Audit Log Management

Logs live under `get_logs_dir()`. Current logs are local operational logs, not an enterprise SIEM feed.

Evidence: log path from `src.config.paths`; ADR-735 audit-event proposal.

### CIS Control 9: Email and Web Browser Protections

Not directly applicable to core Augur runtime. Browser/OAuth flows should use managed browser policy.

Evidence: provider setup flow review.

### CIS Control 10: Malware Defenses

Enterprise endpoint controls should scan the repo, vault executable scripts, and dependency cache.

Evidence: endpoint control logs and skill/script inventory.

### CIS Control 11: Data Recovery

Vault and documents roots need enterprise backup policy. Runtime cache is not authoritative data.

Evidence: storage root inventory and backup configuration.

### CIS Control 12: Network Infrastructure Management

Install and runtime egress should be segmented by allowlist.

Evidence: network snapshot and enterprise firewall/proxy logs.

### CIS Control 13: Network Monitoring and Defense

Runtime proof commands provide point-in-time evidence. Enterprise rollout should collect continuous telemetry externally.

Evidence: `Get-NetTCPConnection`, firewall logs, proxy logs.

### CIS Control 14: Security Awareness and Skills Training

Operators need training that skills are executable code and that local-first does not mean no network.

Evidence: deployment guide acknowledgement.

### CIS Control 15: Service Provider Management

Approved AI/OCR/OAuth providers must be documented with data classes allowed to leave the device.

Evidence: provider configuration and approval records.

### CIS Control 16: Application Software Security

Dashboard runtime must not bypass MCP. Code execution surfaces should be reviewed before release.

Evidence: dashboard direct-exec search and ADR-735.

### CIS Control 17: Incident Response Management

Incident response should include disabling daemon persistence, removing MCP client registrations, preserving logs, and blocking egress.

Evidence: deployment guide uninstall commands and log locations.

### CIS Control 18: Penetration Testing

Before broad rollout, test skill execution boundaries, dashboard MCP boundaries, daemon persistence, and egress controls.

Evidence: test plan and results from target enterprise image.

## NIST Function Mapping Skeleton

| Function | Augur evidence |
| --- | --- |
| Govern | ADR-725, ADR-735, repository agent rules, enterprise deployment guide. |
| Identify | Asset inventory, storage root inventory, skill inventory, dependency lockfiles. |
| Protect | Path separation, MCP topology control, dependency pinning, manual skill review. |
| Detect | Dependency audits, daemon status, runtime network snapshots, logs. |
| Respond | Daemon uninstall, MCP config rollback, provider disablement, egress block. |
| Recover | Git rollback, vault/document backup restore, `uv sync`, dashboard rebuild. |

## Enterprise Go/No-Go

Go for a limited pilot only if:

- Network snapshot has no unexplained non-loopback connections.
- Dependency audits pass after environment sync.
- Daemon status is healthy or daemon is disabled.
- Private skills are reviewed or disabled.
- Provider endpoints and data classes are approved.
- Gaps are accepted in writing.

No-go if:

- Any unreviewed private skill can execute.
- Daemon points at a stale checkout.
- Python or Node dependency audits show known unresolved vulnerabilities.
- Runtime shows unexplained external connections.
- The deployment requires enforced airgap or skill allowlisting before ADR-735 is implemented.
