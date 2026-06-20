---
title: Augur Runtime Security Review for Enterprise Deployment
date: 2026-05-11
status: design
owner: gsannikov
deliverable_visibility: public-via-augur-os-repo (working gap-find is private)
framework: CIS Controls v8 + NIST CSF
---

# Augur Runtime Security Review for Enterprise Deployment

## Context and goal

Augur is being pitched to an enterprise pilot team that today uses GitHub Copilot as their primary AI dev tool. Their enterprise IT has approved Copilot for that team, which sets the bar: an AI dev-tool that runs on the laptop and assists with code is acceptable in principle. The goal of this review is to ensure enterprise IT will not reject Augur runtime installation, and to produce reusable enterprise-readiness documentation that ships in the public `augur-os` repo so any enterprise customer can verify the same claims.

**Strategic frame.** Augur is strictly easier than Copilot to defend on data residency (local-first, no Augur-managed API key in the normal path, no Augur cloud service) and prompt confidentiality (normal prompts route through the user's native AI client). Direct model/API access is a rare named exception and must be documented separately. Where Augur's surface is *larger* than Copilot's is endpoint behavior: skills can execute scripts, the autoloop daemon runs in the background, autoloops mutate files, the MCP exposes ~150 tools that touch the vault. That is where enterprise IT will focus, and that is where this review concentrates.

**On the local-MCP-no-auth concern.** Augur's local MCP servers (`augur-core`, `augur-framework`, vault-tier bundles) are stdio-only subprocesses launched by the AI client. They have no network listener and run under the same user as the parent process. This is the same trust model used by Copilot's IDE extension, Cursor, and Claude Code. The correct response to enterprise IT on this point is a written rationale ("any local-user process is already trusted; the MCP adds no privilege"), not retrofitted authentication.

## Scope

### In scope

- Local MCP servers: `augur-core`, `augur-framework`, vault-tier bundle servers (`augur-vault`, `augur-ingest`, others enumerated by `config/system/mcp_servers.yaml`).
- Autoloop daemon and the autoloops it schedules.
- Dashboard (Next.js, `localhost:3000`).
- CLI: `aug`, `augur`, `augur-mcp`, `augur-codex-mcp`.
- Install paths: `install.sh`, `install.ps1`, `pip install augur-os`, `pnpm install`, GitHub release artifacts.
- Hooks: `.githooks/`, `.pre-commit-config.yaml`, `.claude/settings.json`, `.codex/hooks.json`.
- Client integration files generated into `.claude/`, `.codex/`, `.gemini/`, `.cursor/`, and Copilot skill packs.

### Out of scope

- Augur's public website, the public GitHub repo's CI infrastructure.
- Optional Brain features that would require cloud (podcast and YouTube summarization, URL ingest of remote pages). These are documented as opt-in, off-by-default, and explicitly called out as "do not enable in regulated-enterprise deployment" in the deployment guide.
- User-authored skill contents. The review documents the *sandbox skills run in*, not what individual skills do.
- AI-client backends (Anthropic, OpenAI, Microsoft for Copilot). Those are the client vendor's responsibility, not Augur's.

## Threat model

### Adversaries we model

1. **Network attacker on the developer's network.** Can they reach Augur from outside the laptop? Required answer: no listener exposed; runtime evidence required.
2. **Malicious local process running as the same user.** Can it abuse Augur for privilege amplification beyond what the user already has? Required answer: no — same-user processes are already trusted; the MCP adds no new privilege.
3. **Malicious skill or compromised dependency in the supply chain.** Can a compromised pip/npm/skill package run code on install or at runtime, and what is the blast radius? Required answer: same as any user-installed software; mitigations include SHA-pinned releases, signed binaries plan, no `curl | sh`.
4. **Curious-but-not-malicious developer.** They install Augur on a corp laptop and ingest confidential code into the vault. Required answer: documented exclude-by-roots, classification policy file (future work), opt-in indexing.
5. **Enterprise IT auditor verifying claims.** Every claim must be verifiable with a command they can run on the laptop without trusting our word.

### Adversaries we explicitly do NOT model

- Compromised user account (same posture as Copilot — out of scope at the tool layer).
- Physical access to an unlocked laptop.
- The AI client vendor's backend.

## Tier breakdown of runtime surfaces

### Tier 1 — would-block-deployment

1. **Network egress.** Static + runtime proof Augur makes zero unsolicited outbound calls; explicit list of every domain Augur *can* call (only when the user invokes a feature); admin-configurable egress allowlist; future `--airgap` mode that fails closed.
2. **MCP trust boundary.** Written rationale that stdio + parent-PID + no listener = same model as Copilot, Cursor, Claude Code. Explicit "any local-user process is already trusted" framing. No authentication is added.
3. **Code execution surface.** What can a skill, autoloop, or MCP tool execute? Document the current sandbox (or absence thereof), identify which operations require user confirmation, propose an `--enterprise` policy mode (separate plan) that disables auto-discovered script execution and requires skills to be on an allowlist.
4. **Daemon and persistence.** What runs in background, where the launchd / systemd-user entry lives, how an admin sees and stops it, removability.
5. **Install and supply-chain integrity.** Where binaries come from (pypi, pnpm, GitHub releases), SHA-pinning posture, signed-release plan, `install.sh` no-`curl | sh` pattern, dependency provenance.

### Tier 2 — expected enterprise hygiene

6. **Logging and audit.** What is logged, where, in what format, SIEM-forwardable structure.
7. **File locations and privilege.** Everything in user-writable paths; no admin or root needed; XDG-style paths on Linux, `~/Library/Application Support/Augur/` and `~/Library/Logs/Augur/` on macOS, AppData equivalents on Windows.
8. **Vault data classification.** Exclude-by-roots config, allowlist roots, classification-tagging hooks; propose `classification.yaml` policy file (future work).
9. **Dashboard binding.** Localhost-only on `:3000`; never `0.0.0.0`; verification command.

### Tier 3 — polish

10. **Update mechanism.** Opt-in, signed; no auto-update without consent.
11. **Telemetry posture.** Augur currently has none — the review must *prove* this with the network egress evidence.
12. **Optional admin features.** Read-only mode, policy file, deployment manifest for IT.

## Deliverables

### Public (ships in `augur-os` repo under `docs/security/`)

- `docs/security/README.md` — entry point and claim summary.
- `docs/security/threat-model.md` — adversaries, attack surfaces, mitigations, **accepted residual risks only**.
- `docs/security/enterprise-readiness-packet.md` — formal review doc: NIST CSF executive framing, CIS Controls v8 mapping, threat model summary, regulated-industry non-interaction appendix, operational instructions for IT auditors.
- `docs/security/architecture-trust-boundaries.md` — diagram + data-flow narrative.
- `docs/security/network-egress-proof.md` — reproducible verification: a shell session a reviewer can run that demonstrates zero unsolicited outbound traffic. Treated as a first-class deliverable; arguably the highest-leverage single artifact in the review.
- `docs/security/enterprise-deployment-guide.md` — admin install / uninstall / audit procedure, claims sheet, FAQ.

Every claim in public docs ships with a verification command a reader can run on their own laptop. No "trust us" language.

### Private working doc (not published until empty or fully accepted-residual)

- `docs/superpowers/security-review/2026-05-augur-runtime-gap-analysis.md` with frontmatter `x-augur-release: internal`. Per-surface entries with structure: *Claim → Evidence (file paths, line numbers, commands) → Gaps found → Remediation (linked ADR or `TODO_BUG` marker) → Status*. As gaps are resolved or accepted, content moves to the public docs and is removed from this file.

### Private pitch curation (customer-specific, not in repo)

- One-page index mapping plausible enterprise IT questions to public-doc sections — your in-room cheat sheet, customized per pilot customer.
- Optional 5-slide deck pulling executive-summary content from `enterprise-readiness-packet.md`.

### Why this shape

The pitch story becomes "go look at github.com/augur-os/augur-os/tree/main/docs/security" — stronger than handing over a private PDF. The CIS Controls v8 section is built mechanically from per-surface evidence; once Phases 1-3 produce the evidence, Phase 4 is editorial.

## Framework

**CIS Controls v8** for operational testability (18 controls; many will be marked "N/A — Augur does not handle X" with rationale, which is acceptable).

**NIST CSF (Identify, Protect, Detect, Respond, Recover)** as the executive-summary wrapper. CIS gives enterprise IT something concrete to check; CSF gives them the executive-readable framing.

**Regulated-industry non-interaction appendix** in `enterprise-readiness-packet.md`: a short section listing CMMC, ITAR / EAR export controls, and trade-secret regimes, stating that Augur's local-only architecture makes them non-interactive (no export-controlled data flows out, no cross-border data transit, no DoD-CUI handling). Full NIST 800-171 or CMMC L2 mapping is explicitly deferred to a later customer-driven request.

## Execution phases

### Phase 0 — Foundation

Create `docs/security/` skeleton with stub files so links resolve and reviewers can see the final shape early. Write the private gap-find working doc with the per-surface template. Build the CIS Controls v8 + NIST CSF mapping skeleton in `enterprise-readiness-packet.md`: 18 CIS controls + 5 CSF functions as headers, each marked `TBD`. Inventory the runtime surfaces (one paragraph each: what it is, where it lives, what it can do).

**Checkpoint:** all public-doc filenames committed, working doc template in place, framework skeletons visible.

### Phase 1 — Tier 1 gap-find + fix

Five Tier 1 surfaces, surface-by-surface. For each:

1. **Static analysis.** Grep network calls, audit subprocess invocations, list daemon entries, list MCP tools that execute shell commands, etc. Write findings into the working gap-find doc.
2. **Runtime verification.** Start Augur, run `lsof`, `netstat`, `ps`, `launchctl list`, `tcpdump` / `pktap` capture, etc. Append captured evidence.
3. **Gap triage.** If fix is < 1 day, fix in this phase. If fix is architectural, write a proposed ADR and accept the residual risk for v1.
4. **Distill.** Move resolved findings into the public `docs/security/` files; the gap-find working doc retains only unresolved or accepted-residual entries.

The network-egress proof is produced in this phase and treated as a first-class artifact, with a reproducible script committed to `docs/security/network-egress-proof.md`.

**Checkpoint (emergency-pitch floor):** end of Phase 1, public docs answer all five Tier 1 questions. Sufficient for an emergency pitch but not the canonical bar.

### Phase 2 — Tier 2 gap-find + fix

Four Tier 2 surfaces (logging / audit, file locations / privilege, vault data classification, dashboard binding). Same per-surface methodology as Phase 1. Most Tier 2 surfaces are expected to be in good shape; this phase is mostly evidence-gathering and documentation.

**Checkpoint (canonical pitch-ready bar):** end of Phase 2, public docs answer Tier 1 + Tier 2. This is the bar at which enterprise-customer meetings should happen.

### Phase 3 — Tier 3 gap-find + fix

Three Tier 3 surfaces (update mechanism, telemetry posture, optional admin features). Lightest phase. May surface ship-a-new-feature items (notably the `--enterprise` policy mode); those go to separate plans, not this review.

### Phase 4 — Public-packet consolidation

Fill the CIS Controls v8 mapping; now mechanical because each control points to evidence already produced in `architecture-trust-boundaries.md`, `network-egress-proof.md`, or `threat-model.md`. Add the NIST CSF executive-summary front matter. Add the regulated-industry non-interaction appendix. Write `enterprise-deployment-guide.md` (install / uninstall / audit procedure, claims sheet, FAQ).

### Phase 5 — Pitch curation

Produce a customer-specific cheat-sheet meta-doc (private, not committed): a 1-page index mapping plausible enterprise IT questions to public-doc sections. Optionally produce a 5-slide deck. This step is repeated per pilot customer.

### Sequencing rationale

- Phase 0 sets up the *shape* so reviewers see where things will land before content exists; encourages thinking in the final layout.
- Phase 1 is front-loaded with highest-risk work. An architectural blocker is surfaced in days, not weeks.
- Phases 2-3 can in principle parallelize via subagents because surfaces are independent. Phase 1 stays serial to maintain threat-model coherence.
- Phases 4-5 are editorial; cheap if Phases 1-3 produced honest material.

## Success criteria for "pitch-ready"

1. `docs/security/threat-model.md` and `docs/security/enterprise-readiness-packet.md` are committed and reviewable on GitHub.
2. Every Tier 1 and Tier 2 claim has a verification command an enterprise IT auditor can run.
3. The private gap-find working doc contains no unresolved Tier 1 or Tier 2 entries (accepted-residual entries are allowed and are mirrored into `threat-model.md`).
4. The CIS Controls v8 mapping is filled. "N/A — Augur does not handle X" with rationale counts as filled.
5. The network-egress proof script in `docs/security/network-egress-proof.md` runs end-to-end and produces the documented zero-egress result on a fresh laptop.
6. You can answer 15 plausible enterprise IT questions by pointing at sections of the public docs (validated against the Phase 5 cheat sheet).

## Risks and kill criteria

### Architectural risks that could surface mid-review

For each risk, **in-scope action** describes what this review does; **proposed follow-up** describes work referenced from this review but executed under separate plans (per the scope guards).

- **Ambient outbound network call.** A dependency phones home (transitive lib telemetry, `next/font` fetch, npm postinstall script). Likely. In-scope: identify and document in an "ambient egress" subsection of `network-egress-proof.md` with vendor names and reproducible detection commands; provide opt-out guidance if one exists today. Proposed follow-up: admin-configurable allowlist + `--airgap` fail-closed mode.
- **Daemon escalation or audit gap.** Autoloop daemon needs more privilege than expected, or persists in a way an admin cannot audit. Possible. In-scope: document the current process model and the `launchctl bootout` / `systemctl --user disable` removal path. Proposed follow-up: any redesign needed for enterprise endpoint policies.
- **Code-execution surface too open.** Skills can run arbitrary scripts; enterprise IT will flag this. Likely. In-scope: document the current sandbox (or absence thereof) and which operations require user confirmation. Proposed follow-up: `--enterprise` policy mode (skill allowlist + disabled auto-script-execution).
- **Vault classification gap.** Augur has no concept of "this folder is classified, don't ingest." In-scope: document existing exclude-by-roots configuration and its limits. Proposed follow-up: `classification.yaml` policy file.

### Kill criteria — when to stop and replan

- Phase 1 surfaces an outbound network call we did not know about *and* cannot remove or gate behind opt-in within 2 days → stop, write an ADR, decide between refactor and accepting the risk.
- The daemon model is fundamentally incompatible with corp endpoint policies (persistent processes banned outright) → stop, design a no-daemon mode, separate plan.
- Any Tier 1 claim turns out to be unverifiable (we cannot produce evidence) → do not make the claim; downgrade the public-doc language; do not pitch on it.

## Open questions to resolve during execution

These are non-blocking and will be answered by the phase work:

- Where exactly do Augur logs live on macOS vs Windows? (Phase 0 inventory; informs `enterprise-deployment-guide.md`.)
- Does the Next.js dashboard make outbound calls in dev vs prod mode? Telemetry, font CDN. (Phase 1 network-egress work.)
- Current state of `install.sh` vs `pip install augur-os` — are both supported, what is the SHA-pinning posture of each? (Phase 1 supply-chain work.)
- Are all bundle-tier MCP servers (`augur-vault`, `augur-ingest`, etc.) covered by the same stdio + parent-PID model, or do any expose a different transport? (Phase 0 inventory; Phase 1 MCP trust-boundary writeup.)

## Scope guards (explicit non-goals)

- No architectural refactors. Building `--enterprise` mode, redesigning the daemon, building a skill allowlist registry — these are separate plans referenced from this review.
- No new tests beyond the verification commands an IT auditor will run.
- No audit of user-authored skill contents.
- No additional framework mappings (ISO 27001, SOC2, full CMMC L2 / NIST 800-171). CIS Controls v8 + NIST CSF + the non-interaction appendix is v1.

## Highest-leverage single artifact

The **network egress proof** in `docs/security/network-egress-proof.md` — a concrete shell session demonstrating Augur running for a sustained period with `tcpdump` / `pktap` / Little Snitch capture showing zero unsolicited outbound traffic, committed as a reproducible script. For a local-first product, a single auditable proof of "nothing leaves the box" likely matters more to enterprise IT than 30 pages of controls mapping.

## Next step

After this design spec is approved, hand off to the `writing-plans` skill to produce the implementation plan with concrete file-level and command-level tasks for Phase 0 through Phase 5.
