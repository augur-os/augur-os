"""Auto-detect installed local CLIs and write integration yamls.

Closes the "Connect first integration" onboarding probe for any developer
machine. Walks a registry of well-known local CLIs, runs shutil.which() /
filesystem checks per entry, and writes one yaml per detection to
<vault>/integrations/<id>.yaml — the path the probe at
project-brain/capabilities/skills/onboard/scripts/setup/probes/personalization.py:57
already reads.

Idempotent + non-destructive:
- User-authored fields (e.g. `note`) are preserved on re-scan.
- User-set `enabled: false` is respected — we never override intent.
- New detections write fresh records; vanished detections leave existing
  yamls untouched (operator decides whether to delete).

Registry intentionally focuses on user-visible integrations (Obsidian,
gcloud, gh, code, docker, ollama, claude/codex/gemini/copilot CLIs).
Generic dev toolchain (git, node, pnpm, python) is excluded — those are
prerequisites, not integrations.
"""
from __future__ import annotations

import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml

# Registry: each entry declares ONE detection method (`binary` for PATH-based
# lookup via shutil.which, or `app_path` for filesystem existence — macOS-
# style /Applications/<Name>.app). Both can be present; binary wins.
REGISTRY: list[dict[str, Any]] = [
    {
        "id": "obsidian",
        "name": "Obsidian",
        "type": "local-cli",
        "app_path": "/Applications/Obsidian.app",
        "provides": ["vault editor", "markdown rendering", "graph view", "wikilink resolution"],
        "note": "Augur vault is Obsidian-aware (wikilinks, frontmatter).",
    },
    {
        "id": "gcloud",
        "name": "Google Cloud CLI",
        "type": "local-cli",
        "binary": "gcloud",
        "provides": ["gcp project management", "cloud storage access", "cloud run / functions deploy"],
        "note": "gcloud auth login required for any remote action.",
    },
    {
        "id": "github-cli",
        "name": "GitHub CLI",
        "type": "local-cli",
        "binary": "gh",
        "provides": ["pr management", "issue management", "workflow run inspection", "repo clone/list"],
        "note": "gh auth login required for any remote action.",
    },
    {
        "id": "vscode",
        "name": "Visual Studio Code",
        "type": "local-cli",
        "binary": "code",
        "app_path": "/Applications/Visual Studio Code.app",
        "provides": ["editor launch", "diff", "merge-tool"],
    },
    {
        "id": "docker",
        "name": "Docker",
        "type": "local-cli",
        "binary": "docker",
        "app_path": "/Applications/Docker.app",
        "provides": ["container runtime", "compose", "image management"],
    },
    {
        "id": "ollama",
        "name": "Ollama",
        "type": "local-cli",
        "binary": "ollama",
        "app_path": "/Applications/Ollama.app",
        "provides": ["local LLM runtime", "model registry", "airplane-mode inference"],
    },
    {
        "id": "claude-code",
        "name": "Claude Code CLI",
        "type": "local-cli",
        "binary": "claude",
        "provides": ["augur ai client", "skill execution", "MCP host"],
    },
    {
        "id": "codex",
        "name": "Codex CLI",
        "type": "local-cli",
        "binary": "codex",
        "provides": ["augur ai client", "skill execution", "MCP host"],
    },
    {
        "id": "gemini",
        "name": "Gemini CLI",
        "type": "local-cli",
        "binary": "gemini",
        "provides": ["augur ai client", "skill execution", "MCP host"],
    },
    {
        "id": "jq",
        "name": "jq",
        "type": "local-cli",
        "binary": "jq",
        "provides": ["json processing for scripts"],
    },
    {
        "id": "ripgrep",
        "name": "ripgrep",
        "type": "local-cli",
        "binary": "rg",
        "provides": ["fast full-text search", "unified-search backend", "wiki search"],
        "note": "Powers unified-search and wiki search; without it they fall back to a slower Python scan.",
    },
]


def _resolve(entry: dict[str, Any]) -> str | None:
    """Return absolute path if entry's binary or app_path exists, else None."""
    binary = entry.get("binary")
    if binary:
        path = shutil.which(binary)
        if path:
            return path
    app_path = entry.get("app_path")
    if app_path and Path(app_path).exists():
        return app_path
    return None


def detect(*, registry: Iterable[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Walk the registry and return one record per detected entry.

    Each record is the registry entry merged with `resolved_path`.
    """
    reg = list(registry) if registry is not None else REGISTRY
    detections: list[dict[str, Any]] = []
    for entry in reg:
        resolved = _resolve(entry)
        if resolved is None:
            continue
        detections.append({**entry, "resolved_path": resolved})
    return detections


def _build_yaml_record(entry: dict[str, Any]) -> dict[str, Any]:
    """Map a detected entry to the integration-yaml shape the probe reads."""
    return {
        "id": entry["id"],
        "name": entry["name"],
        "type": entry["type"],
        "enabled": True,
        "binary": entry["resolved_path"],
        "provides": entry.get("provides", []),
        "note": entry.get("note", ""),
        "detected_at": datetime.now(timezone.utc).isoformat(),
    }


def _merge_with_existing(record: dict[str, Any], existing_path: Path) -> dict[str, Any]:
    """Preserve user-authored fields on re-scan. Respect `enabled: false`."""
    if not existing_path.exists():
        return record
    try:
        existing = yaml.safe_load(existing_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return record
    if not isinstance(existing, dict):
        return record
    merged = dict(record)
    # User-set enabled: false is sticky — operator intent wins
    if existing.get("enabled") is False:
        merged["enabled"] = False
    # Preserve user-authored note unless the registry default is different
    # (i.e. only overwrite when existing matches the same registry default)
    if "note" in existing and existing["note"] != record.get("note", ""):
        merged["note"] = existing["note"]
    # Preserve any extra keys the user added (e.g. custom tags)
    for k, v in existing.items():
        if k not in merged:
            merged[k] = v
    return merged


def scan(
    *,
    target_dir: Path,
    registry: Iterable[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Walk the registry, detect installed CLIs, write yamls under target_dir.

    Returns a summary dict with detected/skipped counts and written file paths.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    reg = list(registry) if registry is not None else REGISTRY
    detections = detect(registry=reg)
    written: list[str] = []
    for det in detections:
        target = target_dir / f"{det['id']}.yaml"
        record = _build_yaml_record(det)
        record = _merge_with_existing(record, target)
        target.write_text(yaml.safe_dump(record, sort_keys=False), encoding="utf-8")
        written.append(str(target))
    return {
        "detected_count": len(detections),
        "skipped_count": len(reg) - len(detections),
        "written_files": written,
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "target_dir": str(target_dir),
    }


def main() -> int:
    """CLI entry: scan against the configured vault integrations dir."""
    from src.config.paths import get_vault_dir
    from src.lib.brain_layout import vault_machine_dir
    target = vault_machine_dir(get_vault_dir(), "integrations")
    result = scan(target_dir=target)
    import json
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
