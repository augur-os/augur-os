# Contributing to Augur OS

Thank you for your interest in contributing to Augur OS! This document provides guidelines and instructions for contributing.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Making Changes](#making-changes)
- [Creating a New Skill](#creating-a-new-skill)
- [Submitting Changes](#submitting-changes)
- [Style Guidelines](#style-guidelines)
- [Testing](#testing)
- [Release Process](#release-process)

---

## Code of Conduct

Please be respectful and constructive in all interactions. We're building tools to help people be more productive - let's embody that spirit in our collaboration.

---

## License and Contribution Terms

Augur OS is licensed under the **MIT License**. By contributing to this project, you agree that your contributions will be licensed under the MIT License.

---

## Getting Started

### Prerequisites

- **Git** for version control
- **Python 3.11+** for scripts and utilities
- **Node.js >= 18** for dashboard
- **Claude.ai account** for testing skills
- **GitHub account** for contributions

### Fork & Clone

```bash
# Fork the repository on GitHub, then:
git clone https://github.com/YOUR_USERNAME/augur-os.git
cd augur-os
```

> **Note:** If you maintain a fork, you can copy `.github/workflows/sync-upstream.yml` from the releases to keep your fork in sync.

---

## Development Setup

### 1. Install Dependencies

```bash
# Python dependencies
pip install -r requirements.txt

# Workspace dependencies
npm install

# (Optional) Skill-specific dependencies
pip install -r skills/{skill}/requirements.txt
```

### 2. Build & Verify

```bash
# Build the dashboard (mounts plugins + compiles)
npm run dashboard:build

# Run Python tests
pytest tests/

# Run dashboard tests
npm run dashboard:test
```

### 3. Run Locally

```bash
# Start dev server
npm run dashboard:dev

# Open http://localhost:3000
```

---

## Project Structure

```
augur-os/
├── skills/                # All skills live here (self-contained)
│   └── {skill-name}/
│       ├── SKILL.md               # Skill definition (frontmatter + instructions)
│       ├── augur.yaml             # MCP tool registration and dashboard wiring
│       ├── scripts/
│       │   └── mcp/               # Python MCP tool implementations
│       ├── augur/
│       │   └── dashboard/         # Optional Next.js dashboard pages
│       │       └── page.tsx
│       └── augur/
│           └── tests/             # Skill-level tests
├── src/
│   ├── config/                    # Path resolution
│   ├── mcp/                       # MCP server package (augur_mcp)
│   └── scripts/                   # Core scripts
├── apps/
│   └── dashboard/                 # Next.js 14 dashboard (App Router)
├── dist/plugins/                  # Packaged plugins for distribution
├── config/                        # System configuration
├── docs/                          # Documentation + ADRs
└── .github/                       # CI/CD workflows + scripts
```

### Required Files for Each Skill

| File | Purpose |
|------|---------|
| `SKILL.md` | Main specification (loaded by AI at runtime) |

### Optional Files

| File | Purpose |
|------|---------|
| `augur.yaml` | MCP tool registration and dashboard wiring |
| `augur/dashboard/` | Next.js UI components (pages, tabs) |
| `scripts/mcp/` | MCP tool implementations |
| `augur/tests/` | Skill-level tests |
| `assets/seed-data/` | Template data |

---

## Making Changes

### Branch Naming

```
feature/{skill-name}-{description}
fix/{skill-name}-{description}
docs/{description}
```

Examples:
- `feature/knowledge-semantic-search`
- `fix/scraper-duplicate-detection`
- `docs/contributing-guide`

### Commit Messages

Follow conventional commits:

```
type(scope): description

[optional body]

[optional footer]
```

Types:
- `feat` - New feature
- `fix` - Bug fix
- `docs` - Documentation only
- `refactor` - Code restructuring
- `test` - Adding tests
- `chore` - Maintenance tasks

Examples:
```
feat(knowledge): add semantic search module
fix(scraper): handle URLs with special characters
docs: update contributing guidelines
```

---

### Editing AI Instructions

> [!WARNING]
> **DO NOT** edit `CLAUDE.md`, `CODEX.md`, `.cursorrules`, or other generated instruction files directly.
>
> They are generated from `docs/agent-rules.md` and will be overwritten on sync.

**Correct Workflow:**
```bash
# 1. Edit source rules (single source of truth)
vim docs/agent-rules.md

# 2. Generate instructions for all IDEs
python3 src/scripts/generate_instructions.py

# 3. Verify exports
git status
# Should show changes to:
#   CLAUDE.md, CODEX.md
#   .cursorrules, .windsurfrules, .cursor/rules/augur.mdc
#   .antigravity/instructions.md
#   .vscode/augur-instructions.md
#   .github/copilot-instructions.md

# 4. Commit all changed files
git add docs/agent-rules.md CLAUDE.md CODEX.md .cursorrules .windsurfrules .cursor/rules/augur.mdc \
  .antigravity/instructions.md .vscode/augur-instructions.md .github/copilot-instructions.md
git commit -m "docs: update AI instructions"
```

**Why the Generator?**
- Single source of truth in `docs/agent-rules.md`
- Consistent outputs across IDEs and agents
- Easy to update and review

---

## Creating a New Skill

### 1. Manual Creation

Create the minimum required structure:

```
skills/my-skill/
├── SKILL.md               # Skill definition (REQUIRED)
├── augur.yaml             # MCP tool registration
├── scripts/
│   └── mcp/               # MCP tools (optional)
│       └── __init__.py
├── augur/
│   └── dashboard/         # Dashboard pages (optional)
│       └── page.tsx
└── augur/
    └── tests/             # Tests (optional)
```

### 2. SKILL.md Template

```markdown
---
name: my-skill
description: Brief description of what the skill does
x-augur-hub: dev
---

# My Skill

[Full skill specification following existing patterns]

## Key Capabilities
1. Feature 1
2. Feature 2

## Commands
- `/my-command` - Main command

## Workflow
[Detailed workflow steps]
```

See [Creating Skills](docs/creating-skills.md) for full details.

---

## Submitting Changes

### Pull Request Process

1. **Create a branch** from `main`
2. **Make changes** following style guidelines
3. **Test locally** with Claude
4. **Update documentation** if needed
5. **Submit PR** with clear description

### PR Description Template

```markdown
## Summary
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation
- [ ] Refactoring

## Testing Done
- [ ] Tested with Claude Code
- [ ] Ran validation scripts
- [ ] Updated relevant docs

## Related Issues
Fixes #123
```

### AI-Assisted Contributions

AI-generated PRs are welcome. Please mark them in the PR title or description (e.g., `[AI] feat: ...`). All testing and quality requirements apply regardless of how the code was written.

### Review Process

1. Automated checks run (YAML validation, Python syntax)
2. Maintainer reviews code
3. Address feedback
4. Merge when approved

---

## Style Guidelines

### Markdown

- Use ATX headers (`#`, `##`, `###`)
- One sentence per line for easier diffs
- Use fenced code blocks with language hints
- Tables for structured data
- Links with descriptive text: `[knowledge skill](skills/knowledge/)`

### YAML

- 2-space indentation
- Quote strings with special characters
- Use comments for complex configurations
- Maintain consistent field ordering
- Example:
  ```yaml
  version: 1.0.0
  updated: 2025-11-25
  skill: skill-name
  codename: Descriptive Name
  status: stable  # stable, beta, alpha, deprecated
  ```

### Python

**General**:
- Follow PEP 8
- Type hints encouraged for function signatures
- Docstrings for public functions (Google style)
- Keep scripts focused and simple (single responsibility)

**Naming**:
- `snake_case` for functions and variables
- `PascalCase` for classes
- `UPPER_CASE` for constants
- Descriptive names: `process_job_url()` not `proc()`

**Example**:
```python
def load_database(db_path: str) -> dict:
    """Load YAML database from filesystem.

    Args:
        db_path: Absolute path to YAML file

    Returns:
        Parsed database dictionary

    Raises:
        FileNotFoundError: If database doesn't exist
    """
    with open(db_path) as f:
        return yaml.safe_load(f)
```

### Skill Documentation

- Clear, actionable commands
- Real examples with expected output
- Token usage estimates for heavy operations
- Troubleshooting sections for common issues

---

## Testing

### Manual Testing

1. Load skill in Claude Code
2. Test all documented commands
3. Verify file outputs
4. Check error handling

### Validation Scripts

```bash
# Audit hardcoded paths
python .github/scripts/audit_paths.py .

# Validate repository structure
python .github/scripts/validate_structure.py

# Run full lint + build
cd apps/dashboard && npm run lint && npm run build
```

### CI Checks

GitHub Actions automatically validates:
- Required files exist
- YAML syntax is valid
- Python scripts compile

---

## Release Process

### For Maintainers

1. **Update CHANGELOG.md** with new version entry
2. **Create release** via GitHub Releases
3. **Tag the release** with semantic version

### Version Bumping

- **patch** (1.0.0 -> 1.0.1): Bug fixes, minor docs
- **minor** (1.0.0 -> 1.1.0): New features, non-breaking
- **major** (1.0.0 -> 2.0.0): Breaking changes

---

## Questions?

- **Issues**: https://github.com/augur-os/augur-os/issues
- **Discussions**: https://github.com/augur-os/augur-os/discussions

---

Thank you for contributing!
