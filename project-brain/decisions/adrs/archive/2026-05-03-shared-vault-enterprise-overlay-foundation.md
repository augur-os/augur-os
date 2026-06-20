# Shared Vault Enterprise Overlay Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the foundation for a repo-local `shared-vault/` plus append-only promotion packets while preserving the existing private vault contract.

**Architecture:** This plan implements the first two phases of the shared-vault enterprise overlay design: path helpers and promotion packets. It does not migrate Browse, wiki compilation, or repo-root `skills/`; those need separate plans because they touch independent runtime and UI surfaces. The foundation keeps shared-vault paths explicit, keeps private-vault writes as the default, and writes promotion payloads as new packet folders under `shared-vault/inbox/promotions/`.

**Tech Stack:** Python 3.11+, pytest, `src.config.paths`, `src.lib.frontmatter_utils`, YAML frontmatter, repo-tracked Markdown scaffolding.

---

## Scope Boundaries

This plan covers:

- `shared-vault/` root scaffolding.
- Shared/private vault path helpers.
- Append-only promotion packet creation.
- A small CLI wrapper for creating a promotion packet.
- Tests proving the helpers and packet writer behave as designed.

This plan does not cover:

- Browse merged shared/private UI.
- Wiki compiler integration of accepted packets.
- Role-aware ranking.
- Root `skills/` retirement.
- Skill migration to `shared-vault/skills/`.

Those are separate implementation plans after this foundation lands.

## File Structure

| Path | Action | Responsibility |
| --- | --- | --- |
| `src/config/paths.py` | Modify | Add shared-vault and private-vault alias helpers. |
| `tests/src/test_paths.py` | Modify | Test shared/private vault path resolution. |
| `shared-vault/README.md` | Create | Human-facing shared-vault contract. |
| `shared-vault/inbox/README.md` | Create | Inbox root explanation. |
| `shared-vault/inbox/promotions/README.md` | Create | Append-only promotion packet contract. |
| `shared-vault/notes/README.md` | Create | Shared notes root explanation. |
| `shared-vault/notes/roles/README.md` | Create | Role playbook location. |
| `shared-vault/sources/README.md` | Create | Shared source-card root explanation. |
| `shared-vault/wiki/README.md` | Create | Shared compiled wiki root explanation. |
| `shared-vault/skills/README.md` | Create | Shared skill root explanation. |
| `shared-vault/drafts/README.md` | Create | Inactive draft root explanation. |
| `shared-vault/archive/README.md` | Create | Inactive archive root explanation. |
| `shared-vault/config/README.md` | Create | Durable shared non-secret config root explanation. |
| `tests/test_shared_vault_contract.py` | Create | Static contract tests for tracked shared-vault roots and frontmatter. |
| `src/lib/vault_promotion.py` | Create | Promotion packet data model and writer. |
| `tests/unit/test_vault_promotion.py` | Create | Unit tests for append-only packet behavior. |
| `scripts/create_promotion_packet.py` | Create | CLI wrapper around the packet writer. |
| `tests/scripts/test_create_promotion_packet.py` | Create | CLI wrapper tests. |

---

### Task 1: Shared And Private Vault Path Helpers

**Files:**
- Modify: `src/config/paths.py`
- Modify: `tests/src/test_paths.py`

- [ ] **Step 1: Write failing path helper tests**

Append this test block to `tests/src/test_paths.py` after `test_vault_user_surface_helpers_share_vault_root`:

```python
def test_shared_vault_helpers_resolve_under_project_root(tmp_path, monkeypatch):
    project_root = tmp_path / "repo"
    project_root.mkdir()

    monkeypatch.setattr(paths, "get_project_root", lambda: project_root)
    paths.invalidate_project_cache()

    shared = project_root / "shared-vault"

    assert paths.get_shared_vault_dir() == shared
    assert paths.get_shared_vault_inbox_dir() == shared / "inbox"
    assert paths.get_shared_vault_promotions_dir() == shared / "inbox" / "promotions"
    assert paths.get_shared_vault_notes_dir() == shared / "notes"
    assert paths.get_shared_vault_sources_dir() == shared / "sources"
    assert paths.get_shared_wiki_dir() == shared / "wiki"
    assert paths.get_shared_vault_skills_dir() == shared / "skills"
    assert paths.get_shared_vault_drafts_dir() == shared / "drafts"
    assert paths.get_shared_vault_archive_dir() == shared / "archive"
    assert paths.get_shared_vault_config_dir() == shared / "config"


def test_private_vault_aliases_keep_existing_vault_contract(tmp_path, monkeypatch):
    private_vault = tmp_path / "private-vault"
    private_vault.mkdir()

    monkeypatch.setattr(paths, "_vault_home_dir", lambda: private_vault)
    paths.invalidate_project_cache()

    assert paths.get_private_vault_dir() == private_vault
    assert paths.get_private_vault_skills_dir() == private_vault / "skills"
    assert paths.get_private_wiki_dir() == private_vault / "wiki"


def test_get_vault_source_roots_returns_shared_then_private(tmp_path, monkeypatch):
    project_root = tmp_path / "repo"
    private_vault = tmp_path / "private-vault"
    project_root.mkdir()
    private_vault.mkdir()

    monkeypatch.setattr(paths, "get_project_root", lambda: project_root)
    monkeypatch.setattr(paths, "_vault_home_dir", lambda: private_vault)
    paths.invalidate_project_cache()

    assert paths.get_vault_source_roots() == [
        ("shared", project_root / "shared-vault"),
        ("private", private_vault),
    ]


def test_shared_vault_dir_allows_env_override_for_live_runtime(tmp_path, monkeypatch):
    override = tmp_path / "override-shared-vault"
    monkeypatch.setenv("AUGUR_SHARED_VAULT", str(override))
    paths.invalidate_project_cache()

    assert paths.get_shared_vault_dir() == override
```

- [ ] **Step 2: Run the new path helper tests and verify they fail**

Run:

```bash
pytest \
  tests/src/test_paths.py::test_shared_vault_helpers_resolve_under_project_root \
  tests/src/test_paths.py::test_private_vault_aliases_keep_existing_vault_contract \
  tests/src/test_paths.py::test_get_vault_source_roots_returns_shared_then_private \
  tests/src/test_paths.py::test_shared_vault_dir_allows_env_override_for_live_runtime \
  -q
```

Expected: FAIL with `AttributeError` for `get_shared_vault_dir`.

- [ ] **Step 3: Add the shared/private helper functions**

In `src/config/paths.py`, insert this block immediately after `get_vault_skills_dir()`:

```python
def get_shared_vault_dir(project_root: Path | None = None) -> Path:
    """Return the repo-local shared team vault root."""
    if project_root is None:
        override = _env_path("AUGUR_SHARED_VAULT")
        if override:
            return override
    root = project_root.resolve() if project_root is not None else get_project_root()
    return root / "shared-vault"


def get_shared_vault_inbox_dir(project_root: Path | None = None) -> Path:
    return get_shared_vault_dir(project_root) / "inbox"


def get_shared_vault_promotions_dir(project_root: Path | None = None) -> Path:
    return get_shared_vault_inbox_dir(project_root) / "promotions"


def get_shared_vault_notes_dir(project_root: Path | None = None) -> Path:
    return get_shared_vault_dir(project_root) / "notes"


def get_shared_vault_sources_dir(project_root: Path | None = None) -> Path:
    return get_shared_vault_dir(project_root) / "sources"


def get_shared_wiki_dir(project_root: Path | None = None) -> Path:
    return get_shared_vault_dir(project_root) / "wiki"


def get_shared_vault_skills_dir(project_root: Path | None = None) -> Path:
    return get_shared_vault_dir(project_root) / "skills"


def get_shared_vault_drafts_dir(project_root: Path | None = None) -> Path:
    return get_shared_vault_dir(project_root) / "drafts"


def get_shared_vault_archive_dir(project_root: Path | None = None) -> Path:
    return get_shared_vault_dir(project_root) / "archive"


def get_shared_vault_config_dir(project_root: Path | None = None) -> Path:
    return get_shared_vault_dir(project_root) / "config"


def get_private_vault_dir() -> Path:
    """Alias for the configured user-owned vault root."""
    return get_vault_dir()


def get_private_vault_skills_dir() -> Path:
    return get_vault_skills_dir()


def get_private_wiki_dir() -> Path:
    return get_wiki_dir()


def get_vault_source_roots(project_root: Path | None = None) -> list[tuple[str, Path]]:
    """Return shared and private vault roots in read-precedence order."""
    if project_root is None:
        return [
            ("shared", get_shared_vault_dir()),
            ("private", get_private_vault_dir()),
        ]
    root = project_root.resolve()
    return [
        ("shared", get_shared_vault_dir(root)),
        ("private", get_configured_vault_dir(root)),
    ]
```

- [ ] **Step 4: Include shared-vault roots in path validation**

In `src/config/paths.py`, replace the `repo_dirs` block inside `validate_paths()` with:

```python
    repo_dirs = [
        get_config_dir(),
        get_skills_dir(),
        get_shared_vault_dir(),
        get_shared_vault_inbox_dir(),
        get_shared_vault_promotions_dir(),
        get_shared_vault_notes_dir(),
        get_shared_vault_notes_dir() / "roles",
        get_shared_vault_sources_dir(),
        get_shared_wiki_dir(),
        get_shared_vault_skills_dir(),
        get_shared_vault_drafts_dir(),
        get_shared_vault_archive_dir(),
        get_shared_vault_config_dir(),
    ]
```

- [ ] **Step 5: Run the focused path tests and verify they pass**

Run:

```bash
pytest \
  tests/src/test_paths.py::test_shared_vault_helpers_resolve_under_project_root \
  tests/src/test_paths.py::test_private_vault_aliases_keep_existing_vault_contract \
  tests/src/test_paths.py::test_get_vault_source_roots_returns_shared_then_private \
  tests/src/test_paths.py::test_shared_vault_dir_allows_env_override_for_live_runtime \
  -q
```

Expected: `4 passed`.

- [ ] **Step 6: Run the full path test module**

Run:

```bash
pytest tests/src/test_paths.py tests/unit/test_scoped_paths.py -q
```

Expected: all tests in both modules pass.

- [ ] **Step 7: Commit the path helper change**

```bash
git add src/config/paths.py tests/src/test_paths.py
git commit -m "feat(paths): add shared vault helpers"
```

---

### Task 2: Repo-Tracked Shared Vault Scaffold

**Files:**
- Create: `shared-vault/README.md`
- Create: `shared-vault/inbox/README.md`
- Create: `shared-vault/inbox/promotions/README.md`
- Create: `shared-vault/notes/README.md`
- Create: `shared-vault/notes/roles/README.md`
- Create: `shared-vault/sources/README.md`
- Create: `shared-vault/wiki/README.md`
- Create: `shared-vault/skills/README.md`
- Create: `shared-vault/drafts/README.md`
- Create: `shared-vault/archive/README.md`
- Create: `shared-vault/config/README.md`
- Create: `tests/test_shared_vault_contract.py`

- [ ] **Step 1: Write failing scaffold contract tests**

Create `tests/test_shared_vault_contract.py`:

```python
from __future__ import annotations

from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]


REQUIRED_READMES = [
    "README.md",
    "inbox/README.md",
    "inbox/promotions/README.md",
    "notes/README.md",
    "notes/roles/README.md",
    "sources/README.md",
    "wiki/README.md",
    "skills/README.md",
    "drafts/README.md",
    "archive/README.md",
    "config/README.md",
]


def _frontmatter(path: Path) -> dict:
    content = path.read_text(encoding="utf-8")
    assert content.startswith("---\n"), f"{path} must start with YAML frontmatter"
    _, frontmatter, _body = content.split("---", 2)
    parsed = yaml.safe_load(frontmatter)
    assert isinstance(parsed, dict), f"{path} frontmatter must parse as a mapping"
    return parsed


def test_shared_vault_required_readmes_exist() -> None:
    root = PROJECT_ROOT / "shared-vault"

    for rel_path in REQUIRED_READMES:
        path = root / rel_path
        assert path.is_file(), f"missing shared-vault contract file: {path}"


def test_shared_vault_readmes_have_frontmatter_and_scope() -> None:
    root = PROJECT_ROOT / "shared-vault"

    for rel_path in REQUIRED_READMES:
        metadata = _frontmatter(root / rel_path)
        assert metadata["vault_scope"] == "shared"
        assert metadata["status"] in {"active", "inactive"}


def test_shared_vault_contract_does_not_recreate_root_skills() -> None:
    root_readme = (PROJECT_ROOT / "shared-vault" / "README.md").read_text(encoding="utf-8")

    assert "repo-root `skills/` is retired" in root_readme
    assert "shared-vault/skills/" in root_readme
```

- [ ] **Step 2: Run scaffold tests and verify they fail**

Run:

```bash
pytest tests/test_shared_vault_contract.py -q
```

Expected: FAIL because `shared-vault/README.md` is missing.

- [ ] **Step 3: Create `shared-vault/README.md`**

Create `shared-vault/README.md`:

```markdown
---
title: Shared Vault
vault_scope: shared
status: active
owner: team
---

# Shared Vault

`shared-vault/` is the repo-local team brain. It uses the same root contract as each private vault, but its contents are shared through the project repo.

The default read model is merged: shared vault plus private vault. The default write model remains private. Shared updates enter through append-only promotion packets under `shared-vault/inbox/promotions/`.

Final skill ownership uses `shared-vault/skills/` for team skills and private vault `skills/` for personal skills. The repo-root `skills/` is retired in the final architecture.
```

- [ ] **Step 4: Create inbox README files**

Create `shared-vault/inbox/README.md`:

```markdown
---
title: Shared Vault Inbox
vault_scope: shared
status: active
owner: team
---

# Shared Vault Inbox

This folder holds shared intake queues. Promotion packets live under `promotions/` so contributors can propose shared knowledge without editing canonical wiki, notes, or skill files directly.
```

Create `shared-vault/inbox/promotions/README.md`:

```markdown
---
title: Shared Vault Promotions
vault_scope: shared
status: active
owner: team
---

# Shared Vault Promotions

Promotion packets are append-only PR payloads. Each packet gets a unique folder named with date, contributor, and topic.

Canonical shared files are integrated from accepted packets by a compiler or maintainer process.
```

- [ ] **Step 5: Create shared content README files**

Create `shared-vault/notes/README.md`:

```markdown
---
title: Shared Vault Notes
vault_scope: shared
status: active
owner: team
---

# Shared Vault Notes

Team-readable notes and role playbooks live here. Roles are metadata and views; only role entrypoints live under `roles/`.
```

Create `shared-vault/notes/roles/README.md`:

```markdown
---
title: Shared Vault Role Playbooks
vault_scope: shared
status: active
owner: team
---

# Shared Vault Role Playbooks

Role playbooks are human-readable entrypoints for team roles such as developer, architect, validation, DevOps, product, and manager.
```

Create `shared-vault/sources/README.md`:

```markdown
---
title: Shared Vault Sources
vault_scope: shared
status: active
owner: team
---

# Shared Vault Sources

Team-approved source cards and captured source material live here. Personal source material stays in the private vault until promoted.
```

Create `shared-vault/wiki/README.md`:

```markdown
---
title: Shared Vault Wiki
vault_scope: shared
status: active
owner: team
---

# Shared Vault Wiki

This folder holds canonical shared compiled concept and query pages. Default agents do not write here directly; accepted promotion packets are integrated by a shared compiler or maintainer.
```

Create `shared-vault/skills/README.md`:

```markdown
---
title: Shared Vault Skills
vault_scope: shared
status: active
owner: team
---

# Shared Vault Skills

Team skills and capability bundles live here. Framework libraries belong in `src/lib/`, dashboard app code belongs in `apps/`, and generated client exports remain generated output.
```

- [ ] **Step 6: Create inactive root README files**

Create `shared-vault/drafts/README.md`:

```markdown
---
title: Shared Vault Drafts
vault_scope: shared
status: inactive
owner: team
---

# Shared Vault Drafts

Inactive shared drafts live here. Normal discovery, Browse, wiki compounding, and MCP registration exclude this folder unless an explicit inactive scope is requested.
```

Create `shared-vault/archive/README.md`:

```markdown
---
title: Shared Vault Archive
vault_scope: shared
status: inactive
owner: team
---

# Shared Vault Archive

Inactive historical shared material lives here. Archived content is retained for reference and excluded from normal operation unless explicitly requested.
```

Create `shared-vault/config/README.md`:

```markdown
---
title: Shared Vault Config
vault_scope: shared
status: active
owner: team
---

# Shared Vault Config

Durable non-secret team configuration lives here. Runtime state, logs, caches, generated indexes, sessions, and secrets do not belong in this folder.
```

- [ ] **Step 7: Run scaffold tests and verify they pass**

Run:

```bash
pytest tests/test_shared_vault_contract.py -q
```

Expected: `3 passed`.

- [ ] **Step 8: Commit the shared-vault scaffold**

```bash
git add shared-vault tests/test_shared_vault_contract.py
git commit -m "docs(vault): add shared vault scaffold"
```

---

### Task 3: Append-Only Promotion Packet Library

**Files:**
- Create: `src/lib/vault_promotion.py`
- Create: `tests/unit/test_vault_promotion.py`

- [ ] **Step 1: Write failing promotion packet tests**

Create `tests/unit/test_vault_promotion.py`:

```python
from __future__ import annotations

from datetime import date

import pytest
import yaml

from src.lib.frontmatter_utils import parse_frontmatter
from src.lib.vault_promotion import PromotionPacketRequest, create_promotion_packet


def test_create_promotion_packet_writes_append_only_folder(tmp_path):
    shared_vault = tmp_path / "shared-vault"
    private_note = tmp_path / "private-vault" / "notes" / "idea.md"
    private_note.parent.mkdir(parents=True)
    private_note.write_text("private idea\n", encoding="utf-8")

    packet = create_promotion_packet(
        shared_vault,
        PromotionPacketRequest(
            topic="Compiler Conflict Avoidance",
            contributor="Guri",
            synthesis="Use append-only packets to avoid shared wiki merge conflicts.",
            source_paths=[private_note],
            proposed_actions=["Integrate into the shared wiki promotion model"],
            proposed_links=["Shared Vault Enterprise Overlay"],
            roles=["architect"],
            domains=["knowledge"],
            packet_date=date(2026, 5, 3),
        ),
    )

    assert packet.path == shared_vault / "inbox" / "promotions" / "2026-05-03-guri-compiler-conflict-avoidance"
    assert packet.manifest_path == packet.path / "manifest.yaml"
    assert packet.synthesis_path == packet.path / "synthesis.md"
    assert (packet.path / "sources" / "README.md").is_file()

    manifest = yaml.safe_load(packet.manifest_path.read_text(encoding="utf-8"))
    assert manifest["kind"] == "shared-vault-promotion-packet"
    assert manifest["status"] == "packet"
    assert manifest["topic"] == "Compiler Conflict Avoidance"
    assert manifest["contributor"] == "Guri"
    assert manifest["roles"] == ["architect"]
    assert manifest["domains"] == ["knowledge"]
    assert manifest["source_refs"][0]["path"] == str(private_note)
    assert len(manifest["source_refs"][0]["sha256"]) == 64

    metadata, body = parse_frontmatter(packet.synthesis_path)
    assert metadata["promotion_state"] == "packet"
    assert metadata["vault_scope"] == "shared"
    assert "append-only packets" in body


def test_create_promotion_packet_uses_unique_suffix_when_folder_exists(tmp_path):
    shared_vault = tmp_path / "shared-vault"
    request = PromotionPacketRequest(
        topic="Same Topic",
        contributor="Guri",
        synthesis="First packet.",
        packet_date=date(2026, 5, 3),
    )

    first = create_promotion_packet(shared_vault, request)
    second = create_promotion_packet(shared_vault, request)

    assert first.path.name == "2026-05-03-guri-same-topic"
    assert second.path.name == "2026-05-03-guri-same-topic-2"


def test_create_promotion_packet_rejects_empty_topic(tmp_path):
    with pytest.raises(ValueError, match="topic is required"):
        create_promotion_packet(
            tmp_path / "shared-vault",
            PromotionPacketRequest(topic="", contributor="Guri", synthesis="Body"),
        )


def test_create_promotion_packet_rejects_empty_contributor(tmp_path):
    with pytest.raises(ValueError, match="contributor is required"):
        create_promotion_packet(
            tmp_path / "shared-vault",
            PromotionPacketRequest(topic="Topic", contributor="", synthesis="Body"),
        )
```

- [ ] **Step 2: Run promotion packet tests and verify they fail**

Run:

```bash
pytest tests/unit/test_vault_promotion.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.lib.vault_promotion'`.

- [ ] **Step 3: Create the promotion packet library**

Create `src/lib/vault_promotion.py`:

```python
"""Append-only promotion packets for shared-vault intake."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from hashlib import sha256
from pathlib import Path
import re
from typing import Any

import yaml

from src.lib.frontmatter_utils import write_frontmatter


@dataclass(frozen=True)
class PromotionPacketRequest:
    topic: str
    contributor: str
    synthesis: str
    source_paths: list[Path] = field(default_factory=list)
    proposed_actions: list[str] = field(default_factory=list)
    proposed_links: list[str] = field(default_factory=list)
    roles: list[str] = field(default_factory=list)
    domains: list[str] = field(default_factory=list)
    sensitivity: str = "internal"
    packet_date: date | None = None


@dataclass(frozen=True)
class PromotionPacket:
    path: Path
    manifest_path: Path
    synthesis_path: Path


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "packet"


def _require_text(value: str, field_name: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field_name} is required")
    return cleaned


def _unique_packet_dir(promotions_dir: Path, base_name: str) -> Path:
    candidate = promotions_dir / base_name
    if not candidate.exists():
        return candidate

    index = 2
    while True:
        candidate = promotions_dir / f"{base_name}-{index}"
        if not candidate.exists():
            return candidate
        index += 1


def _hash_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_refs(source_paths: list[Path]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for source_path in source_paths:
        path = Path(source_path)
        record: dict[str, Any] = {
            "path": str(path),
            "exists": path.exists(),
            "is_file": path.is_file(),
        }
        if path.is_file():
            record["sha256"] = _hash_file(path)
        refs.append(record)
    return refs


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def _write_actions(path: Path, request: PromotionPacketRequest) -> None:
    actions = request.proposed_actions or []
    body = "\n".join(f"- [ ] {action}" for action in actions)
    write_frontmatter(
        path,
        {
            "title": "Proposed Actions",
            "vault_scope": "shared",
            "promotion_state": "packet",
        },
        body,
    )


def _write_links(path: Path, request: PromotionPacketRequest) -> None:
    links = request.proposed_links or []
    body = "\n".join(f"- {link}" for link in links)
    write_frontmatter(
        path,
        {
            "title": "Proposed Links",
            "vault_scope": "shared",
            "promotion_state": "packet",
        },
        body,
    )


def create_promotion_packet(
    shared_vault_dir: Path,
    request: PromotionPacketRequest,
) -> PromotionPacket:
    """Create a new append-only promotion packet folder."""
    topic = _require_text(request.topic, "topic")
    contributor = _require_text(request.contributor, "contributor")
    synthesis = _require_text(request.synthesis, "synthesis")
    packet_date = request.packet_date or date.today()

    promotions_dir = Path(shared_vault_dir) / "inbox" / "promotions"
    promotions_dir.mkdir(parents=True, exist_ok=True)

    base_name = f"{packet_date.isoformat()}-{_slug(contributor)}-{_slug(topic)}"
    packet_dir = _unique_packet_dir(promotions_dir, base_name)
    packet_dir.mkdir(parents=True)
    (packet_dir / "sources").mkdir()

    manifest = {
        "schema_version": 1,
        "kind": "shared-vault-promotion-packet",
        "status": "packet",
        "topic": topic,
        "contributor": contributor,
        "date": packet_date.isoformat(),
        "sensitivity": request.sensitivity,
        "roles": list(request.roles),
        "domains": list(request.domains),
        "source_refs": _source_refs(request.source_paths),
        "outputs": {
            "synthesis": "synthesis.md",
            "proposed_actions": "proposed-actions.md",
            "proposed_links": "proposed-links.md",
        },
    }

    manifest_path = packet_dir / "manifest.yaml"
    synthesis_path = packet_dir / "synthesis.md"

    _write_yaml(manifest_path, manifest)
    write_frontmatter(
        synthesis_path,
        {
            "title": topic,
            "vault_scope": "shared",
            "promotion_state": "packet",
            "contributor": contributor,
            "roles": list(request.roles),
            "domains": list(request.domains),
            "sensitivity": request.sensitivity,
        },
        synthesis,
    )
    _write_actions(packet_dir / "proposed-actions.md", request)
    _write_links(packet_dir / "proposed-links.md", request)
    write_frontmatter(
        packet_dir / "sources" / "README.md",
        {
            "title": "Promotion Packet Sources",
            "vault_scope": "shared",
            "promotion_state": "packet",
        },
        "Source files are referenced from `manifest.yaml` with existence and hash metadata.",
    )

    return PromotionPacket(
        path=packet_dir,
        manifest_path=manifest_path,
        synthesis_path=synthesis_path,
    )
```

- [ ] **Step 4: Run promotion packet tests and verify they pass**

Run:

```bash
pytest tests/unit/test_vault_promotion.py -q
```

Expected: `4 passed`.

- [ ] **Step 5: Commit the promotion library**

```bash
git add src/lib/vault_promotion.py tests/unit/test_vault_promotion.py
git commit -m "feat(vault): add promotion packet writer"
```

---

### Task 4: Promotion Packet CLI Wrapper

**Files:**
- Create: `scripts/create_promotion_packet.py`
- Create: `tests/scripts/test_create_promotion_packet.py`

- [ ] **Step 1: Write failing CLI tests**

Create `tests/scripts/test_create_promotion_packet.py`:

```python
from __future__ import annotations

import yaml

from scripts import create_promotion_packet


def test_main_creates_packet_from_inline_synthesis(tmp_path, monkeypatch, capsys):
    shared_vault = tmp_path / "shared-vault"
    monkeypatch.setattr(create_promotion_packet, "get_shared_vault_dir", lambda: shared_vault)

    rc = create_promotion_packet.main(
        [
            "--topic",
            "Team Wiki Conflict Control",
            "--contributor",
            "Guri",
            "--synthesis",
            "Promotion packets keep canonical wiki edits out of contributor PRs.",
            "--date",
            "2026-05-03",
            "--role",
            "architect",
            "--domain",
            "knowledge",
            "--action",
            "Integrate accepted packets in a batch",
            "--link",
            "Shared Vault Enterprise Overlay",
        ]
    )

    captured = capsys.readouterr()
    assert rc == 0
    packet_path = shared_vault / "inbox" / "promotions" / "2026-05-03-guri-team-wiki-conflict-control"
    assert str(packet_path) in captured.out
    assert (packet_path / "synthesis.md").is_file()

    manifest = yaml.safe_load((packet_path / "manifest.yaml").read_text(encoding="utf-8"))
    assert manifest["roles"] == ["architect"]
    assert manifest["domains"] == ["knowledge"]


def test_main_creates_packet_from_synthesis_file(tmp_path, monkeypatch):
    shared_vault = tmp_path / "shared-vault"
    synthesis_file = tmp_path / "synthesis.md"
    synthesis_file.write_text("Packet body from a file.\n", encoding="utf-8")
    monkeypatch.setattr(create_promotion_packet, "get_shared_vault_dir", lambda: shared_vault)

    rc = create_promotion_packet.main(
        [
            "--topic",
            "File Based Packet",
            "--contributor",
            "Guri",
            "--synthesis-file",
            str(synthesis_file),
            "--date",
            "2026-05-03",
        ]
    )

    assert rc == 0
    packet_path = shared_vault / "inbox" / "promotions" / "2026-05-03-guri-file-based-packet"
    assert "Packet body from a file." in (packet_path / "synthesis.md").read_text(encoding="utf-8")
```

- [ ] **Step 2: Run CLI tests and verify they fail**

Run:

```bash
pytest tests/scripts/test_create_promotion_packet.py -q
```

Expected: FAIL with `ImportError` for `scripts.create_promotion_packet`.

- [ ] **Step 3: Create the CLI wrapper**

Create `scripts/create_promotion_packet.py`:

```python
#!/usr/bin/env python3
"""Create an append-only shared-vault promotion packet."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
from typing import Sequence

from src.config.paths import get_shared_vault_dir
from src.lib.vault_promotion import PromotionPacketRequest, create_promotion_packet


def _read_synthesis(args: argparse.Namespace) -> str:
    if args.synthesis_file:
        return Path(args.synthesis_file).read_text(encoding="utf-8")
    return args.synthesis or ""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create a shared-vault promotion packet.")
    parser.add_argument("--topic", required=True)
    parser.add_argument("--contributor", required=True)
    synthesis = parser.add_mutually_exclusive_group(required=True)
    synthesis.add_argument("--synthesis")
    synthesis.add_argument("--synthesis-file")
    parser.add_argument("--source", action="append", default=[])
    parser.add_argument("--action", action="append", default=[])
    parser.add_argument("--link", action="append", default=[])
    parser.add_argument("--role", action="append", default=[])
    parser.add_argument("--domain", action="append", default=[])
    parser.add_argument("--sensitivity", default="internal")
    parser.add_argument("--date", dest="packet_date")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    packet_date = date.fromisoformat(args.packet_date) if args.packet_date else None
    packet = create_promotion_packet(
        get_shared_vault_dir(),
        PromotionPacketRequest(
            topic=args.topic,
            contributor=args.contributor,
            synthesis=_read_synthesis(args),
            source_paths=[Path(source) for source in args.source],
            proposed_actions=list(args.action),
            proposed_links=list(args.link),
            roles=list(args.role),
            domains=list(args.domain),
            sensitivity=args.sensitivity,
            packet_date=packet_date,
        ),
    )
    print(packet.path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run CLI tests and verify they pass**

Run:

```bash
pytest tests/scripts/test_create_promotion_packet.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Run a dry local CLI smoke against a temp shared vault**

Run:

```bash
tmpdir="$(mktemp -d)"
AUGUR_SHARED_VAULT="$tmpdir/shared-vault" python scripts/create_promotion_packet.py \
  --topic "Smoke Packet" \
  --contributor "Guri" \
  --synthesis "Smoke packet body." \
  --date 2026-05-03 \
  --role architect \
  --domain knowledge
find "$tmpdir/shared-vault/inbox/promotions" -maxdepth 2 -type f | sort
```

Expected: command prints a packet directory path, and `find` lists `manifest.yaml`, `proposed-actions.md`, `proposed-links.md`, `sources/README.md`, and `synthesis.md`.

- [ ] **Step 6: Commit the CLI wrapper**

```bash
git add scripts/create_promotion_packet.py tests/scripts/test_create_promotion_packet.py
git commit -m "feat(vault): add promotion packet CLI"
```

---

### Task 5: Foundation Verification

**Files:**
- Verify: `src/config/paths.py`
- Verify: `src/lib/vault_promotion.py`
- Verify: `scripts/create_promotion_packet.py`
- Verify: `shared-vault/`

- [ ] **Step 1: Run focused Python tests**

Run:

```bash
pytest \
  tests/src/test_paths.py \
  tests/unit/test_scoped_paths.py \
  tests/test_shared_vault_contract.py \
  tests/unit/test_vault_promotion.py \
  tests/scripts/test_create_promotion_packet.py \
  -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run runtime pollution guard**

Run:

```bash
pytest tests/test_vault_runtime_pollution.py -q
```

Expected: all tests pass, proving this foundation did not move runtime state into vault roots.

- [ ] **Step 3: Run whitespace check**

Run:

```bash
git diff --check
```

Expected: no output.

- [ ] **Step 4: Inspect status**

Run:

```bash
git status --short --branch
```

Expected: branch is ahead by the task commits and has no unstaged files.

- [ ] **Step 5: Report foundation completion**

The completion report should include:

- Path helper tests passed.
- Shared-vault scaffold tests passed.
- Promotion packet library and CLI tests passed.
- Runtime pollution guard passed.
- The branch status and latest commit hashes.
