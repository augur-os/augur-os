---
title: Architecture Trust Boundaries
status: customer-review
date: 2026-05-12
owner: platform-admin
adr: ADR-725
---

# Architecture Trust Boundaries

Augur is a local-first application composed of a repo, a shared skill vault, a private user vault, local runtime state, a dashboard, AI clients, MCP servers, and optional external providers. This page defines the enterprise review boundaries.

## Storage Boundaries

| Boundary | Source of truth | Enterprise review question |
| --- | --- | --- |
| Repo code | `src/`, `apps/dashboard/`, `scripts/`, `config/`, `docs/` | Is executable code reviewed and version-controlled? |
| Shared/team skills | `project-brain/capabilities/skills/{skill}/` | Which team skills are enabled and who owns them? |
| Private/user skills | configured vault `skills/{skill}/` | Which private skills are allowed to execute? |
| User notes and memory | `get_vault_dir()` | What classification level is allowed in the vault? |
| External documents | `get_documents_dir()` | Which document roots are allowed for ingestion? |
| Runtime state | `get_runtime_dir()` | Can state files leak sensitive metadata or stale execution state? |
| Logs | `get_logs_dir()` | Which logs are retained, rotated, and collected? |
| Cache | `get_cache_dir()` | Are generated artifacts and backups bounded and outside the repo? |

All code that resolves these paths should use `src.config.paths`. Hardcoded local paths are not acceptable in enterprise-facing code.

## MCP Boundary

The MCP topology is declared in `config/system/mcp_servers.yaml`.

| Server id | Tier | Command | Bundle | Boundary |
| --- | --- | --- | --- | --- |
| `augur-core` | Project | `python -m augur_core` | none | Registry and discovery operations. |
| `augur-framework` | Project | `python -m augur_framework` | none | Operational project tools. |
| `augur-vault` | Vault | `python -m augur_shared.bundle_server vault` | `vault` | Private vault integration. |
| `augur-ingest` | Vault | `python -m augur_shared.bundle_server ingest` | `ingest` | Inbox, wiki, URL capture, and source cards. |

The manifest sets:

```yaml
PYTHONPATH: "${AUGUR_ROOT}/project-brain:${AUGUR_ROOT}:${AUGUR_ROOT}/src/mcp"
PYTHONUNBUFFERED: "1"
```

Implications:

- MCP servers are local process bridges started by AI clients.
- The topology file does not define an HTTP listener for MCP.
- Per-client args identify the caller (`claude`, `codex`, `gemini`).
- Vault-tier servers are separated for bundles that should not be resurrected by monolith scanning.

Review command:

```powershell
Get-Content config\system\mcp_servers.yaml
```

Expected: only reviewed server ids, commands, args, bundle paths, and environment variables are present.

## Dashboard Boundary

The dashboard is a local UI. It should not directly execute local scripts, read arbitrary filesystem paths, or call model providers from UI code. The contract is:

1. UI components call dashboard API routes.
2. Dashboard API routes call MCP through the local MCP bridge.
3. MCP tools perform atomic operations.
4. Agents own orchestration and judgment.

Enterprise reviewers should search for direct local execution in dashboard code:

```powershell
rg -n "child_process|spawn\\(|exec\\(|fs\\.|subprocess|openai|anthropic|gemini" apps\dashboard
```

Expected: dashboard-local execution patterns are absent or limited to build/test scripts, not runtime UI routes.

## Daemon Boundary

The daemon is persistent automation. Its service label comes from `project.yaml` through `service_healer.py`; the current default project name yields `com.augur.daemon`.

Windows inspection:

```powershell
$env:AUGUR_DIR = (Get-Location).Path
schtasks /query /tn "com.augur.daemon" /fo LIST /v
& "$env:AUGUR_DIR\.venv\Scripts\python.exe" project-brain\capabilities\skills\daemon\scripts\service_healer.py status
```

macOS inspection:

```bash
launchctl print "gui/$(id -u)/com.augur.daemon"
cat "$HOME/Library/LaunchAgents/com.augur.daemon.plist"
```

Expected: the service points at the intended checkout and the status file is fresh. A stale PID, old path, or mismatched arguments is a deployment finding.

## AI Provider Boundary

Augur user-facing AI interactions are normally mediated by the user's AI client. Internal infrastructure can still call configured AI/OCR providers for retry diagnosis, document OCR escalation, vision work, and self-healing. Enterprise reviewers should treat provider calls as a separate network boundary, not as local-only execution.

Review targets:

- `config/system/llm.yaml`
- `src/lib/ai/client.py`
- `src/lib/llm_retry.py`
- document-extractor cloud escalation settings
- dashboard security settings for airplane/local model routing

Expected: provider endpoints, API-key environment variable names, and local fallback profiles are explicit.

## Skill Boundary

Skills are both documentation and executable automation. Shared skills live in the repo, while private skills can live in the vault. Current controls rely on source review, skill placement rules, and agent command discipline. There is no runtime enterprise allowlist yet.

Enterprise target posture:

- Shared skills are reviewed and pinned to a commit.
- Private skills are disabled unless explicitly allowlisted.
- Auto-discovered script execution is off by default.
- Skill tool calls produce auditable events.

ADR-735 proposes this mode.
