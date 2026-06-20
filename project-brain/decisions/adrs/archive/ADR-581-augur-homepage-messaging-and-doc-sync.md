---
status: Implemented
date: 2026-04-10
deciders:
- Gur Sannikov
related: []
hub: null
tags:
- website
- messaging
- docs
- positioning
superseded_by: null
---

# ADR-581: Augur Homepage Messaging and Doc Sync

## Context

The public Augur homepage and the repo-facing README/architecture docs had drifted out of sync with the approved positioning. The website still led with older framing and pointed at the legacy `github.com/gsannikov/augur` URL. The README and `docs/architecture-overview.md` did not yet carry the deeper philosophy and architecture story that the website now promises.

The approved positioning frames Augur as ownership without vendor lock-in, names concrete capabilities ("add a document and it is automatically indexed", "build local apps you own on top of MCP"), and credits ready apps and ~80 autoloops as the relief from babysitting every moving part. The repo-facing docs need to be the technical companion to the website during the soft launch, with a clear `Augur` (product) vs `Augur OS` (public technical surface) split.

The change spans three surfaces: the working homepage HTML, the top-level `README.md`, and `docs/architecture-overview.md`, with regression tests guarding each surface against future drift, plus a packaged website artifact rebuild.

## Decision

Refresh the public Augur story across three surfaces, gated by tests asserting the new copy:

1. **Homepage** (`Au-docs/venture-augur/website-working/index.html`): hero leads with "Own your AI setup without vendor lock-in" and "one local system for knowledge, tools, and workflows"; capabilities section enumerates concrete actions in plain language; CTA card promotes "Explore Augur OS on GitHub" pointing at `github.com/augur-os/augur-os`; JSON-LD and footer GitHub links updated to the canonical Augur OS URL.
2. **README.md**: top section names the vendor lock-in story and ~80 autoloops; explicitly explains Augur OS as the public open-source repository during soft launch; replaces "What Can I Build" bullets with user-readable capability bullets.
3. **`docs/architecture-overview.md`**: framing block explains "ownership without vendor lock-in" and "apps and autoloops reduce maintenance burden"; explicitly states "Augur OS is the public technical surface for Augur during soft launch"; revised principle and repo-mapping sections explain why local ownership matters and how apps/autoloops absorb ecosystem churn.

Tests in `tests/test_augur_website_citability.py`, `tests/test_augur_website_geo.py`, and a new `tests/test_augur_repo_positioning.py` enforce the new copy. The packaged website (`augur-run-V48.zip`) is regenerated from the refreshed working copy.

## Consequences

### Positive
- Public-facing story aligns across website, README, and architecture overview.
- Authority links point at the canonical `augur-os/augur-os` repo, fixing GEO/citability signals.
- Regression tests prevent silent drift away from approved positioning.
- Soft-launch framing explicit so Augur OS is described as a technical surface rather than the product itself.

### Negative
- Locking copy into tests creates friction for future messaging tweaks; every adjustment requires test updates.
- Three surfaces multiplied by test files plus a website zip artifact means even small wording changes touch many files.
- Architecture overview gains user-positioning prose, slightly diluting its technical-reference tone.

### Neutral
- Phase covers messaging and docs only; product features and skill behavior are unchanged.
- FAQ and other website sections kept as-is where current framing already works.

## Alternatives Considered

### Alternative 1: Update only the homepage
Leave README and architecture-overview alone. Rejected because GitHub visitors land on a repo that contradicts the website story, weakening the soft-launch credibility.

### Alternative 2: Defer until after soft launch
Wait for product feedback before locking copy. Rejected because the legacy GitHub URL and stale positioning actively hurt traffic and citability now; the longer the drift persists, the more places it leaks into.

### Alternative 3: Skip regression tests, rely on review
Manual review only. Rejected because past drift shows that without test gates the public story silently diverges between releases.

## References
- Plan: docs/superpowers/plans/2026-04-10-augur-homepage-messaging-and-doc-sync.md
