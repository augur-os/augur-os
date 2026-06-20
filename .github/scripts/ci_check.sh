#!/usr/bin/env bash
set -euo pipefail

# Plugin-specific CI: ./ci_check.sh --plugin career/skills/career
# This will focus on plugins/career/skills/career/ and plugins/career/skills/career/data/

PLUGIN=""
while [[ $# -gt 0 ]]; do
  case $1 in
    --plugin|-p)
      PLUGIN="$2"
      shift 2
      ;;
    --help|-h)
      echo "Usage: $0 [--plugin <bundle/skills/name>]"
      echo ""
      echo "Examples:"
      echo "  $0                              # Run full CI"
      echo "  $0 --plugin apps/skills/career  # Run CI for specific plugin"
      echo "  $0 -p apps/skills/career        # Short form"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# Navigate to project root (2 levels up from .github/scripts/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$ROOT"

export PYTHONPATH="$ROOT"

VENV_DIR="${VENV_DIR:-.venv}"
PYTHON="${PYTHON:-python3}"

if [ ! -d "$VENV_DIR" ]; then
  echo "Creating venv at $VENV_DIR"
  "$PYTHON" -m venv "$VENV_DIR"
fi

if [ -f "$VENV_DIR/bin/activate" ]; then
  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
else
  echo "Missing venv activation script at $VENV_DIR/bin/activate"
  exit 1
fi

python -m pip install --upgrade pip
python -m pip install ruff black mypy pytest pytest-cov pytest-asyncio pyyaml httpx pip-audit bandit
python -m pip install -e src/mcp

# Determine targets based on --plugin flag
if [ -n "$PLUGIN" ]; then
  echo "=== Plugin-Specific CI: $PLUGIN ==="
  PLUGIN_DIR="plugins/$PLUGIN"
  DATA_DIR="$PLUGIN_DIR/data"

  if [ ! -d "$PLUGIN_DIR" ]; then
    echo "❌ Plugin directory not found: $PLUGIN_DIR"
    exit 1
  fi

  targets=("$PLUGIN_DIR")
  if [ -d "$DATA_DIR" ]; then
    echo "   Plugin: $PLUGIN_DIR"
    echo "   Data:   $DATA_DIR"
  else
    echo "   Plugin: $PLUGIN_DIR"
    echo "   Data:   (none)"
  fi
else
  targets=(src tests)
  if [ -d packages ]; then
    targets+=(packages)
  fi
  if [ -d plugins ]; then
    targets+=(plugins)
  fi
fi

echo "=== Ruff Lint ==="
ruff check "${targets[@]}" --output-format=github

echo "=== Black Format Check ==="
black --check "${targets[@]}"

echo "=== Mypy Type Check ==="
mypy src/config src/mcp --ignore-missing-imports --no-error-summary

# Audit checks - scoped when plugin specified
if [ -n "$PLUGIN" ]; then
  echo "=== Audit Hardcoded Paths (plugin) ==="
  python .github/scripts/audit_paths.py "plugins/$PLUGIN" "$DATA_DIR" 2>/dev/null || python .github/scripts/audit_paths.py "plugins/$PLUGIN"

  echo "=== Check File Sizes (plugin) ==="
  python << EOF
import sys
from pathlib import Path

plugin_dir = Path("plugins/$PLUGIN")
data_dir = Path("$DATA_DIR")
MAX_SIZE = 500 * 1024  # 500KB

issues = []
for search_dir in [plugin_dir, data_dir]:
    if not search_dir.exists():
        continue
    for f in search_dir.rglob("*"):
        if f.is_file() and f.stat().st_size > MAX_SIZE:
            size_kb = f.stat().st_size // 1024
            issues.append(f"   {f}: {size_kb}KB")

if issues:
    print("⚠️  Large files found:")
    for issue in issues:
        print(issue)
else:
    print("✅ File sizes OK")
EOF
else
  echo "=== Audit Hardcoded Paths ==="
  python .github/scripts/audit_paths.py .

  echo "=== Validate Entity Boundaries ==="
  python .github/scripts/validate_boundaries.py

  echo "=== Audit Logging Usage ==="
  python .github/scripts/audit_logging.py

  echo "=== Audit Data Separation ==="
  python .github/scripts/audit_data_separation.py

  echo "=== Validate Repository Structure ==="
  python .github/scripts/validate_structure.py

  echo "=== Validate File Placements ==="
  python .github/scripts/validate_file_placement.py --check

  echo "=== Validate Agent Instruction Artifacts ==="
  PYTHONPATH="$PWD/project-brain/capabilities:$PWD:$PWD/src/mcp" python -m skills.ai.scripts.sync_agents --check

  echo "=== Validate IDE Registry Freshness ==="
  python apps/dashboard/scripts/generate_registry.py --check

  echo "=== Check Runtime Gitignore ==="
  python .github/scripts/check_runtime_gitignore.py || echo "⚠️  Runtime gitignore check had warnings (non-blocking)"

  echo "=== Check File Sizes ==="
  python .github/scripts/check_sizes.py || echo "⚠️  Size check had warnings (non-blocking)"
fi

# Performance checks - skip for plugin-specific CI (global checks)
if [ -z "$PLUGIN" ]; then
  echo "=== Performance: Tool Count Check ==="
  python << 'EOF'
import json
import yaml
import sys
import os
from pathlib import Path

# ADR-260: Try assembled_tool_config.json first, fall back to mcp_tool_groups.yaml
config_path = Path("config/dashboard/generated/assembled_tool_config.json")
if not config_path.exists():
    config_path = Path("config/dashboard/mcp_tool_groups.yaml")
if not config_path.exists():
    print("⚠️ Tool config not found, skipping tool count check")
    sys.exit(0)

with open(config_path) as f:
    if config_path.suffix == ".json":
        config = json.load(f)
    else:
        config = yaml.safe_load(f)

core_tools = config.get("core_tools", [])
# Core tools were expanded in ADR-105 hub-driven scoping.
# Keep a guardrail, but allow current baseline plus modest growth.
MAX_CORE_TOOLS = int(os.environ.get("MAX_CORE_TOOLS", "45"))

print(f"   Core tools: {len(core_tools)} (max: {MAX_CORE_TOOLS})")

if len(core_tools) > MAX_CORE_TOOLS:
    print(f"❌ FAIL: Core tools ({len(core_tools)}) exceeds threshold ({MAX_CORE_TOOLS})")
    sys.exit(1)
print("✅ Core tool count OK")
EOF

  echo "=== Performance: Duplicate Tool Check ==="
  python << 'EOF'
import sys
import re
from pathlib import Path

tool_pattern = re.compile(r'@mcp\.tool\(\s*name=["\']([^"\']+)["\']')
tool_names = {}

ALLOWED_DUPLICATES = {}

for search_path in [Path("src/mcp"), Path("plugins")]:
    if not search_path.exists():
        continue
    for py_file in search_path.rglob("*.py"):
        try:
            content = py_file.read_text()
            for tool_name in tool_pattern.findall(content):
                if tool_name not in tool_names:
                    tool_names[tool_name] = []
                tool_names[tool_name].append(str(py_file))
        except Exception:
            pass

duplicates = {n: f for n, f in tool_names.items() if len(f) > 1}

filtered_duplicates = {}
for name, files in duplicates.items():
    normalized = set(files)
    allowed = ALLOWED_DUPLICATES.get(name)
    if allowed and normalized == allowed:
        continue
    filtered_duplicates[name] = files

print(f"   Total tools: {len(tool_names)}")

if filtered_duplicates:
    print(f"❌ FAIL: {len(filtered_duplicates)} duplicate tool names:")
    for name, files in filtered_duplicates.items():
        print(f"      '{name}': {files}")
    sys.exit(1)
print("✅ No duplicate tools")
EOF

  echo "=== Cross-Platform: Service Healer Check ==="
  python -c "
from plugins.daemon.skills.daemon.scripts.service_healer import get_project_root, heal_all_services
import sys
print(f'   Platform: {sys.platform}')
print(f'   Project root: {get_project_root()}')
" || echo "⚠️ Service healer check skipped"
fi

# Run tests based on scope
if [ -n "$PLUGIN" ]; then
  echo "=== Plugin Tests: $PLUGIN ==="
  PLUGIN_DIR="plugins/$PLUGIN"

  # Install plugin deps if present
  if [ -f "$PLUGIN_DIR/requirements.txt" ]; then
    echo "   Installing plugin dependencies..."
    python -m pip install -r "$PLUGIN_DIR/requirements.txt"
  fi
  if [ -f "$PLUGIN_DIR/pyproject.toml" ]; then
    python -m pip install -e "$PLUGIN_DIR"
  fi

  # Run plugin tests if they exist
  if [ -d "$PLUGIN_DIR/tests" ]; then
    pytest "$PLUGIN_DIR/tests" --verbose --cov="$PLUGIN_DIR" --cov-report=term-missing
  elif [ -d "$PLUGIN_DIR/_dev/tests" ]; then
    pytest "$PLUGIN_DIR/_dev/tests" --verbose --cov="$PLUGIN_DIR" --cov-report=term-missing
  else
    echo "   No tests found in $PLUGIN_DIR/tests or $PLUGIN_DIR/_dev/tests"
  fi

  # Validate plugin SKILL.md if present
  if [ -f "$PLUGIN_DIR/SKILL.md" ]; then
    echo "=== Validate SKILL.md ==="
    python << EOF
import sys
from pathlib import Path

skill_md = Path("$PLUGIN_DIR/SKILL.md")
content = skill_md.read_text()
lines = len(content.splitlines())

print(f"   SKILL.md: {lines} lines")
if lines > 150:
    print(f"⚠️  WARNING: SKILL.md exceeds 150 lines ({lines})")

required = ["## Commands", "## Installation"]
for section in required:
    if section not in content:
        print(f"⚠️  WARNING: Missing section '{section}'")
print("✅ SKILL.md validated")
EOF
  fi
else
  echo "=== Root Tests ==="
  pytest tests/ --verbose --ignore=tests/integration/

  echo "=== Shared Tests ==="
  if [ -d "tests/src" ]; then
    pytest tests/src/ -v --tb=short
  elif [ -d "src/tests" ]; then
    pytest src/tests/ -v --tb=short
  else
    echo "No shared tests directory found; skipping."
  fi

  echo "=== Integration Tests ==="
  if [ -d "tests/integration" ]; then
    pytest tests/integration/ --verbose
  elif [ -d "src/tests/integration" ]; then
    pytest src/tests/integration/ --verbose
  else
    echo "No integration tests directory found; skipping."
  fi

  echo "=== MCP Tests ==="
  if [ -d "tests/mcp" ]; then
    pytest tests/mcp/ --verbose
  elif [ -d "src/tests/mcp" ]; then
    pytest src/tests/mcp/ --verbose
  else
    echo "No MCP tests directory found; skipping."
  fi

  echo "=== Skill Tests ==="
  if [ -d packages ]; then
    while IFS= read -r -d '' test_dir; do
      skill_dir="$(dirname "$test_dir")"
      if [ -f "$skill_dir/pyproject.toml" ]; then
        python -m pip install -e "$skill_dir"
      elif [ -f "$skill_dir/_dev/requirements.txt" ]; then
        python -m pip install -r "$skill_dir/_dev/requirements.txt"
      fi
      pytest "$test_dir" --verbose --cov="$skill_dir" --cov-report=term-missing --cov-fail-under=70
    done < <(find packages -maxdepth 2 -type d -name tests -print0)
  fi
fi

# Security and dashboard checks (skip for plugin-specific CI)
if [ -n "$PLUGIN" ]; then
  echo "=== Security: Plugin-scoped bandit ==="
  bandit -r "plugins/$PLUGIN" --exclude "tests,_dev" -ll --format txt || true

  # Check plugin requirements if present
  if [ -f "plugins/$PLUGIN/requirements.txt" ]; then
    echo "=== Security: Plugin pip-audit ==="
    pip-audit -r "plugins/$PLUGIN/requirements.txt" --desc || true
  fi

  # Check if plugin has dashboard components
  if [ -d "plugins/$PLUGIN/dashboard" ]; then
    echo "=== Plugin Dashboard Validation ==="
    python .github/scripts/validate_dashboard.py "$PLUGIN" 2>/dev/null || echo "   Dashboard validation skipped"
  fi

  echo ""
  echo "✅ Plugin CI complete for: $PLUGIN"
else
  echo "=== Security: pip-audit ==="
  if [ -f "src/mcp/pyproject.toml" ]; then
    pushd src/mcp >/dev/null
    python -m pip install -e . --quiet
    pip-audit --desc --fix --dry-run
    popd >/dev/null
  fi

  pip_audit_fallback_local=false
  while IFS= read -r -d '' req; do
    echo "Checking $req"
    if ! pip-audit -r "$req" --desc; then
      echo "⚠️  pip-audit requirements mode failed for $req; falling back to local environment audit"
      python -m pip install -r "$req" --quiet
      pip_audit_fallback_local=true
    fi
  done < <(find . -name "requirements.txt" -not -path "./.venv/*" -not -path "./node_modules/*" -print0)

  if [ "$pip_audit_fallback_local" = true ]; then
    echo "=== Security: pip-audit (local fallback) ==="
    pip-audit --local --desc
  fi

  echo "=== Security: bandit ==="
  bandit -r packages/ src/ --exclude ".venv,node_modules,tests,_dev" -ll --format txt

  echo "=== Security: gitleaks ==="
  if ! command -v gitleaks >/dev/null 2>&1; then
    echo "gitleaks not found. Install with: brew install gitleaks"
    exit 1
  fi
  gitleaks detect --source . --verbose --no-git --gitleaks-ignore-path .gitleaksignore

  echo "=== Security: npm audit ==="
  if [ -d "apps/dashboard" ]; then
    pushd apps/dashboard >/dev/null
    npm ci
    npm audit --audit-level=high
    popd >/dev/null
  fi

  dashboard_changed=false
  if git diff --name-only HEAD -- apps/dashboard | grep -q .; then
    dashboard_changed=true
  fi
  if [ "${RUN_DASHBOARD_TESTS:-}" = "1" ]; then
    dashboard_changed=true
  fi
  if [ "${SKIP_DASHBOARD_TESTS:-}" = "1" ]; then
    dashboard_changed=false
  fi

  if [ "$dashboard_changed" = "true" ]; then
    echo "=== Dashboard Tests ==="
    pushd apps/dashboard >/dev/null
    npm test -- --coverage --passWithNoTests
    popd >/dev/null
  else
    echo "=== Dashboard Tests ==="
    echo "No dashboard changes detected; skipping."
  fi
fi
