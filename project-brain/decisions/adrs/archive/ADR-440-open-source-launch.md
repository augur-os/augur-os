---
status: Superseded
date: 2026-03-18
deciders:
  - Gur Sannikov
related:
  - ADR-437
  - ADR-438
hub: system
tags:
  - open-source
  - launch
  - licensing
  - community
superseded_by: ADR-537
---

# ADR-440: Open Source Launch Preparation [RECONSTRUCTED]

## Context

Augur was developed as a private personal knowledge/automation system. To share it with the developer community and enable contributions, the project needed preparation for open-source release. This included personal data scrubbing, license changes, fresh git history, install resilience for new users without existing data, and community infrastructure. The vault directory needed to be optional for new users rather than required.

## Decision

Prepare Augur for open-source launch as `augur-os/augur-os` on GitHub. Key decisions:

### Repository and Identity

- Repo name: `augur-os/augur-os` (clean namespace, signals "AI OS")
- Internal module names stay as `augur` / `augur_mcp` (minimize churn)
- Fresh git history with single initial commit (20k commits have high leak surface area)
- Private archive: current repo stays as-is with full history

### Licensing

- License: MIT (maximum adoption, SaaS threat is low for local-first personal OS)
- Replace Elastic License 2.0 entirely, including custom commercial clauses
- Update `pyproject.toml`, `CONTRIBUTING.md`, README badges

### Personal Data Scrub

- Ship all 132 skills, scrub personal data
- Client skills renamed to generic templates (e.g., `client-smb-design` to `smb-client-template`)
- Scrub categories: client names, career data, financial data, health data, contact info, absolute paths, business logic
- Maintainer name and "Sponsored by Guriqo" badge remain

### Fresh-Install Resilience

- All external directories (`~/Vault/Augur/`, state, logs, cache) must be optional for new users
- The vault is optional: code paths must handle missing vault gracefully (ADR-440 comment in `src/config/paths.py`)
- Health checks report "not configured" rather than error when daemon/vault are absent
- Skills report "no data" and seed on first use

### Community

- GitHub Discussions only (no Discord -- single developer cannot moderate)
- Branch protection: maintainer pushes directly to main, external contributors require PR + CI + review
- Soft launch to 5-10 trusted users before public announcement

**Note**: This ADR was superseded by the comprehensive open-source launch design spec at `docs/superpowers/specs/2026-03-18-open-source-launch-design.md`, which identified additional workstreams (CI workflow migration, config templates, launch docs) not covered in the original ADR.

## Consequences

### Positive

- Augur becomes available to the developer/life-hacker community
- MIT license enables maximum adoption and contribution
- Fresh git history eliminates risk of personal data leaks in commit history
- New users get a clean onboarding experience without depending on existing data

### Negative

- Full 20k-commit history lost from public repo (preserved privately)
- Personal data scrub is labor-intensive across 132 skills
- CI workflows need migration from self-hosted runners to GitHub-hosted runners

### Neutral

- Internal module names unchanged, reducing migration risk
- ADR-437 and ADR-438 provide the multi-platform install paths needed for launch
- Soft launch strategy allows iteration before public announcement

## Alternatives Considered

### Alternative 1: Open Core Model

Release a subset of skills as open source, keep premium skills proprietary.

**Rejected because**: Personal productivity skills are not a SaaS business -- there is no revenue to protect. Full open source maximizes community value and contributions.

### Alternative 2: Preserve Full Git History

Clean commits of personal data but keep the full history.

**Rejected because**: 20,000 commits across hundreds of files create too large a surface area for accidental PII exposure. The cleanup effort exceeds the value of preserving history for external contributors.

## References

- Design spec (supersedes this ADR): `docs/superpowers/specs/2026-03-18-open-source-launch-design.md`
- Paths config: `src/config/paths.py` (comment: "External dirs -- vault is optional for new users (ADR-440)")
- ADR-437: Distribution Plugin Architecture
- ADR-438: Multi-Entry Onboarding
