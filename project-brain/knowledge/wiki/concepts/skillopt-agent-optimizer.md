---
title: 'GitHub - microsoft/SkillOpt: Executive Strategy for Self-Evolving Agent Skills'
x-augur-note-type: url
canonical_url: https://github.com/microsoft/SkillOpt
content_hash: sha256:9afb5edbe8ffac81ccae4d01cdd2b5af332fabc9c33083a127010c83c124887d
tags:
- agent-skills
- skill-optimization
- self-improving-agents
- llm
- microsoft
- research
captured_at: '2026-06-08T06:11:42.348995+00:00'
_source_type: url
_relates_to:
- '[[agent-skills]]'
- '[[llm]]'
- '[[microsoft]]'
- '[[research]]'
- '[[self-improving-agents]]'
- '[[skill-optimization]]'
_mentions:
- '[[skills]]'
---



# GitHub - microsoft/SkillOpt: Executive Strategy for Self-Evolving Agent Skills

> [!summary]
> SkillOpt (Microsoft Research) trains an agent's **skill document** like a neural
> net — epochs, (mini-)batch size, learning rates, validation gates — **without
> touching model weights**. An optimizer model turns scored rollouts into bounded
> add/delete/replace edits, accepted only when a held-out validation score
> strictly improves; the deployed artifact is a compact `best_skill.md` (~300–2,000
> tokens) with **zero extra inference-time calls**. Best/tied-best on all 52
> (model, benchmark, harness) cells; on GPT-5.5 lifts no-skill accuracy +23.5
> (direct chat), +24.8 (Codex), +19.1 (Claude Code). MIT.

## Source

- URL: https://github.com/microsoft/SkillOpt · Project page: https://microsoft.github.io/SkillOpt/ · Paper: https://arxiv.org/abs/2605.23904
- Install: `pip install skillopt` (PyPI, v0.1.0) · Python 3.10+ · License: MIT
- Backends: OpenAI / Azure / Claude / Qwen / MiniMax · 6 built-in benchmarks · WebUI dashboard
- Captured: 2026-06-08T06:11:42.348995+00:00
- Note: GitHub README is JS-rendered (auto-fetch hit HTTP 504 / stub); this body was enriched from the raw README.

## Body

**SkillOpt: Executive Strategy for Self-Evolving Agent Skills.** Treats the skill
document as the *trainable state* of a frozen agent and trains it with
deep-learning-optimizer discipline — instead of hand-crafting, one-shot LLM
generation, or loosely controlled self-revision.

**Training loop:** rollout → reflect → aggregate → select → update → evaluate. A
separate optimizer model proposes bounded edits to a single skill doc; a candidate
is accepted only on a strict held-out validation improvement. A textual
learning-rate budget, a rejected-edit buffer, and an epoch-wise slow/meta update
keep skill training stable. Deployment adds **zero inference-time model calls** —
the output is a compact `best_skill.md` run against the unchanged target model.

**Results:** across 6 benchmarks, 7 target models, and 3 harnesses (direct chat,
Codex CLI, Claude Code CLI), best or tied-best on **all 52 evaluated cells**;
optimized skills **transfer** across model scales, between Codex and Claude Code,
and to nearby benchmarks without re-optimization.

**Why kept (relevance to Augur):** a rigorous, benchmarked method to **optimize
Augur's agent skills** — directly applicable to the `[[skills]]` system, the
`/skillify` flow, and skill-enhancement loops, and conceptually adjacent to the
ingest workflow's own learning loop (decisions / correction-learning). Notably it
is **evaluated inside Claude Code (our harness)** and produces a portable
`best_skill.md`. Strong candidate for a proof-of-concept: train a `file-manager`
or routine skill doc with SkillOpt and compare against the current hand-authored
version.
