---
description: Scan for hardcoded secrets, npm vulnerabilities, and known CVEs
visibility: ops
---

# auto-security-scan

Scan the codebase for hardcoded secrets and dependency vulnerabilities.
Daemon-managed (hardening loop, tier 4).

## Scan

- **d0**: Checks source files for hardcoded API keys, tokens, and credentials
  using regex patterns (OpenAI keys, GitHub tokens, AWS keys, generic secrets)
- **d1+**: Also runs `npm audit` against the dashboard package.json
- **d2+**: Expands secret patterns to cover more credential formats

Skips node_modules, .next, runtime, and other non-source directories.

## Fix

Runs `npm audit fix` for safe auto-fixable vulnerabilities. Hardcoded secrets
are never auto-fixed — they are reported for manual review and rotation.
