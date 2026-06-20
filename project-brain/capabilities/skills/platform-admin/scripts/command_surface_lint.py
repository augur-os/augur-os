from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml


SHELL_EXTENSIONS = {".sh"}
SHELL_SHEBANG_MARKERS = ("bash", "/bin/sh", "/bin/zsh", " zsh", " sh")
SHELL_ENGINE_TYPES = {"shell", "bash", "sh", "zsh"}
MANAGED_BLOCK_START = "# === augur CLI shortcuts (ca/xa/ga) ==="
MANAGED_BLOCK_END = "# === end augur CLI shortcuts ==="
DIRECT_CLIENT_PATTERNS = {
    "codex": (
        "codex --dangerously-bypass-approvals-and-sandbox",
        "codex  --dangerously-bypass-approvals-and-sandbox",
    ),
    "claude": ("claude --dangerously-skip-permissions",),
    "gemini": ("gemini --yolo",),
}


@dataclass(frozen=True)
class Issue:
    code: str
    message: str
    path: str = ""
    surface: str = ""


def _load_yaml(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return loaded if isinstance(loaded, dict) else {}


def _tracked_files(root: Path) -> list[str] | None:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return [line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]


def _looks_like_shell_script(root: Path, rel_path: str) -> bool:
    path = root / rel_path
    if path.suffix == ".ps1":
        return False
    if path.suffix in SHELL_EXTENSIONS:
        return True
    try:
        first_line = path.read_text(encoding="utf-8", errors="ignore").splitlines()[0]
    except (IndexError, OSError):
        return False
    if not first_line.startswith("#!"):
        return False
    lowered = first_line.lower()
    return any(marker in lowered for marker in SHELL_SHEBANG_MARKERS)


def _normalized_path(value: object) -> str:
    return str(value).replace("\\", "/")


def _declared_shell_paths(manifest: dict[str, Any]) -> set[str]:
    declared: set[str] = set()
    for surface in (manifest.get("surfaces") or {}).values():
        if not isinstance(surface, dict):
            continue
        adapters = surface.get("adapters") or {}
        if isinstance(adapters, dict):
            for adapter in adapters.values():
                if isinstance(adapter, str):
                    declared.add(_normalized_path(adapter))

    inventory = manifest.get("shell_inventory") or {}
    if isinstance(inventory, dict):
        for section in ("declared_posix_only", "declared_internal"):
            for item in inventory.get(section) or []:
                if isinstance(item, dict) and item.get("path"):
                    declared.add(_normalized_path(item["path"]))
    return declared


def _validate_adapter(
    root: Path,
    issues: list[Issue],
    *,
    surface_name: str,
    platform_name: str,
    adapter: object,
    require_adapter_files: bool,
) -> None:
    if not isinstance(adapter, str):
        issues.append(
            Issue(
                "invalid-adapter-path",
                "Adapter path must be a string.",
                surface=surface_name,
            )
        )
        return

    rel_path = _normalized_path(adapter)
    lowered = rel_path.lower()
    if platform_name == "windows" and not lowered.endswith(".ps1"):
        issues.append(
            Issue(
                "windows-adapter-not-powershell",
                "Windows adapter must use a .ps1 file.",
                path=rel_path,
                surface=surface_name,
            )
        )
    if platform_name == "posix" and not lowered.endswith(".sh"):
        issues.append(
            Issue(
                "posix-adapter-not-shell",
                "POSIX adapter must use a .sh file.",
                path=rel_path,
                surface=surface_name,
            )
        )
    if require_adapter_files and not (root / rel_path).exists():
        issues.append(
            Issue(
                "missing-adapter-file",
                "Declared adapter path does not exist.",
                path=rel_path,
                surface=surface_name,
            )
        )


def _managed_block(content: str) -> str:
    start = content.find(MANAGED_BLOCK_START)
    if start == -1:
        return ""
    end = content.find(MANAGED_BLOCK_END, start)
    if end == -1:
        return ""
    return content[start : end + len(MANAGED_BLOCK_END)]


def _validate_surface_tests(root: Path, issues: list[Issue], *, surface_name: str, surface: dict[str, Any]) -> None:
    tests = surface.get("tests")
    if not isinstance(tests, list) or not tests:
        issues.append(
            Issue(
                "missing-surface-tests",
                "Cross-platform surface must declare test files that cover the surface.",
                surface=surface_name,
            )
        )
        return

    for test_path in tests:
        rel_path = _normalized_path(test_path)
        if not isinstance(test_path, str) or not (root / rel_path).exists():
            issues.append(
                Issue(
                    "missing-surface-test-file",
                    "Declared surface test file does not exist.",
                    path=rel_path,
                    surface=surface_name,
                )
            )


def _validate_installers(
    root: Path,
    issues: list[Issue],
    *,
    surface_name: str,
    surface: dict[str, Any],
) -> None:
    adapters = surface.get("adapters") or {}
    installers = surface.get("installers") or {}
    canonical = surface.get("canonical_engine") or {}
    if not isinstance(adapters, dict) or not isinstance(installers, dict):
        return

    mode = canonical.get("mode") if isinstance(canonical, dict) else None
    direct_patterns = DIRECT_CLIENT_PATTERNS.get(str(mode), ())
    for platform_name, installer in installers.items():
        if not isinstance(installer, str):
            issues.append(
                Issue(
                    "invalid-installer-path",
                    "Installer path must be a string.",
                    surface=surface_name,
                )
            )
            continue

        rel_path = _normalized_path(installer)
        path = root / rel_path
        if not path.exists():
            issues.append(
                Issue(
                    "missing-installer-file",
                    "Declared installer path does not exist.",
                    path=rel_path,
                    surface=surface_name,
                )
            )
            continue

        content = path.read_text(encoding="utf-8", errors="ignore")
        block = _managed_block(content)
        if not block and MANAGED_BLOCK_START not in content and "$beginMarker" not in content:
            issues.append(
                Issue(
                    "missing-installer-managed-block",
                    "Installer does not contain the managed ca/xa/ga shortcut block.",
                    path=rel_path,
                    surface=surface_name,
                )
            )
            continue

        adapter = adapters.get(platform_name)
        if isinstance(adapter, str) and Path(adapter).name not in content:
            issues.append(
                Issue(
                    "installer-missing-adapter-reference",
                    "Installer shortcut block does not reference the declared adapter.",
                    path=rel_path,
                    surface=surface_name,
                )
            )

        validation_text = block or content
        if any(pattern in validation_text for pattern in direct_patterns):
            issues.append(
                Issue(
                    "installer-direct-client-command",
                    "Installer shortcut block must delegate to adapters, not direct AI client commands.",
                    path=rel_path,
                    surface=surface_name,
                )
            )


def lint_manifest(
    root: Path,
    manifest_path: Path | None = None,
    *,
    tracked_files: Iterable[str] | None = None,
    require_adapter_files: bool = True,
) -> list[Issue]:
    manifest_path = manifest_path or root / "config" / "system" / "command_surfaces.yaml"
    if not manifest_path.exists():
        return [
            Issue(
                "missing-manifest",
                "Command surfaces manifest does not exist.",
                path=_normalized_path(manifest_path),
            )
        ]

    manifest = _load_yaml(manifest_path)
    issues: list[Issue] = []

    surfaces = manifest.get("surfaces") or {}
    if isinstance(surfaces, dict):
        for surface_name, surface in surfaces.items():
            if not isinstance(surface, dict):
                continue
            platforms = set(surface.get("platforms") or [])
            adapters = surface.get("adapters") or {}
            canonical = surface.get("canonical_engine") or {}

            if {"windows", "posix"}.issubset(platforms):
                if not isinstance(adapters, dict) or "windows" not in adapters:
                    issues.append(
                        Issue(
                            "missing-windows-adapter",
                            "Cross-platform surface is missing a Windows adapter.",
                            surface=str(surface_name),
                        )
                    )
                if not isinstance(adapters, dict) or "posix" not in adapters:
                    issues.append(
                        Issue(
                            "missing-posix-adapter",
                            "Cross-platform surface is missing a POSIX adapter.",
                            surface=str(surface_name),
                        )
                    )
                if isinstance(canonical, dict) and canonical.get("type") in SHELL_ENGINE_TYPES:
                    issues.append(
                        Issue(
                            "cross-platform-shell-engine",
                            "Cross-platform surface cannot use shell as its canonical engine.",
                            surface=str(surface_name),
                        )
                    )
                _validate_surface_tests(root, issues, surface_name=str(surface_name), surface=surface)
                _validate_installers(root, issues, surface_name=str(surface_name), surface=surface)

            if isinstance(adapters, dict):
                for platform_name, adapter in adapters.items():
                    _validate_adapter(
                        root,
                        issues,
                        surface_name=str(surface_name),
                        platform_name=str(platform_name),
                        adapter=adapter,
                        require_adapter_files=require_adapter_files,
                    )

    declared = _declared_shell_paths(manifest)
    discovered_files = list(tracked_files) if tracked_files is not None else _tracked_files(root)
    if discovered_files is None:
        issues.append(
            Issue(
                "tracked-files-unavailable",
                "Could not enumerate tracked files with git ls-files.",
                path=_normalized_path(root),
            )
        )
        return issues

    files = [_normalized_path(path) for path in discovered_files]
    for rel_path in files:
        if rel_path in declared:
            continue
        if _looks_like_shell_script(root, rel_path):
            issues.append(
                Issue(
                    "unclassified-shell-script",
                    "Tracked shell script is not declared in command surfaces or shell inventory.",
                    path=rel_path,
                )
            )

    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lint Augur cross-OS command surfaces.")
    parser.add_argument("--root", default=".", help="Repository root.")
    parser.add_argument("--manifest", default=None, help="Command surfaces manifest path.")
    parser.add_argument("--json", action="store_true", help="Emit JSON issues.")
    parser.add_argument(
        "--allow-missing-adapter-files",
        action="store_true",
        help="Skip adapter file existence checks for staged manifest work.",
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    manifest_path = Path(args.manifest).resolve() if args.manifest else None
    issues = lint_manifest(
        root,
        manifest_path,
        require_adapter_files=not args.allow_missing_adapter_files,
    )
    if args.json:
        print(json.dumps([asdict(issue) for issue in issues], indent=2))
    else:
        for issue in issues:
            location = issue.path or issue.surface
            print(f"{issue.code}: {location}: {issue.message}")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
