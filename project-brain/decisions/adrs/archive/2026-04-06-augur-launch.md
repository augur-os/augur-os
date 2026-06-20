# Augur Launch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Launch Augur as open source with refreshed website messaging, 1-command install, demo video, and launch content — targeting inbound leads from developers and AI practitioners.

**Architecture:** Plain HTML website (no framework) at `~/Projects/Au-docs/venture-augur/website-working/`. New `create-augur` npm package scaffolder. README and GitHub community polish. LinkedIn + HN launch content.

**Tech Stack:** HTML/CSS (website), Node.js (create-augur scaffolder), Markdown (README, launch posts), GitHub CLI (community setup)

**Spec:** `docs/superpowers/specs/2026-04-06-augur-launch-plan-design.md`

---

## Task Group 0: Dashboard UX Fixes (Week 1, Day 1 — FIRST PRIORITY)

These are critical for launch — a new user opening the dashboard must understand what to do within 10 seconds.

### Task 0A: Welcome Banner on Browse Page

**Files:**
- Modify: `~/Projects/Augur/apps/dashboard/app/browse/page.tsx` (or the browse page component)

- [ ] **Step 1: Read the current browse page component**

Read the browse page to understand the current layout and where to insert the banner.

- [ ] **Step 2: Create a dismissible welcome banner component**

Add a banner at the top of the browse page, above the category tabs. It should:
- Show on first visit (check localStorage `augur-welcome-dismissed`)
- Have a dismiss button (X) that sets the localStorage flag
- Content:

> **Welcome to Augur — your second brain, on your machine.**
>
> Start by exploring a skill below, or use the sidebar to browse hubs like Brain, Career, and Life. Everything here connects to your AI clients through MCP — Claude Code, Cursor, Gemini, and more.
>
> [Explore Skills] [Learn More →](https://augur.run/more.html)

- Use existing shadcn/ui components (Card or Alert) to match the design system
- Subtle background, not intrusive — should feel like a helpful hint, not a modal

- [ ] **Step 3: Test in browser**

Open localhost:3000. Confirm:
- Banner appears on first visit
- Dismiss button works
- Banner stays hidden on refresh after dismissal
- Layout doesn't jump when banner is dismissed

- [ ] **Step 4: Commit**

```bash
cd ~/Projects/Augur
git add apps/dashboard/
git commit -m "feat(dashboard): add dismissible welcome banner on browse page"
```

---

### Task 0B: Hub Tooltips in Sidebar

**Files:**
- Modify: The sidebar navigation component (find via grep for hub names or sidebar)

- [ ] **Step 1: Find the sidebar component**

Search for the component that renders hub links in the sidebar:
```bash
grep -rn "Brain\|Career\|Life\|Studio" apps/dashboard/ --include="*.tsx" -l
```

Identify the sidebar/nav component that renders the hub list.

- [ ] **Step 2: Read hub descriptions**

Hub descriptions come from SKILL.md frontmatter or the assembled-hubs.json. Read the hub data source to get descriptions for each hub.

- [ ] **Step 3: Add tooltips to hub sidebar items**

For each hub in the sidebar, add a tooltip (using shadcn/ui Tooltip component) that shows on hover:

| Hub | Tooltip |
|-----|---------|
| Brain | Knowledge, memory, search, and document management |
| Career | Job pipeline, interviews, resume, company research |
| Life | Finance, health, lifestyle, home automation |
| Studio | Content creation, social media, design |
| Adaptive | System automation, self-healing, quality scanning |
| Command | CLI utilities, workflows, orchestration |

Use the existing shadcn/ui `Tooltip`, `TooltipTrigger`, `TooltipContent` pattern already in the codebase.

- [ ] **Step 4: Test in browser**

Hover over each hub in the sidebar. Confirm tooltips appear with descriptions.

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/
git commit -m "feat(dashboard): add hub description tooltips to sidebar navigation"
```

---

### Task 0C: Hide Activity Page or Show Placeholder

**Files:**
- Modify: Sidebar navigation component or route config

- [ ] **Step 1: Check Activity page current state**

Read `~/Projects/Augur/apps/dashboard/app/activity/page.tsx` to confirm it shows "under construction".

- [ ] **Step 2: Hide from sidebar navigation**

Remove Activity from the sidebar nav items. The route can still exist (for future use) but shouldn't appear in navigation for new users.

If removing from nav is complex, alternatively: replace the "under construction" message with a meaningful placeholder:

> **Activity — Coming Soon**
>
> This page will show your recent interactions across all AI clients and skills.

- [ ] **Step 3: Test in browser**

Confirm Activity is either hidden from sidebar or shows a clean placeholder instead of "under construction".

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/
git commit -m "fix(dashboard): hide incomplete Activity page from navigation"
```

---

### Task 0D: Replace CLI Reindex Message with Button

**Files:**
- Modify: Browse page category component (where the "Run `/search reindex`" message appears)

- [ ] **Step 1: Find the reindex message**

```bash
grep -rn "reindex" apps/dashboard/ --include="*.tsx"
```

Locate the component that shows "Run `/search reindex category`" for unindexed categories.

- [ ] **Step 2: Replace CLI command with action button**

Replace the text message with a button that triggers the reindex via MCP:

```tsx
<Button
  variant="outline"
  onClick={() => mcpCall('knowledge-project-index-rebuild', { category })}
>
  Index this category
</Button>
```

Use the existing `useMcpMutation` hook pattern from the codebase. Keep the explanation text but replace the CLI command with the button.

- [ ] **Step 3: Test in browser**

Navigate to an unindexed category. Confirm: button appears instead of CLI command, clicking it triggers reindex, category loads after indexing.

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/
git commit -m "fix(dashboard): replace CLI reindex message with action button on browse page"
```

---

### Task 0E: Terminal Session Reconnect

**Files:**
- Modify: `~/Projects/Augur/apps/dashboard/app/api/cli/route.ts` (or wherever the PTY process registry and SSE stream live)
- Modify: The xterm/chat component that initiates connections

Currently, if the browser tab refreshes or the SSE connection drops, the PTY session is lost. Cabinet supports reconnecting to a running session.

- [ ] **Step 1: Read the current PTY lifecycle code**

Read the `/api/cli` route handler. Understand:
- How `PtyEntry` is stored in the global `Map<string, PtyEntry>`
- What happens when the SSE stream closes (does the PTY get killed?)
- How `cliId` is generated and tracked

- [ ] **Step 2: Keep PTY alive on SSE disconnect**

Currently the PTY likely dies when the SSE stream closes. Change this:
- On SSE disconnect, do NOT kill the PTY process
- Keep the PTY in the process registry with status `detached`
- Continue buffering output to `rawBuffer` and `outputBuffer` (up to 2000 line limit)
- Add an idle timeout (e.g., 5 minutes) — kill detached PTYs that haven't been reconnected

- [ ] **Step 3: Add reconnect action to /api/cli**

Add a `reconnect` action that:
1. Looks up existing `cliId` in the process registry
2. If found and still running: create a new SSE stream to it, replay buffered output since disconnect
3. If found but exited: return exit status and final output
4. If not found: return 404

```
GET /api/cli?cliId=xxx&action=reconnect&stream=true
```

- [ ] **Step 4: Update client to reconnect on mount**

In the chat/terminal component, on mount:
1. Check if there's a `cliId` in state (from before refresh)
2. If yes, attempt reconnect before starting a new session
3. If reconnect succeeds, resume displaying output
4. If reconnect fails (404), start fresh

- [ ] **Step 5: Test reconnect flow**

1. Start a Claude Code session in the chat
2. Refresh the browser tab
3. Confirm: session reconnects, buffered output replays, can continue typing

- [ ] **Step 6: Commit**

```bash
git add apps/dashboard/
git commit -m "feat(dashboard): add terminal session reconnect on page refresh"
```

---

### Task 0F: Terminal Session Detach

**Files:**
- Modify: `~/Projects/Augur/apps/dashboard/app/api/cli/route.ts`
- Modify: Chat/terminal UI component

- [ ] **Step 1: Add detach action to /api/cli**

Add a `detach` action:
```
POST /api/cli?action=detach&cliId=xxx
```

This should:
1. Close the SSE stream without killing the PTY
2. Mark the session as `detached` in the process registry
3. Return success with session info (cliId, uptime, PID)

- [ ] **Step 2: Add UI for detach**

In the terminal/chat bubble header or context menu, add a "Detach" button (or icon):
- Clicking it sends the detach action
- Shows a toast: "Session detached. You can reconnect later."
- The bubble changes state to show "detached" with a "Reconnect" button

- [ ] **Step 3: Show detached sessions on page load**

On dashboard load, query for any detached sessions:
```
GET /api/cli?action=list
```

Returns all active/detached PTY sessions. If detached sessions exist, show a small banner or indicator: "1 background session running — [Reconnect]"

- [ ] **Step 4: Test detach + reconnect flow**

1. Start a Claude Code session
2. Click Detach — session goes to background
3. Navigate to another page
4. Come back — see "1 background session" indicator
5. Click Reconnect — session resumes with buffered output

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/
git commit -m "feat(dashboard): add terminal session detach and background indicator"
```

---

### Task 0G: Add Visible Send Button to Chat Input

**Files:**
- Modify: Chat input component (where the `⌘ + ↵` hint is rendered)

- [ ] **Step 1: Find the chat input component**

```bash
grep -rn "⌘\|send\|submit\|onSubmit" apps/dashboard/ --include="*.tsx" -l | grep -i chat
```

Read the component. Currently shows a keyboard shortcut hint (`⌘ + ↵`) but no visible send button or icon.

- [ ] **Step 2: Add a send button**

Add a visible send icon button (e.g., Lucide `SendHorizontal` or `ArrowUp`) next to the keyboard hint:
- Button should be clearly clickable
- Show the keyboard shortcut as a tooltip on hover: "Send (⌘+Enter)"
- Button should be visually prominent — users need to discover they can send messages
- Disable when input is empty

- [ ] **Step 3: Ensure Enter or ⌘+Enter both work**

Verify both keyboard shortcuts work for sending. The hint should reflect whichever is the actual binding.

- [ ] **Step 4: Test in browser**

1. Open chat — send button should be clearly visible
2. Click it — message sends
3. Hover — tooltip shows shortcut
4. Empty input — button is disabled/dimmed

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/
git commit -m "feat(dashboard): add visible send button to chat input"
```

---

### Task 0H: Fix or Remove Broken Chat Mode

**Files:**
- Modify: Chat component (where chat/terminal mode toggle lives)

The chat mode (parsed output as chat bubbles) is broken — shows empty/broken icons and output parsing fails. The 3-tier system (Tier 1: chat bubbles → Tier 2: raw text → Tier 3: full terminal) isn't falling through correctly.

- [ ] **Step 1: Diagnose the parsing failure**

```bash
grep -rn "ptyStreamParser\|tier\|parseChatMessage\|ChatBubble" apps/dashboard/ --include="*.tsx" --include="*.ts" -l
```

Read the parser. Understand what's failing: is the confidence threshold wrong? Is the regex not matching Claude Code output format? Has the output format changed?

- [ ] **Step 2: Decide — fix or remove**

**If fixable (< 3 hours):** Fix the parser to correctly classify output. Test with real Claude Code output.

**If not fixable quickly:** Remove chat mode entirely for launch. Default to terminal mode (Tier 3) which works. Remove the mode toggle from the UI. Users get a clean terminal experience instead of a broken chat experience.

To remove:
- Remove the chat/terminal mode toggle button
- Default to terminal view (xterm.js) for all output
- Keep the chat input bar (it sends to PTY either way)
- Remove or hide ChatBubbleView components

A working terminal is better than a broken chat parser.

- [ ] **Step 3: Test the chosen path**

If fixed: verify chat bubbles render correctly with real Claude Code output.
If removed: verify terminal mode works cleanly, no broken UI elements remain, chat input still sends commands.

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/
git commit -m "fix(dashboard): fix chat mode parsing (or remove broken chat mode, default to terminal)"
```

---

### Task 0I: Fix Minimize vs Close Chat Behavior

**Files:**
- Modify: Chat panel header component (where `—` and `×` buttons live)

Currently both minimize and close do the same thing (minimize). They should behave differently:

- [ ] **Step 1: Find the chat panel header component**

```bash
grep -rn "minimize\|close.*chat\|collapse.*panel" apps/dashboard/ --include="*.tsx" -l
```

Read the component. Identify the onClick handlers for both buttons.

- [ ] **Step 2: Differentiate the two actions**

**Minimize (`—`):**
- Collapse the chat panel (current behavior)
- PTY session keeps running in background
- Panel can be re-opened, session resumes

**Close (`×`):**
- Send `POST /api/cli?action=stop` to kill the PTY session
- Clear chat history from the panel
- Collapse the panel
- If session detach (Task 0F) is implemented: offer "Detach instead?" confirmation, or just close

- [ ] **Step 3: Add confirmation on close if session is active**

If there's an active PTY session running, show a brief confirmation before closing:
- "End this session?" with [End] [Cancel] buttons
- Or use a toast with undo: "Session ended" [Undo within 3s]

Skip confirmation if the session has already exited.

- [ ] **Step 4: Test in browser**

1. Start a session → click minimize (`—`) → panel collapses, session continues → reopen → session is there
2. Start a session → click close (`×`) → confirmation → confirm → PTY killed, panel closes clean
3. Session already finished → click close → no confirmation needed, just closes

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/
git commit -m "fix(dashboard): differentiate minimize (keep session) vs close (end session) in chat panel"
```

---

### Task 0J: Fix or Replace Chat Empty State Actions

**Files:**
- Modify: Chat empty state component (where "Ask me anything" and suggested action buttons render)

The "Ask me anything" empty state shows three buttons (List Skills, Get Skill, Find Skill) that don't work when clicked.

- [ ] **Step 1: Find the empty state component**

```bash
grep -rn "Ask me anything\|List Skills\|Get Skill\|Find Skill\|suggested action" apps/dashboard/ --include="*.tsx" -l
```

Read the component. Understand what the buttons are supposed to do — are they sending a command to the PTY? Calling an MCP tool? Or just broken onClick handlers?

- [ ] **Step 2: Decide — fix or replace**

**Option A — Fix:** Wire the buttons to send the command text into the chat input and submit it. E.g., clicking "List Skills" types `list-skills` into the input and sends it to the PTY/MCP.

**Option B — Replace with useful actions:** The current labels are technical ("Get Skill", "Find Skill" — what's the difference?). Replace with more useful first-run suggestions:

- "What can you do?" — sends a natural language prompt
- "Search my knowledge" — triggers knowledge search
- "Show system health" — triggers autoloop status

Pick whichever is more appropriate for the AI client running behind the chat.

- [ ] **Step 3: Test in browser**

1. Open chat (fresh, no session) — empty state shows
2. Click each suggested action — it should send the command and start a session
3. Response should appear in the chat/terminal

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/
git commit -m "fix(dashboard): wire chat empty state action buttons"
```

---

### Task 0K: Fix Chat Scrolling — Bumpy/Janky Scroll Behavior

**Files:**
- Modify: Chat window component (find via grep for scroll-related code in chat components)

- [ ] **Step 1: Identify the chat scroll container and logic**

```bash
grep -rn "scroll\|overflow\|scrollTo\|scrollIntoView" apps/dashboard/ --include="*.tsx" -l | grep -i chat
```

Read the chat container component. Identify:
- What triggers scroll (new message, resize, stream output?)
- Is `scrollIntoView` called with `behavior: 'smooth'` or instant?
- Is there a scroll-to-bottom logic? How is it triggered?
- Are there competing scroll triggers (multiple useEffects calling scroll?)

- [ ] **Step 2: Diagnose the bumpy scroll**

Common causes of janky chat scrolling:
1. **Multiple scroll triggers firing** — new message + stream chunk + resize all calling scrollIntoView
2. **Layout shifts** — agent bubbles resizing as output streams in, pushing scroll position
3. **Smooth scroll conflicting with rapid updates** — `behavior: 'smooth'` during fast streaming creates queued animations
4. **Missing `overflow-anchor`** — browser doesn't know what to anchor scroll to

- [ ] **Step 3: Fix the root cause**

Based on diagnosis, apply the appropriate fix:
- If competing scroll triggers: debounce or consolidate into one scroll handler
- If layout shifts: use `overflow-anchor: auto` on the scroll container, or pin scroll to bottom during streaming
- If smooth scroll during streaming: switch to `behavior: 'instant'` during active output, `'smooth'` only for user-initiated scroll
- If rapid re-renders: use `requestAnimationFrame` for scroll updates instead of direct calls in useEffect

- [ ] **Step 4: Test in browser**

1. Start a Claude Code session that produces long output
2. Scroll should be smooth and consistent — no jumping or bumping
3. Scroll to bottom should stick during streaming
4. Manual scroll up should NOT be overridden by new output (scroll lock)
5. Scrolling back down should re-engage auto-scroll

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/
git commit -m "fix(dashboard): resolve bumpy chat scroll behavior"
```

---

### Task 0L: Fix Chat Auto-Focus

**Files:**
- Modify: Chat input component

- [ ] **Step 1: Identify the auto-focus logic**

```bash
grep -rn "autoFocus\|auto-focus\|\.focus()\|inputRef" apps/dashboard/ --include="*.tsx" -l | grep -i chat
```

Read the chat input component. Understand:
- When should the input auto-focus? (page load, after sending message, after agent response completes, after switching back from focus mode)
- What's currently broken? (doesn't focus on load? loses focus after send? focus stolen by terminal?)

- [ ] **Step 2: Fix auto-focus behavior**

Expected behavior:
- Chat input should be focused on page load
- After sending a message, focus returns to input
- After agent response completes, focus returns to input
- When exiting terminal focus mode ("Back to Chat"), focus returns to input
- Focus should NOT be stolen while user is typing in the input

Use `useEffect` with appropriate dependencies and `inputRef.current?.focus()`. Add a small delay (`setTimeout(..., 0)`) if focus is lost due to React re-render timing.

- [ ] **Step 3: Test in browser**

1. Open chat — input should be focused (cursor blinking)
2. Type a message, press Enter — after send, cursor should be back in input
3. Agent responds — after response, cursor should be in input
4. Enter focus mode, exit it — cursor should be in input

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/
git commit -m "fix(dashboard): restore reliable auto-focus on chat input"
```

---

### Task 0M: Fix Chat Auto-Save

**Files:**
- Modify: Chat session/history component

- [ ] **Step 1: Identify the auto-save logic**

```bash
grep -rn "auto.save\|session.*save\|persist\|chat.json\|localStorage.*chat" apps/dashboard/ --include="*.tsx" --include="*.ts" -l
```

Read the auto-save implementation. Understand:
- What gets saved? (messages, session context, scroll position?)
- Where does it save to? (localStorage, file system, session file?)
- When does it save? (on every message? debounced? on unmount?)
- What's currently broken? (not saving at all? losing messages on refresh? saving stale data?)

- [ ] **Step 2: Fix auto-save**

Based on diagnosis:
- If not saving: ensure save triggers fire on message add/update
- If saving stale data: check that save uses current state, not stale closure
- If losing on refresh: ensure save fires on `beforeunload` and on component unmount
- If debounce is too long: reduce to 1-2 seconds for chat messages

- [ ] **Step 3: Test auto-save**

1. Send several messages in chat
2. Refresh the page
3. Previous messages should be restored
4. Agent responses should be preserved
5. Session context should be intact

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/
git commit -m "fix(dashboard): restore reliable chat auto-save"
```

---

## Task Group A: Website Messaging (Week 1, Days 2-3)

### Task 1: Badge, Hero, and GitHub Link (Changes 1, 2, 12)

**Files:**
- Modify: `~/Projects/Au-docs/venture-augur/website-working/index.html`

- [ ] **Step 1: Read current index.html hero section**

Read the full index.html to locate the badge, hero subtitle, and navigation elements. Note exact line numbers for each edit target.

- [ ] **Step 2: Change badge from "Coming Soon" to "Open Source"**

Find the badge element containing "Open Source . Coming Soon" and change to:
```html
<span class="badge">Open Source</span>
```

- [ ] **Step 3: Update hero subtitle**

Find the hero subtitle and replace with:
```html
<p class="hero-subtitle">One AI identity that connects every model you use. Your notes, files, skills, and workflows — unified on your machine through MCP.</p>
```

- [ ] **Step 4: Add GitHub link to navigation**

In the nav bar, add a GitHub link before the CTA button:
```html
<a href="https://github.com/augur-os/augur-os" target="_blank" rel="noopener">GitHub</a>
```

- [ ] **Step 5: Add GitHub stars badge to hero**

After the "Open Source" badge, add:
```html
<a href="https://github.com/augur-os/augur-os" class="github-badge" target="_blank" rel="noopener">
  <img src="https://img.shields.io/github/stars/augur-os/augur-os?style=social" alt="GitHub stars">
</a>
```

- [ ] **Step 6: Verify in browser**

Open `index.html` in browser. Confirm:
- Badge says "Open Source" (no "Coming Soon")
- Hero subtitle mentions "notes, files, skills, and workflows"
- GitHub link appears in nav
- Stars badge renders in hero

- [ ] **Step 7: Commit**

```bash
cd ~/Projects/Au-docs/venture-augur/website-working
git add index.html
git commit -m "feat(website): update badge, hero subtitle, add GitHub link"
```

---

### Task 2: Remove Course CTA, Update Free CTA (Change 3)

**Files:**
- Modify: `~/Projects/Au-docs/venture-augur/website-working/index.html`

- [ ] **Step 1: Read CTA section**

Locate the three CTA cards section (Start Free, Learn to Build, Get Expert Help).

- [ ] **Step 2: Remove the course card**

Delete the entire "Learn to Build" / $129 course CTA card element.

- [ ] **Step 3: Update free CTA from waitlist to GitHub**

Change the "Start Free" card:
- Button text: "Join Waitlist" -> "Get Started"
- Button link: point to GitHub repo URL
- Keep subtitle: "Open source. Free forever."
- Add secondary link below: "or join the waitlist for updates"

- [ ] **Step 4: Remove course link from navigation**

Find "Course" in nav links and remove it.

- [ ] **Step 5: Verify in browser**

Confirm: two CTA cards (Get Started + Sessions), no course reference, nav has no "Course" link.

- [ ] **Step 6: Commit**

```bash
git add index.html
git commit -m "feat(website): remove course CTA, update free CTA to GitHub"
```

---

### Task 3: Comparison Table Section (Change 4)

**Files:**
- Modify: `~/Projects/Au-docs/venture-augur/website-working/index.html`
- Modify: `~/Projects/Au-docs/venture-augur/website-working/styles.css`

- [ ] **Step 1: Create comparison table HTML**

Add a new section after "The Problem" section with id `comparison`. Use the existing section styling pattern from the page. Table content:

| Capability | Notion AI | Obsidian + Plugins | Augur |
|-----------|-----------|-------------------|-------|
| Knowledge philosophy | You write, AI assists | You write, plugins extend | AI creates, you curate. Knowledge compounds across every conversation. |
| Data ownership | Cloud-hosted on Notion servers | Local notes only | All yours locally -- notes, skills, plugins, documents, workflows |
| AI models | Notion's built-in AI only | Plugin-dependent, one at a time | Any -- Claude, GPT, Ollama, local models |
| Multi-IDE | No | No | Claude Code, Cursor, Codex, Gemini, Ollama |
| Skills / automation | None | Community plugins (not native) | Core of the product -- 200+ skills, ~80 autonomous autoloops |
| Self-healing ops | No | No | Autoloops detect, fix, and evolve nightly |
| RAG / search | Basic AI search | Plugin-dependent | BM25 + ripgrep hybrid, content-aware chunking |
| Offline / airplane | No | Partial (no AI offline) | Full -- local LLM, OCR, speech-to-text |
| Corporate-ready | Cloud compliance concerns | Local but no automation | Local-first, airplane mode, no API keys |
| Extensibility | Limited API | JS plugins | Open skill standard, any language, dev mode |
| UI role | UI IS the product | UI IS the product | UI is one MCP client among many |

Style the Augur column with the accent color. Make the table horizontally scrollable on mobile.

- [ ] **Step 2: Add comparison table styles to styles.css**

Match the existing glassmorphism dark theme. Augur column highlighted with `var(--accent)` color. Hover effect on rows. Responsive overflow-x scroll.

- [ ] **Step 3: Verify in browser**

Confirm: table renders after The Problem section, Augur column is highlighted, responsive on mobile (horizontal scroll), matches site's dark theme.

- [ ] **Step 4: Commit**

```bash
git add index.html styles.css
git commit -m "feat(website): add comparison table (Augur vs Notion AI vs Obsidian)"
```

---

### Task 4: Karpathy Callout and Dashboard Caption (Changes 9, 10)

**Files:**
- Modify: `~/Projects/Au-docs/venture-augur/website-working/index.html`
- Modify: `~/Projects/Au-docs/venture-augur/website-working/styles.css`

- [ ] **Step 1: Add Karpathy angle callout**

After the three problem bullets ("Claude doesn't know...", "Cursor doesn't remember...", "Every vendor's solution..."), add a callout block:

> Obsidian and Notion assume you write your notes. Augur assumes AI writes them -- and you curate. Your AI clients compile knowledge from conversations, research, and workflows into markdown files. You review them in Obsidian, the dashboard, or any tool you prefer. The knowledge base builds itself.

Style: accent-colored left border, slightly transparent background, italic text.

- [ ] **Step 2: Add dashboard caption**

Below the dashboard screenshot tabs section, add muted-text caption:

> The dashboard is one of many ways to interact with Augur. Claude Code, Cursor, Gemini, and the CLI all connect to the same MCP layer. The UI is optional -- your skills and data work everywhere.

Style: centered, smaller font, muted color (50% opacity white).

- [ ] **Step 3: Verify in browser**

Confirm: callout appears after problem bullets with accent border, dashboard caption appears below screenshots in muted text.

- [ ] **Step 4: Commit**

```bash
git add index.html styles.css
git commit -m "feat(website): add Karpathy knowledge callout and dashboard caption"
```

---

### Task 5: New Sections -- Two Modes, Autoloops, Skills, Corporate, No-Cloud (Changes 5, 6, 7, 8 + new)

**Files:**
- Modify: `~/Projects/Au-docs/venture-augur/website-working/index.html`
- Modify: `~/Projects/Au-docs/venture-augur/website-working/styles.css`

- [ ] **Step 1: Add "Meet You Where You Are" section (Two Modes)**

Two cards side-by-side:

**Production Mode:**
- Install community skill packs
- Fill them with your data
- Get AI-assisted immediately
- Technical Level: Same as using ChatGPT or Claude

**Dev Mode:**
- Build your own skills and hubs
- Customize everything
- Shape the system to your life
- Technical Level: Domain knowledge + AI fluency. No coding required.

Use existing card pattern from deploy modes section.

- [ ] **Step 2: Add "Your System Improves While You Sleep" section (Autoloops)**

Single section with descriptive paragraph:

> ~80 autonomous loops run nightly on idle hardware -- zero API cost. They scan for broken links, stale references, security vulnerabilities, and code quality issues -- and fix what they can. Evolution gaps tell you what's still untested. This isn't monitoring -- it's a system that gets better without you.

- [ ] **Step 3: Add "Install Any Skill. Build Your Own." section (Skills)**

Single section with descriptive paragraph and link to Agent Skills standard:

> Skills follow the open Agent Skills standard -- portable across AI clients, not locked to Augur. Your vault stays separate from the project. RAG indexes connect everything. Browse, search, and install from the dashboard or CLI.

- [ ] **Step 4: Add corporate reference**

Small inline callout (not a full section):

> **Works on Corporate PCs** -- Local-first, airplane mode, no data leaves the machine. See our enterprise proposition (link to enterprise.html).

- [ ] **Step 5: Add "No Cloud. By Design." section**

This is a deliberate positioning statement — flips the absence of cloud from weakness to strength:

> **There is no Augur Cloud. That's the point.**
>
> Your second brain runs on your machine -- not on our servers, not behind our login, not subject to our pricing changes. Local-first isn't a limitation. It's the architecture.
>
> When a cloud vendor changes policy, raises prices, or shuts down, your second brain doesn't notice. It's already home.

Place this near the "No API Key Required" section or the Deploy Modes section — wherever the "why local" argument flows naturally.

- [ ] **Step 6: Add CSS for new sections**

Match existing card and section styles from the deploy modes section. Read styles.css first to identify the pattern.

- [ ] **Step 7: Verify in browser**

Confirm: all five new elements render correctly, responsive on mobile, visual consistency with existing sections.

- [ ] **Step 8: Commit**

```bash
git add index.html styles.css
git commit -m "feat(website): add two modes, autoloops, skills, no-cloud, and corporate sections"
```

---

### Task 6: Skill Count Consistency (Change 11)

**Files:**
- Modify: `~/Projects/Au-docs/venture-augur/website-working/index.html`
- Modify: `~/Projects/Au-docs/venture-augur/website-working/more.html`
- Modify: `~/Projects/Augur/README.md`

- [ ] **Step 1: Count actual skills**

```bash
ls ~/Projects/Augur/skills/ | wc -l
```

- [ ] **Step 2: Pick canonical number**

Use "200+" as the public-facing number (rounded up for marketing). If actual count is below 195, use actual rounded number.

- [ ] **Step 3: Search and replace all skill count references**

Search across all website files and README for any skill count mentions (132, 171, 193, 200, 209, etc.) and replace all with the canonical number.

- [ ] **Step 4: Verify no inconsistencies remain**

Re-run the search to confirm one number everywhere.

- [ ] **Step 5: Commit both repos**

Website repo:
```bash
cd ~/Projects/Au-docs/venture-augur/website-working
git add -A && git commit -m "fix(website): standardize skill count to 200+"
```

Augur repo:
```bash
cd ~/Projects/Augur
git add README.md && git commit -m "fix: standardize skill count to 200+"
```

---

## Task Group B: Create-Augur Scaffolder (Week 1, Days 1-2)

### Task 7: Scaffold `create-augur` npm package

**Files:**
- Create: `~/Projects/Augur/packages/create-augur/package.json`
- Create: `~/Projects/Augur/packages/create-augur/index.js`
- Create: `~/Projects/Augur/packages/create-augur/README.md`

- [ ] **Step 1: Create packages directory**

```bash
mkdir -p ~/Projects/Augur/packages/create-augur
```

- [ ] **Step 2: Create package.json**

```json
{
  "name": "create-augur",
  "version": "0.1.0",
  "description": "Create a new Augur project -- your second brain, on your machine",
  "bin": {
    "create-augur": "./index.js"
  },
  "keywords": ["augur", "ai", "mcp", "knowledge-base", "second-brain", "local-first"],
  "author": "Guriqo",
  "license": "MIT",
  "repository": {
    "type": "git",
    "url": "https://github.com/augur-os/augur-os"
  },
  "engines": {
    "node": ">=20"
  }
}
```

- [ ] **Step 3: Write the scaffolder script (index.js)**

Node.js CLI script with zero dependencies. Uses built-in modules only (`child_process`, `fs`, `path`, `readline`).

Behavior:
1. Accept project name as first arg: `npx create-augur my-brain`
2. If no name given, prompt interactively
3. Validate name (no existing directory)
4. Clone repo shallow: `git clone --depth 1 <REPO> <name>`
5. Remove `.git`, init fresh git repo
6. Check Python 3.11+ availability, warn if missing
7. Check `uv` availability, run `uv sync` if available
8. Check `pnpm` availability, run `pnpm install` if available
9. Print success with next steps

Use `spawnSync` (not shell strings) for all subprocess calls to avoid command injection. Example:
```javascript
spawnSync('git', ['clone', '--depth', '1', REPO, name], { stdio: 'inherit' });
```

Print at end:
```
Augur created in ./<name>

Next steps:
  cd <name>
  pnpm --filter dashboard dev    # Start the dashboard
  aug discover                    # Browse available skills

Docs:   https://augur.run
GitHub: https://github.com/augur-os/augur-os
```

- [ ] **Step 4: Make executable**

```bash
chmod +x ~/Projects/Augur/packages/create-augur/index.js
```

- [ ] **Step 5: Test locally**

```bash
cd /tmp
node ~/Projects/Augur/packages/create-augur/index.js test-augur
```

Confirm: clones repo, removes .git, inits fresh git, checks dependencies, prints next steps.

Clean up: `rm -rf /tmp/test-augur`

- [ ] **Step 6: Test via npm link**

```bash
cd ~/Projects/Augur/packages/create-augur
npm link
cd /tmp
npx create-augur test-project
```

Confirm: scaffolder runs end-to-end via npx.

Clean up:
```bash
npm unlink -g create-augur
rm -rf /tmp/test-project
```

- [ ] **Step 7: Write package README.md**

Short README for the npm package page:

```markdown
# create-augur

Scaffold a new [Augur](https://augur.run) project -- your second brain, on your machine.

## Usage

    npx create-augur@latest my-brain

## Requirements

- Node.js 20+
- Python 3.11+ (for MCP server and skills)
- pnpm (for dashboard)
- uv (for Python dependencies)

## Links

- Website: https://augur.run
- GitHub: https://github.com/augur-os/augur-os
- License: MIT
```

- [ ] **Step 8: Commit**

```bash
cd ~/Projects/Augur
git add packages/create-augur/
git commit -m "feat: add create-augur npm scaffolder for 1-command install"
```

---

## Task Group C: Demo and README (Week 1, Days 3-4)

### Task 8: Record Demo GIF/Video

This task is manual -- the user records the demo. This provides the storyboard.

The key differentiator: show onboarding FROM an AI client. The `npx create-augur` stays as a fallback install method, but the primary demo shows Claude Code running `/onboard` -- your AI installs your AI system. Cabinet cannot do this.

- [ ] **Step 1: Plan demo flow (60-90 seconds)**

Two demo options (record both if time permits):

**Demo A: AI Client Onboarding (primary -- the differentiator)**
1. (10s) Open Claude Code in terminal
2. (10s) Type: "Set up Augur as my second brain" -- agent runs `/onboard`
3. (10s) Show skills being installed, vault being connected
4. (5s) Dashboard opens automatically
5. (15s) Dashboard Browse page: scroll through skills, show the breadth
6. (10s) Back in Claude Code: run a skill via chat ("search my knowledge for...")
7. (5s) End card: augur.run + GitHub URL

**Demo B: Quick Install (secondary -- for README/website)**
1. (10s) Terminal: `npx create-augur my-brain` -- show the install
2. (5s) Terminal: `cd my-brain && pnpm --filter dashboard dev` -- start dashboard
3. (15s) Dashboard Browse page: scroll through skills
4. (10s) Click into a skill -- show what a skill looks like
5. (10s) Dashboard System page: show autoloops running
6. (5s) End card: augur.run + GitHub URL

- [ ] **Step 2: Record with macOS screen recording**

Use QuickTime Player > File > New Screen Recording, or Cmd+Shift+5.

Optional: convert to GIF for README:
```bash
ffmpeg -i demo.mp4 -vf "fps=10,scale=800:-1:flags=lanczos" -loop 0 demo.gif
```

- [ ] **Step 3: Save assets**

Video for website:
```bash
cp demo.mp4 ~/Projects/Au-docs/venture-augur/website-working/assets/
```

GIF for README:
```bash
cp demo.gif ~/Projects/Augur/docs/assets/demo.gif
```

- [ ] **Step 4: Embed video in website**

Add to hero section or below dashboard screenshots in index.html:
```html
<video class="demo-video" autoplay muted loop playsinline>
  <source src="assets/demo.mp4" type="video/mp4">
</video>
```

- [ ] **Step 5: Commit website**

```bash
cd ~/Projects/Au-docs/venture-augur/website-working
git add -A && git commit -m "feat(website): add demo video"
```

---

### Task 9: README Rewrite

**Files:**
- Modify: `~/Projects/Augur/README.md`

- [ ] **Step 1: Read current README fully**

Read the complete README to understand all sections.

- [ ] **Step 2: Replace screenshot placeholder**

Find `[Screenshot/GIF TBD]` and replace with:
```markdown
!Augur Dashboard
```

- [ ] **Step 3: Simplify install to 1 command**

Lead the Quick Start section with:
```markdown
## Quick Start

    npx create-augur@latest my-brain
    cd my-brain
    pnpm --filter dashboard dev

Dashboard opens at localhost:3000.
```

Move existing detailed install methods (git clone, Cowork, individual skills) to an "Alternative Install Methods" subsection below.

- [ ] **Step 4: Fix npm vs pnpm inconsistency**

Search for `npm install` and `npm run` in README. Replace with `pnpm install` and `pnpm` equivalents. Keep `npx create-augur` as-is.

- [ ] **Step 5: Update skill count**

Replace any skill count references (132, 171, 193) with the canonical number from Task 6.

- [ ] **Step 6: Add augur.run link**

Add to the top badges area:
```markdown
[Website](https://augur.run) | [Documentation](https://augur.run/more.html) | [Sessions](https://augur.run/sessions.html)
```

- [ ] **Step 7: Verify README renders correctly**

Use a local markdown previewer or push to a test branch to confirm all links, images, and formatting render correctly on GitHub.

- [ ] **Step 8: Commit**

```bash
cd ~/Projects/Augur
git add README.md
git commit -m "docs: rewrite README for external users -- 1-command install, demo, consistent counts"
```

---

## Task Group D: GitHub Repo Polish (Week 2, Days 1-2)

### Task 10: Public Repo Metadata, Badges, and Community Files

Target repo: `augur-os/augur-os` (the clean public repo that gets released versions).

- [ ] **Step 1: Fix social preview**

The current `.github/social_preview.png` says "Exocortex" (old project name). Create a new one with "Augur" branding:
- Use the existing Augur logo/icon from the website
- Text: "Augur -- Your Second Brain, On Your Machine"
- Dark background matching website theme
- Upload via GitHub web UI: Settings > Social preview

- [ ] **Step 2: Set repo description and topics**

Via GitHub web UI or `gh` CLI:

Description: "Local-first personal AI OS. 200+ composable skills. Any model. Plain text. Yours forever."

Topics (set via repo Settings > About > Topics):
`mcp`, `ai-agents`, `knowledge-management`, `second-brain`, `local-first`, `automation`, `skills`, `model-agnostic`, `ollama`, `personal-ai`, `python`, `nextjs`, `cli`, `model-context-protocol`

```bash
gh repo edit augur-os/augur-os --description "Local-first personal AI OS. 200+ composable skills. Any model. Plain text. Yours forever." --add-topic mcp,ai-agents,knowledge-management,second-brain,local-first,automation,skills,model-agnostic,ollama,personal-ai,python,nextjs,cli
```

- [ ] **Step 3: Fix CI badge in README**

Current badge links to non-existent `ci.yml`. Fix to point to actual primary workflow:
```markdown
[![CI](https://github.com/augur-os/augur-os/actions/workflows/ci-tests.yml/badge.svg)](https://github.com/augur-os/augur-os/actions/workflows/ci-tests.yml)
```

- [ ] **Step 4: Add full badge row to README**

Replace current badges with a complete row:
```markdown
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/augur-os/augur-os/actions/workflows/ci-tests.yml/badge.svg)](https://github.com/augur-os/augur-os/actions/workflows/ci-tests.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Node 20+](https://img.shields.io/badge/node-20+-green.svg)](https://nodejs.org/)
[![GitHub stars](https://img.shields.io/github/stars/augur-os/augur-os?style=social)](https://github.com/augur-os/augur-os)
[![GitHub last commit](https://img.shields.io/github/last-commit/augur-os/augur-os)](https://github.com/augur-os/augur-os/commits)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
```

- [ ] **Step 5: Add Star History chart to README**

At the bottom of README, before the license section:
```markdown
## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=augur-os/augur-os&type=Date)](https://star-history.com/#augur-os/augur-os&Date)
```

- [ ] **Step 6: Add `[project.urls]` to pyproject.toml**

```toml
[project.urls]
Homepage = "https://augur.run"
Repository = "https://github.com/augur-os/augur-os"
Documentation = "https://augur.run/more.html"
Issues = "https://github.com/augur-os/augur-os/issues"
```

- [ ] **Step 7: Add CODE_OF_CONDUCT.md**

Use the Contributor Covenant v2.1 standard:
```bash
curl -o CODE_OF_CONDUCT.md https://www.contributor-covenant.org/version/2/1/code_of_conduct/code_of_conduct.md
```

Update the contact email to the appropriate Augur email.

- [ ] **Step 8: Add .github/ISSUE_TEMPLATE/config.yml**

```yaml
blank_issues_enabled: true
contact_links:
  - name: Questions & Discussion
    url: https://github.com/augur-os/augur-os/discussions
    about: Ask questions and discuss ideas here
  - name: Documentation
    url: https://augur.run/more.html
    about: Read the documentation before filing an issue
```

- [ ] **Step 9: Copy SECURITY.md to .github/**

GitHub looks for SECURITY.md in `.github/` first:
```bash
cp SECURITY.md .github/SECURITY.md
```

- [ ] **Step 10: Write real CHANGELOG.md entries**

Replace the placeholder with actual release notes for v0.1.0:
- List major features shipped (skill system, MCP server, dashboard, autoloops, RAG)
- Keep it concise -- 10-15 bullet points max

- [ ] **Step 11: Enable GitHub Discussions**

```bash
gh repo edit augur-os/augur-os --enable-discussions
```

Create categories via web UI:
- General (default)
- Ideas / Feature Requests
- Q&A (with "mark as answer")
- Show and Tell

No Discord needed at launch. Discussions is the community channel.

- [ ] **Step 12: Create labels and 10+ starter issues**

Labels:
```bash
gh label create "good first issue" --description "Good for newcomers" --color 7057ff
gh label create "help wanted" --description "Extra attention is needed" --color 008672
gh label create "documentation" --description "Improvements or additions to docs" --color 0075ca
gh label create "skill-request" --description "Request for a new skill" --color d876e3
```

Create 10+ well-scoped issues:
1. "docs: add troubleshooting section to README" (good first issue, documentation)
2. "docs: add FAQ for creating custom skills" (good first issue, documentation)
3. "feat: add Windows install instructions to README" (good first issue, documentation)
4. "feat: skill request -- Todoist integration" (skill-request, help wanted)
5. "feat: skill request -- Pocket/Instapaper reading list" (skill-request, help wanted)
6. "docs: add architecture diagram to README" (good first issue, documentation)
7. "feat: add Homebrew formula for Augur CLI" (help wanted)
8. "docs: document airplane mode setup with Ollama" (good first issue, documentation)
9. "feat: skill request -- Raindrop.io bookmarks" (skill-request, help wanted)
10. "test: add smoke test for create-augur scaffolder" (good first issue)

- [ ] **Step 13: Commit all repo polish changes**

```bash
git add README.md pyproject.toml CODE_OF_CONDUCT.md .github/SECURITY.md .github/ISSUE_TEMPLATE/config.yml CHANGELOG.md
git commit -m "chore: polish GitHub repo for open source launch -- badges, metadata, community files"
```

---

## Task Group E: Launch Content (Week 2, Days 3-4)

### Task 11: LinkedIn Launch Post

**Files:**
- Create: `~/Projects/Augur/docs/superpowers/plans/launch-content-linkedin.md`

- [ ] **Step 1: Draft the LinkedIn post**

Structure:
- **Hook** (2 lines): Karpathy angle -- "Karpathy described the missing layer for LLMs. We've been building it for months."
- **Flip** (3 lines): Obsidian/Notion assume you write. Augur assumes AI writes, you curate.
- **What it is** (5-6 lines): MCP-first skill layer. 200+ skills. Any model. Any IDE.
- **Key differentiators** (5 bullets): autoloops, airplane mode, skill standard, vault separation, two modes
- **CTA** (2 lines): GitHub link + augur.run + "Book a session to set this up for your team"

Keep under 3000 characters (LinkedIn limit).

- [ ] **Step 2: Review and iterate**

Read aloud. Check: hook grabs in first 2 lines, differentiators are concrete not abstract, CTA is clear.

- [ ] **Step 3: Prepare visual assets**

Best option: carousel with 3-4 images:
1. Dashboard browse page showing skills
2. Architecture diagram (Filesystem > MCP > Any Client)
3. Comparison table screenshot
4. Terminal showing `npx create-augur`

- [ ] **Step 4: Commit draft**

```bash
cd ~/Projects/Augur
git add docs/superpowers/plans/launch-content-linkedin.md
git commit -m "docs: draft LinkedIn launch post"
```

---

### Task 12: HN Show HN Post

**Files:**
- Create: `~/Projects/Augur/docs/superpowers/plans/launch-content-hn.md`

- [ ] **Step 1: Draft the HN post**

Title (under 80 chars): "Show HN: Augur -- MCP-first personal AI OS with 200+ skills (open source)"

URL: https://github.com/augur-os/augur-os

If self-post (text, no URL), structure:
- What it is (1 paragraph)
- How it works (Filesystem > MCP > Any Client)
- What makes it different (4 bullets: AI creates/you curate, autoloops, airplane mode, open skill standard)
- Tech details (Python + TypeScript, BM25 RAG, no vector DB, 388 ADRs)
- Links: GitHub, website, install command

- [ ] **Step 2: Review against HN norms**

Check: no ALL CAPS, no exclamation marks, factual not marketing, shows technical depth, no aggressive CTAs.

- [ ] **Step 3: Commit draft**

```bash
cd ~/Projects/Augur
git add docs/superpowers/plans/launch-content-hn.md
git commit -m "docs: draft HN Show HN post"
```

---

## Task Group F: Launch Day (Week 2, Day 7)

### Task 13: Pre-Launch QA

- [ ] **Step 1: Test install from scratch**

```bash
cd /tmp
npx create-augur test-launch
cd test-launch
pnpm --filter dashboard dev
```

Confirm: installs cleanly, dashboard opens at localhost:3000, browse page shows skills.

Clean up: `rm -rf /tmp/test-launch`

- [ ] **Step 2: Test all website links**

Open augur.run in browser. Click every link:
- GitHub link -> repo loads
- "Get Started" -> GitHub repo
- "Book Session" -> sessions.html loads
- "Enterprise" -> enterprise.html loads
- "Learn More" -> more.html loads
- All internal anchors work
- No broken images
- No course references remain

- [ ] **Step 3: Verify GitHub repo is public**

```bash
gh repo view augur-os/augur-os --json visibility
```

Expected: `"visibility": "public"`

- [ ] **Step 4: Verify README renders on GitHub**

Open the repo URL in browser. Confirm: demo GIF loads, badges render, install command visible above fold, links work.

- [ ] **Step 5: Final skill count check**

Search website files and README for any non-canonical skill count numbers. Confirm only the chosen number appears.

---

### Task 14: Launch Execution

- [ ] **Step 1: Deploy website**

Push final website changes to hosting (GitHub Pages or Hostinger).

- [ ] **Step 2: Post LinkedIn**

Copy final post from `launch-content-linkedin.md`. Attach visual carousel. Post.

- [ ] **Step 3: Post HN (same day or next morning)**

Submit at https://news.ycombinator.com/submit:
- Title: "Show HN: Augur -- MCP-first personal AI OS with 200+ skills (open source)"
- URL: https://github.com/augur-os/augur-os

(HN rules: URL OR text, not both. Use URL if available.)

- [ ] **Step 4: Monitor and respond (first 6 hours)**

- Respond to every LinkedIn comment within 30 minutes
- Respond to every HN comment within 1 hour
- Fix any bug reports immediately
- Track session inquiry count

- [ ] **Step 5: Reddit posts (day 2-3 if traction)**

If LinkedIn or HN gets traction:
- r/selfhosted: "Self-hosted AI knowledge system with 200+ skills -- MCP-first, airplane mode, open source"
- r/LocalLLaMA: "Full airplane mode AI OS -- Ollama + on-device OCR + 200 skills"
- r/ObsidianMD: "Augur: an MCP layer that makes your Obsidian vault AI-native across every IDE"

---

## Dependency Graph

```
Tasks 0A-0D (dashboard UX fixes) -- FIRST, can parallelize
  |
  v
Task 7 (create-augur scaffolder)
  |
  v
Task 8 (demo video) -- needs working dashboard + scaffolder
  |
  v
Task 9 (README rewrite) -- needs demo GIF + canonical install command
  |
  v
Tasks 1-5 (website changes) -- can run in parallel with each other
  |
  v
Task 6 (skill count) -- after website + README are drafted
  |
  v
Task 10 (GitHub repo polish) -- after repo content is polished
  |
  v
Tasks 11-12 (launch content) -- after website and README are final (can parallelize)
  |
  v
Task 13 (QA) -- after everything else
  |
  v
Task 14 (launch)
```

Tasks 0A-0D are independent and can be parallelized.
Tasks 1-5 are independent and can be parallelized.
Tasks 11-12 are independent and can be parallelized.
