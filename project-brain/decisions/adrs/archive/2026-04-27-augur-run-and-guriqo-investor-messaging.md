# augur.run + guriqo.com Investor Messaging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align both public marketing surfaces — augur.run and guriqo.com — with the investor pitch already presented to LPs, by adding a dedicated "Augur Enterprise" section to augur.run and a "What we deploy" section to guriqo.com (plus a title fix and proof-line update).

**Architecture:** All edits in `~/Projects/Au-docs/venture-augur/website-working/` (not a git repo — file changes only). Single source dir; `index.html` serves augur.run as-is; `enterprise.html` serves both augur.run/enterprise.html and (via `release.sh` transforms) guriqo.com. Deploy is two-step: `release.sh` builds zips, then `scp` + `ssh unzip` to Hostinger. The `release.sh` title transforms become no-ops after this change (source title in `enterprise.html` already matches the desired guriqo title) so the transform rules are removed for hygiene.

**Tech Stack:** Static HTML, existing CSS classes (`.multi-cta`, `.cta-grid`, `.cta-card`, `.section-heading`, `.cta-btn-primary/secondary/tertiary`, `.repo-link`, `.github-icon`). No JS changes. Deploy via existing `release.sh`. SSH alias `hostinger` for SCP+unzip.

**Spec:** `docs/superpowers/specs/2026-04-27-augur-run-and-guriqo-investor-messaging-design.md`

**Pre-flight already done:**
- `index.html` anchors confirmed (line 14: `og:description`; line 1228: `<section class="multi-cta" id="get-started">`; line 1270: existing "Enterprise deployment" card `<h3>`).
- `enterprise.html` anchors confirmed (lines 6/13/20: title triplet; line 654: hero proof line).
- `release.sh` has 3 title-transform pairs (lines 74–75, 82–83, 90–91) targeting the old `<title>Augur Enterprise | Enterprise AI Needs a Brain</title>` and matching `og:title`/`twitter:title`. After this plan they become no-ops — Task 4 removes them.
- Au-docs dir is **not a git repo** — no commits possible. File changes are direct.

---

## File Structure

| File | Action |
|------|--------|
| `~/Projects/Au-docs/venture-augur/website-working/index.html` | 3 edits: og:description + new section + replace card 3 |
| `~/Projects/Au-docs/venture-augur/website-working/enterprise.html` | 3 edits: title triplet + hero proof line + new "What we deploy" section |
| `~/Projects/Au-docs/venture-augur/website-working/release.sh` | Remove 3 obsolete title-transform pairs |

---

## Task 1: Edit `index.html` — augur.run

**Files:**
- Modify: `~/Projects/Au-docs/venture-augur/website-working/index.html`

- [ ] **Step 1: Update `og:description` meta tag**

Find around line 14:
```html
    <meta property="og:description" content="Augur connects your local second brain to Claude, Codex, Gemini, Cursor, Ollama, and MCP clients, then compounds useful work back into durable notes, memory, wiki pages, skills, and workflows.">
```

Replace with:
```html
    <meta property="og:description" content="Augur is the local-first runtime that connects Claude, GPT, Gemini, and local models to your work — and compounds useful outcomes back into durable files you own.">
```

- [ ] **Step 2: Insert the new Augur Enterprise section before §5 (Get Started)**

Find around line 1228:
```html

        <!-- CTA -->
        <section class="multi-cta" id="get-started">
```

Insert this block IMMEDIATELY BEFORE that comment+section opening (so the comment moves down):

```html
        <!-- Augur Enterprise -->
        <section class="multi-cta" id="enterprise">
            <div class="multi-cta-bg"></div>
            <div class="container">
                <p style="font-size: 0.8rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.15em; color: var(--accent-violet); margin-bottom: 16px;">For organizations</p>
                <h2 class="section-heading">Augur Enterprise</h2>
                <p class="vision-sub">The closed-source central tier for organizations whose teams already run Augur locally. Augur Enterprise lets IT manage the fleet of runtimes, set policies across the org, and compound nightly into shared org intelligence — built from how people actually work, not from what gets uploaded to SharePoint. The opposite of top-down copilots like Glean or Copilot.</p>

                <div class="cta-grid">
                    <div class="cta-card">
                        <h3>Fleet management</h3>
                        <p>Inventory, control, and policy across every employee laptop running Augur. IT keeps audit, sandboxing, and inspection.</p>
                    </div>
                    <div class="cta-card">
                        <h3>Nightly org compounding</h3>
                        <p>Per-laptop work compounds into a shared org wiki — readable by every employee through the runtime they already have.</p>
                    </div>
                    <div class="cta-card">
                        <h3>Not Glean. Not Copilot.</h3>
                        <p>Top-down copilots scrape what's been uploaded to a corporate document repository. Augur Enterprise builds intelligence from real work — no upload required.</p>
                    </div>
                </div>

                <div style="text-align: center; margin-top: 32px;">
                    <a href="https://guriqo.com" class="cta-btn-primary" target="_blank" rel="noopener">Talk to Guriqo for deployment →</a>
                </div>
            </div>
        </section>

```

(Note: trailing blank line before the existing `<!-- CTA -->` comment.)

- [ ] **Step 3: Replace card 3 in Get Started multi-CTA**

Find the existing third card (the `Enterprise deployment` card, around line 1270 in `index.html`). The full block is:

```html
                    <div class="cta-card">
                        <h3>Enterprise deployment</h3>
                        <p>Need a commercial deployment path, rollout support, or organization-wide second-brain infrastructure? That route goes through Guriqo.</p>
                        <div class="cta-price">Commercial rollout and delivery</div>
                        <div class="cta-card-actions">
                            <a href="https://guriqo.com" class="cta-btn-tertiary" target="_blank" rel="noopener">Visit Guriqo</a>
                        </div>
                    </div>
```

Replace with:

```html
                    <div class="cta-card">
                        <h3>For developers</h3>
                        <p>Inspect the architecture, read the code, and contribute. The runtime, skills, and dashboard all live on GitHub.</p>
                        <div class="cta-price">Open source · MIT</div>
                        <div class="cta-card-actions">
                            <a href="https://github.com/augur-os/augur-os" class="cta-btn-tertiary repo-link" target="_blank" rel="noopener">
                                <svg class="github-icon" viewBox="0 0 16 16" aria-hidden="true" xmlns="http://www.w3.org/2000/svg">
                                    <path fill="currentColor" d="M8 0C3.58 0 0 3.58 0 8a8 8 0 0 0 5.47 7.59c.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.5-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82A7.65 7.65 0 0 1 8 4.69c.68 0 1.37.09 2.01.26 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.19 0 .21.15.46.55.38A8 8 0 0 0 16 8c0-4.42-3.58-8-8-8Z"/>
                                </svg>
                                <span>View on GitHub</span>
                            </a>
                        </div>
                    </div>
```

- [ ] **Step 4: Verify**

```bash
cd ~/Projects/Au-docs/venture-augur/website-working
echo "Enterprise section: $(grep -c 'id="enterprise"' index.html)"        # expect 1
echo "Augur Enterprise H2: $(grep -c '<h2 class="section-heading">Augur Enterprise</h2>' index.html)"   # expect 1
echo "Glean/Copilot: $(grep -c 'Not Glean. Not Copilot' index.html)"      # expect 1
echo "Talk to Guriqo: $(grep -c 'Talk to Guriqo for deployment' index.html)"   # expect 1
echo "For developers: $(grep -c '<h3>For developers</h3>' index.html)"    # expect 1
echo "Old card gone: $(grep -c '<h3>Enterprise deployment</h3>' index.html)"   # expect 0
echo "Old og desc gone: $(grep -c 'connects your local second brain' index.html)"   # expect 0
echo "New og desc: $(grep -c 'connects Claude, GPT, Gemini, and local models' index.html)"   # expect 1
```

All counts must match. If any is off, locate the missed edit and fix.

- [ ] **Step 5: Visual smoke check (optional but recommended)**

Open `file://~/Projects/Au-docs/venture-augur/website-working/index.html` in a browser. Confirm:
- New "Augur Enterprise" section renders between FAQ and Get Started.
- Section uses the same `multi-cta` shell as Get Started (background + container).
- Three cards in the cta-grid render at the same width as the Get Started cards.
- "Talk to Guriqo for deployment" button renders centered below the grid.
- Get Started multi-CTA still has 3 cards: Community release · Roadmap & architecture · For developers.
- "For developers" card shows the GitHub icon + "View on GitHub" label.

---

## Task 2: Edit `enterprise.html` — guriqo.com source

**Files:**
- Modify: `~/Projects/Au-docs/venture-augur/website-working/enterprise.html`

- [ ] **Step 1: Update title triplet**

Find around lines 6, 13, 20:

```html
    <title>Augur Enterprise | Enterprise AI Needs a Brain</title>
```
```html
    <meta property="og:title" content="Augur Enterprise | Enterprise AI Needs a Brain">
```
```html
    <meta name="twitter:title" content="Augur Enterprise | Enterprise AI Needs a Brain">
```

Replace each with:

```html
    <title>Guriqo | Enterprise AI deployment for the Augur runtime</title>
```
```html
    <meta property="og:title" content="Guriqo | Enterprise AI deployment for the Augur runtime">
```
```html
    <meta name="twitter:title" content="Guriqo | Enterprise AI deployment for the Augur runtime">
```

- [ ] **Step 2: Update hero proof line**

Find around line 654:

```html
                <p class="hero-proof">Built on Augur, the open foundation for durable enterprise AI adoption.</p>
```

Replace with:

```html
                <p class="hero-proof">We deploy Augur and Augur Enterprise — the open-source runtime your team installs locally and the closed-source central tier for IT.</p>
```

- [ ] **Step 3: Insert "What we deploy" section after the hero**

Find the closing `</section>` of the hero block (the one that contains the proof line you just edited). The next opening tag should be the first content section heading.

Run this to locate the exact position:
```bash
cd ~/Projects/Au-docs/venture-augur/website-working
grep -n "</section>" enterprise.html | head -5
grep -n "Enterprise AI Work Is Becoming an Infrastructure Problem" enterprise.html
```

The first content section currently starts with the line containing `Enterprise AI Work Is Becoming an Infrastructure Problem`. Insert the new "What we deploy" section between the hero's `</section>` and the next `<section ...>` opening (the one that contains the "Infrastructure Problem" heading).

Insert this block:

```html
        <!-- What we deploy -->
        <section class="what-we-deploy">
            <div class="container">
                <h2 class="section-heading">What we deploy</h2>
                <div class="cta-grid">
                    <div class="cta-card">
                        <h3>Augur</h3>
                        <p>Open-source runtime your team installs locally. Sits on every employee laptop and orchestrates Claude, GPT, Gemini, and local models against the work already happening there.</p>
                        <div class="cta-card-actions">
                            <a href="https://augur.run" class="cta-btn-tertiary" target="_blank" rel="noopener">Learn more on augur.run</a>
                        </div>
                    </div>
                    <div class="cta-card">
                        <h3>Augur Enterprise</h3>
                        <p>Closed-source central tier for IT. Manages the fleet of runtimes, sets policies across the org, and compounds nightly into shared org intelligence — built from real work, not from what gets uploaded to SharePoint.</p>
                        <div class="cta-card-actions">
                            <a href="https://augur.run/#enterprise" class="cta-btn-tertiary" target="_blank" rel="noopener">Learn more on augur.run</a>
                        </div>
                    </div>
                </div>
            </div>
        </section>

```

(Trailing blank line before the next existing section.)

- [ ] **Step 4: Verify**

```bash
cd ~/Projects/Au-docs/venture-augur/website-working
echo "Old title gone: $(grep -c 'Augur Enterprise | Enterprise AI Needs a Brain' enterprise.html)"   # expect 0
echo "New title triplet: $(grep -c 'Guriqo | Enterprise AI deployment for the Augur runtime' enterprise.html)"   # expect 3
echo "Old proof line gone: $(grep -c 'Built on Augur, the open foundation' enterprise.html)"   # expect 0
echo "New proof line: $(grep -c 'We deploy Augur and Augur Enterprise' enterprise.html)"   # expect 1
echo "What we deploy section: $(grep -c 'class="what-we-deploy"' enterprise.html)"   # expect 1
echo "What we deploy H2: $(grep -c '<h2 class="section-heading">What we deploy</h2>' enterprise.html)"   # expect 1
echo "Both product cards: $(grep -c 'Learn more on augur.run' enterprise.html)"   # expect 2
```

All must match.

- [ ] **Step 5: Visual smoke check**

Open `file://~/Projects/Au-docs/venture-augur/website-working/enterprise.html` in a browser. Confirm:
- Browser tab title shows "Guriqo | Enterprise AI deployment for the Augur runtime".
- Hero proof line reads "We deploy Augur and Augur Enterprise — the open-source runtime your team installs locally and the closed-source central tier for IT."
- New "What we deploy" section appears immediately after hero with two cards (Augur · Augur Enterprise) each linking to augur.run.
- The existing "Enterprise AI Work Is Becoming an Infrastructure Problem" section follows directly.

---

## Task 3: Clean up obsolete `release.sh` title transforms

**Files:**
- Modify: `~/Projects/Au-docs/venture-augur/website-working/release.sh`

After Task 2, `enterprise.html` already has the desired guriqo title in all 3 places. The release.sh transforms that targeted the old strings (lines 74–75, 82–83, 90–91) become no-ops. Removing them is hygiene — they'd silently fail to match if the source ever drifts.

- [ ] **Step 1: Locate the 3 obsolete transform pairs**

```bash
grep -n "Augur Enterprise | Enterprise AI Needs a Brain" ~/Projects/Au-docs/venture-augur/website-working/release.sh
```
Expected: 3 lines (74, 82, 90 or thereabouts). Each is one half of a tuple in the `replacements` Python list.

- [ ] **Step 2: Remove the 3 obsolete tuples**

Find this block in the file:

```python
    (
        "<title>Augur Enterprise | Enterprise AI Needs a Brain</title>",
        "<title>Guriqo | Enterprise AI Needs a Brain</title>",
    ),
```

And:

```python
    (
        '<meta property="og:title" content="Augur Enterprise | Enterprise AI Needs a Brain">',
        '<meta property="og:title" content="Guriqo | Enterprise AI Needs a Brain">',
    ),
```

And:

```python
    (
        '<meta name="twitter:title" content="Augur Enterprise | Enterprise AI Needs a Brain">',
        '<meta name="twitter:title" content="Guriqo | Enterprise AI Needs a Brain">',
    ),
```

Delete all three tuples (each tuple is 4 lines including the surrounding `(` `)` and trailing comma). Leave a trailing comma intact on the previous tuple if needed; the `replacements` list must remain valid Python.

- [ ] **Step 3: Verify**

```bash
cd ~/Projects/Au-docs/venture-augur/website-working
grep -c "Augur Enterprise | Enterprise AI Needs a Brain" release.sh   # expect 0
python3 -c "import ast; ast.parse(open('release.sh').read())" 2>&1 | head -3 || echo "release.sh is bash, skip python parse"
bash -n release.sh && echo "bash syntax OK"
```

The `bash -n` syntax check should pass. If Python embedded blocks have indentation issues post-edit, the bash syntax checker won't catch it but a dry-run of the script will.

- [ ] **Step 4: Dry-run release.sh to confirm no syntax error in embedded Python**

```bash
cd ~/Projects/Au-docs/venture-augur/website-working
bash release.sh 99999
```
Expected: zip files created with version `V99999` (e.g., `augur-run-V99999.zip` and `guriqo-com-V99999.zip` in `../websites/`). If Python errors out, the embedded HEREDOC has a syntax problem.

After successful dry-run, **delete the `V99999` zips** so they don't pollute the version sequence:

```bash
rm ~/Projects/Au-docs/venture-augur/websites/augur-run-V99999.zip
rm ~/Projects/Au-docs/venture-augur/websites/guriqo-com-V99999.zip
```

---

## Task 4: Build and deploy

**Files:** no file edits.

This task runs `release.sh` to build production zips, then SCP-uploads and SSH-unzips to Hostinger. **User confirmation required** before executing the deploy commands — production deploy.

- [ ] **Step 1: Build zips**

```bash
cd ~/Projects/Au-docs/venture-augur/website-working
bash release.sh
```
Expected: prints `Created:` followed by paths to two `V<N>.zip` files in `../websites/` (auto-incremented version). Note the version number for the next steps.

- [ ] **Step 2: Confirm new title is in the guriqo zip**

```bash
cd ~/Projects/Au-docs/venture-augur/websites
LATEST_GURIQO=$(ls -t guriqo-com-V*.zip | head -1)
unzip -p "$LATEST_GURIQO" index.html | grep -c "Guriqo | Enterprise AI deployment for the Augur runtime"
```
Expected: `3` (title + og:title + twitter:title). If `0`, the transforms in `release.sh` removed the wrong thing or the source `enterprise.html` was not edited.

- [ ] **Step 3: USER CONFIRMATION GATE — pause before deploy**

Both zips are built and verified. Before running SCP+SSH to live production:
- augur.run will be updated with the new Augur Enterprise section, replaced "For developers" card, and updated `og:description`.
- guriqo.com will be updated with the new title triplet, hero proof line, and "What we deploy" section.

Halt here and wait for explicit confirmation from the controller. Do not run SCP without it.

- [ ] **Step 4: SCP the augur.run zip and unzip on the server**

(Replace `V<N>` with the actual version from Step 1.)

```bash
cd ~/Projects/Au-docs/venture-augur/websites
scp -B "augur-run-V<N>.zip" hostinger:~/domains/augur.run/public_html/
ssh -o BatchMode=yes hostinger "cd domains/augur.run/public_html && unzip -o augur-run-V<N>.zip > /dev/null && rm augur-run-V<N>.zip && find . -type f -exec chmod 644 {} \; && find . -type d -exec chmod 755 {} \; && echo DEPLOYED_AUGUR"
```
Expected: `DEPLOYED_AUGUR` printed at the end.

- [ ] **Step 5: SCP the guriqo.com zip and unzip on the server**

```bash
cd ~/Projects/Au-docs/venture-augur/websites
scp -B "guriqo-com-V<N>.zip" hostinger:~/domains/guriqo.com/public_html/
ssh -o BatchMode=yes hostinger "cd domains/guriqo.com/public_html && unzip -o guriqo-com-V<N>.zip > /dev/null && rm guriqo-com-V<N>.zip && find . -type f -exec chmod 644 {} \; && find . -type d -exec chmod 755 {} \; && echo DEPLOYED_GURIQO"
```
Expected: `DEPLOYED_GURIQO` printed at the end.

---

## Task 5: Live verification

**Files:** no file edits.

- [ ] **Step 1: augur.run live checks**

```bash
echo "=== augur.run new section ==="
curl -s https://augur.run | grep -c 'id="enterprise"'                       # expect 1
echo "=== Talk to Guriqo CTA ==="
curl -s https://augur.run | grep -c 'Talk to Guriqo for deployment'         # expect 1
echo "=== For developers card ==="
curl -s https://augur.run | grep -c '<h3>For developers</h3>'               # expect 1
echo "=== Old Enterprise deployment card gone ==="
curl -s https://augur.run | grep -c '<h3>Enterprise deployment</h3>'        # expect 0
echo "=== New og description ==="
curl -s https://augur.run | grep -c 'connects Claude, GPT, Gemini, and local models'   # expect 1
```

All counts must match.

- [ ] **Step 2: guriqo.com live checks**

```bash
echo "=== guriqo.com title ==="
curl -s https://guriqo.com | grep -c '<title>Guriqo | Enterprise AI deployment for the Augur runtime</title>'   # expect 1
echo "=== old title gone ==="
curl -s https://guriqo.com | grep -c 'Augur Enterprise | Enterprise AI Needs a Brain'   # expect 0
echo "=== old proof line gone ==="
curl -s https://guriqo.com | grep -c 'Built on Augur, the open foundation'   # expect 0
echo "=== new proof line ==="
curl -s https://guriqo.com | grep -c 'We deploy Augur and Augur Enterprise'   # expect 1
echo "=== What we deploy section ==="
curl -s https://guriqo.com | grep -c 'class="what-we-deploy"'                # expect 1
echo "=== Both product cards ==="
curl -s https://guriqo.com | grep -c 'Learn more on augur.run'               # expect 2
```

All counts must match.

- [ ] **Step 3: Manual visual check on both URLs**

Open in a browser, hard-refresh (Cmd+Shift+R):
- `https://augur.run` — confirm new Augur Enterprise section renders with three tiles + "Talk to Guriqo" CTA between FAQ and Get Started; Get Started multi-CTA shows the "For developers" card with GitHub icon.
- `https://guriqo.com` — confirm browser tab title is the new Guriqo title; hero proof line reads "We deploy Augur and Augur Enterprise..."; "What we deploy" section renders right after hero with two product cards.

---

## Self-Review Notes

**Spec coverage:**
- Spec §"In scope" artifact 1 (new Augur Enterprise section) → Task 1 step 2.
- Artifact 2 (replace card 3) → Task 1 step 3.
- Artifact 3 (AI client naming hybrid update — `og:description` only) → Task 1 step 1.
- Artifact 4 (hero proof-line update) → Task 2 step 2.
- Artifact 5 (new "What we deploy" section) → Task 2 step 3.
- Artifact 6 (stale title fix) → Task 2 step 1.
- Spec §"Risks" entry "release.sh title transform doesn't match new strings" → Task 3 (clean up the transforms entirely; verified by Task 4 step 2).
- Spec §"Verification" gates all map to Task 1 step 4 / Task 2 step 4 / Task 3 step 3 / Task 4 step 2 / Task 5 steps 1–2.
- Spec §"Sequencing" step 7 ("user confirmation required before deploy") → Task 4 step 3 (explicit gate).

**Type / name consistency:**
- "Augur Enterprise" used consistently as a proper noun across all tasks.
- Section ID `id="enterprise"` matches the augur.run/#enterprise link in `enterprise.html`'s "Augur Enterprise" card (Task 2 step 3).
- Title string "Guriqo | Enterprise AI deployment for the Augur runtime" appears identically in all 3 meta tags (Task 2 step 1) and in verification (Task 4 step 2 + Task 5 step 2).

**Placeholder scan:** no "TBD", "TODO", "fill in", or "implement later" patterns. Each step has exact content or exact commands.
