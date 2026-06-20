title: Documentation Module
summary: Documentation generation and management logic
last_updated: "2026-01-21"
note: Recovered during plugin migration
---

# Documentation Module v1.0

## Purpose

Manage system documentation including skill audits, API documentation generation, document indexing, and action button management.

## Scripts

### audit_skills.py
Audits all skills in the system for documentation completeness and consistency.

```python
# Key functions:
def audit_all_skills() -> AuditReport
def check_skill_documentation(skill_path: Path) -> SkillAudit
def generate_audit_report(audits: list) -> Report
```

### generate_api_docs.py
Generates API documentation from route files and type definitions.

```python
# Key functions:
def generate_api_docs(plugin_path: Path) -> APIDocumentation
def extract_routes(api_dir: Path) -> list[Route]
def format_documentation(routes: list) -> str
```

### index_docs.py
Indexes documentation files for search and navigation.

```python
# Key functions:
def index_all_docs() -> SearchIndex
def update_index(doc_path: Path) -> None
def search_docs(query: str) -> list[DocResult]
```

### manage_action_buttons.py
Manages action buttons across dashboards.

```python
# Key functions:
def discover_action_buttons() -> list[ActionButton]
def validate_page_buttons(page: str) -> ValidationResult
def register_action_button(button: ActionButton) -> None
```

## Audit Checks

| Check | Description |
|-------|-------------|
| SKILL.md exists | Verify SKILL.md file present |
| README.md exists | Verify README.md file present |
| Scripts documented | Check script docstrings |
| Modules complete | Verify modules have required fields |
| Version tracked | Check version.yaml exists |

## Module Version

**Version**: v1.0
**Last Updated**: January 21, 2026
**Status**: Recovered during migration
