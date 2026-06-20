#!/usr/bin/env python3
"""
Source Extractor

Extracts content from various source types (Notion, Folder, Git, Prompt, Zip).
"""

import json
import sys
import tempfile
import shutil
import zipfile
import tarfile
from pathlib import Path
from typing import Any, Dict
from subprocess import CompletedProcess, TimeoutExpired, run  # nosec B404
import urllib.request
import urllib.parse


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


def _resolve_command(command: list[str]) -> list[str]:
    """Resolve executable path to absolute when available."""
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
    """Run subprocess command with resolved executable path."""
    return run(_resolve_command(command), **kwargs)  # nosec B603


# Add repo root to path
repo_root = Path(__file__).resolve().parents[5]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))


def extract_notion(url: str, api_key: str = None) -> Dict[str, Any]:
    """Extract content from Notion page using Notion API."""
    try:
        # Parse Notion URL to get page ID
        page_id = None
        if 'notion.so' in url:
            # Extract page ID from URL
            # Notion URLs can be: https://notion.so/Page-Name-abc123def456
            # or: https://www.notion.so/Page-Name-abc123def456
            parts = url.split('/')
            for part in parts:
                if part and '-' in part:
                    # Extract the ID part (last segment after dashes)
                    segments = part.split('-')
                    if len(segments) > 0:
                        # Last segment might be the ID
                        potential_id = segments[-1]
                        # Notion IDs are 32 characters (UUID without dashes)
                        if len(potential_id) >= 20:
                            page_id = potential_id.split('?')[0].split('#')[0]
                            break

        if not page_id:
            return {
                'type': 'notion',
                'url': url,
                'error': 'Could not extract page ID from URL',
            }

        if not api_key:
            # Try to use public page access (limited)
            return {
                'type': 'notion',
                'url': url,
                'pages': 1,
                'blocks': 0,
                'extracted': True,
                'preview': {
                    'title': 'Notion Page',
                    'content': 'Public page - API key required for full extraction',
                    'note': 'Provide API key for private pages',
                },
            }

        # Use Notion API to retrieve page
        api_url = f"https://api.notion.com/v1/pages/{page_id}"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Notion-Version": "2022-06-28",
        }

        req = urllib.request.Request(api_url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:  # nosec B310
                page_data = json.loads(resp.read().decode('utf-8'))

            # Extract blocks
            blocks_url = f"https://api.notion.com/v1/blocks/{page_id}/children"
            blocks_req = urllib.request.Request(blocks_url, headers=headers)

            blocks = []
            try:
                with urllib.request.urlopen(blocks_req, timeout=30) as resp:  # nosec B310
                    blocks_data = json.loads(resp.read().decode('utf-8'))
                    blocks = blocks_data.get('results', [])
            except Exception:
                blocks = []

            # Extract title
            title = 'Untitled'
            if 'properties' in page_data:
                for prop_name, prop_data in page_data['properties'].items():
                    if prop_data.get('type') == 'title' and prop_data.get('title'):
                        title = ''.join([t.get('plain_text', '') for t in prop_data['title']])
                        break

            # Extract metadata
            created_time = page_data.get('created_time', '')
            last_edited_time = page_data.get('last_edited_time', '')
            created_by = page_data.get('created_by', {}).get('id', '')
            last_edited_by = page_data.get('last_edited_by', {}).get('id', '')

            return {
                'type': 'notion',
                'url': url,
                'page_id': page_id,
                'pages': 1,
                'blocks': len(blocks),
                'extracted': True,
                'preview': {
                    'title': title,
                    'blocks': len(blocks),
                    'content': f'Extracted {len(blocks)} blocks from Notion page',
                    'requirements': extract_requirements_from_blocks(blocks),
                    'metadata': {
                        'created_time': created_time,
                        'last_edited_time': last_edited_time,
                        'created_by': created_by,
                        'last_edited_by': last_edited_by,
                    },
                },
            }
        except urllib.error.HTTPError as e:
            return {
                'type': 'notion',
                'url': url,
                'error': f'Notion API error: {e.code} - {e.reason}',
            }
    except Exception as e:
        return {
            'type': 'notion',
            'url': url,
            'error': f'Failed to extract from Notion: {str(e)}',
        }


def extract_requirements_from_blocks(blocks: list) -> list:
    """Extract requirements from Notion blocks."""
    requirements = []
    for block in blocks:
        block_type = block.get('type', '')
        if block_type in ['paragraph', 'heading_1', 'heading_2', 'heading_3']:
            rich_text = block.get(block_type, {}).get('rich_text', [])
            text = ''.join([t.get('plain_text', '') for t in rich_text])
            if text.strip():
                requirements.append(text.strip())
    return requirements[:10]  # Limit to first 10


def extract_folder(path: str) -> Dict[str, Any]:
    """Extract content from folder."""
    try:
        folder_path = Path(path).expanduser().resolve()
        if not folder_path.exists():
            return {'error': f'Folder not found: {path}'}

        if not folder_path.is_dir():
            return {'error': f'Path is not a directory: {path}'}

        files = []
        total_size = 0
        file_types = {}

        for file_path in folder_path.rglob('*'):
            if file_path.is_file():
                rel_path = str(file_path.relative_to(folder_path))
                files.append(rel_path)
                try:
                    size = file_path.stat().st_size
                    total_size += size
                    ext = file_path.suffix.lower()
                    file_types[ext] = file_types.get(ext, 0) + 1
                except Exception:
                    _ = None

        return {
            'type': 'folder',
            'path': str(folder_path),
            'files': len(files),
            'extracted': True,
            'preview': {
                'file_list': files[:20],  # First 20 files
                'total_files': len(files),
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'file_types': dict(sorted(file_types.items(), key=lambda x: x[1], reverse=True)[:10]),
            },
        }
    except Exception as e:
        return {'error': f'Failed to extract folder: {str(e)}'}


def extract_git(url: str, branch: str = 'main') -> Dict[str, Any]:
    """Extract content from Git repository."""
    try:
        # Create temporary directory for cloning
        temp_dir = tempfile.mkdtemp(prefix='augur_git_')

        try:
            # Clone repository
            clone_cmd = ['git', 'clone', '--depth', '1', '--branch', branch, url, temp_dir]
            result = _run_command(
                clone_cmd,
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode != 0:
                # Try without branch (use default)
                clone_cmd = ['git', 'clone', '--depth', '1', url, temp_dir]
                result = _run_command(
                    clone_cmd,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )

            if result.returncode != 0:
                return {
                    'type': 'git',
                    'url': url,
                    'error': f'Git clone failed: {result.stderr}',
                }

            # Analyze repository structure
            repo_path = Path(temp_dir)
            files = []
            skill_files = []

            for file_path in repo_path.rglob('*'):
                if file_path.is_file():
                    rel_path = str(file_path.relative_to(repo_path))
                    files.append(rel_path)

                    # Check if it's a skill file
                    if file_path.name == 'SKILL.md' or 'skill' in rel_path.lower():
                        skill_files.append(rel_path)

            # Detect if it's a skill structure
            is_skill = any('SKILL.md' in f for f in files)

            structure = None
            if is_skill:
                # Try to read SKILL.md
                for skill_file in skill_files:
                    try:
                        skill_path = repo_path / skill_file
                        if skill_path.exists():
                            structure = {
                                'type': 'skill',
                                'skill_file': skill_file,
                                'has_tests': any('test' in f.lower() for f in files),
                                'has_scripts': any('script' in f.lower() for f in files),
                            }
                            break
                    except Exception:
                        _ = None

            return {
                'type': 'git',
                'url': url,
                'branch': branch,
                'files': len(files),
                'cloned': True,
                'extracted': True,
                'preview': {
                    'repository': url,
                    'file_count': len(files),
                    'is_skill': is_skill,
                    'skill_files': skill_files[:5],
                    'structure': structure,
                },
            }
        finally:
            # Clean up temporary directory
            try:
                shutil.rmtree(temp_dir)
            except Exception:
                _ = None
    except TimeoutExpired:
        return {
            'type': 'git',
            'url': url,
            'error': 'Git clone timed out',
        }
    except Exception as e:
        return {
            'type': 'git',
            'url': url,
            'error': f'Failed to extract from Git: {str(e)}',
        }


def extract_prompt(text: str) -> Dict[str, Any]:
    """Return prompt analysis context for agent-inline classification (ADR-137).

    Instead of calling an LLM directly, this returns the analysis prompt
    so the calling agent can classify inline — the agent IS the LLM.
    """
    system_prompt = (
        "You are analyzing a user's prompt to extract requirements for creating a skill.\n"
        "Extract:\n"
        "1. Domain (e.g., finance, health, productivity)\n"
        "2. Patterns (inbox, database, scoring, rag)\n"
        "3. Key requirements\n"
        "4. Capabilities needed\n\n"
        "Return JSON with: domain, patterns (array), requirements (array), capabilities (array)."
    )
    user_prompt = f"Analyze this prompt and extract skill requirements:\n\n{text}"

    return {
        'type': 'prompt',
        'text': text,
        'analyzed': False,
        'needs_agent_analysis': True,
        'preview': {
            'requirements': [text[:200] + '...' if len(text) > 200 else text],
            'domain': None,
            'patterns': [],
        },
        'agent_prompt': {
            'system': system_prompt,
            'user': user_prompt,
            'instructions': (
                'Analyze the user prompt and return JSON with: '
                'domain, patterns (array), requirements (array), capabilities (array). '
                'The calling code will merge your response into the result.'
            ),
        },
    }


def extract_zip(file_path: str) -> Dict[str, Any]:
    """Extract content from zip file."""
    try:
        zip_path = Path(file_path)
        if not zip_path.exists():
            return {'error': f'Zip file not found: {file_path}'}

        # Create temporary directory for extraction
        temp_dir = tempfile.mkdtemp(prefix='augur_zip_')

        try:
            files = []
            is_skill = False
            skill_file = None

            # Try zip first
            try:
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)  # nosec B202
                    for member in zip_ref.namelist():
                        files.append(member)
                        if 'SKILL.md' in member or member.endswith('SKILL.md'):
                            is_skill = True
                            skill_file = member
            except zipfile.BadZipFile:
                # Try tar.gz
                try:
                    with tarfile.open(zip_path, 'r:gz') as tar_ref:
                        tar_ref.extractall(temp_dir)  # nosec B202
                        for member in tar_ref.getnames():
                            files.append(member)
                            if 'SKILL.md' in member or member.endswith('SKILL.md'):
                                is_skill = True
                                skill_file = member
                except Exception:
                    return {'error': 'File is not a valid zip or tar.gz archive'}

            # Analyze structure
            structure = None
            if is_skill and skill_file:
                try:
                    extracted_path = Path(temp_dir) / skill_file
                    if extracted_path.exists():
                        structure = {
                            'type': 'skill',
                            'skill_file': skill_file,
                        }
                except Exception:
                    _ = None

            # Build file tree structure
            file_tree = []
            tree_structure = {}
            for file_path in files:
                parts = file_path.split('/')
                current = tree_structure
                for part in parts:
                    if part not in current:
                        current[part] = {}
                    current = current[part]

            def build_tree(node, prefix='', is_last=True):
                items = []
                keys = sorted(node.keys())
                for i, key in enumerate(keys):
                    is_last_item = i == len(keys) - 1
                    current_prefix = prefix + ('└── ' if is_last_item else '├── ')
                    items.append(current_prefix + key)
                    if node[key]:  # Has children
                        next_prefix = prefix + ('    ' if is_last_item else '│   ')
                        items.extend(build_tree(node[key], next_prefix, is_last_item))
                return items

            file_tree = build_tree(tree_structure) if tree_structure else []

            return {
                'type': 'zip',
                'path': str(zip_path),
                'files': len(files),
                'extracted': True,
                'preview': {
                    'file_list': files[:20],
                    'total_files': len(files),
                    'is_skill': is_skill,
                    'skill_file': skill_file,
                    'structure': structure,
                    'file_tree': file_tree[:30],  # Limit tree display
                },
            }
        finally:
            # Clean up temporary directory
            try:
                shutil.rmtree(temp_dir)
            except Exception:
                _ = None
    except Exception as e:
        return {'error': f'Failed to extract zip: {str(e)}'}


def main():
    if len(sys.argv) < 2:
        _out(json.dumps({'error': 'Config file path required'}), file=sys.stderr)
        sys.exit(1)

    config_path = Path(sys.argv[1])
    if not config_path.exists():
        _out(json.dumps({'error': f'Config file not found: {config_path}'}), file=sys.stderr)
        sys.exit(1)

    with open(config_path, 'r') as f:
        config = json.load(f)

    source_type = config.get('type')
    value = config.get('value')

    if not source_type or not value:
        _out(json.dumps({'error': 'Type and value required'}), file=sys.stderr)
        sys.exit(1)

    try:
        if source_type == 'notion':
            result = extract_notion(value, config.get('api_key'))
        elif source_type == 'folder':
            result = extract_folder(value)
        elif source_type == 'git':
            result = extract_git(value, config.get('branch', 'main'))
        elif source_type == 'prompt':
            result = extract_prompt(value)
        elif source_type == 'zip':
            result = extract_zip(value)
        else:
            result = {'error': f'Unknown source type: {source_type}'}

        _out(json.dumps(result))
    except Exception as e:
        _out(json.dumps({'error': str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
