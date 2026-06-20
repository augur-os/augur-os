---
title: system config integrity — schemas, validators, and an atomic merger to stop drift in config/system/{llm,settings}.yaml
date: 2026-05-12
status: Draft
authors:
  - gsannikov
related_adrs:
  - ADR-550   # Windows hardening support
  - ADR-732   # loop-hygiene MVP-v2 (parallel scope: catching destructive writes systemically)
related_memory:
  - feedback_vendor_neutral_design
  - feedback_cross_agent_enforcement
  - project_enforcement_layers
---

# System config integrity

## 1. Problem

`config/system/llm.yaml` has a documented multi-profile structure: `active_profile` (string) + `profiles` (mapping of profile name → provider/base_url/model/timeout_s/api_key_env/command/...) + `tasks` (per-internal-task profile routing). It is the canonical endpoint registry for the **internal Augur tasks that DO make LLM calls** — `retry_diagnosis` (CLI agent retry orchestration in `src/lib/llm_retry.py`), `document_ocr` (cloud OCR escalation in `document-extractor` skill), `cloud_vision`, the daemon's `ai_self_healer`, and similar. It supports airplane mode (forces `local` profile) and per-task profile overrides via the `tasks` mapping.

**Note: this is a SEPARATE concern from `cli_agents.yaml`** — that file (vault-owned per the migration in commit `2cd469781`) is an ordered list of CLI agent binaries to fall back to for shell-level CLI invocations. This spec is strictly about `config/system/llm.yaml` + `config/system/settings.yaml` schema integrity; `cli_agents.yaml` is out of scope.

**Vision reconciliation:** the project's high-level vision (architecture-overview.md, what-is-augur.md) now states the stricter harness boundary: Augur's default path is native AI-client reasoning, while direct model/API access is a rare named exception. `llm.yaml` is therefore an explicit exception registry for approved internal tasks (retry diagnosis, document OCR, cloud vision, self-healing), not a general model router and not a Codex/Gemini routing surface. Defending the schema is defending that exception boundary.

At the end of a long working session, the file in the working tree had been **destructively rewritten** to a flat two-key shape:

```yaml
model: claude-opus-4-20250514
provider: anthropic
```

This shape:
- Loses the `profiles` structure
- Breaks airplane mode (no `local` profile to fall back to)
- Breaks internal-task routing for `retry_diagnosis`, `document_ocr`, `cloud_vision`, `ai_self_healer`, and any other task resolved via `src/lib/llm_retry.py:resolve_cli()` (which reads `llm.yaml` profiles + tasks)
- Hardcodes a single AI vendor — directly contradicts the `feedback_vendor_neutral_design` memory rule and the project's "Vendor-neutral by architecture, not by promise" principle (architecture-overview.md §The Inversion)
- Is not read by any existing code path correctly (every reader expects `profiles[...]`)

`config/system/settings.yaml` was also modified: a `default_cli: claude` line was added on top of the existing `mode: production`. Benign in shape, but indicates the same writer process ran.

Root cause investigation traced the regression to `src/mcp/augur_framework/tools/infrastructure/settings/dashboard.py`, which exposes MCP handlers `_handle_llm_config` and `_handle_llm_config_write` that perform `_helpers._write_yaml(path, config)` — **full file replacement**, no merge, no schema validation. Whenever the dashboard's onboarding/settings UI submits a single-vendor form, the multi-vendor structure gets clobbered.

A second writer (`shared-vault/skills/platform-admin/scripts/lib/credential_store.py:update_llm_yaml`) is additive and well-behaved. The dashboard handler is the specific offender; the broader category is "writers that don't honor the file's documented shape."

Three concrete harms:

1. **AI vendor lock-in by accident.** The flat shape locks all internal-task routing to a single vendor (here Anthropic). Airplane mode, local-only operation, and per-task profile overrides for retry / OCR / vision / self-healing — all silently broken until the next `git diff` surfaces the drift.
2. **Drift goes undetected.** Working-tree-level state isn't caught until commit time or until a reader fails — and the dashboard caller doesn't tell the user it just clobbered fields.
3. **No mechanical defense.** Existing readers do `yaml.safe_load(...)` without validation, so they silently accept the broken shape and fall back to brittle defaults.

## 2. Goal

Make destructive writes to `config/system/llm.yaml` and `config/system/settings.yaml` **mechanically impossible**, not just discouraged:

- The file's canonical shape is declared in code (single source of truth)
- All reads validate against the schema; broken state raises loudly
- All writes through the dashboard handler are structured merges, refused if the merged result would violate the schema
- Commits regressing the shape are refused at the pre-commit gate
- A one-shot restoration script repairs the current drifted state, idempotently

Cross-agent enforcement (per `feedback_cross_agent_enforcement`): the pre-commit gate fires for any agent or hand-edit, not just Claude Code.

## 3. Decision summary

Three-layer enforcement matching Augur's documented `project_enforcement_layers` pattern, plus a one-shot restoration script for the current broken state:

| Layer | Surface | New/Modified | Purpose |
|---|---|---|---|
| 1. Schemas as code | `src/config/schemas/{llm,settings}_schema.py` | NEW | Single source of truth for shape |
| 2. Read-time validator | `src/config/system_config.py` | NEW | All readers go through `load_llm_config()` / `load_settings_config()`; raise on violations |
| 3. Write-time merger | `src/mcp/augur_framework/tools/infrastructure/settings/dashboard.py` | MODIFIED | Structured merge + validate + atomic write; refuse the flat single-vendor shape |
| 4. Commit-time guard | `.githooks/pre-commit` + `src/config/precommit_check.py` | MODIFIED + NEW | Validate staged blobs, refuse regressions |
| One-shot | `scripts/restore_system_config.py` | NEW | Idempotent restore from template + salvaged user values |

**Schema choices:**

- `llm.yaml` is **strict** — unknown top-level keys raise (catches the flat-shape regression at validation time). Required: `active_profile`, `profiles`. Optional: `tasks`. Each profile: required `provider`, `base_url`, `model`; optional `timeout_s`, `api_key_env`, `api_key`, `disable_thinking`; unknown profile fields preserved in an `extra` dict for forward compatibility.
- `settings.yaml` is **permissive** — unknown top-level keys warn but don't raise. Known: `mode` (must be `dev`|`production`), `default_cli` (str, optional). The file is intended to accumulate flags over time.

**Atomic-write discipline (Windows-safe):**

All writes use `os.replace(tmp, target)` (not `os.rename`). On POSIX, the two are equivalent atomic-replace. On Windows, `os.rename` raises `FileExistsError` when the target exists; `os.replace` uses the underlying `MoveFileExW` with `MOVEFILE_REPLACE_EXISTING`. Same atomic guarantee on both platforms.

**Restoration backup discipline:**

The restore script writes a single rolling backup per file to `get_cache_dir() / "system-config-restore" / <filename>.bak`. Out of the repo (no working-tree pollution, no `.gitignore` entry needed), out of git scope, bounded to one backup per file (no timestamp accumulation). Recovery: `cp <cache>/system-config-restore/llm.yaml.bak config/system/llm.yaml`.

**What is NOT committed in this ADR:**

- LLM-vendor selection logic (which provider to use for which task) — stays where it is, just routed through the validated reader.
- Onboarding-UI redesign — the dashboard UI continues to submit single-profile updates; only the handler that receives them is changed.
- Auto-recovery / self-healing on read failure — broken state raises, doesn't auto-repair (user explicitly invokes the restore script).
- Schema for any other file in `config/system/` — scope is exactly `llm.yaml` and `settings.yaml`. A future ADR can extend the pattern.

## 4. Components

### 4.1 Schemas (`src/config/schemas/`)

```
src/config/schemas/
├── __init__.py
├── llm_schema.py        # LlmConfig, LlmProfile, LlmSchemaError, validate_llm_config()
└── settings_schema.py   # SettingsConfig, SettingsSchemaError, validate_settings_config()
```

Frozen `@dataclass(frozen=True)` types (no Pydantic dependency — Augur's pattern from `lifecycle_config.py`). `validate_*` functions take raw dict, return typed dataclass, raise typed exception on violation. Required-key, unknown-key, and cross-reference checks (active_profile ∈ profiles, tasks[*] ∈ profiles) all in the validator.

### 4.2 Read-time validator (`src/config/system_config.py`)

```python
@lru_cache(maxsize=1)
def load_llm_config() -> LlmConfig: ...

@lru_cache(maxsize=1)
def load_settings_config() -> SettingsConfig: ...

def invalidate_caches() -> None: ...

def llm_config_raw() -> dict: ...        # for the merger
def settings_config_raw() -> dict: ...   # for the merger
```

Two read shapes per file: validated (typed dataclass) for production callers, raw (dict) for the merger's read-modify-write cycle.

Missing-file behaviors differ:
- `load_llm_config()` raises (file is required)
- `load_settings_config()` returns `SettingsConfig()` with defaults (file is optional)

Migration: 8–12 existing `yaml.safe_load(...)` callsites on these two files are switched to the validator API. A repo-lint test asserts no remaining raw loads outside `system_config.py` itself.

### 4.3 Write-time merger (modified `dashboard.py`)

Three handlers are rewritten:

- `_handle_llm_config(params)` — structured merger. Reads existing config (raw), applies incoming dict as a focused mutation (`profiles[<name>]` add/update, `active_profile` replace, `tasks` update), re-validates merged result, writes atomically via `os.replace`. Refuses the flat single-vendor shape at the schema level.
- `_handle_llm_config_write(params)` — accepts full YAML text, validates BEFORE writing, no merge. For "restore from template" flows only. Refuses anything failing the schema.
- `_handle_default_cli(params)` — preserves all other settings fields, validates merged result, writes atomically.

All three return `{success: false, error: <msg>, refusal_category: "schema_violation"}` on schema failures — never silently accept.

Atomic-write helper:
```python
def _atomic_write_yaml(path: Path, data: dict) -> None:
    # tempfile.mkstemp in same dir → write → flush → fsync → os.replace
```

### 4.4 Commit-time guard

`.githooks/pre-commit` extended with a check that runs `python -m src.config.precommit_check <staged-paths>` when `config/system/llm.yaml` or `settings.yaml` is in the staged change set.

`src/config/precommit_check.py` reads each staged file via `git show :<path>`, validates against the schema, exits 1 with a per-file diagnostic if any fail. Exit 0 if all pass or no relevant files staged.

Refusal message instructs the user to run the restore script, update the schema first if the schema needs to evolve, or `--no-verify` as a last-resort bypass (with a warning that bypass leaves regression in main).

### 4.5 One-shot restore (`scripts/restore_system_config.py`)

CLI script with three modes:

```
python scripts/restore_system_config.py              # interactive
python scripts/restore_system_config.py --apply      # non-interactive
python scripts/restore_system_config.py --dry-run    # show diff, write nothing
```

Algorithm:

1. Load `shared-vault/skills/ai/augur/config/llm.yaml.template` (the canonical multi-profile structure).
2. Read current `llm.yaml` and `settings.yaml` (raw, no validation — current files might be broken).
3. Build a restored llm.yaml by merging template structure with salvaged user values:
   - Start from template's `profiles` + `active_profile` + `tasks`
   - For each current profile whose name matches a template profile, copy over `api_key_env`, `base_url`, `model` (preserving user's specific credentials and choices)
   - Preserve current `active_profile` IFF it references a profile that exists in the merged result; otherwise fall back to template default
   - Preserve current `tasks` entries that reference profiles existing in the merged result; drop dangling ones
4. Build restored settings.yaml: defaults (`mode: production`) + salvage known keys (`mode`, `default_cli`) from current.
5. Validate both restored configs against the schema BEFORE writing. Abort on validation failure (template itself broken).
6. Backup current versions to `get_cache_dir() / "system-config-restore" / <filename>.bak` (rolling, one per file).
7. Atomic-write the restored files via `os.replace`.

Idempotent: running twice produces no further change.

## 5. Cross-platform behavior

| Concern | Approach |
|---|---|
| Atomic file replacement | `os.replace(tmp, target)` everywhere — atomic on POSIX and Windows |
| Path separators | `pathlib.Path` exclusively; no string-concat path building |
| Cache directory | `get_cache_dir()` from `src/config/paths.py` — ADR-550 covers Windows paths |
| Pre-commit hook | Bash script (`.githooks/pre-commit`); works on Windows via Git for Windows' bundled Git Bash. On systems without Bash, layer 4 (commit-time) is skipped but layer 2 (read-time validator) still catches broken state on every config load — defense in depth degrades gracefully |
| File locking (Windows AV) | `os.replace` uses `MoveFileExW` which handles transient locks better than `os.rename`; tests document AV as a potential flake source |
| Tempfile in same dir | `tempfile.mkstemp(dir=str(path.parent))` ensures tmp and target are on the same filesystem so `os.replace` is atomic |

## 6. Safety and error handling

| Path | Behavior on bad input |
|---|---|
| `load_llm_config()` | Raises `LlmSchemaError` with path-qualified message + hint to run restore script |
| `load_settings_config()` | Raises on hard violations; warns on unknown keys (forward-compat) |
| `_handle_llm_config(params)` | Returns `{success: false, error, refusal_category: "schema_violation"}`. File untouched. |
| `_handle_llm_config_write(params)` | Same — schema validated BEFORE any write. File untouched on failure. |
| `_handle_default_cli(params)` | Same — settings schema validated BEFORE write. |
| Atomic write — yaml.safe_dump raises mid-write | tmp file deleted in except block; original file untouched (still on disk under old name) |
| Atomic write — os.replace raises | tmp file cleaned up; original file untouched |
| Pre-commit hook — schema validator can't import | Hook exits 1 (fails closed). Better to refuse the commit than let a broken codebase deploy. |
| Restore script — template malformed | Abort before writing; original files untouched |
| Restore script — `Ctrl-C` during write | Atomic `os.replace` means the file is either old-or-new, never half-written |

**What we explicitly do NOT do:**

- No auto-repair on `load_*` failure. Raising is the right call — silent repair hides drift.
- No fallback "use defaults if file broken" path. Per CLAUDE.md rule 5 (no workaround fixes), broken state should be a loud failure not a silent fallback.
- No partial writes. Either the whole new file lands atomically or the original stays.
- No `--no-verify` workaround in the merger or restore. The pre-commit hook's `--no-verify` escape is the only documented bypass, and it's marked as last resort.

## 7. Testing strategy

Seven test surfaces under `tests/config/` plus a hook integration test:

1. **Schema tests** — full-config validation happy paths + every violation category (missing required, unknown keys, dangling references, empty profiles, invalid mode).
2. **Read-time validator tests** — happy path, missing file (per-file behavior), broken YAML, cache hit/miss, `invalidate_caches()`.
3. **Write-time merger tests** — flat-shape refusal (the regression case), additive profile add, in-place profile field update, active_profile-only update, task-routing add, merge-then-validate refusal, atomic-write rollback, settings preservation.
4. **Pre-commit hook tests** — staged valid → exit 0; staged invalid → exit 1; multi-file mixed; unstaged-broken-but-staged-good → exit 0.
5. **Restore script tests** — idempotence, salvage of user `api_key_env`, flat-shape replacement, preserved active_profile, dangling active_profile fallback, rolling backup (no timestamp accumulation), validation-before-write, dry-run.
6. **Migration tests** — repo-lint asserting no `yaml.safe_load(.../config/system/llm.yaml)` or `.../settings.yaml` outside `system_config.py`.
7. **Cross-platform tests** — `os.replace` over existing target works on POSIX and Windows; `get_cache_dir()` returns writable path on current platform; `pathlib.Path` throughout (static check).

**Quality gate before merge:**

- All new test files green under `/auto-test-pytest`
- `/auto-lint` clean
- `python scripts/restore_system_config.py --dry-run` against current broken state shows a diff that matches the canonical template + preserves existing `mode: production` and `default_cli: claude`
- One real `--apply` on a test branch: working-tree files match canonical structure, backups land in `get_cache_dir()`
- Pre-commit hook fires on a deliberately broken `llm.yaml` and refuses with diagnostic
- Read-time validator runs in MCP server boot: `python -c "from src.config.system_config import load_llm_config; load_llm_config()"` → no error after restore

## 8. Migration of existing readers

After the validator API ships, the following callsites (identified via grep) are switched from raw `yaml.safe_load(...llm.yaml...)` / `yaml.safe_load(...settings.yaml...)` to `load_llm_config()` / `load_settings_config()`:

- `src/lib/ai/config.py`
- `src/lib/llm_retry.py`
- `src/lib/agent_cli_config.py`
- `src/mcp/augur_shared/config.py`
- `src/mcp/augur_framework/tools/infrastructure/settings/__init__.py`
- `shared-vault/skills/document-extractor/scripts/mcp/tools_extract.py`
- `shared-vault/skills/daemon/scripts/ai_self_healer.py`
- `shared-vault/skills/daemon/scripts/daemon_mode.py`
- `shared-vault/skills/knowledge/scripts/mcp/__init__.py`
- Any others surfaced during the migration task

Each migration is its own small commit. The repo-lint test (surface 6) ensures no `yaml.safe_load` on the two files remains outside `system_config.py`.

## 9. Out of scope / explicit non-goals

- LLM-vendor selection policy — which provider is used for which task is a separate concern; this ADR only enforces the SHAPE of the config file.
- Onboarding UI redesign — the dashboard form continues to submit profile updates; only the receiving handler changes.
- Auto-recovery on read failure — broken state raises; user invokes restore explicitly.
- Schemas for other `config/system/*.yaml` files (e.g., `mcp_servers.yaml`, `vault.yaml`) — same pattern can be extended, but each is its own ADR.
- **`cli_agents.yaml` schema** — that file is vault-owned (not in `config/system/`) and was migrated out of `llm.yaml.external.preferred_cli` per commit `2cd469781`. A separate concern with its own canonical structure (ordered CLI binary list); deserves its own ADR if/when its shape drifts.
- Approval policy for each direct model/API exception — that's a governing ADR/config question, not a schema question. This ADR validates the shape of `llm.yaml`; it does not authorize new exception use.
- Pre-commit hook fallback for Windows-without-Bash — broader platform-tooling concern (ADR-550 lineage), not addressed here.
- Notifications / dashboard surfacing of schema-violation refusals — the dashboard handler returns structured errors; how the UI displays them is unchanged by this ADR.

## 10. Open questions

None at spec-write time. Implementation-detail questions surfacing during plan-writing are answered in plan PRs or follow-up ADRs.

## 11. References

- `CLAUDE.md` rules 4, 5, 11, 14, 19
- `config/system/llm.yaml` — currently regressed to flat shape (drives this work)
- `config/system/settings.yaml` — currently has `default_cli: claude` accumulated via dashboard
- `shared-vault/skills/ai/augur/config/llm.yaml.template` — canonical multi-profile reference
- `src/mcp/augur_framework/tools/infrastructure/settings/dashboard.py` — current offender (destructive `_write_yaml`)
- `shared-vault/skills/platform-admin/scripts/lib/credential_store.py` — well-behaved additive writer (precedent for the merge pattern)
- ADR-550 (Windows Hardening Support) — cross-platform path helpers
- ADR-732 (loop-hygiene MVP-v2) — parallel scope: catching destructive file operations systemically
- Memory: `feedback_vendor_neutral_design`, `feedback_cross_agent_enforcement`, `project_enforcement_layers`
