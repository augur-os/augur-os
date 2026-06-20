# Ideas Vault Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate ~70 ideas from 5+ scattered vault files into 3 canonical YAML+markdown idea files, merge 7 fragmented plan files into 3, deduplicate, fix grammar, and enable Apple sync.

**Architecture:** Pure data migration in `get_vault_dir()/`. Read all source files, classify each idea into the correct target file/category, write 3 idea files + 3 merged plan files, verify counts, then delete originals.

**Tech Stack:** Vault markdown files with YAML frontmatter (ADR-404). No code changes.

**Spec:** `docs/superpowers/specs/2026-03-19-ideas-vault-cleanup-design.md`

---

## File Map

### Files to CREATE

| File | Purpose |
|------|---------|
| `get_vault_dir()/augur-career/venture-augur/ideas/ideas.md` | Canonical venture/startup ideas |
| `get_vault_dir()/augur-life/finance/ideas/ideas.md` | Canonical finance/investment ideas |
| `get_vault_dir()/augur-life/lifestyle/ideas/ideas.md` | Canonical lifestyle/personal ideas (replaces ideas.yaml) |
| `get_vault_dir()/augur-career/venture-augur/planning/ai-chef.md` | Merged AI Chef plan (3->1) |
| `get_vault_dir()/augur-career/venture-augur/planning/moneymind.md` | Merged MoneyMind/Firefly plan (3->1) |

### Files to MOVE

| From | To |
|------|----|
| `get_vault_dir()/augur-career/venture-augur/knowledge/startups/next-sdk.md` | `get_vault_dir()/augur-career/venture-augur/planning/next-sdk.md` |

### Files to DELETE (after migration verified)

| File | Reason |
|------|--------|
| `augur-career/growth/notes/notion-priority-dashboard-start-ups.md` | Ideas migrated to 3 idea files |
| `augur-life/finance/notes/notion-priority-dashboard-businesses.md` | Ideas migrated to finance ideas |
| `augur-life/lifestyle/ideas/ideas.yaml` | Replaced by ideas.md |
| `augur-career/venture-augur/planning/killer-dashboard-ideas.md` | Ideas extracted to idea files |
| `augur-career/venture-augur/planning/life-verticals-dashboard-ideas.md` | Ideas extracted to idea files |
| `augur-career/venture-augur/planning/ai-chef-plan.md` | Merged into ai-chef.md |
| `augur-career/venture-augur/planning/ai-chef-mealie-evaluation.md` | Merged into ai-chef.md |
| `augur-career/venture-augur/planning/ai-chef-implementation-plan.md` | Merged into ai-chef.md |
| `augur-career/venture-augur/planning/firefly-ai-dashboard-plan.md` | Merged into moneymind.md |
| `augur-career/venture-augur/planning/firefly-dashboard-sprint-plan.md` | Merged into moneymind.md |
| `augur-career/venture-augur/planning/firefly-ai-assistant-architecture.md` | Merged into moneymind.md |

---

## Task 1: Create target directories and snapshot source files

**Files:**
- Create: `get_vault_dir()/augur-career/venture-augur/ideas/` (directory)
- Create: `get_vault_dir()/augur-life/finance/ideas/` (directory)

- [ ] **Step 1: Create target directories**

```bash
mkdir -p get_vault_dir()/augur-career/venture-augur/ideas
mkdir -p get_vault_dir()/augur-life/finance/ideas
```

- [ ] **Step 2: Count ideas in each source file for verification**

```bash
# Count checklist items in startups file (expect ~61)
grep -c '^\- \[' get_vault_dir()/augur-career/growth/notes/notion-priority-dashboard-start-ups.md

# Count items in businesses file (expect ~5)
grep -c '^\- \[' get_vault_dir()/augur-life/finance/notes/notion-priority-dashboard-businesses.md

# Count items in lifestyle ideas (expect 2, 1 duplicate)
grep -c '^-' get_vault_dir()/augur-life/lifestyle/ideas/ideas.yaml

# Count ideas in killer-dashboard-ideas (expect ~8 named ideas + 3 tier-2)
grep -c '^###' get_vault_dir()/augur-career/venture-augur/planning/killer-dashboard-ideas.md

# Count ideas in life-verticals (expect ~11 named ideas)
grep -c '^###' get_vault_dir()/augur-career/venture-augur/planning/life-verticals-dashboard-ideas.md

# Count revenue streams in runway.yaml (expect 6)
grep -c 'name:' get_vault_dir()/augur-career/venture-augur/financials/runway.yaml
```

Record totals. After migration, the sum across the 3 target files must equal or exceed these counts (minus duplicates).

- [ ] **Step 3: Commit checkpoint**

```bash
cd get_vault_dir() && git add -A && git commit -m "chore: pre-cleanup snapshot — ideas vault cleanup"
```

---

## Task 2: Write venture-augur ideas file

**Files:**
- Create: `get_vault_dir()/augur-career/venture-augur/ideas/ideas.md`

**Sources to read:**
- `augur-career/growth/notes/notion-priority-dashboard-start-ups.md` — extract startup/product/hardware/service/media ideas
- `augur-career/venture-augur/planning/killer-dashboard-ideas.md` — extract all dashboard wrapper ideas
- `augur-career/venture-augur/planning/life-verticals-dashboard-ideas.md` — extract product ideas that are startups/ventures

- [ ] **Step 1: Read all 3 source files**

Read each source file completely. For each idea, classify into one of the 4 sub-categories:
- **Software Products**: AI tools, dashboard wrappers, SaaS, SDK, workflow tools
- **Hardware & Robotics**: physical products, robots, IoT, wearables
- **Services & Platforms**: marketplaces, service businesses, consulting platforms
- **Media & Entertainment**: creative, experiential, content, VR

- [ ] **Step 2: Write the venture ideas file**

Write `get_vault_dir()/augur-career/venture-augur/ideas/ideas.md` with:
- YAML frontmatter exactly as specified in the spec
- Each idea formatted as `- **Name** — Description.`
- Ideas with existing plans get `plan` links
- No `- [ ]` checkbox syntax
- No quotes around idea names
- Grammar and spelling fixed
- Duplicates removed (keep the richer description)

Cross-reference links needed:
- AI Chef -> `plan`
- MoneyMind/CashFlow AI -> `plan`
- NextProject SDK -> `plan`
- lnav, Glances, Restic, Lazydocker, bandwhich — no plan files, just ideas

- [ ] **Step 3: Verify idea count**

Count bullet items in the new file. Should be ~50-55 (startups minus finance/lifestyle items, minus duplicates, plus dashboard ideas and life-vertical ideas that are ventures).

- [ ] **Step 4: Commit**

```bash
cd get_vault_dir() && git add augur-career/venture-augur/ideas/ideas.md && git commit -m "feat: create canonical venture ideas file — ideas vault cleanup"
```

---

## Task 3: Write finance ideas file

**Files:**
- Create: `get_vault_dir()/augur-life/finance/ideas/ideas.md`

**Sources to read:**
- `augur-life/finance/notes/notion-priority-dashboard-businesses.md` — all 5 items
- `augur-career/venture-augur/financials/runway.yaml` — copy 6 revenue stream names
- `augur-career/growth/notes/notion-priority-dashboard-start-ups.md` — extract any finance-specific ideas (CryptoSurplus, CryptoPrint)

- [ ] **Step 1: Read source files and classify**

Classify into:
- **Investments & Acquisitions**: real estate, business acquisitions, equity deals
- **Revenue Streams**: Augur OS monetization channels (from runway.yaml)
- **Financial Tools**: indexes, crypto, prediction tools

- [ ] **Step 2: Write the finance ideas file**

Write `get_vault_dir()/augur-life/finance/ideas/ideas.md` with:
- YAML frontmatter exactly as specified in the spec
- Format: `- **Name** — Description.`
- Grammar fixed, no checkbox syntax

Expected ideas (~13):
- From businesses.md: acquire SMBs, bring-your-API-key model, hotel in Cyprus, equity-for-compute, bubble prediction index
- From runway.yaml: IDE affiliates, AI course, app store, cloud backup, custom work, skills marketplace
- From startups.md: CryptoSurplus, CryptoPrint (crypto/finance related)

- [ ] **Step 3: Verify idea count**

Count bullet items. Should be ~13.

- [ ] **Step 4: Commit**

```bash
cd get_vault_dir() && git add augur-life/finance/ideas/ideas.md && git commit -m "feat: create canonical finance ideas file — ideas vault cleanup"
```

---

## Task 4: Write lifestyle ideas file

**Files:**
- Create: `get_vault_dir()/augur-life/lifestyle/ideas/ideas.md` (replaces ideas.yaml in same dir)

**Sources to read:**
- `augur-life/lifestyle/ideas/ideas.yaml` — 1 unique idea (recipe scaling)
- `augur-career/growth/notes/notion-priority-dashboard-start-ups.md` — extract home/living/health/urban ideas
- `augur-career/venture-augur/planning/life-verticals-dashboard-ideas.md` — extract personal-use ideas (not venture-scale)

- [ ] **Step 1: Read source files and classify**

Classify into:
- **Home & Living**: household products, smart home, kitchen, furniture, cleaning
- **Health & Wellness**: dental, fitness, nutrition, cooling, medical
- **Urban & Transport**: city infrastructure, transport, accessibility, safety, parking

Note: Many life-verticals ideas (Mealie, Firefly, LubeLogger) are startup-grade and belong in venture-augur. Only extract personal-use ideas for lifestyle (e.g., plant care, pet care, home inventory, standing pool, toaster design).

- [ ] **Step 2: Write the lifestyle ideas file**

Write `get_vault_dir()/augur-life/lifestyle/ideas/ideas.md` with:
- YAML frontmatter exactly as specified in the spec
- Format: `- **Name** — Description.`
- Remove the duplicate recipe scaling idea (keep one)
- Grammar fixed

- [ ] **Step 3: Verify idea count**

Count bullet items. Should be ~15-20 (home/personal ideas from startups list + personal items from life-verticals).

- [ ] **Step 4: Commit**

```bash
cd get_vault_dir() && git add augur-life/lifestyle/ideas/ideas.md && git commit -m "feat: create canonical lifestyle ideas file — ideas vault cleanup"
```

---

## Task 5: Merge AI Chef plan files (3->1)

**Files:**
- Create: `get_vault_dir()/augur-career/venture-augur/planning/ai-chef.md`
- Read: `get_vault_dir()/augur-career/venture-augur/planning/ai-chef-plan.md`
- Read: `get_vault_dir()/augur-career/venture-augur/planning/ai-chef-mealie-evaluation.md`
- Read: `get_vault_dir()/augur-career/venture-augur/planning/ai-chef-implementation-plan.md`

- [ ] **Step 1: Read all 3 AI Chef source files**

- [ ] **Step 2: Write merged file**

Write `ai-chef.md` with:
```yaml
---
title: "AI Chef — Product Plan"
skill: venture-augur
type: plan
created: "2026-03-19"
updated: "2026-03-19"
tags: [plan, product, mealie, ai-chef]
---
```

Sections:
1. **Overview** — from ai-chef-plan.md (goals, vision, value prop)
2. **Mealie Evaluation** — from ai-chef-mealie-evaluation.md (tool analysis, API assessment)
3. **Architecture** — from ai-chef-plan.md (system design, data flow)
4. **Implementation Plan** — from ai-chef-implementation-plan.md (sprint plan, milestones)

Preserve all content. Fix formatting to consistent markdown. Remove redundant headers between files.

- [ ] **Step 3: Commit**

```bash
cd get_vault_dir() && git add augur-career/venture-augur/planning/ai-chef.md && git commit -m "feat: merge 3 AI Chef plan files into one — ideas vault cleanup"
```

---

## Task 6: Merge MoneyMind/Firefly plan files (3->1)

**Files:**
- Create: `get_vault_dir()/augur-career/venture-augur/planning/moneymind.md`
- Read: `get_vault_dir()/augur-career/venture-augur/planning/firefly-ai-dashboard-plan.md`
- Read: `get_vault_dir()/augur-career/venture-augur/planning/firefly-dashboard-sprint-plan.md`
- Read: `get_vault_dir()/augur-career/venture-augur/planning/firefly-ai-assistant-architecture.md`

- [ ] **Step 1: Read all 3 Firefly source files**

- [ ] **Step 2: Write merged file**

Write `moneymind.md` with:
```yaml
---
title: "MoneyMind — Product Plan"
skill: venture-augur
type: plan
created: "2026-03-19"
updated: "2026-03-19"
tags: [plan, product, firefly-iii, moneymind, finance]
---
```

Sections:
1. **Overview** — from firefly-ai-dashboard-plan.md (goals, vision, three-pillar architecture)
2. **Architecture** — from firefly-ai-assistant-architecture.md (Watcher/Thinker/Talker, data flow)
3. **Sprint Plan** — from firefly-dashboard-sprint-plan.md (milestones, tasks)

Preserve all content. Fix formatting. Remove redundant intros.

- [ ] **Step 3: Commit**

```bash
cd get_vault_dir() && git add augur-career/venture-augur/planning/moneymind.md && git commit -m "feat: merge 3 Firefly plan files into MoneyMind — ideas vault cleanup"
```

---

## Task 7: Move NextProject SDK plan file

**Files:**
- Move: `get_vault_dir()/augur-career/venture-augur/knowledge/startups/next-sdk.md` -> `get_vault_dir()/augur-career/venture-augur/planning/next-sdk.md`

- [ ] **Step 1: Move the file**

```bash
mv get_vault_dir()/augur-career/venture-augur/knowledge/startups/next-sdk.md get_vault_dir()/augur-career/venture-augur/planning/next-sdk.md
```

- [ ] **Step 2: Update the startups-overview.md reference**

Edit `get_vault_dir()/augur-career/venture-augur/knowledge/startups/startups-overview.md` to update the link:
- Old: `NeXT SDK`
- New: `NeXT SDK`

- [ ] **Step 3: Commit**

```bash
cd get_vault_dir() && git add -A && git commit -m "feat: move next-sdk.md to planning/ — ideas vault cleanup"
```

---

## Task 8: Delete source files and final verification

**Files to delete:** All 11 source files listed in the DELETE table above.

- [ ] **Step 1: Final idea count verification**

```bash
# Count total ideas across all 3 new files
grep -c '^\- \*\*' get_vault_dir()/augur-career/venture-augur/ideas/ideas.md
grep -c '^\- \*\*' get_vault_dir()/augur-life/finance/ideas/ideas.md
grep -c '^\- \*\*' get_vault_dir()/augur-life/lifestyle/ideas/ideas.md
```

Sum should be ~70+ (original count minus duplicates). If the count is significantly lower than expected, STOP and investigate before deleting.

- [ ] **Step 2: Verify plan files are complete**

```bash
# Verify merged plans exist and have content
wc -l get_vault_dir()/augur-career/venture-augur/planning/ai-chef.md
wc -l get_vault_dir()/augur-career/venture-augur/planning/moneymind.md
wc -l get_vault_dir()/augur-career/venture-augur/planning/next-sdk.md
```

Each should have substantial content (100+ lines for merged files).

- [ ] **Step 3: Delete source files**

```bash
cd get_vault_dir()

# Idea source files
rm augur-career/growth/notes/notion-priority-dashboard-start-ups.md
rm augur-life/finance/notes/notion-priority-dashboard-businesses.md
rm augur-life/lifestyle/ideas/ideas.yaml

# Idea-list files (absorbed into idea files)
rm augur-career/venture-augur/planning/killer-dashboard-ideas.md
rm augur-career/venture-augur/planning/life-verticals-dashboard-ideas.md

# AI Chef fragments
rm augur-career/venture-augur/planning/ai-chef-plan.md
rm augur-career/venture-augur/planning/ai-chef-mealie-evaluation.md
rm augur-career/venture-augur/planning/ai-chef-implementation-plan.md

# Firefly/MoneyMind fragments
rm augur-career/venture-augur/planning/firefly-ai-dashboard-plan.md
rm augur-career/venture-augur/planning/firefly-dashboard-sprint-plan.md
rm augur-career/venture-augur/planning/firefly-ai-assistant-architecture.md
```

- [ ] **Step 4: Verify no broken references**

```bash
# Check for any remaining references to deleted files
grep -r "ai-chef-plan\|ai-chef-mealie\|ai-chef-implementation\|firefly-ai-dashboard\|firefly-dashboard-sprint\|firefly-ai-assistant\|killer-dashboard-ideas\|life-verticals-dashboard\|notion-priority-dashboard-start-ups\|notion-priority-dashboard-businesses" get_vault_dir()/ --include="*.md" --include="*.yaml" -l
```

If any files reference deleted sources, update those references to point to the new canonical files.

- [ ] **Step 5: Commit**

```bash
cd get_vault_dir() && git add -A && git commit -m "chore: delete migrated source files — ideas vault cleanup complete"
```

---

## Summary

| Task | What | Creates/Modifies |
|------|------|-----------------|
| 1 | Setup + snapshot | Directories, git checkpoint |
| 2 | Venture ideas | `venture-augur/ideas/ideas.md` (~50-55 ideas) |
| 3 | Finance ideas | `finance/ideas/ideas.md` (~13 ideas) |
| 4 | Lifestyle ideas | `lifestyle/ideas/ideas.md` (~15-20 ideas) |
| 5 | Merge AI Chef | `planning/ai-chef.md` (3->1) |
| 6 | Merge MoneyMind | `planning/moneymind.md` (3->1) |
| 7 | Move NextSDK | `planning/next-sdk.md` (move) |
| 8 | Delete + verify | Remove 11 source files |

**Total: 8 tasks, ~6 new files, ~11 deleted files**
