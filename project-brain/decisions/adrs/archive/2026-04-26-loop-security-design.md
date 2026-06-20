---
description: Design for auto-security-audit — offline-first security scanner for all skills
author: Augur
spec_version: "1.0"
---

# auto-security-audit Design

## Overview

A unified CLI-only autoloop that scans **all skills** (core tier-0, private tier-0, and external tier≥1) for security vulnerabilities using a 5-stage offline pipeline. No remote API calls. Integrates with Tank CLI if locally available, but fully functional without it.

## Goals

1. Detect prompt injection patterns, hardcoded secrets, dangerous code patterns, and policy violations in skill files
2. Produce a unified security score and quarantine state per skill
3. Auto-fix at higher difficulties: quarantine, block MCP registration, and remove blocked external skills
4. Zero remote dependencies — all scans run locally

## Non-Goals

- Dashboard UI (out of scope — CLI only)
- Remote OSV queries without local cache
- Sigstore/SPDX verification (offline-only evolution gap at d4)
- Modifying skill source code (we report/quarantine, not rewrite skills)

## Architecture

### Skill: `loop-security`

Location: `skills/loop-security/` following the `loop-*` autoloop convention.

Single command: `auto-security-audit` registered as a `scan-fix` protocol command in `SKILL.md` frontmatter.

### 5-Stage Offline Pipeline

| Stage | Name | What It Checks | Implementation |
|-------|------|---------------|----------------|
| S1 | Prompt Injection | Hidden instructions, role hijacking, jailbreak patterns, data exfiltration in SKILL.md and instruction files | Native Python regex (200+ patterns derived from ClawGuard/Tank open-source heuristics) |
| S2 | Secret Scanning | Hardcoded API keys, tokens, passwords, private keys, connection strings | `detect-secrets` (local, offline) + custom regex for skill-specific patterns |
| S3 | Static Code Analysis | Dangerous Python patterns: `eval`, `exec`, `subprocess` without validation, path traversal, SQL injection | `bandit` (local) with native AST fallback if missing |
| S4 | Integrity & Trust | SHA tree hash of skill contents, frontmatter completeness (`x-augur-*` fields), manifest validation | Native Python `hashlib`, `yaml` frontmatter validator |
| S5 | Permissions & Policy | Overly broad declared permissions, missing `x-augur-license`, undocumented MCP tools, policy violations | Native Python policy checker against `docs/references/skill-policy.md` |

**Tank CLI Integration:**
The `loop-security` skill declares Tank in its `SKILL.md` frontmatter via `x-augur-cli-integrations`:

```yaml
x-augur-cli-integrations:
  - name: tank
    install: "npm install -g @tankpkg/cli"
    version_cmd: "tank --version"
    homepage: https://tankpkg.dev
```

The scanner uses `src.mcp.augur_mcp.infrastructure.cli._check_cli_status()` to detect if Tank is installed. If present, it runs `tank scan --offline --json <skill-dir>` and merges findings. If absent, the native 5-stage pipeline runs standalone.

This reuses the existing CLI integration infrastructure — no custom install logic needed.

### Scan Target: All Skills

Use `src/plugins.skill_discovery.discover_all_skills()` to enumerate:

- **Core (tier=0, augur-managed):** 22 skills in `skills/`
- **Private (tier=0, user vault):** 2 skills in vault `skills/`
- **External (tier≥1):** 55 skills from `.agents/`, `.claude/`, `.codex/`, plugin cache

Scan every `SKILL.md`, `*.py` script, `*.sh` script, and `*.md` instruction file within each skill directory.

### Output: Per-Skill Security Report

```yaml
skill_name: "geo-audit"
tier: 2
source: "external-client"
canonical: false
scan_timestamp: "2026-04-26T12:00:00Z"
overall_score: 6.5  # 0-10, 10 = clean
findings:
  - stage: "S1"
    severity: "high"
    file: "SKILL.md"
    line: 45
    message: "Role hijacking pattern detected: 'you are now a helpful assistant'"
    pattern_id: "PI-017"
  - stage: "S2"
    severity: "critical"
    file: "scripts/ops.py"
    line: 12
    message: "Hardcoded AWS access key: AKIA..."
    pattern_id: "SEC-AWS-001"
state: "quarantined"  # approved | quarantined | blocked
```

### Global State: `security-state.yaml`

Stored at `skills/loop-security/augur/data/security-state.yaml` (tracked in repo):

```yaml
version: "1.0"
last_scan: "2026-04-26T12:00:00Z"
skills:
  geo-audit:
    state: "quarantined"
    score: 6.5
    last_findings_hash: "abc123"
  loop-repo:
    state: "approved"
    score: 9.8
```

## Difficulty Escalation

| Difficulty | Action | Policy |
|-----------|--------|--------|
| d0 | Report only | List all findings with severity. No file mutations. |
| d1 | Quarantine | Write `security-state.yaml`. Flag critical/high skills as `quarantined`. These skills remain usable but MCP tool registration emits warnings. |
| d2 | Block | Flag `blocked` skills. Prevent MCP tool registration from blocked skills. Move blocked external skill scripts to `_quarantine/` within the skill dir. |
| d3 | Auto-remove | Physically remove blocked **external** skills (tier≥1) from plugin cache. Core skills (tier=0) are **never** auto-removed — only flagged for manual review. |
| d4 | Evolution gap | Suggest adding: offline Sigstore verification (cosign), SPDX license normalization, GitHub branch protection checks (when network is available in future). |

## CLI Usage

```bash
# Scan all skills at d0 (report only)
python3 skills/loop-security/scripts/security_audit.py --difficulty 0

# Scan at d1 with quarantine writes
python3 skills/loop-security/scripts/security_audit.py --difficulty 1

# Scan at d2 with blocking
python3 skills/loop-security/scripts/security_audit.py --difficulty 2

# Dry run
python3 skills/loop-security/scripts/security_audit.py --difficulty 2 --dry-run
```

Or via Augur MCP:
```
/auto-security-audit --difficulty 2
```

## Fix Actions

At d1+:
1. **Quarantine:** Update `security-state.yaml`, append quarantine notice to skill `SKILL.md` (comment-only, no content mutation)
2. **Block:** Add `.augur-blocked` marker file in skill root, disable MCP tool registration via `skill_discovery.invalidate_discovery_cache()`
3. **Auto-remove (d3, external only):** `shutil.rmtree(external_skill_dir)` after confirmation prompt or `--force`

## Security States

| State | Meaning | User Impact |
|-------|---------|-------------|
| `approved` | Clean or low-severity only | No impact |
| `quarantined` | Critical/high findings | Skills usable, warnings logged |
| `blocked` | Severe findings or policy violations | MCP tools disabled, scripts moved to `_quarantine/` |

## Integration with Existing Infrastructure

- Uses `src.lib.ops_protocol.OpsContext` and `ScanResult`/`FixResult`
- Uses `src.plugins.skill_discovery` for skill enumeration
- Uses `src.lib.frontmatter_utils` for SKILL.md parsing
- Hooks into `skills/ai/scripts/ops/rag_reindex.py` skill registry cache invalidation when states change

## File Structure

```
skills/loop-security/
├── SKILL.md                          # Declares x-augur-cli-integrations for Tank
├── scripts/
│   └── security_audit.py             # Main scan-fix module
├── commands/
│   └── auto-security-audit.md        # Command docs
├── augur/
│   ├── data/
│   │   └── security-state.yaml       # Global quarantine state
│   └── tests/
│       └── test_security_audit.py
└── references/
    └── injection-patterns.json       # 200+ regex patterns (derived from ClawGuard)
```

## Testing Strategy

- Unit tests for each stage (S1-S5) with fixture skills containing known vulnerabilities
- Integration test: scan full `skills/` directory, assert no false positives on clean skills
- Mock Tank CLI presence/absence
- Test difficulty escalation: d0 no mutations, d1 state file written, d2 blocked marker created

## Future Work (Evolution Gap)

- Offline Sigstore verification (when `cosign` is locally installed)
- SPDX license normalization and validation
- GitHub branch protection / tag protection verification (requires network — optional remote mode)
- Tank CLI deep integration (merge Tank's AST analysis and behavioral checks)

## References

- Tank open-source security scanner: https://github.com/tankpkg/tank
- ClawGuard prompt injection patterns (open-source): https://github.com/joergmichno/clawguard
- OSV Python library (offline-capable): https://pypi.org/project/osv/
- `detect-secrets`: https://github.com/Yelp/detect-secrets
- `bandit`: https://github.com/PyCQA/bandit
