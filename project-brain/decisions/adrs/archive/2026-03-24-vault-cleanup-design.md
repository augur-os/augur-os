# Vault Cleanup Design

**Date:** 2026-03-24
**Status:** Approved
**Approach:** Phased cleanup (B) with 30-day aggressive retention (A)

## Problem

The vault at `Au-vault/` has grown to ~3,371 content files. Many are system-generated ephemeral data, orphaned references, runtime state misplaced in version-controlled storage, duplicated memory entries, and stale scraped content. Target: reduce to ~1,600 files through 6 phases ordered by risk.

## Inventory

| Category | Files | % |
|---|---|---|
| Channels reviews (expiry items) | 480 | 14% |
| Memory (entries + system) | 496 | 15% |
| Attention (pending + root expiry) | 487 | 14% |
| Career (jobs, companies, notes) | 348 | 10% |
| Knowledge/RAG entries | 180 | 5% |
| Daemon (notifications, insights) | 138 | 4% |
| AI (demos, templates) | 130 | 4% |
| Other skill dirs (34 dirs) | ~1,112 | 33% |

**Other skill dirs breakdown (not targeted for cleanup — user content):**
lifestyle (64), venture-augur (63), scraper (59), apple (54), advisor (39), books (37), linkedin-writer (32), frontend (32), validator (31), growth (31), finance (28), content (27), devops (24), updater (15), health (15), + 19 dirs with ≤10 files each (~80).

## Key Findings

1. **Dead paths:** All 480 `channels/reviews/expiry-*.md` files reference `~/Projects/augur-data/vertical-work/careers/` — a path that no longer exists. No MCP tool resolves it. Additionally, 169 `attention/expiry-*.md` files in the attention root reference the same dead path.
2. **Memory duplication:** `memory/entries/` and `memory/system/` have 67 overlapping entries (same content, different frontmatter). The `system/` version is more complete (`written-by: augur-system` with slightly longer text).
3. **Career bloat:** 174 individual scraped job files in `career/job-analyzer/jobs/active/`. Ephemeral LinkedIn scrapes, not curated data.
4. **Runtime in vault:** Apple `_sync.yaml` files (18) and validator test captures (14) are runtime state, not user data.
5. **Seed duplicates:** Scraper YAML files with `_seeded: true` markers are exact copies of repo-side `assets/seeds/`.

## MCP Consumer Mapping

### Actively consumed vault paths (must preserve)

| Vault Path | MCP Tool | Dashboard Page |
|---|---|---|
| `dev/adrs/` | `unified-search`, `browse-index(vault)` | brain/ai/memory, brain/knowledge |
| `{skill}/notes/` | `list-skill-vault-notes` | Various skill pages |
| `apple/reminders/` | `file-read`, `file-list` | life/apple |
| `apple/notes-sync/` | `file-read`, `file-list` | life/apple |
| `page-builder/templates/` | `read-active-templates` | studio/page-builder |
| `memory/entries/` | `memory-search`, `unified-search` | brain/ai/memory |
| `memory/system/` | `memory-search` | brain/ai/memory |
| `attention/pending/` | `get-attention-items`, `get-attention-summary` | life/attention, AttentionBlock |
| `daemon/notifications/` | `get-daemon-notifications`, `manage-daemon-notifications` | DaemonNotificationsClient |
| `daemon/insights/` | `insights-pending` | FloatingChat badge |
| `career/notes/` | `list-skill-vault-notes` | career hub pages |

### Orphaned vault paths (safe to clean)

| Vault Path | Evidence |
|---|---|
| `channels/reviews/` | References dead `augur-data` path, no active MCP consumer |
| `attention/expiry-*.md` (root) | Same dead path references as channels, orphaned outside `pending/` |
| `validator/webapp-testing/*.json` | Timestamped test artifacts, no dashboard consumer |

### Consumed but regenerable (clean with dashboard impact warning)

| Vault Path | MCP Tool | Impact |
|---|---|---|
| `attention/pending/expiry-*` | `get-attention-items` | Attention dashboard temporarily empty until scanner re-populates |
| `daemon/notifications/history/*.md` | `manage-daemon-notifications` | Notification history cleared; new notifications unaffected |
| `daemon/insights/*.md` | None (tool reads `insights.yaml`, not individual `.md` files) | No impact — `.md` files are orphaned artifacts |

## Phases

### Phase 1 — System artifacts (zero risk)

Delete files with no consumer and no user value.

- **51** `.DS_Store` files — macOS cruft
- **8** `_index.cache.yaml` files — regenerated on next access
- **3** sparse seed YAMLs (≤5 lines, `_seeded: true`) — duplicate of repo-side `assets/seeds/`

**Reduction: ~62 files**

**Commands:**
```bash
# .DS_Store
find $VAULT -name '.DS_Store' -delete

# Cache files
find $VAULT -name '_index.cache.yaml' -delete

# Seeded stubs (verify each has _seeded: true before delete)
for f in $(grep -rl '_seeded: true' $VAULT --include='*.yaml'); do
  lines=$(wc -l < "$f")
  [ "$lines" -le 5 ] && rm "$f"
done
```

### Phase 2 — Dead references (zero risk)

All files reference the old `augur-data` path. No MCP tool resolves it.

- **480** `channels/reviews/expiry-*.md` — dead path references
- **169** `attention/expiry-*.md` (root, NOT `pending/`) — same dead path

**Reduction: ~649 files**

**Commands:**
```bash
# Channels
rm -rf $VAULT/channels/reviews/
mkdir -p $VAULT/channels/reviews  # preserve dir structure

# Attention root expiry files (NOT pending/)
rm $VAULT/attention/expiry-*.md
```

### Phase 3 — Ephemeral operational data (low risk)

System-generated items. Attention items are actively consumed — dashboard will be temporarily empty until scanner re-populates (~next scan cycle).

- **317** `attention/pending/expiry-*.md` — job-review suggestions (consumed by `get-attention-items`, regenerable)
- **~100** `daemon/notifications/history/*.md` — old notification history
- **30** `daemon/insights/*.md` — orphaned artifacts (MCP tool reads `insights.yaml`, not these)

**Dashboard impact:** Attention page temporarily empty. Daemon notifications history cleared.

**Reduction: ~447 files**

**Commands:**
```bash
# Attention pending (dashboard temporarily empty)
rm $VAULT/attention/pending/expiry-*.md

# Daemon notification history
rm $VAULT/daemon/notifications/history/*.md 2>/dev/null

# Daemon insight artifacts (NOT insights.yaml)
find $VAULT/daemon/insights -name '*.md' -not -name 'README*' -delete
```

### Phase 4 — Runtime state misplaced in vault (low risk)

Files that belong in the runtime directory (`~/Library/Application Support/Augur/state/`), not version-controlled vault.

- **18** `apple/reminders/*_sync.yaml` + `apple/notes-sync/*_sync.yaml` — sync snapshots
- **14** `validator/webapp-testing/*.json` — timestamped test captures

**Reduction: ~32 files**

**Commands:**
```bash
find $VAULT/apple -name '*_sync.yaml' -delete
rm $VAULT/validator/webapp-testing/capture_*.json $VAULT/validator/webapp-testing/ui_qa_*.json 2>/dev/null
```

### Phase 5 — Memory dedup + career stale data (medium risk)

**Memory dedup (67 files):** Where `entries/{client}_{name}.md` and `system/{name}.md` have the same content (after removing client prefix), delete the `entries/` copy. The `system/` version is canonical (more complete text, `written-by: augur-system`).

**Memory archive (~100 files):** `entries/` items from Feb with no `system/` counterpart — client-specific feedback never promoted to system. Archive rather than delete.

**Career jobs (174 files):** `career/job-analyzer/jobs/active/` scraped listings. Ephemeral LinkedIn data.

**Career companies (53 files):** `career/job-analyzer/companies/` stale profiles >30 days.

**Reduction: ~394 files**

**Commands:**
```bash
# Memory dedup: script compares entries/ vs system/ and removes matches
python3 scripts/vault_cleanup_phase5_memory.py

# Career jobs
rm -rf $VAULT/career/job-analyzer/jobs/active/
mkdir -p $VAULT/career/job-analyzer/jobs/active

# Career companies (all stale)
rm -rf $VAULT/career/job-analyzer/companies/
mkdir -p $VAULT/career/job-analyzer/companies
```

### Phase 6 — Deep pruning (medium-high risk)

**Note:** `career/notes/` is excluded — contains user-created technical knowledge (hardware engineering notes like imcv2-system, SPI/I2C bringup), not ephemeral interview notes.

| Target | Count | Action |
|---|---|---|
| `memory/system/` Feb entries (>30d) | ~150 | Delete — stale agent feedback |
| `knowledge/rag/entries/` | 169 | Delete — regenerable via `/auto-rag-reindex` |
| `scraper/entries/` + `scraper/content/` old | ~30 | Delete stale scrape output |
| `daemon/` remaining empty config | ~4 | Delete empty placeholder files |
| `ai/demo/playbooks/` unused presets | ~50 | Keep 10-15 core, delete rest |

**Reduction: ~403 files**

**Commands:**
```bash
# Memory system Feb entries
python3 scripts/vault_cleanup_phase6_memory.py  # filters by created: date

# Knowledge RAG (regenerable)
rm -rf $VAULT/knowledge/rag/entries/
mkdir -p $VAULT/knowledge/rag/entries

# Scraper stale
rm $VAULT/scraper/entries/*.md 2>/dev/null
# Keep scraper/content/ items < 30 days

# AI demo presets (keep core, archive rest)
python3 scripts/vault_cleanup_phase6_ai.py
```

## MCP Verification Protocol

After each phase commit, run:

1. `vault-status` — confirm no broken references
2. `browse-index category=vault` — confirm RAG indexes resolve
3. `list-skill-vault-notes` for skills with notes/ — verify notes still accessible
4. `get-attention-items` + `get-attention-summary` — verify attention tools respond (empty OK after Phase 3)
5. `insights-pending` + `get-daemon-notifications` — verify daemon tools respond
6. Spot-check dashboard pages: career hub, knowledge hub, attention hub, life/apple

**Failure recovery:** Each phase is a separate git commit in the vault repo. If MCP verification fails, `git revert HEAD` restores the phase.

## Projected Outcome

| Phase | Removed | Running Total | Risk |
|---|---|---|---|
| 1 — System artifacts | 62 | 3,309 | Zero |
| 2 — Dead references | 649 | 2,660 | Zero |
| 3 — Ephemeral ops | 447 | 2,213 | Low |
| 4 — Runtime state | 32 | 2,181 | Low |
| 5 — Memory dedup + career | 394 | 1,787 | Medium |
| 6 — Deep pruning | 403 | 1,384 | Medium-high |
| **Total** | **1,987** | **~1,384** | |

## Post-Cleanup

After reaching ~1,400 files, consider adding a retention daemon rule (auto-vault-hygiene) to prevent re-accumulation:
- 30-day TTL on `attention/pending/expiry-*`, `channels/reviews/expiry-*`, `daemon/notifications/history/`
- Block `_sync.yaml` writes to vault (redirect to runtime dir)
- Weekly memory dedup scan
