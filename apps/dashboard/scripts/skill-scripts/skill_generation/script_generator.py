"""
Script Generator Service

Generates Python scripts based on patterns and use cases.
"""

import sys
from pathlib import Path
from typing import Optional


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


def generate_inbox_script(skill_name: str, display_name: str, emoji: str) -> str:
    """Generate inbox processing script."""
    return f'''#!/usr/bin/env python3
"""
Process items from Apple Notes inbox for {display_name} skill.
"""

from pathlib import Path
import sys

# Add project root to path
try:
    from src.config.paths import get_project_root
    sys.path.insert(0, str(get_project_root()))
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))  # fallback

from src.config.paths import get_skill_data_dir


def process_inbox():
    """Process items from Apple Notes inbox."""
    skill_name = "{skill_name}"
    note_name = "{emoji} {display_name} Inbox"
    
    # TODO: Implement inbox processing
    # 1. Read Apple Note
    # 2. Parse pending section
    # 3. Process each item
    # 4. Save to database
    # 5. Update Apple Note
    
    _out(f"Processing inbox for {{skill_name}}")
    data_dir = get_skill_data_dir(skill_name)
    _out(f"Data directory: {{data_dir}}")


if __name__ == "__main__":
    process_inbox()
'''


def generate_database_script(skill_name: str, display_name: str) -> str:
    """Generate database management script."""
    return f'''#!/usr/bin/env python3
"""
Database management for {display_name} skill.
"""

from pathlib import Path
import sys
import yaml

# Add project root to path
try:
    from src.config.paths import get_project_root
    sys.path.insert(0, str(get_project_root()))
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))  # fallback

from src.config.paths import get_skill_data_dir


def load_database(skill_name: str) -> dict:
    """Load skill database."""
    data_dir = get_skill_data_dir(skill_name)
    db_path = data_dir / f"{{skill_name}}.yaml"
    
    if db_path.exists():
        with open(db_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {{}}
    return {{}}


def save_database(skill_name: str, data: dict):
    """Save skill database."""
    data_dir = get_skill_data_dir(skill_name)
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / f"{{skill_name}}.yaml"
    
    with open(db_path, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


if __name__ == "__main__":
    skill_name = "{skill_name}"
    db = load_database(skill_name)
    _out(f"Database loaded: {{len(db)}} items")
'''


def generate_scripts(
    skill_dir: Path, skill_name: str, patterns: list[str], use_cases: Optional[list[str]] = None
) -> tuple[bool, Optional[str]]:
    """
    Generate scripts based on patterns and use cases.

    Args:
        skill_dir: Skill directory path
        skill_name: Skill name (kebab-case)
        patterns: List of patterns (inbox, database, scoring, etc.)
        use_cases: Optional list of use cases for domain-specific scripts

    Returns:
        Tuple of (success, error_message)
    """
    scripts_dir = skill_dir / 'scripts'

    try:
        scripts_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return False, f"Failed to create scripts directory: {e}"

    display_name = skill_name.replace('-', ' ').title()
    emoji = "🔧"  # Default emoji, can be enhanced later

    generated_scripts = []

    # Generate scripts based on patterns
    if 'inbox' in patterns:
        inbox_script = scripts_dir / 'process_inbox.py'
        try:
            inbox_script.write_text(generate_inbox_script(skill_name, display_name, emoji), encoding='utf-8')
            inbox_script.chmod(0o755)  # Make executable
            generated_scripts.append('process_inbox.py')
        except Exception as e:
            return False, f"Failed to write inbox script: {e}"

    if 'database' in patterns:
        db_script = scripts_dir / 'database.py'
        try:
            db_script.write_text(generate_database_script(skill_name, display_name), encoding='utf-8')
            db_script.chmod(0o755)
            generated_scripts.append('database.py')
        except Exception as e:
            return False, f"Failed to write database script: {e}"

    # Generate domain-specific scripts if use cases provided
    if use_cases:
        # TODO: Generate domain-specific scripts based on use cases
        pass

    return True, None
