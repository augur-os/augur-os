"""Bootstrap private actual-data command KPI scenarios."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from src.config.paths import get_documents_dir, get_project_root, get_vault_dir
from skills.evals.scripts.command_kpi_schema import PACK_SCHEMA, SCENARIO_SCHEMA


_SAFE_RUN_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _validate_run_id(run_id: str) -> str:
    if not run_id:
        raise ValueError("run_id must not be empty")
    if "/" in run_id or "\\" in run_id or ".." in run_id or not _SAFE_RUN_ID_RE.fullmatch(run_id):
        raise ValueError("run_id must be a safe path component")
    return run_id


def _scenario(command: str, sid: str, **kwargs: Any) -> dict[str, Any]:
    return {"_schema": SCENARIO_SCHEMA, "id": sid, "command": command, **kwargs}


def _first_markdown(root: Path) -> Path | None:
    if not root.exists():
        return None
    for path in sorted(root.rglob("*.md")):
        if path.is_file() and ".git" not in path.parts:
            return path
    return None


def _write_scratch_file(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def bootstrap_private_scenarios(*, run_id: str) -> dict[str, Any]:
    run_id = _validate_run_id(run_id)
    docs = get_documents_dir()
    vault = get_vault_dir()
    repo = get_project_root()

    scenario_dir = docs / "evals" / "commands" / "scenarios"
    scratch = docs / "evals" / "commands" / "scratch" / run_id
    scenario_dir.mkdir(parents=True, exist_ok=True)
    scratch.mkdir(parents=True, exist_ok=True)

    contract = repo / "docs" / "references" / "command-quality-contract.md"
    keep_file = _write_scratch_file(
        scratch / "keep-local-file.md",
        "# KPI Keep Local File\n\nThis file must stay local.\n",
    )
    generated_artifact = _write_scratch_file(
        scratch / "generated-artifact.md",
        "# Generated Artifact\n\nCreated by the command KPI bootstrap.\n",
    )
    stale_artifact = _write_scratch_file(
        scratch / "draft-v2-old.md",
        "# Old Draft\n\nThis is a stale-version fixture for dry-run sweep evaluation.\n",
    )
    # A Claude Desktop / macOS style path with a space in the filename. Saving a file
    # like this must route to local-file quickly and never default to a cloud store.
    desktop_capture = _write_scratch_file(
        scratch / "Claude Desktop Capture.md",
        "# Claude Desktop Capture\n\nDragged in from Claude Desktop; must stay local.\n",
    )
    private_note = _first_markdown(vault) or contract

    scenarios = [
        _scenario(
            "ask",
            "ask-project-canonical-commands",
            client="engine",
            input_class="project-question",
            input="Which commands are canonical in the command quality contract?",
            private_refs=[str(contract)],
            assertions={
                "required_facts": ["ask", "keep", "discover", "adr", "dev", "routines", "sweep"],
                "required_source_refs": [str(contract)],
            },
            max_duration_ms=60000,
        ),
        _scenario(
            "ask",
            "ask-private-note-title",
            client="engine",
            input_class="private-question",
            input="What private note was selected for the KPI smoke?",
            private_refs=[str(private_note)],
            assertions={"required_source_refs": [str(private_note)], "min_source_count": 1},
            max_duration_ms=60000,
        ),
        _scenario(
            "ask",
            "ask-weak-context",
            client="engine",
            input_class="weak-context",
            input="Answer a question with no usable sources.",
            assertions={"expected_answer_mode": "weak-context", "forbidden_claims": ["definitely", "confirmed"]},
            max_duration_ms=10000,
        ),
        _scenario(
            "ask",
            "ask-stale-or-low-context",
            client="engine",
            input_class="quality-gate",
            input="Check low context handling.",
            assertions={"expected_quality_flags": ["too-few-sources"]},
            max_duration_ms=10000,
        ),
        _scenario(
            "keep",
            "keep-local-file",
            client="engine",
            input_class="local-file",
            input=str(keep_file),
            private_refs=[str(keep_file)],
            assertions={"expected_route": "local-file", "forbidden_routes": ["google-drive", "gdrive", "cloud"]},
            max_duration_ms=10000,
        ),
        _scenario(
            "keep",
            "keep-thought",
            client="engine",
            input_class="thought",
            input="Remember the command KPI loop uses automatic scorecards.",
            assertions={"expected_route": "thought"},
            max_duration_ms=10000,
        ),
        _scenario(
            "keep",
            "keep-url",
            client="engine",
            input_class="url",
            input="https://example.com/augur-command-kpi",
            assertions={"expected_route": "url-capture"},
            max_duration_ms=30000,
        ),
        _scenario(
            "keep",
            "keep-generated-artifact",
            client="engine",
            input_class="artifact",
            input=f"--save {generated_artifact}",
            private_refs=[str(generated_artifact)],
            assertions={"expected_route": "generated-artifact"},
            max_duration_ms=10000,
        ),
        _scenario(
            "keep",
            "keep-cloud-request-warns",
            client="engine",
            input_class="local-file-with-cloud-words",
            input=f"{keep_file} to Google Drive",
            private_refs=[str(keep_file)],
            assertions={
                "required_warnings": ["cloud-route-not-selected"],
                "forbidden_routes": ["google-drive", "gdrive"],
            },
            max_duration_ms=10000,
        ),
        _scenario(
            "keep",
            "keep-claude-desktop-local-file",
            client="claude",
            input_class="local-file",
            input=str(desktop_capture),
            private_refs=[str(desktop_capture)],
            assertions={
                "expected_route": "local-file",
                "forbidden_routes": [
                    "google-drive",
                    "gdrive",
                    "dropbox",
                    "onedrive",
                    "icloud",
                    "cloud",
                ],
            },
            max_duration_ms=3000,
        ),
        _scenario(
            "discover",
            "discover-capabilities",
            client="engine",
            input_class="status",
            input="discover",
            assertions={"required_output_keys": ["canonical_commands", "clients"]},
            max_duration_ms=10000,
        ),
        _scenario(
            "discover",
            "discover-generated-surfaces",
            client="engine",
            input_class="surface-check",
            input="discover commands",
            assertions={"required_clients": ["claude", "codex", "gemini"]},
            max_duration_ms=10000,
        ),
        _scenario(
            "adr",
            "adr-index-state",
            client="engine",
            input_class="inspect",
            input="adr index",
            assertions={"required_output_keys": ["adr_count", "recent_statuses"]},
            max_duration_ms=15000,
        ),
        _scenario(
            "adr",
            "adr-dry-run-create",
            client="engine",
            input_class="dry-run",
            input="adr draft command KPI loop",
            assertions={"required_output_keys": ["frontmatter_valid", "would_write_path"]},
            max_duration_ms=15000,
        ),
        _scenario(
            "dev",
            "dev-status",
            client="engine",
            input_class="safe-status",
            input="dev status",
            assertions={"required_output_keys": ["git_status", "verification_policy"]},
            max_duration_ms=60000,
        ),
        _scenario(
            "dev",
            "dev-debug-dry-run",
            client="engine",
            input_class="debug-dry-run",
            input="dev debug",
            assertions={"required_output_keys": ["blockers", "next_actions"]},
            max_duration_ms=60000,
        ),
        _scenario(
            "routines",
            "routines-status",
            client="engine",
            input_class="status",
            input="routines status",
            assertions={"required_output_keys": ["loop_evals", "routine_count"]},
            max_duration_ms=15000,
        ),
        _scenario(
            "routines",
            "routines-evals-loop-present",
            client="engine",
            input_class="registry",
            input="routines list evals",
            assertions={"required_output_keys": ["loop-evals"]},
            max_duration_ms=15000,
        ),
        _scenario(
            "sweep",
            "sweep-dry-run",
            client="engine",
            input_class="dry-run",
            input=str(scratch),
            private_refs=[str(stale_artifact)],
            assertions={"required_output_keys": ["dry_run", "preserved"], "expected_dry_run": True},
            max_duration_ms=30000,
        ),
        _scenario(
            "sweep",
            "sweep-recovery-info",
            client="engine",
            input_class="dry-run",
            input=str(scratch),
            private_refs=[str(stale_artifact)],
            assertions={"required_output_keys": ["recovery_info"]},
            max_duration_ms=30000,
        ),
    ]

    output = {"_schema": PACK_SCHEMA, "run_id": run_id, "scenarios": scenarios}
    path = scenario_dir / f"{run_id}.yaml"
    path.write_text(yaml.safe_dump(output, sort_keys=False), encoding="utf-8")
    return {"success": True, "scenario_path": str(path), "scenario_count": len(scenarios)}
