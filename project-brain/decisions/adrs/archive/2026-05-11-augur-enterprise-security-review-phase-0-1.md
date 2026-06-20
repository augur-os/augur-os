# Augur Enterprise Security Review — Phase 0 + Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce the Phase 0 foundation and Phase 1 Tier-1 surfaces of the Augur enterprise security review — `docs/security/` public skeleton, the private gap-find working doc, evidence and writeups for the five Tier-1 surfaces (network egress, MCP trust boundary, code execution surface, daemon and persistence, install and supply chain), and arrival at the emergency-pitch-floor checkpoint.

**Architecture:** Document-first, evidence-driven. Each Tier-1 surface follows the same pattern: static analysis → runtime verification → triage (fix < 1 day OR write proposed ADR + accept residual) → distill resolved findings into public docs. The private working doc (`docs/superpowers/security-review/2026-05-augur-runtime-gap-analysis.md`) tracks unresolved gaps; the public docs (`docs/security/`) ship only resolved + accepted-residual content. Phase 2-5 are deferred to a follow-up plan informed by Phase 1 evidence.

**Tech Stack:** Markdown for deliverables; `ripgrep` / `grep` for static analysis; `lsof`, `netstat`, `ps`, `launchctl`, `pgrep`, `find` for runtime evidence; `tcpdump` / `pktap` (macOS) for network-egress capture; Python and Node toolchain audit (`pip show`, `uv lock --check`, `pnpm audit`, `pnpm why`).

**Spec:** `docs/superpowers/specs/2026-05-11-augur-enterprise-security-review-design.md`

---

## Phase 0 — Foundation

### Task 0.1: Create `docs/security/` public skeleton

**Files:**
- Create: `docs/security/README.md`
- Create: `docs/security/threat-model.md`
- Create: `docs/security/enterprise-readiness-packet.md`
- Create: `docs/security/architecture-trust-boundaries.md`
- Create: `docs/security/network-egress-proof.md`
- Create: `docs/security/enterprise-deployment-guide.md`

- [ ] **Step 1: Create README.md as the entry point**

```markdown
---
title: Augur Enterprise Security Documentation
status: in-progress
last_updated: 2026-05-11
---

# Augur Enterprise Security Documentation

Augur is a local-first AI runtime designed for enterprise deployment alongside existing AI dev tools (GitHub Copilot, Cursor, Claude Code). This directory contains the security review and evidence enterprise IT can use to validate Augur for laptop deployment.

## Documents

- [Threat Model](threat-model.md) — adversaries, attack surfaces, mitigations, accepted residual risks.
- [Enterprise Readiness Packet](enterprise-readiness-packet.md) — NIST CSF framing + CIS Controls v8 mapping + regulated-industry non-interaction appendix.
- [Architecture and Trust Boundaries](architecture-trust-boundaries.md) — process model, data flow, file locations.
- [Network Egress Proof](network-egress-proof.md) — reproducible verification of local-only behavior.
- [Enterprise Deployment Guide](enterprise-deployment-guide.md) — admin install / uninstall / audit procedure, claims sheet, FAQ.

## Status

This documentation is built incrementally. Sections marked `TBD` are scheduled for upcoming phases — see [the design spec](../superpowers/specs/2026-05-11-augur-enterprise-security-review-design.md) for the phase plan.
```

- [ ] **Step 2: Create the other five files as stubs with the same frontmatter shape and one-line purpose statement**

Each file gets a top-of-file frontmatter block (`title`, `status: in-progress`, `last_updated: 2026-05-11`) and a single H1 + one-sentence description. Stub bodies say `_Content lands during Phase N of the security review — see [design spec](../superpowers/specs/2026-05-11-augur-enterprise-security-review-design.md)._` where N is 1 for everything except `enterprise-deployment-guide.md` which is Phase 4.

- [ ] **Step 3: Verify the link graph resolves**

Run: `for f in docs/security/*.md; do grep -oE '\[.*\]\(\S+\)' "$f"; done | sort -u`
Expected: every link target points at an existing file (`docs/security/*.md` or `docs/superpowers/specs/...`).

- [ ] **Step 4: Commit**

```bash
git add docs/security/
git commit -m "docs(security): add docs/security/ public skeleton (Phase 0)"
```

---

### Task 0.2: Create private gap-find working doc with per-surface template

**Files:**
- Create: `docs/superpowers/security-review/2026-05-augur-runtime-gap-analysis.md`

- [ ] **Step 1: Verify the directory exists**

Run: `mkdir -p docs/superpowers/security-review`

- [ ] **Step 2: Write the working doc with frontmatter and per-surface template**

```markdown
---
title: Augur Runtime Gap Analysis (Working Doc)
date: 2026-05-11
status: in-progress
x-augur-release: internal
---

# Augur Runtime Gap Analysis — Working Doc

> **Private.** Frontmatter `x-augur-release: internal` excludes this file from public release. As gaps are resolved or accepted, content moves to `docs/security/threat-model.md` and is removed from this file. When this file is empty (or only contains accepted-residual entries already mirrored in public docs), the review is done and this file can be deleted.

## Per-surface entry template

### Surface: <name>

**Claim:** <one sentence — what Augur asserts about this surface>

**Evidence:**
- Static: <file path:line for each finding>
- Runtime: <exact command + captured output>

**Gaps:**
1. <gap description> — severity: low / medium / high — remediation: <fix description OR proposed ADR ref OR `TODO_BUG` marker>

**Status:** open / resolved / accepted-residual

---

## Tier 1 surfaces

(populated by Phase 1 tasks)

## Tier 2 surfaces

(populated by Phase 2 tasks — deferred)

## Tier 3 surfaces

(populated by Phase 3 tasks — deferred)
```

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/security-review/
git commit -m "docs(security): add private gap-find working doc (Phase 0)"
```

---

### Task 0.3: Build CIS Controls v8 + NIST CSF skeleton in enterprise-readiness-packet.md

**Files:**
- Modify: `docs/security/enterprise-readiness-packet.md`

- [ ] **Step 1: Replace the stub body with the framework skeleton**

The file gets these top-level sections (each marked `_Content lands in Phase 1-4._` for now):

```markdown
## Executive summary (NIST CSF framing)

### Identify
_TBD — Phase 4._

### Protect
_TBD — Phase 4._

### Detect
_TBD — Phase 4._

### Respond
_TBD — Phase 4._

### Recover
_TBD — Phase 4._

## Architecture and data flow

_See [architecture-trust-boundaries.md](architecture-trust-boundaries.md)._

## CIS Controls v8 mapping

(All 18 controls listed as subsections; each marked `_TBD — Phase 4._`)

### CIS Control 1 — Inventory and Control of Enterprise Assets
### CIS Control 2 — Inventory and Control of Software Assets
### CIS Control 3 — Data Protection
### CIS Control 4 — Secure Configuration of Enterprise Assets and Software
### CIS Control 5 — Account Management
### CIS Control 6 — Access Control Management
### CIS Control 7 — Continuous Vulnerability Management
### CIS Control 8 — Audit Log Management
### CIS Control 9 — Email and Web Browser Protections
### CIS Control 10 — Malware Defenses
### CIS Control 11 — Data Recovery
### CIS Control 12 — Network Infrastructure Management
### CIS Control 13 — Network Monitoring and Defense
### CIS Control 14 — Security Awareness and Skills Training
### CIS Control 15 — Service Provider Management
### CIS Control 16 — Application Software Security
### CIS Control 17 — Incident Response Management
### CIS Control 18 — Penetration Testing

## Threat model summary

_See [threat-model.md](threat-model.md)._

## Regulated-industry non-interaction appendix

_TBD — Phase 4. Covers CMMC, ITAR / EAR export controls, and trade-secret regimes; states that Augur's local-only architecture makes them non-interactive._

## Operational appendix

_See [enterprise-deployment-guide.md](enterprise-deployment-guide.md)._
```

- [ ] **Step 2: Commit**

```bash
git add docs/security/enterprise-readiness-packet.md
git commit -m "docs(security): add CIS v8 + NIST CSF skeleton (Phase 0)"
```

---

### Task 0.4: Write initial runtime-surface inventory in architecture-trust-boundaries.md

**Files:**
- Modify: `docs/security/architecture-trust-boundaries.md`

- [ ] **Step 1: Inventory the runtime surfaces by reading config and code**

Run these to gather the source-of-truth list, capturing each command + output for the writeup:

```bash
# MCP server topology
sed -n '1,200p' config/system/mcp_servers.yaml

# CLI entry points
ls scripts/aug scripts/augur scripts/augur-mcp scripts/augur-codex-mcp 2>/dev/null

# Daemon entry
find scripts daemon -type f -name "*daemon*" 2>/dev/null

# Dashboard entry
sed -n '1,50p' apps/dashboard/package.json 2>/dev/null || ls apps/dashboard 2>/dev/null

# Hooks
ls .githooks/ 2>/dev/null
sed -n '1,30p' .pre-commit-config.yaml

# Install paths
ls scripts/install.sh scripts/install.ps1 2>/dev/null
```

- [ ] **Step 2: Write the surface inventory with one paragraph per surface**

The file body has these sections, each ~3-6 sentences, no claims yet — just structural description of what exists and where:

```markdown
## Runtime surfaces

### Local MCP servers
### Autoloop daemon
### Dashboard (Next.js, localhost)
### CLI tools
### Install paths
### Hooks
### Client integration files

## Trust boundaries

_TBD — populated by Phase 1 Surface 2 (MCP trust boundary)._

## Data flow

_TBD — populated by Phase 1 evidence._
```

Each surface paragraph names the source-of-truth config file or directory and describes scope (e.g., "Local MCP servers — `augur-core`, `augur-framework`, and per-bundle vault-tier servers (`augur-vault`, `augur-ingest`, …). Topology defined in `config/system/mcp_servers.yaml`. Each server is a stdio subprocess of the AI client; none binds a network port. See [Trust boundaries](#trust-boundaries) for the security rationale.").

- [ ] **Step 3: Commit**

```bash
git add docs/security/architecture-trust-boundaries.md
git commit -m "docs(security): inventory runtime surfaces (Phase 0)"
```

---

### Task 0.5: Phase 0 checkpoint

- [ ] **Step 1: Verify Phase 0 success criteria**

Run: `ls docs/security/`
Expected: 6 files (README.md, threat-model.md, enterprise-readiness-packet.md, architecture-trust-boundaries.md, network-egress-proof.md, enterprise-deployment-guide.md).

Run: `ls docs/superpowers/security-review/`
Expected: `2026-05-augur-runtime-gap-analysis.md` exists.

Run: `grep -c "^### CIS Control" docs/security/enterprise-readiness-packet.md`
Expected: `18`.

- [ ] **Step 2: No code commit needed — Phase 0 already committed task-by-task above. Confirm with `git log --oneline -5`.**

---

## Phase 1 Surface 1 — Network egress

### Task 1.1.1: Static audit — outbound network calls in Python source

**Files:**
- Modify: `docs/superpowers/security-review/2026-05-augur-runtime-gap-analysis.md` (append findings under Surface 1)

- [ ] **Step 1: Grep Python source for network primitives**

Run:
```bash
rg -n --no-heading 'import (requests|httpx|urllib|aiohttp|socket|http\.client|urllib3)' src/ shared-vault/skills/ scripts/ 2>&1 | tee /tmp/augur-py-net.txt
rg -n --no-heading '\b(requests\.|httpx\.|urllib\.|aiohttp\.|socket\.|urlopen|urlretrieve)\(' src/ shared-vault/skills/ scripts/ 2>&1 | tee -a /tmp/augur-py-net.txt
```

Expected: a list of all Python files that import or call network primitives, with line numbers.

- [ ] **Step 2: Triage each finding into one of three buckets**

For each line in `/tmp/augur-py-net.txt`:
- **Always-local** (e.g., `socket.gethostname()`, `urllib.parse`) → not a network call, ignore.
- **User-initiated** (e.g., `requests.get(url)` inside an MCP tool the user invokes by name) → record in working doc as "documented egress, user-initiated only."
- **Ambient** (e.g., a top-level `requests.get()` at import time, or inside an autoloop that runs without user action) → record as a Gap with severity high.

- [ ] **Step 3: Write findings into the working gap-find doc**

Under Surface 1 in `docs/superpowers/security-review/2026-05-augur-runtime-gap-analysis.md`, add a `### Surface: Network egress (static — Python)` entry following the template. Evidence section quotes specific `file:line` references; Gaps section lists every ambient-bucket entry.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/security-review/
git commit -m "docs(security): static audit of Python network calls (Phase 1 Surface 1)"
```

---

### Task 1.1.2: Static audit — Node / Next.js outbound calls

**Files:**
- Modify: `docs/superpowers/security-review/2026-05-augur-runtime-gap-analysis.md`

- [ ] **Step 1: Grep TS/JS source for network primitives**

Run:
```bash
rg -n --no-heading -t ts -t tsx -t js -t jsx '\b(fetch|axios|got|node-fetch|http\.request|https\.request)\(' apps/ packages/ 2>&1 | tee /tmp/augur-js-net.txt
rg -n --no-heading -t ts -t tsx -t js -t jsx "from ['\"](axios|got|node-fetch|undici)" apps/ packages/ 2>&1 | tee -a /tmp/augur-js-net.txt
```

Expected: list of all TS/JS files that use HTTP clients.

- [ ] **Step 2: Audit Next.js-specific ambient egress vectors**

Run:
```bash
rg -n --no-heading 'next/font|@next/font' apps/dashboard 2>&1 | tee /tmp/augur-next-font.txt
rg -n --no-heading 'process\.env\.NEXT_TELEMETRY|next-telemetry' apps/dashboard 2>&1 | tee /tmp/augur-next-telemetry.txt
sed -n '1,80p' apps/dashboard/next.config.* 2>/dev/null
cat apps/dashboard/.env* 2>/dev/null | grep -i telemetry
```

`next/font` may fetch Google Fonts at build time; Next.js has its own telemetry that must be disabled (`NEXT_TELEMETRY_DISABLED=1`).

- [ ] **Step 3: Triage findings into the same three buckets and record in working doc**

Under Surface 1 add `### Surface: Network egress (static — Node/Next.js)`. Special attention to `next/font` and Next.js telemetry — these are **expected** ambient-egress findings; the remediation column should reference `NEXT_TELEMETRY_DISABLED=1` and the choice between `next/font/google` (fetches at build) vs `next/font/local` (no fetch).

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/security-review/
git commit -m "docs(security): static audit of Node/Next.js network calls (Phase 1 Surface 1)"
```

---

### Task 1.1.3: Static audit — install-time outbound calls

**Files:**
- Modify: `docs/superpowers/security-review/2026-05-augur-runtime-gap-analysis.md`

- [ ] **Step 1: Audit install scripts**

Run:
```bash
sed -n '1,200p' scripts/install.sh
sed -n '1,200p' scripts/install.ps1
rg -n 'curl|wget|Invoke-WebRequest|iwr|Net\.WebClient' scripts/install.sh scripts/install.ps1
```

Note every outbound URL referenced; classify as binary-fetch (release tarball), dependency-fetch (pip / pnpm bootstrapping), or telemetry.

- [ ] **Step 2: Audit Python dependency install behavior**

Run:
```bash
grep -E '^(dependencies|\[project\]|\[tool\.uv|\[tool\.poetry)' pyproject.toml
sed -n '1,20p' uv.lock 2>/dev/null
# look for pip extras that install at import-time
rg -n 'pip\.main|subprocess.*pip install' src/ scripts/
```

- [ ] **Step 3: Audit Node dependency install behavior**

Run:
```bash
rg -n '"postinstall"|"preinstall"|"install"' apps/ packages/ -g 'package.json'
pnpm why -r 2>/dev/null | head -50
```

Lifecycle scripts (`postinstall`) are a common ambient-egress vector.

- [ ] **Step 4: Write findings into working doc; commit**

Under Surface 1 add `### Surface: Network egress (static — install)`. Specifically call out: every URL embedded in `install.sh` / `install.ps1`, every package with `postinstall` scripts, and any binary fetches.

```bash
git add docs/superpowers/security-review/
git commit -m "docs(security): static audit of install-time network calls (Phase 1 Surface 1)"
```

---

### Task 1.1.4: Runtime evidence — reproducible network-egress proof

**Files:**
- Modify: `docs/security/network-egress-proof.md`

- [ ] **Step 1: Write the reproducible-capture procedure**

The document captures a procedure an enterprise IT auditor can run on their own laptop and verify. Structure:

```markdown
## Method 1: Per-process connection inventory (macOS)

Run Augur for at least 10 minutes with all features the pilot team will use:
- Start the daemon: `aug daemon start`
- Open the dashboard: `aug dashboard`
- Issue a representative set of MCP tools through the AI client of choice.

Then capture the per-process connection inventory:

\`\`\`bash
PIDS=$(pgrep -f 'augur|aug ' | tr '\n' ',' | sed 's/,$//')
lsof -nP -i -p "$PIDS" 2>/dev/null | tee /tmp/augur-lsof.txt
\`\`\`

**Expected output:** only `LISTEN` lines should appear, and they should all be on `127.0.0.1:3000` (the dashboard) or unix sockets. No `ESTABLISHED` connections to non-loopback IPs unless the user has actively invoked a feature that documents egress (see [threat-model.md](threat-model.md) — Documented egress).

## Method 2: System-wide capture with pktap (macOS) or tcpdump

Capture all outbound non-loopback traffic from any augur-named process for 10 minutes:

\`\`\`bash
sudo tcpdump -i any -nn -w /tmp/augur-egress.pcap \
  "not host 127.0.0.1 and not host ::1" &
TCPDUMP_PID=$!
# ... exercise Augur for 10 minutes ...
kill -INT $TCPDUMP_PID
\`\`\`

Then filter for augur-process traffic only:

\`\`\`bash
sudo dtrace -n 'syscall::connect:entry /pid == $target/ { ... }' -p "$PID"
# (macOS DTrace; equivalent eBPF on Linux)
\`\`\`

**Expected output:** zero packets in `/tmp/augur-egress.pcap` originating from augur-named PIDs, except for any egress documented in `threat-model.md`.

## Method 3: Little Snitch / Lulu profile (macOS user-facing tool)

For end-users who use Little Snitch or Lulu, the following per-process rule pattern is recommended:

\`\`\`
Process: /usr/local/bin/augur (and child processes)
Default: Deny all outgoing
Allowlist: <empty by default>
\`\`\`
```

- [ ] **Step 2: Run the procedure yourself on the dev machine, capture actual output**

Run Methods 1 and 2 on your own laptop while Augur is running. Paste actual output blocks into the document; redact anything sensitive.

- [ ] **Step 3: Compare actual output to the "expected output" claims**

If unexpected non-loopback traffic appears, that's a Phase 1 finding — record in working doc as a Gap, do **not** declare the proof clean.

- [ ] **Step 4: Commit**

```bash
git add docs/security/network-egress-proof.md docs/superpowers/security-review/
git commit -m "docs(security): runtime network-egress proof procedure (Phase 1 Surface 1)"
```

---

### Task 1.1.5: Triage gaps and distill into threat-model.md

**Files:**
- Modify: `docs/security/threat-model.md`
- Modify: `docs/superpowers/security-review/2026-05-augur-runtime-gap-analysis.md`

- [ ] **Step 1: For each Surface 1 Gap in the working doc, decide one of:**

- **Fix now** (< 1 day, single-file change, no architectural impact) — make the fix, log to working doc.
- **Document as accepted-residual** — write rationale, log to working doc, mirror into `threat-model.md`.
- **Defer to follow-up plan** (architectural — needs ADR) — write a proposed ADR stub, link from working doc.

- [ ] **Step 2: For "fix now" items, apply the fix**

Example: if `NEXT_TELEMETRY_DISABLED=1` is missing from the dashboard's `.env`, add it; commit separately. If a postinstall script runs `curl`, replace with a pinned-SHA fetch or remove.

- [ ] **Step 3: For accepted-residual items, write a "Documented egress" section in `threat-model.md`**

Structure:

```markdown
## Documented egress (Surface 1)

Augur only makes outbound network calls in these documented cases:

1. **<feature>** — when the user invokes `<command>`, Augur calls `<domain>` for `<purpose>`. Disable with `<config option>`.
2. ...

All other paths have been audited and show no outbound calls — see [network-egress-proof.md](network-egress-proof.md).
```

- [ ] **Step 4: Commit**

```bash
git add docs/security/threat-model.md docs/superpowers/security-review/ \
        $(any-files-touched-by-fix-now-items)
git commit -m "docs(security): triage network egress findings, document residual (Phase 1 Surface 1)"
```

---

## Phase 1 Surface 2 — MCP trust boundary

### Task 1.2.1: Document MCP server topology

**Files:**
- Modify: `docs/security/architecture-trust-boundaries.md`

- [ ] **Step 1: Add the "Trust boundaries" section**

```markdown
## Trust boundaries

Augur's local MCP servers (`augur-core`, `augur-framework`, vault-tier bundles enumerated in [`config/system/mcp_servers.yaml`](../../config/system/mcp_servers.yaml)) are **stdio-only subprocesses** of the AI client. The trust boundary is:

| Property | Value |
|---|---|
| Transport | Standard input / standard output pipes |
| Network listener | None |
| Authentication | None — inherits parent-process trust |
| Process model | Subprocess of the AI client; dies with parent |
| User context | Same as the user running the AI client |

**Why no authentication.** A local-user process that can talk to Augur's MCP server can already do anything that user can do (read user files, run user commands, exit the user's session). Adding password authentication or token authentication would not increase security — it would only add friction. The trust boundary is the *user account*, not the *MCP server*.

This is the same trust model used by Copilot's IDE extension, Cursor, and Claude Code. Augur's runtime is no different in principle.

**Verification:** run `lsof -nP -i -p $(pgrep -f augur-core)` — expect zero `LISTEN` entries.
```

- [ ] **Step 2: Run the verification command and paste output**

Run: `lsof -nP -i -p $(pgrep -f augur-core)`
Expected: zero output, or only loopback `LISTEN` entries.

- [ ] **Step 3: Commit**

```bash
git add docs/security/architecture-trust-boundaries.md
git commit -m "docs(security): document MCP trust boundary (Phase 1 Surface 2)"
```

---

### Task 1.2.2: Write the "no auth, no listener" rationale into the readiness packet

**Files:**
- Modify: `docs/security/enterprise-readiness-packet.md` (CIS Control 6 — Access Control Management)

- [ ] **Step 1: Replace the CIS Control 6 stub with the rationale**

```markdown
### CIS Control 6 — Access Control Management

**Posture:** Augur's local MCP servers run as stdio subprocesses of the AI client. They do not bind network ports and do not authenticate callers. Access control is delegated to the operating system's user-account boundary: any process that can communicate with Augur is already running as the user. This is the same model used by GitHub Copilot's IDE extension, Cursor, and Claude Code.

**Evidence:** see [architecture-trust-boundaries.md — Trust boundaries](architecture-trust-boundaries.md#trust-boundaries).

**Residual risk:** A second local process running as the same user can invoke MCP tools. The mitigation is that the same process can already do anything the user can do; the MCP server adds no privilege. Accepted residual.
```

- [ ] **Step 2: Commit**

```bash
git add docs/security/enterprise-readiness-packet.md
git commit -m "docs(security): map MCP trust model to CIS Control 6 (Phase 1 Surface 2)"
```

---

### Task 1.2.3: Surface 2 verification + checkpoint

- [ ] **Step 1: Add the verification command to the deployment guide stub**

In `docs/security/enterprise-deployment-guide.md`, add a section:

```markdown
## Verifying MCP trust boundary (10 seconds)

Run while Augur is active:

\`\`\`bash
lsof -nP -i -p $(pgrep -f 'augur-(core|framework)' | tr '\n' ',' | sed 's/,$//') 2>/dev/null
\`\`\`

Expected: no output. If any `LISTEN` line appears, the trust-model claim is broken — file a vulnerability report.
```

- [ ] **Step 2: Commit**

```bash
git add docs/security/enterprise-deployment-guide.md
git commit -m "docs(security): add MCP trust-boundary verification command (Phase 1 Surface 2)"
```

---

## Phase 1 Surface 3 — Code execution surface

### Task 1.3.1: Inventory all script-execution paths

**Files:**
- Modify: `docs/superpowers/security-review/2026-05-augur-runtime-gap-analysis.md`

- [ ] **Step 1: Inventory MCP tools that execute shell or scripts**

Run:
```bash
rg -n --no-heading 'subprocess\.(run|Popen|check_call|check_output)|os\.system|os\.popen' src/ shared-vault/skills/ 2>&1 | tee /tmp/augur-exec.txt
rg -n --no-heading 'shell=True' src/ shared-vault/skills/ 2>&1 | tee -a /tmp/augur-exec.txt
```

- [ ] **Step 2: Inventory autoloop and skill callables**

Run:
```bash
rg -n --no-heading '^callable:' shared-vault/skills/*/SKILL.md
rg -n --no-heading '^callable:' shared-vault/skills/*/commands/*.md 2>/dev/null
```

Each `callable:` is a script that runs when the command is invoked.

- [ ] **Step 3: Inventory hooks**

Run:
```bash
ls .githooks/
cat .pre-commit-config.yaml | grep -E '^\s+- id:'
rg -n 'PreToolUse|PostToolUse|UserPromptSubmit' .claude/settings.json .codex/hooks.json 2>/dev/null
```

- [ ] **Step 4: Write findings into working doc**

Under Surface 3 add `### Surface: Code execution`. The honest disclosure is: Augur has **no sandbox**; skills and autoloops run with full user privilege. The mitigations are: (a) skills come from a known source (the user's vault or the public augur-os skill repo), (b) MCP tools that execute shell run only when the AI client invokes them on behalf of the user.

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/security-review/
git commit -m "docs(security): inventory code execution paths (Phase 1 Surface 3)"
```

---

### Task 1.3.2: Distill code-execution honest disclosure into threat-model.md

**Files:**
- Modify: `docs/security/threat-model.md`

- [ ] **Step 1: Add the "Code execution surface" section**

```markdown
## Code execution surface

Augur skills, autoloops, MCP tools, and hooks execute with the same privilege as the user running Augur. There is no sandbox between an installed skill and the user's filesystem.

**Threat:** a malicious or compromised skill could read user files, modify the vault, or exfiltrate data.

**Mitigations:**
- Skills are installed from a known source (the user's vault directory or the public augur-os skill repo); installation is an explicit user action.
- MCP tools that execute shell commands do so only when the AI client invokes them on behalf of the user; the user sees the tool call before it runs.
- Hooks listed in `.githooks/` and `.pre-commit-config.yaml` run at git commit time; their content is in the repo and reviewable.

**Accepted residual:** a user who installs a malicious skill from an untrusted source has the same exposure as installing any other software from an untrusted source. Enterprise deployments should pin the skill source to a vetted internal repo (see [enterprise-deployment-guide.md — Restricted installations](enterprise-deployment-guide.md)).

**Proposed follow-up (separate plan):** `--enterprise` policy mode that requires skills to be on an allowlist and disables auto-discovered script execution.
```

- [ ] **Step 2: Commit**

```bash
git add docs/security/threat-model.md
git commit -m "docs(security): document code-execution surface and residual risk (Phase 1 Surface 3)"
```

---

### Task 1.3.3: Draft proposed ADR for `--enterprise` policy mode

**Files:**
- Create: `docs/adrs/ADR-NNN-enterprise-policy-mode.md` (use next-available ADR number)

- [ ] **Step 1: Determine the next ADR number**

Run: `ls docs/adrs/ | grep -E '^ADR-[0-9]+' | sed -E 's/ADR-([0-9]+).*/\1/' | sort -n | tail -1`
Expected: `725` (the security-review index ADR). Use `726` for this proposed policy-mode ADR; substitute `NNN` accordingly throughout this task.

- [ ] **Step 2: Write the ADR with status `Proposed`**

```markdown
---
id: ADR-NNN
title: Enterprise Policy Mode for Restricted Skill Execution
status: Proposed
date: 2026-05-11
---

# ADR-NNN: Enterprise Policy Mode for Restricted Skill Execution

## Status

Proposed.

## Context

The Augur enterprise security review (see [spec](../superpowers/specs/2026-05-11-augur-enterprise-security-review-design.md)) identified that skills, autoloops, and MCP tools execute with full user privilege and no sandbox. This is acceptable for the local-only personal-use case but may not meet enterprise IT requirements when Augur is deployed on managed laptops.

## Decision

Introduce an `--enterprise` flag (or equivalent config setting) that, when active:

1. Restricts skill discovery to an allowlist file (`config/enterprise/skills.allowlist.yaml`).
2. Disables auto-execution of skill callables that are not on the allowlist.
3. Disables network-touching skills entirely unless explicitly allowlisted.
4. Disables the autoloop daemon's auto-mutation passes; loops run in report-only mode.
5. Writes a structured audit log entry for every skill invocation, suitable for SIEM forwarding.

## Consequences

Builds on the existing skill registry and autoloop infrastructure. Implementation is deferred until enterprise pilots specifically require it; the security review documents this as a proposed follow-up rather than a v1 requirement.
```

- [ ] **Step 3: Commit**

```bash
git add docs/adrs/ADR-NNN-enterprise-policy-mode.md
git commit -m "docs(adr): propose ADR-NNN enterprise policy mode (Phase 1 Surface 3)"
```

---

### Task 1.3.4: Surface 3 checkpoint

- [ ] **Step 1: Cross-reference the ADR from threat-model.md**

Update the threat-model.md "Proposed follow-up" line to reference the new ADR number:

`**Proposed follow-up:** [ADR-NNN: Enterprise Policy Mode for Restricted Skill Execution](../adrs/ADR-NNN-enterprise-policy-mode.md) (Proposed).`

- [ ] **Step 2: Commit**

```bash
git add docs/security/threat-model.md
git commit -m "docs(security): cross-reference ADR-723 from threat model (Phase 1 Surface 3)"
```

---

## Phase 1 Surface 4 — Daemon and persistence

### Task 1.4.1: Inventory daemon process model

**Files:**
- Modify: `docs/superpowers/security-review/2026-05-augur-runtime-gap-analysis.md`

- [ ] **Step 1: Find the launchd plist (macOS) and systemd unit (Linux), if any**

Run:
```bash
find scripts daemon src -type f \( -name '*.plist' -o -name '*.service' -o -name '*.target' \) 2>/dev/null
rg -n 'launchctl|systemctl|systemd' scripts/ src/ 2>&1 | head -30
```

- [ ] **Step 2: Find where daemon state lives at runtime**

Run:
```bash
rg -n 'get_runtime_dir|Application Support/Augur|\.augur' src/config/paths.py 2>/dev/null
rg -n 'pidfile|pid_file|\.pid' src/ scripts/ 2>&1 | head -20
```

- [ ] **Step 3: Document findings**

Under Surface 4 add `### Surface: Daemon and persistence`. Evidence:
- Plist or service-unit file paths.
- Runtime state directory (resolved from `get_runtime_dir()`).
- PID file location.
- Whether the daemon auto-starts on login (launchd `RunAtLoad`, systemd `WantedBy=default.target`).

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/security-review/
git commit -m "docs(security): inventory daemon process model (Phase 1 Surface 4)"
```

---

### Task 1.4.2: Document daemon-removal procedure for IT auditors

**Files:**
- Modify: `docs/security/enterprise-deployment-guide.md`

- [ ] **Step 1: Add the "Daemon inspection and removal" section**

```markdown
## Daemon inspection and removal

### macOS

Inspect:

\`\`\`bash
launchctl list | grep augur
ls ~/Library/LaunchAgents/ | grep augur
ls "$HOME/Library/Application Support/Augur/state/" 2>/dev/null
\`\`\`

Stop and remove (without uninstalling Augur):

\`\`\`bash
launchctl bootout "gui/$UID" ~/Library/LaunchAgents/dev.augur.daemon.plist
rm ~/Library/LaunchAgents/dev.augur.daemon.plist
\`\`\`

### Linux (systemd user units)

Inspect:

\`\`\`bash
systemctl --user status augur-daemon.service 2>/dev/null
ls ~/.config/systemd/user/ | grep augur
\`\`\`

Stop and remove:

\`\`\`bash
systemctl --user stop augur-daemon.service
systemctl --user disable augur-daemon.service
rm ~/.config/systemd/user/augur-daemon.service
\`\`\`

### Verification

After removal:

\`\`\`bash
pgrep -fa augur || echo "no augur processes"
\`\`\`

Expected: `no augur processes`.
```

(If the inventory in Task 1.4.1 found different file names or paths, use the actual names found.)

- [ ] **Step 2: Commit**

```bash
git add docs/security/enterprise-deployment-guide.md
git commit -m "docs(security): document daemon removal procedure (Phase 1 Surface 4)"
```

---

### Task 1.4.3: Distill daemon model into architecture-trust-boundaries.md

**Files:**
- Modify: `docs/security/architecture-trust-boundaries.md`

- [ ] **Step 1: Append the "Daemon process model" section**

```markdown
## Daemon process model

The Augur autoloop daemon is a user-space process registered with launchd (macOS) or systemd user units (Linux). It:

- Runs as the user, not root.
- Auto-starts on login if installed via `aug daemon install`; the install step is opt-in.
- Writes state to `get_runtime_dir()` (`~/Library/Application Support/Augur/state/` on macOS).
- Writes logs to `get_logs_dir()` (`~/Library/Logs/Augur/` on macOS).
- Listens on no network ports; communicates with the rest of Augur via local IPC (unix sockets or files).

**Removability:** see [enterprise-deployment-guide.md — Daemon inspection and removal](enterprise-deployment-guide.md#daemon-inspection-and-removal). The daemon can be stopped and unregistered without uninstalling Augur itself.
```

- [ ] **Step 2: Commit**

```bash
git add docs/security/architecture-trust-boundaries.md
git commit -m "docs(security): document daemon process model (Phase 1 Surface 4)"
```

---

## Phase 1 Surface 5 — Install and supply chain

### Task 1.5.1: Audit install scripts for unsafe patterns

**Files:**
- Modify: `docs/superpowers/security-review/2026-05-augur-runtime-gap-analysis.md`

- [ ] **Step 1: Read install.sh and install.ps1 end-to-end**

Run:
```bash
sed -n '1,400p' scripts/install.sh
sed -n '1,400p' scripts/install.ps1
```

For each script, log:
- URLs fetched (with what tool — `curl`, `wget`, `iwr`).
- Whether `curl | sh` (or PowerShell equivalent) is used.
- Whether fetched artifacts have SHA-256 verification.
- Whether the script requires sudo / admin rights.

- [ ] **Step 2: Write findings under Surface 5 in working doc**

If `curl | sh` is in use without SHA-256 verification, this is a Gap (severity: medium, fix: pin a release SHA or document the trust-on-first-use model honestly).

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/security-review/
git commit -m "docs(security): audit install scripts (Phase 1 Surface 5)"
```

---

### Task 1.5.2: Audit Python dependency provenance

**Files:**
- Modify: `docs/superpowers/security-review/2026-05-augur-runtime-gap-analysis.md`

- [ ] **Step 1: Enumerate direct + transitive dependencies**

Run:
```bash
uv tree 2>/dev/null | head -100
# fallback if uv tree not available:
pip list --format=freeze 2>/dev/null | head -50
```

- [ ] **Step 2: Check pinning posture in `uv.lock`**

Run:
```bash
sed -n '1,40p' uv.lock 2>/dev/null
grep -c '^name = ' uv.lock 2>/dev/null
grep -c '^version = ' uv.lock 2>/dev/null
```

`uv.lock` should pin every dependency to an exact version with a hash. Confirm.

- [ ] **Step 3: Identify any dependencies with known concerns**

For each top-level dependency, briefly note its purpose and a one-line provenance comment (e.g., "Pydantic — schema validation — pypi/anchor: Samuel Colvin"). Flag any unmaintained or low-trust packages.

- [ ] **Step 4: Write findings under Surface 5 in working doc; commit**

```bash
git add docs/superpowers/security-review/
git commit -m "docs(security): audit Python dependency provenance (Phase 1 Surface 5)"
```

---

### Task 1.5.3: Audit Node dependency provenance

**Files:**
- Modify: `docs/superpowers/security-review/2026-05-augur-runtime-gap-analysis.md`

- [ ] **Step 1: Enumerate Node dependencies**

Run:
```bash
pnpm list -r --depth 0 2>/dev/null | head -80
```

- [ ] **Step 2: Check `pnpm-lock.yaml` pinning**

Run:
```bash
head -40 pnpm-lock.yaml
grep -c '^  /' pnpm-lock.yaml
```

`pnpm-lock.yaml` pins every dependency by exact version + integrity hash. Confirm.

- [ ] **Step 3: Run audit**

Run:
```bash
pnpm audit --prod 2>&1 | tee /tmp/augur-pnpm-audit.txt
```

Note any reported vulnerabilities; classify high-severity findings as Gaps.

- [ ] **Step 4: Write findings under Surface 5 in working doc; commit**

```bash
git add docs/superpowers/security-review/
git commit -m "docs(security): audit Node dependency provenance (Phase 1 Surface 5)"
```

---

### Task 1.5.4: Document supply-chain posture in threat-model.md

**Files:**
- Modify: `docs/security/threat-model.md`

- [ ] **Step 1: Add the "Supply chain" section**

```markdown
## Supply chain

Augur is installed via one of:

1. **`pip install augur-os`** — Python package from PyPI; all dependencies pinned via `uv.lock` with integrity hashes; verifiable with `uv lock --check`.
2. **`pnpm install`** — Node dependencies for the dashboard; all pinned via `pnpm-lock.yaml` with integrity hashes; verifiable with `pnpm install --frozen-lockfile`.
3. **`scripts/install.sh` / `scripts/install.ps1`** — bootstrap scripts that pull a tagged release from GitHub Releases. _<Document whether SHA-256 verification is currently performed; if not, this is a known gap — see [proposed remediation](../superpowers/specs/2026-05-11-augur-enterprise-security-review-design.md).>_

**Direct dependency count:** _<from `uv tree` and `pnpm list`>_.

**Transitive dependency count:** _<from lock files>_.

**Postinstall lifecycle scripts:** _<list any packages with postinstall hooks>_.

**Provenance:** Augur itself is published from the `augur-os/augur-os` repo. Release artifacts are tagged in the GitHub Releases UI. _<Document the release-signing posture: currently signed / planned to sign / unsigned.>_

**Restricted-install posture:** enterprise deployments can pin to a specific release SHA and disable the install script; see [enterprise-deployment-guide.md — Restricted installations](enterprise-deployment-guide.md).
```

(Fill in the `<...>` placeholders from the actual evidence captured in Tasks 1.5.1-1.5.3.)

- [ ] **Step 2: Commit**

```bash
git add docs/security/threat-model.md
git commit -m "docs(security): document supply-chain posture (Phase 1 Surface 5)"
```

---

### Task 1.5.5: Surface 5 checkpoint

- [ ] **Step 1: Cross-check that the working doc Surface 5 entries are all triaged**

Every Gap under Surface 5 must be either:
- fixed (commit reference logged), or
- accepted-residual (rationale mirrored in `threat-model.md`), or
- deferred to a follow-up plan (linked from working doc).

No open Gaps allowed in Surface 5.

- [ ] **Step 2: Commit any final triage edits**

```bash
git add docs/superpowers/security-review/ docs/security/
git commit -m "docs(security): triage Surface 5 gaps to closure (Phase 1 Surface 5)"
```

---

## Phase 1 closing — Consolidation and emergency-pitch-floor checkpoint

### Task 1.6.1: Move all resolved gap-find entries from working doc to public docs

**Files:**
- Modify: `docs/superpowers/security-review/2026-05-augur-runtime-gap-analysis.md`
- Modify: `docs/security/threat-model.md`

- [ ] **Step 1: Walk each Surface 1-5 entry in the working doc**

For each entry with `Status: resolved` or `Status: accepted-residual`:
- Confirm the corresponding content is in `docs/security/threat-model.md`.
- Remove the entry from the working doc (or collapse to a one-line "moved to public docs on YYYY-MM-DD" stub if you want a trail).

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/security-review/ docs/security/threat-model.md
git commit -m "docs(security): distill Phase 1 findings into public threat model (Phase 1 closing)"
```

---

### Task 1.6.2: Write the claim summary in docs/security/README.md

**Files:**
- Modify: `docs/security/README.md`

- [ ] **Step 1: Replace the "Status: in-progress" body with a claim summary**

```markdown
## Claim summary (as of <YYYY-MM-DD>)

Five claims, each with a one-line verification a reader can run on their own laptop:

1. **No unsolicited outbound network traffic.** Verify: `lsof -nP -i -p $(pgrep -f augur)` returns no non-loopback `ESTABLISHED` lines. Full procedure: [network-egress-proof.md](network-egress-proof.md).
2. **No network listener on the local MCP server.** Verify: `lsof -nP -i -p $(pgrep -f augur-core)` returns no `LISTEN` lines. Rationale: [architecture-trust-boundaries.md](architecture-trust-boundaries.md#trust-boundaries).
3. **User-privilege only — no root or admin.** Verify: `ps -o user= -p $(pgrep -f augur)` returns the user's own username for every process. Details: [architecture-trust-boundaries.md](architecture-trust-boundaries.md#daemon-process-model).
4. **Pinned and integrity-hashed dependencies.** Verify: `uv lock --check && pnpm install --frozen-lockfile` both succeed. Details: [threat-model.md — Supply chain](threat-model.md#supply-chain).
5. **Removable without leaving artifacts.** Verify: follow [enterprise-deployment-guide.md — Daemon inspection and removal](enterprise-deployment-guide.md#daemon-inspection-and-removal); then `pgrep -fa augur` returns nothing.

For the full review, see [enterprise-readiness-packet.md](enterprise-readiness-packet.md) (Phase 4 — in progress).
```

- [ ] **Step 2: Commit**

```bash
git add docs/security/README.md
git commit -m "docs(security): claim summary on README (Phase 1 closing)"
```

---

### Task 1.6.3: Self-verify pitch-readiness against emergency-floor success criteria

- [ ] **Step 1: Verify each success criterion**

For each item below, confirm and write the result inline in `docs/superpowers/security-review/2026-05-augur-runtime-gap-analysis.md` under a new "Phase 1 emergency-floor verification" section.

1. `docs/security/threat-model.md` exists, committed, contains Surface 1-5 sections with resolved + accepted-residual entries.
2. Every Tier 1 claim in `docs/security/README.md` has a verification command.
3. The private gap-find working doc has zero open Tier 1 Gaps (everything is resolved, accepted-residual, or deferred to a follow-up plan).
4. `docs/security/network-egress-proof.md` contains a reproducible procedure and at least one actual captured output block.
5. `docs/security/architecture-trust-boundaries.md` contains the "Trust boundaries" and "Daemon process model" sections.

- [ ] **Step 2: If any criterion fails, fix before declaring done**

The point of the checkpoint is to refuse to advance with unresolved Tier 1 work. If a criterion fails, return to the relevant surface, fix, re-run.

- [ ] **Step 3: Commit the verification record**

```bash
git add docs/superpowers/security-review/
git commit -m "docs(security): Phase 1 emergency-floor checkpoint verified (Phase 1 closing)"
```

---

### Task 1.6.4: Phase 1 wrap

- [ ] **Step 1: Confirm git history shows clean per-task commits**

Run: `git log --oneline 2026-05-11..HEAD | head -40`
Expected: ~25-30 commits, each scoped to one task, all prefixed `docs(security):` or `docs(adr):`.

- [ ] **Step 2: Write a brief Phase 1 wrap entry in the working doc**

Append to `docs/superpowers/security-review/2026-05-augur-runtime-gap-analysis.md`:

```markdown
## Phase 1 wrap (YYYY-MM-DD)

Phase 1 (Tier-1 surfaces) closed. Emergency-pitch floor reached.

- Surface 1 (network egress): <N gaps resolved, M accepted-residual, K deferred>.
- Surface 2 (MCP trust boundary): rationale documented in `architecture-trust-boundaries.md`; mapped to CIS Control 6.
- Surface 3 (code execution): honest disclosure in `threat-model.md`; ADR-723 proposed.
- Surface 4 (daemon and persistence): process model and removal procedure documented.
- Surface 5 (install and supply chain): <summary>.

**Open ADRs from this phase:** ADR-NNN (Proposed; number assigned at execution time).
**Next:** follow-up plan for Phase 2-5 (Tier 2/3 surfaces + packet consolidation).
```

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/security-review/
git commit -m "docs(security): Phase 1 wrap (Phase 1 closing)"
```

---

## What this plan does NOT cover

- Phase 2 (Tier-2 surfaces): logging and audit, file locations and privilege, vault data classification, dashboard binding. Deferred to a follow-up plan written after Phase 1 evidence is in hand.
- Phase 3 (Tier-3 surfaces): update mechanism, telemetry posture, optional admin features.
- Phase 4 (Public-packet consolidation): filling the CIS Controls v8 mapping with mechanical references to Phase 1-3 evidence, writing the NIST CSF executive summary, writing the regulated-industry non-interaction appendix, writing the deployment guide.
- Phase 5 (Pitch curation): customer-specific cheat sheet, optional slide deck.
- Implementing the proposed enterprise-policy-mode ADR (drafted in Task 1.3.3). Separate plan.

The follow-up plan should be written immediately after this plan's Task 1.6.4 wrap commit, informed by what Phase 1 actually surfaced.
