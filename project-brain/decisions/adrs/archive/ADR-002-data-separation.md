---
status: Superseded
date: '2025-01-01'
deciders:
- Core team
related: []
hub: null
tags:
- separate
- code
- data
- repositories
superseded_by: null
---

# ADR-002: Separate Code and Data Repositories

## Context

Augur manages both application code (Python skills, TypeScript dashboard, configs) and user data (job applications, recipes, notes, medical records). During early development, mixing code and user data in a single repository caused problems:

1. **Privacy risks**: User data could accidentally be committed to a public code repo
2. **Git noise**: Frequent data updates cluttered commit history with non-code changes
3. **Deployment complexity**: Pushing code changes required excluding user data
4. **Portability issues**: Moving the system to a new machine meant untangling code from data
5. **Backup concerns**: Different backup strategies needed for code (GitHub) vs data (local/encrypted)

## Decision

Maintain **two separate Git repositories**:

### Code Repository (`augur/`)
- Python plugins, TypeScript code, configurations
- Public or private based on open-source strategy
- Pushed to GitHub for collaboration
- Contains no user-specific data

### Data Repository (`augur-data/`)
- YAML databases, Markdown documents, user outputs
- Always private/local
- Can use separate backup strategy (iCloud, encrypted backup)
- Contains no executable code (except workflow definitions)

### Path Resolution

All code must use `src/lib.config.paths` for path resolution:
```python
from src/lib.config.paths import (
    get_user_data_base,    # → augur-data/
    get_project_root,      # → augur/
    get_skill_data_dir,    # → augur-data/{skill}/
)
```

### Enforcement

- Pre-commit hooks (`audit_paths.py`) reject hardcoded paths
- CI fails if `/Users/` or absolute paths appear in code
- Sync script (`sync_repos.py`) commits both repos atomically

## Consequences

### Positive

- **Privacy by default**: User data never accidentally reaches public repos
- **Clean git history**: Code changes are separate from data updates
- **Easy migration**: Move data repo to new machine without touching code
- **Flexible backup**: Different retention policies for code vs data
- **Open source ready**: Code repo can be made public without exposing personal data

### Negative

- **Two repos to manage**: Need to remember to sync both
- **Path indirection**: Can't use simple relative paths; must use path functions
- **Initial setup complexity**: New users must set up both repos
- **Cross-repo references**: Skills need to know where their data lives

### Neutral

- YAML chosen as primary data format (human-readable, git-diff friendly)
- Configuration lives in code repo; user configuration in data repo

## Alternatives Considered

### Alternative 1: Single Repo with .gitignore

Keep everything in one repo, use `.gitignore` for data directories. Rejected because:
- Easy to accidentally commit sensitive data
- `.gitignore` can be overridden with `-f`
- No protection against `git add .` mistakes
- Backup strategies still conflated

### Alternative 2: Encrypted Data in Same Repo

Encrypt user data before committing to same repo. Rejected because:
- Complexity of encryption/decryption workflow
- Git diffs useless for encrypted files
- Key management overhead
- Still conflates code and data lifecycles

### Alternative 3: Database Instead of Files

Store user data in SQLite or similar. Rejected because:
- Less human-readable (can't edit in text editor)
- Git-unfriendly (binary diffs)
- Overkill for personal data volumes
- Loses benefit of Markdown for documents

## References

- Agent Rules - Data Separation
- File Structure Guide
- `src/config/paths.py` - Implementation of path resolution
