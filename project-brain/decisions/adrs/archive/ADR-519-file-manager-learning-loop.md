---
status: Implemented
date: 2026-03-28
deciders:
  - Gur Sannikov
related: [ADR-517, ADR-518]
hub: adaptive
tags: [file-manager, learning-loop, confidence-scoring, autoloop]
superseded_by: null
---

# ADR-519: File Manager Learning Loop — Confidence Scoring and Pending UX

## Context

The file-manager triage (ADR-517) uses static keyword matching against `x-augur-file-intake` declarations. Of 30 Desktop files tested, 9 remained "pending" because the system couldn't confidently route them — Hebrew PDFs with garbled text, files with no matching keywords, and images without OCR text all end up unrouted. Users have no way to review pending files or teach the system their preferences.

ADR-517 consolidated file-manager skills. ADR-518 added document extraction. This ADR adds the intelligence layer: confidence scoring, decision learning, and a pending queue UX.

## Decision

### 1. Confidence Scoring Engine

Pure pattern matching against past decisions — no LLM needed, fast, offline, deterministic. Six signals (filename keywords, content keywords, extension, source folder, size range, past decisions) weighted to produce a 0-1 confidence score per skill. Threshold at 0.6 for auto-routing; below that, file goes to pending queue.

### 2. Decision Learning Loop

When a user manually routes a pending file, the decision is recorded as a training example. Past decisions feed back into the confidence scorer's `past_decisions` signal (weight 0.25), creating a flywheel where the system gets smarter over time.

### 3. Pending Queue Dashboard UX

Dashboard page showing unrouted files with confidence scores, top skill suggestions, and one-click routing buttons. Users can approve, override, or dismiss. Each action feeds the learning loop.

### 4. Autoloop Integration

The file-manager autoloop runs the scorer on new files at each cycle. High-confidence files route automatically; low-confidence files queue for review.

## Consequences

### Positive

- File routing accuracy improves with usage (learning flywheel)
- Users gain visibility into pending files instead of a black hole
- No LLM cost for routing decisions — pure pattern matching

### Negative

- Cold start problem — system needs ~20 decisions before scoring is useful
- Scoring algorithm is an approximation — some edge cases will need manual routing indefinitely

### Neutral

- Existing keyword matching remains as one signal in the scoring engine

## Alternatives Considered

### Alternative 1: LLM-based classification

Use an LLM to classify each file. Rejected because it adds cost per file, requires network access, and is slower than pattern matching. The LLM path is already available via ADR-518 for content extraction — classification should be cheaper.

### Alternative 2: Rule-based routing only

Extend the keyword matching with more rules. Rejected because rules don't learn from user behavior and require manual maintenance as new file types appear.

## References

- Design doc: `docs/superpowers/specs/2026-03-26-file-manager-learning-loop-design.md`
- Implementation plan: `docs/superpowers/plans/2026-03-26-file-manager-learning-loop.md`
- ADR-517: File Manager Consolidation
- ADR-518: Universal Document Extraction
