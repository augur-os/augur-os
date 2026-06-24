---
name: inbox-triage
x-augur-type: skill
x-augur-group: brain
x-augur-release: mvp
x-augur-license: MIT
x-augur-tags:
- routine
- inbox
- capture
- filing
- cross-client
description: Daily routine that files vault-inbox capture cards into vault domains. The client's scheduled session classifies each card; three deterministic tools (inbox-triage-list, inbox-triage-file, inbox-triage-report) handle enumeration, atomic moves, and daily reporting. Move-only with a general/ drain so the inbox always empties. Cross-client, per ADR-744.
x-augur-callable: project-brain/capabilities/skills/inbox-triage/scripts/mcp/__init__.py
x-augur-mcp-tools:
- inbox-triage-list
- inbox-triage-file
- inbox-triage-report
x-augur-data-dir: inbox-triage
x-augur-config:
  commands:
  - id: inbox-triage
    type: routine
    visibility: user
    description: Daily vault-inbox auto-triage. Activated per-client via its native routine surface (Claude Code /schedule, Codex automations, etc.).
    callable: commands/inbox-triage.md
    protocol: routine
x-augur-loop:
  id: inbox-triage
  skill: inbox-triage
  automation:
    trigger: nightly
    runner: auto
    discover: commands/inbox-triage.md
  memory:
    trust: oneshot
---

# inbox-triage

Augur's daily inbox-filing process. Authored once, projected as a scheduled
routine into every supported AI client. Client scheduling and inference stay
entirely outside Augur — the client's session classifies cards and calls the
deterministic skill tools to file them (ADR-744).

## Boundaries

1. **No Augur scheduling.** The client's routine system owns the cron.
2. **No Augur LLM calls.** Classification runs inline in the client session.
3. **Move-only.** Cards are moved within the vault (git-reversible); never deleted.

## MCP tools (deterministic)

| Tool | Purpose |
|---|---|
| `inbox-triage-list` | Enumerate vault-inbox cards + metadata for classification |
| `inbox-triage-file` | Atomically move one card into a domain (+ provenance + Browse refresh) |
| `inbox-triage-report` | Write the daily report to `reports/inbox-triage/<date>.md` |

## Classification policy

Precedence: existing top-level domain → existing subdomain → new domain/subdomain
for a coherent recurring theme (prefer reusing a close match over a near-duplicate)
→ `general/` drain for genuine one-offs. Every folder creation is flagged in the
report.

## Workflow

The triage process runs as a oneshot inline-session routine:

- Step 1: Call `inbox-triage-list` to get all current vault-inbox cards with metadata.
- Step 2: For each card, determine the best-fit domain using the classification policy above.
- Step 3: Call `inbox-triage-file` with the card path and target domain to atomically move it.
- Step 4: After all cards are filed, call `inbox-triage-report` to write the daily summary.
- Step 5: Review the report for any new domain/subdomain folders flagged for user awareness.

If a card is ambiguous, prefer the `general/` drain over leaving it in the inbox.

## Checklist

- [ ] `inbox-triage-list` returns 0 remaining cards after the run
- [ ] No cards were deleted (only moved within the vault)
- [ ] Report written to `reports/inbox-triage/<date>.md`
- [ ] Any new folders created are flagged in the report

## Examples

```bash
# Run the daily inbox-triage routine (via the client's native routine surface)
/a-loops run inbox-triage

# Manually list cards waiting in the inbox
# (calls inbox-triage-list MCP tool)
aug mcp inbox-triage-list
```

## References

- Command contract: `commands/inbox-triage.md`
- Implementation: `scripts/mcp/__init__.py`
- Daily reports output to vault `reports/inbox-triage/`
- ADR-744: cross-client scheduling and LLM delegation model
- Vault domain layout: vault `domains/` top-level directories
