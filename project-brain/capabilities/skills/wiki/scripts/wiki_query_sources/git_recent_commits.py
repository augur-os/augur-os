from __future__ import annotations

import subprocess

from src.config.paths import get_project_root

from .base import SourceResult


def _approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


class GitRecentCommitsAdapter:
    kind = "git_recent_commits"

    def resolve(self, spec: dict, budget_tokens: int) -> SourceResult:
        recent_days = int(spec.get("recent_days", 14))
        cmd = [
            "git",
            "log",
            f"--since={recent_days} days ago",
            "--pretty=format:%h %ai %s",
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=get_project_root(),
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            return SourceResult(text="", citations=[], truncated=False)

        text = result.stdout or ""
        truncated = False
        if _approx_tokens(text) > budget_tokens:
            keep: list[str] = []
            running_tokens = 0
            for line in text.splitlines():
                running_tokens += _approx_tokens(line)
                if running_tokens > budget_tokens:
                    truncated = True
                    break
                keep.append(line)
            text = "\n".join(keep)

        return SourceResult(
            text=text,
            citations=[f"git log --since={recent_days} days ago ({len(text.splitlines())} commits)"],
            truncated=truncated,
        )
