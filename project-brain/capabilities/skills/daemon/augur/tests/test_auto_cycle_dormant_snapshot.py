from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from skills.daemon.scripts.adaptive.engine import AdaptiveLoopEngine


class _Module:
    def __init__(self):
        self.last_ctx = None

    def scan(self, ctx):
        self.last_ctx = ctx

        @dataclass
        class ScanResult:
            issues: list = field(default_factory=list)
            summary: str = ""
            severity: str = "info"
            health: str = "verified"

        return ScanResult(summary="clean")

    def fix(self, ctx, issues):
        raise AssertionError("clean scan should not call fix()")


@dataclass
class _Entry:
    name: str
    module: object
    loop_name: str
    tier: int = 0
    trigger: str = "nightly"
    scheduler: str = "codex"
    initial_trust: float = 0.0
    config: dict = field(default_factory=dict)
    plugin_root: Path = field(default_factory=Path.cwd)


def test_run_auto_cycle_executes_snapshotless_dormant_category(tmp_path):
    config = {
        "engine": {"enabled": True, "verify_command": ""},
        "loops": {
            "duplication": {
                "enabled": True,
                "trigger": "nightly",
                "budget": 5,
                "budget_growth_rate": 1,
                "categories": {
                    "auto-duplication": {
                        "enabled": True,
                        "trust": 0.8,
                        "tier": 0,
                    },
                },
            },
        },
    }
    engine = AdaptiveLoopEngine(config, runtime_dir=tmp_path, project_root=tmp_path)
    module = _Module()
    engine.register_auto_commands(
        {
            "auto-duplication": _Entry(
                name="auto-duplication",
                module=module,
                loop_name="duplication",
            )
        }
    )

    loop_state = engine.ledger.get_loop_state("duplication")
    cat_state = loop_state.categories["auto-duplication"]
    cat_state.difficulty = 4
    cat_state.consecutive_clean_scans = 25
    cat_state.strategy = "dormant"
    loop_state.cycle_count = 1

    report = engine.run_auto_cycle("duplication")

    assert module.last_ctx is not None
    assert cat_state.strategy == "scan"
    assert cat_state.consecutive_clean_scans == 1
    assert [category.name for category in report.categories] == ["auto-duplication"]
