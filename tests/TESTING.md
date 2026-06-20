# Bossanova Studio Testing Framework

This framework provides 3 layers of testing for the Bossanova Automation Studio.

## Structure

```
src/tests/
├── unit/
│   └── test_bossanova_core.py       # Tests Data Manager logic (Filesystem mocked via tempdir)
├── integration/
│   └── test_bossanova_cli.py        # Tests CLI wrapper script (JSON contracts, Exit codes)
└── e2e/
    └── test_bossanova_e2e.py        # Simulates full API lifecycle (Create -> Run -> History)
```

## Running Tests

Run all tests:
```bash
python3 -m unittest discover src/tests
```

Run specific layer:
```bash
python3 -m unittest src/lib.tests.unit.test_bossanova_core
python3 -m unittest src/lib.tests.integration.test_bossanova_cli
python3 -m unittest src/lib.tests.e2e.test_bossanova_e2e
```

## Critical Items Covered

1.  **JSON Contract Integrity**: Ensures CLI tools return valid JSON for the Node.js backend to consume. catches stdout pollution (e.g. `print()`).
2.  **Data Persistence**: Verifies that History logs and Automation specs are saved and retrieved correctly.
3.  **Dry Run Propagation**: Verifies that the `dryRun` flag is passed from API -> CLI -> Script -> Terminal.
4.  **Error Handling**: Ensures that runtime errors (e.g. missing scenario files) return structred JSON errors, not crash dumps.
5.  **Environment Isolation**: Tests run in temporary directories, preventing pollution of the real Data Repo.

## Adding New Tests

*   **Unit**: Add methods to `TestBossanovaDataManager`. Use `self.manager` (automatically patched to temp dir).
*   **Integration**: Add commands to `TestBossanovaCLI.run_cli`.
*   **E2E**: Extend `TestBossanovaE2E` to test complex scenarios. Add scenarios under the Bossanova plugin scripts folder.
