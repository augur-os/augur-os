from __future__ import annotations

import platform
import re
import shutil
import subprocess

from src.lib.onboard.result import OnboardContext, StepResult

REQUIRED_TOOLS = ["uv", "node", "git", "rg"]

# pnpm (pinned via packageManager) requires the `node:sqlite` builtin, which is
# only available on Node.js >= 22.5. Older Node versions fail `pnpm install` with
# ERR_UNKNOWN_BUILTIN_MODULE, so the dashboard cannot build.
MIN_NODE_MAJOR = 22

# tool -> os -> exact install command
_GUIDANCE = {
    "uv": {
        "darwin": "curl -LsSf https://astral.sh/uv/install.sh | sh   (or: brew install uv)",
        "linux": "curl -LsSf https://astral.sh/uv/install.sh | sh",
        "windows": 'powershell -c "irm https://astral.sh/uv/install.ps1 | iex"',
    },
    "node": {
        "darwin": "brew install node   (enables corepack/pnpm)",
        "linux": "sudo apt-get install -y nodejs npm   (or use nvm)",
        "windows": "winget install OpenJS.NodeJS",
    },
    "git": {
        "darwin": "xcode-select --install   (or: brew install git)",
        "linux": "sudo apt-get install -y git",
        "windows": "winget install Git.Git",
    },
    "rg": {
        "darwin": "brew install ripgrep",
        "linux": "sudo apt-get install -y ripgrep",
        "windows": "winget install BurntSushi.ripgrep.MSVC",
    },
}


def _current_os() -> str:
    sysname = platform.system().lower()
    if sysname.startswith("win"):
        return "windows"
    if sysname == "darwin":
        return "darwin"
    return "linux"


def _node_major() -> int | None:
    """Return the installed Node.js major version, or None if undeterminable."""
    exe = shutil.which("node")
    if not exe:
        return None
    try:
        out = subprocess.run(
            [exe, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    match = re.match(r"v?(\d+)", out.stdout.strip())
    return int(match.group(1)) if match else None


def detect_prereqs(ctx: OnboardContext) -> StepResult:
    """Verify required system tools are installed; guide per-OS if not."""
    missing = [tool for tool in REQUIRED_TOOLS if shutil.which(tool) is None]
    if missing:
        os_key = _current_os()
        lines = [f"Missing prerequisite(s): {', '.join(missing)}. Install, then re-run:"]
        for tool in missing:
            cmd = _GUIDANCE.get(tool, {}).get(os_key, f"install {tool}")
            lines.append(f"  - {tool}: {cmd}")
        return StepResult.guide("\n".join(lines), {"missing": missing, "os": os_key})

    node_major = _node_major()
    if node_major is not None and node_major < MIN_NODE_MAJOR:
        os_key = _current_os()
        cmd = _GUIDANCE["node"].get(os_key, "install node")
        return StepResult.guide(
            f"Node.js {node_major} is too old; Augur requires Node.js >= {MIN_NODE_MAJOR} "
            f"(pnpm needs the node:sqlite builtin). Upgrade, then re-run:\n  - node: {cmd}",
            {"node_major": node_major, "min_node_major": MIN_NODE_MAJOR},
        )

    return StepResult.ok("All prerequisites present: " + ", ".join(REQUIRED_TOOLS))
