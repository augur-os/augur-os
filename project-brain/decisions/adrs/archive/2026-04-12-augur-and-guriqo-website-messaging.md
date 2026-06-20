# Augur And Guriqo Website Messaging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refresh `augur.run` and the Guriqo enterprise surface so Augur stays personal/prosumer-first while clearly expressing wiki compounding, dependency-light autoloops, transparency, and laptop-up enterprise transformation.

**Architecture:** Keep the existing static site structure and visual language intact. Update the public story by rewriting copy in `~/Projects/Au-docs/venture-augur/website-working/index.html` and `~/Projects/Au-docs/venture-augur/website-working/enterprise.html`, then preserve Guriqo deployment behavior by updating the `release.sh` transformation logic that builds `guriqo.com` from `enterprise.html`.

**Tech Stack:** Static HTML/CSS, shell release script, pytest.

---

## File Structure

### Website sources

- Modify: `~/Projects/Au-docs/venture-augur/website-working/index.html`
  - Augur homepage hero, section order, section copy, CTA wording
- Modify: `~/Projects/Au-docs/venture-augur/website-working/enterprise.html`
  - Enterprise/Guriqo hero, failure framing, bottom-up rollout framing, dependency language
- Modify: `~/Projects/Au-docs/venture-augur/website-working/release.sh`
  - Guriqo build-time title/canonical/metadata replacements

### Repo tests

- Modify: `tests/test_augur_website_citability.py`
  - Assert the new Augur homepage messaging hierarchy
- Modify: `tests/test_augur_website_geo.py`
  - Keep homepage/geo coverage intact after copy changes
- Create: `tests/test_guriqo_website_messaging.py`
  - Assert enterprise source messaging and release transformation strings for the built Guriqo site

## Task 1: Refresh `augur.run` Messaging Without Breaking Familiarity

**Files:**
- Modify: `tests/test_augur_website_citability.py`
- Modify: `tests/test_augur_website_geo.py`
- Modify: `~/Projects/Au-docs/venture-augur/website-working/index.html`

- [ ] **Step 1: Write the failing homepage messaging tests**

Update `tests/test_augur_website_citability.py` so the homepage is required to express the approved message hierarchy:

```python
from __future__ import annotations

from pathlib import Path


WORKING_DIR = Path.home() / "Projects" / "Au-docs" / "venture-augur" / "website-working"


def _homepage() -> str:
    return (WORKING_DIR / "index.html").read_text(encoding="utf-8")


def test_hero_keeps_second_brain_anchor_and_adds_compounding() -> None:
    html = _homepage()
    assert "Build your second brain on your machine" in html
    assert "maintained knowledge system that keeps getting better as you use it" in html
    assert "wiki compounding" in html


def test_homepage_reorders_story_around_compounding_and_trust() -> None:
    html = _homepage()
    assert "Your second brain should compound, not just store" in html
    assert "Automation that runs on your terms" in html
    assert "Understand it before you depend on it" in html
    assert "Start with the files and folders you already have" in html


def test_autoloops_section_emphasizes_no_mandatory_middle_layer() -> None:
    html = _homepage()
    assert "do not require a mandatory API key" in html
    assert "do not require a third-party orchestration layer" in html
    assert "local or remote" in html


def test_capabilities_section_still_stays_concrete() -> None:
    html = _homepage()
    assert "Add files and folders and have them consumed into your second brain." in html
    assert "Compound your knowledge base as you use it." in html
    assert "Build local apps you own on top of the system." in html
```

Extend `tests/test_augur_website_geo.py` with one homepage metadata assertion so the rewritten hero copy also reaches discoverability surfaces:

```python
def test_homepage_meta_description_mentions_compounding() -> None:
    html = _read("index.html")
    assert "maintained knowledge system" in html
    assert "Build your second brain on your machine" in html
```

- [ ] **Step 2: Run the homepage tests to verify they fail**

Run:

```bash
cd ~/Projects/Augur
pytest -q tests/test_augur_website_citability.py tests/test_augur_website_geo.py
```

Expected:
- `tests/test_augur_website_citability.py` fails because the current homepage still uses the older hero subhead and older section wording/order.
- `tests/test_augur_website_geo.py` may fail on the new meta-description assertion until the homepage metadata is updated.

- [ ] **Step 3: Rewrite the Augur homepage copy in place**

Update `~/Projects/Au-docs/venture-augur/website-working/index.html` to keep the current visual shell but change the story hierarchy.

Replace the hero subhead and badge emphasis:

```html
<h1>Build your second brain on your machine</h1>
<p class="hero-desc">
  Augur turns your notes, documents, skills, pages, and sessions into a maintained
  knowledge system that keeps getting better as you use it.
</p>
<p class="hero-tagline">wiki compounding · background autoloops · full transparency</p>
```

Replace the first explanatory section with the compounding message:

```html
<p class="section-label">Wiki Compounding</p>
<h2>Your second brain should compound, not just store</h2>
<p class="section-sub">
  Augur continuously turns scattered notes, documents, skills, pages, sessions, and
  decisions into maintained knowledge instead of leaving them as disconnected raw inputs.
</p>
```

Rewrite the autoloops section around independence in operation:

```html
<p class="section-label">Automation</p>
<h2>Automation that runs on your terms</h2>
<p class="autoloops-desc">
  Augur's autoloops can run with your own tools, local or remote, so the system keeps
  itself healthy without turning into another stack you have to babysit.
</p>
<div class="autoloops-callout">
  They do not require a mandatory API key, a mandatory Augur cloud, or a third-party
  orchestration layer sitting between you and your second brain.
</div>
```

Rewrite the browse/transparency section heading and copy:

```html
<p class="section-label">Transparency</p>
<h2>Understand it before you depend on it</h2>
<p class="section-sub">
  Browse lets you inspect what exists, how things connect, and how the system is
  structured, so your second brain stays legible as it grows.
</p>
```

Rewrite the ingest section to lower onboarding friction:

```html
<p class="section-label">Start From What You Have</p>
<h2>Start with the files and folders you already have</h2>
<p class="section-sub">
  Drop in raw material and let Augur consume, route, and enrich it so it becomes part
  of your second brain instead of staying disconnected input.
</p>
```

Adjust the capabilities bullets so they stay concrete but follow the new story order:

```html
<div class="capability-card"><p>Add files and folders and have them consumed into your second brain.</p></div>
<div class="capability-card"><p>Compound your knowledge base as you use it.</p></div>
<div class="capability-card"><p>Add a skill and expose it to every connected AI client.</p></div>
<div class="capability-card"><p>Talk to your second brain across local, Google, Apple, and other workflows.</p></div>
<div class="capability-card"><p>Create MCP workflows and action items while keeping control over what runs.</p></div>
<div class="capability-card"><p>Build local apps you own on top of the system.</p></div>
```

Update the homepage `<meta name="description">`, `og:description`, and `twitter:description` to reflect maintained knowledge, not only local storage.

- [ ] **Step 4: Run the homepage tests to verify they pass**

Run:

```bash
cd ~/Projects/Augur
pytest -q tests/test_augur_website_citability.py tests/test_augur_website_geo.py
```

Expected:
- `tests/test_augur_website_citability.py` passes with the new hero and section wording
- `tests/test_augur_website_geo.py` passes, including the new metadata assertion

- [ ] **Step 5: Commit the Augur homepage pass**

Run:

```bash
cd ~/Projects/Augur
git add tests/test_augur_website_citability.py tests/test_augur_website_geo.py
git commit -m "test: cover augur homepage messaging hierarchy"
```

Commit the external website file in its own repo/worktree if needed after verifying the exact local workflow for `~/Projects/Au-docs`.

## Task 2: Rewrite Guriqo Around Laptop-Up Transformation

**Files:**
- Create: `tests/test_guriqo_website_messaging.py`
- Modify: `~/Projects/Au-docs/venture-augur/website-working/enterprise.html`
- Modify: `~/Projects/Au-docs/venture-augur/website-working/release.sh`

- [ ] **Step 1: Write the failing enterprise/Guriqo tests**

Create `tests/test_guriqo_website_messaging.py`:

```python
from __future__ import annotations

from pathlib import Path


WORKING_DIR = Path.home() / "Projects" / "Au-docs" / "venture-augur" / "website-working"
ENTERPRISE = (WORKING_DIR / "enterprise.html").read_text(encoding="utf-8")
RELEASE = (WORKING_DIR / "release.sh").read_text(encoding="utf-8")


def test_enterprise_page_leads_with_laptop_up_transformation() -> None:
    assert "Transform AI work from the laptop up, not from the cloud down" in ENTERPRISE
    assert "starts on workers' laptops" in ENTERPRISE
    assert "inside existing tools and real workflows" in ENTERPRISE


def test_enterprise_page_names_vendor_and_aggregator_dependency() -> None:
    assert "single-vendor dependency" in ENTERPRISE
    assert "third-party aggregator dependency" in ENTERPRISE
    assert "new external control point for models, pricing, workflows, memory, and orchestration" in ENTERPRISE


def test_enterprise_page_keeps_bottom_up_governed_not_chaotic() -> None:
    assert "working systems emerge where the work happens, then scale with structure" in ENTERPRISE
    assert "not from the cloud down" in ENTERPRISE


def test_release_script_builds_guriqo_title_and_canonical() -> None:
    assert "<title>Guriqo | Transform AI Work From the Laptop Up</title>" in RELEASE
    assert '<link rel="canonical" href="https://guriqo.com/">' in RELEASE
```

- [ ] **Step 2: Run the enterprise/Guriqo tests to verify they fail**

Run:

```bash
cd ~/Projects/Augur
pytest -q tests/test_guriqo_website_messaging.py
```

Expected:
- The hero assertion fails because `enterprise.html` still leads with `Deploy Augur For Teams`
- The dependency and laptop-up assertions fail because the current copy is only partially aligned
- The release-script title assertion fails because the build still rewrites to the older Guriqo title

- [ ] **Step 3: Rewrite the enterprise page around laptop-up transformation**

Update `~/Projects/Au-docs/venture-augur/website-working/enterprise.html`.

Replace the hero block:

```html
<h1>Transform AI work from the laptop up, not from the cloud down</h1>
<p class="hero-desc">
  Guriqo helps teams deploy Augur by starting where work actually happens:
  on workers' laptops, inside existing tools and real workflows, then scaling
  what works upward with structure.
</p>
<p class="accent-line">
  Bottom-up transformation, owned control layers, no forced cloud-first rewrite.
</p>
```

Rewrite the failure section so it explicitly targets cloud-down mandates:

```html
<h2 class="section-heading">Why cloud-down AI transformation keeps failing</h2>
<p class="section-sub">
  The common failure mode is not lack of ambition. It is forcing platform adoption
  before the workflow is real on the ground.
</p>
```

Add dependency language to the enterprise pain/difference section:

```html
<p>Single-vendor dependency is risky enough. Third-party aggregator dependency can be worse because it becomes the new external control point for models, pricing, workflows, memory, and orchestration.</p>
```

Rewrite the bottom-up deployment section to keep the critical nuance:

```html
<h2 class="section-heading">Bottom-up, with structure</h2>
<p class="section-sub">
  Transformation starts on workers' laptops and in the tools they already use.
  Working systems emerge where the work happens, then scale with structure.
</p>
```

Keep the existing page layout, cards, and booking/contact structure unless the new copy no longer fits.

- [ ] **Step 4: Update the Guriqo release build transformation**

Modify `~/Projects/Au-docs/venture-augur/website-working/release.sh` so the built `guriqo.com` artifact uses the revised enterprise framing.

Update the title replacement block:

```python
(
    "<title>Augur Enterprise Deployment | Delivered by Guriqo</title>",
    "<title>Guriqo | Transform AI Work From the Laptop Up</title>",
),
(
    '<meta property="og:title" content="Augur Enterprise Deployment | Delivered by Guriqo">',
    '<meta property="og:title" content="Guriqo | Transform AI Work From the Laptop Up">',
),
(
    '<meta name="twitter:title" content="Augur Enterprise Deployment | Delivered by Guriqo">',
    '<meta name="twitter:title" content="Guriqo | Transform AI Work From the Laptop Up">',
),
```

Also fix the canonical replacement to match the exact source string in `enterprise.html`:

```python
(
    '<link rel="canonical" href="https://augur.run/enterprise.html">',
    '<link rel="canonical" href="https://guriqo.com/">',
),
(
    '<meta property="og:url" content="https://augur.run/enterprise.html">',
    '<meta property="og:url" content="https://guriqo.com/">',
),
```

This prevents the build from silently missing the replacement because the old pattern omits `.html`.

- [ ] **Step 5: Run the enterprise/Guriqo tests to verify they pass**

Run:

```bash
cd ~/Projects/Augur
pytest -q tests/test_guriqo_website_messaging.py
```

Expected:
- `4 passed`

- [ ] **Step 6: Commit the enterprise/Guriqo test coverage**

Run:

```bash
cd ~/Projects/Augur
git add tests/test_guriqo_website_messaging.py
git commit -m "test: cover guriqo laptop-up messaging"
```

Commit the external website files in `~/Projects/Au-docs` using that repo's normal workflow after verifying the deployment process.

## Task 3: Final Verification Across Both Surfaces

**Files:**
- Verify: `tests/test_augur_website_citability.py`
- Verify: `tests/test_augur_website_geo.py`
- Verify: `tests/test_guriqo_website_messaging.py`
- Verify: `~/Projects/Au-docs/venture-augur/website-working/index.html`
- Verify: `~/Projects/Au-docs/venture-augur/website-working/enterprise.html`
- Verify: `~/Projects/Au-docs/venture-augur/website-working/release.sh`

- [ ] **Step 1: Run the full messaging test suite**

Run:

```bash
cd ~/Projects/Augur
pytest -q \
  tests/test_augur_website_citability.py \
  tests/test_augur_website_geo.py \
  tests/test_guriqo_website_messaging.py
```

Expected:
- All selected tests pass

- [ ] **Step 2: Inspect the top-of-page copy manually**

Check these exact strings in the website sources:

```bash
rg -n \
  "Build your second brain on your machine|Your second brain should compound, not just store|Automation that runs on your terms|Understand it before you depend on it|Start with the files and folders you already have|Transform AI work from the laptop up, not from the cloud down|working systems emerge where the work happens, then scale with structure" \
  ~/Projects/Au-docs/venture-augur/website-working/index.html \
  ~/Projects/Au-docs/venture-augur/website-working/enterprise.html
```

Expected:
- Every planned message appears in the intended source file

- [ ] **Step 3: Verify the Guriqo build script replacements**

Run:

```bash
rg -n \
  "Guriqo \\| Transform AI Work From the Laptop Up|https://guriqo.com/|og:url" \
  ~/Projects/Au-docs/venture-augur/website-working/release.sh
```

Expected:
- Title and canonical replacements are present in `release.sh`

- [ ] **Step 4: Commit the final plan-aligned verification checkpoint**

Run:

```bash
cd ~/Projects/Augur
git commit --allow-empty -m "chore: verify website messaging refresh plan checkpoints"
```

Expected:
- Empty verification commit records that all test gates and string checks completed
