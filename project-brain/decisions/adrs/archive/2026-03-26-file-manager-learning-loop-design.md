# File Manager Learning Loop — Confidence Scoring, Pending UX, Autoloop Intelligence

**Date:** 2026-03-26
**Status:** Draft
**Scope:** Autoloop enhancement, confidence scoring engine, decision learning loop, pending queue dashboard UX, system LLM CLI config
**ADR:** ADR-517 (extends), ADR-518 (consumes)
**Depends on:** file-manager consolidation (done), document-extractor skill (done)

## Problem

The file-manager triage currently uses keyword matching against `x-augur-file-intake` declarations — a static, brittle approach. Of 30 Desktop files tested, 9 remained "pending" because the system couldn't confidently route them. Hebrew PDFs with garbled text extraction, files with no matching keywords, and images without OCR text all end up in a black hole. Users have no way to review pending files efficiently or teach the system their preferences.

## Design

### 1. Confidence Scoring Engine

Pure pattern matching against past decisions — no LLM needed, fast, offline, deterministic.

**Signal extraction per file:**

| Signal | How extracted | Weight |
|--------|-------------|--------|
| `filename_keywords` | Split filename on delimiters, drop stopwords | 0.15 |
| `content_keywords` | Top 10 frequent meaningful words from extracted text | 0.35 |
| `extension` | File extension | 0.10 |
| `source_folder` | Parent directory path | 0.10 |
| `size_range` | Bucketed: tiny(<1K), small(1-10K), medium(10-100K), large(>100K) | 0.05 |
| `past_decisions` | How many past decisions with similar signals routed to same skill | 0.25 |

**Scoring algorithm:**

```
For each skill in domain map:
  score = 0
  - filename keywords: (matched / total_keywords) * 0.15
  - content keywords: (matched / total_keywords) * 0.35
  - extension matches past decisions for this skill → +0.10 (binary)
  - source_folder matches past decisions → +0.10 (binary)
  - size_range matches → +0.05 (binary)
  - N past decisions with similar signals → this skill: +0.25 * (N / (N + 5))

Best skill = highest score
Confidence = best_score (already in [0, ~0.95] range — theoretical max is
unreachable due to the N/(N+5) saturation curve, practical ceiling ~0.95)
```

Note: `filename_keywords` and `content_keywords` use **proportional overlap** (fraction of keywords that match), not binary. This means a file with 3/10 content keywords matching health gets `0.35 * 0.3 = 0.105`, while 8/10 matching gets `0.35 * 0.8 = 0.28`.

**Cold start (0 decisions):** Only `filename_keywords` and `extension` can match against static `x-augur-file-intake` declarations. Max possible score ~0.25. Everything goes to pending until user decisions build the pattern base. This is intentional — the system learns from the user, not from assumptions.

**Trust-adaptive thresholds** (existing TrustLevel from rules_engine.py):

| Trust Level | Auto-route threshold | How to reach |
|-------------|---------------------|--------------|
| Low (initial) | >= 0.9 | Default |
| Medium | >= 0.8 | 10+ consecutive approvals |
| High | >= 0.6 | 20+ consecutive approvals |

User rejection resets trust for that signal pattern.

**Convergence over time:**

| Decisions | Behavior |
|-----------|----------|
| 0 (fresh) | Everything to pending. Only x-augur-file-intake keyword matches contribute. |
| 5-10 | Common patterns start auto-routing. "מנורה" → health scores 0.7+. |
| 20+ | Most recurring file types auto-route. Pending queue shrinks to genuinely novel files. |

### 2. Decision Storage

Flat YAML at `get_skill_vault_dir("file-manager")/decisions.yaml`:

```yaml
- file: מנורה.pdf
  routed_to: health
  signals:
    filename_keywords: [מנורה]
    content_keywords: [ביטוח, בריאות, תביעות, פוליסה, מבטחים]
    extension: .pdf
    source_folder: ~/Desktop
    size_range: 1k-10k
  confidence_at_decision: 0.45
  user_override: true
  timestamp: 2026-03-26T10:00:00
```

Machine config, not user-facing — YAML, not frontmatter markdown.

**Growth management:** When `decisions.yaml` exceeds 500 entries, the autoloop compacts it: group decisions by `(routed_to, extension, source_folder)`, merge signal keyword sets, keep the most recent timestamp and a `count` field. This reduces 500 individual decisions to ~50-100 aggregated patterns. The compact operation runs once per autoloop scan before scoring. Raw decisions older than 90 days are eligible for compaction.

### 3. Enhanced Nightly Autoloop

The existing d0-d4 autoloop in `autoloop.py` gets enhanced:

**d0 (scan + report) — enhanced:**
1. Scan watched folders (existing)
2. Extract content via document-extractor (tier 0 + Tesseract tier 0.5)
3. Compute confidence scores against `decisions.yaml` (no LLM)
4. Score and classify each file (but do NOT auto-route at d0 — d0 is report-only):
   - `confidence >= trust_threshold` → flagged as "auto-routable at d1+"
   - `confidence >= 0.4` but below threshold → pending WITH suggestion
   - `confidence < 0.4` → pending WITHOUT suggestion
5. Spawn CLI agent session for summary generation (pending + auto-routable files):
   - Uses system LLM CLI config (`get_vault_dir()/config/llm_cli.yaml`)
   - Batch prompt: "Generate a one-line summary for each file" with filename + content (500 chars each)
   - Prompt template: `"For each file below, write a one-line summary (under 100 chars) describing what the document is about.\n\n{files_block}"` where files_block is `"File: {filename}\nContent: {content[:500]}\n---"` per file. Parse response by splitting on file boundaries.
   - If no CLI available → skip summaries, use first 100 chars of extracted text as fallback
6. Write pending files with metadata via `save-pending-files` tool
7. Check if old pending files now score higher (pending resolution)
8. Report to attention inbox: "Scanned N files, X auto-routable, Y need review, Z failed"

**Note on d0 vs d1+:** d0 prepares the data (scores, summaries, pending metadata). d1+ performs the actual auto-routing based on this data. This preserves the existing `should_auto_apply()` contract where d0 always returns False.

**d1-d3 (auto-route with trust gating) — wired:**
- d1: Auto-route where confidence >= trust threshold, action is "move to existing skill"
- d2: Same + archive routing for low-value files
- d3: Same + action detection (invoice with due date → finance reminder)

**d4 (skill discovery) — unchanged.**

**CLI agent session for summaries:**

When called from nightly autoloop (no AI client in context), uses the LLM-Assisted MCP pattern:

```
autoloop detects no AI client in context
  → reads get_vault_dir()/config/llm_cli.yaml
  → tries preferred CLI: claude --print --prompt "Summarize these files..."
  → if unavailable, tries fallback: ollama run llama3 "Summarize..."
  → if neither available: no summaries, raw text snippet used instead
```

When called from Claude Code session (user says "organize my desktop"):

```
Claude IS the LLM
  → reads file content directly
  → generates summaries inline
  → makes routing decisions with full context
  → calls route-pending-file or apply-file-actions directly
```

### 4. MCP Tools

**New tools (file-manager skill):**

| Tool | Purpose | Args |
|------|---------|------|
| `save-pending-files` | Write files to pending queue with rich metadata | `files_json`: array of {path, summary, confidence, suggested_skill, signals} |
| `get-pending-detailed` | Return pending files with summaries, confidence, suggested skill | `limit`: int |
| `route-pending-file` | User approves routing → move file + record decision | `pending_id`, `target_skill`, `override`: bool (user changed suggestion) |
| `get-routing-confidence` | Compute confidence for a single file (used by AI clients for real-time triage and by dashboard for "test a file" feature) | `path`: file path |

**Deprecated:**
| Tool | Replaced by | Migration |
|------|------------|-----------|
| `get-pending` | `get-pending-detailed` | Existing Organize tab dashboard page uses `get-pending` — update to `get-pending-detailed` in the dashboard task |

**Pending file lifecycle:**

Original files stay in place (e.g., on Desktop) during the pending phase — they are NOT moved. The pending metadata YAML tracks them by `source_path`. Deduplication: before writing a new pending entry, check if a pending file with the same `source_path` already exists. If so, update the existing entry (refreshed confidence, updated summary) rather than creating a duplicate. The nightly scan skips files that already have a pending entry.

When the user approves routing via `route-pending-file`, the file is moved from its original location to the target skill's documents dir, and the pending YAML metadata is deleted.

**Pending ID format:** `pending-{YYYYMMDD}-{HHMMSS}-{slug(filename)[:30]}` — timestamp prevents collisions between files with the same slugified name on different days.

**`save-pending-files` writes to** `get_skill_documents_dir("file-manager")/pending/{id}.yaml`:

```yaml
id: pending-20260326-menora
source_path: /Users/x/Desktop/מנורה.pdf
filename: מנורה.pdf
summary: "Insurance claims document from Menora Mivtachim, health department"
content_preview: "תואירב תועיבת | תקלחמ | maccabi-shirut@menoramivt..."
confidence: 0.72
suggested_skill: health
signals:
  filename_keywords: [מנורה]
  content_keywords: [ביטוח, בריאות, תביעות]
  extension: .pdf
  source_folder: ~/Desktop
  size_range: 1k-10k
created_at: 2026-03-26T02:00:00
```

**`get-pending-detailed` response shape:**

```json
{
  "success": true,
  "files": [
    {
      "id": "pending-20260326-menora",
      "filename": "מנורה.pdf",
      "source_path": "/Users/x/Desktop/מנורה.pdf",
      "summary": "Insurance claims document from Menora Mivtachim, health department",
      "content_preview": "תואירב תועיבת | תקלחמ...",
      "confidence": 0.72,
      "suggested_skill": "health",
      "size_bytes": 4188,
      "extension": ".pdf",
      "created_at": "2026-03-26T02:00:00"
    }
  ],
  "total": 9,
  "skills": ["health", "finance", "wealth", "career", "reading-list", "archive"]
}
```

**`route-pending-file` flow:**

1. Load pending file metadata
2. Execute move via `apply-file-actions` (source → `get_skill_documents_dir(target_skill)`)
3. Extract signals from file
4. Append decision to `decisions.yaml` with `user_override: true/false`
5. Update trust level (approval if suggestion accepted, rejection if overridden)
6. Delete pending file metadata
7. Return success + new trust level

### 5. Dashboard — Organize Tab Pending Section

The existing Organize tab's pending section is redesigned. Card list UX:

**Per-file card:**
- AI summary headline (blue text)
- Expandable raw extracted text (`<details>` element)
- Confidence badge: green (0.7+), amber (0.4-0.7), red (<0.4)
- Skill dropdown populated from `get-domain-map` response + "archive" option
- Pre-selected to `suggested_skill` if confidence >= 0.4
- Approve button (green checkmark) → calls `route-pending-file`
- Skip button → file stays in pending

**Batch actions:**
- "Approve All Suggestions" button — routes all files with confidence >= 0.4 to their suggested skill

**Status indicators (in watched folders section):**
- Decision count: "47 decisions learned"
- Trust level: "Trust: medium (auto-routes above 0.8)"

**Data flow:**
- `useMcpQuery('pending-detailed', 'get-pending-detailed')` → populates card list
- `useMcpQuery('domain-map', 'get-domain-map')` → populates skill dropdowns
- `useMcpMutation` on `route-pending-file` → approve action
- Invalidate `pending-detailed` query after each route

### 6. System-Level LLM CLI Config

**Location:** `get_vault_dir()/config/llm_cli.yaml`

**Decentralization note:** This is a deliberate exception to rule 2 (plugin decentralization). "Which CLI agent to spawn" is a system-wide user preference consumed by multiple skills (document-extractor, file-manager, future skills). It doesn't belong to any one skill — it's analogous to `project.yaml` or other system config. The shared loader at `src/lib/` follows the same pattern as `src/lib/frontmatter_utils.py`.

```yaml
preferred: claude
fallback: ollama
ollama_model: llama3        # text model for summaries
ollama_vision_model: llava  # vision model for OCR
timeout: 120
```

**Shared loader:** `src/lib/llm_cli.py`

```python
def get_llm_cli_config() -> dict:
    """Load system-level LLM CLI config."""

def spawn_cli_prompt(prompt: str, timeout: int | None = None) -> str | None:
    """Spawn preferred CLI with prompt, return output.
    Resolution: preferred → fallback → None.
    """

def get_preferred_cli() -> str | None:
    """Return name of available CLI ('claude', 'ollama', or None)."""
```

**Consumers:**
- `document-extractor/scripts/extractor.py` → replaces `_load_cli_config()`, uses `spawn_cli_prompt()` for OCR
- `file-manager/scripts/autoloop.py` → uses `spawn_cli_prompt()` for summary generation

**Migration:** Delete `_load_cli_config()` from `extractor.py`, delete vault config at `get_skill_vault_dir("document-extractor")/config.yaml` (the one created earlier for llm_cli).

## Implementation Order

1. **Confidence scoring engine** — `skills/file-manager/scripts/confidence.py` with signal extraction and scoring algorithm
2. **Decision storage** — load/save/append functions for `decisions.yaml`
3. **System LLM CLI config** — `src/lib/llm_cli.py` with shared loader + spawner
4. **Migrate document-extractor** — replace `_load_cli_config()` with shared `get_llm_cli_config()`
5. **New MCP tools** — `save-pending-files`, `get-pending-detailed`, `route-pending-file`, `get-routing-confidence`
6. **Autoloop enhancement** — wire confidence scoring + CLI summary generation into d0 scan
7. **Dashboard Organize tab** — redesign pending section with card list UX
8. **Verification** — end-to-end test on Desktop files, verify learning loop
