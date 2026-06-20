"""
CLI Bridge - Standard pattern for wrapping external CLIs as Augur MCP tools.

Usage:
    from src.mcp.augur_shared.cli_bridge import CLIBridge

    gog = CLIBridge("gog", install_hint="brew install steipete/tap/gog")
    result = gog.run(["calendar", "list", "--days", "7"])
"""

import json
import shutil
import subprocess  # nosec B404
from typing import Any


def subprocess_run(*args, **kwargs):
    """Compatibility wrapper for subprocess.run (kept patchable for tests)."""
    return subprocess.run(*args, **kwargs)


class CLIBridge:
    """Wrapper for external CLI tools used by Augur plugins.

    Provides a standard interface for checking CLI availability and
    running CLI commands with timeout and error handling.
    """

    def __init__(self, cli_name: str, install_hint: str = ""):
        self.cli_name = cli_name
        self.install_hint = install_hint

    def is_installed(self) -> bool:
        """Check if the CLI tool is available on PATH."""
        return shutil.which(self.cli_name) is not None

    def run(
        self,
        args: list[str],
        timeout: int = 30,
        json_output: bool = False,
    ) -> dict[str, Any]:
        """Run a CLI command and return the result.

        Args:
            args: Command arguments (without the CLI name itself).
            timeout: Timeout in seconds (default 30).
            json_output: If True, parse stdout as JSON.

        Returns:
            dict with stdout, stderr, returncode. If json_output=True
            and parsing succeeds, 'data' key contains the parsed JSON.
        """
        if not self.is_installed():
            return {
                "error": f"{self.cli_name} not installed. {self.install_hint}".strip(),
                "returncode": -1,
            }

        try:
            result = subprocess_run(  # nosec B603
                [self.cli_name] + args,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            output: dict[str, Any] = {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }

            if json_output and result.returncode == 0 and result.stdout.strip():
                try:
                    output["data"] = json.loads(result.stdout)
                except json.JSONDecodeError:
                    pass

            return output

        except subprocess.TimeoutExpired:
            return {
                "error": f"{self.cli_name} timed out after {timeout}s",
                "returncode": -2,
            }
        except FileNotFoundError:
            return {
                "error": f"{self.cli_name} not found. {self.install_hint}".strip(),
                "returncode": -1,
            }

    def run_or_error(self, args: list[str], timeout: int = 30) -> str:
        """Run a CLI command and return stdout on success, error message on failure.

        Convenience method for MCP tool implementations that return a string.
        """
        result = self.run(args, timeout=timeout)
        if "error" in result:
            return result["error"]
        if result["returncode"] != 0:
            return result.get("stderr", "").strip() or f"{self.cli_name} failed with exit code {result['returncode']}"
        return result.get("stdout", "").strip()
