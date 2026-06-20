# Hub Restructuring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure 15 UI hubs into 5 demo-focused apps (Brain, Career, Life, Studio, Command) with 13 consolidated tabs.

**Architecture:** Update skill metadata (`x-augur-hub`, `contributes_to`) to point to new hub IDs. Create hub owner configs for each new app. Write 13 consolidated tab pages that compose sections from multiple skills. Run mount-plugins to rebuild.

**Tech Stack:** TypeScript (Next.js pages), Python (migration script), YAML (SKILL.md frontmatter)

**Spec:** `docs/superpowers/specs/2026-03-18-hub-restructuring-design.md`

---

## File Structure

### New files
- `scripts/migrate-hubs.py` — one-time migration script for SKILL.md frontmatter
- `.claude/skills/knowledge/augur/dashboard/page.tsx` — Brain > Memory (consolidated)
- `.claude/skills/reading-list/augur/dashboard/page.tsx` — Brain > Library (consolidated)
- `.claude/skills/ai_bridge/augur/dashboard/page.tsx` — Brain > Agents (consolidated)
- `.claude/skills/career/augur/dashboard/page.tsx` — Career > Pipeline (consolidated, rewrite)
- `.claude/skills/venture-augur/augur/dashboard/page.tsx` — Career > Venture (consolidated, rewrite)
- `.claude/skills/wealth/augur/dashboard/page.tsx` — Life > Wealth (exists, keep)
- `.claude/skills/attention/augur/dashboard/page.tsx` — Life > Dashboard (consolidated, rewrite)
- `.claude/skills/home-automation/augur/dashboard/page.tsx` — Life > Home (consolidated, rewrite)
- `.claude/skills/advisor/augur/dashboard/page.tsx` — Studio > Workbench (consolidated, rewrite)
- `.claude/skills/frontend/augur/dashboard/page.tsx` — Studio > Design (consolidated, rewrite)
- `.claude/skills/mcp-app-factory/augur/dashboard/page.tsx` — Studio > Factory (consolidated, rewrite)
- `.claude/skills/daemon/augur/dashboard/page.tsx` — Command > Monitor (consolidated, rewrite)
- `.claude/skills/updater/augur/dashboard/page.tsx` — Command > System (consolidated, rewrite)

### Modified files
- `src/config/paths.py:143-160` — update PLUGIN_BUNDLES
- `~130 .claude/skills/*/SKILL.md` — update x-augur-hub frontmatter
- `CLAUDE.md` — update hub list

### Deleted directories
- `apps/dashboard/app/{admin,ai,consulting,core,finance,health,home,lifestyle,observability,productivity,professional}/`

---

### Task 1: Write hub migration script

**Files:**
- Create: `scripts/migrate-hubs.py`

This script reads all SKILL.md files, updates `x-augur-hub` to the new hub ID, and adds `x-augur-tab` to declare the consolidated tab.

- [ ] **Step 1: Write the migration script**

```python
#!/usr/bin/env python3
"""One-time migration: update x-augur-hub in all SKILL.md files."""
import re
from pathlib import Path

# Old hub -> new hub mapping
HUB_MAP = {
    "ai": "brain",
    "admin": None,  # split across multiple hubs, handled in SKILL_OVERRIDES
    "consulting": "hidden",
    "core": None,  # split, handled in SKILL_OVERRIDES
    "enterprise": "career",
    "finance": "life",
    "health": "life",
    "home": "life",
    "lifestyle": "life",
    "observability": "command",
    "productivity": "life",
    "professional": "career",
    # These stay the same or are already correct:
    "career": "career",
    "dev": "studio",
    "adaptive": "adaptive",
}

# Skills that need per-skill override (split hubs)
SKILL_OVERRIDES = {
    # admin -> split
    "attention": ("life", "dashboard"),
    "system-cleanup": ("command", "system"),
    "updater": ("command", "system"),
    "workflows": ("command", "system"),
    "channels": ("life", "dashboard"),
    "save": ("command", "system"),
    "import": ("command", "system"),
    "remote-access": ("command", "system"),
    "discovery": ("command", "system"),
    "onboard": ("command", "system"),
    "file-manager": ("life", "home"),
    # core -> split
    "commands": ("brain", "memory"),
    # ai -> brain (all go to brain, but different tabs)
    "knowledge": ("brain", "memory"),
    "ai_bridge": ("brain", "agents"),
    "dev-sync": ("brain", "agents"),
    "search": ("brain", "memory"),
    "rag": ("brain", "memory"),
    "scraper": ("brain", "memory"),
    "ask": ("brain", "memory"),
    "reindex-rag": ("brain", "memory"),
    "reindex-project": ("brain", "memory"),
    "dev-learn": ("brain", "memory"),
    "reading-list": ("brain", "library"),
    "books": ("brain", "library"),
    # dev -> studio (different tabs)
    "advisor": ("studio", "workbench"),
    "developer": ("studio", "workbench"),
    "devops": ("studio", "workbench"),
    "frontend": ("studio", "design"),
    "mcp-app-factory": ("studio", "factory"),
    "validator": ("studio", "factory"),
    "page-builder": ("studio", "design"),
    "renderer": ("studio", "design"),
    "dev-adr": ("studio", "workbench"),
    "dev-debug": ("studio", "workbench"),
    "test-client": ("studio", "workbench"),
    "dev-build": ("studio", "workbench"),
    "test-ui": ("studio", "workbench"),
    # observability -> command
    "daemon": ("command", "monitor"),
    "observe": ("command", "monitor"),
    "ops-daemon": ("command", "monitor"),
    "metrics": ("command", "monitor"),
    # productivity -> life
    "apple": ("life", "dashboard"),
    "eisenhower": ("life", "dashboard"),
    "google-workspace": ("life", "dashboard"),
    "organizer": ("life", "home"),
    # career (different tabs)
    "career": ("career", "pipeline"),
    "growth": ("career", "pipeline"),
    "coach": ("career", "pipeline"),
    "interview-coach": ("career", "pipeline"),
    "linkedin-writer": ("career", "venture"),
    "content": ("career", "venture"),
    "post": ("career", "venture"),
    "danit": ("career", "venture"),
    "venture-augur": ("career", "venture"),
    "project-dev": ("career", "venture"),
    "enterprise": ("career", "venture"),
    # finance/health/home/lifestyle -> life
    "wealth": ("life", "wealth"),
    "finance": ("life", "wealth"),
    "health": ("life", "home"),
    "wearables": ("life", "home"),
    "home-automation": ("life", "home"),
    "lifestyle": ("life", "home"),
    # command extras
    "dev-rollback": ("command", "system"),
    "dev-test": ("command", "system"),
    "dev-merge": ("command", "system"),
    "dev-loops": ("command", "monitor"),
    "kill-augur": ("adaptive", None),
    "nightly": ("adaptive", None),
    "executor": ("adaptive", None),
    "sync-agents": ("adaptive", None),
    "metrics": ("adaptive", None),
    # hidden
    "client-ai-consulting": ("hidden", None),
    "client-smb-design": ("hidden", None),
    "client-terminal-automation": ("hidden", None),
    "client-hub": ("hidden", None),
}

# Tab -> host skill (the skill whose page.tsx becomes the consolidated tab)
TAB_HOSTS = {
    ("brain", "memory"): "knowledge",
    ("brain", "library"): "reading-list",
    ("brain", "agents"): "ai_bridge",
    ("career", "pipeline"): "career",
    ("career", "venture"): "venture-augur",
    ("life", "wealth"): "wealth",
    ("life", "dashboard"): "attention",
    ("life", "home"): "home-automation",
    ("studio", "workbench"): "advisor",
    ("studio", "design"): "frontend",
    ("studio", "factory"): "mcp-app-factory",
    ("command", "monitor"): "daemon",
    ("command", "system"): "updater",
}


def migrate_skill_md(path: Path, skill_name: str) -> bool:
    """Update x-augur-hub and add x-augur-tab in SKILL.md frontmatter."""
    content = path.read_text()

    # Determine new hub and tab
    if skill_name in SKILL_OVERRIDES:
        new_hub, new_tab = SKILL_OVERRIDES[skill_name]
    else:
        # Check current hub from frontmatter
        hub_match = re.search(r'^x-augur-hub:\s*(.+)$', content, re.MULTILINE)
        if not hub_match:
            print(f"  SKIP {skill_name}: no x-augur-hub found")
            return False
        current_hub = hub_match.group(1).strip()
        new_hub = HUB_MAP.get(current_hub)
        if new_hub is None:
            print(f"  SKIP {skill_name}: hub '{current_hub}' needs manual override")
            return False
        new_tab = None  # auto-* skills don't need tabs

    # Replace x-augur-hub
    content = re.sub(
        r'^(x-augur-hub:\s*).*$',
        f'\\1{new_hub}',
        content,
        count=1,
        flags=re.MULTILINE,
    )

    # Add or update x-augur-tab (after x-augur-hub line)
    if new_tab:
        if 'x-augur-tab:' in content:
            content = re.sub(
                r'^(x-augur-tab:\s*).*$',
                f'\\1{new_tab}',
                content,
                count=1,
                flags=re.MULTILINE,
            )
        else:
            content = re.sub(
                r'^(x-augur-hub:\s*.+)$',
                f'\\1\nx-augur-tab: {new_tab}',
                content,
                count=1,
                flags=re.MULTILINE,
            )

    path.write_text(content)
    print(f"  OK {skill_name}: hub={new_hub} tab={new_tab}")
    return True


def main():
    skills_dir = Path(".claude/skills")
    if not skills_dir.exists():
        print("ERROR: Run from project root")
        return

    count = 0
    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue
        skill_name = skill_dir.name
        if migrate_skill_md(skill_md, skill_name):
            count += 1

    print(f"\nMigrated {count} skills")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the migration script (dry run — review output)**

Run: `cd ~/Projects/Augur && python3 scripts/migrate-hubs.py`
Expected: `Migrated ~130 skills` with OK/SKIP for each

- [ ] **Step 3: Verify a sample of migrations**

Run: `grep 'x-augur-hub:' .claude/skills/knowledge/SKILL.md .claude/skills/career/SKILL.md .claude/skills/daemon/SKILL.md .claude/skills/wealth/SKILL.md`
Expected: brain, career, command, life respectively

- [ ] **Step 4: Commit**

```bash
git add scripts/migrate-hubs.py .claude/skills/*/SKILL.md
git commit -m "refactor: migrate x-augur-hub to new 5-app taxonomy"
```

---

### Task 2: Update PLUGIN_BUNDLES in paths.py

**Files:**
- Modify: `src/config/paths.py:143-160`

- [ ] **Step 1: Update the PLUGIN_BUNDLES list**

Replace the existing list at line ~143:
```python
PLUGIN_BUNDLES = [
    "adaptive", "brain", "career", "command",
    "hidden", "life", "studio",
]
```

- [ ] **Step 2: Verify no other references to old bundle names**

Run: `grep -r '"admin"\|"ai"\|"consulting"\|"core"\|"enterprise"\|"finance"\|"health"\|"home"\|"lifestyle"\|"observability"\|"orchestration"\|"productivity"\|"professional"' src/config/paths.py`
Expected: No matches (only the new names)

- [ ] **Step 3: Commit**

```bash
git add src/config/paths.py
git commit -m "refactor: update PLUGIN_BUNDLES to 5-app taxonomy"
```

---

### Task 3: Create hub owner configs for 5 new hubs

**Files:**
- Modify: `.claude/skills/knowledge/SKILL.md` — Brain hub owner
- Modify: `.claude/skills/career/SKILL.md` — Career hub owner (may already exist)
- Modify: `.claude/skills/attention/SKILL.md` — Life hub owner
- Modify: `.claude/skills/advisor/SKILL.md` — Studio hub owner
- Modify: `.claude/skills/daemon/SKILL.md` — Command hub owner

Each hub needs exactly one skill with `hub.owner: true` in its `x-augur-config`. The hub owner skill provides the hub metadata (title, icon, subtitle, nav_order).

- [ ] **Step 1: Add hub owner config to knowledge SKILL.md (Brain)**

Add to `x-augur-config` section in `.claude/skills/knowledge/SKILL.md`:
```yaml
x-augur-config:
  hub:
    id: brain
    owner: true
    title: Brain
    subtitle: Your AI second brain
    icon: Brain
    nav_order: 10
    category: personal
    iconBg: bg-emerald-500/20
    iconColor: text-emerald-400
    overview:
      search: true
      layout: masonry
```

- [ ] **Step 2: Add hub owner config to attention SKILL.md (Life)**

```yaml
x-augur-config:
  hub:
    id: life
    owner: true
    title: Life
    subtitle: AI life management
    icon: Heart
    nav_order: 30
    category: personal
    iconBg: bg-amber-500/20
    iconColor: text-amber-400
    overview:
      search: true
      layout: masonry
```

- [ ] **Step 3: Add hub owner config to advisor SKILL.md (Studio)**

```yaml
x-augur-config:
  hub:
    id: studio
    owner: true
    title: Studio
    subtitle: Build, test, ship
    icon: Hammer
    nav_order: 40
    category: system
    iconBg: bg-violet-500/20
    iconColor: text-violet-400
    overview:
      search: true
      layout: masonry
```

- [ ] **Step 4: Add hub owner config to daemon SKILL.md (Command)**

```yaml
x-augur-config:
  hub:
    id: command
    owner: true
    title: Command
    subtitle: Self-managing infrastructure
    icon: Terminal
    nav_order: 50
    category: system
    iconBg: bg-pink-500/20
    iconColor: text-pink-400
    overview:
      search: true
      layout: masonry
```

- [ ] **Step 5: Verify career hub owner already exists, update if needed**

Read `.claude/skills/career/SKILL.md` and check if `hub.owner: true` is set. If so, update `nav_order: 20` and `subtitle: "Get hired, grow, build your brand"`. If not, add the config block.

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/knowledge/SKILL.md .claude/skills/attention/SKILL.md .claude/skills/advisor/SKILL.md .claude/skills/daemon/SKILL.md .claude/skills/career/SKILL.md
git commit -m "feat: create hub owner configs for 5 new apps"
```

---

### Task 4: Delete old hub directories and run mount-plugins

**Files:**
- Delete: `apps/dashboard/app/{admin,ai,consulting,core,dev,finance,health,home,lifestyle,observability,productivity,professional}/`
- Keep: `apps/dashboard/app/career/` (reused). `dev/` is deleted and replaced by `studio/` via mount-plugins.

- [ ] **Step 1: Delete old hub directories**

```bash
cd ~/Projects/Augur
rm -rf apps/dashboard/app/admin apps/dashboard/app/ai apps/dashboard/app/consulting apps/dashboard/app/core apps/dashboard/app/finance apps/dashboard/app/health apps/dashboard/app/home apps/dashboard/app/lifestyle apps/dashboard/app/observability apps/dashboard/app/productivity apps/dashboard/app/professional apps/dashboard/app/dev
```

- [ ] **Step 2: Run mount-plugins to create new hub directories**

```bash
cd apps/dashboard && npm run mount-plugins
```

Expected: New directories created under `apps/dashboard/app/brain/`, `apps/dashboard/app/life/`, `apps/dashboard/app/studio/`, `apps/dashboard/app/command/`. Career directory populated with career skills.

- [ ] **Step 3: Verify new hub structure**

```bash
ls apps/dashboard/app/ | grep -E '^(brain|career|life|studio|command)$'
```

Expected: All 5 directories present.

- [ ] **Step 4: Verify mount markers**

```bash
find apps/dashboard/app/brain apps/dashboard/app/life apps/dashboard/app/studio apps/dashboard/app/command -name '.plugin-mount' -o -name '.augur-mounted' | head -20
```

Expected: Mount markers in each skill subdirectory.

- [ ] **Step 5: Commit**

```bash
git add -A apps/dashboard/app/
git commit -m "refactor: delete old hubs, mount skills to new 5-app structure"
```

---

### Task 5: Write consolidated tab pages — Brain app

**Files:**
- Modify: `.claude/skills/knowledge/augur/dashboard/page.tsx` — Memory tab (host)
- Modify: `.claude/skills/reading-list/augur/dashboard/page.tsx` — Library tab (host)
- Modify: `.claude/skills/ai_bridge/augur/dashboard/page.tsx` — Agents tab (host)

Each consolidated page combines sections from multiple skills. Follow the existing pattern: `'use client'`, `useCachedFetch`, `GlassCard`, Lucide icons. Sections use a CSS grid with `grid-cols-1 lg:grid-cols-2` for half-width layout.

- [ ] **Step 1: Read existing pages for knowledge, reading-list, ai_bridge**

Read the current source pages to understand their existing data fetching and MCP tool calls. Preserve all working functionality.

- [ ] **Step 2: Rewrite knowledge page as Brain > Memory**

The Memory tab combines: knowledge graph, semantic search, memory timeline, RAG index status. Keep all existing knowledge page functionality. Add search bar and RAG status sections.

The page should render:
- Full-width search bar at top (calls search MCP tool)
- Half-width knowledge graph overview (existing)
- Half-width memory timeline (existing)
- Full-width RAG index status (calls rag-status MCP tool if available)

- [ ] **Step 3: Rewrite reading-list page as Brain > Library**

The Library tab combines: reading queue + book notes. Keep existing reading-list functionality. Add a books section below.

- [ ] **Step 4: Rewrite ai_bridge page as Brain > Agents**

The Agents tab combines: connected agents + cross-client sync. Keep existing ai_bridge functionality. Add sync status section from dev-sync.

- [ ] **Step 5: Verify pages render**

Run: `cd apps/dashboard && npm run mount-plugins && npm run dev`
Navigate to `/brain/knowledge`, `/brain/reading-list`, `/brain/ai_bridge`. Verify pages load without errors.

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/knowledge/augur/dashboard/ .claude/skills/reading-list/augur/dashboard/ .claude/skills/ai_bridge/augur/dashboard/
git commit -m "feat(brain): write consolidated tab pages for Memory, Library, Agents"
```

---

### Task 6: Write consolidated tab pages — Career app

**Files:**
- Modify: `.claude/skills/career/augur/dashboard/page.tsx` — Pipeline tab (host)
- Modify: `.claude/skills/venture-augur/augur/dashboard/page.tsx` — Venture tab (host)

- [ ] **Step 1: Read existing career and venture-augur pages**
- [ ] **Step 2: Rewrite career page as Career > Pipeline**

Combine: job search kanban, interview prep, resume/STAR, skills growth tracker. Keep existing career functionality. Add growth skill sections.

- [ ] **Step 3: Rewrite venture-augur page as Career > Venture**

Combine: business strategy, project portfolio, competition/market, content/social. Keep existing venture-augur functionality. Add project-dev sections.

- [ ] **Step 4: Verify pages render at `/career/career` and `/career/venture-augur`**
- [ ] **Step 5: Commit**

```bash
git add .claude/skills/career/augur/dashboard/ .claude/skills/venture-augur/augur/dashboard/
git commit -m "feat(career): write consolidated tab pages for Pipeline, Venture"
```

---

### Task 7: Write consolidated tab pages — Life app

**Files:**
- Modify: `.claude/skills/attention/augur/dashboard/page.tsx` — Dashboard tab (host)
- Modify: `.claude/skills/home-automation/augur/dashboard/page.tsx` — Home tab (host)
- Keep: `.claude/skills/wealth/augur/dashboard/page.tsx` — Wealth tab (standalone, no rewrite needed)

- [ ] **Step 1: Read existing attention, home-automation, wealth pages**
- [ ] **Step 2: Rewrite attention page as Life > Dashboard**

Combine: unified inbox/triage, priority matrix (eisenhower), calendar/reminders (apple), notes. Keep existing attention functionality. Add eisenhower and apple sections.

- [ ] **Step 3: Rewrite home-automation page as Life > Home**

Combine: smart home controls, wellness/habits (lifestyle), files/documents (file-manager). Keep existing home-automation functionality. Add lifestyle and file-manager sections.

- [ ] **Step 4: Verify Wealth page still renders at `/life/wealth`**
- [ ] **Step 5: Verify Dashboard and Home pages render**
- [ ] **Step 6: Commit**

```bash
git add .claude/skills/attention/augur/dashboard/ .claude/skills/home-automation/augur/dashboard/ .claude/skills/wealth/augur/dashboard/
git commit -m "feat(life): write consolidated tab pages for Dashboard, Home, Wealth"
```

---

### Task 8: Write consolidated tab pages — Studio app

**Files:**
- Modify: `.claude/skills/advisor/augur/dashboard/page.tsx` — Workbench tab (host)
- Modify: `.claude/skills/frontend/augur/dashboard/page.tsx` — Design tab (host)
- Modify: `.claude/skills/mcp-app-factory/augur/dashboard/page.tsx` — Factory tab (host)

- [ ] **Step 1: Read existing advisor, frontend, mcp-app-factory pages**
- [ ] **Step 2: Rewrite advisor page as Studio > Workbench**

Combine: code insights/analysis (advisor), dev tools/refactoring (developer), deploy/CI-CD (devops). Keep existing advisor functionality. Add developer and devops sections.

- [ ] **Step 3: Rewrite frontend page as Studio > Design**

Combine: UI design/components (frontend), page canvas builder (page-builder), preview/render (renderer). Keep existing frontend functionality.

- [ ] **Step 4: Rewrite mcp-app-factory page as Studio > Factory**

Combine: plugin builder (mcp-app-factory), quality/compliance (validator). Keep existing mcp-app-factory functionality. Add validator section.

- [ ] **Step 5: Verify pages render at `/studio/advisor`, `/studio/frontend`, `/studio/mcp-app-factory`**
- [ ] **Step 6: Commit**

```bash
git add .claude/skills/advisor/augur/dashboard/ .claude/skills/frontend/augur/dashboard/ .claude/skills/mcp-app-factory/augur/dashboard/
git commit -m "feat(studio): write consolidated tab pages for Workbench, Design, Factory"
```

---

### Task 9: Write consolidated tab pages — Command app

**Files:**
- Modify: `.claude/skills/daemon/augur/dashboard/page.tsx` — Monitor tab (host)
- Modify: `.claude/skills/updater/augur/dashboard/page.tsx` — System tab (host)

- [ ] **Step 1: Read existing daemon and updater pages**
- [ ] **Step 2: Rewrite daemon page as Command > Monitor**

Combine: system health dashboard (observe), background services (daemon), self-healing log (ops-daemon), MCP status. Keep existing daemon functionality. Add observe and ops-daemon sections.

- [ ] **Step 3: Rewrite updater page as Command > System**

Combine: version/updates (updater), workflow pipelines (workflows), system cleanup. Keep existing updater functionality. Add workflows section.

- [ ] **Step 4: Verify pages render at `/command/daemon` and `/command/updater`**
- [ ] **Step 5: Commit**

```bash
git add .claude/skills/daemon/augur/dashboard/ .claude/skills/updater/augur/dashboard/
git commit -m "feat(command): write consolidated tab pages for Monitor, System"
```

---

### Task 10: Update tab contributions for correct tab labels

**Files:**
- Modify: 13 skill SKILL.md files — the tab host skills need `contributions.pages` with correct tab labels

Each host skill's `x-augur-config.contributions.pages` must declare the tab with a user-facing title matching the consolidated tab name.

- [ ] **Step 1: Update each host skill's contributions.pages**

For each host skill, ensure `contributions.pages` has:
```yaml
contributions:
  pages:
    - id: <tab-name>  # e.g., "memory", "pipeline", "monitor"
      title: <Tab Title>  # e.g., "Memory", "Pipeline", "Monitor"
      icon: <IconName>
      order: <1-3>
      page_type: custom
```

Host skills and their tab titles:
| Skill | Tab ID | Tab Title | Icon | Order |
|-------|--------|-----------|------|-------|
| knowledge | memory | Memory | Brain | 1 |
| reading-list | library | Library | BookOpen | 2 |
| ai_bridge | agents | Agents | Bot | 3 |
| career | pipeline | Pipeline | Kanban | 1 |
| venture-augur | venture | Venture | Rocket | 2 |
| wealth | wealth | Wealth | DollarSign | 1 |
| attention | dashboard | Dashboard | LayoutDashboard | 2 |
| home-automation | home | Home | Home | 3 |
| advisor | workbench | Workbench | Wrench | 1 |
| frontend | design | Design | Palette | 2 |
| mcp-app-factory | factory | Factory | Factory | 3 |
| daemon | monitor | Monitor | Activity | 1 |
| updater | system | System | Settings | 2 |

- [ ] **Step 2: Remove contributions.pages from non-host skills that were merged**

Skills whose pages were merged into a host should have their `contributions.pages` removed or set to `page_type: auto` so they don't get mounted as separate tabs.

Affected skills: growth, books, dev-sync, project-dev, eisenhower, apple, lifestyle, file-manager, developer, devops, page-builder, renderer, validator, observe, ops-daemon, workflows.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/*/SKILL.md
git commit -m "feat: update tab contributions for consolidated page labels"
```

---

### Task 11: Full rebuild and verification

- [ ] **Step 1: Run mount-plugins**

```bash
cd ~/Projects/Augur/apps/dashboard && npm run mount-plugins
```

- [ ] **Step 2: Verify hub registry**

```bash
cat config/dashboard/generated/hub_registry.yaml | head -30
```

Expected: 5 hubs listed (brain, career, life, studio, command)

- [ ] **Step 3: Build dashboard**

```bash
cd ~/Projects/Augur/apps/dashboard && npm run build
```

Expected: Build succeeds with no errors

- [ ] **Step 4: Run dev server and verify all 13 tabs**

```bash
npm run dev
```

Navigate to each tab and verify it loads:
- `/brain/knowledge`, `/brain/reading-list`, `/brain/ai_bridge`
- `/career/career`, `/career/venture-augur`
- `/life/wealth`, `/life/attention`, `/life/home-automation`
- `/studio/advisor`, `/studio/frontend`, `/studio/mcp-app-factory`
- `/command/daemon`, `/command/updater`

- [ ] **Step 5: Verify sidebar shows only 5 apps**

Check that only Brain, Career, Life, Studio, Command appear in the sidebar. No old hubs visible.

- [ ] **Step 6: Verify hidden client pages are accessible**

Navigate to `/hidden/client-ai-consulting`, `/hidden/client-smb-design`, `/hidden/client-terminal-automation`. Should render but not appear in sidebar.

- [ ] **Step 7: Commit any fixes**

```bash
git add -A && git commit -m "fix: resolve build/mount issues from hub restructuring"
```

---

### Task 12: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update the hub list in CLAUDE.md**

Replace the current hub list:
```
**Apps** (sidebar label, internally "hubs"): 5 apps: brain, career, command, life, studio
```

Also update any references to the old 15 hubs throughout the file.

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md hub list to 5-app taxonomy"
```
