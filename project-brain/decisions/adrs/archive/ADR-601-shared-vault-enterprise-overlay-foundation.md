---
status: Implemented
date: 2026-05-03
deciders:
  - Gur Sannikov
related: []
hub: null
tags: []
superseded_by: null
---

# ADR-601: Shared Vault Enterprise Overlay Foundation

## Context

Augur needs one model that works for personal use and for an initial enterprise deployment to a team of roughly 40 engineers across roles (developer, architect, validation, DevOps, product, manager). The target is a local-first project repo that contains both the deployable Augur product and a shared team brain, plus one private vault per user. The same vault structure is used in both places — the difference is ownership and write policy, not folder semantics.

This foundation lands the first two phases of the larger shared-vault enterprise overlay design: path helpers and promotion packets. Browse merging, wiki compiler integration, and repo-root `skills/` retirement are out of scope here because they touch independent runtime and UI surfaces.

The foundation must keep shared-vault paths explicit, keep private-vault writes as the default, and write promotion payloads as new packet folders under `shared-vault/inbox/promotions/`.

## Decision

Land four sequential, focused commits:

1. **Path helpers** in `src/config/paths.py`: `get_shared_vault_dir`, `get_shared_vault_inbox_dir`, `get_shared_vault_promotions_dir`, `get_shared_vault_notes_dir`, `get_shared_vault_sources_dir`, `get_shared_wiki_dir`, `get_shared_vault_skills_dir`, `get_shared_vault_drafts_dir`, `get_shared_vault_archive_dir`, `get_shared_vault_config_dir`. Plus private-vault aliases (`get_private_vault_dir`, `get_private_vault_skills_dir`, `get_private_wiki_dir`) and `get_vault_source_roots()` that returns shared then private in read-precedence order. `AUGUR_SHARED_VAULT` env override is supported.
2. **Repo-tracked `shared-vault/` scaffold**: `README.md`, `inbox/`, `notes/` (with `roles/`), `sources/`, `wiki/`, `skills/`, `drafts/`, `archive/`, `config/`. Each README has YAML frontmatter (`vault_scope: shared`, `status: active|inactive`). The root README documents that repo-root `skills/` is retired in the final architecture.
3. **`src/lib/vault_promotion.py`**: `PromotionPacketRequest` and `PromotionPacket` dataclasses plus `create_promotion_packet(shared_vault_dir, request)`. Packets are append-only folders named `{date}-{contributor-slug}-{topic-slug}` under `shared-vault/inbox/promotions/`, containing `manifest.yaml` (with source SHA-256 hashes), `synthesis.md`, `proposed-actions.md`, `proposed-links.md`, and a `sources/` subfolder. Topic/contributor are required; a numeric suffix avoids collisions.
4. **CLI wrapper**: `scripts/create_promotion_packet.py` exposes the library through argparse with `--topic`, `--contributor`, `--synthesis` or `--synthesis-file`, plus optional `--source`, `--action`, `--link`, `--role`, `--domain`, `--sensitivity`, `--date`.

Validation is enforced through tests: path resolution, scaffold contract (frontmatter, required scope), append-only packet behavior, unique-suffix on collision, empty-topic/contributor rejection, and CLI smoke.

## Consequences

### Positive
- Path helpers make shared-vault paths explicit and overridable via env.
- The repo ships a tracked, documented `shared-vault/` skeleton; new clones get the team brain root automatically.
- Promotion packets give contributors an append-only, PR-friendly path for shared updates without editing canonical files.
- Sensitivity, source provenance (paths plus hashes), roles, and domains are recorded in the manifest for downstream compilers.

### Negative
- Adds new path API surface; consumers must opt in (overlay, Browse, wiki compiler) before user-facing features change.
- Runtime/cache/log helpers must remain outside vault roots; future scanners need to keep enforcing this.

### Neutral
- This foundation does not retire repo-root `skills/`, does not migrate Browse, and does not integrate accepted packets — those are separate ADRs/plans.

## Alternatives Considered

### Alternative 1: Direct shared writes (PR edits canonical wiki/notes/skills)
Rejected. With 40+ engineers, PR conflict pressure on canonical shared files is unworkable. Append-only packets keep PRs additive and reviewable in isolation.

### Alternative 2: Hosted shared service first
Rejected. Local-first proves the model with Git as the sync layer before adding server-side auth, multitenancy, or central indexing.

### Alternative 3: Folder-per-role hierarchy in `shared-vault/notes/roles/`
Rejected. Roles are metadata and views, not top-level folders. Only role playbook entrypoints live in `notes/roles/`; physical organization stays by content type.

## References
- Plan: docs/superpowers/plans/2026-05-03-shared-vault-enterprise-overlay-foundation.md
- Spec: docs/superpowers/specs/2026-05-03-shared-vault-enterprise-overlay-design.md
