# Launch Trust And Agent Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix seven launch trust and agent hardening issues one by one with truthful public claims, smaller global instructions, code-enforced dashboard/page gates, and safer worktree workflows.

**Architecture:** Implement this as seven independent slices with a focused commit after each verified checkpoint. Public claims are backed by tests or computed inventory, generated agent files are changed only through their source and sync generator, dashboard YAML rules move into page-health validation, and worktree safety moves into reusable script guards.

**Tech Stack:** Python 3.11+, pytest, Node.js for `create-augur`, Markdown docs, TypeScript dashboard mount scripts where needed, Bash/Python worktree scripts.

---

## Spec Reference

Design spec:

- `docs/superpowers/specs/2026-04-21-launch-trust-and-agent-hardening-design.md`

## File Structure

Create:

- `src/lib/launch_inventory.py` - computed inventory for live top-level skills and staged release skills.
- `tests/test_launch_trust_inventory.py` - public skill-count honesty tests.
- `tests/test_create_augur_install_copy.py` - install story and `create-augur` copy tests.
- `tests/test_demo_surface.py` - real demo asset/link tests.
- `tests/test_agent_instruction_burden.py` - global instruction size and workflow-detail relocation tests.
- `config/dashboard/README.md` - classification ledger for central dashboard config files.
- `tests/test_dashboard_config_classification.py` - config classification regression tests.
- `skills/platform-admin/scripts/worktree_guard.py` - reusable main-checkout branch guard.
- `skills/platform-admin/augur/tests/test_worktree_guard.py` - worktree guard unit tests.

Modify:

- `README.md` - public skill counts, install path, demo link.
- `~/Projects/Au-docs/venture-augur/website-working/more.html` - remove unsupported `200+` skill claims.
- `packages/create-augur/README.md` - clarify supported full setup and planned MCP/skills-only path.
- `packages/create-augur/index.js` - clarify help and next-step output.
- `docs/demo/README.md` - mark GIF recording state truthfully.
- `docs/agent-topics/agent-rules.md` - reduce global rules to cross-cutting principles.
- `docs/agent-topics/DASHBOARD.md` - move dashboard verification, wiring audit, and YAML page details here.
- `docs/agent-topics/WORKFLOWS.md` - move worktree and `/dev-merge` operational details here.
- `docs/agent-topics/SKILLS.md` - move skill schema and decentralization details here.
- `AGENTS.md`, `CODEX.md`, `CLAUDE.md`, `.gemini/GEMINI.md`, and other generated client surfaces - regenerate through `sync_agents`, do not hand-edit.
- `skills/loop-ops/scripts/page_health.py` - add YAML passive data-source diagnostics.
- `skills/loop-ops/augur/tests/test_page_health.py` - add YAML gate tests.
- `scripts/worktree_preflight.py` - wire the main-checkout branch guard into preflight.

## Task 1: Skill-Count Honesty

**Files:**

- Create: `src/lib/launch_inventory.py`
- Create: `tests/test_launch_trust_inventory.py`
- Modify: `README.md`
- Modify: `~/Projects/Au-docs/venture-augur/website-working/more.html`

- [ ] **Step 1: Write failing inventory and public-claim tests**

Create `tests/test_launch_trust_inventory.py`:

```python
from __future__ import annotations

from pathlib import Path

from src.lib.launch_inventory import count_launch_skills


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEBSITE_WORKING = Path.home() / "Projects" / "Au-docs" / "venture-augur" / "website-working"


def _public_texts() -> list[tuple[Path, str]]:
    paths = [
        PROJECT_ROOT / "README.md",
        WEBSITE_WORKING / "index.html",
        WEBSITE_WORKING / "more.html",
        WEBSITE_WORKING / "llms.txt",
    ]
    return [(path, path.read_text(encoding="utf-8")) for path in paths if path.exists()]


def test_launch_inventory_counts_top_level_live_and_staged_skills() -> None:
    inventory = count_launch_skills(PROJECT_ROOT)

    live_paths = sorted(
        path
        for path in (PROJECT_ROOT / "skills").iterdir()
        if path.is_dir() and (path / "SKILL.md").exists()
    )
    staged_paths = sorted((PROJECT_ROOT / "staging").glob("*/skills/*/SKILL.md"))

    assert inventory.live_top_level == len(live_paths)
    assert inventory.staged_total == len(staged_paths)
    assert inventory.live_top_level == 21
    assert inventory.staged_total == 30


def test_public_surfaces_do_not_claim_unproven_200_plus_skills() -> None:
    forbidden = [
        "200+ portable skills",
        "200+ skills, community skill packs",
        "200+ composable skills",
    ]

    failures: list[str] = []
    for path, text in _public_texts():
        for phrase in forbidden:
            if phrase in text:
                failures.append(f"{path}: {phrase}")

    assert not failures, "Unsupported public skill-count claims found: " + "; ".join(failures)


def test_readme_names_current_live_and_staged_skill_counts() -> None:
    inventory = count_launch_skills(PROJECT_ROOT)
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")

    assert f"{inventory.live_top_level} live MVP skills" in readme
    assert f"{inventory.staged_total} staged release skills" in readme
    assert "staged releases are not presented as live skills" in readme


def test_deep_dive_names_current_live_and_staged_skill_counts() -> None:
    more = WEBSITE_WORKING / "more.html"
    if not more.exists():
        return

    inventory = count_launch_skills(PROJECT_ROOT)
    text = more.read_text(encoding="utf-8")

    assert f"{inventory.live_top_level} live MVP skills" in text
    assert f"{inventory.staged_total} staged release skills" in text
```

- [ ] **Step 2: Run the tests and verify the expected failure**

Run:

```bash
pytest -q tests/test_launch_trust_inventory.py
```

Expected:

```text
ModuleNotFoundError: No module named 'src.lib.launch_inventory'
```

- [ ] **Step 3: Add the launch inventory helper**

Create `src/lib/launch_inventory.py`:

```python
"""Launch-scope inventory helpers for public trust surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LaunchSkillInventory:
    live_top_level: int
    staged_total: int
    staged_by_release: dict[str, int]


def count_launch_skills(project_root: Path) -> LaunchSkillInventory:
    """Count live top-level skills and staged release skills from the repo tree."""
    root = project_root.resolve()
    skills_dir = root / "skills"
    staging_dir = root / "staging"

    live_top_level = 0
    if skills_dir.exists():
        live_top_level = sum(
            1
            for child in skills_dir.iterdir()
            if child.is_dir() and (child / "SKILL.md").exists()
        )

    staged_by_release: dict[str, int] = {}
    if staging_dir.exists():
        for release_dir in sorted(path for path in staging_dir.iterdir() if path.is_dir()):
            count = len(list((release_dir / "skills").glob("*/SKILL.md")))
            if count:
                staged_by_release[release_dir.name] = count

    return LaunchSkillInventory(
        live_top_level=live_top_level,
        staged_total=sum(staged_by_release.values()),
        staged_by_release=staged_by_release,
    )
```

- [ ] **Step 4: Run tests and verify copy failures remain**

Run:

```bash
pytest -q tests/test_launch_trust_inventory.py
```

Expected:

```text
FAILED tests/test_launch_trust_inventory.py::test_public_surfaces_do_not_claim_unproven_200_plus_skills
FAILED tests/test_launch_trust_inventory.py::test_readme_names_current_live_and_staged_skill_counts
FAILED tests/test_launch_trust_inventory.py::test_deep_dive_names_current_live_and_staged_skill_counts
```

- [ ] **Step 5: Update README skill-count copy**

In `README.md`, replace the `## Release Staging` body with:

```markdown
`skills/` contains the live MVP tree. A fresh clone currently exposes 21 live MVP skills at the top level of `skills/`.

Future releases are staged under `staging/r1/`, `staging/r2/`, `staging/r3/`, `staging/r4/`, and `staging/later/`. The current staged tree contains 30 staged release skills. Staged releases are not presented as live skills until they are ported into `skills/` and verified.
```

- [ ] **Step 6: Update website deep-dive skill-count copy**

In `~/Projects/Au-docs/venture-augur/website-working/more.html`, replace:

```html
<td>200+ portable skills (open SKILL.md format)</td>
```

with:

```html
<td>21 live MVP skills and 30 staged release skills (open SKILL.md format)</td>
```

Then replace:

```html
<td>200+ skills, community skill packs, full dashboard</td>
```

with:

```html
<td>Live MVP skills, staged release skills, community skill packs, full dashboard</td>
```

- [ ] **Step 7: Run the focused verification**

Run:

```bash
pytest -q tests/test_launch_trust_inventory.py
```

Expected:

```text
4 passed
```

- [ ] **Step 8: Commit slice 1**

Run:

```bash
git add src/lib/launch_inventory.py tests/test_launch_trust_inventory.py README.md ~/Projects/Au-docs/venture-augur/website-working/more.html
git diff --cached --check
git commit -m "fix(docs): make launch skill counts truthful"
```

## Task 2: Install Friction And Zero-Dashboard Clarity

**Files:**

- Create: `tests/test_create_augur_install_copy.py`
- Modify: `README.md`
- Modify: `packages/create-augur/README.md`
- Modify: `packages/create-augur/index.js`

- [ ] **Step 1: Write failing install-copy tests**

Create `tests/test_create_augur_install_copy.py`:

```python
from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_readme_leads_with_create_augur_as_current_simplest_path() -> None:
    readme = _read("README.md")
    working = readme.split("## Working Locally", 1)[1].split("## Release Staging", 1)[0]

    assert "npx create-augur@latest my-brain" in working
    assert "repo-first full Augur workspace" in working
    assert "MCP/skills-only path" in working
    assert "planned" in working.lower()


def test_create_augur_readme_distinguishes_current_and_planned_paths() -> None:
    text = _read("packages/create-augur/README.md")

    assert "repo-first full Augur workspace" in text
    assert "installs Python and Node dependencies" in text
    assert "MCP/skills-only path is planned" in text
    assert "does not install a zero-dashboard runtime yet" in text


def test_create_augur_help_names_supported_setup() -> None:
    result = subprocess.run(
        ["node", "packages/create-augur/index.js", "--help"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Creates a repo-first full Augur workspace" in result.stdout
    assert "MCP/skills-only mode is planned" in result.stdout
```

- [ ] **Step 2: Run the tests and verify they fail on copy**

Run:

```bash
pytest -q tests/test_create_augur_install_copy.py
```

Expected:

```text
FAILED tests/test_create_augur_install_copy.py::test_readme_leads_with_create_augur_as_current_simplest_path
FAILED tests/test_create_augur_install_copy.py::test_create_augur_readme_distinguishes_current_and_planned_paths
FAILED tests/test_create_augur_install_copy.py::test_create_augur_help_names_supported_setup
```

- [ ] **Step 3: Update README install section**

In `README.md`, replace the first paragraph and command block under `## Working Locally` with:

```markdown
This repository is the source of truth for development and validation. The simplest current setup path is `create-augur`, which creates a repo-first full Augur workspace and installs the Python and Node dependency layers used by the MCP server and dashboard.

```bash
npx create-augur@latest my-brain
cd my-brain
pnpm --filter dashboard dev
```

The dashboard runs at [localhost:3000](http://localhost:3000).

Manual clone remains useful for contributors who want direct control over bootstrap:

```bash
git clone https://github.com/augur-os/augur-os.git
cd augur-os
corepack enable && pnpm install && uv sync
pnpm --filter dashboard dev
```

The MCP/skills-only path is planned but not claimed as a working public install path yet. Until that mode is implemented, use the full repo-first setup when you need the local MCP server, generated client surfaces, indexes, and dashboard.
```

- [ ] **Step 4: Update create-augur README copy**

Replace `packages/create-augur/README.md` with:

```markdown
# create-augur

Scaffold a repo-first full Augur workspace: local second-brain infrastructure for notes, documents, skills, MCP commands, and dashboard pages.

## Usage

```bash
npx create-augur@latest my-brain
cd my-brain
pnpm --filter dashboard dev
```

`create-augur` clones Augur, initializes a fresh git repository, installs Python dependencies with `uv` when available, and installs Node dependencies with `pnpm` when available.

This is the current full setup path. The MCP/skills-only path is planned, but `create-augur` does not install a zero-dashboard runtime yet.

## Links

- Website: https://augur.run
- GitHub: https://github.com/augur-os/augur-os
```

- [ ] **Step 5: Update create-augur CLI help and next-step output**

In `packages/create-augur/index.js`, update the help block:

```javascript
if (name === '--help' || name === '-h') {
  console.log('  Usage: npx create-augur [project-name]');
  console.log();
  console.log('  Creates a repo-first full Augur workspace in the specified directory.');
  console.log('  If no name is given, you will be prompted interactively.');
  console.log('  MCP/skills-only mode is planned; this command sets up the full repo and dashboard path.');
  console.log();
  process.exit(0);
}
```

Then replace the final dimmed next-step line with:

```javascript
console.log(dim('  This is the full repo-first setup. MCP/skills-only mode is planned, not installed by this scaffolder yet.'));
console.log(dim('  Then add your documents and notes so Augur can start compounding them.'));
```

- [ ] **Step 6: Run focused verification**

Run:

```bash
pytest -q tests/test_create_augur_install_copy.py
node packages/create-augur/index.js --help
```

Expected:

```text
3 passed
```

and the help output contains:

```text
Creates a repo-first full Augur workspace
MCP/skills-only mode is planned
```

- [ ] **Step 7: Commit slice 2**

Run:

```bash
git add README.md packages/create-augur/README.md packages/create-augur/index.js tests/test_create_augur_install_copy.py
git diff --cached --check
git commit -m "docs(install): clarify current Augur setup paths"
```

## Task 3: Demo Surface

**Files:**

- Create: `tests/test_demo_surface.py`
- Modify: `README.md`
- Modify: `docs/demo/README.md`

- [ ] **Step 1: Write failing demo-surface tests**

Create `tests/test_demo_surface.py`:

```python
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
DEMO_HTML = ROOT / "docs" / "demo" / "second-brain-report-demo.html"
DEMO_GIF = ROOT / "docs" / "demo" / "augur-demo.gif"
DEMO_README = ROOT / "docs" / "demo" / "README.md"


def test_readme_links_existing_demo_html() -> None:
    readme = README.read_text(encoding="utf-8")

    assert DEMO_HTML.exists()
    assert "docs/demo/second-brain-report-demo.html" in readme
    assert "self-contained second-brain report demo" in readme


def test_readme_does_not_reference_missing_demo_gif() -> None:
    readme = README.read_text(encoding="utf-8")

    if not DEMO_GIF.exists():
        assert "docs/demo/augur-demo.gif" not in readme
        assert "augur-demo.gif" not in readme


def test_demo_readme_truthfully_marks_gif_status() -> None:
    text = DEMO_README.read_text(encoding="utf-8")

    if DEMO_GIF.exists():
        assert "Status: GIF checked in" in text
    else:
        assert "Status: GIF not checked in yet" in text
        assert "Do not reference `docs/demo/augur-demo.gif` from public docs until the file exists." in text
```

- [ ] **Step 2: Run the tests and verify the expected failures**

Run:

```bash
pytest -q tests/test_demo_surface.py
```

Expected:

```text
FAILED tests/test_demo_surface.py::test_readme_links_existing_demo_html
FAILED tests/test_demo_surface.py::test_demo_readme_truthfully_marks_gif_status
```

- [ ] **Step 3: Add a real demo link to README**

In `README.md`, add this section after `## What You Can Do With Augur`:

```markdown
## Demo

Open the self-contained second-brain report demo to see the kind of inspectable output Augur can generate from a local knowledge base. It works directly in a browser with no server.

A short ingest-to-`/ask` GIF is still a launch asset to record; it is not referenced here until `docs/demo/augur-demo.gif` exists.
```

- [ ] **Step 4: Update demo README status**

In `docs/demo/README.md`, add this block after the opening paragraph:

```markdown
## Status

Status: GIF not checked in yet.

Do not reference `docs/demo/augur-demo.gif` from public docs until the file exists. The current checked-in demo asset is `second-brain-report-demo.html`.
```

- [ ] **Step 5: Run focused verification**

Run:

```bash
pytest -q tests/test_demo_surface.py
```

Expected:

```text
3 passed
```

- [ ] **Step 6: Commit slice 3**

Run:

```bash
git add README.md docs/demo/README.md tests/test_demo_surface.py
git diff --cached --check
git commit -m "docs(demo): expose real Augur demo surface"
```

## Task 4: Global Agent Instruction Shrink

**Files:**

- Create: `tests/test_agent_instruction_burden.py`
- Modify: `docs/agent-topics/agent-rules.md`
- Modify: `docs/agent-topics/DASHBOARD.md`
- Modify: `docs/agent-topics/WORKFLOWS.md`
- Modify: `docs/agent-topics/SKILLS.md`
- Regenerate: generated agent/client instruction surfaces through `sync_agents`

- [ ] **Step 1: Write failing instruction-burden tests**

Create `tests/test_agent_instruction_burden.py`:

```python
from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / "docs" / "agent-topics" / "agent-rules.md"
DASHBOARD = ROOT / "docs" / "agent-topics" / "DASHBOARD.md"
WORKFLOWS = ROOT / "docs" / "agent-topics" / "WORKFLOWS.md"
SKILLS = ROOT / "docs" / "agent-topics" / "SKILLS.md"


def _critical_rules(text: str) -> list[str]:
    section = text.split("## Critical Rules", 1)[1].split("## Topic Docs", 1)[0]
    return re.findall(r"^\d+\. \*\*", section, flags=re.MULTILINE)


def test_global_agent_rules_are_short_enough_for_every_session() -> None:
    text = RULES.read_text(encoding="utf-8")

    assert len(_critical_rules(text)) <= 24


def test_workflow_specific_dashboard_details_live_in_dashboard_topic() -> None:
    rules = RULES.read_text(encoding="utf-8")
    dashboard = DASHBOARD.read_text(encoding="utf-8")

    assert "wait 6+ seconds" not in rules
    assert "useMcpMutation/mcpCall" not in rules
    assert "YAML page migration must not regress UX" not in rules
    assert "Browser verification for dashboard fixes" in dashboard
    assert "YAML page migration safety" in dashboard


def test_worktree_cleanup_details_live_in_workflows_topic() -> None:
    rules = RULES.read_text(encoding="utf-8")
    workflows = WORKFLOWS.read_text(encoding="utf-8")

    assert "lsof -Fpc +D" not in rules
    assert "`/dev-merge` must salvage before discard" not in rules
    assert "Dev-merge salvage and cleanup" in workflows
    assert "active AI/client process" in workflows


def test_skill_schema_details_live_in_skills_topic() -> None:
    rules = RULES.read_text(encoding="utf-8")
    skills = SKILLS.read_text(encoding="utf-8")

    assert "Banned at root: `docs/`" not in rules
    assert "Skill folder schema" in skills
    assert "Agent Skills standard" in skills
```

- [ ] **Step 2: Run the tests and verify the expected failures**

Run:

```bash
pytest -q tests/test_agent_instruction_burden.py
```

Expected:

```text
FAILED tests/test_agent_instruction_burden.py::test_global_agent_rules_are_short_enough_for_every_session
FAILED tests/test_agent_instruction_burden.py::test_workflow_specific_dashboard_details_live_in_dashboard_topic
FAILED tests/test_agent_instruction_burden.py::test_worktree_cleanup_details_live_in_workflows_topic
FAILED tests/test_agent_instruction_burden.py::test_skill_schema_details_live_in_skills_topic
```

- [ ] **Step 3: Replace global critical rules with a shorter cross-cutting list**

In `docs/agent-topics/agent-rules.md`, replace the numbered list under `## Critical Rules (Apply Every Session)` with this list:

```markdown
1. **User-visible correctness first** - Fix the real user-facing problem. Do not hide broken data, empty pages, API failures, or scanner findings with fallbacks that leave the product worse.
2. **Plugin decentralization** - Skill-owned config, metadata, data, types, pages, and tools live inside `skills/{skill}/`. Central dashboard config must be classified in `config/dashboard/README.md`; unclassified central config is debt.
3. **Use path helpers** - Do not hardcode local paths. Use `src.config.paths` for project, vault, documents, runtime, logs, and cache locations.
4. **Keep data separated** - Code lives in `src/`, `skills/`, and repo `docs/`; config lives in `config/`; user data lives in the external vault; runtime state, logs, and cache live outside the repo.
5. **No workaround fixes** - No skipped tests, ignored type errors, disabled lint, empty fallback data, removed data sources, or assertion rewrites that bless broken behavior.
6. **Read folder README files before editing** - Directory README files carry local ownership and placement rules.
7. **Use TODO_ markers for discovered debt** - Mark real issues in place with `TODO_BUG`, `TODO_CLEANUP`, `TODO_OUTDATED`, or another scanned `TODO_` marker.
8. **Auto-loops must be honest** - A green loop with known coverage gaps should report evolution gaps, not claim complete coverage.
9. **Fix blockers before handoff** - If verification exposes a blocker, debug and fix it before declaring the task done.
10. **Commit verified checkpoints** - Make small focused commits after user-meaningful verified checkpoints and push when the workflow calls for it.
11. **Dashboard uses MCP, not direct local execution** - Dashboard data flows through MCP hooks and `POST /api/mcp/tool`; no direct LLM calls, direct Python scripts, `fs`, `spawn`, or `exec` in dashboard code.
12. **ADR is canonical for architectural decisions** - Architectural decisions go through ADRs in `get_adr_dir()`, with implementation plans used for execution detail.
13. **Hub ownership follows skill metadata** - A skill's `x-augur-hub` determines hub ownership. Do not add skill-specific hub data to central config.
14. **Prefer canonical cleanup over compatibility shims** - Do not add redirects, aliases, or compatibility stubs unless a governing ADR requires them.
15. **`--help` stops execution** - Slash commands invoked with `--help` display usage from the owning skill and do not execute the command.
16. **User-facing files use Markdown frontmatter** - User-facing ADRs, actions, vault files, and generated agent Markdown start with YAML frontmatter written through project frontmatter helpers.
17. **Generated agent Markdown keeps frontmatter at line 1** - Generated agent files with frontmatter must place any auto-generated comments after the closing frontmatter marker.
18. **Gemini runtime files are local-only generated output** - `.gemini/skills/` remains ignored and untracked; fix discovery through generators, `.gemini/unignore`, extension packaging, or settings.
19. **New workflows are agent-orchestrated MCP execution** - Agents own judgment and orchestration; MCP tools own atomic operations; docs/commands own policy; daemons schedule only.
20. **Plan before multi-step or architectural work** - For work with three or more implementation steps or architectural impact, write and approve a plan before building.
21. **Autonomous bug fixing** - When logs, tests, reproduction steps, or code can answer the question, fix the bug without asking avoidable clarifying questions.
22. **Check ADR history before destructive or architectural changes** - Before deleting files, retiring modules, or rewriting infrastructure functions, inspect recent git history and governing ADRs.
23. **Exhaustive migrations** - Renames, path migrations, config key moves, and URL changes require complete reference searches, including split path construction and tests.
24. **Main checkout and AI-client safety** - Main checkout branch work, worktree cleanup, and AI/client process ownership follow `WORKFLOWS.md`; never remove active session-owned worktrees or kill AI clients without explicit user authorization.
```

- [ ] **Step 4: Move dashboard workflow details into DASHBOARD topic**

Append this section to `docs/agent-topics/DASHBOARD.md`:

```markdown
## Browser verification for dashboard fixes

For dashboard fixes, curl responses, `next build`, and API success are not enough. Verify the actual page in a browser on the checkout that owns the dashboard port.

Required flow:

1. If Python MCP code changed, restart the MCP server through the documented lifecycle gate.
2. Identify which checkout owns the dashboard port before opening it.
3. Open the affected page in Chrome on that checkout's server.
4. Wait long enough for MCP-backed data to load.
5. Confirm real domain data appears, not only headings, skeletons, or empty states.
6. If browser automation is unavailable, ask the user to verify before claiming the page is fixed.

## Wiring audit for broken or empty pages

When a dashboard page is broken or empty, audit wiring before UI polish:

1. Grep `useMcpQuery`, `useMcpMutation`, and `useMcpPoll` tool names.
2. Compare them with actual `@mcp.tool(name=...)` registrations.
3. Confirm the component destructures the response shape the tool returns.
4. Confirm dashboard code does not bypass MCP with direct `fs`, `spawn`, `exec`, or Python script calls.
5. Check all custom pages in the affected hub, not only the first reported page.

## YAML page migration safety

Before replacing TSX with YAML config, inspect the TSX source. A page must stay TSX when it uses `useMcpMutation`, modal/toast workflows, more than two `useState` calls, or multiple local component imports that the YAML renderer cannot express.

Before adding YAML passive data blocks, verify the MCP tool is a read-only empty-args data source. Mutation tools, search tools, argument-required tools, and metadata-only status tools are not passive data sources.
```

- [ ] **Step 5: Move worktree and dev-merge details into WORKFLOWS topic**

Append this section to `docs/agent-topics/WORKFLOWS.md`:

```markdown
## Dev-merge salvage and cleanup

When `/dev-merge` finds leftover branches or worktrees, classify commits into `already_in_main`, `clean_salvage`, and `stale_or_conflicting`. Salvage merge-worthy commits before discarding leftovers. After salvage is proven, cleanup may remove leftover branches and worktrees only when no active AI/client process owns the path.

Before deleting an Augur worktree:

1. Repair Codex thread state with `skills/platform-admin/scripts/codex_thread_state.py`.
2. Check for active `codex`, `claude`, `gemini`, or Cowork ownership of the path.
3. Treat `lsof -Fpc +D <worktree>` stdout as meaningful even when `lsof` exits non-zero.
4. If active ownership exists, report PID, command, cwd, branch, and defer deletion.
5. Do not kill AI/client processes unless the user explicitly asks for that exact process kill.

## Main checkout branch safety

The main checkout must stay on `main`. If the primary checkout is on a non-main branch, stop branch work there and continue in a worktree or merge through `/dev-merge`.
```

- [ ] **Step 6: Move skill schema details into SKILLS topic**

Append this section to `docs/agent-topics/SKILLS.md`:

```markdown
## Skill folder schema

Skills follow the Agent Skills standard. Standard directories at skill root include `commands/`, `references/`, `scripts/`, `assets/`, `examples/`, `evals/`, and `modules/`.

Augur-specific content belongs in `augur/`, including `augur/dashboard/`, `augur/data/`, `augur/tests/`, and `augur/lib/`.

Allowed optional root files include `README.md`, `CHANGELOG.md`, `LICENSE*`, `pyproject.toml`, `package.json`, and `config.yaml` when they are skill-owned.

Banned at skill root:

- `docs/` - use `references/`
- `data/` - use `augur/data/` or `assets/`
- `lib/` - use `scripts/` or `augur/lib/`
- `augur/seed/` - use `assets/seeds/`

Dashboard files in `augur/dashboard/` may use `.tsx`, `.ts`, `.css`, `.js`, or `.jsx`.
```

- [ ] **Step 7: Regenerate agent surfaces**

Run:

```bash
AUGUR_SYNC_PROJECT_ROOT="$PWD" AUGUR_SYNC_REPO_LOCAL_ONLY=1 python3 -m skills.ai.scripts.sync_agents sync all
AUGUR_SYNC_PROJECT_ROOT="$PWD" AUGUR_SYNC_REPO_LOCAL_ONLY=1 python3 -m skills.ai.scripts.sync_agents check
```

Expected: `check` exits `0`.

- [ ] **Step 8: Run focused verification**

Run:

```bash
pytest -q tests/test_agent_instruction_burden.py tests/scripts/test_sync_output_policy.py
```

Expected:

```text
passed
```

- [ ] **Step 9: Commit slice 4**

Run:

```bash
git add docs/agent-topics/agent-rules.md docs/agent-topics/DASHBOARD.md docs/agent-topics/WORKFLOWS.md docs/agent-topics/SKILLS.md AGENTS.md CODEX.md CLAUDE.md .gemini/GEMINI.md tests/test_agent_instruction_burden.py
git diff --cached --check
git commit -m "docs(agents): shrink global instruction rules"
```

If `sync_agents` regenerates additional tracked surfaces, inspect them and include only generated outputs that are expected from the source-doc change.

## Task 5: Decentralization And Dashboard Config Truth

**Files:**

- Create: `config/dashboard/README.md`
- Create: `tests/test_dashboard_config_classification.py`
- Modify: `docs/agent-topics/agent-rules.md`
- Regenerate: generated agent/client instruction surfaces through `sync_agents`

- [ ] **Step 1: Write failing config classification tests**

Create `tests/test_dashboard_config_classification.py`:

```python
from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_CONFIG = ROOT / "config" / "dashboard"
README = DASHBOARD_CONFIG / "README.md"
RULES = ROOT / "docs" / "agent-topics" / "agent-rules.md"


def _classified_files() -> set[str]:
    if not README.exists():
        return set()
    text = README.read_text(encoding="utf-8")
    return set(re.findall(r"`([^`]+\.ya?ml)`", text))


def test_dashboard_yaml_files_are_classified() -> None:
    actual = {path.name for path in DASHBOARD_CONFIG.glob("*.yaml")}
    classified = _classified_files()

    assert actual <= classified


def test_dashboard_config_readme_marks_debt_and_exceptions() -> None:
    text = README.read_text(encoding="utf-8")

    assert "`app_mode.yaml`" in text
    assert "`cli_parser_profiles.yaml`" in text
    assert "`mcp_tools.yaml`" in text
    assert "migration debt" in text
    assert "legitimate central system config" in text
    assert "Do not add new central dashboard YAML without classifying it here." in text


def test_global_decentralization_rule_matches_config_reality() -> None:
    text = RULES.read_text(encoding="utf-8")

    assert "Central dashboard config must be classified in `config/dashboard/README.md`" in text
    assert "Centralized config files (`config/dashboard/*.yaml`) are technical debt, not a pattern to extend." not in text
```

- [ ] **Step 2: Run tests and verify expected failures**

Run:

```bash
pytest -q tests/test_dashboard_config_classification.py
```

Expected:

```text
FAILED tests/test_dashboard_config_classification.py::test_dashboard_yaml_files_are_classified
FAILED tests/test_dashboard_config_classification.py::test_dashboard_config_readme_marks_debt_and_exceptions
```

- [ ] **Step 3: Add dashboard config classification README**

Create `config/dashboard/README.md`:

```markdown
# config/dashboard/

Dashboard configuration that is still central must be classified here. Skill-owned dashboard metadata belongs in `skills/{skill}/SKILL.md` frontmatter or the owning skill's `augur/` tree.

Do not add new central dashboard YAML without classifying it here.

| File | Classification | Owner | Rule |
|------|----------------|-------|------|
| `app_mode.yaml` | migration debt | legacy app-mode and minimal-MCP behavior | Do not extend. Migrate skill-specific app/tool exposure to skill metadata or generated assembly before deleting this file. |
| `cli_parser_profiles.yaml` | legitimate central system config | operation-mode CLI stream parsing | Central because it describes external CLI protocol parsing, not skill-owned product metadata. |
| `mcp_tools.yaml` | migration debt | legacy MCP tool category/preset behavior | Do not extend. Prefer `x-augur-mcp-tools` frontmatter and generated tool assembly. Delete after consumers no longer read it. |

Generated files under `config/dashboard/generated/` are derived artifacts and are not hand-maintained policy sources.
```

- [ ] **Step 4: Confirm global rule already uses the classification wording**

Inspect `docs/agent-topics/agent-rules.md` and verify rule 2 contains:

```markdown
Central dashboard config must be classified in `config/dashboard/README.md`; unclassified central config is debt.
```

If the wording is missing, update rule 2 to include that sentence.

- [ ] **Step 5: Regenerate agent surfaces if rule text changed**

Run:

```bash
AUGUR_SYNC_PROJECT_ROOT="$PWD" AUGUR_SYNC_REPO_LOCAL_ONLY=1 python3 -m skills.ai.scripts.sync_agents sync all
AUGUR_SYNC_PROJECT_ROOT="$PWD" AUGUR_SYNC_REPO_LOCAL_ONLY=1 python3 -m skills.ai.scripts.sync_agents check
```

Expected: `check` exits `0`.

- [ ] **Step 6: Run focused verification**

Run:

```bash
pytest -q tests/test_dashboard_config_classification.py
```

Expected:

```text
3 passed
```

- [ ] **Step 7: Commit slice 5**

Run:

```bash
git add config/dashboard/README.md docs/agent-topics/agent-rules.md AGENTS.md CODEX.md CLAUDE.md .gemini/GEMINI.md tests/test_dashboard_config_classification.py
git diff --cached --check
git commit -m "docs(config): classify central dashboard config"
```

Include regenerated files only when `sync_agents` changed them.

## Task 6: YAML Page Gates

**Files:**

- Modify: `skills/loop-ops/scripts/page_health.py`
- Modify: `skills/loop-ops/augur/tests/test_page_health.py`
- Modify: `docs/agent-topics/DASHBOARD.md` if diagnostics need documentation wording

- [ ] **Step 1: Replace page-health import-only test with concrete YAML diagnostics tests**

Replace `skills/loop-ops/augur/tests/test_page_health.py` with:

```python
"""Tests for auto-page-health YAML data-source diagnostics."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

from src.lib.ops_protocol import OpsContext


PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


mod = importlib.import_module("page_health")


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _ctx(root: Path) -> OpsContext:
    return OpsContext(project_root=root, difficulty=0)


def test_page_health_importable() -> None:
    assert mod is not None


def test_scan_flags_mutation_tool_used_as_passive_yaml_source(tmp_path: Path) -> None:
    _write(
        tmp_path / "skills" / "career" / "augur" / "pages" / "pipeline.yaml",
        """
hub: career
route: pipeline
blocks:
  - type: data-table
    title: Jobs
    mcp_tool: update-career-job
""".strip()
        + "\n",
    )
    _write(
        tmp_path / "src" / "mcp" / "augur_mcp" / "domain" / "career.py",
        '@mcp.tool(name="update-career-job")\nasync def update():\n    pass\n',
    )

    result = mod.scan(_ctx(tmp_path))

    assert result.severity == "error"
    assert any(issue["action"] == "yaml-passive-mutation-tool" for issue in result.issues)


def test_scan_flags_search_tool_used_as_passive_yaml_source(tmp_path: Path) -> None:
    _write(
        tmp_path / "skills" / "knowledge" / "augur" / "pages" / "search.yaml",
        """
hub: brain
route: search
blocks:
  - type: data-list
    title: Search
    mcp_tool: search-knowledge
""".strip()
        + "\n",
    )
    _write(
        tmp_path / "src" / "mcp" / "augur_mcp" / "domain" / "knowledge.py",
        '@mcp.tool(name="search-knowledge")\nasync def search():\n    pass\n',
    )

    result = mod.scan(_ctx(tmp_path))

    assert result.severity == "error"
    assert any(issue["action"] == "yaml-passive-argument-required-tool" for issue in result.issues)


def test_metadata_only_response_detection() -> None:
    assert mod._is_metadata_only_response({"skill": "demo", "status": "ok", "version": "1.0.0"}) is True
    assert mod._is_metadata_only_response({"success": True, "data": [{"name": "real"}]}) is False
```

- [ ] **Step 2: Run tests and verify expected failures**

Run:

```bash
pytest -q skills/loop-ops/augur/tests/test_page_health.py
```

Expected:

```text
FAILED skills/loop-ops/augur/tests/test_page_health.py::test_scan_flags_mutation_tool_used_as_passive_yaml_source
FAILED skills/loop-ops/augur/tests/test_page_health.py::test_scan_flags_search_tool_used_as_passive_yaml_source
FAILED skills/loop-ops/augur/tests/test_page_health.py::test_metadata_only_response_detection
```

- [ ] **Step 3: Extend YAML tool extraction with block context**

In `skills/loop-ops/scripts/page_health.py`, add constants near the regex section:

```python
PASSIVE_YAML_BLOCK_TYPES = {
    "chart",
    "data-list",
    "data-table",
    "metrics-dashboard",
    "stat-grid",
    "timeline",
}
MUTATION_TOOL_PREFIXES = (
    "add-",
    "cancel-",
    "create-",
    "delete-",
    "execute-",
    "save-",
    "sync-",
    "update-",
)
ARGUMENT_REQUIRED_TOOL_PREFIXES = (
    "find-",
    "search-",
)
METADATA_ONLY_KEYS = {"skill", "status", "version"}
```

Then update `_extract_yaml_tools()` so direct block refs include `block_type`:

```python
        block_type = str(block.get("type", ""))
        if "mcp_tool" in block:
            tools.append({
                "tool": block["mcp_tool"],
                "source": "yaml",
                "page": page,
                "file": str(yaml_path),
                "block_type": block_type,
            })
```

For `sources` refs, include the parent block type:

```python
                tools.append({
                    "tool": source["mcp_tool"],
                    "source": "yaml",
                    "page": page,
                    "file": str(yaml_path),
                    "block_type": block_type,
                })
```

- [ ] **Step 4: Add YAML data-source diagnostic helpers**

Add these functions before `scan()` in `skills/loop-ops/scripts/page_health.py`:

```python
def _is_passive_yaml_ref(ref: dict) -> bool:
    return ref.get("source") == "yaml" and ref.get("block_type") in PASSIVE_YAML_BLOCK_TYPES


def _is_mutation_tool_name(tool_name: str) -> bool:
    return tool_name.startswith(MUTATION_TOOL_PREFIXES)


def _is_argument_required_tool_name(tool_name: str) -> bool:
    return tool_name.startswith(ARGUMENT_REQUIRED_TOOL_PREFIXES)


def _is_metadata_only_response(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    keys = {str(key) for key in payload.keys()}
    return bool(keys) and keys <= METADATA_ONLY_KEYS


def _yaml_data_source_issues(refs: list[dict]) -> list[dict]:
    issues: list[dict] = []
    for ref in refs:
        if not _is_passive_yaml_ref(ref):
            continue
        tool = str(ref["tool"])
        if _is_mutation_tool_name(tool):
            issues.append({
                "action": "yaml-passive-mutation-tool",
                "file": ref["file"],
                "tool": tool,
                "page": ref["page"],
                "source_type": ref["source"],
                "block_type": ref.get("block_type", ""),
                "error": "passive YAML data blocks cannot use mutation tools",
            })
        elif _is_argument_required_tool_name(tool):
            issues.append({
                "action": "yaml-passive-argument-required-tool",
                "file": ref["file"],
                "tool": tool,
                "page": ref["page"],
                "source_type": ref["source"],
                "block_type": ref.get("block_type", ""),
                "error": "passive YAML data blocks cannot use search/find tools that require arguments",
            })
    return issues
```

- [ ] **Step 5: Wire diagnostics into scan**

In `scan()`, after `all_refs` is populated and before unique tool registry checks, add:

```python
    yaml_data_issues = _yaml_data_source_issues(all_refs)
    if yaml_data_issues:
        return ScanResult(
            issues=yaml_data_issues,
            summary=f"{len(yaml_data_issues)} unsafe YAML passive data source reference(s)",
            severity="error",
        )
```

- [ ] **Step 6: Run focused verification**

Run:

```bash
pytest -q skills/loop-ops/augur/tests/test_page_health.py
pytest -q skills/loop-ops/augur/tests/test_mcp_health_audit.py
```

Expected:

```text
passed
```

- [ ] **Step 7: Commit slice 6**

Run:

```bash
git add skills/loop-ops/scripts/page_health.py skills/loop-ops/augur/tests/test_page_health.py
git diff --cached --check
git commit -m "fix(dashboard): gate unsafe YAML page data sources"
```

## Task 7: Worktree Operational Guards

**Files:**

- Create: `skills/platform-admin/scripts/worktree_guard.py`
- Create: `skills/platform-admin/augur/tests/test_worktree_guard.py`
- Modify: `scripts/worktree_preflight.py`

- [ ] **Step 1: Write failing worktree guard tests**

Create `skills/platform-admin/augur/tests/test_worktree_guard.py`:

```python
"""Tests for worktree branch safety guards."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
MODULE_PATH = SCRIPTS_DIR / "worktree_guard.py"


def _module():
    module_name = "platform_admin_worktree_guard_test"
    if module_name in sys.modules:
        return sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "Codex")
    _git(repo, "config", "user.email", "codex@example.com")
    (repo / "README.md").write_text("root\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "initial")
    return repo


def test_main_checkout_guard_passes_on_main(tmp_path: Path) -> None:
    mod = _module()
    repo = _init_repo(tmp_path)

    result = mod.check_main_checkout_branch(repo)

    assert result.ok is True
    assert result.branch == "main"
    assert result.is_main_checkout is True


def test_main_checkout_guard_blocks_non_main_primary_checkout(tmp_path: Path) -> None:
    mod = _module()
    repo = _init_repo(tmp_path)
    _git(repo, "checkout", "-b", "feature")

    result = mod.check_main_checkout_branch(repo)

    assert result.ok is False
    assert result.branch == "feature"
    assert result.is_main_checkout is True
    assert "main checkout is on feature" in result.message


def test_main_checkout_guard_allows_non_main_linked_worktree(tmp_path: Path) -> None:
    mod = _module()
    repo = _init_repo(tmp_path)
    worktree = tmp_path / "augur-wt-feature"
    _git(repo, "worktree", "add", str(worktree), "-b", "feature")

    result = mod.check_main_checkout_branch(worktree)

    assert result.ok is True
    assert result.branch == "feature"
    assert result.is_main_checkout is False
```

- [ ] **Step 2: Run tests and verify missing module failure**

Run:

```bash
pytest -q skills/platform-admin/augur/tests/test_worktree_guard.py
```

Expected:

```text
FileNotFoundError: worktree_guard.py
```

- [ ] **Step 3: Implement worktree guard module**

Create `skills/platform-admin/scripts/worktree_guard.py`:

```python
#!/usr/bin/env python3
"""Guards for Augur main-checkout and worktree branch safety."""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class MainCheckoutGuardResult:
    ok: bool
    repo_root: str
    main_checkout: str
    branch: str
    is_main_checkout: bool
    message: str


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


def _main_checkout(repo_root: Path) -> Path:
    output = _git(repo_root, "worktree", "list", "--porcelain")
    for line in output.splitlines():
        if line.startswith("worktree "):
            return Path(line.removeprefix("worktree ").strip()).resolve()
    return repo_root.resolve()


def _branch(repo_root: Path) -> str:
    branch = _git(repo_root, "rev-parse", "--abbrev-ref", "HEAD")
    return branch or "HEAD"


def check_main_checkout_branch(repo_root: Path, allowed_branch: str = "main") -> MainCheckoutGuardResult:
    root = repo_root.resolve()
    main_checkout = _main_checkout(root)
    branch = _branch(root)
    is_main_checkout = root == main_checkout
    ok = (not is_main_checkout) or branch == allowed_branch
    if ok:
        message = f"branch guard passed: root={root} branch={branch} main_checkout={main_checkout}"
    else:
        message = f"main checkout is on {branch}; continue branch work in a worktree or merge it into {allowed_branch}"
    return MainCheckoutGuardResult(
        ok=ok,
        repo_root=str(root),
        main_checkout=str(main_checkout),
        branch=branch,
        is_main_checkout=is_main_checkout,
        message=message,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".", help="Repo root or worktree path")
    parser.add_argument("--allowed-branch", default="main")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = check_main_checkout_branch(Path(args.repo_root), args.allowed_branch)
    if args.json:
        print(json.dumps(asdict(result), indent=2))
    else:
        print(result.message)
    return 0 if result.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run guard tests and verify they pass**

Run:

```bash
pytest -q skills/platform-admin/augur/tests/test_worktree_guard.py
```

Expected:

```text
3 passed
```

- [ ] **Step 5: Add preflight integration test**

Append this test to `tests/scripts/test_worktree_preflight.py`:

```python
def test_build_contract_checks_main_checkout_branch(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-b", "main"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Codex"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "codex@example.com"], check=True)
    (repo / "README.md").write_text("root\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "initial"], check=True)
    subprocess.run(["git", "-C", str(repo), "checkout", "-b", "feature"], check=True)

    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()

    import src.config.paths as config_paths

    monkeypatch.setattr(config_paths, "get_runtime_dir", lambda: runtime_dir)

    report = worktree_preflight.build_contract(repo, "shell", repair=False)

    check = next(item for item in report["checks"] if item["name"] == "main_checkout_branch")
    assert check["ok"] is False
    assert "main checkout is on feature" in check["details"]
    assert report["verify_passed"] is False
```

- [ ] **Step 6: Run preflight test and verify it fails**

Run:

```bash
pytest -q tests/scripts/test_worktree_preflight.py::test_build_contract_checks_main_checkout_branch
```

Expected:

```text
StopIteration
```

- [ ] **Step 7: Wire guard into worktree preflight**

In `scripts/worktree_preflight.py`, add `"main_checkout_branch"` to these profile requirements:

```python
PROFILE_REQUIREMENTS = {
    "worktree": {"runtime", "python", "ruff", "dashboard_deps", "sync_outputs"},
    "shell": {"runtime", "python", "main_checkout_branch"},
    "mcp": {"runtime", "python", "main_checkout_branch"},
    "dashboard": {"runtime", "python", "dashboard_deps", "main_checkout_branch"},
}
```

Then inside `build_contract()`, after `checks`, `repairs`, and `incidents` are initialized, add this dynamic import block:

```python
    if not is_worktree:
        guard_script = project_root / "skills" / "platform-admin" / "scripts" / "worktree_guard.py"
        if guard_script.exists():
            import importlib.util

            spec = importlib.util.spec_from_file_location("worktree_guard", guard_script)
            if spec is not None and spec.loader is not None:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                guard = module.check_main_checkout_branch(project_root)
                _check("main_checkout_branch", guard.ok, guard.message, checks)
            else:
                _check("main_checkout_branch", False, "worktree guard script could not be loaded", checks)
        else:
            _check("main_checkout_branch", True, "worktree guard script not present", checks)
```

- [ ] **Step 8: Run focused verification**

Run:

```bash
pytest -q skills/platform-admin/augur/tests/test_worktree_guard.py tests/scripts/test_worktree_preflight.py::test_build_contract_checks_main_checkout_branch
python3 skills/platform-admin/scripts/worktree_guard.py --repo-root "$PWD" --json
```

Expected:

```text
passed
```

and the JSON command exits `0` in this worktree because this checkout is not the primary main checkout.

- [ ] **Step 9: Commit slice 7**

Run:

```bash
git add skills/platform-admin/scripts/worktree_guard.py skills/platform-admin/augur/tests/test_worktree_guard.py scripts/worktree_preflight.py tests/scripts/test_worktree_preflight.py
git diff --cached --check
git commit -m "fix(worktree): guard main checkout branch drift"
```

## Final Verification

- [ ] **Step 1: Run focused test suite for all slices**

Run:

```bash
pytest -q \
  tests/test_launch_trust_inventory.py \
  tests/test_create_augur_install_copy.py \
  tests/test_demo_surface.py \
  tests/test_agent_instruction_burden.py \
  tests/test_dashboard_config_classification.py \
  skills/loop-ops/augur/tests/test_page_health.py \
  skills/platform-admin/augur/tests/test_worktree_guard.py \
  tests/scripts/test_worktree_preflight.py::test_build_contract_checks_main_checkout_branch
```

Expected:

```text
passed
```

- [ ] **Step 2: Check generated surfaces**

Run:

```bash
AUGUR_SYNC_PROJECT_ROOT="$PWD" AUGUR_SYNC_REPO_LOCAL_ONLY=1 python3 -m skills.ai.scripts.sync_agents check
```

Expected: exits `0`.

- [ ] **Step 3: Audit hardcoded worktree paths**

Run:

```bash
rg -n '/Users/[^/]+/Projects/augur-wt-|augur-wt-[0-9]{8}-[0-9]{6}' README.md docs src skills scripts tests config packages AGENTS.md CODEX.md CLAUDE.md .gemini/GEMINI.md
```

Expected: no output.

- [ ] **Step 4: Check final git state**

Run:

```bash
git status --short --branch
git log --oneline -8
```

Expected: working tree clean, branch ahead by the seven slice commits plus the spec/plan commits unless already pushed or merged.
