# Page Migration Tier 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Safely migrate the 5 simplest custom TSX pages to YAML configs, verifying each one works in the browser before moving to the next.

**Architecture:** For each page: verify MCP tools return data, write YAML config, rebuild, browser-verify, delete TSX, commit. Tool verification script runs first to diagnose all tools at once.

**Tech Stack:** Python (tool verification), YAML (page configs), bash (build/verify commands)

**Spec:** `docs/superpowers/specs/2026-03-30-page-migration-runbook.md`

**Critical rules:**
- NEVER create a YAML with an MCP tool name you haven't verified returns data
- NEVER delete a TSX page before confirming the YAML replacement renders in the browser
- If a tool doesn't exist, implement it BEFORE writing the YAML
- One page per commit

---

### Task 1: Build tool verification script

**Files:**
- Create: `scripts/verify-page-tools.py`

- [ ] **Step 1: Create the verification script**

```python
#!/usr/bin/env python3
"""Verify MCP tools referenced by dashboard TSX pages.

Scans skills/dashboard/pages/ for useMcpQuery/useMcpMutation tool names,
calls each via the MCP server, and reports which exist and return data.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def extract_tools_from_tsx(file_path: Path) -> list[str]:
    """Extract MCP tool names from useMcpQuery/useMcpMutation calls."""
    content = file_path.read_text()
    tools = []

    # Pattern: useMcpQuery<T>(key, 'tool-name', preset, ...)
    # The tool name is the 2nd string argument
    for match in re.finditer(
        r'useMcpQuery[^(]*\([^,]+,\s*\n?\s*"\'["\']',
        content,
    ):
        tools.append(match.group(1))

    # Pattern: useMcpMutation<T, U>('tool-name', ...)
    for match in re.finditer(
        r'useMcpMutation[^(]*\(\s*\n?\s*"\'["\']',
        content,
    ):
        tools.append(match.group(1))

    # Pattern: useMcpPoll<T>('tool-name', ...)
    for match in re.finditer(
        r'useMcpPoll[^(]*\(\s*\n?\s*"\'["\']',
        content,
    ):
        tools.append(match.group(1))

    return sorted(set(tools))


def call_mcp_tool(tool_name: str, args: dict | None = None) -> dict:
    """Call an MCP tool and return verification result."""
    try:
        result = subprocess.run(
            [
                str(PROJECT_ROOT / ".venv" / "bin" / "python"),
                "-m", "augur_mcp",
                "--call-tool", tool_name,
                "--args", json.dumps(args or {}),
            ],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=str(PROJECT_ROOT),
        )
        if result.returncode != 0:
            return {"exists": False, "error": result.stderr.strip()[:200]}

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"exists": True, "returns_data": False, "raw": result.stdout[:200]}

        if isinstance(data, dict):
            return {
                "exists": True,
                "returns_data": bool(data),
                "shape": "object",
                "fields": list(data.keys())[:10],
            }
        elif isinstance(data, list):
            return {
                "exists": True,
                "returns_data": len(data) > 0,
                "shape": "array",
                "length": len(data),
                "sample_fields": list(data[0].keys())[:10] if data and isinstance(data[0], dict) else [],
            }
        else:
            return {"exists": True, "returns_data": True, "shape": type(data).__name__}

    except subprocess.TimeoutExpired:
        return {"exists": True, "returns_data": False, "error": "timeout"}
    except Exception as e:
        return {"exists": False, "error": str(e)[:200]}


def main():
    pages_dir = PROJECT_ROOT / "skills" / "dashboard" / "pages"
    results: dict[str, dict] = {}
    page_tools: dict[str, list[str]] = {}

    # Scan all TSX pages
    for page_tsx in sorted(pages_dir.rglob("page.tsx")):
        rel = str(page_tsx.relative_to(pages_dir)).replace("/page.tsx", "")
        if "[" in rel:
            continue  # Skip dynamic routes
        tools = extract_tools_from_tsx(page_tsx)
        if tools:
            page_tools[rel] = tools

    # Collect unique tools
    all_tools = sorted(set(t for tools in page_tools.values() for t in tools))

    print(f"Found {len(page_tools)} pages with {len(all_tools)} unique MCP tools\n")

    # Verify each tool
    for tool in all_tools:
        pages_using = [p for p, ts in page_tools.items() if tool in ts]
        print(f"  Verifying: {tool} (used by {len(pages_using)} pages)...", end=" ", flush=True)
        result = call_mcp_tool(tool)
        result["pages"] = pages_using
        results[tool] = result
        status = "OK" if result.get("returns_data") else ("EXISTS" if result.get("exists") else "MISSING")
        print(status)

    # Summary
    ok = sum(1 for r in results.values() if r.get("returns_data"))
    exists = sum(1 for r in results.values() if r.get("exists") and not r.get("returns_data"))
    missing = sum(1 for r in results.values() if not r.get("exists"))

    print(f"\nResults: {ok} OK, {exists} exist but no data, {missing} missing")

    # Write manifest
    output_path = PROJECT_ROOT / "docs" / "generated" / "tool-verification.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, indent=2))
    print(f"Written to {output_path}")

    # Print pages grouped by readiness
    print("\n=== Page Readiness ===")
    for page, tools in sorted(page_tools.items()):
        all_ok = all(results.get(t, {}).get("returns_data") for t in tools)
        any_missing = any(not results.get(t, {}).get("exists") for t in tools)
        if all_ok:
            print(f"  READY:   {page}")
        elif any_missing:
            missing_tools = [t for t in tools if not results.get(t, {}).get("exists")]
            print(f"  BLOCKED: {page} (missing: {', '.join(missing_tools)})")
        else:
            no_data = [t for t in tools if not results.get(t, {}).get("returns_data")]
            print(f"  NO DATA: {page} (empty: {', '.join(no_data)})")

    return 0 if missing == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run the verification script**

```bash
cd ~/Projects/Augur
python3 scripts/verify-page-tools.py
```

Expected: A list of tools with OK/EXISTS/MISSING status, and pages grouped by readiness.

- [ ] **Step 3: Commit**

```bash
git add scripts/verify-page-tools.py docs/generated/tool-verification.json
git commit -m "feat: add MCP tool verification script for page migration"
```

---

### Task 2: Fix any missing/broken tools found by verification

**Files:** Depends on verification results — MCP tool implementations in `src/mcp/augur_mcp/`

- [ ] **Step 1: Review verification output**

Read `docs/generated/tool-verification.json`. For each tool marked as MISSING or no data:
- Check if the tool exists under a different name
- If truly missing, implement it in the MCP server
- If it exists but returns no data, check the data source

- [ ] **Step 2: Fix each broken tool**

For each tool that needs fixing, locate the registration in `src/mcp/augur_mcp/` and fix it. Re-run the verification script after each fix.

- [ ] **Step 3: Re-run verification until all Tier 1 page tools pass**

```bash
python3 scripts/verify-page-tools.py
```

The 5 Tier 1 pages need these tools to return data:
- `list-skill-actions` (career/growth)
- `get-skill-doc` (career/growth)
- `skill-score` (adaptive/auto-skill-quality/skill-scores)
- `apple-list-voice-memos` (life/apple/voice)
- `updater-plugins` (command/updater/plugins)
- `skill-action` (command/updater/plugins)
- `health-summary` (life/health)
- `health-symptoms` (life/health)
- `health-medications` (life/health)
- `health-history` (life/health)

- [ ] **Step 4: Commit fixes**

```bash
git add -A
git commit -m "fix(mcp): ensure Tier 1 page tools return data"
```

---

### Task 3: Migrate career/growth (293L → YAML)

**Tools needed:** `list-skill-actions`, `get-skill-doc` (standard tools — should work)

- [ ] **Step 1: Read the TSX page to understand what it renders**

Read `skills/dashboard/pages/career/growth/page.tsx` completely. Note:
- What GlassCards it shows
- What data each card displays
- What the layout looks like

- [ ] **Step 2: Write the YAML config**

Create `skills/growth/augur/pages/overview.yaml`:

**IMPORTANT:** Only use tool names confirmed by the verification script. The tools for this page are `list-skill-actions` and `get-skill-doc` — both standard tools. This page renders skill actions and documentation.

Since this page only uses the standard 3 tools (health + actions + doc), it's actually handled by `buildDefaultPageConfig()` via Browse. So just delete the TSX — no YAML needed.

But FIRST verify it works via Browse: navigate to `/browse/growth` and confirm data renders.

- [ ] **Step 3: Rebuild**

```bash
cd ~/Projects/Augur/apps/dashboard
node scripts/dist/mount-plugins.mjs 2>&1 | grep -E "Tab registry|orphan"
```

Expected: 0 orphans

- [ ] **Step 4: Browser verify**

Navigate to the growth page in Chrome. Confirm:
- Page renders (no blank/error)
- Data loads (actions list shows, doc content shows)
- No 500 errors

If it doesn't work, DO NOT delete the TSX. Debug the issue first.

- [ ] **Step 5: Delete TSX (only after browser confirmation)**

```bash
rm skills/dashboard/pages/career/growth/page.tsx
# Rebuild to remove from registry
node scripts/dist/mount-plugins.mjs 2>&1 | grep "Tab registry"
```

- [ ] **Step 6: Commit**

```bash
git add -u skills/dashboard/pages/career/growth/
git commit -m "feat(pages): migrate career/growth — standard tools, handled by buildDefaultPageConfig"
```

---

### Task 4: Migrate adaptive/auto-skill-quality/skill-scores (113L → YAML)

**Tools needed:** `skill-score`

- [ ] **Step 1: Read the TSX page**

Read `skills/dashboard/pages/adaptive/auto-skill-quality/skill-scores/page.tsx` and `SkillGateVisualizer.tsx`. Note what data it displays and how.

- [ ] **Step 2: Verify the tool returns data**

```bash
python3 -c "
import subprocess, json
r = subprocess.run(['.venv/bin/python', '-m', 'augur_mcp', '--call-tool', 'skill-score', '--args', '{}'], capture_output=True, text=True, cwd='.')
print(r.stdout[:500] if r.returncode == 0 else f'ERROR: {r.stderr[:200]}')
"
```

If the tool doesn't exist or returns no data, implement/fix it before proceeding.

- [ ] **Step 3: Write the YAML config**

Create `skills/auto-skill-quality/augur/pages/skill-scores.yaml` with the VERIFIED tool name:

```yaml
title: Skill Scores
icon: BarChart3
hub: adaptive
route: auto-skill-quality/skill-scores
order: 50
blocks:
  - type: metrics-dashboard
    size: full
    sources:
      - mcp_tool: skill-score
        title: Skill Quality Scores
        icon: BarChart3
        color: purple
```

**NOTE:** Only write this YAML if `skill-score` tool returned data in Step 2. If it didn't, fix the tool first.

- [ ] **Step 4: Rebuild and verify**

```bash
cd ~/Projects/Augur/apps/dashboard
node scripts/dist/mount-plugins.mjs 2>&1 | grep -E "Tab registry|orphan"
printf '{}' > tsconfig.tsbuildinfo && rm -f .next/lock && npx next build 2>&1 | grep -E "Compiled|Type error|Failed"
```

- [ ] **Step 5: Browser verify**

Navigate to `/adaptive/auto-skill-quality/skill-scores` in Chrome. Confirm:
- Page renders with real data (not "No data")
- Skill scores display correctly
- No 500 errors

If broken, revert YAML and keep TSX.

- [ ] **Step 6: Delete TSX (only after browser confirmation)**

```bash
rm skills/dashboard/pages/adaptive/auto-skill-quality/skill-scores/page.tsx
rm skills/dashboard/pages/adaptive/auto-skill-quality/skill-scores/SkillGateVisualizer.tsx
rmdir skills/dashboard/pages/adaptive/auto-skill-quality/skill-scores
rmdir skills/dashboard/pages/adaptive/auto-skill-quality
node scripts/dist/mount-plugins.mjs 2>&1 | grep "Tab registry"
```

- [ ] **Step 7: Commit**

```bash
git add skills/auto-skill-quality/augur/pages/ && git add -u skills/dashboard/pages/adaptive/
git commit -m "feat(pages): migrate adaptive/auto-skill-quality/skill-scores to YAML"
```

---

### Task 5: Migrate life/health (206L → YAML)

**Tools needed:** `health-summary`, `health-symptoms`, `health-medications`, `health-history`

- [ ] **Step 1: Read the TSX page**

Read `skills/dashboard/pages/life/health/page.tsx`. Note what each MCP query displays.

- [ ] **Step 2: Verify ALL 4 tools return data**

```bash
for tool in health-summary health-symptoms health-medications health-history; do
  echo -n "$tool: "
  python3 -c "
import subprocess, json
r = subprocess.run(['.venv/bin/python', '-m', 'augur_mcp', '--call-tool', '$tool', '--args', '{}'], capture_output=True, text=True, cwd='.')
if r.returncode == 0:
    try:
        d = json.loads(r.stdout)
        print('OK -', type(d).__name__, '- fields:', list(d.keys())[:5] if isinstance(d, dict) else f'{len(d)} items')
    except: print('OK - raw output')
else: print('MISSING -', r.stderr[:100])
"
done
```

If ANY tool is missing, implement it before proceeding. Do NOT write YAML with unverified tools.

- [ ] **Step 3: Write the YAML config**

Create `skills/health/augur/pages/overview.yaml` with ONLY the verified tool names:

```yaml
title: Health
icon: Heart
hub: life
route: health
order: 40
blocks:
  - type: metrics-dashboard
    size: full
    sources:
      - mcp_tool: health-summary
        title: Health Summary
        icon: Heart
        color: emerald
      - mcp_tool: health-symptoms
        title: Symptoms
        icon: Thermometer
        color: amber
      - mcp_tool: health-medications
        title: Medications
        icon: Pill
        color: blue
      - mcp_tool: health-history
        title: History
        icon: Calendar
        color: purple
```

- [ ] **Step 4: Rebuild and verify build passes**

```bash
cd ~/Projects/Augur/apps/dashboard
node scripts/dist/mount-plugins.mjs 2>&1 | grep -E "Tab registry|orphan"
printf '{}' > tsconfig.tsbuildinfo && rm -f .next/lock && npx next build 2>&1 | grep -E "Compiled|Failed"
```

- [ ] **Step 5: Browser verify**

Navigate to `/life/health` in Chrome. Confirm:
- All 4 cards render with real data
- Health summary shows metrics
- Symptoms, medications, history cards have content
- No 500 errors, no "No data" placeholders

If broken, revert YAML and keep TSX. Debug first.

- [ ] **Step 6: Delete TSX (only after browser confirmation)**

```bash
rm -rf skills/dashboard/pages/life/health/
node scripts/dist/mount-plugins.mjs 2>&1 | grep "Tab registry"
```

- [ ] **Step 7: Commit**

```bash
git add skills/health/augur/pages/ && git add -u skills/dashboard/pages/life/health/
git commit -m "feat(pages): migrate life/health to YAML metrics-dashboard"
```

---

### Task 6: Migrate command/updater/plugins (178L → YAML)

**Tools needed:** `updater-plugins`, `skill-action`

- [ ] **Step 1: Read the TSX page**

Read `skills/dashboard/pages/command/updater/plugins/page.tsx`. Note:
- Displays a list of plugins with status badges
- Has an archive section with restore functionality

- [ ] **Step 2: Verify tools**

```bash
for tool in updater-plugins skill-action; do
  echo -n "$tool: "
  python3 -c "
import subprocess, json
args = '{}' if '$tool' != 'skill-action' else '{\"skill\": \"plugin-lifecycle\", \"action\": \"list-archive\"}'
r = subprocess.run(['.venv/bin/python', '-m', 'augur_mcp', '--call-tool', '$tool', '--args', args], capture_output=True, text=True, cwd='.')
if r.returncode == 0: print('OK')
else: print('MISSING -', r.stderr[:100])
"
done
```

- [ ] **Step 3: Write the YAML config**

Create `skills/updater/augur/pages/plugins.yaml`:

```yaml
title: Plugins
icon: Package
hub: command
route: updater/plugins
order: 50
blocks:
  - type: card-grid
    mcp_tool: updater-plugins
    title: Installed Plugins
    size: full
    search:
      enabled: true
```

- [ ] **Step 4: Rebuild and verify build**

```bash
cd ~/Projects/Augur/apps/dashboard
node scripts/dist/mount-plugins.mjs 2>&1 | grep -E "Tab registry|orphan"
printf '{}' > tsconfig.tsbuildinfo && rm -f .next/lock && npx next build 2>&1 | grep -E "Compiled|Failed"
```

- [ ] **Step 5: Browser verify**

Navigate to `/command/updater/plugins` in Chrome. Confirm plugins list renders with real data.

- [ ] **Step 6: Delete TSX (only after browser confirmation)**

```bash
rm skills/dashboard/pages/command/updater/plugins/page.tsx
node scripts/dist/mount-plugins.mjs 2>&1 | grep "Tab registry"
```

- [ ] **Step 7: Commit**

```bash
git add skills/updater/augur/pages/ && git add -u skills/dashboard/pages/command/updater/
git commit -m "feat(pages): migrate command/updater/plugins to YAML card-grid"
```

---

### Task 7: Migrate life/apple/voice (148L → YAML or keep)

**Tools needed:** `apple-list-voice-memos`

- [ ] **Step 1: Read the TSX page**

Read `skills/dashboard/pages/life/apple/voice/page.tsx`. Note:
- This page imports custom components: VoiceRecorderPanel, VoiceRecordingsTabs, VoiceImportsPanel, VoiceFoldersPanel, VoiceSearchPanel
- These are interactive components with recording capability
- This is NOT a simple data display — it has a recorder, search, folders, import

- [ ] **Step 2: Assess convertibility**

This page has custom interactive components (voice recorder, file import). These CANNOT be expressed as YAML blocks. This page should STAY as custom TSX.

- [ ] **Step 3: Document decision**

This page stays as TSX because:
- VoiceRecorderPanel: interactive audio recording (no block equivalent)
- VoiceImportsPanel: file import (no block equivalent)
- VoiceFoldersPanel/VoiceSearchPanel: custom filtering with URL search params

No changes needed. Move to next page.

- [ ] **Step 4: Commit documentation**

No code changes for this task. The page stays as-is.

---

### Task 8: Final verification

- [ ] **Step 1: Run full build**

```bash
cd ~/Projects/Augur/apps/dashboard
pnpm run build:scripts
node scripts/dist/mount-plugins.mjs 2>&1 | grep -E "Tab registry|orphan"
printf '{}' > tsconfig.tsbuildinfo && rm -f .next/lock && npx next build 2>&1 | grep -E "Compiled|Failed"
```

Expected: Build passes, 0 orphans.

- [ ] **Step 2: Count pages**

```bash
echo "YAML: $(find skills/*/augur/pages -name '*.yaml' | wc -l)"
echo "TSX:  $(find skills/dashboard/pages -name 'page.tsx' | wc -l)"
```

Expected: YAML increased by 2-3, TSX decreased by 2-3 (some pages stay as TSX).

- [ ] **Step 3: Browser spot-check all migrated pages**

Navigate to each migrated page in Chrome and confirm it works:
- `/career/growth` (or via Browse)
- `/adaptive/auto-skill-quality/skill-scores`
- `/life/health`
- `/command/updater/plugins`

All must render real data with no errors.

- [ ] **Step 4: Run auto-detect tests**

```bash
cd ~/Projects/Augur/apps/dashboard
npx jest lib/blocks/__tests__/auto-detect.test.ts --no-coverage
```

Expected: All tests pass.
