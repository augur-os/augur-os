import json
import sys
from pathlib import Path

# Add project root and daemon scripts dir to sys.path
sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path.cwd() / "project-brain" / "capabilities" / "skills" / "daemon" / "scripts"))

from src.config.paths import get_project_root, get_runtime_dir, get_config_dir
from adaptive.engine import AdaptiveLoopEngine
from adaptive.discovery import discover_auto_commands
from adaptive.heal import heal_detect, heal_fix, format_heal_fix_report

project_root = get_project_root()
runtime_dir = get_runtime_dir()

import yaml

config_path = get_config_dir() / "system" / "adaptive_loops.yaml"
if config_path.exists():
    with open(config_path) as f:
        config = yaml.safe_load(f) or {}
else:
    config = {}

engine = AdaptiveLoopEngine(config, runtime_dir=runtime_dir, project_root=project_root)
registry = discover_auto_commands(project_root)
engine.register_auto_commands(registry)

journal_entries = []
journal_path = runtime_dir / "adaptive" / "journal.jsonl"
if journal_path.exists():
    with open(journal_path) as f:
        for line in f:
            if line.strip():
                journal_entries.append(json.loads(line))

findings = heal_detect(engine.ledger, journal_entries)
print(f"Found {len(findings)} findings")
for f in findings:
    print(f" - {f.loop}/{f.category}: {f.message} ({f.kind})")

results = heal_fix(
    findings, engine.ledger, registry, project_root, journal_entries, force=False
)
print(format_heal_fix_report(results))
