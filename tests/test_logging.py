"""Auto-generated importability test for logging."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_logging_importable():
    """Verify that logging can be imported without errors."""
    import src.mcp.augur_shared.logging

    assert src.mcp.augur_shared.logging is not None


def test_date_aware_handlers_lazy_open(tmp_path):
    """Handlers must not create empty log files until the first emit."""
    import logging
    from datetime import datetime

    from src.logging.config import (
        _DateAwareFileHandler,
        _DateAwareRotatingHandler,
    )

    today = datetime.now().strftime("%Y-%m-%d")

    err_base = tmp_path / "errors"
    err_handler = _DateAwareFileHandler(
        entity_base_dir=str(err_base),
        filename_pattern="errors_42.log",
    )
    err_path = err_base / today / "errors_42.log"
    assert not err_path.exists(), "errors handler must lazy-open"

    main_base = tmp_path / "main"
    main_handler = _DateAwareRotatingHandler(
        entity_base_dir=str(main_base),
        filename_pattern="00-00_42.log",
        when="H",
        interval=1,
        backupCount=1,
    )
    main_path = main_base / today / "00-00_42.log"
    assert not main_path.exists(), "main handler must lazy-open"

    record = logging.LogRecord("t", logging.ERROR, "p", 1, "msg", None, None)
    err_handler.emit(record)
    main_handler.emit(record)
    err_handler.close()
    main_handler.close()

    assert err_path.exists() and err_path.stat().st_size > 0
    assert main_path.exists() and main_path.stat().st_size > 0


def test_date_aware_handlers_suppress_permission_errors_on_emit(monkeypatch, tmp_path, capsys):
    """Delayed file open permission failures must not print logging tracebacks."""
    import logging

    from src.logging.config import (
        _DateAwareFileHandler,
        _DateAwareRotatingHandler,
    )

    def _raise_permission(self):
        raise PermissionError("logs are not writable")

    monkeypatch.setattr(_DateAwareFileHandler, "_open", _raise_permission)
    monkeypatch.setattr(_DateAwareRotatingHandler, "_open", _raise_permission)

    err_handler = _DateAwareFileHandler(
        entity_base_dir=str(tmp_path / "errors"),
        filename_pattern="errors_42.log",
    )
    main_handler = _DateAwareRotatingHandler(
        entity_base_dir=str(tmp_path / "main"),
        filename_pattern="00-00_42.log",
        when="H",
        interval=1,
        backupCount=1,
    )

    record = logging.LogRecord("t", logging.ERROR, "p", 1, "msg", None, None)
    err_handler.emit(record)
    main_handler.emit(record)
    err_handler.close()
    main_handler.close()

    assert "Logging error" not in capsys.readouterr().err


def test_entity_logger_falls_back_to_console_when_log_dir_unwritable(monkeypatch):
    """Entity logger should keep console logging alive without writable files."""
    import logging

    from src.logging.config import EntityLogger

    def _raise_unwritable_log_dir(self):
        raise PermissionError("logs are read-only")

    monkeypatch.setattr(EntityLogger, "_get_log_dir", _raise_unwritable_log_dir)

    entity_logger = EntityLogger("test-unwritable-logs")

    assert entity_logger.log_dir is None
    assert entity_logger.file_logging_error == "logs are read-only"
    handlers = entity_logger.get_logger().handlers
    assert any(isinstance(handler, logging.StreamHandler) for handler in handlers)
    assert not any(isinstance(handler, logging.FileHandler) for handler in handlers)


def test_mcp_logger_suppresses_fallback_output_when_log_dir_unwritable(monkeypatch):
    """MCP logger must not write fallback warnings to stdio or root logging."""
    import logging

    from src.logging.config import EntityLogger

    root_records = []

    class _RootCapture(logging.Handler):
        def emit(self, record):
            root_records.append(record)

    def _raise_unwritable_log_dir(self):
        raise PermissionError("logs are read-only")

    root_logger = logging.getLogger()
    root_handler = _RootCapture()
    root_logger.addHandler(root_handler)
    monkeypatch.setattr(EntityLogger, "_get_log_dir", _raise_unwritable_log_dir)

    try:
        entity_logger = EntityLogger("mcp")
    finally:
        root_logger.removeHandler(root_handler)

    logger = entity_logger.get_logger()
    handlers = logger.handlers

    assert entity_logger.log_dir is None
    assert entity_logger.file_logging_error == "logs are read-only"
    assert any(isinstance(handler, logging.NullHandler) for handler in handlers)
    assert not any(isinstance(handler, logging.StreamHandler) for handler in handlers)
    assert logger.propagate is False
    assert root_records == []


def test_mcp_logger_suppresses_permission_errors_when_log_file_unwritable(monkeypatch, tmp_path, capsys):
    """MCP logger file-write failures must not leak Python logging tracebacks."""
    import logging

    from src.mcp.augur_shared import logging as mcp_logging

    logger_name = "augur_mcp.permission-test"
    logger = logging.getLogger(logger_name)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    def _raise_permission(self):
        raise PermissionError("logs are not writable")

    monkeypatch.setenv("AUGUR_MCP_LOG_FILE", str(tmp_path / "blocked.log"))
    monkeypatch.setenv("AUGUR_MCP_STDERR_LEVEL", "CRITICAL")
    monkeypatch.setattr(mcp_logging._SafeRotatingFileHandler, "_open", _raise_permission)

    configured = mcp_logging.get_logger("permission-test")
    configured.info("silent file failure")

    assert "Logging error" not in capsys.readouterr().err
