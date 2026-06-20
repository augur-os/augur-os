---
title: email-drop-ingest-routes-personal-emails-to-shared-vault-scope
name: email-drop-ingest-routes-personal-emails-to-shared-vault-scope
description: Background email ingest (likely Cowork or antigravity, exact writer unknown)
  wrote a personal Claude-subscription email to shared-vault/notes/ instead of the
  user's private vault (~/Projects/Au-vault/notes/). Routing logic should default
  email-drop to private scope unless explicitly opted into shared.
brain_scope: project
type: project
status: active
source_client: claude-code
source_file: project_email_drop_routes_to_shared_scope.md
source_hash: 3d7260bcaa52b711
---


**Symptom (2026-05-18):** during `/dev-merge full` inspection, found
`shared-vault/notes/2026-05-18-email-agent-sdk-credit.md` — an email
from Claude Team about Agent SDK monthly credits, with frontmatter
`source_type: email`, `x-augur-note-type: email`, `tags: [email]`,
`captured_at: 2026-05-18T00:00:00Z`. File mtime was 00:48 same day, no
matching entry in code-repo git history (untracked when found).

The RAG indexer already pulled it in at
`~/Library/Application Support/Augur/rag/vault/notes/shared/2026-05-18-email-agent-sdk-credit.md`
with `vault_scope: shared` — exactly the wrong scope for a personal email.

**Why this matters:** ADR-490 vault overlays distinguish `shared`
(team-readable, lives in code repo at `shared-vault/`) from `private`
(user-only, lives in `~/Projects/Au-vault/`). Personal emails belong
in private. A shared-scope email leaks into commits and is visible to
anyone with code-repo access.

**Investigation done:**
- `shared-vault/notes/` IS a legitimate scope target (per
  `src/config/paths.py:523 get_shared_vault_notes_dir`).
- Nothing in `src/` or `shared-vault/skills/ingest/` writes per-email
  cards to `shared-vault/notes/` — `email_drop_consume.py` writes
  packet bodies to `<vault>/sources/extracted/`, not `<vault>/notes/`.
- No matching entry in `~/Library/Logs/Augur/augur_mcp.log`,
  `dashboard.stdout.log`, or any `state/jobs/*/events.jsonl`.
- Filename pattern `YYYY-MM-DD-<type>-<slug>.md` matches the Augur
  convention, so the writer is Augur-aware (not random file drop).

**Most likely writer:** a non-Augur-MCP path — Claude Cowork (Desktop)
or antigravity background ingest with its own path resolution that
defaults to `shared-vault/notes/`. Neither's logs are in
`~/Library/Logs/Augur/`.

**Recovery taken:** moved the file to
`~/Projects/Au-vault/notes/2026-05-18-email-agent-sdk-credit.md`
(committed as part of the next `/dev-merge full`).

**How to apply (next time you see one):**
1. Move the file: `mv shared-vault/notes/<file> ~/Projects/Au-vault/notes/<file>`
2. The stale `rag/vault/notes/shared/<file>` index entry self-cleans on
   next reindex.
3. To pin the writer: ingest another email through whatever flow you
   normally use, and `fswatch -1 shared-vault/notes/` to catch the
   write in real time.

**Open task:** instrument email-drop with a writer-trace (process PID +
caller stack at write time), OR — better — change the default
destination of any `x-augur-note-type: email` write to private vault
unless an explicit `--shared` flag is set. See task #29 (logged).
