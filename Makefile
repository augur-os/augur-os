# Augur Development Commands
# ================================
# Local CI/CD commands that mirror GitHub Actions workflows
#
# Usage:
#   make help        - Show all available commands
#   make install     - Install all dependencies
#   make quality     - Run all quality checks (mirrors ci-quality.yml)
#   make test        - Run all tests (mirrors ci-test.yml)
#   make pre-merge   - Full pre-merge validation
#   make security    - Run security scans (mirrors ci-security.yml)

.PHONY: help install lint lint-fix lint-python lint-python-fix lint-ts lint-ts-fix format format-check \
        typecheck typecheck-python typecheck-ts \
        audit audit-paths audit-boundaries audit-logging audit-data audit-structure \
        dashboard-build validate-tab-registry ui-checks \
        test test-python test-integration test-dashboard test-mcp test-skills \
        coverage quality security pre-merge post-merge clean

# Colors for output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

PY_TARGETS := src tests
ifneq ("$(wildcard plugins)","")
PY_TARGETS += plugins
endif

# Default target
help:
	@echo "$(BLUE)Augur Development Commands$(NC)"
	@echo "================================"
	@echo ""
	@echo "$(GREEN)Setup:$(NC)"
	@echo "  install        Install all dependencies (Python + Node.js)"
	@echo ""
	@echo "$(GREEN)Quality (mirrors ci-quality.yml):$(NC)"
	@echo "  lint           Run all linters (ruff + eslint)"
	@echo "  lint-fix       Auto-fix lint where possible"
	@echo "  lint-python    Run Python linter (ruff)"
	@echo "  lint-ts        Run TypeScript linter (eslint)"
	@echo "  format         Format code (black)"
	@echo "  format-check   Check formatting (black --check)"
	@echo "  typecheck      Run type checkers (mypy + tsc)"
	@echo "  ui-checks      Run dashboard build + tab registry validation"
	@echo "  audit          Run all audit scripts"
	@echo "  quality        Run all quality checks"
	@echo ""
	@echo "$(GREEN)Testing (mirrors ci-test.yml):$(NC)"
	@echo "  test           Run all tests (root + skills + mcp + integration + dashboard)"
	@echo "  test-python    Run root Python tests (excludes integration)"
	@echo "  test-integration Run integration tests"
	@echo "  test-dashboard Run dashboard tests (Jest)"
	@echo "  test-mcp       Run MCP integration tests"
	@echo "  test-skills    Run skill tests with coverage"
	@echo "  coverage       Run tests with coverage"
	@echo ""
	@echo "$(GREEN)Security (mirrors ci-security.yml):$(NC)"
	@echo "  security       Run security scans (pip-audit, npm audit, bandit)"
	@echo ""
	@echo "$(GREEN)Workflows:$(NC)"
	@echo "  pre-merge      Full pre-merge validation (quality + tests)"
	@echo "  post-merge     Post-merge full test suite"
	@echo "  clean          Clean generated files"

# ============================================
# SETUP
# ============================================

install:
	@echo "$(BLUE)=== Installing Dependencies ===$(NC)"
	@echo "Setting up Python environment..."
	uv sync
	uv pip install -e src/mcp
	@echo ""
	@echo "Setting up Node.js dependencies..."
	npm install
	@echo ""
	@echo "$(GREEN)✓ Installation complete$(NC)"

# ============================================
# LINTING
# ============================================

lint-python:
	@echo "$(BLUE)=== Running Ruff Linter ===$(NC)"
	uv run ruff check $(PY_TARGETS)

lint-python-fix:
	@echo "$(BLUE)=== Fixing Ruff Issues ===$(NC)"
	uv run ruff check $(PY_TARGETS) --fix

lint-ts:
	@echo "$(BLUE)=== Running ESLint ===$(NC)"
	npm run dashboard:lint

lint: lint-python lint-ts
	@echo "$(GREEN)✓ All linting passed$(NC)"

lint-ts-fix:
	@echo "$(BLUE)=== Fixing ESLint Issues ===$(NC)"
	npm --workspace dashboard run lint -- --fix

lint-fix: lint-python-fix lint-ts-fix
	@echo "$(GREEN)✓ All lint fixes applied$(NC)"

# ============================================
# FORMATTING
# ============================================

format:
	@echo "$(BLUE)=== Formatting with Black ===$(NC)"
	uv run black $(PY_TARGETS)
	@echo "$(GREEN)✓ Formatting complete$(NC)"

format-check:
	@echo "$(BLUE)=== Checking Black Formatting ===$(NC)"
	uv run black --check $(PY_TARGETS)

# ============================================
# TYPE CHECKING
# ============================================

typecheck-python:
	@echo "$(BLUE)=== Running Mypy ===$(NC)"
	uv run mypy src/config src/mcp --ignore-missing-imports

typecheck-ts:
	@echo "$(BLUE)=== Running TypeScript Type Check ===$(NC)"
	npm run dashboard:typecheck

typecheck: typecheck-python typecheck-ts
	@echo "$(GREEN)✓ All type checks passed$(NC)"

# ============================================
# UI VALIDATION
# ============================================

dashboard-build:
	@echo "$(BLUE)=== Building Dashboard ===$(NC)"
	npm run dashboard:build:safe

validate-tab-registry:
	@echo "$(BLUE)=== Validating Tab Registry ===$(NC)"
	npm --workspace dashboard run build:scripts
	npm --workspace dashboard exec -- node scripts/dist/validate-tab-registry.mjs

ui-checks: dashboard-build validate-tab-registry
	@echo "$(GREEN)✓ UI checks passed$(NC)"

# ============================================
# AUDITS
# ============================================

audit-paths:
	@echo "$(BLUE)=== Auditing Hardcoded Paths ===$(NC)"
	uv run python .github/scripts/audit_paths.py .

audit-boundaries:
	@echo "$(BLUE)=== Validating Entity Boundaries ===$(NC)"
	uv run python .github/scripts/validate_boundaries.py

audit-logging:
	@echo "$(BLUE)=== Auditing Logging Usage ===$(NC)"
	uv run python .github/scripts/audit_logging.py

audit-data:
	@echo "$(BLUE)=== Auditing Data Separation ===$(NC)"
	uv run python .github/scripts/audit_data_separation.py

audit-structure:
	@echo "$(BLUE)=== Validating Repository Structure ===$(NC)"
	uv run python .github/scripts/validate_structure.py

audit: audit-paths audit-boundaries audit-logging audit-data audit-structure
	@echo "$(GREEN)✓ All audits passed$(NC)"

# ============================================
# TESTING
# ============================================

test-python:
	@echo "$(BLUE)=== Running Python Tests ===$(NC)"
	uv run pytest tests/ -v --ignore=tests/integration/

test-integration:
	@echo "$(BLUE)=== Running Integration Tests ===$(NC)"
	uv run pytest tests/integration/ -v

test-dashboard:
	@echo "$(BLUE)=== Running Dashboard Tests ===$(NC)"
	npm --workspace dashboard run test -- --passWithNoTests

test-mcp:
	@echo "$(BLUE)=== Running MCP Tests ===$(NC)"
	uv run pytest tests/mcp/ -v

test-skills:
	@echo "$(BLUE)=== Running Skill Tests ===$(NC)"
	@echo "$(YELLOW)Note: Skill tests now run from augur-data repo$(NC)"
	@echo "$(GREEN)✓ No local skill tests to run (plugins migrated to data repo)$(NC)"

test: test-python test-integration test-mcp test-skills test-dashboard
	@echo "$(GREEN)✓ All tests passed$(NC)"

coverage:
	@echo "$(BLUE)=== Running Tests with Coverage ===$(NC)"
	uv run pytest tests/ --cov=src/lib --cov-report=term-missing --cov-fail-under=70
	npm --workspace dashboard run test -- --coverage --passWithNoTests
	@echo "$(GREEN)✓ Coverage report generated$(NC)"

# ============================================
# SECURITY
# ============================================

security:
	@echo "$(BLUE)=== Running Security Scans ===$(NC)"
	@echo ""
	@echo "$(YELLOW)Python Dependencies:$(NC)"
	uv run pip-audit
	@echo ""
	@echo "$(YELLOW)npm Dependencies:$(NC)"
	npm --workspace dashboard audit --audit-level=high
	@echo ""
	@echo "$(YELLOW)Python Code Security (Bandit):$(NC)"
	uv run bandit -r plugins/ src/ plugins/ --exclude ".venv,node_modules,tests,_dev" -ll
	@echo ""
	@echo "$(GREEN)✓ Security scan complete$(NC)"

# ============================================
# WORKFLOWS
# ============================================

quality: lint format-check typecheck audit ui-checks
	@echo ""
	@echo "$(GREEN)════════════════════════════════════$(NC)"
	@echo "$(GREEN)✓ All quality checks passed!$(NC)"
	@echo "$(GREEN)════════════════════════════════════$(NC)"

pre-merge: quality test
	@echo ""
	@echo "$(GREEN)════════════════════════════════════$(NC)"
	@echo "$(GREEN)✓ Pre-merge validation complete!$(NC)"
	@echo "$(GREEN)  Ready to create PR$(NC)"
	@echo "$(GREEN)════════════════════════════════════$(NC)"

post-merge: test coverage
	@echo ""
	@echo "$(GREEN)════════════════════════════════════$(NC)"
	@echo "$(GREEN)✓ Post-merge validation complete!$(NC)"
	@echo "$(GREEN)════════════════════════════════════$(NC)"

# ============================================
# CLEANUP
# ============================================

clean:
	@echo "$(BLUE)=== Cleaning Generated Files ===$(NC)"
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf .ruff_cache
	rm -rf coverage/
	rm -rf htmlcov/
	rm -rf .coverage
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf apps/dashboard/.next apps/dashboard/coverage/ 2>/dev/null || true
	@echo "$(GREEN)✓ Cleanup complete$(NC)"
