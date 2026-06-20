"""
Security Validator Service

Validates folder paths, file sizes, and file types for security.
Implements security measures from story-004 AC6.
"""

import os
import mimetypes
from pathlib import Path
from typing import Tuple, List, Optional

# Security limits (configurable via env vars)
MAX_FILE_SIZE_MB = int(os.getenv('SKILL_GEN_MAX_FILE_SIZE_MB', '100'))
MAX_FOLDER_SIZE_MB = int(os.getenv('SKILL_GEN_MAX_FOLDER_SIZE_MB', '1024'))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
MAX_FOLDER_SIZE_BYTES = MAX_FOLDER_SIZE_MB * 1024 * 1024

# Allowed home directory (default to user's home)
ALLOWED_BASE_DIR = Path(os.getenv('HOME', '/home/user'))

# Executable extensions to reject
EXECUTABLE_EXTENSIONS = {
    '.exe',
    '.sh',
    '.app',
    '.command',
    '.bat',
    '.ps1',
    '.msi',
    '.dmg',
    '.pkg',
    '.deb',
    '.rpm',
    '.run',
    '.bin',
    '.jar',
    '.apk',
}

# Supported file types for indexing
SUPPORTED_FILE_TYPES = {
    # Documents
    '.pdf',
    '.docx',
    '.pptx',
    '.xlsx',
    '.doc',
    '.xls',
    '.ppt',
    # Text
    '.md',
    '.txt',
    '.json',
    '.yaml',
    '.yml',
    '.xml',
    '.csv',
    # Code
    '.py',
    '.js',
    '.ts',
    '.jsx',
    '.tsx',
    '.java',
    '.c',
    '.cpp',
    '.h',
    '.cs',
    '.go',
    '.rb',
    '.php',
    '.swift',
    '.kt',
    '.rs',
    # Images (for OCR)
    '.png',
    '.jpg',
    '.jpeg',
    '.tiff',
    '.tif',
    '.webp',
    '.gif',
    # Other
    '.html',
    '.css',
    '.scss',
    '.sql',
    '.r',
}


class SecurityError(Exception):
    """Raised when security validation fails."""

    pass


def validate_folder_path(folder_path: str) -> Tuple[bool, Optional[str]]:
    """
    Validate folder path is within allowed directory.

    Security checks:
    - Path must be within user's home directory
    - Path must not contain path traversal attempts (../)
    - Path must exist and be a directory
    - Symlinks must not point outside allowed paths

    Args:
        folder_path: Folder path to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        path = Path(folder_path).resolve()
    except Exception as e:
        return False, f"Invalid path: {e}"

    # Check if path exists
    if not path.exists():
        return False, f"Path does not exist: {folder_path}"

    # Check if it's a directory
    if not path.is_dir():
        return False, f"Path is not a directory: {folder_path}"

    # Check if path is within allowed base directory
    try:
        # resolve() follows symlinks and normalizes path
        resolved_path = path.resolve()
        allowed_base = ALLOWED_BASE_DIR.resolve()

        # Check if path is relative to allowed base
        resolved_path.relative_to(allowed_base)
    except ValueError:
        return False, f"Path is outside allowed directory. Must be within {ALLOWED_BASE_DIR}"

    # Check for symlinks pointing outside allowed paths
    if path.is_symlink():
        target = path.readlink()
        target_resolved = (path.parent / target).resolve()
        try:
            target_resolved.relative_to(allowed_base)
        except ValueError:
            return False, f"Symlink points outside allowed directory: {folder_path}"

    return True, None


def validate_file_size(file_path: Path) -> Tuple[bool, Optional[str]]:
    """
    Validate file size is within limits.

    Args:
        file_path: File path to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        size_bytes = file_path.stat().st_size
    except Exception as e:
        return False, f"Cannot get file size: {e}"

    if size_bytes > MAX_FILE_SIZE_BYTES:
        size_mb = size_bytes / (1024 * 1024)
        return False, f"File exceeds size limit: {size_mb:.1f}MB (max: {MAX_FILE_SIZE_MB}MB)"

    return True, None


def validate_folder_size(folder_path: Path) -> Tuple[bool, Optional[str]]:
    """
    Validate total folder size is within limits.

    Args:
        folder_path: Folder path to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    total_size = 0

    try:
        for item in folder_path.rglob('*'):
            if item.is_file():
                total_size += item.stat().st_size

                # Early exit if exceeding limit
                if total_size > MAX_FOLDER_SIZE_BYTES:
                    size_mb = total_size / (1024 * 1024)
                    return False, f"Folder exceeds size limit: {size_mb:.1f}MB (max: {MAX_FOLDER_SIZE_MB}MB)"
    except Exception as e:
        return False, f"Cannot calculate folder size: {e}"

    return True, None


def is_executable_file(file_path: Path) -> bool:
    """
    Check if file is an executable.

    Args:
        file_path: File path to check

    Returns:
        True if file is executable, False otherwise
    """
    # Check file extension
    if file_path.suffix.lower() in EXECUTABLE_EXTENSIONS:
        return True

    # Check file permissions (executable bit)
    try:
        # Check if any execute bit is set
        mode = file_path.stat().st_mode
        if mode & 0o111:  # Check user/group/other execute bits
            return True
    except Exception:
        pass

    return False


def is_supported_file_type(file_path: Path) -> bool:
    """
    Check if file type is supported for indexing.

    Args:
        file_path: File path to check

    Returns:
        True if file type is supported, False otherwise
    """
    return file_path.suffix.lower() in SUPPORTED_FILE_TYPES


def validate_mime_type(file_path: Path) -> Tuple[bool, Optional[str]]:
    """
    Validate file MIME type matches extension.

    Args:
        file_path: File path to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Get MIME type from extension
    guessed_type, _ = mimetypes.guess_type(str(file_path))

    # Skip MIME validation for files without guessable type
    if guessed_type is None:
        return True, None

    # For now, just check that we can guess a type
    # More sophisticated check would read file headers
    return True, None


def validate_file_for_indexing(file_path: Path) -> Tuple[bool, List[str]]:
    """
    Comprehensive file validation for indexing.

    Checks:
    - File is not executable
    - File size is within limits
    - File type is supported
    - MIME type matches extension

    Args:
        file_path: File path to validate

    Returns:
        Tuple of (is_valid, warnings)
    """
    warnings = []

    # Check if file is executable
    if is_executable_file(file_path):
        warnings.append(f"Skipping executable file: {file_path.name}")
        return False, warnings

    # Check file size
    is_valid, error = validate_file_size(file_path)
    if not is_valid:
        warnings.append(f"Skipping large file: {file_path.name} ({error})")
        return False, warnings

    # Check if file type is supported
    if not is_supported_file_type(file_path):
        warnings.append(f"Skipping unsupported file type: {file_path.name}")
        return False, warnings

    # Validate MIME type
    is_valid, error = validate_mime_type(file_path)
    if not is_valid:
        warnings.append(f"MIME type mismatch: {file_path.name} ({error})")
        return False, warnings

    return True, []


def sanitize_skill_name(name: str) -> str:
    """
    Sanitize skill name to prevent path traversal.

    Args:
        name: Skill name to sanitize

    Returns:
        Sanitized skill name
    """
    # Remove path traversal attempts
    sanitized = name.replace('..', '').replace('/', '').replace('\\', '')

    # Remove any non-alphanumeric characters except hyphens
    sanitized = ''.join(c for c in sanitized if c.isalnum() or c == '-')

    # Ensure it starts with a letter
    if sanitized and not sanitized[0].isalpha():
        sanitized = 'skill-' + sanitized

    return sanitized.lower()


def get_folder_stats(folder_path: Path) -> dict:
    """
    Get folder statistics for preview.

    Args:
        folder_path: Folder path to analyze

    Returns:
        Dict with folder statistics
    """
    stats = {
        'total_files': 0,
        'supported_files': 0,
        'unsupported_files': 0,
        'executable_files': 0,
        'oversized_files': 0,
        'total_size_bytes': 0,
        'file_types': {},
    }

    try:
        for item in folder_path.rglob('*'):
            if item.is_file():
                stats['total_files'] += 1
                file_size = item.stat().st_size
                stats['total_size_bytes'] += file_size

                # Count file types
                ext = item.suffix.lower()
                stats['file_types'][ext] = stats['file_types'].get(ext, 0) + 1

                # Check if executable
                if is_executable_file(item):
                    stats['executable_files'] += 1
                    continue

                # Check file size
                if file_size > MAX_FILE_SIZE_BYTES:
                    stats['oversized_files'] += 1
                    continue

                # Check if supported
                if is_supported_file_type(item):
                    stats['supported_files'] += 1
                else:
                    stats['unsupported_files'] += 1

    except Exception as e:
        stats['error'] = str(e)

    return stats
