"""IDE Detection Service for Mode 3 (Enterprise IDE Integration).

Detects available agentic IDEs (Cursor, GitHub Copilot, Antigravity) and their capabilities.
Supports Windows, macOS, and Linux.
"""

from __future__ import annotations

import os
import platform
import shutil
from dataclasses import dataclass
from pathlib import Path
from subprocess import CompletedProcess, TimeoutExpired, run  # nosec B404
from typing import Any


@dataclass
class IDEDetectionResult:
    """Result of IDE detection."""

    found: bool
    name: str
    version: str | None = None
    path: Path | None = None
    capabilities: dict[str, Any] | None = None
    error: str | None = None


class IDEDetector:
    """Detects agentic IDEs on the system."""

    def __init__(self) -> None:
        self._system = platform.system()

    def _resolve_command(self, command: list[str]) -> list[str]:
        """Resolve command executable to an absolute path when available."""
        if not command:
            raise ValueError("Command must not be empty")

        executable = command[0]
        if Path(executable).is_absolute():
            return command

        resolved = shutil.which(executable)
        if not resolved:
            return command

        return [resolved, *command[1:]]

    def _run_command(self, command: list[str], **kwargs: object) -> CompletedProcess:
        """Run subprocess command with resolved executable path."""
        return run(self._resolve_command(command), **kwargs)  # nosec B603

    def _get_cursor_paths(self) -> list[Path]:
        """Get platform-specific Cursor installation paths."""
        if self._system == "Windows":
            local_app_data = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
            program_files = os.environ.get("PROGRAMFILES", "C:\\Program Files")  # audit-ignore: Windows fallback
            return [
                Path(local_app_data) / "Programs" / "cursor" / "Cursor.exe",
                Path(local_app_data) / "cursor" / "Cursor.exe",
                Path(program_files) / "Cursor" / "Cursor.exe",
                Path.home() / ".cursor",
            ]
        elif self._system == "Darwin":
            return [
                Path.home() / "Applications" / "Cursor.app",
                Path("/Applications/Cursor.app"),
                Path.home() / ".cursor",
            ]
        else:  # Linux
            return [
                Path.home() / ".local" / "share" / "cursor" / "cursor",
                Path("/opt/Cursor/cursor"),
                Path("/usr/share/cursor/cursor"),
                Path.home() / ".cursor",
            ]

    def detect_cursor(self) -> IDEDetectionResult:
        """Detect Cursor installation."""
        cursor_paths = self._get_cursor_paths()

        # Check for Cursor executable/app
        for app_path in cursor_paths[:-1]:  # Exclude .cursor config dir
            if app_path.exists():
                version = self._get_cursor_version(app_path)
                return IDEDetectionResult(
                    found=True,
                    name="Cursor",
                    version=version,
                    path=app_path,
                    capabilities={
                        "mcp": True,  # Cursor supports MCP
                        "chat": True,
                        "completions": True,
                    },
                )

        # Check for .cursor directory (indicates Cursor was used)
        cursor_config = cursor_paths[-1]
        if cursor_config.exists():
            return IDEDetectionResult(
                found=True,
                name="Cursor",
                version=None,
                path=cursor_config,
                capabilities={
                    "mcp": True,
                    "chat": True,
                    "completions": True,
                },
            )

        return IDEDetectionResult(
            found=False,
            name="Cursor",
            error="Cursor not found in common installation locations",
        )

    def _get_cursor_version(self, app_path: Path) -> str | None:
        """Get Cursor version (platform-specific)."""
        try:
            if self._system == "Darwin":
                return self._get_macos_app_version(app_path)
            elif self._system == "Windows":
                return self._get_windows_exe_version(app_path)
            # Linux: try running --version
            return self._get_cli_version(app_path)
        except (OSError, RuntimeError, ValueError):
            return None

    def _get_macos_app_version(self, app_path: Path) -> str | None:
        """Get version from macOS .app bundle Info.plist."""
        try:
            plist_path = app_path / "Contents" / "Info.plist"
            if not plist_path.exists():
                return None

            # SECURITY: Validate path is within expected application directories
            try:
                resolved_plist = plist_path.resolve()
                resolved_app = app_path.resolve()
                if not str(resolved_plist).startswith(str(resolved_app)):
                    return None
            except (OSError, ValueError):
                return None

            result = self._run_command(
                ["defaults", "read", str(resolved_plist), "CFBundleShortVersionString"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (OSError, TimeoutExpired):
            return None
        return None

    def _get_windows_exe_version(self, exe_path: Path) -> str | None:
        """Get version from Windows executable using PowerShell."""
        try:
            # Use PowerShell to get file version info
            result = self._run_command(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    f"(Get-Item '{exe_path}').VersionInfo.ProductVersion",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except (OSError, TimeoutExpired):
            return None
        return None

    def _get_cli_version(self, exe_path: Path) -> str | None:
        """Get version by running executable with --version."""
        try:
            result = self._run_command(
                [str(exe_path), "--version"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0:
                return result.stdout.strip().split("\n")[0]
        except (OSError, TimeoutExpired):
            return None
        return None

    def detect_copilot(self) -> IDEDetectionResult:
        """Detect GitHub Copilot availability."""
        # Check for GitHub CLI
        try:
            result = self._run_command(
                ["gh", "--version"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0:
                # Check if user is authenticated
                auth_result = self._run_command(
                    ["gh", "auth", "status"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                authenticated = auth_result.returncode == 0

                return IDEDetectionResult(
                    found=True,
                    name="GitHub Copilot",
                    version=None,
                    capabilities={
                        "chat": authenticated,
                        "completions": authenticated,
                        "workspace": authenticated,
                    },
                )
        except (FileNotFoundError, TimeoutExpired):
            # Continue with filesystem-based VS Code extension detection.
            result = None

        # Check for Copilot in VS Code (cross-platform paths)
        vscode_extensions = [
            Path.home() / ".vscode" / "extensions",
            Path.home() / ".vscode-insiders" / "extensions",
        ]
        # Add Windows-specific paths
        if self._system == "Windows":
            app_data = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
            vscode_extensions.extend(
                [
                    Path(app_data) / "Code" / "User" / "extensions",
                    Path(app_data) / "Code - Insiders" / "User" / "extensions",
                ]
            )

        for ext_path in vscode_extensions:
            if ext_path.exists():
                # Look for GitHub Copilot extension
                for ext_dir in ext_path.iterdir():
                    if "github.copilot" in ext_dir.name.lower():
                        return IDEDetectionResult(
                            found=True,
                            name="GitHub Copilot",
                            version=None,
                            path=ext_dir,
                            capabilities={
                                "chat": True,
                                "completions": True,
                                "workspace": True,
                            },
                        )

        return IDEDetectionResult(
            found=False,
            name="GitHub Copilot",
            error="GitHub Copilot not detected",
        )

    def detect_antigravity(self) -> IDEDetectionResult:
        """Detect Antigravity installation."""
        # Check for Antigravity in common locations
        antigravity_paths = [
            Path.home() / ".antigravity",
            Path.home() / ".config" / "antigravity",
            Path("/opt/antigravity"),
        ]

        for ag_path in antigravity_paths:
            if ag_path.exists():
                return IDEDetectionResult(
                    found=True,
                    name="Antigravity",
                    version=None,
                    path=ag_path,
                    capabilities={
                        "workflows": True,
                        "tasks": True,
                        "agents": True,
                    },
                )

        # Check if antigravity command is available
        try:
            result = self._run_command(
                ["antigravity", "--version"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0:
                version = result.stdout.strip()
                return IDEDetectionResult(
                    found=True,
                    name="Antigravity",
                    version=version,
                    capabilities={
                        "workflows": True,
                        "tasks": True,
                        "agents": True,
                    },
                )
        except (FileNotFoundError, TimeoutExpired):
            # Fall through to the default "not detected" result below.
            result = None

        return IDEDetectionResult(
            found=False,
            name="Antigravity",
            error="Antigravity not detected",
        )

    def detect_all(self) -> dict[str, IDEDetectionResult]:
        """Detect all available IDEs."""
        return {
            "cursor": self.detect_cursor(),
            "copilot": self.detect_copilot(),
            "antigravity": self.detect_antigravity(),
        }


def detect_ides() -> dict[str, IDEDetectionResult]:
    """Convenience function to detect all IDEs."""
    detector = IDEDetector()
    return detector.detect_all()
