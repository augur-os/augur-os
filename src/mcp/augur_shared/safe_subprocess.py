"""Hang-safe subprocess wrapper for MCP tools.

MCP tools run inside the stdio bridge, whose stdin is the JSON-RPC pipe from the
dashboard. A child process that inherits that stdin can block forever if it (or
a helper such as git's credential/askpass/fsmonitor) reads from it: there is no
terminal and the pipe never yields EOF. This silently hung the activity-summary
widget for the full request timeout.

`safe_run` is a thin wrapper over subprocess.run that injects safe defaults
without changing any explicit caller behavior:

  - stdin=DEVNULL: never inherit the bridge's MCP pipe (the real fix)
  - GIT_TERMINAL_PROMPT=0: git never blocks on an interactive prompt

It deliberately does NOT force a timeout: some tools legitimately run long
operations (installs, configure scripts), and stdin=DEVNULL alone removes the
inherited-stdin hang. Callers that want a timeout still pass their own; it is
preserved. Every kwarg uses setdefault, so explicit caller values always win.
"""

from __future__ import annotations

import os
import subprocess
from subprocess import DEVNULL, CompletedProcess
from typing import Any


def safe_run(*args: Any, **kwargs: Any) -> CompletedProcess[Any]:
    """subprocess.run with bridge-safe defaults (stdin=DEVNULL, no terminal prompts).

    Calls subprocess.run via attribute access (not a captured reference) so test
    patches of `subprocess.run` continue to intercept these calls.
    """
    kwargs.setdefault("stdin", DEVNULL)

    env = kwargs.get("env")
    env = dict(os.environ) if env is None else dict(env)
    env.setdefault("GIT_TERMINAL_PROMPT", "0")
    kwargs["env"] = env

    return subprocess.run(*args, **kwargs)  # noqa: S603


__all__ = ["safe_run"]
