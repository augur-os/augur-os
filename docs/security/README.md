---
title: Augur Enterprise Security Review
status: customer-review
date: 2026-05-12
owner: platform-admin
adr: ADR-725
audience:
  - enterprise-security
  - it-administration
  - augur-maintainers
---

# Augur Enterprise Security Review

This folder is the public-facing Phase 0 and Phase 1 packet for ADR-725. It is written for enterprise security reviewers who need to understand what Augur runs, what it can reach, where data lives, and which controls are already documented versus proposed follow-up work.

## Customer Review Release

This packet is ready for customer review as a Phase 0 and Phase 1 security package. It supports review of a controlled single-user managed-laptop pilot. It does not claim that Augur has a completed enterprise lockdown mode.

Reviewers should start with:

1. [Enterprise Readiness Packet](enterprise-readiness-packet.md)
2. [Threat Model](threat-model.md)
3. [Architecture Trust Boundaries](architecture-trust-boundaries.md)
4. [Network Egress Proof](network-egress-proof.md)
5. [Enterprise Deployment Guide](enterprise-deployment-guide.md)

Known follow-up work is intentionally called out in the packet and tracked through follow-up ADRs rather than hidden as completed posture.

## Packet Contents

- [Threat Model](threat-model.md) - assets, trust boundaries, risks, current controls, and tracked gaps.
- [Architecture Trust Boundaries](architecture-trust-boundaries.md) - repository, vault, runtime, dashboard, MCP, daemon, and AI-provider boundaries.
- [Network Egress Proof](network-egress-proof.md) - static inventory, runtime snapshot commands, and evidence limits.
- [Enterprise Deployment Guide](enterprise-deployment-guide.md) - install, update, daemon, network, and operations guidance for managed devices.
- [Enterprise Readiness Packet](enterprise-readiness-packet.md) - claim summary, control mapping skeleton, and review checklist.

## Claim Summary

Augur is local-first, but it is not a sealed offline binary. Enterprise reviewers should evaluate these claims:

| Claim | Current posture | Evidence |
| --- | --- | --- |
| User content storage is local-first | User-editable data resolves through `src.config.paths` into the configured vault and documents directories. | `project.yaml`, `src/config/paths.py` |
| MCP servers are local process integrations | The source-of-truth manifest launches Python modules over client-managed stdio, with no MCP listener port in the manifest. | `config/system/mcp_servers.yaml` |
| Dashboard execution is mediated | Dashboard code should call MCP through `POST /api/mcp/tool`; direct local execution from dashboard code is disallowed by repository rules. | `AGENTS.md`, dashboard MCP routes |
| Runtime egress is present but classifiable | Installers, dependency managers, setup/OAuth flows, optional AI/OCR providers, and local backend probes can create network traffic. | `network-egress-proof.md` |
| Background persistence is explicit | The unified daemon is installed as a macOS LaunchAgent or Windows Scheduled Task named from `project.yaml`, currently `com.augur.daemon`. | `project-brain/capabilities/skills/daemon/scripts/service_healer.py` |
| Enterprise policy mode is not implemented yet | Current skill and automation surfaces can execute scripts under user/agent control. A follow-up ADR proposes a fail-closed enterprise mode. | `ADR-735` |

## Emergency Review Floor

Run these commands from the Augur repository root unless a command says otherwise.

```powershell
git status --short --branch
Get-Content config\system\mcp_servers.yaml
Get-Content project.yaml
```

Expected: the checkout is on the intended branch, `mcp_servers.yaml` lists local Python module commands for `augur-core`, `augur-framework`, `augur-vault`, and `augur-ingest`, and `project.yaml` names the configured vault and documents roots.

```powershell
Push-Location apps\dashboard
try {
  corepack pnpm audit --prod
} finally {
  Pop-Location
}
```

Expected as of the 2026-05-12 ADR-725 review: `No known vulnerabilities found` for dashboard production dependencies.

```powershell
$env:AUGUR_DIR = (Get-Location).Path
$python312 = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
uv tool run --python $python312 pip-audit --progress-spinner off --desc off --path "$env:AUGUR_DIR\.venv\Lib\site-packages"
```

Expected on a freshly synchronized Python environment: no known vulnerabilities outside private editable packages that are not published to PyPI. During the ADR-725 review, the first local shared-venv audit found stale `urllib3 2.6.3` even though `uv.lock` already pinned `urllib3 2.7.0`; after `uv sync --python <python-3.12-path>`, the same `pip-audit --path` command reported `No known vulnerabilities found`. Run `uv sync` before treating an installed-environment audit as source posture.

```powershell
$env:AUGUR_DIR = (Get-Location).Path
schtasks /query /tn "com.augur.daemon" /fo LIST /v
& "$env:AUGUR_DIR\.venv\Scripts\python.exe" project-brain\capabilities\skills\daemon\scripts\service_healer.py status
```

Expected: the scheduled task, if installed, points at the intended Augur checkout and the service status is healthy. A worktree checkout can legitimately report a mismatch if the installed task points at the main checkout. A mismatch from the main checkout is an operations finding and should be remediated before an enterprise pilot.

```powershell
$augur = Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -like "*Augur*" -or $_.CommandLine -like "*augur*" }
$ids = @($augur | ForEach-Object { [int]$_.ProcessId })
Get-NetTCPConnection |
  Where-Object { $ids -contains $_.OwningProcess } |
  Select-Object OwningProcess,State,LocalAddress,LocalPort,RemoteAddress,RemotePort
```

Expected in local-only idle mode: no established non-loopback remote connections for Augur-owned processes. Any non-loopback remote address should be classified in [Network Egress Proof](network-egress-proof.md) before enterprise rollout.

## Follow-Up ADRs

- `ADR-735` proposes enterprise policy mode: skill allowlist, disabled auto-discovered script execution, report-only automation defaults, and SIEM-forwardable audit events.
- Future work should add an admin-configurable egress allowlist and airgap fail-closed mode.
- Future work should add a vault classification policy for excluding classified roots from ingestion.
