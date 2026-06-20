# File Manager Consolidation & Evolution

**Date:** 2026-03-25
**Status:** Draft
**Scope:** Skill consolidation (file-manager + organizer), rules engine, autoloop, dashboard, MCP tools, skill discovery pipeline

## Problem

Three overlapping skills handle file-related tasks — `file-manager` (D tier, 28.8), `organizer` (D tier, 34.2), and `system-cleanup` (C tier, 38.5). The first two share the same hub (life), same tab (home), and overlapping concerns (file intelligence, browsing, organization). Neither is functional. ADR-111 defines an aspirational vision for organizer that was never implemented.

`system-cleanup` stays separate — it lives in the command hub and handles disk hygiene (caches, trash, dev artifacts), which is a fundamentally different user intent.

## Design

### 1. Skill Consolidation

`file-manager` becomes the surviving skill, absorbing organizer's vision and assets. `organizer` is deleted entirely (no backward-compat stubs per rule 14).

**Migrated from organizer:**
- `organizer/assets/seeds/*` → `file-manager/assets/seeds/`
- Useful test stubs from `organizer/augur/tests/` → `file-manager/augur/tests/`
- Note: `organizer/augur/modules/organization.md` is a stub with no implementation — not worth migrating. The rules engine (Section 2) replaces it entirely.
- Note: `organizer/augur/seed/` contains legacy seed data (`example-organizer.yaml`) — review before deletion, do not migrate (superseded by new rules engine).

**Deleted:**
- `skills/organizer/` entire directory
- `skills/dashboard/pages/life/organizer/` — generated dashboard pages (lives outside `skills/organizer/`, must be deleted separately)
- Any route mounts referencing organizer paths (`/productivity/organizer`, `/productivity/organize`, `/productivity/duplicates`, `/productivity/cleanup`)

**Cleaned up:**
- Remove legacy `file-manager/augur/seed/` directory (violates rule 19 — seeds belong in `assets/seeds/`)

**Updated:**
- file-manager SKILL.md — new description, `x-augur-file-intake` spec, expanded MCP tools list
- Skill type becomes `domain` (high-capability)
- New ADR supersedes ADR-111 and ADR-220

### 2. Rules Engine — Triage-First Decision Tree

The core intelligence. All three consumption modes (dashboard action, autoloop, Cowork client) share this engine. The MCP tools provide data and execution — the AI client (IDE agent or external) makes the decisions.

**Path resolution:** Throughout this spec, file destinations use `paths.py` functions:
- Valuable files route to `get_skill_documents_dir(skill_name)` — e.g., health files → `get_skill_documents_dir("health")`
- Archive files go to `get_skill_documents_dir("file-manager") / "archive"`
- Pending files go to `get_skill_documents_dir("file-manager") / "pending" / topic`
- User rules and history stored in `get_skill_vault_dir("file-manager")` (user-editable config data)

**Decision tree — evaluated for each input:**

```
Input (folder or file)
  │
  ├─ Is input a folder?
  │   YES → Folder-level triage first
  │   │   Assess folder name, contents sample, structure
  │   │   Route entire folder to domain if clear match
  │   │   Then file-level passes within for sub-folder mapping
  │   NO → File-level triage directly
  │
  ├─ Step 1: Triage — Valuable/actionable or low-value?
  │
  ├─ Step 2: Domain routing — Match to existing skill?
  │   ├─ MATCH → Route to get_skill_documents_dir(skill)/
  │   └─ NO MATCH but valuable → Step 2b: Skill discovery
  │       │  No existing skill covers this content
  │       │  → Attention inbox: suggest new skill
  │       │  → User approves → triggers /evolve pipeline
  │       │  → Files parked in get_skill_documents_dir("file-manager")/pending/{topic}/
  │
  ├─ Step 3: Sub-folder mapping by content within the skill domain
  │
  ├─ Step 4: Archive fallback — Low-value files
  │   │  Goes to get_skill_documents_dir("file-manager")/archive/
  │   └─ Sorted by extension/date/size heuristics
  │
  └─ Step 5: Action detection — Does this file need a follow-up?
      │  PDF report → create reading-list reminder
      │  Invoice with due date → create finance reminder
      │  Signed contract → flag for career/venture review
      └─ Routes to attention inbox with suggested action
```

**Folder-level triage:** Before analyzing individual files, assess the folder as a whole. A folder named `Medical_Records_2026` gets routed to health as a unit. Much faster than file-by-file for bulk organization.

**Domain map — decentralized via skill frontmatter:**

Each skill that accepts documents declares its intake in SKILL.md:
```yaml
x-augur-file-intake:
  accepts: ["medical records", "lab results", "insurance docs"]
  folder: health
  subfolders: [labs, insurance, prescriptions, records]
```

The `get-domain-map` MCP tool assembles these declarations at runtime. No centralized registry.

**File actions include rename + move as atomic operations:**

```python
@dataclass
class FileAction:
    source_path: str          # original location
    new_name: str | None      # rename (None = keep original name)
    destination: str          # target folder
    action: str               # "move" | "archive" | "pending"
    reason: str               # AI's reasoning
    skill_target: str | None  # which skill domain, if matched
```

### 3. MCP Tools

| Tool | Purpose | Called by |
|------|---------|----------|
| `scan-folder` | Analyze a folder/file, return metadata + content sample for AI triage | IDE agent, Cowork client |
| `get-domain-map` | Return all skills with `x-augur-file-intake` declarations | IDE agent, Cowork client |
| `get-rules` | Return user's rules config (overrides + defaults) | IDE agent, autoloop |
| `update-rules` | User edits/adds organization rules | Dashboard, Cowork client |
| `apply-file-actions` | Execute a plan (rename + move), trigger RAG reindex on affected folders | IDE agent, autoloop |
| `get-pending` | List files in pending/{topic}/ awaiting skill creation | Dashboard, attention |
| `get-archive` | Browse/search archive folder | Dashboard |
| `get-file-history` | Audit trail of past moves/renames | Dashboard |

**Key principle:** Tools are the rules + file ops layer, not the decision layer. The AI client makes triage decisions using data from `scan-folder` and `get-domain-map`.

**RAG reindex:** After `apply-file-actions` completes, it triggers `knowledge-project-index-rebuild` scoped to the affected skill folders. Files routed to `get_skill_documents_dir("health")/` → reindex health's RAG. No new infrastructure needed.

**Audit trail:** Every `apply-file-actions` call logs to `get_skill_vault_dir("file-manager")/history.yaml` — what moved, where, when, which AI decision, which source. Enables undo and trust scoring.

### 4. Autoloop

Nightly autoloop runs the same rules engine with progressive difficulty and trust-aware approval.

**Difficulty levels:**

| Level | Behavior | Approval |
|-------|----------|----------|
| d0 | Scan watched folders, report findings | None — info item in attention inbox |
| d1 | Apply renames on high-confidence matches | Auto-apply if trust allows, otherwise attention inbox |
| d2 | Rename + move files to skill domains | Trust-gated |
| d3 | Full triage: archive routing + action detection (reminders, tasks) | Trust-gated |
| d4 | Skill discovery suggestions for unmatched valuable content | Always attention inbox (new skill = always needs human) |

**Watched folders:** Configurable in `get_skill_vault_dir("file-manager")/rules.yaml`. Defaults: `~/Downloads`, `~/Desktop`, `~/Documents/Inbox`.

**Trust escalation:**
- Starts at low trust (d0-d1 only, everything needs approval)
- Approval history tracked in `get_skill_vault_dir("file-manager")/history.yaml`
- Consecutive approved actions without rejection → trust level increases
- User rejection resets trust for that action type
- Low trust: only renames with confidence > 0.9 auto-apply
- Medium trust: moves with confidence > 0.8 auto-apply
- High trust: all actions with confidence > 0.6 auto-apply

**Attention inbox integration (pilot pattern):**
- Autoloop calls `raise_attention()` from `channels.augur.lib.registry` to create attention items
- Item includes: file name, proposed action (rename + destination), reasoning, and a `callback` field containing the serialized `FileAction` list
- User approve/deny/defer from inbox
- On approval, the attention skill's `act-on-attention-item` handler checks `source_type == "file-action"` and calls `apply-file-actions` MCP tool with the stored callback payload
- This requires extending the attention skill: (1) add `"file-action"` to `raise_attention()` accepted `source_type` values, (2) add `"file-action"` to `source_weights` in `triage.py`, (3) add a dispatch branch in `act_on_attention_item` for `source_type == "file-action"` that calls `apply-file-actions` with the stored callback payload. This is the pilot for universal autoloop-to-attention-inbox pattern (separate ADR later)

**`x-augur-loop` frontmatter** (added to file-manager SKILL.md):
```yaml
x-augur-loop:
  name: file-organizer
  tier: 1
  trigger: nightly
  config:
    max_difficulty: 4
    trust_aware: true
    attention_source_type: file-action
```

### 5. Dashboard

Two tabs in the life hub.

**Tab 1: Browse** (replaces existing "Explorer" tab)
- New file browser component (the existing page builds an inline FileTree + FileEditor — these will be refactored into a reusable block)
- Folder intelligence (replaces existing "Intelligence" tab — merged into Browse as a panel rather than a separate tab)
- Drag-and-drop — drop folder/file to trigger organization action
- History view — audit trail with undo

**Tab 2: Organize** (new)
- Watched folders list with status (last scan, pending count, trust level)
- Rules editor — view/edit/add organization rules
- Pending queue — files awaiting skill creation decisions
- Archive browser — search and retrieve archived files

**Attention inbox items (rendered in existing attention skill):**
- File action approvals: "Rename `IVC.pdf` → `2026-03-invoice-report.pdf`, move to `finance/invoices/`" [Approve] [Deny]
- Skill discovery: "Found car maintenance content — suggest `car-maintenance` skill?" [Create] [Archive] [Ignore]
- Action triggers: "Found `IVC.pdf` — add to reading list?" [Yes] [No]
- Nightly summary: "Organized 12 files, 3 need review" [Review]

### 6. Mode 2 — External Client (Cowork / Claude Code / Codex)

Any MCP-capable client can organize files using the same tools.

**Flow:**
1. Client calls `get-domain-map` → gets all skill intake declarations
2. Client calls `scan-folder` → gets file metadata + content samples
3. Client's LLM makes triage decisions (valuable vs archive, domain routing, renames)
4. Client calls `apply-file-actions` with the plan
5. MCP tool executes, triggers RAG reindex, logs to history

**`get-domain-map` response** (paths resolved at runtime via `get_skill_documents_dir()`):
```json
{
  "skills": [
    {"name": "health", "documents_dir": "/Users/x/Documents/Augur/health", "accepts": ["medical records", "lab results"], "subfolders": ["labs", "insurance"]},
    {"name": "finance", "documents_dir": "/Users/x/Documents/Augur/finance", "accepts": ["invoices", "tax docs", "receipts"], "subfolders": ["tax", "invoices"]}
  ],
  "archive_path": "/Users/x/Documents/Augur/file-manager/archive",
  "pending_path": "/Users/x/Documents/Augur/file-manager/pending"
}
```

No special client integration needed. The intelligence is in the client, the rules and execution are in the tools.

### 7. Skill Discovery Pipeline

When triage finds valuable content with no matching skill domain.

**Flow:**
1. Files parked in `get_skill_documents_dir("file-manager")/pending/{topic}/`
2. Attention inbox item: "Found content about `{topic}` — no matching skill exists"
3. User options:
   - **Create skill** → triggers `/evolve` with context (files become seed data)
   - **Route to existing skill** → user picks a skill, system learns the mapping
   - **Archive** → moves to archive
   - **Ignore** → stays in pending, resurfaces if more content arrives
4. When `/evolve` completes and the new skill exists (detected by the nightly autoloop checking for new `x-augur-file-intake` declarations that match pending topics), the autoloop calls `apply-file-actions` to move pending files to the new skill's documents folder. This is not a synchronous callback — the autoloop polls for resolution on its next run.
5. New skill's `x-augur-file-intake` declaration routes future files automatically

**Learning loop:** Repeated manual routing of a topic to a skill triggers a suggestion to add that mapping to the skill's `x-augur-file-intake`.

## Implementation Order (Approach A: Rules-First)

1. **Consolidate skills** — migrate organizer seeds/tests to file-manager, delete `skills/organizer/` and `skills/dashboard/pages/life/organizer/`, clean up legacy `file-manager/augur/seed/`, update SKILL.md with `x-augur-loop` frontmatter
2. **Build rules engine** — Python, triage decision tree, FileAction struct
3. **Wire MCP tools** — scan-folder, get-domain-map, apply-file-actions, get-rules, update-rules, get-pending, get-archive, get-file-history
4. **Extend attention skill** — add `source_type: "file-action"` handler with cross-skill callback to `apply-file-actions`
5. **Build autoloop** — d0-d4, trust-aware, attention inbox via `raise_attention()`, pending topic resolution on nightly scan
6. **Build dashboard** — Browse tab (refactor existing FileTree/FileEditor into reusable block, merge Intelligence panel) + Organize tab
7. **Add `x-augur-file-intake`** to existing skills (health, finance, career, etc.)
8. **Skill discovery pipeline** — pending flow, /evolve integration (async — autoloop polls for new skill intake declarations)

## Supersedes

- ADR-111: Organizer Hub Hardening
- ADR-220: Files Hardening
