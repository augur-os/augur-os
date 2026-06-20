"""Tests for CLI logging setup."""

from __future__ import annotations

import logging
import os

from src import cli


def test_cli_logging_is_suppressed_before_plugin_discovery(monkeypatch) -> None:
    calls: list[int] = []
    monkeypatch.delenv("AUGUR_CLI_MODE", raising=False)
    monkeypatch.delenv("AUGUR_LOG_LEVEL", raising=False)
    monkeypatch.setattr(logging, "disable", lambda level: calls.append(level))

    cli._configure_cli_logging(verbose=False)

    assert os.environ["AUGUR_CLI_MODE"] == "1"
    assert os.environ["AUGUR_LOG_LEVEL"] == "ERROR"
    assert calls[-1] == logging.WARNING
