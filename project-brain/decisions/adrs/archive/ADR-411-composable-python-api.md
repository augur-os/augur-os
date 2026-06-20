---
status: Implemented
date: '2026-03-07'
deciders:
- Gur Sannikov
- Claude
related: []
hub: null
tags:
- composable
- python
- api
superseded_by: null
---

# ADR-411: Composable Python API

## Decision summary

### 1. Module Structure

## Status notes

 | Flipped to Implemented 2026-05-10 — code evidence: packages/create-augur/ scaffolder, pyproject.toml declares packages=["src"] with exclude=["apps/dashboard","src/scripts"], src/ has the proposed module structure (cli, mcp, plugins, lib, config, logging, scripts).
