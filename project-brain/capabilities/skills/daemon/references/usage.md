## Usage

```bash
# Start unified daemon (manages all services)
python3 unified_daemon.py start

# Check status
python3 unified_daemon.py status

# Stop daemon
python3 unified_daemon.py stop

# Individual monitors (for debugging)
python3 dashboard_monitor.py --check
python3 mcp_health_monitor.py --check
python3 runtime_marker_scanner.py --summary

# AI Self-Healer
python3 ai_self_healer.py --scan      # One-shot scan + classify + act
python3 ai_self_healer.py --status    # Show issue registry stats
python3 ai_self_healer.py --loop      # Continuous mode (used by daemon)
```
