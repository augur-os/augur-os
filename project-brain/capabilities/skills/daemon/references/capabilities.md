## Capabilities

### Core Services
- **log_monitor.py** - Watches LLM logs for errors, generates P0/P1 bug reports
- **continuous_executor.py** - Executes background tasks from queue
- **nightly_maintainer.py** - Scheduled nightly maintenance tasks (3 AM)

### Production Monitoring (ADR-041)
- **dashboard_monitor.py** - Monitors Next.js dashboard, auto-restarts with recovery stages
- **mcp_health_monitor.py** - Detects stalled MCP PIDs, auto-cleanup in production
- **runtime_marker_scanner.py** - Scans logs for errors, generates TODO_ tech debt markers

### AI Self-Healing (ADR-076)
- **ai_self_healer.py** - Scans external Augur logs via ripgrep, classifies severity via LLM, auto-fixes critical/high issues using headless `/debug` protocol, creates TODO markers for medium/low issues

### Utilities
- **cleanup_processes.py** - Cross-platform process cleanup (port 3000, MCP PIDs)
- **mcp_health_check.py** - MCP configuration and runtime health validation
- **notification_service.py** - Cross-platform notifications (macOS, Windows, Slack)
- **service_healer.py** - LaunchAgent plist management and migration
- **daemon_mode.py** - Mode detection (production vs dev)
- **merge_tech_debt.py** - Merges runtime markers into codebase (for nightly workflow)
