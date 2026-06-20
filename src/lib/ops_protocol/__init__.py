"""
Ops Command Protocol — shared interface for all auto-* commands.

Every auto-* command (daemon-managed operations) implements this protocol.
Two execution paths reach the same implementation:
  1. User: /auto-lint -> CLI loads module -> calls scan() then fix()
  2. Daemon: engine discovers module -> calls scan(difficulty=N) -> trust-gates fix()

See ADR-200 for full architecture.
"""

from __future__ import annotations

import subprocess  # noqa: F401 — exposed for monkeypatching in tests

# ---------------------------------------------------------------------------
# Core: data models, protocol, helpers
# ---------------------------------------------------------------------------
from src.lib.ops_protocol._core import (  # noqa: F401
    DifficultySpec,
    FixResult,
    FixType,
    IssueKind,
    OpsCapabilities,
    OpsCommand,
    OpsContext,
    OpsExecutionDecision,
    RootCauseType,
    ScanHealth,
    ScanResult,
    SessionContext,
    Severity,
    SupportedPlatform,
    WindowsFixMode,
    clear_report,
    coerce_ops_capabilities,
    declare_ops_capabilities,
    evolution_gap,
    issue_fingerprint,
    make_issue,
    make_test_ctx,
    report_only_fix,
    resolve_ops_execution,
    validate_ops_module,
    write_report,
)

# ---------------------------------------------------------------------------
# Classify: fix classification + intentional-skip guard
# ---------------------------------------------------------------------------
from src.lib.ops_protocol._classify import (  # noqa: F401
    DeletionInfo,
    FixClassification,
    ModificationInfo,
    _check_git_deletion_history,
    _check_git_recent_modification,
    _extract_reason,
    check_intentional_skip,
    classify_fix,
    make_migration_incomplete_issue,
)

# ---------------------------------------------------------------------------
# Scan: shared scanning utilities
# ---------------------------------------------------------------------------
from src.lib.ops_protocol._scan import (  # noqa: F401
    CANONICAL_BLOCK_TYPES,
    _collect_page_routes_from_root,
    _dashboard_app_root,
    _parse_catchall_registry,
    check_http_route,
    collect_all_block_ids,
    find_api_routes,
    find_page_routes,
)

__all__ = [
    # Core models
    "ScanResult",
    "SessionContext",
    "FixResult",
    "OpsCapabilities",
    "OpsExecutionDecision",
    "OpsContext",
    "OpsCommand",
    "DifficultySpec",
    # Type aliases
    "Severity",
    "ScanHealth",
    "SupportedPlatform",
    "WindowsFixMode",
    "IssueKind",
    "RootCauseType",
    "FixType",
    # Core helpers
    "declare_ops_capabilities",
    "coerce_ops_capabilities",
    "resolve_ops_execution",
    "issue_fingerprint",
    "make_issue",
    "validate_ops_module",
    "write_report",
    "clear_report",
    "evolution_gap",
    "report_only_fix",
    "make_test_ctx",
    # Classification
    "FixClassification",
    "DeletionInfo",
    "ModificationInfo",
    "classify_fix",
    "make_migration_incomplete_issue",
    "check_intentional_skip",
    # Scanning
    "CANONICAL_BLOCK_TYPES",
    "collect_all_block_ids",
    "find_page_routes",
    "find_api_routes",
    "check_http_route",
]
