import os
import subprocess
import sys
import time

import pytest
from pathlib import Path


@pytest.fixture
def clean_server_process():
    """Yields a clean environment and kills any server process after test."""
    # Setup: Ensure no stale servers are running matching our signature
    subprocess.run(["pkill", "-f", "python.*src.mcp.augur_framework"], check=False)

    yield

    # Teardown: Kill anything we started
    subprocess.run(["pkill", "-f", "python.*src.mcp.augur_framework"], check=False)


@pytest.mark.e2e
@pytest.mark.skipif(
    sys.platform == "win32", reason="Windows MCP-server subprocess spawn (WinError 2); validation pending (ROADMAP)"
)
def test_server_startup_smoke_test(clean_server_process):
    """
    Smoke test to verify the MCP server starts and stays alive.
    Replicates test-mcp-connection.sh
    """
    # Get the Python executable and module path
    python_exe = sys.executable
    project_root = Path(__file__).parents[2]  # src/lib/tests/mcp -> src/lib -> tests -> root

    cmd = [python_exe, "-m", "src.mcp.augur_framework"]

    # Ensure PYTHONPATH includes the MCP source directory
    env = os.environ.copy()
    mcp_src = str(project_root / "src" / "mcp")
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{project_root}:{mcp_src}:{existing}" if existing else f"{project_root}:{mcp_src}"

    # Start the server with a piped stdin to keep it alive
    process = subprocess.Popen(
        cmd,
        cwd=str(project_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.PIPE,  # Key change: Keep stdin open
        env=env,
        # Own process group on Windows so a child console Ctrl event can't
        # propagate a spurious KeyboardInterrupt up to pytest.
        creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0),
    )

    try:
        # Wait for 3 seconds to check stability (shell script used 2s)
        time.sleep(3)

        # Check if process is still alive
        if process.poll() is not None:
            # It died
            stdout, stderr = process.communicate()
            error_msg = f"Server exited immediately with code {process.returncode}.\nStderr: {stderr.decode()}\nStdout: {stdout.decode()}"
            pytest.fail(error_msg)

        # If we get here, it's alive!
        assert process.poll() is None, "Server process should be running"

    finally:
        # Clean up this specific process
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
