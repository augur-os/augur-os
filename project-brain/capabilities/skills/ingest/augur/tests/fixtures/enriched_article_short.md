---
title: "The Architecture of Leverage"
x-augur-note-type: url
url: https://example.com/leverage
x-augur-enrichment-status: enriched
x-augur-enrichment-version: 1
---

## Executive summary

- Leverage is the compounding return on a single good design decision
- The architect's job is to compound future work, not just make today's system function
- Three reliable sources of leverage: cheap-to-maintain invariants, composable interfaces, intent-documenting tests
- Friction is the opposite of leverage and the audit signal for missing leverage points

## Key insights

1. Leverage is measured in deferred work, not in current throughput
2. Interfaces that survive their first author are the load-bearing artifact of a healthy system
3. Tests should document intent — when they document current behavior, every refactor is a rewrite

## Why it matters

For our team's roadmap, the leverage frame separates work that compounds (invariants, interfaces) from work that burns (per-incident fixes). Most quarters we spend more on the burn side; this is the explicit case for shifting allocation.

## Verbatim quotes

> "Leverage in software, broadly construed, is the multiplier that lets one good decision keep paying dividends for years."

> "The opposite of leverage is friction — every workaround for a bad invariant, every interface a team learns to fear, every brittle test that has to be rewritten when behavior is updated."

## Cross-references

- [[wiki/concepts/leverage]]
- [[wiki/concepts/architecture]]

## Original content

Leverage in software, broadly construed, is the multiplier that lets one good decision keep paying dividends for years. The architect's job is not just to make systems work today — it is to compound future work. Three patterns reliably create leverage: invariants that are cheap to maintain and expensive to violate, composable interfaces that survive their first author, and tests that document the system's intent rather than its current shape. The opposite of leverage is friction — every workaround for a bad invariant, every interface a team learns to fear, every brittle test that has to be rewritten when behavior is updated.
