from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "wiki_signals_config.py"
SPEC = importlib.util.spec_from_file_location("wiki_signals_config_under_test", MODULE_PATH)
assert SPEC and SPEC.loader
wiki_signals_config = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = wiki_signals_config
SPEC.loader.exec_module(wiki_signals_config)


def test_defaults_when_file_missing(tmp_path: Path) -> None:
    cfg = wiki_signals_config.load_config(tmp_path / "missing.yaml")

    assert cfg.mtime_window_minutes == 30
    assert cfg.tier_caps == {"critical": 5, "high": 15, "medium": 30, "low": 50}
    assert cfg.extraction_limit == 20
    assert cfg.include_logs is False
    assert cfg.client_memory["enabled"] is True
    clients = cfg.client_memory["clients"]
    assert clients["claude"]["path"] == "~/.claude"
    assert clients["claude"]["globs"] == ["projects/*/memory/*.md"]
    assert clients["codex"]["path"] == "~/.codex/sessions"
    assert clients["codex"]["tier"] == "critical"
    assert clients["gemini"]["path"] == "~/.gemini/conversations"
    assert clients["gemini"]["tier"] == "high"
    assert clients["copilot"]["enabled"] is True


def test_yaml_overrides_defaults(tmp_path: Path) -> None:
    config_path = tmp_path / "wiki_signals.yaml"
    config_path.write_text(
        """
mtime_window_minutes: 60
tier_caps:
  critical: 10
extraction_limit: 35
include_logs: true
client_memory:
  clients:
    gemini:
      enabled: false
    codex:
      path: /tmp/codex-sessions
    chatgpt:
      path: /tmp/chatgpt
      tier: high
""",
        encoding="utf-8",
    )

    cfg = wiki_signals_config.load_config(config_path)

    assert cfg.mtime_window_minutes == 60
    assert cfg.tier_caps["critical"] == 10
    assert cfg.tier_caps["high"] == 15
    assert cfg.extraction_limit == 35
    assert cfg.include_logs is True
    clients = cfg.client_memory["clients"]
    assert clients["gemini"]["enabled"] is False
    assert clients["codex"]["path"] == "/tmp/codex-sessions"
    assert clients["chatgpt"]["path"] == "/tmp/chatgpt"
    assert clients["chatgpt"]["tier"] == "high"
