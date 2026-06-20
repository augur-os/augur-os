---
title: Network Egress Proof
status: customer-review
date: 2026-05-12
owner: platform-admin
adr: ADR-725
---

# Network Egress Proof

This page defines how to prove Augur's network behavior for an enterprise review. The proof is a repeatable procedure, not a blanket claim that Augur never uses the network.

## Egress Categories

| Category | Trigger | Expected destinations | Current control |
| --- | --- | --- | --- |
| Repository install/update | `git clone`, `git fetch`, installer update paths | GitHub remotes | User/admin initiated. |
| Python dependencies | `uv sync`, `uv tool run`, `pip-audit` | PyPI and configured package indexes | Lockfile plus admin network policy. |
| Node dependencies | `corepack`, `pnpm install`, `pnpm audit` | npm registry and pnpm/corepack sources | Lockfile plus admin network policy. |
| System dependencies | Homebrew, apt, Chocolatey/manual installers | Platform package repos | Admin initiated. |
| Optional AI providers | Internal LLM tasks, OCR/vision escalation, configured provider clients | Provider base URLs in config/env | Airplane/local settings for supported flows; no global allowlist yet. |
| OAuth/setup | provider setup wizards and local callback flows | OAuth provider endpoints and loopback callback | User/admin initiated. |
| Local dashboard/MCP | dashboard dev server, MCP bridge, local health checks | Loopback addresses | Local-only in expected idle mode. |
| Local model backends | Ollama/LM Studio probes | Loopback addresses by default | Local backend readiness checks. |

## Static Inventory Commands

Run from the repository root:

```powershell
rg -n "curl|Invoke-RestMethod|Invoke-WebRequest|requests\\.|httpx\\.|urllib\\.request|urlopen|fetch\\(|axios|socket|getaddrinfo|oauth|openai|anthropic|gemini" scripts src project-brain config apps\dashboard
```

Expected: every match is classified as install/update, dependency management, local loopback, optional provider/OAuth, health check, or test/dev-only code.

For dependency manifests:

```powershell
Get-Content pyproject.toml
Get-Content uv.lock | Select-String -Pattern "name = `"urllib3`" -Context 0,8
Get-Content apps\dashboard\package.json
Push-Location apps\dashboard
try {
  corepack pnpm audit --prod
} finally {
  Pop-Location
}
```

Expected as of 2026-05-12: dashboard production audit reports no known vulnerabilities; `uv.lock` pins `urllib3 2.7.0`.

## Runtime Snapshot Commands

Windows:

```powershell
$augur = Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -like "*Augur*" -or $_.CommandLine -like "*augur*" }
$augur | Select-Object ProcessId,Name,CommandLine

$ids = @($augur | ForEach-Object { [int]$_.ProcessId })
Get-NetTCPConnection |
  Where-Object { $ids -contains $_.OwningProcess } |
  Select-Object OwningProcess,State,LocalAddress,LocalPort,RemoteAddress,RemotePort |
  Sort-Object OwningProcess,State,RemoteAddress,RemotePort
```

macOS:

```bash
pgrep -afil 'augur|Augur' || true
lsof -nP -iTCP -sTCP:ESTABLISHED | grep -Ei 'augur|python|node' || true
```

Linux:

```bash
pgrep -afil 'augur|Augur' || true
ss -tpn | grep -Ei 'augur|python|node' || true
```

Expected in local-only idle mode: no established non-loopback remote connections owned by Augur processes. Loopback connections for dashboard, MCP, local model backends, and internal process coordination are expected.

## ADR-725 Windows Snapshot

Captured on 2026-05-12 from the B2 Windows session:

- Active Augur-related processes included `augur_core` MCP servers for Codex/Antigravity, a dashboard dev server from a separate ADR-733 worktree on port 3001, and `augur_framework` for that dashboard.
- TCP connections for the matched set were loopback or listener/bound sockets: `127.0.0.1`, `::`, and `0.0.0.0`.
- No established non-loopback remote connection appeared in the captured set.
- The daemon Scheduled Task existed as `com.augur.daemon`, but `service_healer.py status` reported degraded health because the installed task arguments/status were stale. That is a daemon posture finding, not network egress.

The snapshot is evidence for that machine at that time. It is not a permanent guarantee. Enterprise review should rerun the commands on the deployment image after install and after enabling any optional providers.

## Triage Rules

Classify every non-loopback connection:

| Destination type | Action |
| --- | --- |
| GitHub or package registry during install/update | Allowed only in install/update windows. |
| OAuth provider during setup | Allowed only during setup and documented by provider. |
| AI/OCR provider | Allowed only if the tenant approves that provider and data class. |
| Unknown public IP or domain | Block release; identify callsite before pilot. |
| Private RFC1918 address | Confirm whether it is local backend, proxy, or enterprise service. |
| Loopback | Usually acceptable; confirm owner process and port purpose. |

## Known Gaps

- No global egress allowlist is enforced in code today.
- Airplane/local mode covers selected AI routing paths, not every network primitive.
- Installers intentionally bootstrap dependencies from public registries unless an enterprise mirror is configured.
- Runtime snapshots are point-in-time. Continuous network monitoring is an enterprise deployment concern.
