---
description: Manage the local Ollama backend, installed models, and launch configuration.
visibility: core
---

# /local

Manage the local Ollama backend for running Augur with local models.

## Usage

```bash
/local
/local launch
/local status
/local pull <model>
/local config
/local models
```

## What It Covers

- inspect local backend readiness
- launch the configured local agent
- pull and select models
- review and update local backend preferences
- hand off per-action routing changes to `/local config`

## Notes

- use `get-local-backend-status` for readiness and installed models
- use preferences tools for backend configuration
- use [local-config.md](local-config.md) for per-action routing overrides

