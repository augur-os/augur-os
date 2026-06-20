---
title: feedback-chrome-mcp-multi-browser
name: feedback-chrome-mcp-multi-browser
description: User mirrors Augur across 2 laptops (Mac + Windows), each with its own
  Chrome+MCP extension paired to the same account; verify list_connected_browsers
  BEFORE acting and select_browser to the local one or you'll silently verify the
  wrong machine's localhost
brain_scope: personal
type: feedback
status: active
source_client: claude-code
source_file: feedback_chrome_mcp_multi_browser.md
source_hash: 661c2f3e3f36c106
_mentions:
- '[[feedback-cross-agent-enforcement]]'
_entity_tier: 3
---




The user runs Augur on **two** laptops in parallel — a Mac and a Windows HP — synced via git, each with its own local Chrome and Chrome MCP extension paired to the same MCP account. Both browsers can appear in `mcp__claude-in-chrome__list_connected_browsers` simultaneously. The most-recently-paired isn't necessarily the one MCP is talking to; MCP can stick with whichever one it was last bound to.

**Why:** burned on 2026-05-16 during ADR-759/760 verification. After successful earlier dashboard checks against the Mac browser, MCP silently re-targeted the Windows browser between calls. Every `read_page` and `get_page_text` against `http://localhost:3000/` failed with "Frame with ID 0 is showing error page". `curl` against the Mac's localhost returned HTTP 200 fine, `lsof -iTCP:3000` showed `next-server` healthy, server stdout logged clean 200s — all signals pointed at a working Mac dashboard. The actual cause: MCP was driving the **Windows** Chrome, where `http://localhost:3000/` resolved to nothing (no service listening on the Windows side), Chrome landed on `chrome-error://chromewebdata/` ("Hmmm… can't reach this page"), and MCP correctly but unhelpfully described that as "Frame is showing error page". The smoking gun was `navigator.userAgent` reporting `Windows NT 10.0; Win64; x64` from a session run on a Mac.

**How to apply:**
1. **Always call `mcp__claude-in-chrome__list_connected_browsers` FIRST** when starting browser verification in a new session, before any navigate/read_page. Don't assume the bound browser is the local one.
2. **Auto-pick — do NOT ask the user which browser.** When list returns multiple entries, `select_browser` to the local one matching this session: the entry with `isLocal: true` and `osPlatform` aligned with the session OS (Mac session → macOS entry, Windows session → Windows entry). User explicitly pushed back on 2026-05-18 against being asked to pick every time: "you are running locally, if you run now on mac it is mac, if I run from windows it is windows — I don't understand why you ask it every time". The chrome MCP tool description says to ask, but the user's standing instruction overrides that for the unambiguous case (exactly one `isLocal: true` entry matching the session OS). Only escalate via `AskUserQuestion` if there are zero local entries or multiple `isLocal: true` entries on the same OS. **Reinforced 2026-05-20:** user got frustrated again after I asked which browser ("why are you keep asking me this questions") and directed me to encode it in AGENTS.md. Now a durable cross-agent rule — `docs/agent-topics/agent-rules.md` rule 35 (regenerated into CLAUDE.md / AGENTS.md / .opencode/AGENTS.md). Follow it silently. See [[feedback-cross-agent-enforcement]].
3. If `read_page` returns "Frame is showing error page" and the server (`curl`, `lsof`, server stdout) shows healthy, do NOT spiral into "Turbopack workspace-root error" diagnosis. Probe `navigator.userAgent` and `location.href` via `javascript_tool` — if UA is Windows on a Mac session, or URL is `chrome-error://chromewebdata/`, you're on the wrong browser. Switch and retry.
4. The Mac browser pairing can be ephemeral after sleep/network changes. If verification used to work in-session and stops working, re-list and re-select before re-trying.
