from __future__ import annotations

import os
import subprocess
from pathlib import Path

from src.lib.onboard.result import OnboardContext, StepResult


def _run(
    cmd: list[str],
    ctx: OnboardContext,
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd or ctx.repo_root), text=True, capture_output=True, env=env)


def _aug(args: list[str]) -> list[str]:
    # Invoke the project's `aug` CLI through `uv run` for cross-OS safety. This
    # matches the scripts/onboard.{sh,ps1} adapters (`uv run aug ...`) and keeps
    # the engine independent of whether `aug` is on PATH in a fresh clone.
    return ["uv", "run", "aug", *args]


def sync_deps(ctx: OnboardContext) -> StepResult:
    """corepack enable; pnpm install; uv sync. Idempotent (package managers no-op
    when nothing changed)."""
    # COREPACK_ENABLE_DOWNLOAD_PROMPT=0: a fresh clone has no cached pnpm, so the
    # pinned packageManager triggers corepack's interactive "about to download"
    # prompt, which fails non-interactively (fresh users + CI). Auto-approve it.
    sync_env = {**os.environ, "COREPACK_ENABLE_DOWNLOAD_PROMPT": "0"}
    # The pnpm workspace root is apps/dashboard (root has no package.json), so
    # `pnpm install` must run there; corepack/uv run from the repo root.
    dashboard_dir = ctx.repo_root / "apps" / "dashboard"
    for cmd, cwd in (
        (["corepack", "enable"], None),
        (["pnpm", "install"], dashboard_dir),
        (["uv", "sync"], None),
    ):
        proc = _run(cmd, ctx, env=sync_env, cwd=cwd)
        if proc.returncode != 0:
            return StepResult.fail(
                f"`{' '.join(cmd)}` failed: {proc.stderr.strip() or proc.stdout.strip()}",
                {"cmd": cmd, "code": proc.returncode},
            )
    return StepResult.ok("Dependencies synced (pnpm install, uv sync)")


def build_dashboard(ctx: OnboardContext) -> StepResult:
    """Build the dashboard via the sanctioned `aug dev build` wrapper (rule 29)."""
    proc = _run(_aug(["dev", "build"]), ctx)
    if proc.returncode != 0:
        return StepResult.fail(
            f"dashboard build failed: {proc.stderr.strip() or proc.stdout.strip()}",
            {"code": proc.returncode},
        )
    return StepResult.ok("Dashboard built (aug dev build)")


def wire_mcp(ctx: OnboardContext) -> StepResult:
    """Generate client MCP configs via `aug config sync`."""
    proc = _run(_aug(["config", "sync"]), ctx)
    if proc.returncode != 0:
        return StepResult.fail(
            f"MCP wiring failed: {proc.stderr.strip() or proc.stdout.strip()}",
            {"code": proc.returncode},
        )
    return StepResult.ok("MCP client configs synced (aug config sync)")


def _default_vault_dir(ctx: OnboardContext) -> Path:
    # Config-driven; falls back to a sibling of the repo. Never hardcode a user path.
    try:
        from src.config.paths import get_vault_dir

        return Path(get_vault_dir())
    except Exception:
        return ctx.repo_root.parent / "Au-vault"


def seed_brain_and_vault(ctx: OnboardContext, vault_dir: Path | None = None) -> StepResult:
    """Initialize the project brain (aug init) and create an empty private vault
    scaffold at a config-driven path. Idempotent and self-healing: each scaffold
    element is created only when missing, so a half-seeded vault (dir exists but
    MEMORY.md absent) repairs itself on re-run. Never overwrites existing user
    content (an existing MEMORY.md is left untouched)."""
    vault = vault_dir or _default_vault_dir(ctx)
    vault_existed = vault.exists()

    inbox = vault / "inbox"
    inbox_created = not inbox.exists()
    inbox.mkdir(parents=True, exist_ok=True)

    memory = vault / "MEMORY.md"
    memory_created = not memory.exists()
    if memory_created:
        memory.write_text("# Memory\n", encoding="utf-8")

    healed = inbox_created or memory_created

    proc = _run(_aug(["init", "--project", str(ctx.repo_root)]), ctx)
    if proc.returncode != 0:
        return StepResult.fail(
            f"brain init failed: {proc.stderr.strip() or proc.stdout.strip()}",
            {"code": proc.returncode},
        )
    if not vault_existed:
        msg = f"Vault scaffold created at {vault}"
    elif healed:
        msg = f"Vault scaffold repaired at {vault}"
    else:
        msg = f"Vault exists at {vault} (skipped)"
    return StepResult.ok(
        f"Brain initialized; {msg}",
        {"vault": str(vault), "created": healed},
    )
