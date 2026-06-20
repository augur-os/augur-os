#!/usr/bin/env python3
"""Import workflow: 5-stage pipeline using src/lib WorkflowRunner (ADR-086).

Stages:
    1. DeepScan  -- folder scan + flow analysis
    2. Blueprint -- generate blueprint.yaml + user Q&A
    3. WriteADR  -- generate ADR for user review (pause point)
    4. CodeGen   -- generate plugin files from blueprint (after approval)
    5. Connect   -- call POST /api/bridge/connections to auto-connect

CLI:
    python3 import_workflow.py --folder ~/Documents/Finance --hub finance
    python3 import_workflow.py --folder ~/Documents/Finance --plan-only  # stop after ADR
    python3 import_workflow.py --folder ~/Documents/Finance --execute    # resume from codegen
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Ensure the src/scripts directory is importable for the src/lib runner
_project_root = Path(__file__).resolve()
while _project_root.name != "plugins" and _project_root != _project_root.parent:
    _project_root = _project_root.parent
_project_root = _project_root.parent
sys.path.insert(0, str(_project_root))
sys.path.insert(0, str(_project_root / "src" / "scripts"))

import re  # noqa: E402
from src.config.paths import get_runtime_dir  # noqa: E402
from workflow_runner import WorkflowRunner  # noqa: E402

from import_stages import (  # noqa: E402
    DeepScanStage,
    BlueprintStage,
    WriteADRStage,
    CodeGenStage,
    ConnectStage,
)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def run_import(
    folder: str,
    hub: str | None = None,
    auto_mode: bool = False,
    plan_only: bool = False,
    execute_only: bool = False,
) -> dict[str, Any]:
    """Run the import workflow.

    Args:
        folder: Path to the data folder.
        hub: Hub identifier. If None, inferred from folder name.
        auto_mode: Skip user questions, use defaults.
        plan_only: Stop after writing the ADR (stages 1-3).
        execute_only: Resume from code generation (stages 4-5), assumes ADR approved.

    Returns:
        Workflow result dict.
    """
    folder_path = Path(folder).expanduser().resolve()

    if not folder_path.is_dir():
        return {"status": "error", "error": f"Not a directory: {folder_path}"}

    if not hub:
        hub = _slugify(folder_path.name)

    # State directory for persistence
    state_dir = get_runtime_dir() / "import" / hub

    # Select stages based on mode
    if plan_only:
        stages = [
            DeepScanStage(),
            BlueprintStage(),
            WriteADRStage(),
        ]
    elif execute_only:
        stages = [
            CodeGenStage(),
            ConnectStage(),
        ]
    else:
        stages = [
            DeepScanStage(),
            BlueprintStage(),
            WriteADRStage(),
            CodeGenStage(),
            ConnectStage(),
        ]

    runner = WorkflowRunner(
        stages,
        state_dir=state_dir,
        auto_mode=auto_mode,
    )

    return runner.run(
        context={"folder": str(folder_path), "hub": hub},
        run_id=f"import-{hub}",
    )


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Import external data folder as a new Augur hub.")
    parser.add_argument(
        "--folder",
        required=True,
        help="Path to the data folder to import",
    )
    parser.add_argument(
        "--hub",
        default=None,
        help="Hub identifier (default: inferred from folder name)",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Skip user questions, use defaults",
    )
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="Stop after writing the ADR (stages 1-3). User reviews before code generation.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Resume from code generation (stages 4-5). Assumes ADR has been reviewed.",
    )

    args = parser.parse_args()
    result = run_import(
        args.folder,
        hub=args.hub,
        auto_mode=args.auto,
        plan_only=args.plan_only,
        execute_only=args.execute,
    )
    json.dump(result, sys.stdout, indent=2, default=str)
    print()


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _slugify(text: str) -> str:
    """Convert text to kebab-case slug."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower())
    return slug.strip("-") or "data"


if __name__ == "__main__":
    main()
