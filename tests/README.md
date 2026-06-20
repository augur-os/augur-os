# Tests

All core tests for the Augur project are unified under this directory.

## Structure

```
tests/
├── src/              # Framework tests
│   ├── boundary/        # Boundary validation tests
│   ├── cli/             # CLI tests
│   ├── dashboard/       # Next.js dashboard tests (Jest)
│   ├── e2e/             # End-to-end tests
│   ├── fixtures/        # Shared test fixtures
│   ├── integration/     # Integration tests
│   ├── llm/             # LLM module tests
│   ├── mcp/             # MCP server tests
│   └── unit/            # Unit tests
├── plugins/            # Package tests
│   └── augur-mcp/       # MCP package tests
└── README.md
```

## Skill Tests

Skill tests stay with their skills for self-containment:

```
skills/{skill}/augur/tests/
```

## Running Tests

```bash
# Run all Python tests
pytest

# Run core framework tests only
pytest tests/src/

# Run specific category
pytest tests/src/unit/
pytest tests/src/integration/
pytest tests/src/mcp/
pytest tests/src/llm/

# Run dashboard tests (Jest)
cd apps/dashboard && npm test

# Run skill tests
pytest skills/apple/augur/tests/
```

## Test Guidelines

1. **Core framework tests** → `tests/src/`
2. **Package tests** → `tests/plugins/{package}/`
3. **Skill tests** → stay with skills in `skills/{skill}/augur/tests/`
4. Use fixtures from `tests/src/fixtures/`
5. Follow naming convention: `test_*.py` (Python), `*.test.tsx` (Jest)
