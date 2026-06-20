# MCP Health Monitor

## Purpose
Monitor MCP server health, detect failures, and provide auto-restart capabilities. Goes beyond the basic health check by adding continuous monitoring and auto-fix for common issues.

## Monitoring Targets

| Component | Check | Threshold |
|-----------|-------|-----------|
| MCP servers | Process alive | Restart if dead > 30s |
| Tool registration | Tools responding | Alert if 0 tools |
| Startup time | Init duration | Warn if > 5s |
| Memory usage | RSS per server | Alert if > 500MB |
| Error rate | Errors / minute | Alert if > 5/min |

## Auto-Fix Capabilities

| Issue | Detection | Fix |
|-------|-----------|-----|
| **Dead MCP server** | Process not found | Restart with same config |
| **Stale tool registration** | Tool call returns "not found" | Re-register tools from SKILL.md |
| **Missing MCP config** | IDE config file missing augur entry | Generate config block |
| **Port conflict** | EADDRINUSE on startup | Find next available port |
| **Hung server** | No response for 60s | Kill and restart |

## Commands

| Command | Action |
|---------|--------|
| `/mcp health` | Check all MCP servers, report status |
| `/mcp restart [server]` | Restart specific MCP server |
| `/mcp fix` | Auto-fix common MCP issues |

## Integration
- Called by daemon health check commands
- Feeds status data to observe for uptime tracking
- Connected to daemon's task scheduler for periodic checks
- Results logged to `~/Library/Logs/Augur/mcp-health/`

## Health Report Format
```
MCP Health Report (2026-02-07 14:30)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ augur-mcp: running (pid 12345, 3.2s startup, 45MB RSS)
✅ context7: running (pid 12346, 1.1s startup, 23MB RSS)
⚠️  install-mcp: slow startup (7.2s > 5s threshold)
❌ scraper-mcp: not responding (last seen 2m ago)
   → Auto-fix: restarting...
   → ✅ scraper-mcp: restarted successfully

Summary: 3/4 healthy, 1 auto-fixed
```
