# System Config Integrity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the three-layer enforcement (schemas → read-time validator → write-time merger → commit-time guard) plus one-shot restore script per `docs/superpowers/specs/2026-05-12-system-config-integrity-design.md` so destructive writes to `config/system/llm.yaml` and `config/system/settings.yaml` become mechanically impossible. Catches the regression the dashboard handler currently produces (clobbering multi-profile structure to a flat `{model, provider}` shape) AT the dashboard handler, at every reader, at every commit, and via an explicit one-shot restore for the present broken state.

**Architecture:** Seven checkpoints, 18 tasks. C1 builds schemas (TDD). C2 builds the read-time validator + raw-read API. C3 rewrites the three dashboard handlers to merge + validate. C4 adds the commit-time guard. C5 ships the one-shot restore script. C6 migrates 5 existing `yaml.safe_load` callsites to the validator API. C7 runs quality gates + manual verification. Every write uses `os.replace` (not `os.rename`) for cross-platform atomicity. Rolling backup lives in `get_cache_dir()` (no repo pollution).

**Tech Stack:** Python 3.11+ (stdlib `os`, `pathlib`, `tempfile`, `subprocess`, `functools.lru_cache`, `dataclasses`; PyYAML for parsing). No new runtime dependencies. Existing FastMCP integration unchanged.

**Spec:** `docs/superpowers/specs/2026-05-12-system-config-integrity-design.md`

**Related ADRs:** ADR-550 (Windows Hardening Support), ADR-732 (loop-hygiene MVP-v2 — parallel scope, used as plan structure precedent).

---

## Boundary rules (apply to every task)

- **TDD discipline.** Every code-adding task: failing test FIRST, run to confirm fail, then minimal implementation, run to confirm pass, then commit.
- **Auto-loops only.** Tests run via `/auto-test-pytest` or `uv run pytest <path> -v`; never raw `pytest` per CLAUDE.md rule 29.
- **Path helpers.** Use `src.config.paths.get_project_root()`, `get_cache_dir()`, `get_config_dir()`. Never hardcode paths per CLAUDE.md rule 3.
- **Atomic writes use `os.replace`, not `os.rename`.** Critical for Windows compatibility — `os.rename` raises `FileExistsError` when the target exists; `os.replace` uses `MoveFileExW` with `MOVEFILE_REPLACE_EXISTING`.
- **Commits.** Pattern: `feat(system-config): <subject>`, `test(system-config): <subject>`, `chore(system-config): <subject>`, `refactor(system-config): <subject>`. Heredoc style with `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` trailer.
- **Plugin decentralization.** Schemas + validator + precommit + restore script all live in `src/config/` (system-wide infrastructure, parallel to `paths.py`). The dashboard handler stays in its existing location. Per CLAUDE.md rule 2 — system-wide config infrastructure is NOT skill-owned.
- **No LLM SDK imports.** This plan adds zero `anthropic`, `openai`, `google.generativeai` imports. Pure config-file plumbing.
- **Working on main per Augur convention** (matches ADR-731 and ADR-732 workflows).

---

## File structure (locked in before tasks)

```
src/config/
├── __init__.py                 # existing, untouched
├── paths.py                    # existing, untouched
├── schemas/                    # NEW — schema-as-code package
│   ├── __init__.py             # NEW, empty
│   ├── llm_schema.py           # NEW — LlmConfig, LlmProfile, LlmSchemaError, validate_llm_config()
│   └── settings_schema.py      # NEW — SettingsConfig, SettingsSchemaError, validate_settings_config()
├── system_config.py            # NEW — load_llm_config(), load_settings_config(), invalidate_caches(), raw readers
└── precommit_check.py          # NEW — pre-commit hook entry point

src/mcp/augur_framework/tools/infrastructure/settings/
└── dashboard.py                # MODIFIED — _handle_llm_config, _handle_llm_config_write, _handle_default_cli rewritten

.githooks/
└── pre-commit                  # MODIFIED — add system-config schema-validation block

scripts/
└── restore_system_config.py    # NEW — one-shot remediation

tests/config/
├── __init__.py                 # NEW, empty
├── test_llm_schema.py          # NEW
├── test_settings_schema.py     # NEW
├── test_system_config.py       # NEW
├── test_dashboard_merger.py    # NEW
├── test_precommit_check.py     # NEW
├── test_restore_script.py      # NEW
└── test_migration_lint.py      # NEW — repo-lint test

# Migration touchpoints (C6):
src/lib/agent_cli_config.py     # MODIFIED — yaml.safe_load → load_llm_config()
src/lib/llm_retry.py            # MODIFIED — yaml.safe_load → load_llm_config()
src/lib/ai/config.py            # MODIFIED — yaml.safe_load → load_llm_config()
shared-vault/skills/daemon/scripts/daemon_mode.py  # MODIFIED — yaml.safe_load → load_llm_config()
# Note: shared-vault/skills/platform-admin/scripts/lib/credential_store.py is a WRITER (additive
# update_llm_yaml), not a reader. Its read calls inside update_llm_yaml use llm_config_raw() for
# round-trip preservation; covered in C6.
```

---

## C1 — Schemas

### Task 1: `LlmSchemaError` + `LlmProfile` + `LlmConfig` dataclasses + `validate_llm_config()` with tests

**Files:**
- Create: `src/config/schemas/__init__.py` (empty)
- Create: `src/config/schemas/llm_schema.py`
- Create: `tests/config/__init__.py` (empty)
- Create: `tests/config/test_llm_schema.py`

- [ ] **Step 1: Create empty package markers**

```bash
touch src/config/schemas/__init__.py
touch tests/config/__init__.py
```

- [ ] **Step 2: Write the failing test**

Write `tests/config/test_llm_schema.py`:

```python
"""Tests for src/config/schemas/llm_schema.py — the canonical LLM config schema."""
from __future__ import annotations

import pytest

from src.config.schemas.llm_schema import (
    LlmConfig,
    LlmProfile,
    LlmSchemaError,
    REQUIRED_KEYS,
    OPTIONAL_KEYS,
    REQUIRED_PROFILE_FIELDS,
    validate_llm_config,
)


def _full_valid_config() -> dict:
    """A minimum valid llm.yaml shape used as the happy-path baseline."""
    return {
        "active_profile": "local",
        "profiles": {
            "local": {
                "provider": "openai_compatible",
                "base_url": "http://localhost:11434/v1",
                "model": "qwen3.5:latest",
            },
        },
        "tasks": {},
    }


def test_valid_full_config_returns_typed_dataclass():
    cfg = validate_llm_config(_full_valid_config())
    assert isinstance(cfg, LlmConfig)
    assert cfg.active_profile == "local"
    assert "local" in cfg.profiles
    assert isinstance(cfg.profiles["local"], LlmProfile)
    assert cfg.profiles["local"].provider == "openai_compatible"


def test_top_level_must_be_mapping():
    with pytest.raises(LlmSchemaError, match="top-level"):
        validate_llm_config("not-a-dict")


def test_missing_active_profile_raises():
    raw = _full_valid_config()
    del raw["active_profile"]
    with pytest.raises(LlmSchemaError, match="active_profile"):
        validate_llm_config(raw)


def test_missing_profiles_raises():
    raw = _full_valid_config()
    del raw["profiles"]
    with pytest.raises(LlmSchemaError, match="profiles"):
        validate_llm_config(raw)


def test_flat_single_vendor_shape_raises():
    """The regression case: a flat {model, provider} shape is the bug we're catching."""
    raw = {"model": "claude-opus-4-20250514", "provider": "anthropic"}
    with pytest.raises(LlmSchemaError, match="unknown top-level"):
        validate_llm_config(raw)


def test_unknown_top_level_key_raises():
    raw = _full_valid_config()
    raw["totally_made_up_key"] = "value"
    with pytest.raises(LlmSchemaError, match="unknown top-level"):
        validate_llm_config(raw)


def test_empty_profiles_dict_raises():
    raw = _full_valid_config()
    raw["profiles"] = {}
    with pytest.raises(LlmSchemaError, match="non-empty mapping"):
        validate_llm_config(raw)


def test_profile_missing_required_field_raises():
    raw = _full_valid_config()
    del raw["profiles"]["local"]["model"]
    with pytest.raises(LlmSchemaError, match="model"):
        validate_llm_config(raw)


def test_active_profile_must_reference_existing_profile():
    raw = _full_valid_config()
    raw["active_profile"] = "ghost"
    with pytest.raises(LlmSchemaError, match="active_profile.*ghost"):
        validate_llm_config(raw)


def test_task_routing_must_reference_existing_profile():
    raw = _full_valid_config()
    raw["tasks"] = {"document_ocr": "ghost"}
    with pytest.raises(LlmSchemaError, match="document_ocr"):
        validate_llm_config(raw)


def test_unknown_profile_field_preserved_in_extra():
    raw = _full_valid_config()
    raw["profiles"]["local"]["custom_provider_specific_field"] = "value"
    cfg = validate_llm_config(raw)
    assert cfg.profiles["local"].extra.get("custom_provider_specific_field") == "value"


def test_profile_field_types_validated():
    raw = _full_valid_config()
    raw["profiles"]["local"]["timeout_s"] = "not-an-int"
    cfg = validate_llm_config(raw)
    # timeout_s is coerced via int(); a non-coercible value raises
    # Our implementation: int(prof_raw.get("timeout_s", 60)) — "not-an-int" raises
    # Document expected behavior. Adjust if implementation chooses a different policy.
    # (This test will be made strict in the implementation.)
    assert cfg.profiles["local"].timeout_s is not None  # placeholder, see implementation


def test_constants_are_frozensets():
    assert isinstance(REQUIRED_KEYS, frozenset)
    assert isinstance(OPTIONAL_KEYS, frozenset)
    assert isinstance(REQUIRED_PROFILE_FIELDS, frozenset)
    assert "active_profile" in REQUIRED_KEYS
    assert "profiles" in REQUIRED_KEYS
    assert "tasks" in OPTIONAL_KEYS
    assert REQUIRED_PROFILE_FIELDS == frozenset({"provider", "base_url", "model"})


def test_full_template_shape_validates():
    """Mirrors the canonical template at shared-vault/skills/ai/augur/config/llm.yaml.template."""
    raw = {
        "active_profile": "local",
        "profiles": {
            "local": {
                "provider": "openai_compatible",
                "base_url": "http://localhost:11434/v1",
                "model": "qwen3.5:latest",
                "timeout_s": 120,
                "disable_thinking": True,
            },
            "remote": {
                "provider": "openai_compatible",
                "base_url": "https://glama.ai/api/gateway/openai/v1",
                "model": "anthropic/claude-sonnet-4",
                "timeout_s": 60,
                "api_key_env": "GLAMA_API_KEY",
            },
        },
        "tasks": {"document_ocr": "local"},
    }
    cfg = validate_llm_config(raw)
    assert cfg.active_profile == "local"
    assert len(cfg.profiles) == 2
    assert cfg.profiles["remote"].api_key_env == "GLAMA_API_KEY"
    assert cfg.tasks == {"document_ocr": "local"}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/config/test_llm_schema.py -v`
Expected: `ModuleNotFoundError: No module named 'src.config.schemas.llm_schema'`

- [ ] **Step 4: Write the minimal implementation**

Write `src/config/schemas/llm_schema.py`:

```python
"""Canonical schema for config/system/llm.yaml.

Source of truth for all readers, the write-time merger, and the
pre-commit guard. The shape matches shared-vault/skills/ai/augur/config/
llm.yaml.template (which is the user-facing canonical example).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class LlmSchemaError(ValueError):
    """Raised when llm.yaml violates the schema."""


@dataclass(frozen=True)
class LlmProfile:
    """One named LLM profile (e.g., 'local', 'remote', 'vision-local')."""
    name: str
    provider: str
    base_url: str
    model: str
    timeout_s: int = 60
    api_key_env: str | None = None
    api_key: str | None = None
    disable_thinking: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LlmConfig:
    """Top-level llm.yaml shape."""
    active_profile: str
    profiles: dict[str, LlmProfile]
    tasks: dict[str, str] = field(default_factory=dict)


REQUIRED_KEYS: frozenset[str] = frozenset({"active_profile", "profiles"})
OPTIONAL_KEYS: frozenset[str] = frozenset({"tasks"})
REQUIRED_PROFILE_FIELDS: frozenset[str] = frozenset({"provider", "base_url", "model"})

_KNOWN_PROFILE_FIELDS: frozenset[str] = frozenset({
    "provider", "base_url", "model", "timeout_s",
    "api_key_env", "api_key", "disable_thinking",
})


def validate_llm_config(raw: Any) -> LlmConfig:
    """Validate raw YAML data against the schema. Return LlmConfig or raise LlmSchemaError."""
    if not isinstance(raw, dict):
        raise LlmSchemaError("llm.yaml top-level must be a mapping")

    missing = REQUIRED_KEYS - raw.keys()
    if missing:
        raise LlmSchemaError(
            f"llm.yaml missing required key(s): {sorted(missing)}. "
            "Expected shape: active_profile + profiles{...} per llm.yaml.template"
        )

    unknown = raw.keys() - REQUIRED_KEYS - OPTIONAL_KEYS
    if unknown:
        raise LlmSchemaError(
            f"llm.yaml has unknown top-level key(s): {sorted(unknown)}. "
            f"Allowed: {sorted(REQUIRED_KEYS | OPTIONAL_KEYS)}"
        )

    profiles_raw = raw["profiles"]
    if not isinstance(profiles_raw, dict) or not profiles_raw:
        raise LlmSchemaError("llm.yaml 'profiles' must be a non-empty mapping")

    profiles: dict[str, LlmProfile] = {}
    for name, prof_raw in profiles_raw.items():
        if not isinstance(prof_raw, dict):
            raise LlmSchemaError(f"profile {name!r} must be a mapping")
        missing_fields = REQUIRED_PROFILE_FIELDS - prof_raw.keys()
        if missing_fields:
            raise LlmSchemaError(
                f"profile {name!r} missing required field(s): {sorted(missing_fields)}"
            )
        try:
            timeout_s = int(prof_raw.get("timeout_s", 60))
        except (TypeError, ValueError) as exc:
            raise LlmSchemaError(
                f"profile {name!r}: timeout_s must be an integer, got {prof_raw.get('timeout_s')!r}"
            ) from exc
        profiles[name] = LlmProfile(
            name=name,
            provider=prof_raw["provider"],
            base_url=prof_raw["base_url"],
            model=prof_raw["model"],
            timeout_s=timeout_s,
            api_key_env=prof_raw.get("api_key_env"),
            api_key=prof_raw.get("api_key"),
            disable_thinking=bool(prof_raw.get("disable_thinking", False)),
            extra={k: v for k, v in prof_raw.items() if k not in _KNOWN_PROFILE_FIELDS},
        )

    active = raw["active_profile"]
    if not isinstance(active, str) or active not in profiles:
        raise LlmSchemaError(
            f"active_profile={active!r} must reference one of the defined profiles: "
            f"{sorted(profiles.keys())}"
        )

    tasks_raw = raw.get("tasks", {})
    if not isinstance(tasks_raw, dict):
        raise LlmSchemaError("'tasks' must be a mapping of task_name → profile_name")
    for task_name, profile_name in tasks_raw.items():
        if not isinstance(profile_name, str) or profile_name not in profiles:
            raise LlmSchemaError(
                f"task {task_name!r}: profile {profile_name!r} not defined in profiles"
            )

    return LlmConfig(active_profile=active, profiles=profiles, tasks=dict(tasks_raw))
```

Then update `test_profile_field_types_validated` to assert the new strict behavior:

```python
def test_profile_field_types_validated():
    raw = _full_valid_config()
    raw["profiles"]["local"]["timeout_s"] = "not-an-int"
    with pytest.raises(LlmSchemaError, match="timeout_s"):
        validate_llm_config(raw)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/config/test_llm_schema.py -v`
Expected: PASS — all tests green.

- [ ] **Step 6: Commit**

```bash
git add src/config/schemas/__init__.py src/config/schemas/llm_schema.py tests/config/__init__.py tests/config/test_llm_schema.py
git commit -m "$(cat <<'EOF'
feat(system-config): llm.yaml schema with frozen dataclasses and validate_llm_config()

Schema-as-code module owning the canonical shape of config/system/llm.yaml:
- LlmConfig(active_profile, profiles, tasks)
- LlmProfile(name, provider, base_url, model, timeout_s, api_key_env,
  api_key, disable_thinking, extra) — frozen dataclasses, extra dict
  preserves unknown profile fields for forward compatibility
- validate_llm_config() enforces required keys, rejects unknown top-level
  keys (catches the flat {model, provider} regression at validation time),
  verifies active_profile and tasks cross-references to existing profiles
- frozensets for REQUIRED_KEYS, OPTIONAL_KEYS, REQUIRED_PROFILE_FIELDS

13 unit tests covering happy path, every refusal category, and the
template shape from shared-vault/skills/ai/augur/config/llm.yaml.template.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: `SettingsSchemaError` + `SettingsConfig` + `validate_settings_config()` with tests

**Files:**
- Create: `src/config/schemas/settings_schema.py`
- Create: `tests/config/test_settings_schema.py`

- [ ] **Step 1: Write the failing test**

Write `tests/config/test_settings_schema.py`:

```python
"""Tests for src/config/schemas/settings_schema.py — settings.yaml schema."""
from __future__ import annotations

import pytest

from src.config.schemas.settings_schema import (
    ALLOWED_MODES,
    KNOWN_KEYS,
    SettingsConfig,
    SettingsSchemaError,
    validate_settings_config,
)


def test_empty_dict_returns_defaults():
    cfg = validate_settings_config({})
    assert isinstance(cfg, SettingsConfig)
    assert cfg.mode == "production"
    assert cfg.default_cli is None


def test_mode_production_validates():
    cfg = validate_settings_config({"mode": "production"})
    assert cfg.mode == "production"


def test_mode_dev_validates():
    cfg = validate_settings_config({"mode": "dev"})
    assert cfg.mode == "dev"


def test_invalid_mode_raises():
    with pytest.raises(SettingsSchemaError, match="mode"):
        validate_settings_config({"mode": "staging"})


def test_non_string_mode_raises():
    with pytest.raises(SettingsSchemaError, match="mode"):
        validate_settings_config({"mode": 42})


def test_default_cli_string_validates():
    cfg = validate_settings_config({"default_cli": "claude"})
    assert cfg.default_cli == "claude"


def test_default_cli_non_string_raises():
    with pytest.raises(SettingsSchemaError, match="default_cli"):
        validate_settings_config({"default_cli": 42})


def test_default_cli_none_is_default():
    cfg = validate_settings_config({"mode": "production"})
    assert cfg.default_cli is None


def test_unknown_keys_do_not_raise():
    """settings.yaml is permissive — unknown keys preserved/ignored without error."""
    cfg = validate_settings_config({"mode": "production", "weird_future_flag": True})
    # The current schema returns dataclass with known fields only; unknown keys
    # are silently accepted at validation time. (The system_config reader will
    # surface a warning via stderr — separate concern.)
    assert cfg.mode == "production"


def test_top_level_must_be_mapping():
    with pytest.raises(SettingsSchemaError, match="top-level"):
        validate_settings_config("not-a-dict")


def test_constants_shape():
    assert ALLOWED_MODES == frozenset({"dev", "production"})
    assert KNOWN_KEYS == frozenset({"mode", "default_cli"})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/config/test_settings_schema.py -v`
Expected: `ModuleNotFoundError: No module named 'src.config.schemas.settings_schema'`

- [ ] **Step 3: Write the minimal implementation**

Write `src/config/schemas/settings_schema.py`:

```python
"""Canonical schema for config/system/settings.yaml.

settings.yaml is intentionally small — global runtime flags that don't
belong in any single skill's config. Schema is permissive (unknown keys
do not raise) because it's intended to accumulate flags over time. The
read-time validator surfaces unknown keys as warnings.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class SettingsSchemaError(ValueError):
    """Raised when settings.yaml violates the schema."""


@dataclass(frozen=True)
class SettingsConfig:
    mode: str = "production"
    default_cli: str | None = None


ALLOWED_MODES: frozenset[str] = frozenset({"dev", "production"})
KNOWN_KEYS: frozenset[str] = frozenset({"mode", "default_cli"})


def validate_settings_config(raw: Any) -> SettingsConfig:
    """Validate settings.yaml data. Return SettingsConfig or raise SettingsSchemaError."""
    if not isinstance(raw, dict):
        raise SettingsSchemaError("settings.yaml top-level must be a mapping")

    mode = raw.get("mode", "production")
    if not isinstance(mode, str) or mode not in ALLOWED_MODES:
        raise SettingsSchemaError(
            f"settings.yaml 'mode' must be one of {sorted(ALLOWED_MODES)}, got {mode!r}"
        )

    default_cli = raw.get("default_cli")
    if default_cli is not None and not isinstance(default_cli, str):
        raise SettingsSchemaError(
            f"'default_cli' must be a string, got {type(default_cli).__name__}"
        )

    return SettingsConfig(mode=mode, default_cli=default_cli)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/config/test_settings_schema.py -v`
Expected: PASS — 11 tests green.

- [ ] **Step 5: Commit**

```bash
git add src/config/schemas/settings_schema.py tests/config/test_settings_schema.py
git commit -m "$(cat <<'EOF'
feat(system-config): settings.yaml schema with permissive unknown-key policy

SettingsConfig(mode, default_cli) frozen dataclass. validate_settings_config()
enforces mode ∈ {dev, production} and default_cli is str|None. Unknown keys
do not raise (settings.yaml is intentionally permissive for forward compat);
warnings are surfaced at the read-time validator layer, not here.

11 unit tests cover defaults, all field types, validation failures, and
the permissive unknown-key behavior.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## C2 — Read-time validator

### Task 3: `system_config.py` — typed + raw readers, cache, invalidate API

**Files:**
- Create: `src/config/system_config.py`
- Create: `tests/config/test_system_config.py`

- [ ] **Step 1: Write the failing test**

Write `tests/config/test_system_config.py`:

```python
"""Tests for src/config/system_config.py — read-time validator API."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.config import system_config
from src.config.schemas.llm_schema import LlmConfig, LlmSchemaError
from src.config.schemas.settings_schema import SettingsConfig


def _valid_llm() -> dict:
    return {
        "active_profile": "local",
        "profiles": {
            "local": {
                "provider": "openai_compatible",
                "base_url": "http://localhost:11434/v1",
                "model": "x",
            }
        },
        "tasks": {},
    }


def _patch_paths(monkeypatch, llm_path: Path | None, settings_path: Path | None):
    if llm_path is not None:
        monkeypatch.setattr(system_config, "llm_config_path", lambda: llm_path)
    if settings_path is not None:
        monkeypatch.setattr(system_config, "settings_config_path", lambda: settings_path)
    system_config.invalidate_caches()


def test_load_llm_config_happy_path(tmp_path, monkeypatch):
    llm_path = tmp_path / "llm.yaml"
    llm_path.write_text(yaml.safe_dump(_valid_llm()))
    _patch_paths(monkeypatch, llm_path, None)

    cfg = system_config.load_llm_config()
    assert isinstance(cfg, LlmConfig)
    assert cfg.active_profile == "local"
    assert "local" in cfg.profiles


def test_load_llm_config_missing_file_raises(tmp_path, monkeypatch):
    _patch_paths(monkeypatch, tmp_path / "does-not-exist.yaml", None)
    with pytest.raises(LlmSchemaError, match="not found"):
        system_config.load_llm_config()


def test_load_llm_config_broken_yaml_raises(tmp_path, monkeypatch):
    llm_path = tmp_path / "llm.yaml"
    llm_path.write_text("not: : valid: yaml: ::")
    _patch_paths(monkeypatch, llm_path, None)
    with pytest.raises(LlmSchemaError, match="malformed"):
        system_config.load_llm_config()


def test_load_llm_config_flat_shape_raises(tmp_path, monkeypatch):
    """The regression: flat {model, provider} shape must be refused at read time."""
    llm_path = tmp_path / "llm.yaml"
    llm_path.write_text("model: claude-opus-4-20250514\nprovider: anthropic\n")
    _patch_paths(monkeypatch, llm_path, None)
    with pytest.raises(LlmSchemaError, match="unknown top-level"):
        system_config.load_llm_config()


def test_load_llm_config_caches_within_process(tmp_path, monkeypatch):
    llm_path = tmp_path / "llm.yaml"
    llm_path.write_text(yaml.safe_dump(_valid_llm()))
    _patch_paths(monkeypatch, llm_path, None)

    cfg1 = system_config.load_llm_config()
    # Mutate the file
    bad = _valid_llm()
    bad["active_profile"] = "ghost"
    llm_path.write_text(yaml.safe_dump(bad))
    # Without invalidation, cache returns prior value
    cfg2 = system_config.load_llm_config()
    assert cfg1 is cfg2  # same cached LlmConfig instance


def test_invalidate_caches_forces_reread(tmp_path, monkeypatch):
    llm_path = tmp_path / "llm.yaml"
    llm_path.write_text(yaml.safe_dump(_valid_llm()))
    _patch_paths(monkeypatch, llm_path, None)

    system_config.load_llm_config()
    # Mutate file and invalidate
    new = _valid_llm()
    new["profiles"]["remote"] = {
        "provider": "openai_compatible",
        "base_url": "https://api.example.com/v1",
        "model": "x",
    }
    llm_path.write_text(yaml.safe_dump(new))
    system_config.invalidate_caches()
    cfg = system_config.load_llm_config()
    assert "remote" in cfg.profiles


def test_load_settings_config_returns_defaults_when_absent(tmp_path, monkeypatch):
    _patch_paths(monkeypatch, None, tmp_path / "missing-settings.yaml")
    cfg = system_config.load_settings_config()
    assert isinstance(cfg, SettingsConfig)
    assert cfg.mode == "production"
    assert cfg.default_cli is None


def test_load_settings_config_reads_existing(tmp_path, monkeypatch):
    settings_path = tmp_path / "settings.yaml"
    settings_path.write_text("mode: production\ndefault_cli: claude\n")
    _patch_paths(monkeypatch, None, settings_path)

    cfg = system_config.load_settings_config()
    assert cfg.mode == "production"
    assert cfg.default_cli == "claude"


def test_load_settings_config_warns_on_unknown_keys(tmp_path, monkeypatch, capsys):
    settings_path = tmp_path / "settings.yaml"
    settings_path.write_text("mode: production\nweird_flag: true\n")
    _patch_paths(monkeypatch, None, settings_path)
    system_config.load_settings_config()
    captured = capsys.readouterr()
    assert "weird_flag" in captured.err


def test_llm_config_raw_skips_validation(tmp_path, monkeypatch):
    """The raw API returns whatever's on disk, never raises on schema violations."""
    llm_path = tmp_path / "llm.yaml"
    llm_path.write_text("model: x\nprovider: y\n")  # invalid shape
    _patch_paths(monkeypatch, llm_path, None)
    raw = system_config.llm_config_raw()
    assert raw == {"model": "x", "provider": "y"}


def test_llm_config_raw_returns_skeleton_when_missing(tmp_path, monkeypatch):
    _patch_paths(monkeypatch, tmp_path / "missing.yaml", None)
    raw = system_config.llm_config_raw()
    # Skeleton lets the merger always work, even on fresh installs
    assert "profiles" in raw
    assert "tasks" in raw


def test_settings_config_raw_returns_empty_when_missing(tmp_path, monkeypatch):
    _patch_paths(monkeypatch, None, tmp_path / "missing-settings.yaml")
    raw = system_config.settings_config_raw()
    assert raw == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/config/test_system_config.py -v`
Expected: `ModuleNotFoundError: No module named 'src.config.system_config'`

- [ ] **Step 3: Write the minimal implementation**

Write `src/config/system_config.py`:

```python
"""Canonical reader API for config/system/*.yaml.

All code that reads these files should go through this module. Direct
yaml.safe_load() calls on config/system/* are a code smell — they bypass
schema validation and let silently-broken configs propagate.
"""
from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from src.config.paths import get_project_root
from src.config.schemas.llm_schema import (
    LlmConfig,
    LlmSchemaError,
    validate_llm_config,
)
from src.config.schemas.settings_schema import (
    KNOWN_KEYS as SETTINGS_KNOWN_KEYS,
    SettingsConfig,
    SettingsSchemaError,
    validate_settings_config,
)


def llm_config_path() -> Path:
    return get_project_root() / "config" / "system" / "llm.yaml"


def settings_config_path() -> Path:
    return get_project_root() / "config" / "system" / "settings.yaml"


@lru_cache(maxsize=1)
def load_llm_config() -> LlmConfig:
    """Load and validate llm.yaml. Raise LlmSchemaError on any shape violation."""
    path = llm_config_path()
    if not path.is_file():
        raise LlmSchemaError(
            f"llm.yaml not found at {path}. "
            "Run scripts/restore_system_config.py to bootstrap from template."
        )
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise LlmSchemaError(f"llm.yaml at {path} is malformed YAML: {exc}") from exc
    return validate_llm_config(raw)


@lru_cache(maxsize=1)
def load_settings_config() -> SettingsConfig:
    """Load and validate settings.yaml. Raise on hard violations; warn on unknown keys."""
    path = settings_config_path()
    if not path.is_file():
        return SettingsConfig()
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise SettingsSchemaError(
            f"settings.yaml at {path} is malformed YAML: {exc}"
        ) from exc

    if isinstance(raw, dict):
        unknown = raw.keys() - SETTINGS_KNOWN_KEYS
        if unknown:
            print(
                f"warning: settings.yaml has unknown key(s) {sorted(unknown)} — "
                "preserved but not validated. Update src/config/schemas/settings_schema.py "
                "to add them to the known set.",
                file=sys.stderr,
            )
    return validate_settings_config(raw)


def invalidate_caches() -> None:
    """Reset read caches. Tests call this after mutating a file in tmp_path."""
    load_llm_config.cache_clear()
    load_settings_config.cache_clear()


def llm_config_raw() -> dict[str, Any]:
    """Read llm.yaml as a raw dict, NO validation. For the merger's read-modify-write cycle."""
    path = llm_config_path()
    if not path.is_file():
        return {"active_profile": None, "profiles": {}, "tasks": {}}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def settings_config_raw() -> dict[str, Any]:
    """Read settings.yaml as a raw dict, NO validation. For the merger's read-modify-write cycle."""
    path = settings_config_path()
    if not path.is_file():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/config/test_system_config.py -v`
Expected: PASS — 12 tests green.

- [ ] **Step 5: Commit**

```bash
git add src/config/system_config.py tests/config/test_system_config.py
git commit -m "$(cat <<'EOF'
feat(system-config): read-time validator with cache + raw API

system_config.load_llm_config() and load_settings_config() are the new
canonical reader entry points. Both:
- Resolve paths via get_project_root() (no hardcoded paths)
- Cache results with @lru_cache(maxsize=1)
- Raise typed errors (LlmSchemaError / SettingsSchemaError) on
  shape violations — never silently fall back

The raw companions llm_config_raw() and settings_config_raw() return
unvalidated dicts for the dashboard merger's read-modify-write cycle
(it needs to preserve unknown fields during merges, then validate the
merged result before writing).

invalidate_caches() clears caches; tests call it after mutating
fixture files. Settings reader warns on unknown keys via stderr;
llm.yaml is strict and raises on the same.

12 tests cover happy paths, missing files, malformed YAML, flat-shape
refusal, caching behavior, invalidation, raw vs validated APIs.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## C3 — Write-time merger (rewrite dashboard handlers)

### Task 4: Atomic write helper + `_merge_llm_payload` with tests

**Files:**
- Modify: `src/mcp/augur_framework/tools/infrastructure/settings/dashboard.py` (add helpers; rewrites in Task 5)
- Create: `tests/config/test_dashboard_merger.py`

- [ ] **Step 1: Inspect existing imports in dashboard.py**

Run: `head -22 src/mcp/augur_framework/tools/infrastructure/settings/dashboard.py`
Note the existing imports and `_helpers` reference. You'll add new imports alongside.

- [ ] **Step 2: Write the failing test**

Write `tests/config/test_dashboard_merger.py`:

```python
"""Tests for the dashboard MCP handlers' schema-validated merge + atomic write."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from src.config import system_config
from src.config.schemas.llm_schema import LlmSchemaError


@pytest.fixture(autouse=True)
def _isolate_paths(tmp_path, monkeypatch):
    llm = tmp_path / "config" / "system" / "llm.yaml"
    settings = tmp_path / "config" / "system" / "settings.yaml"
    llm.parent.mkdir(parents=True)
    monkeypatch.setattr(system_config, "llm_config_path", lambda: llm)
    monkeypatch.setattr(system_config, "settings_config_path", lambda: settings)
    system_config.invalidate_caches()
    yield
    system_config.invalidate_caches()


def _seed_valid_llm():
    path = system_config.llm_config_path()
    path.write_text(yaml.safe_dump({
        "active_profile": "local",
        "profiles": {
            "local": {
                "provider": "openai_compatible",
                "base_url": "http://localhost:11434/v1",
                "model": "qwen3.5",
            },
        },
        "tasks": {},
    }))


def test_merge_llm_payload_refuses_flat_shape():
    from src.mcp.augur_framework.tools.infrastructure.settings.dashboard import _merge_llm_payload
    existing = {"active_profile": "local", "profiles": {}, "tasks": {}}
    with pytest.raises(LlmSchemaError, match="unsupported top-level"):
        _merge_llm_payload(existing, {"model": "claude-opus", "provider": "anthropic"})


def test_merge_llm_payload_adds_new_profile_preserving_others():
    from src.mcp.augur_framework.tools.infrastructure.settings.dashboard import _merge_llm_payload
    existing = {
        "active_profile": "local",
        "profiles": {
            "local": {"provider": "x", "base_url": "y", "model": "z"},
            "remote": {"provider": "a", "base_url": "b", "model": "c", "api_key_env": "OLD"},
        },
        "tasks": {},
    }
    incoming = {
        "profiles": {
            "vision-local": {"provider": "openai_compatible", "base_url": "http://x/v1", "model": "llava"},
        },
    }
    merged = _merge_llm_payload(existing, incoming)
    assert set(merged["profiles"].keys()) == {"local", "remote", "vision-local"}
    # original profiles untouched
    assert merged["profiles"]["remote"]["api_key_env"] == "OLD"


def test_merge_llm_payload_updates_existing_profile_field():
    from src.mcp.augur_framework.tools.infrastructure.settings.dashboard import _merge_llm_payload
    existing = {
        "active_profile": "local",
        "profiles": {
            "remote": {"provider": "x", "base_url": "y", "model": "z", "api_key_env": "OLD"},
        },
        "tasks": {},
    }
    incoming = {"profiles": {"remote": {"api_key_env": "NEW"}}}
    merged = _merge_llm_payload(existing, incoming)
    assert merged["profiles"]["remote"]["api_key_env"] == "NEW"
    # other fields preserved
    assert merged["profiles"]["remote"]["model"] == "z"


def test_merge_llm_payload_active_profile_only():
    from src.mcp.augur_framework.tools.infrastructure.settings.dashboard import _merge_llm_payload
    existing = {
        "active_profile": "local",
        "profiles": {
            "local": {"provider": "x", "base_url": "y", "model": "z"},
            "remote": {"provider": "a", "base_url": "b", "model": "c"},
        },
        "tasks": {},
    }
    merged = _merge_llm_payload(existing, {"active_profile": "remote"})
    assert merged["active_profile"] == "remote"
    assert set(merged["profiles"].keys()) == {"local", "remote"}


def test_merge_llm_payload_tasks_added():
    from src.mcp.augur_framework.tools.infrastructure.settings.dashboard import _merge_llm_payload
    existing = {
        "active_profile": "local",
        "profiles": {"local": {"provider": "x", "base_url": "y", "model": "z"}},
        "tasks": {"existing_task": "local"},
    }
    merged = _merge_llm_payload(existing, {"tasks": {"new_task": "local"}})
    assert merged["tasks"] == {"existing_task": "local", "new_task": "local"}


def test_atomic_write_yaml_uses_os_replace(tmp_path):
    """os.replace must be used (not os.rename) for Windows compatibility when target exists."""
    from src.mcp.augur_framework.tools.infrastructure.settings.dashboard import _atomic_write_yaml
    target = tmp_path / "x.yaml"
    target.write_text("first: 1\n")
    _atomic_write_yaml(target, {"second": 2})
    assert target.read_text().strip() == "second: 2"
    # No leftover temp files
    siblings = list(tmp_path.iterdir())
    assert all(p.name == "x.yaml" for p in siblings), f"unexpected siblings: {siblings}"


def test_atomic_write_yaml_cleans_up_on_failure(tmp_path, monkeypatch):
    """If yaml.safe_dump raises, the temp file must be cleaned up and the target untouched."""
    from src.mcp.augur_framework.tools.infrastructure.settings.dashboard import _atomic_write_yaml
    target = tmp_path / "x.yaml"
    target.write_text("first: 1\n")

    def boom(*args, **kwargs):
        raise RuntimeError("disk full")

    monkeypatch.setattr("yaml.safe_dump", boom)
    with pytest.raises(RuntimeError, match="disk full"):
        _atomic_write_yaml(target, {"second": 2})

    # Original target intact
    assert target.read_text() == "first: 1\n"
    # No leftover .tmp files
    leftovers = [p for p in tmp_path.iterdir() if p.name != "x.yaml"]
    assert leftovers == []
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/config/test_dashboard_merger.py::test_merge_llm_payload_refuses_flat_shape -v`
Expected: ImportError on `_merge_llm_payload` from `dashboard.py`.

- [ ] **Step 4: Add helpers to `dashboard.py` (do NOT rewrite handlers yet — that's Task 5)**

Open `src/mcp/augur_framework/tools/infrastructure/settings/dashboard.py`. After the existing imports at the top of the file, add:

```python
import os
import tempfile
from pathlib import Path

from src.config import system_config
from src.config.schemas.llm_schema import LlmSchemaError, validate_llm_config
from src.config.schemas.settings_schema import SettingsSchemaError, validate_settings_config
```

After the existing handler functions (search for the last `def _handle_*` and add below it, BEFORE the read handlers section), add:

```python
# =============================================================================
# System config write helpers (schema-validated, atomic, Windows-safe)
# =============================================================================

def _atomic_write_yaml(path: Path, data: dict[str, Any]) -> None:
    """Write yaml to `path` atomically: write to tmp + os.replace.

    Uses os.replace (not os.rename) for cross-platform atomicity — on Windows,
    os.rename raises FileExistsError when target exists; os.replace uses
    MoveFileExW with MOVEFILE_REPLACE_EXISTING.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _merge_llm_payload(existing: dict, incoming: dict) -> dict:
    """Merge an incoming LLM-config payload into the existing structure.

    Allowed top-level keys in `incoming`: active_profile, profiles, tasks.
    Anything else (including the flat {model, provider} regression shape)
    raises LlmSchemaError before any merge happens.
    """
    if not isinstance(incoming, dict):
        raise LlmSchemaError("incoming llm config payload must be a mapping")

    allowed = {"active_profile", "profiles", "tasks"}
    unknown = incoming.keys() - allowed
    if unknown:
        raise LlmSchemaError(
            f"incoming llm config has unsupported top-level key(s): {sorted(unknown)}. "
            "If you're trying to set a single model, wrap it in profiles[<name>] instead."
        )

    merged = dict(existing) if isinstance(existing, dict) else {}
    merged.setdefault("profiles", {})
    merged.setdefault("tasks", {})

    if "profiles" in incoming:
        if not isinstance(incoming["profiles"], dict):
            raise LlmSchemaError("incoming 'profiles' must be a mapping")
        for name, fields in incoming["profiles"].items():
            if not isinstance(fields, dict):
                raise LlmSchemaError(f"profile {name!r} must be a mapping")
            existing_profile = merged["profiles"].get(name, {})
            merged["profiles"][name] = {**existing_profile, **fields}

    if "tasks" in incoming:
        if not isinstance(incoming["tasks"], dict):
            raise LlmSchemaError("incoming 'tasks' must be a mapping")
        merged["tasks"] = {**merged["tasks"], **incoming["tasks"]}

    if "active_profile" in incoming:
        merged["active_profile"] = incoming["active_profile"]

    return merged
```

(If `yaml` isn't already imported in dashboard.py, add `import yaml` near the top.)

- [ ] **Step 5: Run test to verify helpers pass**

Run: `uv run pytest tests/config/test_dashboard_merger.py -v -k "merge_llm_payload or atomic_write"`
Expected: All 7 tests green (5 merge + 2 atomic write).

- [ ] **Step 6: Commit**

```bash
git add src/mcp/augur_framework/tools/infrastructure/settings/dashboard.py tests/config/test_dashboard_merger.py
git commit -m "$(cat <<'EOF'
feat(system-config): atomic write helper + structured llm merge helper in dashboard

_atomic_write_yaml uses tempfile.mkstemp + flush + fsync + os.replace
(NOT os.rename) so writes are atomic on POSIX AND Windows. Cleans up
the tmp file in the except block; original file untouched on any failure.

_merge_llm_payload rejects the flat {model, provider} regression shape
(unsupported top-level keys raise LlmSchemaError). On valid payloads it
performs a structured merge: profiles map adds/updates, tasks map
extends, active_profile replaces. Unknown profile fields preserved in
the per-profile dict.

7 tests cover all three merge cases plus atomic-write happy path and
mid-write failure rollback.

The dashboard handlers themselves are still using the old destructive
path — that's Task 5. This task ships only the helpers + tests.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Rewrite the three dashboard handlers

**Files:**
- Modify: `src/mcp/augur_framework/tools/infrastructure/settings/dashboard.py:136-172` (handlers)
- Modify: `tests/config/test_dashboard_merger.py` (add handler-level tests)

- [ ] **Step 1: Add handler-level tests**

Append to `tests/config/test_dashboard_merger.py`:

```python
def test_handle_llm_config_refuses_flat_shape_with_refusal_category():
    _seed_valid_llm()
    from src.mcp.augur_framework.tools.infrastructure.settings.dashboard import _handle_llm_config
    result = _handle_llm_config({"config": {"model": "claude-opus", "provider": "anthropic"}})
    assert result["success"] is False
    assert result["refusal_category"] == "schema_violation"
    # File untouched
    on_disk = yaml.safe_load(system_config.llm_config_path().read_text())
    assert on_disk["active_profile"] == "local"
    assert "model" not in on_disk  # no leakage


def test_handle_llm_config_adds_new_profile():
    _seed_valid_llm()
    from src.mcp.augur_framework.tools.infrastructure.settings.dashboard import _handle_llm_config
    result = _handle_llm_config({"config": {
        "profiles": {
            "remote": {
                "provider": "openai_compatible",
                "base_url": "https://api.example.com/v1",
                "model": "gpt-x",
                "api_key_env": "OPENAI_API_KEY",
            }
        }
    }})
    assert result["success"] is True
    on_disk = yaml.safe_load(system_config.llm_config_path().read_text())
    assert set(on_disk["profiles"].keys()) == {"local", "remote"}
    assert on_disk["profiles"]["local"]["model"] == "qwen3.5"


def test_handle_llm_config_refuses_when_merged_result_invalid():
    """Incoming valid-shape but produces invalid merged result (dangling active_profile)."""
    _seed_valid_llm()
    from src.mcp.augur_framework.tools.infrastructure.settings.dashboard import _handle_llm_config
    result = _handle_llm_config({"config": {"active_profile": "ghost"}})
    assert result["success"] is False
    assert result["refusal_category"] == "schema_violation"
    # File untouched
    on_disk = yaml.safe_load(system_config.llm_config_path().read_text())
    assert on_disk["active_profile"] == "local"


def test_handle_llm_config_write_validates_full_payload():
    _seed_valid_llm()
    from src.mcp.augur_framework.tools.infrastructure.settings.dashboard import _handle_llm_config_write
    bad_yaml = "model: x\nprovider: y\n"
    result = _handle_llm_config_write({"yaml": bad_yaml})
    assert result["success"] is False
    assert result["refusal_category"] == "schema_violation"
    on_disk = yaml.safe_load(system_config.llm_config_path().read_text())
    assert on_disk["active_profile"] == "local"  # untouched


def test_handle_llm_config_write_replaces_with_valid_payload():
    _seed_valid_llm()
    from src.mcp.augur_framework.tools.infrastructure.settings.dashboard import _handle_llm_config_write
    new_yaml = yaml.safe_dump({
        "active_profile": "fresh",
        "profiles": {"fresh": {"provider": "x", "base_url": "y", "model": "z"}},
        "tasks": {},
    })
    result = _handle_llm_config_write({"yaml": new_yaml})
    assert result["success"] is True
    on_disk = yaml.safe_load(system_config.llm_config_path().read_text())
    assert on_disk["active_profile"] == "fresh"
    assert "fresh" in on_disk["profiles"]


def test_handle_default_cli_preserves_mode():
    settings_path = system_config.settings_config_path()
    settings_path.write_text("mode: production\n")
    system_config.invalidate_caches()

    from src.mcp.augur_framework.tools.infrastructure.settings.dashboard import _handle_default_cli
    result = _handle_default_cli({"default_cli": "claude"})
    assert result["success"] is True
    on_disk = yaml.safe_load(settings_path.read_text())
    assert on_disk["mode"] == "production"
    assert on_disk["default_cli"] == "claude"


def test_handle_default_cli_creates_file_if_missing():
    settings_path = system_config.settings_config_path()
    assert not settings_path.exists()
    from src.mcp.augur_framework.tools.infrastructure.settings.dashboard import _handle_default_cli
    result = _handle_default_cli({"default_cli": "claude"})
    assert result["success"] is True
    on_disk = yaml.safe_load(settings_path.read_text())
    assert on_disk["default_cli"] == "claude"
    # mode defaulted in schema
    assert on_disk.get("mode", "production") == "production"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/config/test_dashboard_merger.py::test_handle_llm_config_refuses_flat_shape_with_refusal_category -v`
Expected: FAIL — the existing `_handle_llm_config` still uses the destructive `_write_yaml(path, config)` path. Currently returns `{success: true}` for the flat shape.

- [ ] **Step 3: Rewrite the three handlers**

In `src/mcp/augur_framework/tools/infrastructure/settings/dashboard.py`, locate the existing `_handle_default_cli` (around line 136), `_handle_llm_config` (around line 148), `_handle_llm_config_write` (around line 158). Replace ALL THREE with:

```python
def _handle_default_cli(params: dict[str, Any]) -> dict[str, Any]:
    default_cli = params.get("default_cli")
    if not isinstance(default_cli, str) or not default_cli:
        return {"success": False, "error": "Missing 'default_cli' parameter"}

    existing = system_config.settings_config_raw()
    merged = {**(existing if isinstance(existing, dict) else {}), "default_cli": default_cli}

    try:
        validate_settings_config(merged)
    except SettingsSchemaError as exc:
        return {
            "success": False,
            "error": str(exc),
            "refusal_category": "schema_violation",
        }

    _atomic_write_yaml(system_config.settings_config_path(), merged)
    system_config.invalidate_caches()
    return {"success": True, "default_cli": default_cli}


def _handle_llm_config(params: dict[str, Any]) -> dict[str, Any]:
    """MCP handler: merge incoming LLM config into llm.yaml.

    BREAKING CHANGE from prior behavior: rejects the flat {model, provider}
    shape. Callers must use the profiles[<name>] shape per the schema.
    """
    incoming = params.get("config")
    if not isinstance(incoming, dict):
        return {"success": False, "error": "Missing or invalid 'config' parameter"}

    try:
        existing = system_config.llm_config_raw()
        merged = _merge_llm_payload(existing, incoming)
        validate_llm_config(merged)
    except LlmSchemaError as exc:
        return {
            "success": False,
            "error": str(exc),
            "refusal_category": "schema_violation",
        }

    _atomic_write_yaml(system_config.llm_config_path(), merged)
    system_config.invalidate_caches()
    return {"success": True, "config_path": str(system_config.llm_config_path())}


def _handle_llm_config_write(params: dict[str, Any]) -> dict[str, Any]:
    """MCP handler: write raw YAML text to llm.yaml.

    Validates parsed result against the schema BEFORE writing. No merge here —
    caller is asserting the full file shape. Use only for restore-from-template
    flows; onboarding/dashboard wizards should use _handle_llm_config.
    """
    yaml_text = params.get("yaml", "")
    if not isinstance(yaml_text, str) or not yaml_text:
        return {"success": False, "error": "Missing 'yaml' parameter"}

    try:
        parsed = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        return {"success": False, "error": f"Invalid YAML: {exc}"}

    try:
        validate_llm_config(parsed)
    except LlmSchemaError as exc:
        return {
            "success": False,
            "error": str(exc),
            "refusal_category": "schema_violation",
        }

    _atomic_write_yaml(system_config.llm_config_path(), parsed)
    system_config.invalidate_caches()
    return {"success": True, "config_path": str(system_config.llm_config_path())}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/config/test_dashboard_merger.py -v`
Expected: PASS — all 14 tests green (7 helper + 7 handler).

- [ ] **Step 5: Commit**

```bash
git add src/mcp/augur_framework/tools/infrastructure/settings/dashboard.py tests/config/test_dashboard_merger.py
git commit -m "$(cat <<'EOF'
feat(system-config): rewrite dashboard MCP handlers to merge + validate

_handle_llm_config: read raw, structured-merge via _merge_llm_payload,
re-validate via validate_llm_config, atomic write via _atomic_write_yaml.
Refuses the flat {model, provider} shape with refusal_category:schema_violation.

_handle_llm_config_write: validate parsed YAML BEFORE writing; refuses
schema violations.

_handle_default_cli: read raw settings, merge default_cli field, validate,
atomic write. Preserves mode and any future settings fields.

All three return {success: bool, error?, refusal_category?} — never silently
accept. invalidate_caches() called after every successful write so subsequent
load_llm_config()/load_settings_config() reads see the new state.

BREAKING CHANGE: the dashboard handlers no longer accept the flat
{model, provider} payload. Onboarding UIs that currently submit that
shape will now see refusal_category: schema_violation; they must be
updated to submit profiles[<name>].

7 new handler-level tests added. All 14 tests in test_dashboard_merger.py pass.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## C4 — Commit-time guard

### Task 6: `precommit_check.py` entry point with tests

**Files:**
- Create: `src/config/precommit_check.py`
- Create: `tests/config/test_precommit_check.py`

- [ ] **Step 1: Write the failing test**

Write `tests/config/test_precommit_check.py`:

```python
"""Tests for src/config/precommit_check.py — pre-commit hook entry point."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True)


def _stage(repo: Path, rel_path: str, content: str) -> None:
    target = repo / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    subprocess.run(["git", "add", rel_path], cwd=repo, check=True)


def _run_check(repo: Path, *staged_paths: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["python", "-m", "src.config.precommit_check", *staged_paths],
        cwd=repo,
        capture_output=True,
        text=True,
        # Inherit env so PYTHONPATH points at the augur src
        env={"PYTHONPATH": str(Path(__file__).resolve().parents[2])},
    )


def _valid_llm() -> str:
    return yaml.safe_dump({
        "active_profile": "local",
        "profiles": {"local": {"provider": "x", "base_url": "y", "model": "z"}},
        "tasks": {},
    })


def test_staged_valid_llm_exits_0(tmp_path):
    _init_git_repo(tmp_path)
    _stage(tmp_path, "config/system/llm.yaml", _valid_llm())
    result = _run_check(tmp_path, "config/system/llm.yaml")
    assert result.returncode == 0, f"stderr: {result.stderr}"


def test_staged_flat_single_vendor_exits_1(tmp_path):
    _init_git_repo(tmp_path)
    _stage(tmp_path, "config/system/llm.yaml", "model: x\nprovider: y\n")
    result = _run_check(tmp_path, "config/system/llm.yaml")
    assert result.returncode == 1
    assert "unknown top-level" in result.stderr or "unknown" in result.stderr.lower()


def test_staged_settings_valid_exits_0(tmp_path):
    _init_git_repo(tmp_path)
    _stage(tmp_path, "config/system/settings.yaml", "mode: production\ndefault_cli: claude\n")
    result = _run_check(tmp_path, "config/system/settings.yaml")
    assert result.returncode == 0, f"stderr: {result.stderr}"


def test_staged_settings_unknown_keys_does_not_fail(tmp_path):
    _init_git_repo(tmp_path)
    _stage(tmp_path, "config/system/settings.yaml", "mode: production\nfuture_flag: x\n")
    result = _run_check(tmp_path, "config/system/settings.yaml")
    # Permissive schema: unknown keys at the schema layer don't fail commit
    assert result.returncode == 0, f"stderr: {result.stderr}"


def test_multiple_files_one_bad(tmp_path):
    _init_git_repo(tmp_path)
    _stage(tmp_path, "config/system/llm.yaml", _valid_llm())
    _stage(tmp_path, "config/system/settings.yaml", "mode: staging\n")  # invalid mode
    result = _run_check(tmp_path, "config/system/llm.yaml", "config/system/settings.yaml")
    assert result.returncode == 1
    assert "settings.yaml" in result.stderr


def test_no_files_exits_0(tmp_path):
    _init_git_repo(tmp_path)
    result = _run_check(tmp_path)
    assert result.returncode == 0


def test_staged_malformed_yaml_exits_1(tmp_path):
    _init_git_repo(tmp_path)
    _stage(tmp_path, "config/system/llm.yaml", "not: : valid: ::")
    result = _run_check(tmp_path, "config/system/llm.yaml")
    assert result.returncode == 1
    assert "malformed" in result.stderr.lower() or "yaml" in result.stderr.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/config/test_precommit_check.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Write the minimal implementation**

Write `src/config/precommit_check.py`:

```python
"""Pre-commit hook entry point for system-config schema validation.

Reads the STAGED version of each given file path via `git show :<path>`
and validates against the schema. Exits 0 on success, 1 on any violation.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

from src.config.schemas.llm_schema import LlmSchemaError, validate_llm_config
from src.config.schemas.settings_schema import (
    SettingsSchemaError,
    validate_settings_config,
)


def _read_staged(path: str) -> str | None:
    """Return staged content for `path`. None if not staged or unreadable."""
    result = subprocess.run(
        ["git", "show", f":{path}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def _validate_file(path: str) -> list[str]:
    """Validate a single staged config file. Return list of error messages."""
    content = _read_staged(path)
    if content is None:
        return [f"{path}: could not read staged content"]
    try:
        parsed = yaml.safe_load(content) or {}
    except yaml.YAMLError as exc:
        return [f"{path}: malformed YAML — {exc}"]

    errors: list[str] = []
    name = Path(path).name
    if name == "llm.yaml":
        try:
            validate_llm_config(parsed)
        except LlmSchemaError as exc:
            errors.append(f"{path}: {exc}")
    elif name == "settings.yaml":
        try:
            validate_settings_config(parsed)
        except SettingsSchemaError as exc:
            errors.append(f"{path}: {exc}")
    else:
        errors.append(f"{path}: precommit_check called on unsupported file")
    return errors


def main(argv: list[str]) -> int:
    if not argv:
        return 0
    all_errors: list[str] = []
    for path in argv:
        all_errors.extend(_validate_file(path))
    if all_errors:
        for err in all_errors:
            print(err, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/config/test_precommit_check.py -v`
Expected: PASS — 7 tests green.

- [ ] **Step 5: Commit**

```bash
git add src/config/precommit_check.py tests/config/test_precommit_check.py
git commit -m "$(cat <<'EOF'
feat(system-config): pre-commit check entry point with subprocess-based git-show reads

src/config/precommit_check.py reads STAGED versions of config files via
git show :<path>, validates each against the matching schema, exits 1
with per-file diagnostic on any failure. Exit 0 if all pass or no
relevant paths given.

llm.yaml: strict — flat {model, provider} shape and other regressions
refused. settings.yaml: permissive — unknown keys do NOT fail commit
(matches the read-time validator's policy).

7 subprocess-based tests with tmp_path-initialized git repos verify
staged-valid passes, staged-invalid fails, mixed multi-file, no-files,
malformed YAML, and the settings permissive-key behavior.

The .githooks/pre-commit script wiring lands in the next task.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: Wire the check into `.githooks/pre-commit`

**Files:**
- Modify: `.githooks/pre-commit`

- [ ] **Step 1: Inspect the existing hook**

Run: `cat .githooks/pre-commit | head -50`
Note the existing structure — there are likely sections for `require-browser-verify`, `BINARY_ALLOWED`, etc. The new section gets appended near the end of the script, before the final `exit 0`.

- [ ] **Step 2: Add the system-config validation block**

Open `.githooks/pre-commit`. Append (or insert at a logical position near other staged-file checks):

```bash

# -----------------------------------------------------------------------
# System config schema validation (system-config-integrity spec)
# -----------------------------------------------------------------------
SYSTEM_CONFIG_FILES=$(git diff --cached --name-only --diff-filter=ACM \
    | grep -E '^config/system/(llm|settings)\.yaml$' || true)

if [ -n "$SYSTEM_CONFIG_FILES" ]; then
    if ! python -m src.config.precommit_check $SYSTEM_CONFIG_FILES; then
        echo "" >&2
        echo "❌ Pre-commit refused: system config schema violation." >&2
        echo "" >&2
        echo "config/system/llm.yaml or settings.yaml regressed below the schema." >&2
        echo "See: src/config/schemas/llm_schema.py and settings_schema.py" >&2
        echo "" >&2
        echo "Fix:" >&2
        echo "  1. If the working-tree shape is wrong, run:" >&2
        echo "       python scripts/restore_system_config.py" >&2
        echo "  2. If the schema itself needs to evolve, update the schema in code FIRST," >&2
        echo "     then update the file." >&2
        echo "  3. To bypass (NOT RECOMMENDED, leaves regression on main):" >&2
        echo "       git commit --no-verify" >&2
        exit 1
    fi
fi
```

- [ ] **Step 3: Verify the hook fires correctly**

Run a smoke test against a real bad-shape file. From the project root:

```bash
# Simulate staging a broken file
mkdir -p /tmp/_pcheck_test/config/system
cd /tmp/_pcheck_test
git init -q
git config user.email t@example.com && git config user.name t
echo "model: x
provider: y" > config/system/llm.yaml
git add config/system/llm.yaml
PYTHONPATH=~/Projects/Augur python -m src.config.precommit_check config/system/llm.yaml
echo "Exit: $?"
cd - > /dev/null
rm -rf /tmp/_pcheck_test
```

Expected: stderr contains "unknown top-level" diagnostic, exit code `1`.

- [ ] **Step 4: Verify the hook does NOT fire when no system-config files are staged**

```bash
# In the project repo, make an irrelevant edit
cd ~/Projects/Augur
echo "# noop" >> tests/config/test_llm_schema.py
git add tests/config/test_llm_schema.py
git status --short
# The pre-commit hook should not even invoke precommit_check.py
# (only fires when config/system/(llm|settings).yaml is in the staged set)
```

Then either run the hook directly or just inspect with:

```bash
SYSTEM_CONFIG_FILES=$(git diff --cached --name-only --diff-filter=ACM \
    | grep -E '^config/system/(llm|settings)\.yaml$' || true)
echo "would check: [$SYSTEM_CONFIG_FILES]"
```

Expected: empty list, no check would run. Unstage the test mutation:

```bash
git restore --staged tests/config/test_llm_schema.py
git restore tests/config/test_llm_schema.py
```

- [ ] **Step 5: Commit**

```bash
git add .githooks/pre-commit
git commit -m "$(cat <<'EOF'
feat(system-config): wire commit-time schema validation into .githooks/pre-commit

When config/system/llm.yaml or settings.yaml appears in the staged
changeset (--diff-filter=ACM), the hook invokes python -m
src.config.precommit_check on the staged paths. Schema violations
refuse the commit with an actionable diagnostic pointing at the
restore script.

The check is a no-op for any commit that doesn't touch these two files.
Cross-agent enforcement (per feedback_cross_agent_enforcement memory):
fires for Claude, Codex, Gemini, OpenCode, Copilot, and hand-edits
alike — the gate is in the git hook, not in any agent's behavior.

Windows note: hook script is Bash, requires Git Bash on Windows (via
Git for Windows). On Windows-without-Bash, this layer is skipped but
the read-time validator in src/config/system_config.py still catches
broken state on every config load — graceful degradation.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## C5 — One-shot restore script

### Task 8: `scripts/restore_system_config.py` with tests

**Files:**
- Create: `scripts/restore_system_config.py`
- Create: `tests/config/test_restore_script.py`

- [ ] **Step 1: Write the failing test**

Write `tests/config/test_restore_script.py`:

```python
"""Tests for scripts/restore_system_config.py — one-shot remediation."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

from src.config import paths


_RESTORE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "restore_system_config.py"
_SPEC = importlib.util.spec_from_file_location("restore_system_config_under_test", _RESTORE_PATH)
assert _SPEC and _SPEC.loader
restore = importlib.util.module_from_spec(_SPEC)
sys.modules["restore_system_config_under_test"] = restore
_SPEC.loader.exec_module(restore)


def _canonical_template() -> dict:
    """Mirror the shape of shared-vault/skills/ai/augur/config/llm.yaml.template."""
    return {
        "active_profile": "local",
        "profiles": {
            "local": {
                "provider": "openai_compatible",
                "base_url": "http://localhost:11434/v1",
                "model": "qwen3.5:latest",
            },
            "remote": {
                "provider": "openai_compatible",
                "base_url": "https://glama.ai/api/gateway/openai/v1",
                "model": "anthropic/claude-sonnet-4",
                "api_key_env": "GLAMA_API_KEY",
            },
        },
        "tasks": {"document_ocr": "local"},
    }


def _patch_paths(monkeypatch, tmp_path):
    repo = tmp_path / "repo"
    cache = tmp_path / "cache"
    (repo / "config" / "system").mkdir(parents=True)
    (repo / "shared-vault" / "skills" / "ai" / "augur" / "config").mkdir(parents=True)
    template = (
        repo / "shared-vault" / "skills" / "ai" / "augur" / "config" / "llm.yaml.template"
    )
    template.write_text(yaml.safe_dump(_canonical_template()))
    monkeypatch.setattr(paths, "get_project_root", lambda: repo)
    monkeypatch.setattr(paths, "get_cache_dir", lambda: cache)
    return repo, cache


def test_restore_replaces_flat_shape(tmp_path, monkeypatch):
    repo, _cache = _patch_paths(monkeypatch, tmp_path)
    (repo / "config" / "system" / "llm.yaml").write_text(
        "model: claude-opus-4-20250514\nprovider: anthropic\n"
    )
    rc = restore.main(["--apply"])
    assert rc == 0
    restored = yaml.safe_load((repo / "config" / "system" / "llm.yaml").read_text())
    assert "profiles" in restored
    assert "local" in restored["profiles"]
    assert restored["active_profile"] == "local"


def test_restore_salvages_user_api_key_env(tmp_path, monkeypatch):
    repo, _cache = _patch_paths(monkeypatch, tmp_path)
    current = _canonical_template()
    current["profiles"]["remote"]["api_key_env"] = "MY_CUSTOM_KEY"
    (repo / "config" / "system" / "llm.yaml").write_text(yaml.safe_dump(current))
    rc = restore.main(["--apply"])
    assert rc == 0
    restored = yaml.safe_load((repo / "config" / "system" / "llm.yaml").read_text())
    assert restored["profiles"]["remote"]["api_key_env"] == "MY_CUSTOM_KEY"


def test_restore_preserves_valid_active_profile(tmp_path, monkeypatch):
    repo, _cache = _patch_paths(monkeypatch, tmp_path)
    current = _canonical_template()
    current["active_profile"] = "remote"
    (repo / "config" / "system" / "llm.yaml").write_text(yaml.safe_dump(current))
    rc = restore.main(["--apply"])
    assert rc == 0
    restored = yaml.safe_load((repo / "config" / "system" / "llm.yaml").read_text())
    assert restored["active_profile"] == "remote"


def test_restore_drops_dangling_active_profile(tmp_path, monkeypatch):
    repo, _cache = _patch_paths(monkeypatch, tmp_path)
    current = _canonical_template()
    current["active_profile"] = "ghost"  # doesn't exist
    (repo / "config" / "system" / "llm.yaml").write_text(yaml.safe_dump(current))
    rc = restore.main(["--apply"])
    assert rc == 0
    restored = yaml.safe_load((repo / "config" / "system" / "llm.yaml").read_text())
    # Falls back to template default
    assert restored["active_profile"] == "local"


def test_restore_idempotent(tmp_path, monkeypatch):
    repo, _cache = _patch_paths(monkeypatch, tmp_path)
    (repo / "config" / "system" / "llm.yaml").write_text(yaml.safe_dump(_canonical_template()))
    restore.main(["--apply"])
    after_first = (repo / "config" / "system" / "llm.yaml").read_text()
    restore.main(["--apply"])
    after_second = (repo / "config" / "system" / "llm.yaml").read_text()
    assert after_first == after_second


def test_restore_rolling_backup_in_cache_dir(tmp_path, monkeypatch):
    repo, cache = _patch_paths(monkeypatch, tmp_path)
    llm = repo / "config" / "system" / "llm.yaml"
    llm.write_text("model: x\nprovider: y\n")
    restore.main(["--apply"])
    backup_dir = cache / "system-config-restore"
    assert backup_dir.is_dir()
    backup = backup_dir / "llm.yaml.bak"
    assert backup.is_file()
    # Backup contains the OLD broken content
    assert "model: x" in backup.read_text()

    # Run again with a different broken state — backup should ROLL (overwrite)
    llm.write_text("totally: different\n")
    restore.main(["--apply"])
    # Still exactly one backup file per source
    backups = sorted(p.name for p in backup_dir.iterdir())
    assert backups == ["llm.yaml.bak", "settings.yaml.bak"] or backups == ["llm.yaml.bak"]
    assert "totally" in backup.read_text()  # rolled


def test_restore_settings_yaml_preserves_known_keys(tmp_path, monkeypatch):
    repo, _cache = _patch_paths(monkeypatch, tmp_path)
    (repo / "config" / "system" / "llm.yaml").write_text(yaml.safe_dump(_canonical_template()))
    (repo / "config" / "system" / "settings.yaml").write_text(
        "mode: production\ndefault_cli: claude\n"
    )
    rc = restore.main(["--apply"])
    assert rc == 0
    restored = yaml.safe_load((repo / "config" / "system" / "settings.yaml").read_text())
    assert restored["mode"] == "production"
    assert restored["default_cli"] == "claude"


def test_restore_dry_run_writes_nothing(tmp_path, monkeypatch):
    repo, _cache = _patch_paths(monkeypatch, tmp_path)
    llm = repo / "config" / "system" / "llm.yaml"
    llm.write_text("model: x\nprovider: y\n")
    before = llm.read_text()
    rc = restore.main(["--dry-run"])
    assert rc == 0
    after = llm.read_text()
    assert before == after


def test_restore_aborts_if_template_missing(tmp_path, monkeypatch):
    repo, _cache = _patch_paths(monkeypatch, tmp_path)
    # Remove the template
    (repo / "shared-vault" / "skills" / "ai" / "augur" / "config" / "llm.yaml.template").unlink()
    (repo / "config" / "system" / "llm.yaml").write_text("model: x\n")
    rc = restore.main(["--apply"])
    assert rc != 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/config/test_restore_script.py -v`
Expected: FAIL — restore_system_config.py doesn't exist.

- [ ] **Step 3: Write the implementation**

Write `scripts/restore_system_config.py`:

```python
"""One-shot restoration of config/system/{llm,settings}.yaml from canonical
template + user-set values.

Idempotent. Run interactively or with --apply / --dry-run.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

from src.config.paths import get_cache_dir, get_project_root
from src.config.schemas.llm_schema import (
    LlmSchemaError,
    validate_llm_config,
)
from src.config.schemas.settings_schema import (
    KNOWN_KEYS as SETTINGS_KNOWN_KEYS,
    SettingsSchemaError,
    validate_settings_config,
)


def _load_yaml_if_exists(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return None


def _template_path() -> Path:
    return (
        get_project_root()
        / "shared-vault" / "skills" / "ai" / "augur" / "config" / "llm.yaml.template"
    )


def _llm_path() -> Path:
    return get_project_root() / "config" / "system" / "llm.yaml"


def _settings_path() -> Path:
    return get_project_root() / "config" / "system" / "settings.yaml"


def _backup_to_cache(path: Path) -> Path | None:
    if not path.is_file():
        return None
    backup_dir = get_cache_dir() / "system-config-restore"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"{path.name}.bak"
    shutil.copy2(path, backup_path)
    return backup_path


def _atomic_write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _restore_llm_config(current: dict | None, template: dict) -> dict:
    restored: dict[str, Any] = {
        "active_profile": template.get("active_profile", "local"),
        "profiles": {k: dict(v) for k, v in template.get("profiles", {}).items()},
        "tasks": dict(template.get("tasks", {})),
    }
    if not isinstance(current, dict):
        return restored
    current_profiles = current.get("profiles", {})
    if isinstance(current_profiles, dict):
        for name, prof in current_profiles.items():
            if not isinstance(prof, dict):
                continue
            if name in restored["profiles"]:
                for fld in ("api_key_env", "base_url", "model"):
                    if fld in prof:
                        restored["profiles"][name][fld] = prof[fld]
    current_active = current.get("active_profile")
    if isinstance(current_active, str) and current_active in restored["profiles"]:
        restored["active_profile"] = current_active
    current_tasks = current.get("tasks", {})
    if isinstance(current_tasks, dict):
        for task, profile_name in current_tasks.items():
            if profile_name in restored["profiles"]:
                restored["tasks"][task] = profile_name
    return restored


def _restore_settings_config(current: dict | None) -> dict:
    restored: dict[str, Any] = {"mode": "production"}
    if isinstance(current, dict):
        for key in SETTINGS_KNOWN_KEYS:
            if key in current:
                restored[key] = current[key]
    return restored


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Restore config/system/{llm,settings}.yaml")
    parser.add_argument("--apply", action="store_true", help="Apply without confirmation")
    parser.add_argument("--dry-run", action="store_true", help="Show diff, write nothing")
    args = parser.parse_args(argv)

    template_path = _template_path()
    template = _load_yaml_if_exists(template_path)
    if template is None:
        print(f"ERROR: template not found or unreadable at {template_path}", file=sys.stderr)
        return 2

    llm_path = _llm_path()
    settings_path = _settings_path()

    current_llm = _load_yaml_if_exists(llm_path)
    current_settings = _load_yaml_if_exists(settings_path)

    restored_llm = _restore_llm_config(current_llm, template)
    restored_settings = _restore_settings_config(current_settings)

    try:
        validate_llm_config(restored_llm)
    except LlmSchemaError as exc:
        print(f"ERROR: restored llm.yaml does not satisfy schema: {exc}", file=sys.stderr)
        return 2
    try:
        validate_settings_config(restored_settings)
    except SettingsSchemaError as exc:
        print(f"ERROR: restored settings.yaml does not satisfy schema: {exc}", file=sys.stderr)
        return 2

    print("=== restored config/system/llm.yaml ===")
    print(yaml.safe_dump(restored_llm, sort_keys=False))
    print("=== restored config/system/settings.yaml ===")
    print(yaml.safe_dump(restored_settings, sort_keys=False))

    if args.dry_run:
        print("Dry-run mode; no files written.")
        return 0

    if not args.apply:
        try:
            resp = input("Apply these restorations? [y/N] ")
        except EOFError:
            resp = "n"
        if resp.strip().lower() not in ("y", "yes"):
            print("Aborted.")
            return 0

    llm_backup = _backup_to_cache(llm_path)
    settings_backup = _backup_to_cache(settings_path)

    _atomic_write_yaml(llm_path, restored_llm)
    _atomic_write_yaml(settings_path, restored_settings)

    print(f"\nrestored: {llm_path}")
    print(f"restored: {settings_path}")
    if llm_backup or settings_backup:
        backup_dir = get_cache_dir() / "system-config-restore"
        print(f"\nPrior state backed up to {backup_dir}/")
        print("To revert:")
        if llm_backup:
            print(f"  cp '{llm_backup}' '{llm_path}'")
        if settings_backup:
            print(f"  cp '{settings_backup}' '{settings_path}'")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/config/test_restore_script.py -v`
Expected: PASS — 9 tests green.

- [ ] **Step 5: Commit**

```bash
git add scripts/restore_system_config.py tests/config/test_restore_script.py
git commit -m "$(cat <<'EOF'
feat(system-config): one-shot restoration script

scripts/restore_system_config.py loads the canonical multi-profile
template at shared-vault/skills/ai/augur/config/llm.yaml.template,
salvages user-set values (api_key_env, base_url, model overrides,
valid active_profile, profile-referencing tasks), validates the
restored result against the schema, and atomically writes both
config/system/llm.yaml and config/system/settings.yaml.

Idempotent (running twice produces no diff). Atomic writes via
os.replace (Windows-safe). Backups: single rolling .bak per file
at get_cache_dir()/system-config-restore/ — out of the repo, no
.gitignore entry needed, bounded to one backup per source file.

Three modes:
- interactive (default) — show diff, confirm with prompt
- --apply — non-interactive, just apply
- --dry-run — show diff, write nothing

9 tests cover flat-shape replacement, api_key_env salvage,
active_profile preservation/fallback, idempotence, rolling backup,
settings preservation, dry-run, and template-missing abort.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## C6 — Migration of existing readers

### Task 9: Migration repo-lint test

**Files:**
- Create: `tests/config/test_migration_lint.py`

This test asserts no `yaml.safe_load(...)` reads of `config/system/llm.yaml` or `config/system/settings.yaml` outside the new `system_config.py` module. It's the safety net for the C6 migration — failing this test means a callsite was missed.

- [ ] **Step 1: Write the test (it will currently FAIL, surfacing the callsites to migrate)**

Write `tests/config/test_migration_lint.py`:

```python
"""Repo-lint: no raw yaml.safe_load of config/system/{llm,settings}.yaml
outside the canonical reader at src/config/system_config.py.

This is a static-analysis test. It runs against the source tree and
fails if any file other than system_config.py performs a direct
yaml.safe_load on the two protected config files.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from src.config.paths import get_project_root


# Files explicitly allowed to read the protected configs directly.
ALLOWED_FILES: frozenset[str] = frozenset({
    "src/config/system_config.py",
    "src/config/precommit_check.py",
    "scripts/restore_system_config.py",
    # Tests legitimately seed and inspect these files
})

# Pattern matches yaml.safe_load(...) calls where the argument
# references one of the protected config paths.
_PROTECTED_PATHS = ("config/system/llm.yaml", "config/system/settings.yaml")


def _walk_python(root: Path):
    for path in root.rglob("*.py"):
        # Skip tests, generated, caches, venvs
        rel = str(path.relative_to(root))
        if rel.startswith(("tests/", ".venv/", "node_modules/", ".pytest_cache/")):
            continue
        if "__pycache__" in path.parts:
            continue
        yield path


def test_no_raw_yaml_load_of_protected_configs():
    root = get_project_root()
    violations: list[str] = []
    for path in _walk_python(root):
        rel = str(path.relative_to(root))
        if rel in ALLOWED_FILES:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if "yaml.safe_load" not in text and "yaml.load(" not in text:
            continue
        for protected in _PROTECTED_PATHS:
            if protected in text:
                # Make sure the file actually opens that path AND parses it
                # (a docstring mentioning the path is not a violation)
                if re.search(
                    r"yaml\.(safe_load|load)\s*\(\s*[^)]*"
                    + re.escape(protected.replace("/", r"/"))
                    + r"[^)]*\)",
                    text,
                ):
                    violations.append(f"{rel}: reads {protected} directly")

    if violations:
        pytest.fail(
            "Direct yaml.safe_load of protected config files. "
            "Migrate to src.config.system_config.load_llm_config() / "
            "load_settings_config(). Offenders:\n  - "
            + "\n  - ".join(violations)
        )
```

- [ ] **Step 2: Run the test — it will fail and surface the callsites**

Run: `uv run pytest tests/config/test_migration_lint.py -v`
Expected: FAIL with a list of offending files. Capture the list — these are the migration targets for Tasks 10-13. The expected offenders (based on the spec's enumeration):

- `src/lib/agent_cli_config.py`
- `src/lib/llm_retry.py`
- `src/lib/ai/config.py`
- `shared-vault/skills/daemon/scripts/daemon_mode.py`
- `shared-vault/skills/platform-admin/scripts/lib/credential_store.py` (special case — see Task 13)

- [ ] **Step 3: Commit the test as a known-failing canary**

```bash
git add tests/config/test_migration_lint.py
git commit -m "$(cat <<'EOF'
test(system-config): repo-lint canary for migration completion

tests/config/test_migration_lint.py walks the source tree and fails if
any file outside the allowlist (system_config.py, precommit_check.py,
restore_system_config.py) calls yaml.safe_load on config/system/llm.yaml
or config/system/settings.yaml.

This test currently FAILS by design — it lists the migration targets
that the next four tasks (C6.10-C6.13) will eliminate. Once all
callsites route through load_llm_config() / load_settings_config(),
this test goes green and stays green.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 10: Migrate `src/lib/agent_cli_config.py`

**Files:**
- Modify: `src/lib/agent_cli_config.py`

- [ ] **Step 1: Inspect the existing reader**

Run: `grep -n "yaml.safe_load\|llm.yaml\|settings.yaml" src/lib/agent_cli_config.py`
Read the surrounding 10 lines of each match to understand the existing pattern.

- [ ] **Step 2: Replace raw load with `load_llm_config()`**

Find every block of the form (literal example, adapt to actual code):

```python
import yaml
# ...
with open(<llm_yaml_path>) as f:
    config = yaml.safe_load(f) or {}
profile_name = config.get("active_profile")
profile = config.get("profiles", {}).get(profile_name, {})
# ...
```

Replace with:

```python
from src.config.system_config import load_llm_config
# ...
cfg = load_llm_config()
profile = cfg.profiles[cfg.active_profile]
# ... access via profile.provider, profile.base_url, profile.model, profile.api_key_env, profile.timeout_s
```

If the original reader had error handling for missing fields, replace it with a try/except on `LlmSchemaError` and re-raise with appropriate context (or let it propagate — the schema error is more informative than a custom one).

- [ ] **Step 3: Run the migration-lint test**

Run: `uv run pytest tests/config/test_migration_lint.py -v`
Expected: still FAIL, but `src/lib/agent_cli_config.py` should NO LONGER appear in the offender list.

- [ ] **Step 4: Run any existing tests for this module**

Run: `uv run pytest tests/ -k agent_cli_config -v`
Expected: PASS (or unchanged from baseline if there are no specific tests).

- [ ] **Step 5: Commit**

```bash
git add src/lib/agent_cli_config.py
git commit -m "refactor(system-config): migrate agent_cli_config.py to load_llm_config()

Direct yaml.safe_load of config/system/llm.yaml replaced with the
canonical reader. Schema violations now surface as LlmSchemaError
with diagnostic message instead of silently-broken dict access.

Part of the C6 migration. The migration-lint canary in
tests/config/test_migration_lint.py is one offender lighter.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 11: Migrate `src/lib/llm_retry.py`

**Files:**
- Modify: `src/lib/llm_retry.py`

- [ ] **Step 1: Inspect**

Run: `grep -n "yaml.safe_load\|llm.yaml" src/lib/llm_retry.py`

This file's `resolve_cli()` function uses llm.yaml to look up `tasks[<task>]` → profile → `command`. Per the spec, this is one of the canonical USE CASES for the multi-profile + task-routing shape.

- [ ] **Step 2: Replace raw load with `load_llm_config()`**

Locate the resolve_cli function (around line 320 per the earlier git history inspection). The current pattern reads llm.yaml directly. Replace the relevant block with:

```python
from src.config.system_config import load_llm_config
from src.config.schemas.llm_schema import LlmSchemaError
# ...
def resolve_cli(cli_setting: str = "auto", *, search_path: str | None = None, task: str | None = None) -> str:
    # ... existing explicit cli_setting branch unchanged ...

    # Check llm.yaml profiles for task-routed command
    try:
        cfg = load_llm_config()
    except LlmSchemaError as exc:
        # No usable config; fall through to cli_agents.yaml
        cfg = None

    if cfg is not None and task is not None and task in cfg.tasks:
        profile = cfg.profiles[cfg.tasks[task]]
        cmd = profile.extra.get("command")
        if cmd:
            resolved = _which(cmd, search_path)
            if resolved:
                return resolved

    # Fall through to cli_agents.yaml (existing logic)
    # ...
```

The exact shape depends on the existing function structure; adapt while preserving the resolution priority documented in the source (`Explicit cli_setting → llm.yaml task profile command → cli_agents.yaml`).

- [ ] **Step 3: Run the migration-lint test**

Run: `uv run pytest tests/config/test_migration_lint.py -v`
Expected: `llm_retry.py` no longer in offender list.

- [ ] **Step 4: Run any existing tests for the module**

Run: `uv run pytest tests/ -k llm_retry -v`
Expected: existing tests pass (or report stable).

- [ ] **Step 5: Commit**

```bash
git add src/lib/llm_retry.py
git commit -m "refactor(system-config): migrate llm_retry.resolve_cli to load_llm_config()

resolve_cli now reads task-routed profile commands via the typed
LlmConfig instead of a raw yaml.safe_load. Resolution priority
preserved: explicit cli_setting → llm.yaml.tasks[<task>] →
cli_agents.yaml.

LlmSchemaError on broken config is caught and falls through to
cli_agents.yaml (graceful degradation — broken llm.yaml shouldn't
break CLI resolution when an alternative exists).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 12: Migrate `src/lib/ai/config.py`

**Files:**
- Modify: `src/lib/ai/config.py`

- [ ] **Step 1: Inspect**

Run: `grep -n "yaml.safe_load\|llm.yaml" src/lib/ai/config.py`

- [ ] **Step 2: Replace raw load with `load_llm_config()`**

Replace direct YAML loading with the typed reader. The exact shape of the existing code dictates the migration — typically a `get_llm_config()` or similar function that does `yaml.safe_load(open(...))` and returns a dict. After migration:

```python
from src.config.system_config import load_llm_config
# Returns LlmConfig dataclass — callers access cfg.profiles[<name>].field
```

If existing callers expect a dict, either (a) update them to access the typed shape, or (b) add an `asdict()` adapter to maintain backwards compat for this commit and convert callers in follow-up. Prefer (a) — see test results to confirm no regressions.

- [ ] **Step 3: Run the migration-lint test**

Run: `uv run pytest tests/config/test_migration_lint.py -v`
Expected: `src/lib/ai/config.py` no longer in offender list.

- [ ] **Step 4: Run any existing tests**

Run: `uv run pytest tests/ -k "ai/config or ai_config" -v`

- [ ] **Step 5: Commit**

```bash
git add src/lib/ai/config.py
git commit -m "refactor(system-config): migrate src/lib/ai/config.py to load_llm_config()

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 13: Migrate `shared-vault/skills/daemon/scripts/daemon_mode.py` and `credential_store.py`

**Files:**
- Modify: `shared-vault/skills/daemon/scripts/daemon_mode.py`
- Modify: `shared-vault/skills/platform-admin/scripts/lib/credential_store.py`

`credential_store.py` is special: its `update_llm_yaml` is the well-behaved additive WRITER. It uses `yaml.safe_load` for the read step of its read-modify-write. Migrate it to use `system_config.llm_config_raw()` (the unvalidated raw read) so it preserves all existing fields including unknowns during update.

- [ ] **Step 1: Migrate daemon_mode.py**

Run: `grep -n "yaml.safe_load\|llm.yaml" shared-vault/skills/daemon/scripts/daemon_mode.py`

Replace raw load with `from src.config.system_config import load_llm_config`. Adapt callers to use the typed dataclass.

- [ ] **Step 2: Migrate credential_store.py's update_llm_yaml**

In `shared-vault/skills/platform-admin/scripts/lib/credential_store.py`, find the `update_llm_yaml` method (which does `self.load_llm_config()` — a different method internal to the class, NOT to be confused with `system_config.load_llm_config`).

Replace the internal `load_llm_config` method's body — wherever it does `yaml.safe_load(<llm.yaml path>)` — with:

```python
from src.config.system_config import llm_config_raw
# inside the load_llm_config method (rename to avoid confusion: load_llm_config_raw)
def _load_llm_config_raw(self) -> dict:
    return llm_config_raw()
```

If `credential_store` already has an instance-level `load_llm_config` returning a dict, rename it to `_load_llm_config_raw` to avoid shadowing the canonical reader name, and update its single caller (`update_llm_yaml`).

- [ ] **Step 3: Run the migration-lint test**

Run: `uv run pytest tests/config/test_migration_lint.py -v`
Expected: **PASS** — empty offender list. The canary goes green.

- [ ] **Step 4: Run existing tests for both files**

Run: `uv run pytest tests/ -k "daemon_mode or credential_store" -v`

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/daemon/scripts/daemon_mode.py shared-vault/skills/platform-admin/scripts/lib/credential_store.py
git commit -m "$(cat <<'EOF'
refactor(system-config): final migration — daemon_mode + credential_store

daemon_mode.py: yaml.safe_load → load_llm_config() with typed access.

credential_store.py: the additive writer's read step now goes through
system_config.llm_config_raw() (raw, no validation — required because
update_llm_yaml needs round-trip preservation of fields). Renamed the
class's internal load_llm_config method to _load_llm_config_raw to
avoid shadowing the canonical system_config.load_llm_config name.

The migration-lint canary in tests/config/test_migration_lint.py now
PASSES — no remaining raw yaml.safe_load of protected configs outside
the allowed files (system_config.py, precommit_check.py,
restore_system_config.py).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## C7 — Quality gates and remediation

### Task 14: Full test suite green + lint

**Files:** None new; verification only.

- [ ] **Step 1: Run all new tests**

Run: `uv run pytest tests/config/ -v`
Expected: All tests green across schemas, system_config, dashboard_merger, precommit_check, restore_script, migration_lint.

- [ ] **Step 2: Run the broader project tests for regressions**

Run: `uv run pytest tests/ -x --timeout=60 2>&1 | tail -30`
(If `pytest-timeout` is not installed, drop `--timeout=60`.)
Focus on: no new failures introduced by the migration. Pre-existing failures unrelated to system-config work are out of scope.

- [ ] **Step 3: Lint check**

Run: `uv run ruff check src/config/ src/mcp/augur_framework/tools/infrastructure/settings/dashboard.py scripts/restore_system_config.py tests/config/ 2>&1 | head -30`
Expected: clean. If issues, run `uv run ruff check --fix <paths>` and review the fixes.

- [ ] **Step 4: Smoke test the MCP handler imports**

```
python -c "from src.mcp.augur_framework.tools.infrastructure.settings.dashboard import _handle_llm_config, _handle_llm_config_write, _handle_default_cli, _merge_llm_payload, _atomic_write_yaml; print('OK')"
```
Expected: `OK`.

- [ ] **Step 5: Commit any lint fixes**

If `ruff check --fix` made changes:

```bash
git add -A
git commit -m "chore(system-config): ruff auto-fix on new files

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

Otherwise no commit needed.

---

### Task 15: Run the restore script against the current broken state

**Files:** None new; this fixes `config/system/llm.yaml` and `config/system/settings.yaml` on disk.

- [ ] **Step 1: Dry-run first**

Run: `python scripts/restore_system_config.py --dry-run`
Expected output: shows the restored llm.yaml (multi-profile template structure with `local`/`remote` profiles) and the restored settings.yaml (`mode: production` + `default_cli: claude` preserved). No files written.

- [ ] **Step 2: Inspect the dry-run output for accuracy**

Manually verify:
- `restored_llm.profiles` contains `local` and `remote` (matching the template)
- `restored_settings.mode == "production"` (preserved from current)
- `restored_settings.default_cli == "claude"` (preserved from current)

- [ ] **Step 3: Apply**

Run: `python scripts/restore_system_config.py --apply`
Expected: writes both files, prints backup paths under `get_cache_dir()/system-config-restore/`.

- [ ] **Step 4: Verify the files now satisfy the schema**

```bash
python -c "from src.config.system_config import invalidate_caches, load_llm_config, load_settings_config; invalidate_caches(); print('llm:', load_llm_config().active_profile, '|', list(load_llm_config().profiles.keys())); print('settings:', load_settings_config().mode, '|', load_settings_config().default_cli)"
```
Expected: `llm: local | ['local', 'remote']` and `settings: production | claude`.

- [ ] **Step 5: Verify the pre-commit guard now allows committing**

Stage the restored files:

```bash
git add config/system/llm.yaml config/system/settings.yaml
git status --short
```

Then dry-run the precommit_check:

```bash
python -m src.config.precommit_check config/system/llm.yaml config/system/settings.yaml
echo "Exit: $?"
```

Expected: exit `0`.

- [ ] **Step 6: Commit the restored configs**

```bash
git commit -m "$(cat <<'EOF'
fix(system-config): restore config/system/{llm,settings}.yaml to canonical shape

llm.yaml: regressed flat {model: claude-opus-4-20250514, provider: anthropic}
shape replaced with canonical multi-profile structure (local + remote
profiles + tasks routing for document_ocr) per
shared-vault/skills/ai/augur/config/llm.yaml.template. User-set fields
(api_key_env etc.) salvaged where applicable.

settings.yaml: mode=production preserved, default_cli=claude preserved.

Backups of prior state at ~/Library/Caches/Augur/system-config-restore/
(out of repo, rolling, one per source file).

This is the one-shot remediation. Subsequent regressions are prevented
by the three enforcement layers (read-time validator, write-time merger,
commit-time guard) shipped in C1-C5.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 16: Cross-platform verification (read-time validator on Windows path)

**Files:** None new; verification step.

This task is a Windows-platform note in the plan. If executing on macOS/Linux only:

- [ ] **Step 1: Verify `os.replace` is in use everywhere**

Run: `grep -rn "os.rename\|os.replace" src/config/ src/mcp/augur_framework/tools/infrastructure/settings/dashboard.py scripts/restore_system_config.py | grep -v test`
Expected: every match in the new code is `os.replace`. NO `os.rename` calls in the new code paths.

- [ ] **Step 2: Verify `pathlib.Path` is used consistently**

Run: `grep -rn 'os.path.join\|"/".join' src/config/ scripts/restore_system_config.py`
Expected: clean (no string-concat path building in new files).

- [ ] **Step 3: Verify `get_cache_dir()` resolution**

Run: `python -c "from src.config.paths import get_cache_dir; p = get_cache_dir(); print(p, '|', p.is_dir() or p.parent.is_dir())"`
Expected: prints a writable path (on macOS: `~/Library/Caches/Augur/`; on Windows: `%LOCALAPPDATA%\Augur\Caches` per ADR-550).

- [ ] **Step 4: Document Windows verification status**

This step does NOT commit. It's a note: if the project has a Windows CI lane, ensure these tests run there. If not, file a follow-up task to validate manually on Windows before claiming full Windows support. Per ADR-550 (Windows Hardening Support), the path helpers are platform-aware; the new code's use of `os.replace` + `pathlib.Path` should compose correctly.

---

### Task 17: ADR finalization via `/adr`

**Files:**
- Will create: `docs/adrs/ADR-733-system-config-integrity.md` (via `/adr` slash command)

- [ ] **Step 1: Find the next ADR number**

Run: `ls docs/adrs/ADR-73*.md | sort | tail -3`
Expected: latest is `ADR-732-loop-hygiene.md`. Next is ADR-733.

- [ ] **Step 2: Inspect ADR-732's frontmatter as a thin-index precedent**

Run: `head -30 docs/adrs/ADR-732-loop-hygiene.md`
Note the structure: frontmatter with `status`, `date`, `deciders`, `related`, `hub`, `tags`, `spec_file`, `plan_file` pointing at the spec and plan basenames.

- [ ] **Step 3: Create the ADR-733 thin index**

Write `docs/adrs/ADR-733-system-config-integrity.md`:

```markdown
---
status: Accepted
date: 2026-05-12
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

> **ADR-733 is an index file.** The substantive design and implementation steps live in the linked spec + plan. This file carries pointers, status, and a one-line decision summary.

## Decision summary

Introduce three-layer enforcement for `config/system/llm.yaml` and `config/system/settings.yaml`: schemas-as-code in `src/config/schemas/`, a read-time validator in `src/config/system_config.py`, a write-time merger in `src/mcp/augur_framework/tools/infrastructure/settings/dashboard.py` (rewritten to merge + validate + atomic-write via `os.replace`), a commit-time guard in `.githooks/pre-commit` + `src/config/precommit_check.py`, and a one-shot remediation script `scripts/restore_system_config.py`. Root cause: dashboard onboarding handler performed full-file `_write_yaml(path, config)` for every form submission, clobbering the canonical multi-profile structure to a flat `{model, provider}` shape whenever the form was for a single vendor — directly contradicting the "Vendor-neutral by architecture" principle. All five existing `yaml.safe_load` callsites for these two files migrated to the validator API; a repo-lint canary asserts no remaining raw loads outside the allowed files. Cross-platform safety via `os.replace` (Windows-safe) everywhere; rolling backups in `get_cache_dir()` (no repo pollution).

## Spec (canonical)

- [`docs/superpowers/specs/2026-05-12-system-config-integrity-design.md`](../superpowers/specs/2026-05-12-system-config-integrity-design.md)

## Plan (canonical, drives `/adr implement`)

- [`docs/superpowers/plans/2026-05-12-system-config-integrity.md`](../superpowers/plans/2026-05-12-system-config-integrity.md) — 17 tasks across 7 checkpoints (C1 schemas, C2 read-time validator, C3 dashboard merger + atomic write, C4 commit-time guard, C5 one-shot restore, C6 migration of 5 readers, C7 quality gates + one-shot remediation + this ADR). TDD throughout.

## Status notes

Spec + plan + implementation landed 2026-05-12 in the same `/superpowers:brainstorming` → `/superpowers:writing-plans` → `/superpowers:subagent-driven-development` chain. Two framing fixes applied to the spec during a cross-check against `docs/architecture-overview.md` + `docs/what-is-augur.md` + git history: (1) reframed `llm.yaml`'s purpose as explicit internal-task LLM exception routing (retry_diagnosis, document_ocr, cloud_vision, ai_self_healer per `src/lib/llm_retry.py:resolve_cli()`), not "Codex/Gemini routing" which is a separate `cli_agents.yaml` concern; (2) recorded the harness boundary: Augur defaults to native AI-client reasoning, while direct model/API use is a rare named exception governed by config/ADR approval.

Load-bearing claim: the schema in `src/config/schemas/llm_schema.py` is the single source of truth for the shape of `config/system/llm.yaml`. Every reader, the dashboard merger, and the pre-commit hook all import from it. Future shape changes happen in the schema FIRST, then the file. The cross-agent enforcement (pre-commit hook fires for Claude/Codex/Gemini/OpenCode/Copilot and hand-edits) makes the regression mechanically impossible at the commit boundary.
```

- [ ] **Step 4: Run the post-write hook**

```bash
python .github/scripts/generate_adr_index.py
python src/lib/index/unified_indexer.py --category adrs
cd shared-vault/skills/ai/scripts && python sync_agents sync all && cd -
```

Expected: ADR index regenerated, RAG pointer regenerated (582 entries), agent instructions resynced.

- [ ] **Step 5: Commit**

```bash
git add docs/adrs/ADR-733-system-config-integrity.md docs/generated/adr-index.md
git commit -m "$(cat <<'EOF'
adr(system-config-integrity): ADR-733 — schemas, validators, and atomic merger

Thin index ADR pointing at the spec at
docs/superpowers/specs/2026-05-12-system-config-integrity-design.md
and the plan at
docs/superpowers/plans/2026-05-12-system-config-integrity.md.

Status: Accepted. 17/17 plan tasks complete. Root cause (destructive
_write_yaml in dashboard handler) fixed; three enforcement layers
shipped (read-time validator, write-time merger, commit-time guard);
one-shot restore script repaired the current broken state. 5 yaml.safe_load
callsites migrated to the validator API; repo-lint canary green.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review

**Spec coverage:**

| Spec section | Plan tasks covering it |
|---|---|
| §3 Decision summary — three-layer enforcement + one-shot | C1-C5 fully implement the architecture |
| §3 — strict llm.yaml schema (unknown keys raise) | Task 1 |
| §3 — permissive settings.yaml schema (unknown keys warn, don't raise) | Task 2 |
| §3 — atomic `os.replace` everywhere (Windows-safe) | Tasks 4, 8, 16 |
| §3 — rolling backup in `get_cache_dir()` (no repo pollution) | Task 8 |
| §4.1 Schemas | Tasks 1, 2 |
| §4.2 Read-time validator with cache + raw API | Task 3 |
| §4.3 Write-time merger (3 rewritten handlers) | Tasks 4, 5 |
| §4.4 Commit-time guard (precommit_check + .githooks/pre-commit) | Tasks 6, 7 |
| §4.5 One-shot restore script with all behavior contracts | Task 8 |
| §5 Cross-platform behavior | Task 16 verifies os.replace + pathlib.Path + get_cache_dir() |
| §6 Safety / error handling — all refusal paths return structured errors | Tasks 5, 6, 8 tests cover every refusal |
| §7 Testing strategy (all 7 surfaces) | Tasks 1, 2, 3, 4+5, 6, 8, 9 (repo-lint) |
| §8 Migration of existing readers | Task 9 (canary) + Tasks 10-13 (callsites) |
| §9 Out of scope | Confirmed not implemented (no cli_agents.yaml schema, no LLM-vendor selection logic, no onboarding UI redesign, no auto-recovery on read failure) |

No gaps detected.

**Placeholder scan:** no "TBD", "TODO", "implement later", "fill in details", "add appropriate error handling", or "similar to Task N" markers in the plan body.

**Type consistency:**

- `LlmConfig`, `LlmProfile`, `LlmSchemaError` — used consistently across Tasks 1, 3, 4, 5, 8.
- `SettingsConfig`, `SettingsSchemaError` — Tasks 2, 3, 5, 8.
- `validate_llm_config()`, `validate_settings_config()` — same signatures throughout.
- `load_llm_config()`, `load_settings_config()`, `invalidate_caches()`, `llm_config_raw()`, `settings_config_raw()` — defined in Task 3, referenced verbatim in Tasks 4-13.
- `_atomic_write_yaml(path, data)` — defined in Task 4, used in Tasks 4-8.
- `_merge_llm_payload(existing, incoming)` — defined in Task 4, used in Task 5.
- `REQUIRED_KEYS`, `OPTIONAL_KEYS`, `REQUIRED_PROFILE_FIELDS`, `ALLOWED_MODES`, `KNOWN_KEYS` — frozensets defined in Tasks 1-2, referenced consistently.
- `os.replace` (not `os.rename`) — used everywhere; verified in Task 16.

All identifiers stable across tasks.

---

## Execution

Plan complete and saved to `docs/superpowers/plans/2026-05-12-system-config-integrity.md`. Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task, two-stage review between tasks, fast iteration.
2. **Inline Execution** — execute tasks in this session via `superpowers:executing-plans`, batch execution with checkpoints.

Which approach?
