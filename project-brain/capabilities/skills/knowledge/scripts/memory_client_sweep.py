"""Run the client-memory sweep for the active brain stack (ADR-811).

Usage: memory_client_sweep.py [--dry-run]
Scheduled daily via the daemon tasks.yaml; safe to run manually any time.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path


def _ensure_project_paths(start: Path) -> Path:
    for candidate in (start.parent, *start.parents):
        if (
            (candidate / "pyproject.toml").is_file()
            and (candidate / "src" / "config" / "paths.py").is_file()
        ):
            for path in (candidate / "src" / "mcp", candidate, candidate / "project-brain" / "capabilities"):
                text = str(path)
                if text not in sys.path:
                    sys.path.insert(0, text)
            return candidate
    raise RuntimeError(f"Unable to locate Augur project root from {start}")


_project_root = _ensure_project_paths(Path(__file__).resolve())

from src.config.paths import get_logs_dir, get_project_root  # noqa: E402
from src.lib.brain_registry_models import BrainType  # noqa: E402
from src.lib.brain_stack import resolve_active_stack  # noqa: E402
from src.lib.client_memory_sweep import (  # noqa: E402
    claude_project_memory_dir,
    sweep_client_memory,
    write_memory_index,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    log_path = get_logs_dir() / "memory_client_sweep.log"
    logging.basicConfig(
        filename=str(log_path), level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    stack = resolve_active_stack(cwd=get_project_root())
    brains = {b.type: b for b in stack.ordered()}
    project_brain = brains.get(BrainType.PROJECT)
    personal_brain = brains.get(BrainType.PERSONAL)

    source = claude_project_memory_dir(get_project_root())
    result = sweep_client_memory(
        source,
        project_brain=project_brain,
        personal_brain=personal_brain,
        source_client="claude-code",
        dry_run=args.dry_run,
    )
    for brain in (project_brain, personal_brain):
        if brain is not None:
            write_memory_index(brain, dry_run=args.dry_run)

    summary = (
        f"source={source} swept={len(result.swept)} "
        f"skipped={len(result.skipped)} errors={len(result.errors)}"
    )
    logging.info(summary)
    print(summary)
    for error in result.errors:
        logging.warning("sweep error: %s", error)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
