from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def bash_command() -> str:
    found = shutil.which("bash")
    if found:
        return found

    for candidate in (
        Path("C:/Program Files/Git/bin/bash.exe"),
        Path("C:/Program Files/Git/usr/bin/bash.exe"),
    ):
        if candidate.is_file():
            return str(candidate)

    return "bash"


def run_bash_script(
    script: Path,
    *args: str,
    cwd: Path,
    input_text: str = "",
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    raw = subprocess.run(
        [bash_command(), str(script), *args],
        cwd=cwd,
        input=input_text.encode("utf-8"),
        capture_output=True,
        check=False,
        env=env,
    )
    return subprocess.CompletedProcess(
        args=raw.args,
        returncode=raw.returncode,
        stdout=raw.stdout.decode("utf-8", errors="replace"),
        stderr=raw.stderr.decode("utf-8", errors="replace"),
    )
