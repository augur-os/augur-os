from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import yaml

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.lib.partition_integrity import load_policy, public_release_files  # noqa: E402

DOCS_ONLY_ALLOWLIST = [
    "README.md",
    "ROADMAP.md",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "SECURITY.md",
    "CHANGELOG.md",
    "LICENSE",
    "docs/getting-started.md",
    "docs/what-is-augur.md",
    "docs/technical-architecture-review.md",
    "docs/developer-guide.md",
    "docs/user-guide.md",
    "docs/creating-skills.md",
    "docs/architecture-agents.md",
    "docs/architecture-capability-exposure.md",
    "docs/architecture-daemon.md",
    "docs/architecture-dashboard.md",
    "docs/architecture-eval-harness.md",
    "docs/architecture-memory.md",
    "docs/architecture-onboarding.md",
    "docs/architecture-overview.md",
    "docs/architecture-mcp-gateway.md",
    "docs/architecture-sdlc.md",
    "docs/architecture-skills.md",
    "docs/architecture-sync-agents.md",
    "docs/architecture-vault.md",
    "docs/architecture-wiki.md",
    "docs/guides/installation-windows.md",
    "docs/guides/wiki-llm-release-gate.md",
]

DOCS_ONLY_DIR_ALLOWLIST: list[str] = []


def load_release_scope(config_path: Path) -> str:
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"invalid release scope config: {config_path}")

    scope = data.get("scope")
    if scope not in {"docs_only", "mvp", "full"}:
        raise ValueError(f"unsupported release scope: {scope!r}")
    return scope


def _build_full_tree(source_root: Path, output_root: Path) -> list[str]:
    policy = load_policy(source_root / "config/system/partition_policy.yaml")
    manifest = public_release_files(source_root, policy)

    # TODO_BUG: shutil.rmtree(output_root) has no path-safety guard (same pattern
    # in the docs_only branch). Callers always pass a mktemp/tmp_path dir, but a
    # guard (reject output_root == source_root / repo root / "/") would harden it.
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    for rel in manifest:
        src = source_root / rel
        dst = output_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    return manifest


def build_release_tree(scope: str, source_root: Path, output_root: Path) -> list[str]:
    if scope == "full":
        return _build_full_tree(source_root, output_root)
    if scope != "docs_only":
        raise NotImplementedError(f"release scope not implemented yet: {scope}")

    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    manifest: list[str] = []
    for rel_path in DOCS_ONLY_ALLOWLIST:
        src = source_root / rel_path
        if not src.exists():
            raise FileNotFoundError(f"missing allowlisted release file: {rel_path}")
        dst = output_root / rel_path
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        manifest.append(rel_path)

    for rel_dir in DOCS_ONLY_DIR_ALLOWLIST:
        src_dir = source_root / rel_dir
        if not src_dir.is_dir():
            raise FileNotFoundError(f"missing allowlisted release directory: {rel_dir}")
        for file_path in sorted(src_dir.rglob("*")):
            if not file_path.is_file():
                continue
            rel_file = file_path.relative_to(source_root)
            dst = output_root / rel_file
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file_path, dst)
            manifest.append(rel_file.as_posix())

    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/system/release_scope.yaml")
    parser.add_argument("--source-root", default=".")
    parser.add_argument("--output-root", required=True)
    args = parser.parse_args()

    scope = load_release_scope(Path(args.config))
    manifest = build_release_tree(
        scope,
        Path(args.source_root).resolve(),
        Path(args.output_root).resolve(),
    )
    print(f"release_scope={scope}")
    for item in manifest:
        print(item)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
