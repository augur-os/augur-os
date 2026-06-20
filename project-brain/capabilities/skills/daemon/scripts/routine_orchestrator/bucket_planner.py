"""Bucket planning for ADR-755 routine orchestrator dispatch."""
from __future__ import annotations

import importlib.util
import sys
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping

import yaml


DispatchStrategy = Literal["inline-sequential", "parallel-fan-out"]
Finding = dict[str, Any]

DEFAULT_FAN_OUT_THRESHOLD = 8


@dataclass(frozen=True)
class FindingBucket:
    """A set of local-semantic findings for one auto-command and file."""

    auto_command: str
    primary_file: str
    findings: list[Finding]

    @property
    def key(self) -> tuple[str, str]:
        return (self.auto_command, self.primary_file)


@dataclass(frozen=True)
class BucketPlan:
    """Dispatch plan for local-semantic buckets plus design-gated findings."""

    buckets: list[FindingBucket]
    strategy: DispatchStrategy
    design_gate_findings: list[Finding]
    fan_out_threshold: int = DEFAULT_FAN_OUT_THRESHOLD


def plan_dispatch(
    findings: list[Finding],
    *,
    loop_name: str,
    fan_out_threshold: int | None = None,
    config: Mapping[str, Any] | None = None,
    project_root: Path | str | None = None,
) -> BucketPlan:
    """Group local-semantic findings and choose an execution strategy."""
    threshold = _resolve_fan_out_threshold(
        loop_name=loop_name,
        fan_out_threshold=fan_out_threshold,
        config=config,
        project_root=project_root,
    )
    grouped: "OrderedDict[tuple[str, str], list[Finding]]" = OrderedDict()
    design_gate_findings: list[Finding] = []

    for finding in findings:
        if _is_deterministic_finding(finding):
            continue
        band = _finding_band(finding)
        if band == _engine_quality().STRUCTURAL:
            design_gate_findings.append(finding)
            continue
        if band != _engine_quality().LOCAL_SEMANTIC:
            continue

        key = (_auto_command(finding), _primary_file(finding))
        grouped.setdefault(key, []).append(finding)

    buckets = [
        FindingBucket(
            auto_command=auto_command,
            primary_file=primary_file,
            findings=list(bucket_findings),
        )
        for (auto_command, primary_file), bucket_findings in grouped.items()
    ]
    strategy: DispatchStrategy = (
        "inline-sequential"
        if len(buckets) <= threshold
        else "parallel-fan-out"
    )
    return BucketPlan(
        buckets=buckets,
        strategy=strategy,
        design_gate_findings=design_gate_findings,
        fan_out_threshold=threshold,
    )


def _resolve_fan_out_threshold(
    *,
    loop_name: str,
    fan_out_threshold: int | None,
    config: Mapping[str, Any] | None,
    project_root: Path | str | None,
) -> int:
    if fan_out_threshold is not None:
        return _positive_int(fan_out_threshold, DEFAULT_FAN_OUT_THRESHOLD)

    active_config = config if config is not None else _load_project_config(project_root)
    loops = active_config.get("loops", {}) if isinstance(active_config, Mapping) else {}
    loop_config = loops.get(loop_name, {}) if isinstance(loops, Mapping) else {}
    if isinstance(loop_config, Mapping) and "fan_out_threshold" in loop_config:
        return _positive_int(loop_config.get("fan_out_threshold"), DEFAULT_FAN_OUT_THRESHOLD)
    return DEFAULT_FAN_OUT_THRESHOLD


def _load_project_config(project_root: Path | str | None) -> dict[str, Any]:
    if project_root is None:
        root = _find_project_root()
    else:
        root = Path(project_root)
    config_path = root / "config" / "system" / "adaptive_loops.yaml"
    if not config_path.is_file():
        return {}
    loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, dict) else {}


def _positive_int(value: Any, default: int) -> int:
    try:
        threshold = int(value)
    except (TypeError, ValueError):
        return default
    return threshold if threshold > 0 else default


def _finding_band(finding: Finding) -> str:
    explicit = finding.get("finding_band", finding.get("band"))
    if explicit:
        return _normalize_band(str(explicit))
    return _engine_quality().classify_finding_band(finding)


def _is_deterministic_finding(finding: Finding) -> bool:
    return (
        finding.get("kind") == "maintenance"
        or finding.get("root_cause_type") == "generated_artifact"
    )


def _normalize_band(band: str) -> str:
    normalized = band.strip().lower().replace("_", "-")
    if normalized == "local-semantic":
        return _engine_quality().LOCAL_SEMANTIC
    if normalized == "structural":
        return _engine_quality().STRUCTURAL
    if normalized == "mechanical":
        return _engine_quality().MECHANICAL
    return normalized


def _auto_command(finding: Finding) -> str:
    value = finding.get("auto_command", finding.get("category", "unknown-auto-command"))
    return str(value)


def _primary_file(finding: Finding) -> str:
    for key in ("primary_file", "path", "file_path", "file"):
        value = finding.get(key)
        if value:
            return str(value)
    return "unknown-file"


def _engine_quality() -> Any:
    try:
        from adaptive import engine_quality

        return engine_quality
    except Exception:  # noqa: BLE001
        scripts_dir = Path(__file__).resolve().parents[1]
        module_path = scripts_dir / "adaptive" / "engine_quality.py"
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))
        spec = importlib.util.spec_from_file_location("adaptive.engine_quality", module_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load adaptive engine_quality from {module_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module


def _find_project_root() -> Path:
    current = Path(__file__).resolve()
    for parent in (current.parent, *current.parents):
        if (parent / "src").is_dir() and (parent / "config").is_dir():
            return parent
    return Path.cwd()
