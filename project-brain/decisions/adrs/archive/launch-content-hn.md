# Hacker News Show HN Post — Draft

## Format A: URL Submission (Preferred)

**Title:** Show HN: Augur – local-first personal AI OS with 200+ skills, MCP-native

**URL:** https://github.com/augur-os/augur-os

No text body. HN shows URL or text, not both. The README does the heavy lifting.

---

## Format B: Text Submission (Self-Post Fallback)

**Title:** Show HN: Augur – local-first personal AI OS with 200+ skills, MCP-native

**Text:**

Augur is a local-first system that connects your notes, files, skills, and workflows to any AI client through MCP. It started as a personal project six months ago and grew into 200+ composable skills across career, finance, health, knowledge management, and home automation. I open-sourced it under MIT.

**Architecture: Filesystem -> MCP -> Any Client**

Everything is plain files on disk — markdown notes, YAML configs, Python scripts. An MCP server exposes them as tools. Any MCP-compatible client (Claude Code, Cursor, Codex, Gemini, Ollama) connects to the same identity. The dashboard is just another client — not the product.

The three layers:

1. **Vault** — your data. Markdown notes, documents, skill configs. Survives uninstalling Augur.
2. **MCP server** — Python 3.11+. Exposes 100+ tools for search, file ops, skill execution, knowledge retrieval.
3. **Clients** — anything that speaks MCP. The Next.js dashboard, your IDE, CLI agents.

**What makes it different:**

- **AI creates, you curate.** Flips the note-taking paradigm. AI compiles knowledge from conversations and research into markdown. You review in Obsidian, the dashboard, or any editor.
- **~80 autoloops run nightly.** Self-healing automation on idle hardware. Code review, test coverage, security scans, RAG reindexing, doc freshness — zero API cost via local models.
- **Full airplane mode.** Ollama backend for corporate or offline environments. No API keys, no data leaves the machine.
- **Open skill standard.** Skills follow agentskills.io — portable across AI clients, not locked to Augur.
- **BM25 + ripgrep hybrid RAG.** No vector database. Contextual chunking with local Ollama summarization. Fast, deterministic, auditable.

**Tech details:** Python (MCP server, skills, automation) + TypeScript/Next.js (dashboard). 388 architecture decision records. ~2,800 test files. MIT licensed.

**Install:**

```
npx create-augur
```

GitHub: https://github.com/augur-os/augur-os
Website: https://augur.run

---

## Notes for Submission

**Timing:** Post between 8-10am ET on a weekday (Tuesday-Thursday optimal for Show HN).

**First comment:** HN convention is for the creator to post a comment immediately after submission explaining the backstory. Draft:

> I built this over six months as my personal second brain. It started because I was frustrated that every AI conversation disappeared — useful research, decisions, action items — all gone after the session ended.
>
> Augur captures that output as plain markdown files and makes it searchable across all my AI clients. The key insight was making MCP the integration layer instead of building another chat UI. Any client that speaks MCP gets access to the same knowledge, the same skills, the same identity.
>
> The autoloops were an accident. I wrote a few scripts to reindex my RAG and run lint overnight. Then I added security scans, doc freshness checks, test coverage analysis. Now there are ~80 of them. They run on local models so there's no API cost — just idle CPU time.
>
> Architecture-wise, the interesting bits:
> - RAG is BM25 + ripgrep, no vector DB. I found that for personal knowledge bases (< 50K docs), sparse retrieval with good chunking beats embeddings on recall and is 10x faster to index.
> - Skills follow the Agent Skills standard (agentskills.io) — each skill is a self-contained directory with SKILL.md metadata, commands, scripts, and data. You can copy a skill folder into any compatible AI client.
> - The 388 ADRs are real — every architectural decision is documented with context, alternatives considered, and rationale. It's how I keep the system coherent as a solo developer.
>
> Happy to answer questions about the architecture, the autoloop system, or the RAG approach.

**Response prep:** Be ready to answer about:
- Why not use a vector DB (performance comparison data, recall metrics)
- How autoloops avoid runaway costs (local models only, no API calls)
- MCP vs custom API (portability, client ecosystem)
- How this compares to Obsidian + plugins (integration layer vs editor)
- License and monetization (MIT, sessions at $249/hr for customization help)
