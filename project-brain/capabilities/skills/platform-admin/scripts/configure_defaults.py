#!/usr/bin/env python3
"""
Configure sensible defaults for Augur.

Eliminates configuration decisions by setting up:
- LLM configuration (IDE mode by default)
- Data directory paths
- Skill preferences
- Dashboard settings
"""


import importlib.util as _augur_importlib_util
import sys as _augur_sys
from pathlib import Path as _AugurPath

_augur_bootstrap_start = _AugurPath(__file__).resolve()
for _augur_bootstrap_parent in (_augur_bootstrap_start.parent, *_augur_bootstrap_start.parents):
    _augur_bootstrap_path = _augur_bootstrap_parent / "daemon" / "scripts" / "bootstrap_paths.py"
    if _augur_bootstrap_path.is_file():
        break
else:
    raise RuntimeError(f"Unable to locate shared skill bootstrap from {_augur_bootstrap_start}")

_augur_bootstrap_spec = _augur_importlib_util.spec_from_file_location(
    "_augur_shared_bootstrap_paths", _augur_bootstrap_path
)
if _augur_bootstrap_spec is None or _augur_bootstrap_spec.loader is None:
    raise RuntimeError(f"Unable to load shared skill bootstrap from {_augur_bootstrap_path}")
_augur_bootstrap_module = _augur_importlib_util.module_from_spec(_augur_bootstrap_spec)
_augur_sys.modules[_augur_bootstrap_spec.name] = _augur_bootstrap_module
_augur_bootstrap_spec.loader.exec_module(_augur_bootstrap_module)
_augur_bootstrap_module.ensure_project_paths(__file__)
import sys
from pathlib import Path
import yaml
from src.config.paths import get_project_root


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


# ═══════════════════════════════════════════════════════════════════════════════
# DEFAULTS
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_LLM_CONFIG = {
    "mode": "ide",
    "provider": None,
    "model": None,
    "temperature": 0.7,
    "max_tokens": 4096,
}

DEFAULT_PATHS = {
    "data_dir": "~/Projects/augur",
    "skills_dir": "plugins",
    "dashboard_dir": "dashboard",
}

DEFAULT_PREFERENCES = {
    "auto_confirm_threshold": 0.7,
    "default_skill": "platform-admin",
    "night_shift_enabled": True,
    "retrospectives_enabled": True,
}


def get_repo_root() -> Path:
    """Find the repository root."""
    current = Path(__file__).resolve()
    for parent in [current] + list(current.parents):
        if (parent / ".git").exists():
            return parent
    return Path.cwd()


def get_data_dir() -> Path:
    """Get or create data directory."""
    data_paths = [
        get_project_root(),
        get_project_root(),
    ]

    for p in data_paths:
        if p.exists():
            return p

    return data_paths[0]


def create_llm_config(data_dir: Path) -> Path:
    """Create default LLM configuration."""
    config_path = data_dir / "config" / "llm.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)

    if config_path.exists():
        _out(f"  ✓ LLM config exists: {config_path}")
        return config_path

    with open(config_path, "w") as f:
        yaml.safe_dump(DEFAULT_LLM_CONFIG, f, default_flow_style=False)

    _out(f"  ✓ Created LLM config: {config_path}")
    return config_path


def create_preferences(data_dir: Path) -> Path:
    """Create default preferences."""
    pref_path = data_dir / "config" / "preferences.yaml"
    pref_path.parent.mkdir(parents=True, exist_ok=True)

    if pref_path.exists():
        _out(f"  ✓ Preferences exist: {pref_path}")
        return pref_path

    with open(pref_path, "w") as f:
        yaml.safe_dump(DEFAULT_PREFERENCES, f, default_flow_style=False)

    _out(f"  ✓ Created preferences: {pref_path}")
    return pref_path


def create_env_template(repo_root: Path) -> Path:
    """Create .env.example template."""
    env_path = repo_root / ".env.example"

    content = """# Augur Environment Configuration
# Copy this to .env and customize

# Data directory (optional, defaults to ~/Projects/augur)
# AUGUR_ROOT=~/Projects/augur

# LLM Profile (optional, defaults to IDE mode)
# AUGUR_LLM_PROFILE=ide

# OpenAI API Key (only needed for remote LLM mode)
# OPENAI_API_KEY=sk-...

# Adaptive Growth Provider (none, llm, openai)
# AUGUR_GROWTH_PROVIDER=none
"""

    if env_path.exists():
        _out(f"  ✓ .env.example exists: {env_path}")
        return env_path

    with open(env_path, "w") as f:
        f.write(content)

    _out(f"  ✓ Created .env.example: {env_path}")
    return env_path


def create_skill_defaults(data_dir: Path) -> None:
    """Create default configurations for key skills."""

    # Inbox processor defaults
    inbox_config = data_dir / "horizontal" / "inbox-processor" / "config.yaml"
    if not inbox_config.exists():
        inbox_config.parent.mkdir(parents=True, exist_ok=True)
        config = {
            "inbox": {"note_name": "📥 Inbox"},
            "processing": {"dry_run": False, "auto_confirm_threshold": 0.7},
            "cleanup": {"max_processed_age_days": 7, "archive_processed": True},
        }
        with open(inbox_config, "w") as f:
            yaml.safe_dump(config, f, default_flow_style=False, allow_unicode=True)
        _out(f"  ✓ Created inbox config: {inbox_config}")
    else:
        _out(f"  ✓ Inbox config exists: {inbox_config}")

    # Careers defaults
    careers_config = data_dir / "vertical" / "careers" / "config.yaml"
    if not careers_config.exists():
        careers_config.parent.mkdir(parents=True, exist_ok=True)
        config = {
            "scoring": {
                "min_match_threshold": 0.6,
                "weights": {"skills": 0.4, "experience": 0.3, "location": 0.2, "company": 0.1},
            },
            "alerts": {"enabled": True, "frequency": "daily"},
        }
        with open(careers_config, "w") as f:
            yaml.safe_dump(config, f, default_flow_style=False)
        _out(f"  ✓ Created careers config: {careers_config}")
    else:
        _out(f"  ✓ Careers config exists: {careers_config}")


def main():
    _out("🔧 Configuring Augur Sensible Defaults\n")

    repo_root = get_repo_root()
    data_dir = get_data_dir()

    _out(f"Repository: {repo_root}")
    _out(f"Data Directory: {data_dir}\n")

    _out("Creating configuration files...")
    create_llm_config(data_dir)
    create_preferences(data_dir)
    create_env_template(repo_root)
    create_skill_defaults(data_dir)

    _out("\n✅ Sensible defaults configured!")
    _out("\nConfiguration files created:")
    _out(f"  - {data_dir}/config/llm.yaml")
    _out(f"  - {data_dir}/config/preferences.yaml")
    _out(f"  - {repo_root}/.env.example")
    _out("\nNo additional configuration required to start using Augur.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
