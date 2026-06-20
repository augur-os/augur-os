---
status: Implemented
date: '2026-05-11'
deciders:
- gsannikov
related:
- ADR-723
hub: command
tags:
- wiki
- mcp
- agent-contract
- report
- ai-client-execution-model
superseded_by: null
spec_file: 2026-05-11-wiki-report-agent-step-contract-design.md
plan_file: 2026-05-11-wiki-report-agent-step-contract.md
---

# ADR-726: Wiki Report Agent-Step Contract

## Decision summary

Define a tiered-required contract between `wiki-report-data`, the AI-client agent, and `wiki-report-generate` — with three coordinated surfaces (machine-readable schema, slash-command docs, runtime validation) — so `/wiki report` produces a deterministic Second Brain Intelligence Report...

## Status notes

Spec + plan written 2026-05-11 in the same session via `/superpowers:brainstorming` + `/superpowers:writing-plans`. Discovered while regenerating the deleted `docs/demo/second-brain-report.html` artifact — the `/wiki report` pipeline was end-to-end broken: missing seed assets, missing Jinja template, missing editorial contract between the aggregator and the renderer. Seeds + template restored in commit `3b376ba74`; this ADR locks the missing editorial contract. Wiki-only scope by design. Future report types (career, finance, project) get their own ADRs that may reference this pattern. Implemented 2026-05-12 in Windows session B2. The implementation added the wiki report contract module, wired `wiki-report-data` and `wiki-report-generate` to the schema/validator, aligned output with ADR-723 HTML artifact sidecars, documented `/wiki report`, and added focused unit/e2e coverage plus a live `brain` wiki-query contract smoke.

## Impact Manifest

```yaml
paths_renamed: []
apis_changed:
- 'wiki-report-data MCP tool response: adds synthesis_schema + hub_sections (list)'
- 'wiki-report-generate MCP tool: validates input rich dict, returns structured agent_step_required
  error on missing/invalid required fields'
- "wiki-report-generate output path: get_documents_dir()/reports/ \u2192 get_documents_dir()/brain/artifacts/"
- wiki-report-generate now writes a .meta.yaml sidecar alongside HTML+PDF per ADR-723
patterns_deprecated: []
files_affected:
- shared-vault/skills/ingest/scripts/wiki_report_contract.py (NEW)
- shared-vault/skills/ingest/scripts/mcp/wiki_tools.py
- shared-vault/skills/ingest/assets/templates/report.html.j2
- shared-vault/skills/rag/commands/wiki.md
- tests/unit/test_wiki_report_contract.py (NEW)
- tests/unit/test_wiki_report_e2e.py (NEW)
```
