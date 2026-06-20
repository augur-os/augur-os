---
status: Implemented
date: '2026-05-12'
deciders:
- gsannikov
related:
- ADR-550
- ADR-732
hub: null
tags:
- system-config
- schema-validation
- drift-prevention
- mcp-handler
- pre-commit-hook
- cross-platform
- windows-safe
superseded_by: null
spec_file: 2026-05-12-system-config-integrity-design.md
plan_file: 2026-05-12-system-config-integrity.md
---

# ADR-733: System Config Integrity — Schemas, Validators, and an Atomic Merger to Stop Drift in config/system/{llm,settings}.yaml

## Decision summary

Introduce three-layer enforcement for `config/system/llm.yaml` and `config/system/settings.yaml`: schemas-as-code in `src/config/schemas/`, a read-time validator in `src/config/system_config.py`, a write-time merger in `src/mcp/augur_framework/tools/infrastructure/settings/dashboard.py` (rewritten...

## Status notes

Spec + plan written 2026-05-12 in the same `/superpowers:brainstorming` → `/superpowers:writing-plans` session. Spec passed a deliberate cross-check against `docs/architecture-overview.md`, `docs/what-is-augur.md`, `docs/agent-topics/ARCHITECTURE.md`, and the recent git history on `config/system/llm.yaml` (commits `f4a774a13` removing `active_profile`, `2cd469781` removing `external.preferred_cli` and centralizing CLI resolution). Three framing fixes were applied as a follow-up commit before invoking `/superpowers:writing-plans`: 1. Reframe `llm.yaml`'s purpose as **explicit internal-task LLM exception routing** (retry_diagnosis, document_ocr, cloud_vision, ai_self_healer per `src/lib/llm_retry.py:resolve_cli()`), NOT "Codex/Gemini routing" — the latter is the separate `cli_agents.yaml` concern (vault-owned, migrated out of `llm.yaml.external.preferred_cli`). 2. Add an explicit out-of-scope note covering `cli_agents.yaml` schema work. 3. Record the harness boundary: Augur's default path is native AI-client reasoning. Direct model/API use is not a product default; it is an explicit internal exception surface for named tasks only (retry, OCR, vision, self-healing), with credentials and approval tracked through the governing config/ADR. Defending the schema is defending the exception registry, not making Augur a general LLM wrapper. Load-bearing claims: - **`src/config/schemas/llm_schema.py` is the single source of truth** for the shape of `config/system/llm.yaml`. Every reader, the dashboard merger, and the pre-commit hook all import `validate_llm_config` from it. Future shape changes happen in the schema FIRST, then the file. Schema-as-code means there is no "spec drift from implementation" possible. - **Cross-agent enforcement.** The `.githooks/pre-commit` hook fires for any agent (Claude, Codex, Gemini, OpenCode, Copilot) and any hand-edit. Defense-in-depth: even on Windows-without-Bash where the commit-time hook can't run, the read-time validator catches broken state at every config load. - **Windows-safe atomicity.** All writes use `os.replace` (not `os.rename`) so the same code works on POSIX and Windows. ADR-550's path helpers (`get_project_root`, `get_cache_dir`) provide platform-aware locations. - **Rolling backup discipline.** Restore script writes to `get_cache_dir()/system-config-restore/<basename>.bak` — out of the repo, no `.gitignore` entry needed, bounded to one backup per source file. Recovery is `cp <cache>/<basename>.bak config/system/<basename>`. This is the second ADR landed via the corrected `/adr` post-write hook chain (ADR-731's session fixed the central-JSON upsert step; ADR-732 was the first; this is the second).
