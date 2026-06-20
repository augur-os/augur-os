"""Restore protected system config files to a validated shape."""

from __future__ import annotations

import argparse
import copy
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config.paths import get_cache_dir, get_config_dir, get_project_root
from src.config.schemas.llm_schema import LlmSchemaError, validate_llm_config
from src.config.schemas.settings_schema import validate_settings_config


def _read_yaml_mapping(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return raw if isinstance(raw, dict) else {}


def _atomic_write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            yaml.safe_dump(data, handle, sort_keys=False, default_flow_style=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        finally:
            raise


def _profile_is_complete(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and isinstance(value.get("provider"), str)
        and isinstance(value.get("base_url"), str)
        and isinstance(value.get("model"), str)
    )


def build_restored_llm_config(current: dict[str, Any], template: dict[str, Any]) -> dict[str, Any]:
    """Build a validated llm.yaml shape while preserving usable user values."""

    try:
        validate_llm_config(current)
        return copy.deepcopy(current)
    except LlmSchemaError:
        pass

    restored = copy.deepcopy(template)
    restored_profiles = restored.setdefault("profiles", {})
    if not isinstance(restored_profiles, dict):
        restored_profiles = {}
        restored["profiles"] = restored_profiles

    current_profiles = current.get("profiles")
    if isinstance(current_profiles, dict):
        for name, profile in current_profiles.items():
            if isinstance(name, str) and _profile_is_complete(profile):
                restored_profiles[name] = copy.deepcopy(profile)

    if not restored_profiles:
        # Last-resort conversion for a flat shape that happens to have enough
        # data. The common broken {model, provider} shape lacks base_url and
        # therefore falls back to the template.
        if _profile_is_complete(current):
            restored_profiles["local"] = {
                key: copy.deepcopy(current[key])
                for key in ("provider", "base_url", "model", "timeout_s", "api_key_env", "api_key")
                if key in current
            }

    template_active = restored.get("active_profile")
    current_active = current.get("active_profile")
    if isinstance(current_active, str) and current_active in restored_profiles:
        restored["active_profile"] = current_active
    elif not isinstance(template_active, str) or template_active not in restored_profiles:
        restored["active_profile"] = sorted(restored_profiles)[0]

    restored_tasks: dict[str, str] = {}
    for source in (template.get("tasks"), current.get("tasks")):
        if not isinstance(source, dict):
            continue
        for task, profile_name in source.items():
            if isinstance(task, str) and isinstance(profile_name, str) and profile_name in restored_profiles:
                restored_tasks[task] = profile_name
    restored["tasks"] = restored_tasks

    validate_llm_config(restored)
    return restored


def build_restored_settings(current: dict[str, Any]) -> dict[str, Any]:
    restored: dict[str, Any] = {"mode": "production"}
    if current.get("mode") in {"production", "prod", "dev", "development"}:
        restored["mode"] = current["mode"]
    if isinstance(current.get("default_cli"), str) and current["default_cli"].strip():
        restored["default_cli"] = current["default_cli"].strip()
    validate_settings_config(restored)
    return restored


def _backup(path: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"{path.name}.bak"
    if path.exists():
        backup_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        backup_path.write_text("", encoding="utf-8")
    return backup_path


def restore_system_config(*, apply: bool) -> dict[str, Any]:
    project_root = get_project_root()
    template_path = project_root / "project-brain" / "capabilities" / "skills" / "ai" / "augur" / "config" / "llm.yaml.template"
    llm_path = get_config_dir() / "system" / "llm.yaml"
    settings_path = get_config_dir() / "system" / "settings.yaml"

    template = _read_yaml_mapping(template_path)
    restored_llm = build_restored_llm_config(_read_yaml_mapping(llm_path), template)
    restored_settings = build_restored_settings(_read_yaml_mapping(settings_path))

    result: dict[str, Any] = {
        "success": True,
        "llm_path": str(llm_path),
        "settings_path": str(settings_path),
        "restored_llm": restored_llm,
        "restored_settings": restored_settings,
        "applied": apply,
    }

    if not apply:
        return result

    backup_dir = get_cache_dir() / "system-config-restore"
    result["backups"] = [str(_backup(llm_path, backup_dir)), str(_backup(settings_path, backup_dir))]
    _atomic_write_yaml(llm_path, restored_llm)
    _atomic_write_yaml(settings_path, restored_settings)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write restored files")
    parser.add_argument("--dry-run", action="store_true", help="print restored YAML without writing")
    args = parser.parse_args(argv)

    apply = bool(args.apply and not args.dry_run)
    result = restore_system_config(apply=apply)
    print("# Restored llm.yaml")
    print(yaml.safe_dump(result["restored_llm"], sort_keys=False), end="")
    print("# Restored settings.yaml")
    print(yaml.safe_dump(result["restored_settings"], sort_keys=False), end="")
    if result.get("backups"):
        print("Backups:")
        for backup in result["backups"]:
            print(f"  {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
