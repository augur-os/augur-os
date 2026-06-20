---
description: "Browser-based UI QA validation of dashboard pages using Chrome MCP"
visibility: test
---

# /test-ui

Validate Augur dashboard pages in a real browser using Claude-in-Chrome MCP tools.

## Usage

```bash
/test-ui                  # Validate homepage + all hub landing pages
/test-ui /career          # Validate a specific page
/test-ui /ai/chatbot      # Validate a nested page
```

## Execution Steps

### 1. Ensure Dev Server Is Running

Check if the dashboard dev server is already running on port 3000:

```bash
lsof -i :3000 -sTCP:LISTEN
```

If not running, start it in the background:

```bash
cd $AUGUR_ROOT && npm run dev &
```

Wait for the server to be ready before proceeding (check `curl -s http://localhost:3000` returns 200).

### 2. Connect to Chrome

Call `tabs_context_mcp` to get the current browser context. If no tab group exists, create one with `createIfEmpty: true`. Then create a new tab with `tabs_create_mcp`.

### 3. Navigate and Validate

For each target page:

1. **Navigate**: Use `navigate` to go to `http://localhost:3000{path}`
2. **Wait**: Use `computer` with `action: wait, duration: 3` for page load
3. **Dismiss modals**: Check for and dismiss any blocking modals:
   - Look for elements matching "System Move Detected" or similar modal overlays
   - If found, click the dismiss/close button
4. **Screenshot**: Take a screenshot with `computer` action `screenshot`
5. **Console check**: Use `read_console_messages` with `onlyErrors: true` to capture JS errors
6. **Interactive check**: Use `read_page` with `filter: interactive` to verify navigation and controls rendered

### 4. Hub Landing Pages (Dynamic Discovery, when no specific page given)

When invoked as `/test-ui` with no arguments, do **not** use a hardcoded page list.

Discover target pages from mounted hub metadata:

1. Read `apps/dashboard/lib/plugin-runtime/assembled-hubs.json`
2. Extract `hubs[].id` (optionally sort by `nav_order`)
3. Build routes as `/{hubId}`
4. Prepend `/` as the homepage

Example discovery:

```bash
python3 - <<'PY'
import json
from pathlib import Path

p = Path("apps/dashboard/lib/plugin-runtime/assembled-hubs.json")
data = json.loads(p.read_text())
hubs = data.get("hubs", [])
hubs.sort(key=lambda h: h.get("nav_order", 9999))
pages = ["/"] + [f"/{h['id']}" for h in hubs if h.get("id")]
print("\n".join(pages))
PY
```

Fallback (if metadata file is missing/stale):

1. Open `/` and collect sidebar hub links dynamically
2. Validate only discovered hub routes
3. Do not add legacy, removed, or guessed routes manually

### 5. Report Results

Summarize as a table:

```
| Page | Status | Console Errors | Notes |
|------|--------|---------------|-------|
| /    | PASS   | 0             |       |
| /ai  | PASS   | 0             |       |
| /career | FAIL | 2           | TypeError: Cannot read property... |
```

## Pass/Fail Criteria

- **PASS**: Page loads (no 404/500), screenshot shows rendered content, zero console errors
- **WARN**: Page loads but has console warnings or minor rendering issues
- **FAIL**: Page returns error status, blank/white screen, or has console errors
