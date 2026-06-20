#!/usr/bin/env python3
"""
Claude Skills - Skill Generator

Creates a new skill with proper structure based on learned patterns.

Usage:
    python skill_generator.py --name "expense-tracker" --patterns inbox,database
"""

import argparse
from datetime import datetime
from pathlib import Path

import sys


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


try:
    from src.config.paths import get_project_root
    REPO_ROOT = get_project_root()
except ImportError:
    REPO_ROOT = Path(__file__).parent.parent.parent  # fallback
PACKAGES_DIR = REPO_ROOT / 'plugins'
TEMPLATES_DIR = Path(__file__).parent.parent / 'templates'

# Emoji mapping for skill types
EMOJI_MAP = {
    'tracker': '📊',
    'capture': '💡',
    'automation': '⚙️',
    'list': '📚',
    'memos': '🎙️',
    'notes': '📝',
    'calendar': '📅',
    'finance': '💰',
    'health': '❤️',
    'default': '🔧',
}


def get_emoji(name: str) -> str:
    """Get appropriate emoji based on skill name."""
    for key, emoji in EMOJI_MAP.items():
        if key in name.lower():
            return emoji
    return EMOJI_MAP['default']


def create_skill_structure(name: str, patterns: list, description: str = '', layer: str = 'vertical'):
    """Create the full skill directory structure."""
    # Support layer selection: factory, horizontal, or vertical
    if layer not in ['factory', 'horizontal', 'vertical']:
        layer = 'vertical'  # Default to vertical

    skill_dir = PACKAGES_DIR / layer / name

    if skill_dir.exists():
        _out(f"❌ Skill '{name}' already exists at {skill_dir}")
        return False

    # Create directories
    (skill_dir / 'skill-package').mkdir(parents=True)
    (skill_dir / 'skill-package' / 'modules').mkdir()
    (skill_dir / 'skill-package' / 'tests').mkdir()
    (skill_dir / 'augur').mkdir(parents=True, exist_ok=True)

    emoji = get_emoji(name)
    display_name = name.replace('-', ' ').title()

    # Generate SKILL.md
    skill_md = generate_skill_md(name, emoji, display_name, patterns, description)
    (skill_dir / 'skill-package' / 'SKILL.md').write_text(skill_md)

    # Generate version.yaml
    version_yaml = f"""version: 1.0.0
updated: {datetime.now().strftime('%Y-%m-%d')}
skill: {name}
codename: "Initial Release"
"""
    (skill_dir / 'augur' / 'version.yaml').write_text(version_yaml)

    # Generate README.md
    readme = f"""# {emoji} {display_name}

{description or f'A Claude skill for {display_name.lower()}.'}

## Quick Start

```
process {name.replace('-', ' ')}
```

## Patterns

- {'Apple Notes Inbox' if 'inbox' in patterns else 'Direct input'}
- {'YAML Database' if 'database' in patterns else 'File-based storage'}
{'- Scoring System' if 'scoring' in patterns else ''}

## Version

See `augur/version.yaml` for version info.
"""
    (skill_dir / 'README.md').write_text(readme)

    # Generate CHANGELOG.md
    changelog = f"""# Changelog

## [1.0.0] - {datetime.now().strftime('%Y-%m-%d')}

- Initial release
- {', '.join(patterns)} patterns implemented
"""
    (skill_dir / 'CHANGELOG.md').write_text(changelog)

    # Generate test files
    conftest_content = generate_conftest(name)
    (skill_dir / 'skill-package' / 'tests' / 'conftest.py').write_text(conftest_content)

    smoke_test_content = generate_smoke_test(name)
    (skill_dir / 'skill-package' / 'tests' / f'test_{name}_smoke.py').write_text(smoke_test_content)

    _out(f"✅ Created skill: {skill_dir}")
    _out("   - SKILL.md")
    _out("   - version.yaml")
    _out("   - README.md")
    _out("   - CHANGELOG.md")
    _out("   - tests/conftest.py")
    _out(f"   - tests/test_{name}_smoke.py")

    # Create user-data directory using centralized path config
    from src.config.paths import get_skill_data_dir

    user_data_dir = get_skill_data_dir(name)
    if not user_data_dir.exists():
        user_data_dir.mkdir(parents=True)
        _out(f"✅ Created user-data: {user_data_dir}")

    # Suggest Apple Note creation
    if 'inbox' in patterns:
        _out(f"\n📝 Create Apple Note: '{emoji} {display_name} Inbox'")

    return True


def generate_skill_md(name: str, emoji: str, display_name: str, patterns: list, description: str) -> str:
    """Generate SKILL.md content based on patterns."""

    # Base template
    content = f"""---
name: {name}
description: {description or f'{display_name} skill with {", ".join(patterns)} patterns.'}
---

# {emoji} {display_name}

{description or f'A Claude skill for {display_name.lower()}.'}

## 🌟 Key Capabilities
"""

    # Add capabilities based on patterns
    cap_num = 1
    if 'inbox' in patterns:
        content += f"{cap_num}. **Apple Notes Inbox**: Add items to \"{emoji} {display_name} Inbox\" note\n"
        cap_num += 1
    if 'database' in patterns:
        content += f"{cap_num}. **YAML Database**: Persistent storage with stats tracking\n"
        cap_num += 1
    if 'scoring' in patterns:
        content += f"{cap_num}. **Scoring System**: Multi-dimensional scoring with tiers\n"
        cap_num += 1

    # Storage configuration
    content += f"""
## ⚙️ Storage Configuration

**User Data Location**: Determined by `src/lib/config/paths.py`
Path: `augur/{name}/` (or monorepo `data/{name}/`)

```
{name}/
├── {name}.yaml           # Main database
├── config.yaml           # Local config overrides
└── output/               # Generated outputs
```

## 🚀 Commands

| Command | Action |
|---------|--------|
| `process {name.replace('-', ' ')}` | Process items from inbox |
| `show {name.replace('-', ' ')}` | Display current items |
| `search: [query]` | Find by keyword |
"""

    # Add inbox workflow if applicable
    if 'inbox' in patterns:
        content += f"""
## 📋 Workflow: Apple Notes Inbox

### Step 1: Read Inbox

```python
def process_inbox():
    note_content = get_note_content("{emoji} {display_name} Inbox")
    # Parse pending section
    # Process items
    # Update processed section
```

### Step 2: Process Items

For each item in inbox:
1. Validate/parse input
2. {'Score and classify' if 'scoring' in patterns else 'Process content'}
3. Save to database
4. Update Apple Note

### Step 3: Update Apple Note

Move processed items to Processed section with timestamp.
"""

    # Footer
    content += f"""
---

**Version**: 1.0.0
**Last Updated**: {datetime.now().strftime('%Y-%m-%d')}
**Patterns**: {', '.join(patterns)}
"""

    return content


def generate_conftest(skill_name: str) -> str:
    """Generate conftest.py with common fixtures."""
    return f'''"""
Pytest configuration and fixtures for {skill_name} skill tests.
"""

import pytest
from pathlib import Path


@pytest.fixture
def skill_dir():
    """Return the skill directory path."""
    return Path(__file__).parent.parent


@pytest.fixture
def skill_name():
    """Return the skill name."""
    return "{skill_name}"
'''


def generate_smoke_test(skill_name: str) -> str:
    """Generate smoke test file."""
    skill_display = skill_name.replace('-', ' ').title()
    return f'''"""
Smoke tests for {skill_display} skill.

These tests validate basic skill structure and configuration.
"""

import yaml
import re
from pathlib import Path
import pytest


def parse_yaml_frontmatter(content: str):
    """Parse YAML frontmatter from markdown content."""
    if not content.startswith("---"):
        return None, content
    
    match = re.match(r"^---\\n(.*?)\\n---\\n?(.*)", content, re.DOTALL)
    if not match:
        return None, content
    
    try:
        frontmatter = yaml.safe_load(match.group(1))
        return frontmatter, match.group(2)
    except yaml.YAMLError:
        return None, content


def test_skill_md_exists(skill_dir):
    """SKILL.md MUST exist."""
    # Check both skill-package subdirectory and root
    skill_md = skill_dir / "skill-package" / "SKILL.md"
    if not skill_md.exists():
        skill_md = skill_dir / "SKILL.md"
    assert skill_md.exists(), f"Missing SKILL.md in {{skill_dir}}"


def test_skill_md_has_frontmatter(skill_dir):
    """SKILL.md MUST have YAML frontmatter."""
    skill_md = skill_dir / "skill-package" / "SKILL.md"
    if not skill_md.exists():
        skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        pytest.skip("SKILL.md not found")
    
    content = skill_md.read_text()
    frontmatter, _ = parse_yaml_frontmatter(content)
    
    assert frontmatter is not None, "SKILL.md must have YAML frontmatter"


def test_skill_md_has_name(skill_dir, skill_name):
    """SKILL.md frontmatter MUST have 'name' field matching skill name."""
    skill_md = skill_dir / "skill-package" / "SKILL.md"
    if not skill_md.exists():
        skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        pytest.skip("SKILL.md not found")
    
    content = skill_md.read_text()
    frontmatter, _ = parse_yaml_frontmatter(content)
    
    if frontmatter is None:
        pytest.skip("No frontmatter found")
    
    assert "name" in frontmatter, "SKILL.md must have 'name' field"
    assert frontmatter["name"] == skill_name, f"SKILL.md 'name' should be '{skill_name}'"


def test_skill_md_has_description(skill_dir):
    """SKILL.md frontmatter MUST have 'description' field."""
    skill_md = skill_dir / "skill-package" / "SKILL.md"
    if not skill_md.exists():
        skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        pytest.skip("SKILL.md not found")
    
    content = skill_md.read_text()
    frontmatter, _ = parse_yaml_frontmatter(content)
    
    if frontmatter is None:
        pytest.skip("No frontmatter found")
    
    assert "description" in frontmatter, "SKILL.md must have 'description' field"
    assert len(frontmatter["description"]) >= 20, "Description should be at least 20 characters"


def test_version_yaml_exists(skill_dir):
    """version.yaml MUST exist."""
    # Check augur/ subdirectory (new location)
    version_file = skill_dir / "augur" / "version.yaml"
    assert version_file.exists(), f"Missing version.yaml in {{skill_dir}}"


def test_version_yaml_is_valid(skill_dir):
    """version.yaml MUST be valid YAML."""
    version_file = skill_dir / "augur" / "version.yaml"
    if not version_file.exists():
        pytest.skip("version.yaml not found")

    content = version_file.read_text()
    try:
        data = yaml.safe_load(content)
        assert data is not None, "version.yaml is empty"
    except yaml.YAMLError as e:
        pytest.fail(f"version.yaml has invalid YAML: {{e}}")


def test_version_yaml_has_required_fields(skill_dir, skill_name):
    """version.yaml MUST have required fields."""
    version_file = skill_dir / "augur" / "version.yaml"
    if not version_file.exists():
        pytest.skip("version.yaml not found")
    
    content = version_file.read_text()
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError:
        pytest.skip("Invalid YAML")
    
    assert "version" in data, "version.yaml must have 'version' field"
    assert "updated" in data, "version.yaml must have 'updated' field"
    assert "skill" in data, "version.yaml must have 'skill' field"
    assert data["skill"] == skill_name, f"version.yaml 'skill' should be '{skill_name}'"
    
    # Validate semver format
    version = str(data["version"])
    semver_pattern = r"^\\d+\\.\\d+\\.\\d+(-[a-zA-Z0-9.]+)?(\\+[a-zA-Z0-9.]+)?$"
    assert re.match(semver_pattern, version), f"Version '{{version}}' doesn't follow semver format"


def test_modules_directory_exists(skill_dir):
    """modules/ directory SHOULD exist if skill uses modules."""
    # Check both skill-package subdirectory and root
    modules_dir = skill_dir / "skill-package" / "modules"
    if not modules_dir.exists():
        modules_dir = skill_dir / "modules"
    # This is optional, so we just check if it exists when expected
    if modules_dir.exists():
        assert modules_dir.is_dir(), "modules should be a directory"
'''


def main():
    parser = argparse.ArgumentParser(description='Generate new Claude Skill')
    parser.add_argument('--name', required=True, help='Skill name (kebab-case)')
    parser.add_argument(
        '--patterns', default='inbox,database', help='Patterns to include (comma-separated: inbox,database,scoring)'
    )
    parser.add_argument('--description', default='', help='Skill description')
    parser.add_argument(
        '--layer',
        default='vertical',
        choices=['factory', 'horizontal', 'vertical'],
        help='Layer: factory (role agents), horizontal (capabilities), vertical (applications)',
    )

    args = parser.parse_args()

    patterns = [p.strip() for p in args.patterns.split(',')]

    create_skill_structure(args.name, patterns, args.description, args.layer)


if __name__ == '__main__':
    main()
