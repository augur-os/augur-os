---
status: Implemented
date: '2026-02-14'
deciders: []
related:
- ADR-101 (Worktree Isolation)
hub: null
tags:
- worktree
- validation
- plan
superseded_by: null
---

# ADR-117: Worktree Validation Plan

## Overview

This validation plan verifies that ADR-101 worktree isolation works correctly across all components:
- Port allocation via registry
- Daemon worktree detection
- MCP config generation for all IDEs
- Instance lock isolation
- Path sanitization
- Concurrent worktree support

---

## Test Matrix

| Test | Component | Expected Result |
|------|-----------|-----------------|
| V1 | Worktree Registry | Ports allocated dynamically (3001-3010) |
| V2 | Daemon Detection | Skips monitoring in worktree context |
| V3 | MCP Generation | Configs created for all IDEs |
| V4 | Instance Lock | Port-specific PID files don't conflict |
| V5 | Path Sanitization | Worktree paths replaced with main repo |
| V6 | Concurrency | Multiple worktrees can run simultaneously |

---

## V1: Worktree Registry Port Allocation

### Test 1.1: Register Worktree

```bash
# Create test worktree
git worktree add /tmp/augur-test-wt1 -b test-wt1

# Register and allocate port
python scripts/worktree_registry.py register --path /tmp/augur-test-wt1 --name test-wt1
```

**Expected output:**
```json
{
  "name": "test-wt1",
  "dashboard_port": 3001,
  "mcp_port": 8081,
  "branch": "test-wt1",
  "status": "active"
}
```

### Test 1.2: Register Second Worktree

```bash
git worktree add /tmp/augur-test-wt2 -b test-wt2
python scripts/worktree_registry.py register --path /tmp/augur-test-wt2 --name test-wt2
```

**Expected output:**
```json
{
  "name": "test-wt2",
  "dashboard_port": 3002,
  "mcp_port": 8082,
  ...
}
```

### Test 1.3: List Worktrees

```bash
python scripts/worktree_registry.py list
```

**Expected:** Array with both worktrees, different ports.

### Test 1.4: Unregister Worktree

```bash
python scripts/worktree_registry.py unregister --path /tmp/augur-test-wt1
python scripts/worktree_registry.py list
```

**Expected:** Only test-wt2 remains, port 3001 freed.

### Test 1.5: Port Reallocation

```bash
git worktree add /tmp/augur-test-wt3 -b test-wt3
python scripts/worktree_registry.py register --path /tmp/augur-test-wt3 --name test-wt3
```

**Expected:** Gets port 3001 (reused from freed slot).

### Cleanup

```bash
python scripts/worktree_registry.py unregister --path /tmp/augur-test-wt2
python scripts/worktree_registry.py unregister --path /tmp/augur-test-wt3
git worktree remove /tmp/augur-test-wt1 2>/dev/null || rm -rf /tmp/augur-test-wt1
git worktree remove /tmp/augur-test-wt2 2>/dev/null || rm -rf /tmp/augur-test-wt2
git worktree remove /tmp/augur-test-wt3 2>/dev/null || rm -rf /tmp/augur-test-wt3
git branch -D test-wt1 test-wt2 test-wt3 2>/dev/null
```

---

## V2: Daemon Worktree Detection

### Test 2.1: Detect Main Repo Context

```bash
cd ~/Projects/Augur
python3 -c "
import sys
sys.path.insert(0, 'plugins/observability/skills/daemon/scripts')
from daemon_mode import is_worktree_context, get_daemon_behavior

print('is_worktree_context():', is_worktree_context())
print('get_daemon_behavior():', get_daemon_behavior())
"
```

**Expected:**
```
is_worktree_context(): False
get_daemon_behavior(): {'monitor_dashboard': True, 'auto_restart': True, 'notify_only': False, 'skip_monitoring': False}
```
*(In production mode)*

### Test 2.2: Detect Worktree Context

```bash
# Create worktree
git worktree add /tmp/augur-test-daemon -b test-daemon
cd /tmp/augur-test-daemon

python3 -c "
import sys
sys.path.insert(0, '~/Projects/Augur/plugins/observability/skills/daemon/scripts')
from daemon_mode import is_worktree_context, get_daemon_behavior

print('is_worktree_context():', is_worktree_context())
print('get_daemon_behavior():', get_daemon_behavior())
"
```

**Expected:**
```
is_worktree_context(): True
get_daemon_behavior(): {'monitor_dashboard': False, 'auto_restart': False, 'notify_only': True, 'skip_monitoring': True}
```

### Cleanup

```bash
cd ~/Projects/Augur
git worktree remove /tmp/augur-test-daemon 2>/dev/null || rm -rf /tmp/augur-test-daemon
git branch -D test-daemon 2>/dev/null
```

---

## V3: MCP Config Generation for All IDEs

### Test 3.1: Generate for All IDEs

```bash
mkdir -p /tmp/augur-test-mcp
python scripts/generate-worktree-mcp.py \
  --path /tmp/augur-test-mcp \
  --name test-mcp \
  --dashboard-port 3005 \
  --mcp-port 8085 \
  --all
```

**Expected files created:**
```
/tmp/augur-test-mcp/.claude/mcp.json
/tmp/augur-test-mcp/.cursor/mcp.json
/tmp/augur-test-mcp/.windsurf/mcp.json
/tmp/augur-test-mcp/.gemini/settings.json
/tmp/augur-test-mcp/.opencode/mcp.json
/tmp/augur-test-mcp/.agent/mcp.json
```

### Test 3.2: Verify Config Content

```bash
cat /tmp/augur-test-mcp/.claude/mcp.json
```

**Expected:**
```json
{
  "mcpServers": {
    "augur": {
      "command": "python3",
      "args": ["-m", "augur_mcp", "--client-id", "worktree"],
      "cwd": "/tmp/augur-test-mcp",
      "env": {
        "AUGUR_ROOT": "/tmp/augur-test-mcp",
        "AUGUR_MODE": "dev",
        "MCP_PORT": "8085",
        ...
      }
    }
  }
}
```

### Test 3.3: Generate for Specific Client

```bash
python scripts/generate-worktree-mcp.py \
  --path /tmp/augur-test-mcp \
  --client cursor \
  --mcp-port 8086 \
  --stdout
```

**Expected:** JSON to stdout with MCP_PORT=8086.

### Cleanup

```bash
rm -rf /tmp/augur-test-mcp
```

---

## V4: Instance Lock Port Isolation

### Test 4.1: Port-Specific Lock File Names

```python
import sys
sys.path.insert(0, 'src/mcp')
from pathlib import Path
from augur_mcp.instance_lock import InstanceLock

# Global lock
lock1 = InstanceLock()
print("Global lock file:", lock1.lock_file.name)

# Client-specific lock  
lock2 = InstanceLock(client_id="claude")
print("Client lock file:", lock2.lock_file.name)

# Port-specific lock
lock3 = InstanceLock(port=8081)
print("Port lock file:", lock3.lock_file.name)

# Port from environment
import os
os.environ["MCP_PORT"] = "8082"
lock4 = InstanceLock()
print("Env port lock file:", lock4.lock_file.name)
```

**Expected:**
```
Global lock file: augur-mcp.pid
Client lock file: augur-mcp-claude.pid
Port lock file: augur-mcp-port8081.pid
Env port lock file: augur-mcp-port8082.pid
```

### Test 4.2: No Conflict Between Ports

```python
# Simulate two worktrees with different ports
lock1 = InstanceLock(port=8081)
lock2 = InstanceLock(port=8082)

# Both should be able to acquire
assert lock1.acquire() == True, "Lock 1 should acquire"
assert lock2.acquire() == True, "Lock 2 should acquire (different port)"

# Cleanup
lock1.release()
lock2.release()
print("✅ Port-specific locks don't conflict")
```

---

## V5: Path Sanitization

### Test 5.1: Dry Run

```bash
# Create test file with worktree path
mkdir -p /tmp/augur-test-sanitize
echo '{"cwd": "~/Projects/augur-adr-101"}' > /tmp/augur-test-sanitize/test.json
echo 'AUGUR_ROOT: ~/Projects/augur-harden-finance' > /tmp/augur-test-sanitize/test.yaml

# Dry run
bash scripts/sanitize-worktree-paths.sh --dry-run --files /tmp/augur-test-sanitize/test.json /tmp/augur-test-sanitize/test.yaml
```

**Expected:** Shows what would be changed (augur-adr-101 → Augur, etc.)

### Test 5.2: Actual Sanitization

```bash
bash scripts/sanitize-worktree-paths.sh --files /tmp/augur-test-sanitize/test.json /tmp/augur-test-sanitize/test.yaml

cat /tmp/augur-test-sanitize/test.json
cat /tmp/augur-test-sanitize/test.yaml
```

**Expected:**
```json
{"cwd": "~/Projects/Augur"}
```
```yaml
AUGUR_ROOT: ~/Projects/Augur
```

### Cleanup

```bash
rm -rf /tmp/augur-test-sanitize
```

---

## V6: Concurrent Worktrees

### Test 6.1: Create Multiple Worktrees

```bash
# Create 3 worktrees
for i in 1 2 3; do
  git worktree add /tmp/augur-concurrent-$i -b test-concurrent-$i
  python scripts/worktree_registry.py register --path /tmp/augur-concurrent-$i --name test-$i
done

# Verify different ports
python scripts/worktree_registry.py list | jq '.[].dashboard_port'
```

**Expected:** `[3001, 3002, 3003]` (different ports for each)

### Test 6.2: Generate MCP for Each

```bash
for i in 1 2 3; do
  python scripts/generate-worktree-mcp.py --path /tmp/augur-concurrent-$i --name test-$i --all
done

# Verify different MCP ports
for i in 1 2 3; do
  cat /tmp/augur-concurrent-$i/.claude/mcp.json | jq '.mcpServers.augur.env.MCP_PORT'
done
```

**Expected:** `["8081", "8082", "8083"]`

### Test 6.3: Verify No Port Conflicts

```bash
# Check instance locks don't conflict
python3 -c "
import sys
sys.path.insert(0, 'src/mcp')
from augur_mcp.instance_lock import InstanceLock

locks = [InstanceLock(port=8081+i) for i in range(3)]
for i, lock in enumerate(locks):
    acquired = lock.acquire(timeout=1)
    print(f'Lock {i+1} (port {8081+i}): acquired={acquired}')
    if acquired:
        lock.release()
"
```

**Expected:** All 3 locks acquire successfully.

### Cleanup

```bash
for i in 1 2 3; do
  python scripts/worktree_registry.py unregister --path /tmp/augur-concurrent-$i
  git worktree remove /tmp/augur-concurrent-$i 2>/dev/null || rm -rf /tmp/augur-concurrent-$i
  git branch -D test-concurrent-$i 2>/dev/null
done
```

---

## V7: End-to-End Workflow

### Full Workflow Simulation

```bash
# 1. Create worktree for ADR simulation
git worktree add /tmp/augur-adr-test -b adr-test-impl
cd /tmp/augur-adr-test

# 2. Register and get ports
PORT_INFO=$(python ~/Projects/Augur/scripts/worktree_registry.py register --path $(pwd) --name adr-test)
DASHBOARD_PORT=$(echo "$PORT_INFO" | jq -r '.dashboard_port')
MCP_PORT=$(echo "$PORT_INFO" | jq -r '.mcp_port')
echo "Allocated: dashboard=$DASHBOARD_PORT, mcp=$MCP_PORT"

# 3. Set port for dev server
echo "PORT=$DASHBOARD_PORT" > .env.local

# 4. Generate MCP configs for all IDEs
python ~/Projects/Augur/scripts/generate-worktree-mcp.py --path $(pwd) --name adr-test --all

# 5. Create worktree marker
cat > .augur-worktree.yaml << EOF
worktree: true
dashboard_port: $DASHBOARD_PORT
mcp_port: $MCP_PORT
main_repo: ~/Projects/Augur
name: adr-test
EOF

# 6. Verify daemon skips this worktree
python3 -c "
import sys
sys.path.insert(0, '~/Projects/Augur/plugins/observability/skills/daemon/scripts')
from daemon_mode import is_worktree_context, get_daemon_behavior
assert is_worktree_context() == True, 'Should detect worktree'
behavior = get_daemon_behavior()
assert behavior['skip_monitoring'] == True, 'Should skip monitoring'
print('✅ Daemon correctly skips worktree')
"

# 7. Verify MCP configs exist
ls -la .claude/mcp.json .cursor/mcp.json .windsurf/mcp.json

# 8. Cleanup simulation
cd ~/Projects/Augur
python scripts/worktree_registry.py unregister --path /tmp/augur-adr-test
git worktree remove /tmp/augur-adr-test 2>/dev/null || rm -rf /tmp/augur-adr-test
git branch -D adr-test-impl 2>/dev/null
```

**Expected:**
- Port allocated (e.g., 3001)
- .env.local created with PORT=3001
- MCP configs generated for all IDEs
- Daemon behavior shows skip_monitoring=True
- Cleanup frees the port

---

## Execution Checklist

Run each test section in order:

- [ ] **V1**: Worktree Registry Port Allocation
- [ ] **V2**: Daemon Worktree Detection  
- [ ] **V3**: MCP Config Generation for All IDEs
- [ ] **V4**: Instance Lock Port Isolation
- [ ] **V5**: Path Sanitization
- [ ] **V6**: Concurrent Worktrees
- [ ] **V7**: End-to-End Workflow

## Success Criteria

| Criteria | Threshold |
|----------|-----------|
| Port allocation | Unique ports 3001-3010 |
| Daemon detection | Correctly identifies worktree |
| MCP generation | All 6 IDE configs created |
| Lock isolation | No conflicts between ports |
| Sanitization | All worktree paths replaced |
| Concurrency | 3+ worktrees run simultaneously |
| E2E workflow | Complete workflow passes |

## Failure Recovery

If any test fails:

1. Check error output for specific failure
2. Verify file paths in error match expected locations
3. Run individual test in isolation to debug
4. Check `runtime/worktree_registry.yaml` for stale entries
5. Run cleanup commands before re-testing
