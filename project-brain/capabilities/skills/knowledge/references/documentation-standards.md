# Skill Documentation Standards

## Overview

This document defines the required structure and quality standards for skill documentation in the Augur ecosystem.

---

## Required Files

Every skill MUST have:

1. **SKILL.md** - Primary documentation (<150 lines)
2. **ACCEPTANCE_CRITERIA.md** - Completion checklist
3. **version.yaml** - Version and metadata

Every skill SHOULD have:

4. **references/** - Detailed workflow documentation
5. **README.md** - User-facing overview (optional)
6. **CHANGELOG.md** - Version history (optional)

---

## SKILL.md Structure

### Required Sections

```markdown
---
name: skill-name
version: 0.1.0
description: One-line description with trigger phrases
triggers:
  - trigger phrase 1
  - trigger phrase 2
---

# [Emoji] Skill Name

## Overview
2-3 sentences on responsibility and scope.

## Capabilities

- Capability 1: Brief description of what this enables
- Capability 2: Brief description of what this enables
- Capability 3: Brief description of what this enables

> ⚠️ **CRITICAL**: The Capabilities section is REQUIRED and must use
> bullet points starting with `- `. This section is parsed by the registry
> to expose skill capabilities to the Skills Manager and MCP tools.

## Commands
| Command | Action |
Table of trigger → action mappings.

## Workflows (if complex)
### 1. Primary Workflow
**Trigger**: What activates this
**Steps**: Numbered list
**Output**: What gets produced

## Module Loading (if applicable)
| Trigger | Load |
Table of when to load reference docs.

## Storage
Path and structure of data files.

## Constraints (optional)
Important limitations and rules.

## References (optional)
Links to reference docs.

---
**Version**: X.Y.Z | **Patterns**: list
```

### Quality Checklist

- [ ] **Length**: Under 150 lines (use references/ for details)
- [ ] **Clarity**: Each section has clear purpose
- [ ] **Frontmatter**: YAML metadata with name, version, description, triggers
- [ ] **Capabilities**: Bullet list with `- ` format (REQUIRED for registry)
- [ ] **Commands**: All trigger phrases documented in table format
- [ ] **Workflows**: Step-by-step procedures (if complex skill)
- [ ] **Storage**: Data location specified
- [ ] **Version**: Footer includes version and patterns

---

## ACCEPTANCE_CRITERIA.md Structure

### Template

```markdown
# Acceptance Criteria: skill-name

## Capabilities
- [x] Capability 1 - Description
- [x] Capability 2 - Description
- [ ] Capability 3 - Not yet implemented

## Commands Implemented
- [x] `command1` - Description
- [x] `command2` - Description
- [ ] `command3` - Planned

## Storage Structure
- [x] Primary data directory
- [x] File format defined
- [ ] Migration scripts (if needed)

## Reference Docs
- [x] `references/workflow.md`
- [ ] `references/advanced.md` (TODO)

## Readiness
- [x] SKILL.md complete (<150 lines)
- [x] Reference workflows documented
- [x] Data storage configured
- [ ] Unit tests (if applicable)
- [x] Documentation up to date

## Version
- Current: X.Y.Z
- Last updated: YYYY-MM-DD
```

### Purpose
- Track implementation progress
- Identify missing features
- Guide development priorities
- Document completion status

---

## version.yaml Structure

### Template

```yaml
name: skill-name
version: X.Y.Z
description: One-line description
status: active | deprecated | experimental
created: YYYY-MM-DD
updated: YYYY-MM-DD
patterns:
  - pattern1
  - pattern2
dependencies:
  - dependency1
  - dependency2 (or "None")
storage:
  location: ~/Projects/augur-data/skill-name/
  format: yaml | markdown | json
```

### Fields Explained

- **name**: Skill identifier (kebab-case)
- **version**: Semantic version (MAJOR.MINOR.PATCH)
- **description**: One-line summary
- **status**:
  - `active` - Production ready
  - `experimental` - Under development
  - `deprecated` - No longer maintained
- **patterns**: Architecture patterns used (inbox, database, scoring, etc.)
- **dependencies**: External dependencies or "None"
- **storage**: Data location and format

---

## Reference Documentation Standards

### File Naming
- Use descriptive kebab-case names
- Examples:
  - `architecture-workflow.md`
  - `competitor-research.md`
  - `pricing-strategy.md`

### Structure
Each reference doc should have:
1. **Title**: Clear H1 heading (Required)
2. **Overview**: Purpose of the document
3. **Sections**: Logical breakdown with H2/H3
4. **Examples**: Code snippets or templates
5. **Links**: Related documents

### Submodules (modules/ and references/)
- Files in these directories MUST have an H1 title (e.g., `# Module Name`) within the first 30 lines.
- Files should not be empty stubs.
- Use `references/` for static documentation and `modules/` for functional subcomputers or prompts.

### Length
- No strict limit (SKILL.md is the constrained one)
- Break into multiple files if >500 lines
- Prefer depth over breadth

---

## Documentation Quality Levels

### Level 1: Minimal (Stub)
- SKILL.md exists but <50 lines
- No reference docs
- No acceptance criteria
- **Status**: Not production-ready

### Level 2: Functional
- SKILL.md complete (<150 lines)
- Basic workflows documented
- Acceptance criteria partial
- **Status**: Works but needs refinement

### Level 3: Production
- SKILL.md polished
- Reference docs complete
- Acceptance criteria 80%+ checked
- version.yaml accurate
- **Status**: Ready for use

### Level 4: Exemplary (Reference Quality)
- All Level 3 requirements
- Multiple reference docs
- Examples and templates
- Cross-references to other skills
- **Status**: Best practice example

**Examples**:
- business-expert (Level 4)
- frontend (Level 3)
- architect (Level 3 after refactor)
- librarian (Level 3 after refactor)

---

## Common Documentation Anti-Patterns

### ❌ Avoid

1. **Over-detailed SKILL.md**
   - Don't: 300-line SKILL.md with everything
   - Do: <150 lines, link to references/

2. **Missing Trigger Phrases**
   - Don't: Commands section without examples
   - Do: List all trigger phrases in Commands table

3. **Vague Workflows**
   - Don't: "Process the data appropriately"
   - Do: Numbered steps with specific actions

4. **No Storage Documentation**
   - Don't: Assume user knows where data lives
   - Do: Explicit paths in Storage section

5. **Stale Acceptance Criteria**
   - Don't: Leave completed items unchecked
   - Do: Update checklist as work progresses

6. **Version Mismatch**
   - Don't: SKILL.md says 0.3.0, version.yaml says 0.1.0
   - Do: Keep version synchronized

---

## Documentation Review Checklist

Use this when reviewing skill documentation:

### Structure
- [ ] SKILL.md exists and is <150 lines
- [ ] All required sections present
- [ ] Frontmatter YAML correct
- [ ] Version footer matches version.yaml

### Content
- [ ] Commands clearly documented
- [ ] At least one workflow with steps
- [ ] Storage location specified
- [ ] References to detailed docs

### Metadata
- [ ] ACCEPTANCE_CRITERIA.md exists
- [ ] version.yaml exists and valid
- [ ] Version numbers consistent

### References
- [ ] references/ directory exists (if needed)
- [ ] Reference docs are well-structured
- [ ] No broken links

### Quality
- [ ] Clear, concise writing
- [ ] No typos or formatting errors
- [ ] Examples provided where helpful
- [ ] Constraints/limitations noted

---

## Versioning Guidelines

### When to Bump Version

**MAJOR (X.0.0)**: Breaking changes
- Changed command syntax
- Removed features
- Incompatible storage format

**MINOR (0.X.0)**: New features
- Added commands
- New workflows
- Enhanced capabilities

**PATCH (0.0.X)**: Bug fixes and docs
- Fixed bugs
- Updated documentation
- Refactored code (no behavior change)

### Update Locations
When bumping version, update:
1. version.yaml
2. SKILL.md footer
3. ACCEPTANCE_CRITERIA.md "Version" section
4. CHANGELOG.md (if it exists)

---

## Skill Documentation Lifecycle

### 1. Creation (Scaffold)
- Generate skeleton with next-skill
- Fill in basic SKILL.md
- Create ACCEPTANCE_CRITERIA.md with TODOs

### 2. Development
- Implement features
- Document workflows as you build
- Update acceptance criteria

### 3. Refinement
- Ensure SKILL.md is <150 lines
- Move details to references/
- Complete acceptance criteria

### 4. Production
- All core features working
- Documentation complete
- Version 1.0.0 release

### 5. Maintenance
- Update docs with new features
- Fix inaccuracies
- Deprecate outdated sections

---

## Enforcement Strategy

### For New Skills
- Use next-skill to generate compliant structure
- Review before merging to main
- Require all Level 3 standards

### For Existing Skills
- **Don't** retroactively enforce on working skills
- **Do** refactor when adding major features
- **Do** apply standards to new agents in factory/

### Tools
- `doc standards: [skill]` - Run compliance check
- `.github/scripts/` - Potential linter (future)
- CI checks (future) - Fail if SKILL.md >150 lines

---

## Examples by Quality Level

### Level 4: business-expert
- 139 lines in SKILL.md
- 3 reference docs
- Complete acceptance criteria
- Active version tracking

### Level 3: architect (after refactor)
- 170 lines in SKILL.md
- 2 reference docs
- Full acceptance criteria
- Clear workflows

### Level 1: Old librarian (before refactor)
- 16 lines in SKILL.md
- No references
- Stub acceptance criteria
- Not usable

---

## Project-Level Documentation (`docs/`)

### Flat Structure
The `docs/` folder uses a flat structure with minimal nesting:

```
docs/
├── agent-rules.md              # Agent instructions (primary)
├── vision.md                   # Project philosophy & goals
├── developer-guide.md          # Developer onboarding
├── user-guide.md               # User documentation
├── architecture-*.md           # Architecture docs (prefixed)
├── decisions/                  # ADRs only
│   ├── README.md
│   ├── TEMPLATE.md
│   └── ADR-NNN-title.md        # Sequential numbering
├── archive/                    # Outdated docs (preserved)
└── guides/                     # How-to guides
```

### ADR (Architecture Decision Records)
- **Location**: `get_adr_dir()/ADR-NNN-title.md` (`get_documents_dir()/adrs/`)
- **Numbering**: Sequential. Check latest: `ls $(python3 -c "from src.config.paths import get_adr_dir; print(get_adr_dir())") | grep ADR | tail -1`
- **Template**: Copy `get_adr_dir()/TEMPLATE.md`
- **When to create**: Major architectural changes, new patterns, breaking changes

### Documentation Cleanup
- Archive outdated docs to `docs/archive/` (don't delete)
- Keep `docs/` flat - max 1 level nesting (decisions/, archive/, guides/)
- Prefix architecture docs with `architecture-` when at root level

---

## Getting Help

If documentation standards are unclear:
1. Review `business-expert` as reference
2. Check this document
3. Ask architect agent for design guidance
4. Run `doc standards: [skill]` for automated review
