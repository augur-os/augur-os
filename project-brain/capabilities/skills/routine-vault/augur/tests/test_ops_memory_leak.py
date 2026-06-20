"""Tests for auto-memory-leak scanning."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from src.lib.ops_protocol import OpsContext

from memory_leak import _scan_file, fix, scan


def test_scan_skips_client_skill_files_outside_project_root(tmp_path: Path):
    inside_dir = tmp_path / ".claude" / "skills" / "demo"
    inside_dir.mkdir(parents=True)
    (inside_dir / "safe.ts").write_text("const value = 1;\n", encoding="utf-8")

    outside_root = tmp_path.parent / "external-skill-cache"
    outside_dir = outside_root / "skills" / "cached"
    outside_dir.mkdir(parents=True, exist_ok=True)
    (outside_dir / "leaky.ts").write_text(
        "'use client';\nuseEffect(() => { setInterval(() => {}, 1000); }, []);\n",
        encoding="utf-8",
    )

    with patch("memory_leak.get_all_client_skill_dirs", return_value=[inside_dir, outside_dir]):
        result = scan(OpsContext(project_root=tmp_path))

    assert result.severity == "info"
    assert result.items_scanned == 1
    assert result.issues == []


def test_scan_file_flags_real_aggressive_polling_for_short_fetch_interval():
    issues = _scan_file(
        Path("apps/dashboard/components/LivePanel.tsx"),
        """
'use client';
import { useEffect } from 'react';

export default function LivePanel() {
  useEffect(() => {
    const id = setInterval(async () => {
      await fetch('/api/live-data');
    }, 1000);
    return () => clearInterval(id);
  }, []);
  return null;
}
""".strip(),
    )

    assert any(issue["pattern"] == "aggressive-polling" for issue in issues)


def test_scan_file_ignores_one_shot_delays_and_local_progress_timers():
    issues = _scan_file(
        Path("apps/dashboard/components/LocalOnly.tsx"),
        """
'use client';
import { useEffect } from 'react';

export default function LocalOnly() {
  useEffect(() => {
    const timer = setInterval(() => {
      setProgress((value) => Math.min(value + 5, 95));
    }, 200);
    return () => clearInterval(timer);
  }, []);

  async function handleStart() {
    await new Promise((resolve) => setTimeout(resolve, 300));
  }

  return null;
}
""".strip(),
    )

    assert all(issue["pattern"] != "aggressive-polling" for issue in issues)
    assert all(issue["pattern"] != "setInterval-without-cleanup" for issue in issues)


def test_fix_prunes_stale_markers_when_issue_no_longer_reproduces(tmp_path: Path):
    inside_dir = tmp_path / ".claude" / "skills" / "demo"
    inside_dir.mkdir(parents=True)
    target = inside_dir / "local_only.tsx"
    target.write_text(
        "\n".join(
            [
                "'use client';",
                "// TODO_BUG(auto-memory-leak): aggressive-polling — Polling interval 200ms is under 10s — causes high CPU/network usage",
                "const timer = setInterval(() => {",
                "  setProgress((value) => Math.min(value + 5, 95));",
                "}, 200);",
            ]
        ),
        encoding="utf-8",
    )

    with (
        patch("memory_leak.get_all_client_skill_dirs", return_value=[inside_dir]),
        patch("memory_leak._commit_files", return_value=True),
    ):
        result = fix(OpsContext(project_root=tmp_path, dry_run=False), [])

    assert result.summary == "Removed 1 stale memory leak markers"
    assert result.actions == [
        {
            "status": "removed",
            "pattern": "aggressive-polling",
            "file": ".claude/skills/demo/local_only.tsx",
            "line": 2,
        }
    ]
    assert result.changes == [".claude/skills/demo/local_only.tsx"]
    assert "TODO_BUG(auto-memory-leak)" not in target.read_text(encoding="utf-8")
