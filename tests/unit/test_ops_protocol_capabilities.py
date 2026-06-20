import pytest

from src.lib.ops_protocol import (
    OpsCapabilities,
    coerce_ops_capabilities,
    declare_ops_capabilities,
    resolve_ops_execution,
)


def test_windows_auto_fix_runs_and_allows_fix():
    caps = declare_ops_capabilities(
        platforms=("cross_platform",),
        windows_fix_mode="auto_fix",
    )

    decision = resolve_ops_execution(
        caps,
        platform_name="win32",
        allow_fix=True,
    )

    assert decision.run_scan is True
    assert decision.allow_fix is True
    assert decision.outcome == "ran"
    assert decision.fix_mode == "auto_fix"


def test_windows_report_only_runs_without_fix():
    caps = declare_ops_capabilities(
        platforms=("cross_platform",),
        windows_fix_mode="report_only",
        skip_reason="safe subset only",
    )

    decision = resolve_ops_execution(
        caps,
        platform_name="windows",
        allow_fix=True,
    )

    assert decision.run_scan is True
    assert decision.allow_fix is False
    assert decision.outcome == "report-only"
    assert decision.fix_mode == "report_only"
    assert decision.skip_reason == "safe subset only"


def test_windows_unsupported_skips_scan():
    caps = declare_ops_capabilities(
        platforms=("macos",),
        windows_fix_mode="unsupported",
        skip_reason="launchd-only check",
    )

    decision = resolve_ops_execution(
        caps,
        platform_name="win32",
        allow_fix=True,
    )

    assert decision.run_scan is False
    assert decision.allow_fix is False
    assert decision.outcome == "skipped_unsupported"
    assert decision.fix_mode == "unsupported"
    assert decision.skip_reason == "launchd-only check"


def test_coerce_ops_capabilities_rejects_invalid_values():
    with pytest.raises(TypeError, match="OPS_CAPABILITIES"):
        coerce_ops_capabilities({"platforms": ("windows",)})  # type: ignore[arg-type]


def test_coerce_ops_capabilities_rejects_invalid_dataclass_contents():
    with pytest.raises(TypeError, match="must be a tuple"):
        coerce_ops_capabilities(
            OpsCapabilities(
                platforms=["windows"],  # type: ignore[arg-type]
                windows_fix_mode="auto_fix",
            )
        )

    with pytest.raises(TypeError, match="unsupported values"):
        coerce_ops_capabilities(
            OpsCapabilities(
                platforms=("solaris",),  # type: ignore[arg-type]
                windows_fix_mode="auto_fix",
            )
        )

    with pytest.raises(TypeError, match="windows_fix_mode"):
        coerce_ops_capabilities(
            OpsCapabilities(
                platforms=("cross_platform",),
                windows_fix_mode="bogus",  # type: ignore[arg-type]
            )
        )

    with pytest.raises(TypeError, match="skip_reason"):
        coerce_ops_capabilities(
            OpsCapabilities(
                platforms=("cross_platform",),
                windows_fix_mode="auto_fix",
                skip_reason=1,  # type: ignore[arg-type]
            )
        )
