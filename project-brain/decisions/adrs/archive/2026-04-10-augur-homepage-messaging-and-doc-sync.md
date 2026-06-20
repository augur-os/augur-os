# Augur Homepage Messaging And Doc Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refresh the public Augur story so the homepage clearly explains persona, pains, capabilities, and Augur OS, then align the repo-facing README and architecture doc with that same story.

**Architecture:** Update the public website homepage in the website working copy to lead with ownership and anti-lock-in while keeping the product approachable through apps and autoloops. In parallel, refresh the repo-facing `README.md` and `docs/architecture-overview.md` so GitHub carries the deeper philosophy and architecture story promised by the site.

**Tech Stack:** Static HTML/CSS, Markdown docs, pytest, zip packaging.

---

### Task 1: Homepage Messaging Pass

**Files:**
- Modify: `~/Projects/Au-docs/venture-augur/website-working/index.html`
- Modify: `tests/test_augur_website_citability.py`
- Modify: `tests/test_augur_website_geo.py`

This task updates the homepage copy and metadata to reflect the approved positioning: ownership without vendor lock-in, clear pain recognition, concrete capabilities, calmer maintenance, and the public Augur OS GitHub CTA.

- [ ] **Step 1: Write the failing tests**

Update `tests/test_augur_website_citability.py` to assert the new public story:

```python
from __future__ import annotations

from pathlib import Path


WORKING_DIR = Path.home() / "Projects" / "Au-docs" / "venture-augur" / "website-working"


def _homepage() -> str:
    return (WORKING_DIR / "index.html").read_text(encoding="utf-8")


def test_hero_leads_with_ownership_and_vendor_risk() -> None:
    html = _homepage()
    assert "Own your AI setup without vendor lock-in" in html
    assert "one local system for knowledge, tools, and workflows" in html


def test_homepage_names_apps_and_autoloops_as_relief() -> None:
    html = _homepage()
    assert "ready apps and ~80 autoloops" in html
    assert "without babysitting every moving part yourself" in html


def test_capabilities_section_lists_concrete_actions() -> None:
    html = _homepage()
    assert "Add a document and it is automatically indexed into your second brain." in html
    assert "Add a skill and expose it to every connected AI client." in html
    assert "Build local apps you own on top of MCP and all the connected parts." in html


def test_github_cta_names_augur_os() -> None:
    html = _homepage()
    assert "Explore Augur OS on GitHub" in html
    assert "Read the philosophy, architecture, and technical direction in the public Augur OS repository." in html
```

Update `tests/test_augur_website_geo.py` so authority links use the canonical public repo:

```python
def test_core_pages_link_privacy_and_augur_os_github() -> None:
    for name in CORE_PAGES:
        html = _read(name)
        assert 'href="privacy.html"' in html, f"{name} is missing privacy footer/link coverage"
        assert "github.com/augur-os/augur-os" in html, f"{name} is missing Augur OS authority link"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd ~/Projects/Augur
pytest -q tests/test_augur_website_citability.py tests/test_augur_website_geo.py
```

Expected:
- `tests/test_augur_website_citability.py` fails because the new ownership/apps/autoloops/Augur OS phrases are not in the homepage yet.
- `tests/test_augur_website_geo.py` fails because the site still points to the old GitHub URL.

- [ ] **Step 3: Implement the homepage messaging refresh**

Update `~/Projects/Au-docs/venture-augur/website-working/index.html` with the approved copy direction:

```html
<h1>Own your AI setup without vendor lock-in</h1>
<p class="hero-desc">
  Augur gives you one local system for knowledge, tools, and workflows. It already comes
  with ready apps and ~80 autoloops, so you get ownership and portability without
  babysitting every moving part yourself.
</p>
```

Add or rewrite the capabilities section so the homepage answers “what can I do with Augur?” in plain language:

```html
<section class="capabilities animate-on-scroll">
  <div class="container">
    <p class="section-label">What You Can Do</p>
    <h2>Use Augur without rebuilding your stack every month</h2>
    <div class="capability-list">
      <div class="capability-item">Add a document and it is automatically indexed into your second brain.</div>
      <div class="capability-item">Add a skill and expose it to every connected AI client.</div>
      <div class="capability-item">Connect local apps through CLI, including home control systems.</div>
      <div class="capability-item">Talk to your second brain while it stays connected to Google and Apple workflows.</div>
      <div class="capability-item">Bring in your Obsidian vault and work with it from any markdown editor.</div>
      <div class="capability-item">Create MCP workflows and action items while keeping control over each workflow that runs.</div>
      <div class="capability-item">Compound your knowledge base every day as you use it.</div>
      <div class="capability-item">Build local apps you own on top of MCP and all the connected parts.</div>
    </div>
  </div>
</section>
```

Replace the open-source CTA card with the GitHub split agreed in the spec:

```html
<div class="cta-card">
  <h3>Explore Augur OS on GitHub</h3>
  <p>Read the philosophy, architecture, and technical direction in the public Augur OS repository.</p>
  <div class="cta-price">Soft launch</div>
  <a href="https://github.com/augur-os/augur-os" class="cta-btn-tertiary" target="_blank" rel="noopener">Open GitHub</a>
  <p style="font-size: 0.8rem; color: var(--text-muted); margin-top: 12px; margin-bottom: 0;">Augur is currently in soft launch.</p>
</div>
```

Update homepage JSON-LD and footer GitHub links from `https://github.com/gsannikov/augur` to `https://github.com/augur-os/augur-os`.

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
cd ~/Projects/Augur
pytest -q tests/test_augur_website_citability.py tests/test_augur_website_geo.py
```

Expected:
- `tests/test_augur_website_citability.py` passes.
- `tests/test_augur_website_geo.py` passes.

- [ ] **Step 5: Commit**

```bash
cd ~/Projects/Augur
git add tests/test_augur_website_citability.py tests/test_augur_website_geo.py docs/superpowers/plans/2026-04-10-augur-homepage-messaging-and-doc-sync.md
git commit -m "test: cover homepage messaging and augur os authority"
```

### Task 2: README Public Story Refresh

**Files:**
- Modify: `README.md`

This task makes the repo landing page sound like the technical companion to the website: still concrete and usable, but aligned to ownership, vendor risk, shipped apps, autoloops, and the current soft-launch framing.

- [ ] **Step 1: Write the failing doc assertions**

Create `tests/test_augur_repo_positioning.py`:

```python
from pathlib import Path


README = Path("README.md").read_text(encoding="utf-8")


def test_readme_names_vendor_lock_in_story() -> None:
    assert "Own your AI setup without vendor lock-in." in README
    assert "ready apps and ~80 autoloops" in README


def test_readme_explains_augur_os_role() -> None:
    assert "Augur OS is the public open-source repository for the Augur system." in README
    assert "soft launch" in README


def test_readme_keeps_capabilities_concrete() -> None:
    assert "Add a document and automatically index it into your second brain" in README
    assert "Build local apps you own on top of MCP and the connected parts" in README
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd ~/Projects/Augur
pytest -q tests/test_augur_repo_positioning.py
```

Expected:
- The new README assertions fail because the current README still leads with older positioning and does not mention Augur OS soft-launch framing.

- [ ] **Step 3: Update `README.md`**

Revise the top section, capability section, and architecture framing in `README.md`:

```md
> **Own your AI setup without vendor lock-in.**
>
> Augur gives you one local system for knowledge, tools, and workflows. It already comes with ready apps and ~80 autoloops, so you get ownership and portability without babysitting every moving part yourself.

Augur OS is the public open-source repository for the Augur system. It is the technical home for the philosophy, architecture, install path, and public implementation details while Augur is in soft launch.
```

Replace the old “What Can I Build” bullets with user-readable capability bullets:

```md
## What You Can Do With Augur

- Add a document and automatically index it into your second brain
- Add a skill and expose it to every connected AI client
- Connect local apps through CLI, including home automation
- Bring in your Obsidian vault and work with it from any markdown editor
- Create MCP workflows and action items while keeping control over each workflow
- Compound your knowledge base every day as you use it
- Build local apps you own on top of MCP and the connected parts
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
cd ~/Projects/Augur
pytest -q tests/test_augur_repo_positioning.py
```

Expected:
- `3 passed`

- [ ] **Step 5: Commit**

```bash
cd ~/Projects/Augur
git add README.md tests/test_augur_repo_positioning.py
git commit -m "docs: align readme with augur public story"
```

### Task 3: Architecture Doc Sync

**Files:**
- Modify: `docs/architecture-overview.md`
- Test: `tests/test_augur_repo_positioning.py`

This task updates the public architecture overview so it matches the website promise: local ownership, calmer maintenance through apps/autoloops, and a clearer Augur-vs-Augur-OS split.

- [ ] **Step 1: Extend the failing doc assertions**

Append to `tests/test_augur_repo_positioning.py`:

```python
ARCH = Path("docs/architecture-overview.md").read_text(encoding="utf-8")


def test_architecture_overview_explains_calmer_local_control() -> None:
    assert "ownership without vendor lock-in" in ARCH
    assert "apps and autoloops reduce maintenance burden" in ARCH


def test_architecture_overview_mentions_augur_os_repo_role() -> None:
    assert "Augur OS is the public technical surface for Augur during soft launch." in ARCH
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd ~/Projects/Augur
pytest -q tests/test_augur_repo_positioning.py
```

Expected:
- The new architecture assertions fail because the current doc is accurate but missing the new public-story framing.

- [ ] **Step 3: Update `docs/architecture-overview.md`**

Add a short framing block near the top:

```md
Augur is designed for people who want ownership without vendor lock-in. The system keeps knowledge, tools, and workflows on the user side, while apps and autoloops reduce maintenance burden so users do not have to rebuild their AI stack every time the ecosystem shifts.

Augur OS is the public technical surface for Augur during soft launch. The repository documents the philosophy, architecture, and implementation model behind the product story presented on `augur.run`.
```

Revise the “Principle: reasoning is scarce, execution is cheap” and “Repository mapping to layers” sections so the file also explains:
- why local ownership matters operationally
- how apps/autoloops absorb ecosystem churn
- why GitHub goes deeper than the website

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
cd ~/Projects/Augur
pytest -q tests/test_augur_repo_positioning.py
```

Expected:
- `5 passed`

- [ ] **Step 5: Commit**

```bash
cd ~/Projects/Augur
git add docs/architecture-overview.md tests/test_augur_repo_positioning.py
git commit -m "docs: sync architecture overview with public positioning"
```

### Task 4: Final Verification And Package

**Files:**
- Modify: `~/Projects/Au-docs/venture-augur/websites/augur-run-V48.zip`

This task verifies the website copy, repo docs, and packaged website artifact together.

- [ ] **Step 1: Run the full verification set**

Run:

```bash
cd ~/Projects/Augur
pytest -q tests/test_augur_website_citability.py tests/test_augur_website_geo.py tests/test_augur_repo_positioning.py
```

Expected:
- All tests pass.

- [ ] **Step 2: Package the updated website**

Run:

```bash
cd ~/Projects/Au-docs/venture-augur/website-working
zip -r ~/Projects/Au-docs/venture-augur/websites/augur-run-V48.zip . -x "*.DS_Store"
```

Expected:
- `~/Projects/Au-docs/venture-augur/websites/augur-run-V48.zip` is created with the refreshed homepage copy.

- [ ] **Step 3: Sanity-check the packaged artifact**

Run:

```bash
unzip -p ~/Projects/Au-docs/venture-augur/websites/augur-run-V48.zip index.html | rg "Own your AI setup without vendor lock-in|Explore Augur OS on GitHub|ready apps and ~80 autoloops"
```

Expected:
- The command prints the refreshed hero and CTA phrases from the packaged site.

- [ ] **Step 4: Commit repo-side plan and tests if not already committed**

```bash
cd ~/Projects/Augur
git add docs/superpowers/plans/2026-04-10-augur-homepage-messaging-and-doc-sync.md tests/test_augur_repo_positioning.py tests/test_augur_website_citability.py tests/test_augur_website_geo.py README.md docs/architecture-overview.md
git commit -m "docs: refresh augur public messaging surfaces"
```
