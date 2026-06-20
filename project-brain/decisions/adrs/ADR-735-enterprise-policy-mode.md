---
status: Accepted
date: 2026-05-21
deciders:
  - gsannikov
related:
  - ADR-725
  - ADR-754
  - ADR-768
  - ADR-769
  - ADR-770
  - ADR-771
  - ADR-772
  - ADR-640
  - ADR-743
  - ADR-757
hub: null
tags:
  - enterprise
  - security
  - policy
  - governance
  - multi-brain
  - mcp
superseded_by: null
spec_file: null
plan_file: null
---

# ADR-735: Augur Enterprise Governance Layer — Reality-Grounded Architecture

## Status

**Accepted** — as an *architectural direction*. This is a positioning ADR: it fixes the
canonical architecture for the enterprise tier's governance/security layer and a maturity
snapshot of what exists today. **Implementation is deferred to a post-funding plan**
(Stage-01 hardening / Tier-2 "Enterprise to GA"). Supersedes the thin "Enterprise Policy
Mode" intent that previously occupied this number.

Maturity snapshot: **2026-05-21**. The Reality Assessment below is the ground truth on
that date and must be re-checked before any external use.

## Context

ADR-725 (Augur Enterprise Security Review) found that Augur has a clean local-first
architecture and a source-controlled MCP topology, but **no runtime enterprise
governance layer**. Skills, MCP tools, slash commands, routines, installers, and the
daemon all execute local code by design — fine for a trusted personal install, not
sufficient for a managed enterprise device.

The company's investor positioning makes the **enterprise tier the product and the
moat** ("Augur for Teams & Orgs", "Layer 4"). The pitch promises a specific bundle of
controls: capability allowlist, audit trail, airgap mode, central control across every
brain, approved-AI deployment, remote MCP, and an inspectable plain-text vault.

The multi-brain work is the **substrate** this governance layer must sit on. ADR-754
(brain registry) and ADR-769 (project-brain foundation + `augur init`) are implemented;
ADR-768/770/771/772 are accepted and in flight. Governance is therefore expressed **per
brain type**: personal (private, user-owned), project (versioned, ships in-repo), team
(federated, admin-governed).

This ADR is the canonical, **honest** architecture for that layer. It deliberately
separates what is *real today*, what is *achievable on the existing substrate*, and what
is currently *overclaimed*, so the team builds the real thing and represents it
accurately.

## The Reactive Trust Model — Honest Version

The pitch's strongest security idea is the **reactive architecture**: Augur authors
skills, hooks, routines, and configuration into a plain-text vault, and the AI client the
org *already pays for* executes the knowledge work.

**Defensible core (keep saying this) — verified in code:**

- **Augur never originates a cloud LLM call.** Agent reasoning, cloud-escalated OCR, and
  routine judgment all dispatch to the AI client: routine work goes through the client's
  subagent surface (`routine_orchestrator/subagent_dispatch.py` raises `NoSessionAvailable`
  rather than calling a cloud API when no client session exists); cloud OCR runs as a
  "passive agent" CLI job (`src/lib/extraction/cloud_vision.py`). Augur's *only* originated
  inference is **local Ollama** (extraction; opt-in `--local` routines). So with the
  default profile, no inference data leaves the machine and Augur holds **no cloud
  inference key**.
- For reasoning, Augur reuses the trust boundary the org already established with its AI
  client — **no new cloud reasoning vendor**.
- The vault is plain-text and inspectable; the harness is vendor-neutral and local-first.

**Where it is overclaimed (stop saying this):**

- Augur is **not** zero-compute / zero-surface. It runs a local MCP server (300+ tools,
  local stdio), a daemon (which **schedules, monitors, and applies deterministic fixes — it
  does not execute LLM work**; that dispatches to the client), spawns subprocesses (agent
  launch, IDE bridges, sync, dashboard PTY, the passive-agent CLI), and ships a local LLM
  client (`src/lib/ai/client.py`) plus a credential store. That **is** real local attack
  surface — which is exactly why the nightly 5-stage security routine exists.
- The honest framing is **"local, governed, nightly-scanned surface — not remote, not
  zero,"** not "no hidden CLI processes / no attack surface."

**Consequence:** the governance layer controls **Augur's own execution surfaces** (MCP
tools, CLI, daemon, dashboard route, scripts, *and Augur-originated LLM calls*) — *not* the
AI client. Two enforcement upgrades turn defaults into guarantees: forbid Augur-originated
cloud LLM (egress policy, below) and the no-bypass chokepoint.

## Decision — The Enterprise Governance Layer

A governance layer over Augur's own execution surfaces, expressed per brain type, built
on the substrate that already exists. Seven controls:

1. **Capability / skill allowlist.** Built on `config/system/capability_exposure.yaml`
   (which already classifies every capability: `classification_status`, `export_to`,
   `management`, `owner_kind`, `scope`). Scoped per brain — team-brain admin sets the
   allowlist, personal-brain stays user-controlled, project-brain ships its allowlist
   in-repo. Default-deny in enterprise mode. **Do not** invent a parallel policy registry.
2. **Script-execution control.** Auto-discovered script execution is default-deny in
   enterprise mode; scripts must declare policy metadata and be admin-allowed.
3. **MCP tool policy labels.** Tool definitions declare sensitivity + action class
   (`read-only` / `local-write` / `network` / `subprocess` / `provider-call` /
   `persistence`), reconciled with the existing capability vocabulary. Directly mitigates
   **CurXecute (CVE-2025-54135)** and **MCPoison (CVE-2025-54136)** — the MCP
   config-rewrite and trust-once-trust-forever attacks the deck already cites.
4. **Report-only automation defaults.** Unify with the *existing* routine autonomy
   boundary (`remedy_auto` / `scan-fix`). Auto-fix, adaptive remediation, and daemon
   critical-action dispatch run report-only unless explicitly enabled.
5. **Egress / airgap policy.** Build on ADR-640 offline mode. Network-capable tools
   declare a destination class and fail closed when policy denies. Includes **LLM
   origination control** — Augur-originated calls restricted to local-or-dispatch (see
   *LLM Origination & Egress* below). *Certified* airgap (egress enforcement + dependency
   mirror + provider disablement) is a separate, larger effort — see Non-Goals.
6. **Audit events.** Ride the **ADR-743 job ledger** (ADR-757 made it the sole
   observability substrate). Policy decisions, denials, and approved high-risk executions
   become structured, SIEM-forwardable events. Do not create a new log substrate.
7. **Override discipline.** Admin-vs-user separation maps to brain ownership (team-brain
   admin policy vs personal-brain user). Per-command override requires explicit
   confirmation and leaves an audit record. On a managed device, real tamper-resistance
   requires MDM/OS-delivered policy — see Threat Model.

**Core mechanism — the single chokepoint.** All seven controls route through **one
policy-decision module** (under `src/`) that *every* Augur surface calls: MCP tool
registration/dispatch, CLI dispatch, the dashboard `POST /api/mcp/tool` route, the daemon
scheduler, and script discovery. A **no-bypass parity scanner** (in the spirit of the
existing agent-config-parity scanner) proves no surface skips it. Without the single
chokepoint + parity test, the claim "no surface can bypass policy" is unverifiable — and
unverifiable enforcement is not enforcement.

### MCP Governance (elaboration of controls 1 & 3)

The enterprise fear here is **MCP sprawl** — employees adding arbitrary MCP servers per
laptop, with no org visibility (the deck's Problem 03) and the named MCP attack class
(CurXecute CVE-2025-54135 config-rewrite; MCPoison CVE-2025-54136 trust-once-trust-forever).
Augur's stance has two halves that **must not be conflated**:

**(a) Augur's own MCP is local stdio by design.** Every Augur server runs as a local
subprocess over stdin/stdout (`mcp_servers.yaml` → generated `mcp.json`), with no network
listener — zero remote attack surface on Augur's own servers. Caveat stated plainly:
"local stdio" reduces *remote* surface; it does not make an *allowed* server's code safe
(it can still touch fs/net/exec). The security value is **curation of which servers run**,
not the transport.

**(b) Remote / third-party MCP is governed by an allow/deny list.** Augur is the *sole
generator* of the client `mcp.json`, which makes it the control point for which servers
reach a laptop. The governance is layered, and each layer is honestly labeled fail-closed
or advisory — claiming more than this is the overclaim to avoid:

| Layer | Mechanism | Status / fail-closed? |
|---|---|---|
| Policy source | Org allow/deny list in managed config (extends `mcp_servers.yaml` + the existing `monolith_exclusions` precedent), **per brain**: team-admin owns the org list, project ships its own, personal stays user-owned | design |
| Distribution curation | Augur generates `mcp.json` with **only** allowlisted servers; unapproved are never distributed | ✅ fail-closed at distribution (generator exists) |
| Integrity pinning | Each allowed server pinned by SHA tree hash; extend `routine-security/s4_integrity.py` from compute-and-report → **compare-vs-baseline**; changed code fails the pin (defeats MCPoison) | 🟡 hashing exists, baseline-compare not built |
| Continuous reconciliation | Daemon re-asserts the approved config; the sync drift check flags manual tampering; enterprise mode auto-remediates to the approved set + emits an event | 🟡 drift check exists, auto-remediation not built |
| Enforcement teeth | The client's managed/enterprise MCP allowlist or MDM-locked config — the only true **block at load time**, because the client (not Augur) reads `mcp.json` and spawns servers | 🔴 client/MDM dependency, not built |
| Audit | Every allow/deny, drift, integrity failure → structured event on the ADR-743 ledger, SIEM-forwardable | 🟡 ledger exists, policy events not built |

**Honest claim this earns:** Augur makes unauthorized MCP servers **impossible to
distribute** and **detectable if manually added**; **blocking** them at load is the
client's managed allowlist / MDM, which Augur drives via the policy source + audit. The
overclaim to avoid is implying Augur itself blocks a server the AI client chooses to load.

### LLM Origination & Egress Policy (elaboration of control 5)

Verified: Augur **dispatches** all cloud inference to the AI client (reasoning →
subagent surface; cloud OCR → passive-agent CLI) and *defaults* to local-only origination
(`active_profile: local` → Ollama). But that is a **default, not a guarantee**. A latent
path exists — `llm.yaml` ships a cloud profile (`openai`) and `src/lib/ai/client.py` can
call it, so `active_profile: openai` would make **Augur itself** originate cloud calls,
bypassing the reactive dispatch and opening a vault-exfiltration channel.

Enterprise mode closes this by policy: **Augur-originated LLM calls are restricted to
`local` (on-device Ollama) or `dispatch` (passive-agent / client subagent); `cloud-direct`
is denied.** Enforced at `load_llm_config()` / `resolve_llm_profile()` through the same
chokepoint — a non-local profile selected for an Augur-originated call fails closed and
emits a denial event on the ADR-743 ledger. This converts "Augur never originates cloud
calls" from a *default* into an **enforced egress guarantee**: cloud inference can happen
only via the already-approved client, never via an Augur-held key.

> **Maturity caveat (multi-client):** routine semantic dispatch (`subagent_dispatch`) is
> implemented for **Claude Code** only; `codex`/`gemini` raise `NotImplementedError`. A
> client-agnostic *oneshot-agent-CLI* dispatch already exists (the passive-agent OCR path,
> `build_agent_command`) and is the path to multi-client routine dispatch. Until then,
> "9 clients" describes skills/config **projection**, not routine **dispatch**.

## Reality Assessment — Achievable vs Bluster

Ground truth as of the maturity snapshot. Blunt by design; this section is the point of
the ADR.

| Capability (as positioned) | Reality today | Verdict | What closes the gap |
|---|---|---|---|
| Inspectable plain-text vault | Markdown vault, fully readable | ✅ **Real** | — |
| Nightly 5-stage security routine (CurXecute / MCPoison / secrets / permissions) | Shipping, runs nightly | ✅ **Real** | — |
| Vendor-neutral / "privacy is structural" | True for the **vault + harness** (local, plain-text, multi-client) | ✅ **Real, with caveat** | State the caveat: structural for the harness — a *cloud* AI client still sends data under its own boundary |
| No new cloud reasoning vendor / no new inference API keys | True — reasoning runs through the client you already pay for | ✅ **Real** | — |
| Offline / airplane mode ("nothing leaves the machine") | ADR-640 offline inference (Ollama/OpenVINO) implemented | 🟡 **Partial** | Certified airgap = egress enforcement + dependency mirror + provider disablement (not built; deck already non-goals this) |
| Capability allowlist / central control across brains | `capability_exposure.yaml` classification + brain registry (ADR-754/769) exist; **no enforcement** | 🟡 **Achievable** | The single policy chokepoint + per-brain enforcement (post-funding) |
| Audit / compliance trail | ADR-743 job ledger is a real substrate | 🟡 **Achievable** | Structured, SIEM-forwardable *policy* events on the ledger |
| Multi-brain federation / "team brains govern" | Registry + project-brain foundation built (754/769); federation + write-routing + UI are **Accepted, not implemented** (770/771/772) | 🟡 **Achievable** | Land 770–772, then attach governance |
| Approved-AI deployment / "no new vendor" | Projects into existing approved clients | 🟡 **Mostly true** | IT still approves the Augur *runtime* itself (one-time, local) |
| Augur's own MCP is local stdio by design (no network listener) | All servers `command: python` over stdio; `mcp_servers.yaml` → generated `mcp.json` | ✅ **Real** | Deliberate hardening. The deck's "remote MCP not local stdio" wording states this **backwards** — fix the sentence, keep the design |
| Allow/deny governance of remote/third-party MCP ("prevent unauthorized MCP entering the org") | Augur is the sole `mcp.json` generator; drift check + s4 SHA hashing exist; **no enforced allow/deny, no pinned baseline** | 🟡 **Achievable** | Distribution-layer curation is real; fail-closed needs integrity pinning + reconciliation + client-managed-allowlist/MDM teeth (see MCP Governance) |
| Reactive dispatch + local-only LLM origination ("no cloud calls/keys from Augur") | **Verified:** routine/reasoning judgment dispatches to the client subagent surface (`subagent_dispatch`; `NoSessionAvailable` if no client); cloud OCR = passive-agent (client); Augur originates only local Ollama; default holds no cloud key | 🟡 **Mostly real** | True by default → make it *enforced* (egress policy forbids Augur-originated cloud LLM; see LLM Origination & Egress) |
| Multi-client reactive routines ("5+/9 clients") | Routine subagent dispatch implemented for **Claude Code** only; codex/gemini → `NotImplementedError`; a client-agnostic oneshot-agent dispatch exists (used for OCR) but isn't adopted for routines | 🟡 **Partial** | "9 clients" = skills/config *projection*; *routine dispatch* is Claude-Code-native today — unify via the existing oneshot-agent-CLI mechanism |
| "No hidden CLI processes / no new attack surface" | Daemon (schedules/monitors/deterministic-fixes, **not** LLM exec); 300+ local-stdio MCP tools; local LLM client; credential store; spawned passive-agent/PTY | 🔴 **Overclaim** | Reframe: **"local, governed, nightly-scanned surface — not remote, not zero."** |

## Threat Model & Trust Boundaries

- **Personal install:** user == admin. Governance is convenience + visibility, not
  adversarial. Most controls are advisory here.
- **Managed enterprise device:** admin ≠ user; the user may be careless *or hostile*.
  Repo-local policy files are user-editable and are therefore **not** a control against a
  hostile user. Enterprise enforcement against that threat needs **MDM/OS-delivered,
  integrity-checked policy**. As specified, controls 1–7 are honest for the
  *careless-user* and *compromised-dependency* threats; the *hostile-user* threat needs
  the managed-policy delivery layer.
- **The AI client is the executor.** Augur cannot constrain what the agent does with its
  own Bash/Write tools *outside* Augur's surfaces. Client-level controls (the AI client's
  permission settings, hooks, OS sandbox) are the complementary layer. **Augur governs
  Augur.** This boundary must be stated, not blurred.
- **MCP config is a tamper target.** The client reads its own `mcp.json` and spawns
  servers; Augur generates that file but does not sit between the client and it. An
  allow/deny list enforced *only* at generation is therefore advisory against a user who
  edits `mcp.json` directly — fail-closed *blocking* requires the client's managed
  allowlist or MDM-locked config. Integrity must be pinned by **SHA, not identity**
  (MCPoison's trust-once-trust-forever class). See MCP Governance.

## Non-Goals

- Does not remove Augur's automation model or ban local execution for trusted personal
  installs.
- Does not sandbox the AI client.
- Does not certify airgap by itself (needs dependency mirror + provider disablement +
  egress enforcement).
- Does not define the final policy-file schema — that belongs in the implementation plan.
- Does **not** claim "no new attack surface."

## Relationship to Latest ADRs

- **ADR-725** — parent enterprise security review (the gap this answers).
- **ADR-754 / ADR-769** — brain registry + project-brain foundation: the substrate
  governance attaches to (per-brain allowlist, admin-vs-user).
- **ADR-768 / ADR-770 / ADR-771 / ADR-772** — multi-brain roadmap, physical migration,
  client projections/write-routing, brain UI federation: governance enforcement points
  land as these implement.
- **ADR-640** — offline mode: the airgap basis.
- **ADR-743 / ADR-757** — job ledger as the sole observability substrate: the audit event
  sink.
- `config/system/capability_exposure.yaml` — the existing classification substrate (config,
  not an ADR) the allowlist and tool labels extend rather than replace.

## Implementation (Deferred)

Targeted at **Stage-01** (runtime hardened on the first deep-tech enterprise) and
**Tier-2** ("Augur Enterprise to GA"); post-funding. Suggested sequencing:

1. Policy-decision chokepoint module + policy-file schema.
2. Capability/skill allowlist on `capability_exposure.yaml`, scoped per brain.
3. MCP tool policy labels (action class + sensitivity).
4. Audit events on the ADR-743 ledger.
5. Report-only unification with `remedy_auto` / `scan-fix`.
6. Egress / airgap policy on ADR-640.
7. No-bypass parity scanner across all surfaces.
8. Managed-policy delivery (MDM/OS) for the hostile-user threat.

Produce the executable plan via `/adr write` → `/superpowers:brainstorming` +
`writing-plans` when funded. This ADR stays the canonical architecture; the plan carries
schema and execution detail.

## Investor-Claim Map (internal — Q&A defense)

For each positioned claim: the reality verdict, and **how to say it honestly in the
room** so you stay out of overclaim territory under diligence.

| Positioned claim | Verdict | How to say it honestly |
|---|---|---|
| "Privacy is structural, not contractual" | ✅ | "Structural for the vault and harness — local, plain-text, vendor-neutral. Your AI client's own data handling still applies when you run a cloud client." |
| "No new cloud vendor / no new API keys" | ✅ | "Reasoning runs through the AI client you already approved and pay for. We add no new inference vendor." |
| "Inspectable plain-text vault" | ✅ | Say it plainly — it's true and demoable. |
| "5-stage nightly security routine" | ✅ | Name the five: prompt-injection (CurXecute), MCP integrity/SHA (MCPoison), secrets, permissions. It's a genuine strength. |
| "Airgap / nothing leaves the machine" | 🟡 | "Offline inference works today (airplane mode, local Ollama). Certified airgap with egress enforcement is enterprise-tier roadmap." Don't claim certified airgap. |
| "Central control / allowlist across brains" | 🟡 | "The governance substrate — capability classification plus the brain registry — ships today. Enforced central allowlist is the funded Enterprise build." |
| "Audit / compliance" | 🟡 | "Every routine writes to a file-based job ledger today; SIEM-forwardable policy audit is the Enterprise build." |
| "Team brains govern / federation" | 🟡 | "Registry and project brains are live; team federation is accepted and in build (ADR-770–772)." Don't imply federation is shipping. |
| "Approved-AI deployment" | 🟡 | "We project into the clients IT already approved; IT approves the Augur runtime once — not a new cloud vendor." |
| Augur's own MCP is local stdio (no network surface) | ✅ | Say it as the strength it is: "Our MCP runs local stdio by design — no network listener, no remote attack surface." **Do not** say "remote MCP, not local stdio" — that's backwards. |
| "Control which MCP servers enter the org" (allow/deny) | 🟡 | "Augur is the single generator of MCP config, so we curate an org allow/deny list — unauthorized servers never get distributed, manual additions are detected. Hard *blocking* at load uses the client's managed allowlist / MDM, which we drive." Don't imply Augur blocks a server the client chooses to load. |
| "No new attack surface / reactive, no processes" | 🔴 | **Reframe.** "We reuse your AI client's trust boundary for reasoning, so no new inference surface. The local runtime is governed and continuously scanned — we treat it as real surface, not zero surface." |

## Verification Sketch (when implemented)

Enterprise mode is implemented only when these pass — across **every** surface, not just
the CLI:

```powershell
aug --enterprise list-policy           # active allowlist, disabled skills, denied classes, audit sink
aug --enterprise verify                # one chokepoint reachable from CLI, MCP, dashboard, daemon
aug --enterprise run-tool blocked-network-tool   # fails closed + emits a denial event to the ledger
aug --enterprise run-tool allowed-readonly-tool  # still works
```

Plus a **no-bypass parity check** proving the dashboard `POST /api/mcp/tool` route and the
daemon scheduler resolve the same policy decision as the CLI — and a managed-device check
that user edits to a repo-local policy file do not loosen an admin/MDM-delivered policy.
