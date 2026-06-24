---
name: routine-security
x-augur-type: autoloop
x-augur-group: augur_autoloops
x-augur-release: mvp
x-augur-license: MIT
description: Scheduled security routines that audit Augur's code, config, and vault for prompt-injection vectors, leaked secrets and credentials, static-analysis defects, file-integrity drift, and permission or exposure gaps, reporting findings and applying safe fixes nightly.
x-augur-tab: security
x-augur-tags:
- routine
- autoloop
- security
x-augur-dashboard-pages: []
x-augur-data-dir: routine-security
x-augur-commands:
- id: auto-security-audit
  type: workflow
  visibility: auto
  description: Scan all skills for security vulnerabilities using a 5-stage offline pipeline.
  callable: scripts/security_audit.py
  protocol: scan-fix
  loop:
    name: hardening
    tier: 3
    trigger: nightly
x-augur-config:
  contributions:
    commands:
    - id: auto-security-audit
      type: workflow
      visibility: auto
      description: Scan all skills for security vulnerabilities using a 5-stage offline pipeline.
      callable: scripts/security_audit.py
      protocol: scan-fix
---

# routine-security

Security routines for prompt-injection, secret, static-analysis, integrity, and permission checks.

## Commands

- [commands/auto-security-audit.md](commands/auto-security-audit.md)

## Scope

Use this routine skill for security audits previously owned by the retired security loop skill.

## When to use

Use `routine-security` when auditing or hardening Augur before a release, after a large refactor, or on the nightly schedule. It is the security concern of the consolidated routine family (alongside code-quality, coverage, and vault hygiene).

## What it checks

- **Prompt injection** — scans skill instructions and ingested content for injection vectors.
- **Secrets** — detects leaked credentials, tokens, and API keys in code and config.
- **Static analysis** — flags risky patterns via an offline multi-stage pipeline.
- **Integrity** — verifies file integrity and surfaces unexpected drift.
- **Permissions** — checks for over-broad permission grants and exposure gaps.

## How it runs

The `auto-security-audit` workflow in `scripts/security_audit.py` runs as a nightly scan-fix process: it reports findings, applies safe mechanical fixes, and escalates risky findings for human review.

## Examples

```bash
# Run the deterministic security scan on demand
aug a-loops scan-only --loop hardening
```
