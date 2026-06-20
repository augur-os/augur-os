# Skill Taxonomy Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align Augur's skill ecosystem with Anthropic's recommended taxonomy — delete 19 skills, classify all remaining skills by type, create 7 new skills + 2 hooks, upgrade top 15 skills structurally, add usage instrumentation.

**Architecture:** 7-phase pipeline. Phase 0 (cleanup) must complete first. Phases 1-4 have dependencies (classification before new skills, new skills before structural upgrades). Phases 5-6 depend on Phase 1 (type system exists). Many tasks within phases are parallelizable.

**Tech Stack:** SKILL.md frontmatter (YAML), Python (classification script, ops_protocol), TypeScript/React (browse page), shell (hooks)

**Spec:** `docs/superpowers/specs/2026-03-21-skill-taxonomy-alignment-design.md`
**ADR:** `get_vault_dir()/dev/adrs/ADR-463-skill-taxonomy-alignment.md`

---

## Task 1: Delete 9 Stub Skills + Preserve Intent in ADR

**Files:**
- Modify: `get_vault_dir()/dev/adrs/ADR-463-skill-taxonomy-alignment.md`
- Delete: `.claude/skills/auto-a11y/`
- Delete: `.claude/skills/auto-broken-assets/`
- Delete: `.claude/skills/auto-circular-deps/`
- Delete: `.claude/skills/auto-empty-states/`
- Delete: `.claude/skills/auto-env-check/`
- Delete: `.claude/skills/auto-i18n/`
- Delete: `.claude/skills/auto-onboarding/`
- Delete: `.claude/skills/auto-perf-budget/`
- Delete: `.claude/skills/auto-markers/`

- [ ] **Step 1: Read each stub's SKILL.md to extract intent**

For each of the 9 stubs, read the SKILL.md and note the intended capability in one line.

- [ ] **Step 2: Add Future Capabilities section to ADR-463**

Append to `get_vault_dir()/dev/adrs/ADR-463-skill-taxonomy-alignment.md`:

```markdown
## Future Capabilities (Deferred from Stub Skills)

These capabilities were tracked as placeholder skills with no implementation. They are preserved here for future consideration.

| Capability | Former Skill | Description |
|-----------|-------------|-------------|
| Accessibility validation | auto-a11y | ARIA roles, keyboard navigation, contrast checks |
| Asset existence checks | auto-broken-assets | Verify image/asset references resolve |
| Circular dependency detection | auto-circular-deps | Detect circular imports in Python/TypeScript |
| Empty state validation | auto-empty-states | Verify pages handle empty data gracefully |
| Environment variable validation | auto-env-check | Verify required env vars are set |
| Internationalization | auto-i18n | i18n string extraction and validation |
| Onboarding validation | auto-onboarding | First-run experience completeness |
| Performance budgets | auto-perf-budget | Page load time and bundle size limits |
| TODO marker scanning | auto-markers | Replaced by auto-fix and auto-tidy |
```

- [ ] **Step 3: Delete the 9 skill directories**

```bash
rm -rf .claude/skills/auto-a11y .claude/skills/auto-broken-assets .claude/skills/auto-circular-deps .claude/skills/auto-empty-states .claude/skills/auto-env-check .claude/skills/auto-i18n .claude/skills/auto-onboarding .claude/skills/auto-perf-budget .claude/skills/auto-markers
```

- [ ] **Step 4: Verify deletion and check for dangling references**

```bash
# Verify directories gone
ls .claude/skills/auto-a11y 2>&1 | grep "No such file"

# Check daemon loop configs for references to deleted skills
grep -r "auto-a11y\|auto-broken-assets\|auto-circular-deps\|auto-empty-states\|auto-env-check\|auto-i18n\|auto-onboarding\|auto-perf-budget\|auto-markers" config/system/adaptive_loops.yaml
```

Remove any references found in loop configs.

- [ ] **Step 5: Commit**

```bash
git add -A .claude/skills/auto-a11y .claude/skills/auto-broken-assets .claude/skills/auto-circular-deps .claude/skills/auto-empty-states .claude/skills/auto-env-check .claude/skills/auto-i18n .claude/skills/auto-onboarding .claude/skills/auto-perf-budget .claude/skills/auto-markers
git commit -m "chore: delete 9 stub skills, preserve intent in ADR-463"
```

---

## Task 2: Delete 8 Duplicate Skills

**Files:**
- Delete: `.claude/skills/auto-debt/`
- Delete: `.claude/skills/auto-debt-scan/`
- Delete: `.claude/skills/documentation-sync/`
- Delete: `.claude/skills/rollback-recovery/`
- Delete: `.claude/skills/test-heal/`
- Delete: `.claude/skills/dev-retro/`
- Delete: `.claude/skills/fix-build/`
- Delete: `.claude/skills/reindex-rag/`

- [ ] **Step 1: Verify canonical versions exist and contain equivalent content**

For each pair, confirm the canonical skill has the same or superset content:
- `auto-tech-debt` covers `auto-debt` + `auto-debt-scan`
- `auto-docs` covers `documentation-sync`
- `ops-rollback` covers `rollback-recovery`
- `ops-self-heal-test` covers `test-heal`
- `dev-improve` covers `dev-retro`
- `runbook-dashboard` (created in Task 8) will cover `fix-build`
- `auto-rag-reindex` covers `reindex-rag`

- [ ] **Step 2: Delete the 8 skill directories**

```bash
rm -rf .claude/skills/auto-debt .claude/skills/auto-debt-scan .claude/skills/documentation-sync .claude/skills/rollback-recovery .claude/skills/test-heal .claude/skills/dev-retro .claude/skills/fix-build .claude/skills/reindex-rag
```

- [ ] **Step 3: Check for dangling references**

```bash
grep -r "auto-debt\b\|auto-debt-scan\|documentation-sync\|rollback-recovery\|test-heal\|dev-retro\|fix-build\|reindex-rag" config/ CLAUDE.md docs/agent-topics/ --include="*.md" --include="*.yaml"
```

Fix any references found.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: delete 8 duplicate skills — canonical versions retained"
```

---

## Task 3: Merge ops-daemon into daemon + file-bug into dev-improve

**Files:**
- Modify: `.claude/skills/daemon/SKILL.md`
- Modify: `.claude/skills/dev-improve/SKILL.md`
- Delete: `.claude/skills/ops-daemon/`
- Delete: `.claude/skills/file-bug/`

- [ ] **Step 1: Read ops-daemon SKILL.md for unique content**

Read `.claude/skills/ops-daemon/SKILL.md` — identify any launchd management content not already in `.claude/skills/daemon/SKILL.md`.

- [ ] **Step 2: Merge unique ops-daemon content into daemon**

Append any unique sections (launchd commands, status checks) to `.claude/skills/daemon/SKILL.md`. Do not duplicate content already present.

- [ ] **Step 3: Read file-bug SKILL.md and merge into dev-improve**

Read `.claude/skills/file-bug/SKILL.md` — append the TODO_ marker bug-filing workflow as a subsection of `.claude/skills/dev-improve/SKILL.md`.

- [ ] **Step 4: Delete merged skills**

```bash
rm -rf .claude/skills/ops-daemon .claude/skills/file-bug
```

- [ ] **Step 5: Update CLAUDE.md slash commands if /ops-daemon is listed**

Check if `/ops-daemon` appears in CLAUDE.md slash commands section. If so, replace with `/daemon` or note that daemon now covers this.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "chore: merge ops-daemon into daemon, file-bug into dev-improve"
```

---

## Task 4: Fix Stale augur.yaml Documentation

**Files:**
- Modify: `docs/agent-topics/SKILLS.md` (lines 68, 82, 89, 133)
- Modify: `docs/agent-topics/ARCHITECTURE.md` (lines 132, 213, 215)
- Modify: `docs/agent-topics/CONTEXT.md` (line 98)
- Modify: `docs/agent-topics/agent-rules.md` (lines 28, 43)
- Modify: `CLAUDE.md` (lines 33, 48)
- Modify: `config/system/skill-template.yaml` (lines 38, 75, 284)
- Modify: `config/system/adaptive_loops.yaml` (line 2)
- Modify: `~/.claude/projects/-Users-<user>-Projects-Augur/memory/feedback_mcp-api-testing-misc.md`
- Modify: `~/.claude/projects/-Users-<user>-Projects-Augur/memory/feedback_sync-mount-registry.md`
- Modify: `~/.claude/projects/-Users-<user>-Projects-Augur/memory/feedback_autoloop-regression-patterns.md`

- [ ] **Step 1: Fix docs/agent-topics/SKILLS.md**

Read the file. Replace all references to `augur.yaml` with the correct `x-augur-*` SKILL.md frontmatter pattern:
- Line 68: Remove `augur.yaml` from directory listing, replace with note that metadata lives in SKILL.md frontmatter
- Line 82: Change "CRITICAL: augur.yaml lives at..." to "CRITICAL: All skill metadata lives in SKILL.md frontmatter using x-augur-* fields"
- Line 89: Change "Create augur/augur.yaml" to "Add x-augur-* fields to SKILL.md frontmatter"
- Line 133: Change "use the skill's own augur.yaml" to "use the skill's SKILL.md frontmatter"

- [ ] **Step 2: Fix docs/agent-topics/ARCHITECTURE.md**

- Line 132: Update skill internal structure to remove augur.yaml reference
- Line 213, 215: Update tool config references to SKILL.md frontmatter

- [ ] **Step 3: Fix docs/agent-topics/CONTEXT.md and agent-rules.md**

- CONTEXT.md line 98: Update plugin scoping reference
- agent-rules.md lines 28, 43: Sync with CLAUDE.md rule wording

- [ ] **Step 4: Fix CLAUDE.md**

- Rule 2 (line 33): Replace "augur.yaml" with "SKILL.md x-augur-* frontmatter"
- Rule 16 (line 48): Remove augur.yaml from machine config examples (it no longer exists)

- [ ] **Step 5: Fix config/system files**

- `skill-template.yaml`: Remove augur.yaml from scaffold template, add `x-augur-type` field
- `adaptive_loops.yaml`: Update comment on line 2

- [ ] **Step 6: Fix memory files**

- `feedback_mcp-api-testing-misc.md` line 9: Update augur.yaml reference
- `feedback_sync-mount-registry.md` lines 41, 52, 54: Update Plugin State section
- `feedback_autoloop-regression-patterns.md` lines 9, 11: Update context

Note: Memory files are at `~/.claude/projects/-Users-<user>-Projects-Augur/memory/` — outside the project tree.

- [ ] **Step 7: Commit**

```bash
git add docs/agent-topics/ CLAUDE.md config/system/
git commit -m "docs: fix all stale augur.yaml references — retired per ADR-430"
```

---

## Task 5: Rebuild Registries and Verify Cleanup

**Files:**
- Modify: `docs/generated/skill-registry.md` (auto-generated)

- [ ] **Step 1: Run reindex-project**

Invoke `/reindex-project` to rebuild the skill registry from the current `.claude/skills/` state.

- [ ] **Step 2: Verify skill count**

```bash
ls -d .claude/skills/*/ | wc -l
```

Expected: ~187 (206 - 19 deleted).

- [ ] **Step 3: Verify no dangling slash commands in CLAUDE.md**

```bash
# Extract slash commands from CLAUDE.md
grep -oP '/[a-z-]+' CLAUDE.md | sort -u > /tmp/claude-commands.txt

# Check each against actual skill directories
while read cmd; do
  name="${cmd#/}"
  [ -d ".claude/skills/$name" ] || echo "MISSING: $cmd"
done < /tmp/claude-commands.txt
```

Fix any missing references.

- [ ] **Step 4: Commit registry**

```bash
git add docs/generated/
git commit -m "chore: rebuild skill registry after cleanup (187 skills)"
```

---

## Task 6: Build Classification Script + Run Scan

**Files:**
- Create: `scripts/classify_skills.py`

- [ ] **Step 1: Write classification script**

```python
#!/usr/bin/env python3
"""Classify all skills by x-augur-type based on directory structure and frontmatter."""

import os
import re
import yaml
from pathlib import Path
from src.config.paths import get_project_root

SKILLS_DIR = get_project_root() / ".claude" / "skills"

TYPE_RULES = {
    "template": lambda name, fm, dirs: name.endswith("-template"),
    "autoloop": lambda name, fm, dirs: (
        name.startswith("auto-")
        or fm.get("x-augur-loop")
        or any(f.endswith("_ops.py") for f in dirs.get("scripts", []))
    ),
    "domain": lambda name, fm, dirs: (
        "augur/api" in dirs.get("subdirs", [])
        or "augur/dashboard" in dirs.get("subdirs", [])
        or fm.get("x-augur-dashboard-pages")
        or fm.get("x-augur-mcp-tools")
    ),
    "command": lambda name, fm, dirs: fm.get("x-augur-visibility") in ("dev", "app", "ops"),
    "meta": lambda name, fm, dirs: True,  # fallback
}

ANOMALY_CHECKS = [
    ("type-straddler", lambda name, fm, dirs, typ:
        typ == "autoloop" and (
            "augur/api" in dirs.get("subdirs", [])
            or fm.get("x-augur-dashboard-pages")
        )),
    ("underpowered-domain", lambda name, fm, dirs, typ:
        typ == "domain" and not dirs.get("subdirs", [])),
    ("orphan-command", lambda name, fm, dirs, typ:
        typ == "command" and not fm.get("x-augur-visibility")),
]


def parse_frontmatter(skill_md: Path) -> dict:
    """Extract YAML frontmatter from SKILL.md."""
    text = skill_md.read_text(errors="replace")
    match = re.match(r"^(?:<!--.*?-->\s*)?---\s*\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return {}
    try:
        return yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return {}


def scan_dirs(skill_dir: Path) -> dict:
    """Scan skill directory structure."""
    subdirs = []
    scripts = []
    for root, dirs, files in os.walk(skill_dir):
        rel = os.path.relpath(root, skill_dir)
        if rel != ".":
            subdirs.append(rel)
        for f in files:
            if rel.startswith("scripts") and f.endswith(".py"):
                scripts.append(f)
    return {"subdirs": subdirs, "scripts": scripts}


def classify(name: str, fm: dict, dirs: dict) -> str:
    """Return the x-augur-type for a skill."""
    for typ, rule in TYPE_RULES.items():
        if rule(name, fm, dirs):
            return typ
    return "meta"


def main():
    results = {"clean": [], "flagged": []}
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue
        name = skill_dir.name
        fm = parse_frontmatter(skill_md)
        dirs = scan_dirs(skill_dir)
        typ = classify(name, fm, dirs)

        anomalies = []
        for anom_name, check in ANOMALY_CHECKS:
            if check(name, fm, dirs, typ):
                anomalies.append(anom_name)

        entry = {"name": name, "type": typ, "hub": fm.get("x-augur-hub", "unknown")}
        if anomalies:
            entry["anomalies"] = anomalies
            results["flagged"].append(entry)
        else:
            results["clean"].append(entry)

    # Print report
    print(f"## Skill Classification Report\n")
    print(f"### Clean Classifications ({len(results['clean'])} skills)\n")
    print("| Skill | Type | Hub |")
    print("|-------|------|-----|")
    for e in results["clean"]:
        print(f"| {e['name']} | {e['type']} | {e['hub']} |")

    if results["flagged"]:
        print(f"\n### Flagged for Review ({len(results['flagged'])} skills)\n")
        print("| Skill | Type | Hub | Anomalies |")
        print("|-------|------|-----|-----------|")
        for e in results["flagged"]:
            print(f"| {e['name']} | {e['type']} | {e['hub']} | {', '.join(e['anomalies'])} |")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the classification scan**

```bash
python3 scripts/classify_skills.py > docs/generated/skill-classification-report.md
```

- [ ] **Step 3: Review flagged skills — present to user for decisions**

Read `docs/generated/skill-classification-report.md` and present the flagged anomalies. Wait for user to decide on each.

- [ ] **Step 4: Commit**

```bash
git add scripts/classify_skills.py docs/generated/skill-classification-report.md
git commit -m "feat: add skill classification script, generate initial report"
```

---

## Task 7: Write x-augur-type + x-augur-tags to All Skills

**Files:**
- Modify: Every `.claude/skills/*/SKILL.md` (~187 files)

- [ ] **Step 1: Write frontmatter migration script**

Create `scripts/write_skill_types.py` that:
1. Reads the classification report from Task 6
2. For each skill, reads SKILL.md, parses frontmatter
3. Adds `x-augur-type: <type>` if not present
4. Adds `x-augur-tags: []` if not present (empty for now — filled during structural upgrades)
5. Writes back the updated SKILL.md preserving all other content

```python
#!/usr/bin/env python3
"""Write x-augur-type to all SKILL.md frontmatter based on classification report."""

import re
import yaml
from pathlib import Path
from src.config.paths import get_project_root

SKILLS_DIR = get_project_root() / ".claude" / "skills"


def read_classification(report_path: Path) -> dict:
    """Parse classification report markdown into {name: type} mapping."""
    mapping = {}
    text = report_path.read_text()
    for line in text.splitlines():
        if line.startswith("| ") and not line.startswith("| Skill") and not line.startswith("|---"):
            parts = [p.strip() for p in line.split("|")[1:-1]]
            if len(parts) >= 2:
                mapping[parts[0]] = parts[1]
    return mapping


def update_frontmatter(skill_md: Path, skill_type: str):
    """Add x-augur-type to SKILL.md frontmatter if not present."""
    text = skill_md.read_text(errors="replace")

    # Check if already has x-augur-type
    if "x-augur-type:" in text:
        return False

    # Find frontmatter end marker
    # Handle optional HTML comment before frontmatter
    pattern = r"(^(?:<!--.*?-->\s*)?---\s*\n)(.*?)(\n---)"
    match = re.match(pattern, text, re.DOTALL)
    if not match:
        return False

    prefix = match.group(1)
    fm_body = match.group(2)
    suffix = match.group(3)
    rest = text[match.end():]

    # Add x-augur-type after existing x-augur-hub if present, else at end
    if "x-augur-hub:" in fm_body:
        fm_body = fm_body.replace(
            "x-augur-hub:",
            f"x-augur-type: {skill_type}\nx-augur-hub:",
            1
        )
    else:
        fm_body += f"\nx-augur-type: {skill_type}"

    # Add x-augur-tags if not present
    if "x-augur-tags:" not in fm_body:
        fm_body += "\nx-augur-tags: []"

    skill_md.write_text(prefix + fm_body + suffix + rest)
    return True


def main():
    report = get_project_root() / "docs" / "generated" / "skill-classification-report.md"
    mapping = read_classification(report)

    updated = 0
    for name, typ in mapping.items():
        skill_md = SKILLS_DIR / name / "SKILL.md"
        if skill_md.exists() and update_frontmatter(skill_md, typ):
            updated += 1

    print(f"Updated {updated} / {len(mapping)} skills with x-augur-type")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the migration**

```bash
python3 scripts/write_skill_types.py
```

- [ ] **Step 3: Spot-check 5 skills across different types**

```bash
head -15 .claude/skills/career/SKILL.md       # should show x-augur-type: domain
head -15 .claude/skills/auto-lint/SKILL.md     # should show x-augur-type: autoloop
head -15 .claude/skills/dev-merge/SKILL.md     # should show x-augur-type: command
head -15 .claude/skills/advisor/SKILL.md       # should show x-augur-type: meta
head -15 .claude/skills/hub-template/SKILL.md  # should show x-augur-type: template
```

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/ scripts/write_skill_types.py
git commit -m "feat: add x-augur-type to all 187 SKILL.md frontmatter files"
```

---

## Task 8: Create Library Reference Skills (4)

**Files:**
- Create: `.claude/skills/nextjs-patterns/SKILL.md`
- Create: `.claude/skills/shadcn-patterns/SKILL.md`
- Create: `.claude/skills/python-patterns/SKILL.md`
- Create: `.claude/skills/mcp-sdk-patterns/SKILL.md`

These are parallel — all 4 can be created simultaneously by separate agents.

- [ ] **Step 1: Create nextjs-patterns**

Read `~/.claude/projects/-Users-<user>-Projects-Augur/memory/feedback_nextjs-turbopack-dashboard.md` to extract gotchas. Create:

```markdown
---
name: nextjs-patterns
description: "Use when editing files in apps/dashboard/, touching route.ts, page.tsx, layout.tsx, or server/client components in the Augur dashboard"
x-augur-type: library-reference
x-augur-hub: studio
x-augur-tags: [nextjs, turbopack, dashboard, react]
x-augur-master: claude-code
---

# Next.js Patterns for Augur Dashboard

## Gotchas

### 1. API Route Exports Must Be Named
API routes in `apps/dashboard/app/**/api/**/route.ts` must use named exports (`GET`, `POST`, `PUT`, `DELETE`). Default exports silently fail — the route returns 405.

### 2. Turbopack Cache Corruption
When the dev server behaves unexpectedly (stale pages, missing routes), the Turbopack cache is likely corrupt. Fix: stop dev server via `/dev-build`, delete `.next/`, restart.

### 3. Server/Client Boundary
Files importing browser APIs (`window`, `document`, `localStorage`) must have `"use client"` directive. Files importing server-only modules (`fs`, `crypto`, database) must NOT have `"use client"`. Mixing causes hydration errors that only appear in production builds.

### 4. Dynamic Route Segments
Dynamic routes `[param]` must match the directory name exactly. A route at `app/career/jobs/[id]/page.tsx` receives `params.id`, not `params.jobId`. Mismatched param names return undefined silently.

### 5. No fs Imports in API Routes
Per CLAUDE.md Rule 11, API routes must NEVER import `fs`, `fs/promises`, or `node:fs`. All file operations go through MCP tools. ESLint enforces this — if it blocks your build, you need an MCP tool, not an eslint-disable.

### 6. Route Group Layout Inheritance
Route groups `(group)` don't create URL segments but DO affect layout inheritance. A layout.tsx in `(admin)/` won't apply to routes outside that group, even in the same directory level.
```

- [ ] **Step 2: Create shadcn-patterns**

Explore `apps/dashboard/components/ui/` for existing ShadCN components. Create SKILL.md with gotchas about correct component composition, imports from `@/components/ui/`, theming, and form patterns.

- [ ] **Step 3: Create python-patterns**

Explore `src/config/paths.py` and `scripts/` for Python patterns. Create SKILL.md with gotchas about `src.config.paths` usage, Click CLI patterns, pydantic v2, pytest fixtures.

- [ ] **Step 4: Create mcp-sdk-patterns**

Explore `scripts/mcp/` and existing `@mcp.tool` registrations. Create SKILL.md with gotchas about tool naming (snake_case), parameter types, response shapes, and transformResponse contracts.

- [ ] **Step 5: Commit all 4**

```bash
git add .claude/skills/nextjs-patterns .claude/skills/shadcn-patterns .claude/skills/python-patterns .claude/skills/mcp-sdk-patterns
git commit -m "feat: add 4 library reference skills — nextjs, shadcn, python, mcp-sdk"
```

---

## Task 9: Create data-query Skill

**Files:**
- Create: `.claude/skills/data-query/SKILL.md`
- Create: `.claude/skills/data-query/scripts/` (query helpers)

- [ ] **Step 1: Create SKILL.md**

```markdown
---
name: data-query
description: "Use when querying vault data, analyzing logs, checking metrics, or inspecting skill data files across the Augur ecosystem"
x-augur-type: command
x-augur-hub: brain
x-augur-tags: [data, query, vault, logs, analysis]
x-augur-master: claude-code
---

# Data Query

## Vault Data Locations

| Data Type | Location | Format |
|-----------|----------|--------|
| Skill user data | `get_vault_dir()/{hub}/{skill}/` | Markdown with YAML frontmatter |
| ADRs | `get_vault_dir()/dev/adrs/` | Markdown with YAML frontmatter |
| Memory | `~/.claude/projects/*/memory/` | Markdown with YAML frontmatter |
| Logs | `~/Library/Logs/Augur/` | JSONL, plain text |
| State | `~/Library/Application Support/Augur/state/` | JSON, YAML |
| Caches | `~/Library/Caches/Augur/` | Various |

## Query Patterns

### Frontmatter Query
To find all vault files matching a criteria:
```bash
grep -rl "status: Active" get_vault_dir()/career/jobs/
```

### Log Analysis
```bash
# Recent errors
grep -i "error\|fail" ~/Library/Logs/Augur/*.log | tail -20

# Skill usage (after instrumentation)
cat ~/Library/Logs/Augur/skill-usage.jsonl | jq -r '.skill' | sort | uniq -c | sort -rn
```

## Gotchas

### 1. Frontmatter Uses write_frontmatter()
Never write vault data files with raw YAML. Use `src.lib.frontmatter_utils.write_frontmatter()` per ADR-404.

### 2. Vault Paths Resolved via src.config.paths
Never hardcode `get_vault_dir()/`. Use `get_vault_dir()` from `src.config.paths`.

### 3. Binary Files in ~/Documents/Augur/
PDFs, images, and other binaries live in `~/Documents/Augur/`, NOT in the vault.
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/data-query/
git commit -m "feat: add data-query skill for vault and log querying"
```

---

## Task 10: Create Runbook Skills (2)

**Files:**
- Create: `.claude/skills/runbook-dashboard/SKILL.md`
- Create: `.claude/skills/runbook-mcp/SKILL.md`

These are parallel — both can be created simultaneously.

- [ ] **Step 1: Create runbook-dashboard**

```markdown
---
name: runbook-dashboard
description: "Use when a dashboard page is blank, an API returns 500, a block shows no data, or an MCP tool call fails silently in the Augur dashboard"
x-augur-type: runbook
x-augur-hub: studio
x-augur-tags: [dashboard, debugging, wiring, api, mcp]
x-augur-master: claude-code
---

# Dashboard Diagnosis Runbook

When a dashboard page is broken, follow these steps IN ORDER. Do not skip steps.

## Steps

### Step 1: Identify the Symptom

| Symptom | Most Likely Cause | Jump To |
|---------|-------------------|---------|
| Page completely blank | Missing page.tsx or layout error | Step 2 |
| Page loads but block shows "no data" | MCP tool wiring mismatch | Step 3 |
| API returns 500 | MCP tool error or fs bypass | Step 4 |
| Block shows stale/wrong data | gracefulFallback masking failure | Step 5 |
| Build fails | TypeScript or import error | Step 6 |

### Step 2: Page Structure Check

```bash
# Verify the page file exists
ls apps/dashboard/app/{hub}/{page}/page.tsx

# Check if it's a mounted copy (auto-generated)
head -5 apps/dashboard/app/{hub}/{page}/page.tsx
# If it says "auto-generated", edit the source in .claude/skills/{skill}/augur/dashboard/
```

### Step 3: MCP Wiring Audit (CLAUDE.md Rule 17)

This is the most common failure. For EVERY API route the page calls:

```bash
# 1. Find the API route
grep -r "toolName" apps/dashboard/app/{hub}/**/api/**/route.ts

# 2. For each toolName found, verify it matches an actual MCP tool
grep -r "@mcp.tool(name=" scripts/ .claude/skills/*/scripts/ | grep "{toolName}"

# 3. If toolName doesn't match, that's the bug. Fix the toolName string.

# 4. Check transformResponse field names match MCP output
# Read the API route's transformResponse function
# Compare field names against the MCP tool's return dict keys
```

### Step 4: API Route Audit

```bash
# Check for forbidden fs imports (CLAUDE.md Rule 11)
grep -r "import.*\bfs\b\|from 'fs'\|from 'node:fs'" apps/dashboard/app/{hub}/**/api/**/route.ts

# Check for spawn/exec bypasses
grep -r "spawn\|execSync\|execFile\|runPythonScript" apps/dashboard/app/{hub}/**/api/**/route.ts
```

If found, the API route must use MCP tools instead.

### Step 5: Fallback Masking Check

```bash
# Find gracefulFallback usage
grep -r "gracefulFallback\|fallback" apps/dashboard/app/{hub}/ --include="*.ts" --include="*.tsx"
```

If a fallback is returning data, the PRIMARY path is broken. Fix the primary path (correct MCP tool, correct params, correct response transform). Do NOT improve the fallback.

### Step 6: Build Diagnosis

```bash
# Run build and capture errors
cd apps/dashboard && npx next build 2>&1 | head -50
```

Common fixes:
- Missing imports: add the import
- Type errors: fix the type, don't use @ts-ignore
- ESLint fs ban: use MCP tool instead of fs

## Output Template

After completing the runbook, produce a structured report:

```
## Diagnosis Report
**Page**: {hub}/{page}
**Symptom**: {description}
**Root Cause**: {what was wrong}
**Fix Applied**: {what was changed}
**Verification**: {how it was confirmed working}
```
```

- [ ] **Step 2: Create runbook-mcp**

```markdown
---
name: runbook-mcp
description: "Use when MCP server won't start, tools don't appear in listing, handshake fails, or tool returns unexpected shape"
x-augur-type: runbook
x-augur-hub: studio
x-augur-tags: [mcp, debugging, server, tools]
x-augur-master: claude-code
---

# MCP Server Diagnosis Runbook

When MCP tools fail, follow these steps IN ORDER.

## Steps

### Step 1: Check MCP Server Process
Is the Augur MCP server running?
```bash
ps aux | grep -i "augur.*mcp\|mcp.*augur" | grep -v grep
```
If not running, check startup logs at `~/Library/Logs/Augur/`.

### Step 2: Verify PYTHONPATH
```bash
echo $PYTHONPATH
# Must include both:
# - Project root: /Users/*/Projects/Augur
# - MCP source: /Users/*/Projects/Augur/src/mcp
```

### Step 3: Test list_tools Response
Call the MCP server's list_tools endpoint. Verify it returns without error and includes expected tools.

### Step 4: Validate Tool Names Match API Routes
```bash
# Extract all toolName references from API routes
grep -r "toolName" apps/dashboard/app/**/api/**/route.ts

# Cross-reference against registered MCP tools
grep -r "@mcp.tool(name=" scripts/ .claude/skills/*/scripts/
```
Every `toolName` in an API route MUST have a matching `@mcp.tool(name=...)`.

### Step 5: Check Parameter Schema Compliance
For the failing tool, compare the parameters the API route sends vs what the `@mcp.tool` function accepts. Mismatched parameter names cause silent failures.

### Step 6: Verify Response Shape Contracts
The MCP tool's return dict keys must match the field names used in the API route's `transformResponse`. A key mismatch returns `undefined` to the dashboard.

## Output Template
```
## MCP Diagnosis Report
**Tool**: {tool_name}
**Symptom**: {description}
**Root Cause**: {what was wrong}
**Fix Applied**: {what was changed}
**Verification**: {how it was confirmed working}
```
```

- [ ] **Step 3: Commit both**

```bash
git add .claude/skills/runbook-dashboard .claude/skills/runbook-mcp
git commit -m "feat: add runbook-dashboard and runbook-mcp diagnostic skills"
```

---

## Task 11: Create On-Demand Hook Skills (careful + freeze)

**Files:**
- Create: `.claude/skills/careful/SKILL.md`
- Create: `.claude/skills/freeze/SKILL.md`

- [ ] **Step 1: Create careful skill**

```markdown
---
name: careful
description: "Use when user invokes /careful — activates destructive command blocking for the session"
x-augur-type: command
x-augur-hub: command
x-augur-tags: [safety, hooks, session]
x-augur-master: claude-code
---

# /careful — Destructive Command Blocker

When this skill is active, you MUST refuse to execute any of the following commands without explicit per-command confirmation from the user:

## Blocked Patterns

| Pattern | Why |
|---------|-----|
| `rm -rf` | Recursive deletion |
| `git reset --hard` | Discards uncommitted changes |
| `git push --force` | Overwrites remote history |
| `git branch -D` | Deletes branch without merge check |
| `DROP TABLE`, `DROP DATABASE` | Database destruction |
| `/kill-augur` | Kills all Augur processes |
| `git checkout -- .` | Discards all working changes |
| `git clean -f` | Deletes untracked files |

## Behavior

When you encounter a blocked command:
1. STOP — do not execute
2. Show the user: "BLOCKED by /careful: `{command}` — this is a destructive operation"
3. Ask: "Do you want to proceed? (yes/no)"
4. Only execute if user explicitly confirms with "yes"

## Deactivation

This skill remains active for the entire session. There is no `/careful off` — start a new session to remove the restriction.
```

- [ ] **Step 2: Create freeze skill**

```markdown
---
name: freeze
description: "Use when user invokes /freeze <dir> — restricts file edits to only the specified directory"
x-augur-type: command
x-augur-hub: command
x-augur-tags: [safety, hooks, session, focus]
x-augur-master: claude-code
---

# /freeze — Directory Edit Boundary

When this skill is active, you MUST refuse to write or edit files outside the specified directory.

## Usage

- `/freeze .claude/skills/career` — only allow edits inside career skill
- `/freeze apps/dashboard` — only allow edits inside dashboard
- `/freeze off` — deactivate the restriction

## Behavior

When you encounter a Write or Edit targeting a file OUTSIDE the frozen directory:
1. STOP — do not execute
2. Show: "BLOCKED by /freeze: `{file_path}` is outside `{frozen_dir}`"
3. Ask: "Do you want to proceed anyway? (yes/no)"
4. Only execute if user explicitly confirms

## Exceptions

These are always allowed regardless of freeze:
- Reading any file (Read tool is never blocked)
- Running bash commands (Bash tool is never blocked)
- Searching files (Grep, Glob tools never blocked)
```

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/careful .claude/skills/freeze
git commit -m "feat: add /careful and /freeze on-demand session safety skills"
```

---

## Task 12: Structural Upgrades — Add Gotchas to Top 15 Skills

**Files:**
- Modify: `.claude/skills/{career,advisor,apple,knowledge,validator,frontend,daemon,dev-build,dev-debug,evolve,attention,content,google-workspace,coach,dev-merge}/SKILL.md`

This task is highly parallelizable — each skill upgrade is independent.

- [ ] **Step 1: Source gotchas for each skill**

For each of the 15 skills:
1. Read `~/.claude/projects/-Users-<user>-Projects-Augur/memory/feedback_*.md` for relevant patterns
2. Run `git log --oneline --grep="fix" -- .claude/skills/{skill}/` for bug fix history
3. Check CLAUDE.md rules that reference the skill

- [ ] **Step 2: Add ## Gotchas section to each SKILL.md**

For each skill, insert a `## Gotchas` section after the description/overview. Minimum 3 gotchas per skill. Format:

```markdown
## Gotchas

### 1. [Short title]
[Description of the failure mode and correct approach]

### 2. [Short title]
[Description]

### 3. [Short title]
[Description]
```

- [ ] **Step 3: Rewrite descriptions as triggers**

For each skill, change the `description` field from a summary to a trigger:
- Before: `"Manage job search pipeline, company research, and interview preparation"`
- After: `"Use when managing job applications, researching companies, preparing for interviews, or tracking career pipeline activity"`

- [ ] **Step 4: Add x-augur-tags**

For each skill, add 2-5 relevant tags. Example for career:
```yaml
x-augur-tags: [jobs, interview, companies, pipeline, resume]
```

- [ ] **Step 5: Progressive disclosure for large skills**

For each of the 15 skills with SKILL.md >200 lines:
1. Identify sections with detailed reference content (API docs, exhaustive parameter lists, long examples)
2. Extract those sections into `references/` subdir as separate .md files
3. Replace extracted content in SKILL.md with a pointer: `See references/{filename}.md for details`
4. Keep SKILL.md as a concise entry point: overview + gotchas + high-level usage

Example for `career/`:
- Extract detailed MCP tool parameter docs → `references/mcp-tools-api.md`
- Extract workflow diagrams → `references/interview-workflow.md`
- SKILL.md stays as overview + gotchas + trigger info

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/
git commit -m "feat: add Gotchas sections and trigger descriptions to top 15 skills"
```

---

## Task 13: Usage Instrumentation — PreToolUse Hook

**Files:**
- Create: `scripts/hooks/skill-usage-tracker.sh`
- Modify: `.claude/settings.json` (via update-config skill)

- [ ] **Step 1: Create the tracking script**

```bash
#!/bin/bash
# skill-usage-tracker.sh — Log skill invocations for analytics
# Triggered by PreToolUse hook when Skill tool is called

LOG_DIR="$HOME/Library/Logs/Augur"
LOG_FILE="$LOG_DIR/skill-usage.jsonl"

mkdir -p "$LOG_DIR"

# Extract skill name from tool input (passed via stdin as JSON)
SKILL_NAME=$(cat | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('skill','unknown'))" 2>/dev/null || echo "unknown")

# Append to log
echo "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"skill\":\"$SKILL_NAME\"}" >> "$LOG_FILE"

# Always exit 0 — don't block the tool call
exit 0
```

```bash
chmod +x scripts/hooks/skill-usage-tracker.sh
```

- [ ] **Step 2: Register the hook via update-config skill**

Use the `update-config` skill to add the PreToolUse hook to settings.json:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": { "tool_name": "Skill" },
        "command": "scripts/hooks/skill-usage-tracker.sh"
      }
    ]
  }
}
```

- [ ] **Step 3: Test the hook**

Invoke any skill and verify a line was appended to `~/Library/Logs/Augur/skill-usage.jsonl`.

- [ ] **Step 4: Commit**

```bash
git add scripts/hooks/skill-usage-tracker.sh
git commit -m "feat: add PreToolUse hook for skill usage tracking"
```

---

## Task 14: Create auto-skill-usage Autoloop

**Files:**
- Create: `.claude/skills/auto-skill-usage/SKILL.md`
- Create: `.claude/skills/auto-skill-usage/scripts/auto_skill_usage_ops.py`

- [ ] **Step 1: Create SKILL.md**

```markdown
---
name: auto-skill-usage
description: "Analyze skill invocation logs to identify undertriggered, overtriggered, and popular skills for adaptive engine and self-healing automation"
x-augur-type: autoloop
x-augur-hub: adaptive
x-augur-tags: [analytics, skills, instrumentation]
x-augur-visibility: auto
x-augur-loop:
  category: skill-standards
  tier: 5
x-augur-master: claude-code
---

# auto-skill-usage

Analyzes `~/Library/Logs/Augur/skill-usage.jsonl` to produce skill usage metrics.

## Metrics

| Metric | What It Tells You |
|--------|-------------------|
| Invocation count per skill (30 days) | Popular skills — prioritize for quality upgrades |
| Skills with 0 invocations in 30 days | Undertriggered — bad description or unused |
| Type distribution | Are library-reference skills loading? |
```

- [ ] **Step 2: Create ops script**

Write `scripts/auto_skill_usage_ops.py` following ops_protocol pattern with `scan()` function that reads the JSONL log, aggregates counts, and reports undertriggered skills as issues.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/auto-skill-usage/
git commit -m "feat: add auto-skill-usage autoloop for usage analytics"
```

---

## Task 15: Update Standards Enforcement Auto-Skills

**Files:**
- Modify: `.claude/skills/auto-skill-md/SKILL.md`
- Modify: `.claude/skills/auto-skill-md/scripts/auto_skill_md_ops.py`
- Modify: `.claude/skills/auto-skill-structure/SKILL.md`
- Modify: `.claude/skills/auto-skill-structure/scripts/auto_skill_structure_ops.py`
- Modify: `.claude/skills/auto-skill-quality/SKILL.md`
- Modify: `.claude/skills/auto-skill-enhance/SKILL.md`
- Modify: `.claude/skills/auto-loop-advisor/SKILL.md`
- Modify: `.claude/skills/evolve/SKILL.md`
- Modify: `config/system/skill-template.yaml`

- [ ] **Step 1: Update auto-skill-md to require x-augur-type**

Read `auto_skill_md_ops.py`. Add validation that `x-augur-type` exists in frontmatter. If missing, report as issue with auto-suggested type based on classification algorithm.

- [ ] **Step 2: Update auto-skill-structure for type contracts**

Read `auto_skill_structure_ops.py`. Add validation per type:
- `library-reference` must NOT have `augur/api/`, `augur/dashboard/`, `scripts/*_ops.py`
- `autoloop` must have `scripts/*_ops.py` with `scan()`
- `domain` should have `x-augur-mcp-tools` or `x-augur-dashboard-pages`
- Flag any `augur.yaml` files as retired artifacts

- [ ] **Step 3: Update auto-skill-quality for type-specific scoring**

Read `auto-skill-quality/SKILL.md`. Add type-aware scoring criteria:
- `library-reference`: score on gotchas depth, reference doc count
- `autoloop`: score on ops_protocol compliance, difficulty levels
- `domain`: score on dashboard page completeness, MCP tool coverage

- [ ] **Step 4: Update auto-skill-enhance for trigger descriptions**

Read `auto-skill-enhance/SKILL.md`. Add rule: generated descriptions must start with "Use when..." format. Infer `x-augur-tags` from skill content.

- [ ] **Step 5: Update evolve scaffolding**

Read `evolve/SKILL.md`. Add type prompt during new skill scaffolding — ask user which type, then generate the correct skeleton per type contract.

- [ ] **Step 6: Update skill-template.yaml**

Remove `augur.yaml` from scaffold. Add `x-augur-type` as required field.

- [ ] **Step 7: Commit**

```bash
git add .claude/skills/auto-skill-md .claude/skills/auto-skill-structure .claude/skills/auto-skill-quality .claude/skills/auto-skill-enhance .claude/skills/auto-loop-advisor .claude/skills/evolve config/system/skill-template.yaml
git commit -m "feat: enforce skill type system in auto-skill pipeline and scaffolding"
```

---

## Task 16: Browse Page Type/Tag Filtering

**Files:**
- Modify: Dashboard browse page (explore via `apps/dashboard/app/` to find the skills/browse page)
- Modify: API route serving skill data (needs to expose `x-augur-type` and `x-augur-tags`)

- [ ] **Step 1: Find the browse page**

```bash
find apps/dashboard/app -name "page.tsx" | xargs grep -l "skill\|browse" -i
```

Identify the component that renders the skill list.

- [ ] **Step 2: Expose type and tags in API response**

Ensure the API route that serves skill data includes `x-augur-type` and `x-augur-tags` from SKILL.md frontmatter in its response.

- [ ] **Step 3: Add filter controls**

Add to the browse page:
- Type filter dropdown: Domain / Library Reference / Runbook / Autoloop / Command / Template / Meta
- Tag filter: multi-select or freeform from `x-augur-tags`
- Preserve existing hub filter

Use ShadCN `Select` and `Badge` components per project conventions.

- [ ] **Step 4: Test in browser**

Open the browse page, verify:
- All skills display with their type badge
- Filtering by type shows correct subset
- Filtering by tag works
- Hub filter still works
- Combined filters work (type + hub)

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/
git commit -m "feat: add type and tag filtering to skill browse page"
```

---

## Task 17: Update ADR-463 Status

**Files:**
- Modify: `get_vault_dir()/dev/adrs/ADR-463-skill-taxonomy-alignment.md`

- [ ] **Step 1: Verify all phases complete**

Checklist:
- [ ] 19 skills deleted (9 stubs + 8 duplicates + 2 merged)
- [ ] All stale augur.yaml doc references fixed
- [ ] All skills classified with x-augur-type + x-augur-tags
- [ ] 7 new skills created (4 lib-ref + 1 data-query + 2 runbooks)
- [ ] 2 hook skills created (careful + freeze)
- [ ] Top 15 skills upgraded with Gotchas + trigger descriptions
- [ ] PreToolUse hook installed and logging
- [ ] auto-skill-usage autoloop operational
- [ ] Auto-skill pipeline enforcing type system
- [ ] Browse page filtering by type and tag

- [ ] **Step 2: Update ADR status to Implemented**

Change `status: Proposed` to `status: Implemented` in ADR-463 frontmatter.

- [ ] **Step 3: Commit**

```bash
git add get_vault_dir()/dev/adrs/ADR-463-skill-taxonomy-alignment.md
git commit -m "docs: mark ADR-463 as Implemented — skill taxonomy alignment complete"
```

---

## Dependency Graph

```
Task 1 (stubs) ──┐
Task 2 (dupes) ──┤
Task 3 (merges) ─┤
Task 4 (docs) ───┼──→ Task 5 (registries) ──→ Task 6 (classify) ──→ Task 7 (write types)
                 │                                                          │
                 │                              ┌───────────────────────────┤
                 │                              ↓                           ↓
                 │                     Task 8 (lib-ref skills)    Task 12 (structural upgrades)
                 │                     Task 9 (data-query)
                 │                     Task 10 (runbooks)          Task 15 (standards enforcement)
                 │                     Task 11 (hooks)
                 │                              │                           │
                 │                              ↓                           ↓
                 │                     Task 13 (instrumentation hook)  Task 16 (browse page)
                 │                     Task 14 (auto-skill-usage)
                 │                              │
                 └──────────────────────────────┴──→ Task 17 (ADR status)
```

**Parallelism opportunities:**
- Tasks 1-4 are independent (run all 4 in parallel)
- Tasks 8-11 are independent (run all 4 in parallel after Task 7)
- Tasks 13-14 are independent of Tasks 15-16
- Task 12 depends on Task 7 (needs type data) but is independent of Tasks 8-11
