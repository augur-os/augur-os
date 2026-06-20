---
title: "Comparison — Augur (ingest/RAG/knowledge) vs Onyx"
brain_scope: project
status: active
owner: team
date: 2026-05-24
tags: [comparison, rag, ingest, knowledge, connectors, landscape]
sources:
  - https://github.com/onyx-dot-app/onyx
note: "Onyx analyzed at README/architecture level (not source-cloned). Augur side grounded in source. The honest comparable Augur component is the ingest+RAG+knowledge layer, NOT sync_agents."
---

# Comparison — Augur vs Onyx (formerly Danswer)

> **Important framing:** Onyx has almost nothing to do with Augur's `sync_agents` projection engine. The user asked for "the same flow" as the cc-switch comparison, but Onyx's "sync" is **connector sync** — scheduled background jobs that pull data from external SaaS sources into a vector index. The honest Augur counterpart is its **ingest + RAG + knowledge layer** (`ingest`, `rag`, `knowledge`, `graph` skills + `unified_indexer.py`), not the client-projection sync. This note compares those.

> One-liner: **Onyx is an enterprise, server-hosted, multi-user RAG/search platform that continuously pulls from 50+ SaaS connectors into a vector index. Augur is a single-user, local-first, file-first second brain that ingests on-demand (files/URLs/audio/email-drop) and retrieves via lexical hybrid search with zero embeddings and zero database.** Same problem space ("answer questions over my knowledge"), opposite architecture on every axis.

## What Onyx is

Open-source (MIT CE + EE) "application layer for LLMs" — self-hostable, feature-rich chat over your org's knowledge. Python backend (~66%), Next.js/TypeScript frontend, Go bits. Agentic RAG (hybrid keyword+vector), deep research, custom agents, web search, code execution, artifacts, voice, image-gen. Supports all major LLM providers (Ollama/LiteLLM/vLLM self-hosted + OpenAI/Anthropic/Gemini). 29.7k★.

Deployment: **Lite** (<1GB, chat+agents only) and **Standard** (vector+keyword indexing engines, background job queues/workers for connector sync, DL inference servers, Redis cache, MinIO blob storage). Docker / Kubernetes / Helm / Terraform / major clouds. Onyx Cloud also offered.

## Side-by-side

| Dimension | Augur (ingest/RAG/knowledge) | Onyx |
|---|---|---|
| **Core purpose** | Personal second brain: capture + retrieve your own knowledge | Enterprise gen-AI search over org SaaS data |
| **Ingest sources** | Local files, URLs (browser-first, ADR-750), audio (voice memos/meetings, ADR-752), email-drop, watched/inbox folders, freeform thoughts | 50+ SaaS **connectors** (Slack, Google Drive, Confluence, Notion, GitHub, email…) + MCP |
| **Sync model** | **On-demand / explicit** (`/note`, `/keep`); only "background" is email-drop folder-watch (filesystem) | **Scheduled background jobs** polling live SaaS APIs; near-real-time refresh |
| **Incremental?** | Checksum-based incremental rebuild in `unified_indexer.py`; full rebuild on demand or nightly | Connector-level incremental + full re-index via worker queues |
| **Retrieval** | **Lexical hybrid**: ripgrep (markdown) + BM25 (extracted docs) + wiki, fused by **RRF** (ADR-739). Budget tiers (conservative/balanced/tokenmax) | **Semantic hybrid**: dense embeddings + keyword, agentic reranking |
| **Embeddings / vectors** | **None.** No embedding model, no vector DB | Embedding models + vector index (Vespa-class hybrid engine) |
| **Storage substrate** | **File-first**: markdown + JSON. No database (`bm25_index.json`, frontmatter graph, JSONL job ledger ADR-743) | Postgres + vector store + Redis + MinIO blob storage |
| **Knowledge graph** | Typed, **zero-LLM** edges in frontmatter (`_cites`, `_mentions`…), ADR-738 | N/A (vector-centric) |
| **Multi-user / auth** | **Single-user, local-first.** Multi-brain (ADR-754) is registry+aliasing only; no access control | **Enterprise multi-tenant**: RBAC, Google OAuth/OIDC/SAML, SCIM group sync, query auditing, doc-level permission sync |
| **LLM** | Rides the host AI client's LLM; vendor-neutral abstraction | Configurable provider per deployment; runs its own inference servers |
| **Footprint** | Runs from a repo on a laptop; nightly daemon loop | Multi-container cluster (Standard mode) |
| **Privacy posture** | Data never leaves the machine unless the host client sends it | Self-host for control, or Onyx Cloud |

## Where they overlap

Conceptually both do **RAG**: get documents → index → hybrid-search → feed an LLM → answer. Both offer hybrid retrieval. Both can use multiple LLM providers. Both are open/self-hostable rather than SaaS-locked. The end-user question — "answer me from my knowledge" — is identical.

## Where they fundamentally differ

1. **Connectors vs. capture.** Onyx's defining feature is the **connector framework**: 50+ scheduled background workers that *push* SaaS data into the index continuously. Augur has **no SaaS connectors at all** — it is pull-only and explicit. To approximate Onyx breadth, an Augur user manually exports/drops docs into Au-docs or the email-drop folder. This is the single biggest architectural gap and it is *by design* (local-first, single-user).

2. **Vectors vs. lexical.** Onyx is embeddings-first (semantic dense retrieval + reranking). Augur deliberately ships **no embeddings and no vector DB** — pure BM25 + ripgrep fused by RRF. Augur trades semantic recall for transparency (`cat bm25_index.json` works), zero infra, zero embedding cost, and offline operation. Onyx trades infra weight for semantic quality at scale.

3. **Database cluster vs. files.** Onyx Standard is Postgres + vector engine + Redis + MinIO + inference servers + worker queues. Augur is markdown and JSON on disk with a nightly daemon loop and a JSONL job ledger (ADR-743 explicitly *rejects* SQLite). Different scaling philosophies: Onyx scales to teams/orgs; Augur scales to one person's lifetime of notes without a server.

4. **Enterprise governance vs. single-user.** Onyx has RBAC, SSO, SCIM, document-level permission syncing, query auditing — it must, because many users share one index over sensitive sources. Augur has none of that and needs none: one user, one machine, the filesystem is the boundary.

5. **Agentic platform vs. capture+retrieve primitive.** Onyx is a full product surface (deep research, code execution, artifacts, voice, image-gen, web search). Augur's knowledge layer is a *primitive* inside a larger harness; "agentic" behavior comes from the host AI client orchestrating Augur's atomic MCP tools (rule 19), not from Onyx-style built-in agent runtime.

## What Augur could learn from Onyx

- **A connector abstraction for scheduled SaaS pull.** Even local-first, an opt-in connector (e.g. a scheduled Google Drive/Notion/GitHub export → email-drop/inbox lane) would close Augur's biggest ingest gap without abandoning the file-first model. The folder-watch + inbox-lane plumbing already exists; connectors would be "scheduled fetch → drop into a lane."
- **Optional semantic layer.** A local embedding index (sqlite-vec / lancedb) as a *fourth* RRF source would lift semantic recall while keeping the file-first lexical sources as the transparent default. RRF already fuses heterogeneous sources, so this slots in cleanly.
- **Permission-aware retrieval *if* multi-brain ever federates.** Onyx's document-level ACLs are the reference design for the day ADR-754 multi-brain grows cross-brain search.

## What Onyx could learn from Augur (or what Augur does better for its niche)

- **Zero-infra, file-first transparency.** No cluster, no vector DB, fully inspectable index, works offline — unbeatable for single-user/private knowledge.
- **Deterministic zero-LLM typed knowledge graph** (ADR-738) — cheap structured relations Onyx's vector-centric model doesn't capture.
- **Vendor-neutral, host-client-driven LLM** — no inference servers to run.

## Bottom line

Onyx and Augur answer the same user question from **opposite ends of the design space**: Onyx is a **heavyweight, multi-user, connector-fed, vector-based enterprise search server**; Augur is a **lightweight, single-user, capture-driven, lexical, file-first personal brain**. They are not substitutes — Onyx for a team standing up gen-AI search over shared SaaS; Augur for one person who wants a private, transparent, infra-free knowledge OS. The one idea most worth importing into Augur is a **scheduled, opt-in connector lane** (SaaS → existing inbox/email-drop plumbing), and secondarily an **optional local embedding source feeding RRF** — both adoptable without breaking Augur's local-first, file-first principles.

> Caveat: Onyx side is README/architecture-level (vector engine inferred as Vespa-class, not source-confirmed; exact connector list not enumerated in the README excerpt). Augur side is source-grounded.
