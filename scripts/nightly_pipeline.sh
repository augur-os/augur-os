#!/usr/bin/env bash
set -euo pipefail

# Colors for output
BLUE='\033[0;34m'
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

print_header() {
    echo -e "\n${BLUE}==================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}==================================================${NC}\n"
}

print_step() {
    echo -e "${GREEN}>>> $1${NC}"
}

fail() {
    echo -e "${RED}❌ $1 failed${NC}"
    exit 1
}

# Ensure we are in the project root
cd "$(dirname "$0")/.."

print_header "Nightly Hardening Cycle"

# 1. Python Tests
print_step "1. Python Tests"
uv run python -mpytest tests/ project-brain/capabilities/skills/*/augur/tests/ -v --tb=short || fail "Python Tests"

# 2. Dashboard Tests
print_step "2. Dashboard Tests"
(cd apps/dashboard && pnpm test -- --watchAll=false) || fail "Dashboard Tests"

# 3. Lint & Quality
print_step "3. Lint & Quality"
echo "Running Ruff..."
uv run python -mruff check src/ plugins/ plugins/ .github/scripts/ || fail "Ruff Lint"

echo "Running Mypy..."
uv run python -mmypy src/config src/mcp --ignore-missing-imports --no-error-summary || fail "Mypy Type Check"

echo "Running TypeScript Lint & Check..."
(cd apps/dashboard && pnpm exec tsc --noEmit && pnpm exec eslint . --max-warnings=0) || fail "TypeScript Quality Checks"

# 4. Security Scan
print_step "4. Security Scan"
echo "Running Bandit..."
uv run python -mbandit -r plugins/ src/ plugins/ -c pyproject.toml -lll -q || fail "Bandit Security Scan"

echo "Running Gitleaks..."
if command -v gitleaks &> /dev/null; then
    gitleaks detect --source . --no-banner || fail "Gitleaks"
else
    echo "⚠️ gitleaks not found, skipping..."
fi

# 5. Build
print_step "5. Build"
(cd apps/dashboard && pnpm run build) || fail "Dashboard Build"

# 6. Code Health Metrics
print_step "6. Code Health Metrics"
python3 .github/scripts/scan_code_markers.py --summary || fail "Scan Code Markers"
python3 .github/scripts/track_codebase_metrics.py --json || fail "Track Codebase Metrics"
python3 .github/scripts/coverage_tracker.py --save || fail "Coverage Tracker"

print_header "Nightly Cycle Complete: SUCCESS"
