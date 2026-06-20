---
description: Audit a skill or dashboard hub, identify gaps, and drive hardening follow-up work
visibility: ops
---

# /harden

Audit a skill or a dashboard hub, identify the biggest quality gaps, and turn
them into concrete follow-up actions instead of leaving the surface half-wired.

## Usage

```bash
/harden career
/harden http://localhost:3000/career
```

If the argument looks like a URL, use hub mode. Otherwise, use skill mode.

## Skill Mode

Use when the target is a skill name.

1. Read the target skill definition and owned pages/actions/data
2. Assess the current state across:
   - problem alignment
   - action coverage
   - data support
   - UI access
   - capability completeness
   - end-to-end user journey fit
   - use [references/harden-assess-quality-6-dimensions.md](../references/harden-assess-quality-6-dimensions.md) as the scoring rubric
3. Ask only the minimum clarifying questions needed to close the largest gaps
4. Apply the fixes directly:
   - import or generate missing data
   - wire missing actions
   - remove dead promises from the skill surface
   - fix page/data mismatches
5. Re-score and report the delta

## Hub Mode

Use when the argument is a dashboard URL.

1. Audit the live page wiring first
2. Identify broken or empty blocks, missing MCP data, or missing action handlers
3. Produce the hardening path for the owning skills or ADR follow-up

## Rules

- run hardening work in a git worktree when the fix surface is broad
- fix the biggest user-visible gaps first
- remove dead claims and dead UI rather than preserving fake completeness
- do not treat fallback data as a fix

## Examples

- `/harden finance`
- `/harden http://localhost:3000/career`

## Additional resources

- [../references/harden-assess-quality-6-dimensions.md](../references/harden-assess-quality-6-dimensions.md)

