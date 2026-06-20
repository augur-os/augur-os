# Augur Guriqo Positioning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply the approved Augur/Guriqo positioning split across the GitHub repo, Augur website, Guriqo website, tests, and release packages.

**Architecture:** Preserve three distinct surfaces: GitHub repo as Augur OS technical proof, `augur.run` as personal/SMB open-source product story, and `guriqo.com` as commercial enterprise deployment story. Guard the split with tests before changing copy, then update each surface and package both static sites.

**Tech Stack:** Markdown docs, Python pytest, static HTML/CSS, shell release packaging, zip verification.

---

## Spec Reference

Design spec:

- `docs/superpowers/specs/2026-04-21-augur-guriqo-positioning-design.md`

Core decisions:

- Augur = personal and SMB open-source second-brain infrastructure.
- Guriqo = commercial enterprise company for second-brain deployments.
- GitHub repo = technical proof.
- Augur website = product story and self-serve conversion.
- Guriqo website = enterprise buyer story.

## File Structure

Repo files:

- `README.md`: GitHub-facing Augur OS positioning, install path, capability summary.
- `docs/architecture-overview.md`: Architecture framing and brand boundary.
- `packages/create-augur/README.md`: Installer package positioning.
- `packages/create-augur/index.js`: Installer CLI wording and next-step output.
- `packages/create-augur/package.json`: Package description.
- `tests/test_augur_repo_positioning.py`: Repo positioning regression tests.
- `tests/test_augur_website_citability.py`: Augur homepage story regression tests.
- `tests/test_augur_website_geo.py`: Augur metadata, JSON-LD, and LLM-facing text tests.
- `tests/test_guriqo_website_messaging.py`: Guriqo enterprise and release package positioning tests.

External website working copy:

- `~/Projects/Au-docs/venture-augur/website-working/index.html`: Augur website homepage.
- `~/Projects/Au-docs/venture-augur/website-working/llms.txt`: LLM-facing Augur/Guriqo entity summary.
- `~/Projects/Au-docs/venture-augur/website-working/enterprise.html`: Augur enterprise page and source for the standalone Guriqo site.
- `~/Projects/Au-docs/venture-augur/website-working/release.sh`: Static packaging script and Guriqo rewrite rules.

Generated external artifacts:

- Release packages created by `~/Projects/Au-docs/venture-augur/website-working/release.sh` under `~/Projects/Au-docs/venture-augur/websites/`.

## Task 1: Add Positioning Tests First

**Files:**

- Modify: `tests/test_augur_repo_positioning.py`
- Modify: `tests/test_augur_website_citability.py`
- Modify: `tests/test_augur_website_geo.py`
- Modify: `tests/test_guriqo_website_messaging.py`

- [ ] **Step 1: Update repo positioning tests**

Replace the existing assertions in `tests/test_augur_repo_positioning.py` with tests that distinguish Augur from Guriqo:

```python
from pathlib import Path


README = Path("README.md").read_text(encoding="utf-8")
ARCH = Path("docs/architecture-overview.md").read_text(encoding="utf-8")


def test_readme_names_augur_as_open_source_personal_smb_infrastructure() -> None:
    assert "Augur is open-source second-brain infrastructure for individuals and SMBs." in README
    assert "documents, notes, skills, MCP commands, dashboards, and AI agents" in README
    assert "one local system you own" in README


def test_readme_preserves_augur_not_guriqo_boundary() -> None:
    assert "Augur is the open-source second brain." in README
    assert "Guriqo is the enterprise deployment company behind it." in README
    assert "not a commercial enterprise services company" in README


def test_readme_keeps_two_step_install_target() -> None:
    assert "install Augur, add documents and notes" in README
    assert "let Augur start compounding" in README
    assert "repo-first" in README


def test_architecture_overview_names_brand_boundary() -> None:
    assert "Augur is the open-source second-brain infrastructure layer" in ARCH
    assert "Guriqo is the commercial enterprise deployment company" in ARCH
    assert "personal builders, technical operators, and SMB teams" in ARCH
```

- [ ] **Step 2: Update Augur homepage story tests**

In `tests/test_augur_website_citability.py`, make the homepage assertions protect the personal/SMB open-source story:

```python
def test_hero_leads_with_open_source_personal_smb_positioning() -> None:
    html = _homepage()
    assert "Build the open-source second brain your AI agents can operate." in html
    assert "Install Augur, add your documents and notes" in html
    assert "let your knowledge compound across skills, dashboards, MCP commands" in html
    assert "No API key" in html
    assert "No wrapper" in html


def test_homepage_keeps_augur_and_guriqo_split_visible() -> None:
    html = _homepage()
    assert "Augur is for builders and small teams." in html
    assert "Need enterprise deployment?" in html
    assert "Guriqo helps organizations deploy second-brain infrastructure commercially." in html
    assert "Guriqo helps enterprises unlock AI" not in html


def test_homepage_keeps_two_step_target_story() -> None:
    html = _homepage()
    assert "The target first-run story is two steps: install Augur, then add your documents and notes." in html
    assert "From there Augur starts compounding" in html
```

Keep the existing tests for GitHub CTA, waitlist visibility, and retired copy unless their expected copy is intentionally replaced by these assertions.

- [ ] **Step 3: Update Augur metadata and LLM text tests**

In `tests/test_augur_website_geo.py`, update the metadata expectations:

```python
def test_homepage_meta_description_mentions_open_source_personal_smb() -> None:
    html = _read("index.html")
    description = _meta_content(html, name="description")
    og_description = _meta_content(html, property="og:description")
    twitter_description = _meta_content(html, name="twitter:description")

    expected = "open-source second brain for individuals and small teams"
    for value in (description, og_description, twitter_description):
        assert expected in value
        assert "documents, notes, skills, MCP commands, and dashboards" in value
        assert "No API key. No wrapper." in value


def test_llms_txt_names_augur_and_guriqo_surface_split() -> None:
    text = (WORKING_DIR / "llms.txt").read_text(encoding="utf-8")
    assert "Augur: open-source second-brain infrastructure for individuals and SMBs" in text
    assert "Guriqo: commercial enterprise deployment company for second-brain infrastructure" in text
    assert "GitHub repo: technical proof" in text
    assert "Augur website: personal and SMB product story" in text
    assert "Guriqo website: enterprise deployment story" in text
```

- [ ] **Step 4: Update Guriqo website tests**

In `tests/test_guriqo_website_messaging.py`, replace the laptop-up lead tests with enterprise second-brain infrastructure tests:

```python
def test_enterprise_page_leads_with_second_brain_infrastructure() -> None:
    html = _read("enterprise.html")
    assert "Enterprise AI needs a brain, not another vendor dashboard." in html
    assert "Guriqo helps organizations deploy second-brain infrastructure" in html
    assert "reducing vendor lock-in and uncontrolled AI costs" in html


def test_enterprise_page_preserves_augur_relationship() -> None:
    html = _read("enterprise.html")
    assert "Augur is the open-source second brain." in html
    assert "Guriqo is the enterprise deployment company behind it." in html
    assert "Built around Augur, the open-source second-brain infrastructure for builders and small teams." in html


def test_enterprise_page_names_enterprise_risks() -> None:
    html = _read("enterprise.html")
    assert "vendor lock-in" in html
    assert "runaway AI costs" in html
    assert "governance" in html
    assert "integration" in html
    assert "enablement" in html
```

Update the release package assertions:

```python
def test_release_build_rewrites_guriqo_metadata_and_jsonld(tmp_path: Path) -> None:
    zip_path = _build_guriqo_site(tmp_path)
    html = _read_zip_member(zip_path, "index.html")

    assert "<title>Guriqo | Enterprise AI Needs a Brain</title>" in html
    assert '<link rel="canonical" href="https://guriqo.com/">' in html
    assert '<meta property="og:title" content="Guriqo | Enterprise AI Needs a Brain">' in html
    assert '<meta property="og:url" content="https://guriqo.com/">' in html
    assert '<meta name="twitter:title" content="Guriqo | Enterprise AI Needs a Brain">' in html
    assert '"name": "Guriqo Enterprise Second-Brain Deployment"' in html
    assert '"@id": "https://guriqo.com/#service"' in html
    assert '"url": "https://guriqo.com/"' in html
```

- [ ] **Step 5: Run tests to confirm they fail**

Run:

```bash
pytest -q tests/test_augur_repo_positioning.py tests/test_augur_website_citability.py tests/test_augur_website_geo.py tests/test_guriqo_website_messaging.py
```

Expected:

```text
FAILED tests/test_augur_repo_positioning.py::test_readme_names_augur_as_open_source_personal_smb_infrastructure
FAILED tests/test_augur_website_citability.py::test_hero_leads_with_open_source_personal_smb_positioning
FAILED tests/test_augur_website_geo.py::test_homepage_meta_description_mentions_open_source_personal_smb
FAILED tests/test_guriqo_website_messaging.py::test_enterprise_page_leads_with_second_brain_infrastructure
```

The exact number of failures may be higher because several stale expectations should fail together.

- [ ] **Step 6: Commit failing tests**

```bash
git add tests/test_augur_repo_positioning.py tests/test_augur_website_citability.py tests/test_augur_website_geo.py tests/test_guriqo_website_messaging.py
git commit -m "test: lock Augur Guriqo positioning split"
```

## Task 2: Update GitHub Repo And Installer Copy

**Files:**

- Modify: `README.md`
- Modify: `docs/architecture-overview.md`
- Modify: `packages/create-augur/README.md`
- Modify: `packages/create-augur/index.js`
- Modify: `packages/create-augur/package.json`

- [ ] **Step 1: Update README opening**

Change the README opening block to:

```markdown
> **Augur is open-source second-brain infrastructure for individuals and SMBs.**
>
> It connects documents, notes, skills, MCP commands, dashboards, and AI agents into one local system you own.

Augur OS is the public open-source repository for the Augur system. It is the technical proof for the personal and SMB product story: SDK, MCP server, skill runtime, document pipeline, dashboard, wiki compiler, tests, ADRs, and auto-loops.

Augur is the open-source second brain. Guriqo is the enterprise deployment company behind it.

Augur is not a `.agent/` folder you copy into each project, not a generic LLM wrapper, and not a commercial enterprise services company. You run Augur as the local layer underneath your AI agents, then connect projects, documents, notes, skills, dashboard pages, and MCP commands to that shared brain.
```

- [ ] **Step 2: Update README install story**

Use this wording in `README.md` under `Working Locally`:

```markdown
The target first-run story is simple: install Augur, add documents and notes, and let Augur start compounding. The current install remains repo-first because Augur runs more than a prompt folder: it starts a Python MCP server, a Next.js dashboard, skill discovery, generated client surfaces, indexes, and runtime state.
```

Keep the existing clone/install command block.

- [ ] **Step 3: Update architecture overview boundary**

Add this paragraph near the top of `docs/architecture-overview.md` after the current Augur definition:

```markdown
Augur is the open-source second-brain infrastructure layer for personal builders, technical operators, and SMB teams. Guriqo is the commercial enterprise deployment company that brings this architecture into organizations with governance, integration, enablement, and cost control.
```

- [ ] **Step 4: Update create-augur package copy**

In `packages/create-augur/package.json`, set:

```json
"description": "Create an open-source Augur second-brain workspace for individuals and SMBs"
```

In `packages/create-augur/README.md`, use:

```markdown
Scaffold a repo-first [Augur](https://augur.run) workspace: open-source second-brain infrastructure for individuals and SMBs.

The target first-run story is simple:

1. Install Augur.
2. Add your documents and notes.

Augur then starts compounding that knowledge through indexes, summaries, skills, MCP commands, and dashboards.
```

In `packages/create-augur/index.js`, update the intro line:

```javascript
console.log(bold('  create-augur') + dim('  - open-source second-brain infrastructure'));
```

Update the help text:

```javascript
console.log('  Creates a repo-first Augur second-brain workspace in the specified directory.');
```

Keep the existing next-step line:

```javascript
console.log(dim('  Then add your documents and notes so Augur can start compounding them.'));
```

- [ ] **Step 5: Run repo positioning tests**

Run:

```bash
pytest -q tests/test_augur_repo_positioning.py
```

Expected:

```text
....                                                                     [100%]
```

- [ ] **Step 6: Run installer help smoke test**

Run:

```bash
node packages/create-augur/index.js --help
```

Expected output includes:

```text
create-augur  - open-source second-brain infrastructure
Creates a repo-first Augur second-brain workspace in the specified directory.
```

- [ ] **Step 7: Commit repo and installer copy**

```bash
git add README.md docs/architecture-overview.md packages/create-augur/README.md packages/create-augur/index.js packages/create-augur/package.json
git commit -m "docs: align Augur open-source positioning"
```

## Task 3: Update Augur Website Copy

**Files:**

- Modify: `~/Projects/Au-docs/venture-augur/website-working/index.html`
- Modify: `~/Projects/Au-docs/venture-augur/website-working/llms.txt`

- [ ] **Step 1: Update Augur homepage metadata**

In `index.html`, update title and meta descriptions to:

```html
<title>Augur | Open-source second brain for AI agents</title>
<meta name="description" content="Augur is the open-source second brain for individuals and small teams. Install Augur, add documents and notes, and compound knowledge across skills, MCP commands, dashboards, and the AI clients you already use. No API key. No wrapper.">
<meta property="og:title" content="Augur | Open-source second brain for AI agents">
<meta property="og:description" content="Augur is the open-source second brain for individuals and small teams. Install Augur, add documents and notes, and compound knowledge across skills, MCP commands, dashboards, and the AI clients you already use. No API key. No wrapper.">
<meta name="twitter:title" content="Augur | Open-source second brain for AI agents">
<meta name="twitter:description" content="Augur is the open-source second brain for individuals and small teams. Install Augur, add documents and notes, and compound knowledge across skills, MCP commands, dashboards, and the AI clients you already use. No API key. No wrapper.">
```

- [ ] **Step 2: Update Augur homepage hero**

In `index.html`, set the hero to:

```html
<h1>Build the open-source second brain your AI agents can operate.</h1>
<p class="hero-desc">Install Augur, add your documents and notes, and let your knowledge compound across skills, dashboards, MCP commands, and the AI clients you already use.</p>
<p class="hero-tagline">For individuals and small teams. No API key. No wrapper. No vendor lock-in.</p>
```

- [ ] **Step 3: Add Augur/Guriqo relationship copy**

In the “Where we are today” section of `index.html`, add this paragraph before the inline actions:

```html
<p>Augur is for builders and small teams. Need enterprise deployment? Guriqo helps organizations deploy second-brain infrastructure commercially with governance, integration, enablement, and cost control.</p>
```

- [ ] **Step 4: Update CTA card copy**

In the GitHub CTA card, use:

```html
<h3>Explore Augur OS on GitHub</h3>
<p>Use the open-source SDK path to connect documents, notes, skills, MCP commands, dashboard pages, and AI agents. MIT licensed.</p>
```

In the waitlist card, use:

```html
<p>We'll email when the simpler self-serve install path opens. No spam; launch updates only.</p>
```

- [ ] **Step 5: Update `llms.txt`**

Replace the entity summary with:

```markdown
## Entity Summary

- Product: Augur
- Augur: open-source second-brain infrastructure for individuals and SMBs
- Guriqo: commercial enterprise deployment company for second-brain infrastructure
- GitHub repo: technical proof for Augur OS
- Augur website: personal and SMB product story
- Guriqo website: enterprise deployment story
- Key distinction: Augur is not an LLM wrapper. No Augur API key is required.
- AI clients: Claude, Codex, Gemini, Cursor, and Ollama can act as the thinking engines
- Protocol layer: Augur operates the harness through local MCP
- Operating story: Install Augur, add documents and notes, then let the second brain compound through indexes, summaries, skills, MCP commands, and dashboards.
- Delivery partner: Guriqo
- Founder: Gur Sannikov
- Public code reference: https://github.com/augur-os/augur-os
```

- [ ] **Step 6: Run Augur website tests**

Run:

```bash
pytest -q tests/test_augur_website_citability.py tests/test_augur_website_geo.py
```

Expected:

```text
........................                                                [100%]
```

All tests in both files must pass.

- [ ] **Step 7: Commit Augur website copy and tests**

Repo tests are tracked, but website files live outside this repo. Commit the tracked test changes only if they were not committed in Task 1:

```bash
git add tests/test_augur_website_citability.py tests/test_augur_website_geo.py
git commit -m "test: protect Augur website positioning"
```

If Task 1 already committed these tests, skip this commit and record that the external website working copy is untracked by the repo.

## Task 4: Update Guriqo Enterprise Website And Release Rewrites

**Files:**

- Modify: `~/Projects/Au-docs/venture-augur/website-working/enterprise.html`
- Modify: `~/Projects/Au-docs/venture-augur/website-working/release.sh`
- Modify: `tests/test_guriqo_website_messaging.py`

- [ ] **Step 1: Update Guriqo enterprise metadata**

In `enterprise.html`, set:

```html
<title>Augur Enterprise | Enterprise AI Needs a Brain</title>
<meta name="description" content="Guriqo helps enterprises unlock AI through second-brain infrastructure without vendor lock-in or runaway AI costs.">
<meta property="og:title" content="Augur Enterprise | Enterprise AI Needs a Brain">
<meta property="og:description" content="Guriqo helps organizations deploy second-brain infrastructure that connects knowledge, workflows, agents, and tools while reducing vendor lock-in and uncontrolled AI costs.">
<meta name="twitter:title" content="Augur Enterprise | Enterprise AI Needs a Brain">
<meta name="twitter:description" content="Guriqo helps organizations deploy second-brain infrastructure that connects knowledge, workflows, agents, and tools while reducing vendor lock-in and uncontrolled AI costs.">
```

In JSON-LD, use:

```json
"name": "Guriqo Enterprise Second-Brain Deployment",
"serviceType": "Enterprise second-brain infrastructure deployment",
"description": "Guriqo helps organizations deploy second-brain infrastructure that connects knowledge, workflows, agents, and tools while reducing vendor lock-in and uncontrolled AI costs."
```

- [ ] **Step 2: Update Guriqo hero**

In `enterprise.html`, set the hero to:

```html
<div class="hero-badge">
    <span>&#9679;</span> Enterprise Second-Brain Infrastructure
</div>
<h1>Enterprise AI needs a brain, not another vendor dashboard.</h1>
<p class="hero-desc">Guriqo helps organizations deploy second-brain infrastructure that connects knowledge, workflows, agents, and tools while reducing vendor lock-in and uncontrolled AI costs.</p>
<p class="accent-line">Your models can change. Your memory, workflows, and operating layer should stay yours.</p>
<p class="hero-proof">Augur is the open-source second brain. Guriqo is the enterprise deployment company behind it.</p>
```

- [ ] **Step 3: Update enterprise sections**

Rename the failure section heading to:

```html
<h2 class="section-heading">Why Vendor-First AI Programs Stall</h2>
```

Use risk cards that include these exact phrases:

```html
<h3>Vendor Lock-In</h3>
<p>When memory, workflow orchestration, and model access live behind one vendor dashboard, switching models becomes a migration project.</p>

<h3>Runaway AI Costs</h3>
<p>Uncontrolled tool sprawl and per-seat AI subscriptions make spend grow faster than durable capability.</p>

<h3>Ungoverned Local Workarounds</h3>
<p>Teams adopt AI anyway, but without shared governance, integration, enablement, or inspectable infrastructure.</p>
```

Add a relationship paragraph in the Guriqo difference section:

```html
<p class="section-sub">Built around Augur, the open-source second-brain infrastructure for builders and small teams. Guriqo brings the enterprise layer: governance, integration, enablement, rollout support, and cost control.</p>
```

- [ ] **Step 4: Update release rewrite rules**

In `release.sh`, update replacements so standalone `guriqo.com` metadata becomes:

```python
(
    "<title>Augur Enterprise | Enterprise AI Needs a Brain</title>",
    "<title>Guriqo | Enterprise AI Needs a Brain</title>",
),
(
    '<meta property="og:title" content="Augur Enterprise | Enterprise AI Needs a Brain">',
    '<meta property="og:title" content="Guriqo | Enterprise AI Needs a Brain">',
),
(
    '<meta name="twitter:title" content="Augur Enterprise | Enterprise AI Needs a Brain">',
    '<meta name="twitter:title" content="Guriqo | Enterprise AI Needs a Brain">',
),
(
    '<span>&#9679;</span> Enterprise Second-Brain Infrastructure',
    '<span>&#9679;</span> Commercial Enterprise Deployment',
),
```

Set the Guriqo logo note in `release.sh` to:

```html
<span class="logo-note">Enterprise second-brain deployment</span>
```

Replace the previous generated proof line with:

```python
html = html.replace(
    "Augur is the open-source second brain. Guriqo is the enterprise deployment company behind it.",
    "Guriqo helps enterprises deploy second-brain infrastructure commercially, with Augur as the open-source technical foundation.",
)
```

- [ ] **Step 5: Run Guriqo tests**

Run:

```bash
pytest -q tests/test_guriqo_website_messaging.py
```

Expected:

```text
.......                                                                  [100%]
```

- [ ] **Step 6: Commit Guriqo tests and release-script changes**

Commit the tracked test update. `release.sh` is outside the repo, so record it in the final report but do not try to add it to this repo.

```bash
git add tests/test_guriqo_website_messaging.py
git commit -m "test: protect Guriqo enterprise positioning"
```

If Task 1 already committed the test update, skip this commit.

## Task 5: Package And Verify Static Sites

**Files:**

- External generated Augur site zip under `~/Projects/Au-docs/venture-augur/websites/`.
- External generated Guriqo site zip under `~/Projects/Au-docs/venture-augur/websites/`.

- [ ] **Step 1: Run the full focused suite**

Run:

```bash
pytest -q tests/test_augur_repo_positioning.py tests/test_augur_website_citability.py tests/test_augur_website_geo.py tests/test_guriqo_website_messaging.py
```

Expected:

```text
passed
```

All tests in the listed files must pass.

- [ ] **Step 2: Run stale-copy scan**

Run:

```bash
rg -n "Transform AI work from the laptop up|Laptop-Up Transformation|AI strategy & implementation|local-first infrastructure for treating your second brain like software|Build a long-term second brain" \
  README.md docs/architecture-overview.md packages/create-augur tests/test_augur_* tests/test_guriqo_website_messaging.py \
  ~/Projects/Au-docs/venture-augur/website-working
```

Expected:

```text
```

No output, except negative assertions in tests if any are intentionally retained.

- [ ] **Step 3: Build release packages**

Run:

```bash
bash ~/Projects/Au-docs/venture-augur/website-working/release.sh
```

Expected output:

```text
Created:
  ~/Projects/Au-docs/venture-augur/websites/augur-run-V*.zip
  ~/Projects/Au-docs/venture-augur/websites/guriqo-com-V*.zip
```

Set shell variables for the latest package paths:

```bash
AUGUR_ZIP="$(ls -t ~/Projects/Au-docs/venture-augur/websites/augur-run-V*.zip | head -1)"
GURIQO_ZIP="$(ls -t ~/Projects/Au-docs/venture-augur/websites/guriqo-com-V*.zip | head -1)"
printf '%s\n%s\n' "$AUGUR_ZIP" "$GURIQO_ZIP"
```

Expected output includes one `augur-run-V*.zip` path and one `guriqo-com-V*.zip` path.

- [ ] **Step 4: Verify zip contents**

Run:

```bash
unzip -p "$AUGUR_ZIP" index.html | rg "Build the open-source second brain|Need enterprise deployment|Use the open-source SDK path"
unzip -p "$GURIQO_ZIP" index.html | rg "Enterprise AI needs a brain|enterprise deployment company|vendor lock-in|uncontrolled AI costs"
```

Expected:

```text
<h1>Build the open-source second brain your AI agents can operate.</h1>
Need enterprise deployment?
Use the open-source SDK path
<h1>Enterprise AI needs a brain, not another vendor dashboard.</h1>
enterprise deployment company
vendor lock-in
uncontrolled AI costs
```

- [ ] **Step 5: Final git status check**

Run:

```bash
git status --short --branch
```

Expected:

```text
## main...origin/main
 M scripts/configure_mcp.py
 M scripts/mcp_ide_config.py
```

Only the two pre-existing unrelated script files should remain dirty after tracked commits. External website files and zips are outside this repo and should be reported separately.

- [ ] **Step 6: Push tracked commits**

Run:

```bash
git push origin main
```

Expected:

```text
main -> main
```

## Completion Report

The final report should include:

- Commit hashes for tracked repo changes.
- Exact release zip paths for Augur and Guriqo.
- Verification commands and pass/fail results.
- Confirmation that the unrelated dirty files were left untouched:
  - `scripts/configure_mcp.py`
  - `scripts/mcp_ide_config.py`
- Note that `~/Projects/Au-docs` is not a Git repo, so website working-copy and zip updates are external artifacts.
