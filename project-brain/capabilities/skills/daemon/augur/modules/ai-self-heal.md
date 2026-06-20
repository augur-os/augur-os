# AI Self-Healing Module (ADR-076)

## Overview

The AI Self-Healer extends daemon monitoring from process-level recovery to
code-level fixes. It scans external Augur logs, classifies errors by severity, and
automatically applies fixes for critical/high issues.

## Pipeline

```
scan (ripgrep) → dedup (registry) → classify (LLM) → route → fix | TODO
```

### 1. Scan
- Uses ripgrep (`rg`) for fast log scanning (falls back to Python `re`)
- Targets: `~/Library/Logs/Augur/*.log`, `*.stderr.log`
- Patterns: ERROR, FATAL, CRITICAL, Traceback, Exception

### 2. Dedup (Issue Registry)
- Persistent at `~/Library/Application Support/Augur/state/self_heal_registry.json`
- Hash-based dedup key (normalized message + source file)
- Status tracking: new → classifying → fixing → fixed/failed/abandoned
- Regression detection: fixed issues that reappear within 1h
- Max retry limit (default: 2 attempts)

### 3. Classify
- Sends error context to configured LLM CLI
- Returns: severity (critical/high/medium/low), category, suggested approach
- Single-turn, fast call (~30s timeout)

### 4. Route + Act

| Severity | Action |
|----------|--------|
| critical | Headless `/debug` protocol via CLI |
| high | Headless `/debug` protocol via CLI |
| medium | Create `TODO_BUG` marker in `tech_debt.md` |
| low | Create `TODO_IMPROVE` marker in `tech_debt.md` |

### 5. Headless Fix
- Spawns CLI with constrained prompt
- Safety: max 3 files, 5min timeout, complexity abort at 7/10
- Auto-commits with `fix(self-heal):` prefix
- Fix lock prevents parallel attempts

## Configuration

File: `config/system/self_heal.yaml`

```yaml
enabled: true
scan_interval_minutes: 5
llm:
  cli: auto          # auto | claude | kimi | codex
  classify_timeout_s: 30
  fix_timeout_s: 300
fix:
  max_files_modified: 3
  max_fix_attempts: 2
routing:
  critical: fix
  high: fix
  medium: todo
  low: todo
```

## CLI Usage

```bash
python3 ai_self_healer.py --scan      # One-shot
python3 ai_self_healer.py --status    # Registry stats
python3 ai_self_healer.py --loop      # Daemon mode
```

## Notifications

Three-stage: detected → healing → resolved/failed. Uses `notification_service.py`.
