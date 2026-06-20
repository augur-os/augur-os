---
status: Implemented
date: 2026-03-18
deciders:
  - Gur Sannikov
related:
  - ADR-163
  - ADR-436
hub: system
tags:
  - browse
  - cli
  - integrations
  - frontmatter
  - discovery
superseded_by: null
---

# ADR-441: CLI Integration Discovery in Browse [RECONSTRUCTED]

## Context

Skills that depend on external CLI tools (e.g., `gws` for Google Workspace, `openhue` for home automation, `sonos` for audio) had no standardized way to declare their CLI dependencies. Users had to discover install instructions buried in SKILL.md prose. The Browse page's integrations category could not show CLI install/version/config status because there was no machine-readable CLI metadata in skill frontmatter.

## Decision

Add `x-augur-cli-integrations` as a structured frontmatter field in SKILL.md that declares external CLI dependencies with install commands, version checks, config requirements, and homepages. The Browse page's `list-integrations` MCP tool discovers these declarations and enriches them with live status checks.

### Frontmatter Schema

```yaml
x-augur-cli-integrations:
  - name: gws
    install: "npm install -g @googleworkspace/cli"
    version_cmd: "gws --version"
    requires_config: true
    config_check: "gws auth status"
    homepage: "https://github.com/googleworkspace/cli"
```

### CLI Registry

A `_build_cli_registry()` function in `browse.py` scans all SKILL.md files across client skill directories, extracts `x-augur-cli-integrations` entries, and builds a cached registry (300s TTL). This registry maps CLI names to their definitions and source skills.

### Status Checking

`_check_cli_status()` performs three checks per CLI tool:
1. **Installed**: `shutil.which()` to find the binary
2. **Version**: Run `version_cmd`, extract semver from output (falls back to first line)
3. **Configured**: If `requires_config` is true, run `config_check` and check exit code (0 = configured, non-zero = not configured, timeout = null)

Results are cached with 60s TTL, invalidated after `cli-install`.

### Overall Status Derivation

Per-skill status follows priority: **missing** (any CLI not installed) > **needs_config** (all installed but config check fails) > **ready** (all installed and configured).

### MCP Tools

Three new MCP tools complement the existing `list-integrations`:
- `cli-install` -- install a CLI by name (only accepts names from frontmatter registry, never runs caller-controlled commands)
- `cli-status` -- check status of a CLI tool, bypassing cache
- `cli-help` -- run `--help` for CLI tools and return formatted markdown

### Security

`cli-install` validates the CLI name against the frontmatter registry before executing any install command. It rejects unknown names and built-in system utilities (e.g., `osascript`). This prevents arbitrary command execution.

## Consequences

### Positive

- CLI dependencies are machine-readable and discoverable from SKILL.md frontmatter
- Browse page shows live install/version/config status for all CLI integrations
- One-click install from the dashboard via `cli-install` MCP tool
- Decentralized: each skill declares its own CLI dependencies, no central registry

### Negative

- Shell-based version and config checks can be slow for many CLIs (mitigated by 60s cache)
- `cli-install` runs shell commands (controlled by frontmatter, not user input, but still a surface)

### Neutral

- Skills without `x-augur-cli-integrations` are excluded from the integrations listing
- Built-in utilities (osascript, brew) are listed but cannot be "installed" via `cli-install`
- Cache invalidation happens automatically after successful install

## Alternatives Considered

### Alternative 1: Central CLI Registry File

Maintain a `config/cli-integrations.yaml` file listing all CLI dependencies.

**Rejected because**: Violates ADR-163 (plugin decentralization). CLI dependencies belong in the skill that uses them, not in a central config file.

### Alternative 2: Runtime CLI Detection Without Frontmatter

Scan PATH for known CLI binaries without requiring frontmatter declarations.

**Rejected because**: Cannot distinguish between "CLI X happens to be installed" and "CLI X is required by skill Y". Frontmatter provides the install instructions and config check commands that runtime detection cannot.

## References

- Tests: `tests/packages/augur-mcp/infrastructure/test_browse_cli_integrations.py`
- Implementation: `src/mcp/augur_mcp/infrastructure/browse.py`
- Example skill: `.claude/skills/google-workspace/SKILL.md` (has `x-augur-cli-integrations` for `gws`)
- ADR-163: Plugin Decentralization

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - "list-integrations MCP tool now discovers x-augur-cli-integrations from SKILL.md"
    - "New MCP tools: cli-install, cli-status, cli-help"
  patterns_deprecated: []
  files_affected:
    - "src/mcp/augur_mcp/infrastructure/browse.py"
    - ".claude/skills/google-workspace/SKILL.md"
    - "tests/packages/augur-mcp/infrastructure/test_browse_cli_integrations.py"
```
