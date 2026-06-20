---
description: Scan all skills for security vulnerabilities and auto-quarantine/block findings
visibility: auto
---

# auto-security-audit

Scan all skills (core, private, external) for security vulnerabilities.

## Difficulty Levels

| Difficulty | Action |
|-----------|--------|
| d0 | Report only — list all findings |
| d1 | Quarantine — flag critical/high skills in security-state.yaml |
| d2 | Block — disable MCP tool registration, move scripts to _quarantine/ |
| d3 | Auto-remove — remove blocked external skills (tier>=1) |
| d4 | Evolution gap — suggest Sigstore/SPDX/GitHub verification |

## CLI Usage

```bash
python3 project-brain/capabilities/skills/routine-security/scripts/security_audit.py --difficulty 0
python3 project-brain/capabilities/skills/routine-security/scripts/security_audit.py --difficulty 1 --dry-run
```
