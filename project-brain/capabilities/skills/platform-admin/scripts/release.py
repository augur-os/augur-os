#!/usr/bin/env python3
"""
Augur Skills - Unified Release Script

Usage:
    python release.py career --patch
    python release.py all --minor
    python release.py analyst --major --dry-run
"""

import argparse
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from subprocess import CalledProcessError, CompletedProcess, run  # nosec B404

import yaml

from bootstrap_paths import ensure_project_paths  # noqa: E402

REPO_ROOT = ensure_project_paths(__file__)

from src.config.paths import get_runtime_dir


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


def _resolve_command(command: list[str]) -> list[str]:
    """Resolve executable path to absolute when available on PATH."""
    if not command:
        raise ValueError("Command must not be empty")

    executable = command[0]
    if Path(executable).is_absolute():
        return command

    resolved = shutil.which(executable)
    if not resolved:
        return command

    return [resolved, *command[1:]]


def _run_command(command: list[str], **kwargs: object) -> CompletedProcess:
    """Run subprocess command with resolved executable."""
    return run(_resolve_command(command), **kwargs)  # nosec B603


PLUGINS_DIR = REPO_ROOT / 'plugins'

# Dashboard is a special case outside the plugins structure
DASHBOARD_CONFIG = {
    'has_tests': True,
    'version_file': 'package.json',
    'changelog': 'CHANGELOG.md',
}


def discover_skills() -> dict:
    """Auto-discover skills from plugins/{bundle}/skills/{name}/."""
    skills = {}
    for bundle_dir in sorted(PLUGINS_DIR.iterdir()):
        if not bundle_dir.is_dir():
            continue
        skills_dir = bundle_dir / 'skills'
        if not skills_dir.is_dir():
            continue
        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            skills[skill_dir.name] = {
                'bundle': bundle_dir.name,
                'has_tests': (skill_dir / 'tests').is_dir(),
                'version_file': 'augur/version.yaml',
                'changelog': 'CHANGELOG.md',
            }
    skills['dashboard'] = DASHBOARD_CONFIG
    return skills


def get_skill_dir(skill_name: str, config: dict | None = None) -> Path:
    """Resolve the directory for a skill."""
    if skill_name == 'dashboard':
        return REPO_ROOT / 'apps' / 'dashboard'
    if config and 'bundle' in config:
        return PLUGINS_DIR / config['bundle'] / 'skills' / skill_name
    # Fallback: search all bundles
    for bundle_dir in PLUGINS_DIR.iterdir():
        candidate = bundle_dir / 'skills' / skill_name
        if candidate.is_dir():
            return candidate
    raise ValueError(f"Skill '{skill_name}' not found in any bundle")


SKILL_CONFIG = discover_skills()


def get_current_version(skill_name: str) -> str:
    """Read current version from skill's version file."""
    config = SKILL_CONFIG[skill_name]
    skill_dir = get_skill_dir(skill_name, config)
    version_path = skill_dir / config['version_file']

    if not version_path.exists():
        return '0.0.0'

    if version_path.suffix == '.toml':
        import re

        content = version_path.read_text()
        match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
        return match.group(1) if match else '0.0.0'
    elif version_path.name == 'package.json':
        import json

        with open(version_path) as f:
            return json.load(f).get('version', '0.0.0')

    with open(version_path) as f:
        data = yaml.safe_load(f)
        return data.get('version', '0.0.0')


def bump_version(version: str, bump_type: str) -> str:
    """Bump version according to semver."""
    parts = version.split('.')
    major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2].split('-')[0])

    if bump_type == 'major':
        return f'{major + 1}.0.0'
    elif bump_type == 'minor':
        return f'{major}.{minor + 1}.0'
    else:  # patch
        return f'{major}.{minor}.{patch + 1}'


def update_version_file(skill_name: str, new_version: str, dry_run: bool = False):
    """Update the version file with new version."""
    config = SKILL_CONFIG[skill_name]
    skill_dir = get_skill_dir(skill_name, config)
    version_path = skill_dir / config['version_file']

    if dry_run:
        _out(f"[DRY RUN] Would update {version_path} to {new_version}")
        return

    if version_path.suffix == '.toml':
        import re

        content = version_path.read_text()
        new_content = re.sub(r'^version\s*=\s*"[^"]+"', f'version = "{new_version}"', content, flags=re.MULTILINE)
        version_path.write_text(new_content)
        _out(f"✅ Updated {version_path}")
        return
    elif version_path.name == 'package.json':
        import json

        with open(version_path) as f:
            data = json.load(f)
        data['version'] = new_version
        with open(version_path, 'w') as f:
            json.dump(data, f, indent=2)
            f.write('\n')  # Add trailing newline
        _out(f"✅ Updated {version_path}")
        return

    version_path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        'version': new_version,
        'updated': datetime.now().strftime('%Y-%m-%d'),
        'skill': skill_name,
    }

    with open(version_path, 'w') as f:
        yaml.dump(data, f, default_flow_style=False)
    _out(f"✅ Updated {version_path}")


def get_last_tag(skill_name: str) -> str:
    """Get the last git tag for this skill."""
    try:
        # List tags, filter by skill name, sort by creation date desc
        result = _run_command(
            ['git', 'tag', '--list', f'{skill_name}-v*', '--sort=-creatordate'],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        tags = result.stdout.strip().split('\n')
        return tags[0] if tags and tags[0] else None
    except Exception:
        return None


def get_commits_since_tag(tag: str, path: str) -> list[str]:
    """Get commit messages since the specified tag for a path."""
    rev_range = f"{tag}..HEAD" if tag else "HEAD"
    try:
        # Get subject only which is cleaner
        cmd = ['git', 'log', rev_range, '--format=%s', '--', path]
        result = _run_command(cmd, capture_output=True, text=True, cwd=REPO_ROOT)
        return [line for line in result.stdout.split('\n') if line]
    except Exception:
        return []


def format_changelog_entry(version: str, commits: list[str]) -> str:
    """Format changelog entry from commits."""
    date = datetime.now().strftime('%Y-%m-%d')

    # Categorize commits
    features = []
    fixes = []
    others = []

    for msg in commits:
        if msg.startswith('feat'):
            features.append(msg)
        elif msg.startswith('fix'):
            fixes.append(msg)
        else:
            others.append(msg)

    entry = f"\n## [{version}] - {date}\n"

    if features:
        entry += "\n### Added\n"
        for msg in features:
            entry += f"- {msg}\n"

    if fixes:
        entry += "\n### Fixed\n"
        for msg in fixes:
            entry += f"- {msg}\n"

    if others:
        entry += "\n### Other\n"
        for msg in others:
            entry += f"- {msg}\n"

    if not commits:
        entry += "\n- Maintenance release\n"

    return entry


def update_changelog(skill_name: str, new_version: str, dry_run: bool = False):
    """Add new version entry to changelog."""
    config = SKILL_CONFIG[skill_name]
    skill_dir = get_skill_dir(skill_name, config)
    changelog_path = skill_dir / config['changelog']
    skill_path = str(skill_dir.relative_to(REPO_ROOT))

    # Get commits
    last_tag = get_last_tag(skill_name)
    commits = get_commits_since_tag(last_tag, skill_path)
    new_entry = format_changelog_entry(new_version, commits)

    if not changelog_path.exists():
        content = f"# Changelog\n{new_entry}"
        if dry_run:
            _out(f"[DRY RUN] Would create {changelog_path} with:\n{new_entry}")
        else:
            changelog_path.parent.mkdir(parents=True, exist_ok=True)
            with open(changelog_path, 'w') as f:
                f.write(content)
        return

    with open(changelog_path) as f:
        content = f.read()

    # Add new version section after # Changelog
    # Robustly handle different header styles
    if '# Changelog' in content:
        content = content.replace('# Changelog\n', f'# Changelog\n{new_entry}', 1)
    else:
        # Fallback if header missing
        content = f"# Changelog\n{new_entry}\n{content}"

    if dry_run:
        _out(f"[DRY RUN] Would update {changelog_path} with:\n{new_entry}")
    else:
        with open(changelog_path, 'w') as f:
            f.write(content)
        _out(f"✅ Updated {changelog_path}")


def run_tests(skill_name: str) -> bool:
    """Run tests if configured."""
    config = SKILL_CONFIG[skill_name]
    if not config['has_tests']:
        _out(f"ℹ️  No tests configured for {skill_name}")
        return True

    config = SKILL_CONFIG[skill_name]
    test_path = get_skill_dir(skill_name, config) / 'tests'
    if not test_path.exists():
        _out(f"⚠️  Tests directory not found: {test_path}")
        return True

    _out(f"Running tests for {skill_name}...")
    # Use uv run pytest to ensure correct environment
    test_cmd = ["uv", "run", "pytest", str(test_path)]
    try:
        # Run from REPO_ROOT to ensure pytest.ini is found correctly
        _run_command(test_cmd, check=True, cwd=REPO_ROOT)
        _out(f"✅ Tests passed for {skill_name}")
        return True
    except CalledProcessError as e:
        _out(f"❌ Tests failed for {skill_name}")
        _out(e.stdout.decode() if e.stdout else "")
        _out(e.stderr.decode() if e.stderr else "")
        return False


def create_git_tag(skill_name: str, version: str, dry_run: bool = False):
    """Create git tag for the release."""
    tag_name = f"{skill_name}-v{version}"

    if dry_run:
        _out(f"[DRY RUN] Would create tag: {tag_name}")
        return

    _run_command(['git', 'add', '-A'], cwd=REPO_ROOT)
    _run_command(['git', 'commit', '-m', f'Release {skill_name} v{version}'], cwd=REPO_ROOT)
    _run_command(['git', 'tag', '-a', tag_name, '-m', f'Release {skill_name} v{version}'], cwd=REPO_ROOT)
    _out(f"✅ Created tag: {tag_name}")


def create_package(skill_name: str, version: str, dry_run: bool = False):
    """Create a compressed package for the skill."""
    _out(f"\n📦 Packaging {skill_name} v{version}...")

    # Ensure releases dir exists in persistent state storage.
    releases_dir = get_runtime_dir() / 'releases'
    if not releases_dir.exists():
        releases_dir.mkdir(parents=True, exist_ok=True)

    # Cleanup old releases for this specific skill/version to avoid stale files
    # We match pattern: skill_name-v*.zip
    # But specifically checking for the current one to be safe,
    # though usually we want to keep history?
    # The user asked not to "overhelp repo with historical plugins",
    # but that was about git history. Local releases/ dir is gitignored.
    # To be safe and clean, we'll remove ANY existing file with this exact target name.

    target_base = releases_dir / f"{skill_name}-v{version}"
    target_zip = releases_dir / f"{skill_name}-v{version}.zip"

    if target_zip.exists():
        if dry_run:
            _out(f"[DRY RUN] Would remove existing: {target_zip}")
        else:
            target_zip.unlink()
            _out(f"   Removed existing: {target_zip.name}")

    if dry_run:
        _out(f"[DRY RUN] Would create zip package: {target_zip}")
        return

    config = SKILL_CONFIG[skill_name]
    package_dir = get_skill_dir(skill_name, config)

    try:
        shutil.make_archive(str(target_base), 'zip', root_dir=package_dir, base_dir='.')
        _out(f"✅ Created package: {target_zip.name}")
        _out(f"   Path: {target_zip}")
    except Exception as e:
        _out(f"❌ Failed to create package: {e}")
        raise


def release_skill(skill_name: str, bump_type: str, dry_run: bool = False, skip_tests: bool = False) -> tuple[bool, str]:
    """Execute full release process for a skill."""
    _out(f"\n{'='*50}")
    _out(f"Releasing {skill_name} ({bump_type})")
    _out(f"{'='*50}\n")

    # Get current and new version
    current = get_current_version(skill_name)
    new_version = bump_version(current, bump_type)
    _out(f"Version: {current} → {new_version}")

    # Run tests
    if not skip_tests and not run_tests(skill_name):
        _out("❌ Release aborted due to test failures")
        return False, ''

    # Update version file
    update_version_file(skill_name, new_version, dry_run)

    # Update changelog
    update_changelog(skill_name, new_version, dry_run)

    # Create package
    create_package(skill_name, new_version, dry_run)

    # Create git tag
    if not dry_run:
        create_git_tag(skill_name, new_version, dry_run)

    _out(f"\n✅ {'[DRY RUN] ' if dry_run else ''}Released {skill_name} v{new_version}")
    return True, new_version


def main():
    parser = argparse.ArgumentParser(description='Release Claude Skills')
    parser.add_argument('skill', choices=list(SKILL_CONFIG.keys()) + ['all'], help='Skill to release (or "all")')
    parser.add_argument('--patch', action='store_true', help='Patch release')
    parser.add_argument('--minor', action='store_true', help='Minor release')
    parser.add_argument('--major', action='store_true', help='Major release')
    parser.add_argument('--dry-run', action='store_true', help='Preview without making changes')
    parser.add_argument('--skip-tests', action='store_true', help='Skip running tests')

    args = parser.parse_args()

    # Determine bump type
    if args.major:
        bump_type = 'major'
    elif args.minor:
        bump_type = 'minor'
    else:
        bump_type = 'patch'

    # Release skill(s)
    skills = list(SKILL_CONFIG.keys()) if args.skill == 'all' else [args.skill]
    released_version = ''

    for skill in skills:
        success, version = release_skill(skill, bump_type, args.dry_run, args.skip_tests)
        if not success:
            sys.exit(1)
        released_version = version

    # Output version for GitHub Actions
    github_output = os.environ.get('GITHUB_OUTPUT')
    if github_output and released_version:
        with open(github_output, 'a') as f:
            f.write(f"version={released_version}\n")

    if not args.dry_run:
        _out("\n🎉 Release complete! Don't forget to push:")
        _out("   git push origin main --tags")


if __name__ == '__main__':
    main()
