# `/dev-adr gaps` Subcommand Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `gaps` subcommand to `/dev-adr` that scans multiple ADRs for implementation gaps and produces a severity-ranked report with suggested fixes.

**Architecture:** Pure declarative addition to SKILL.md — no new Python scripts, MCP tools, or dashboard code. Follows the existing pattern where the agent reads the spec from SKILL.md and executes using built-in tools (grep, glob, read).

**Tech Stack:** Markdown (SKILL.md frontmatter + spec)

**Spec:** `docs/superpowers/specs/2026-03-17-dev-adr-gaps-subcommand-design.md`

---

### Task 1: Update SKILL.md frontmatter description

**Files:**
- Modify: `.claude/skills/dev-adr/SKILL.md:3-4`

- [ ] **Step 1: Update description to include `gaps`**

Change line 3-4 from:
```yaml
description: Manage Architecture Decision Records -- query, write, implement, harden,
  plan, test, status
```
to:
```yaml
description: Manage Architecture Decision Records -- query, write, implement, harden,
  plan, test, status, gaps
```

- [ ] **Step 2: Verify frontmatter is valid YAML**

Read the first 20 lines of the file and confirm the frontmatter parses correctly (no broken indentation, no missing closing `---`).

---

### Task 2: Add `gaps` to Sub-commands table and Examples

**Files:**
- Modify: `.claude/skills/dev-adr/SKILL.md:38-57`

- [ ] **Step 1: Add `gaps` row to the Sub-commands table**

After the `status` row (line 46), add:
```markdown
| `gaps` | Scan multiple ADRs for implementation gaps, rank by severity, suggest fixes |
```

- [ ] **Step 2: Add `gaps` examples to the Examples block**

After the `status` example (line 56), add:
```
/adr gaps ADR-420 ADR-425        # Scan two ADRs for implementation gaps
/adr gaps ADR-400..ADR-430       # Scan a range of ADRs
/adr gaps --status Accepted      # Scan all Accepted ADRs for gaps
```

- [ ] **Step 3: Add `gaps`-specific flags to Options table**

After the `--evolve` row (line 64), add:
```markdown
| `--severity` | (gaps only) Filter to gaps at or above this level: `critical`, `high`, `medium`, `low` |
| `--format` | (gaps only) `summary` = table only, `full` = table + suggested fixes (default: `full`) |
```

---

### Task 3: Add the `## Sub-command: gaps` section

**Files:**
- Modify: `.claude/skills/dev-adr/SKILL.md` — insert new section after the `status` subcommand (after line 251)

- [ ] **Step 1: Write the full `gaps` subcommand spec**

Append the following section after the `status` subcommand's closing content (after line 251):

````markdown
---

## Sub-command: `gaps`

Scan multiple ADRs for implementation gaps. Produces a severity-ranked report with gap classification and suggested fixes.

### Usage

```
/adr gaps <adr-list> [--severity <level>] [--format <format>]
```

### ADR list formats

| Format | Example | Behavior |
|--------|---------|----------|
| Explicit | `gaps ADR-420 ADR-425 ADR-430` | Analyze listed ADRs |
| Range | `gaps ADR-420..ADR-430` | Expand to all ADRs in numeric range that exist |
| Filter | `gaps --status Accepted` | All ADRs matching that status |

### Gap Taxonomy

| Type | Description | Detection |
|------|-------------|-----------|
| **Unimplemented** | ADR specifies a requirement, no code exists | Grep/glob for expected files, functions, endpoints, MCP tools — zero matches |
| **Partial** | Code exists but missing pieces vs. ADR spec | Code found but missing fields, parameters, handlers, or test cases specified in ADR |
| **Conflict** | Two ADRs specify contradictory things for the same target | Same file/function/route modified by multiple ADRs with incompatible specs |
| **Drift** | Implementation diverged from what ADR specifies | Code exists but behavior/structure no longer matches ADR description |

### Severity Matrix

| Severity | Criteria |
|----------|----------|
| **Critical** | Core requirement missing or cross-ADR conflict blocking work |
| **High** | Significant functionality gap (endpoint missing parameters, migration not run) |
| **Medium** | Non-critical missing pieces (test coverage gap, incomplete wiring) |
| **Low** | Convention/documentation drift (functionally equivalent but different pattern) |

### Execution

#### Dispatch strategy

- **1-2 ADRs**: Sequential analysis in the main agent
- **3+ ADRs**: Parallel subagents — one per ADR for individual gap analysis, then merge for cross-ADR conflicts

#### Steps

1. **Parse input** — Resolve ADR list (expand ranges, apply status filters). Search **both** `get_vault_dir()/dev/adrs/` (primary) and `docs/decisions/` (legacy). Skip missing ADRs with a warning: `ADR-NNN: not found — skipped`
2. **Extract requirements per ADR** — Read each ADR and extract a structured checklist:
   - Files to create/modify
   - Functions/classes/endpoints to add
   - MCP tools to register (look for `@mcp.tool` references)
   - Dashboard pages/blocks to wire
   - Migrations/data changes
   - Test cases specified in the Testing section
3. **Scan codebase per requirement** — For each requirement, grep/glob the codebase. Classify:
   - **Unimplemented** — zero matches
   - **Partial** — exists but incomplete vs. spec
   - **Drift** — exists but diverged from spec
4. **Cross-ADR conflict detection** — Build a target map (`file/function/route` → `list of ADRs that touch it`). Flag any target claimed by 2+ ADRs with incompatible specs as **Conflict**
5. **Assign severity** — Apply the severity matrix to each gap
6. **Produce report** — Structured output per the format below

#### Parallel subagent contract

When dispatching subagents (3+ ADRs), each receives:
- The full ADR text
- Instructions to extract requirements and scan code
- The gap taxonomy and severity matrix definitions
- Returns: list of `{requirement, status, gap_type, severity, evidence, suggested_fix}`

Main agent merges results and runs step 4 (cross-ADR conflict detection) on the combined data.

### Output Format

#### Summary header

```
## Gap Analysis: N ADRs scanned

| Severity | Count |
|----------|-------|
| Critical | X     |
| High     | Y     |
| Medium   | Z     |
| Low      | W     |
```

#### Per-ADR gap table

```
### ADR-NNN: Title

| # | Requirement | Gap Type | Severity | Evidence |
|---|-------------|----------|----------|----------|
| 1 | MCP tool `plugin_list` | Unimplemented | Critical | No `@mcp.tool(name="plugin_list")` found |
| 2 | Dashboard page `/admin/plugins` | Partial | High | Page exists but missing 3 of 5 blocks |
| 3 | Migration script | Unimplemented | High | No migration in `src/scripts/` |
```

#### Cross-ADR conflicts

Only shown when conflicts exist:

```
### Cross-ADR Conflicts

| Target | ADRs | Conflict | Severity |
|--------|------|----------|----------|
| `src/config/paths.py:get_plugin_dir()` | ADR-425, ADR-430 | Returns list vs. single path | Critical |
```

#### Suggested fixes (`--format full` only)

After each per-ADR table:

```
**Fixes for ADR-NNN:**
1. Register `plugin_list` tool in `src/mcp/dev_tools.py` — follow pattern of existing `skill_list` tool
2. Add missing blocks to `/admin/plugins` — see ADR-NNN §3 for specs
3. Create migration using `src.config.paths` resolver
```

#### ADRs with no gaps

```
ADR-NNN: Title — No gaps detected
```

### Rules

- Do NOT modify any files — this is a read-only analysis command
- Sort output by severity (Critical first, Low last)
- `--severity` flag filters the final output, not the scanning — scan everything, then filter the report
- `--format summary` omits the "Suggested fixes" sections
- When `--help` is passed, show usage and stop
````

- [ ] **Step 2: Verify the complete SKILL.md is well-formed**

Read the full file and check:
- Frontmatter opens and closes with `---`
- All 8 sub-command sections are present (implement, plan, write, query, harden, test, status, gaps)
- No broken markdown tables
- Sub-commands table matches the number of `## Sub-command:` sections

---

### Task 4: Commit

- [ ] **Step 1: Commit the change**

```bash
git add .claude/skills/dev-adr/SKILL.md
git commit -m "feat(dev-adr): add gaps subcommand for multi-ADR implementation gap analysis"
```
