"""Base adapter implementation with common utilities."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from src.lib.ai.ide_intent import IDEAdapter


class BaseAdapter(IDEAdapter):
    """Base adapter with common utilities."""

    def __init__(self, ide_name: str):
        super().__init__(ide_name)
        self._config_paths: list[Path] = []

    def _backup_config(self, config_path: Path) -> Path:
        """Create a timestamped backup of a config file."""
        if not config_path.exists():
            return config_path

        backup_dir = config_path.parent / ".backups"
        backup_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = backup_dir / f"{config_path.name}.{timestamp}.bak"

        shutil.copy2(config_path, backup_path)
        return backup_path

    def _write_config_safely(self, config_path: Path, content: str, format: str = "json") -> dict[str, Any]:
        """
        Write config file with backup.

        Returns:
            dict with keys: success, backup_path, error
        """
        try:
            backup_path = None
            if config_path.exists():
                backup_path = self._backup_config(config_path)

            config_path.parent.mkdir(parents=True, exist_ok=True)

            if format == "json":
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump(json.loads(content) if isinstance(content, str) else content, f, indent=2)
            else:
                with open(config_path, "w", encoding="utf-8") as f:
                    f.write(content)

            return {"success": True, "backup_path": str(backup_path) if backup_path else None, "error": None}
        except Exception as e:
            return {"success": False, "backup_path": None, "error": str(e)}

    def _read_config(self, config_path: Path, format: str = "json") -> Any:
        """Read config file."""
        if not config_path.exists():
            return None

        try:
            if format == "json":
                with open(config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            else:
                with open(config_path, "r", encoding="utf-8") as f:
                    return f.read()
        except Exception:
            return None
