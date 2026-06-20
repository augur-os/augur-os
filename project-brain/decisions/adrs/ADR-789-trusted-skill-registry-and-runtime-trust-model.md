---
status: Future
date: 2026-05-28
deciders:
  - gsannikov
related:
  - ADR-522
  - ADR-627
  - ADR-635
  - ADR-638
  - ADR-735
  - ADR-754
  - ADR-769
  - ADR-781
  - ADR-782
  - ADR-783
  - ADR-788
hub: command
tags:
  - skills
  - registry
  - supply-chain
  - provenance
  - sandbox
  - enterprise
  - tank
superseded_by: null
spec_file: null
plan_file: null
---

# ADR-789: Trusted Skill Registry And Runtime Trust Model

## Decision summary

Augur will defer Tank-like registry, signing/provenance, full scanner, private/team catalogs, and runtime trust enforcement into a future trusted skill registry program built on top of ADR-788's local guardrails.

## Status notes

Future as of 2026-05-28. This ADR captures the full target architecture so short-term work does not accidentally sprawl into registry, package-manager, signing, or sandbox scope. It should not be implemented until ADR-788 has produced a working local lock, authority model, scanner verdict, and projection-time gate.

## Context

Tank demonstrates the shape of a registry-grade skill package ecosystem: manifests, lockfiles, package publish/install/update, permission budgets, permission escalation, scanner findings, audit score, registry UI/API/admin, and MCP package-management tools. That model is valuable, but Augur's product boundary is different.

Augur is a local-first brain and harness runtime. Its durable source is the resolved brain stack: Global, User, Team, and Project capabilities. It projects skills, instructions, commands, agents, hooks, memory, MCP configuration, and plugin packages into native AI clients. This gives Augur a stronger local/private/team story than a plain public registry, but it also means registry work must respect brain ownership, generated-output boundaries, enterprise policy, and client-native packaging.

ADR-788 handles the short-term need: make local skill and plugin projection safer. This future ADR handles the larger platform question: how Augur eventually supports trusted external skill distribution without giving up local-first control or overclaiming runtime safety.

The future program must be honest about maturity. Tank itself labels runtime sandboxing and signing/provenance as planned. Augur should borrow the direction, not pretend those features exist before they are implemented and verified.

## Feature Scope

| Capability | Why it belongs in the future ADR | Dependency |
|---|---|---|
| Public or federated skill registry | Requires auth, package storage, publishing, moderation, trust policy, and lifecycle semantics | ADR-788 lock/verdict baseline |
| Private/team catalogs | Requires multi-brain/team governance and enterprise admin policy | ADR-754, ADR-769, ADR-735, ADR-788 |
| Package publish/install/update | Requires stable package format, versioning, lockfile, and migration policy | ADR-788 |
| Full scanner pipeline | Requires deterministic stages plus optional agent-mediated review and stored findings | ADR-788 scanner subset |
| Signing/provenance | Requires identity, key management, signature verification, and provenance storage | package format and registry |
| Runtime sandbox or runtime policy enforcement | Requires per-client and OS integration; Augur can govern Augur surfaces but cannot sandbox arbitrary AI client tools alone | ADR-735 governance and client/MDM integrations |
| Audit score and trust UX | Requires stable verdicts and a user-facing risk model | ADR-788 verdicts |
| MCP registry parity | Package operations should be available through bounded MCP tools | registry APIs and policy |

## Decision

### 1. Build On ADR-788, Not Around It

The trusted registry program must consume the local lockfile, authority metadata, scanner verdicts, and projection gates created by ADR-788. It must not create a parallel skill inventory or a second capability policy system.

The registry can introduce package metadata, but `SKILL.md` remains the skill entrypoint and brain-owned skill roots remain canonical for Augur-managed skills.

### 2. Define An Augur Skill Package Format

A future package format must represent:

- skill metadata and `SKILL.md`
- commands, scripts, references, assets, examples, evals, agents, dashboard declarations, and action metadata
- normalized authority declarations
- supported brain scopes: global, user, team, project
- compatible client targets
- scanner summary and package digest
- provenance/signature metadata when signing is implemented

The package format must preserve Augur's generated-output boundary. Client folders such as `.codex/skills/`, `.claude/skills/`, and `.gemini/skills/` are not source packages. They are generated projections.

### 3. Support Registry Modes Instead Of One Central Registry

Augur should support three registry modes:

1. local catalog: file-backed package cache for personal/project use
2. team/private catalog: organization-managed catalog with allowlists and policy
3. public catalog: optional open distribution and discovery layer

This avoids forcing every user through a cloud registry and keeps private/team work compatible with the local-first model.

### 4. Add Publish, Install, Update, Remove, Verify, And Audit Lifecycle

The future CLI/MCP lifecycle should be:

- publish package from a canonical skill root
- install package into a selected brain scope
- update package with permission escalation checks
- remove package without deleting unrelated local user content
- verify lock/provenance/scanner verdict
- audit package and compare findings across versions

Every lifecycle operation must be brain-scope aware. Installing into a project brain is different from installing into a personal brain or team brain.

### 5. Expand Scanner From Local Guardrail To Registry Verdict

ADR-788's deterministic scanner is the seed. The future scanner should add:

- archive/package extraction safety
- deeper static analysis
- stronger prompt-injection detection
- dependency and supply-chain analysis
- package provenance checks
- optional agent-mediated review packets
- stored scan history and diffable findings

Scanner verdicts must stay explainable. A numeric score can be added only if the findings behind it remain inspectable from CLI, MCP, and Browse.

### 6. Add Signing And Provenance Only After Package Format Stabilizes

Signing/provenance is not just another field. It requires:

- author identity model
- key management
- signature verification in install/update paths
- signature preservation in mirrors and private catalogs
- revocation policy
- provenance display and audit events

The target direction can use modern package provenance ideas, but implementation must be planned after the package format and lockfile have stabilized.

### 7. Treat Runtime Sandbox As A Separate Enforcement Layer

Runtime enforcement must not be overclaimed. Augur can enforce policy on Augur surfaces: MCP tool dispatch, CLI dispatch, daemon scheduling, dashboard MCP route, sync/projection, and plugin-pack exports. Augur cannot alone sandbox all arbitrary AI client behavior outside those surfaces.

Future runtime trust work may include:

- policy checks at Augur MCP dispatch
- generated client hook policies where clients support hooks
- OS/MDM policy for managed enterprise devices
- egress controls for provider calls
- subprocess and filesystem gating for Augur-owned tools
- integration with client-managed allowlists

This belongs to the enterprise governance path and must cite ADR-735.

### 8. Surface Registry Trust Through Existing Augur UX

Registry and trust state should appear through:

- Browse cards and detail panels
- plugin-pack readiness
- skill health
- capability exposure manager surfaces
- MCP verify/audit tools
- command/CLI workflows

Do not build a standalone marketplace UI first. The first user value is knowing whether a capability in the current brain stack is trusted, current, and safe to project.

## Consequences

### Positive

- Augur gets a clear future path toward secure skill distribution without derailing immediate local guardrails.
- Team/private catalogs align with Augur's multi-brain model and enterprise positioning.
- The public registry can remain optional instead of becoming the default trust boundary.
- Signing, provenance, and sandboxing are documented as real future work rather than implied shipped behavior.

### Negative

- This is a large program with auth, storage, policy, packaging, scanner, and client integration work.
- Registry features can distract from the local-first product if started too early.
- Runtime enforcement depends partly on client and OS capabilities outside Augur's direct control.
- A public package ecosystem creates moderation, abuse, and support obligations.

### Neutral

- Tank remains a useful comparison and potential source of implementation ideas, but Augur should not clone Tank's architecture.
- The registry program can reuse external tools or services later, but the governing model stays Augur-native.
- ADR-788 must land first so the registry has a local trust substrate to extend.

## Implementation Order

### Phase 0: Prerequisite Gate

Do not begin this ADR until ADR-788 has:

1. generated a real lockfile from current Augur skill roots
2. blocked external SHA drift
3. normalized authority metadata
4. produced scanner verdicts
5. surfaced findings through CLI/MCP and Browse
6. validated against real skills and plugin-package outputs

### Phase 1: Package Format And Local Catalog

1. Define package format and archive safety rules.
2. Implement local file-backed catalog and package cache.
3. Add publish/install/update/remove operations for local packages.
4. Verify brain-scope-aware installs into project and user roots.

### Phase 2: Registry API And Private/Team Catalogs

1. Define registry API around package metadata, blobs, scan findings, and trust policy.
2. Add private/team catalog support before public marketplace support.
3. Integrate with team/admin policy from the enterprise governance layer.
4. Add audit events for every package lifecycle action.

### Phase 3: Full Scanner And Trust History

1. Expand scanner stages beyond ADR-788.
2. Store findings and version diffs.
3. Add scanner history to package metadata and Browse detail surfaces.
4. Add registry-side fail/flag/pass workflows.

### Phase 4: Signing And Provenance

1. Define identity and key model.
2. Sign packages and verify signatures on install/update.
3. Add revocation and compromised-package handling.
4. Display provenance in CLI/MCP/Browse.

### Phase 5: Runtime Trust Enforcement

1. Map authority metadata to Augur-owned runtime dispatch points.
2. Enforce policy at MCP, CLI, daemon, dashboard MCP, and sync/projection boundaries.
3. Add client hook integrations where available.
4. Add managed-device/MDM integration for enterprise enforcement.
5. Verify no-bypass behavior across surfaces.

### Phase 6: Public Registry And Marketplace UX

1. Add public discovery only after private/team lifecycle and scanner are stable.
2. Add moderation/admin flows.
3. Add package reputation and trust UX.
4. Document precise shipped versus planned guarantees.

## Alternatives Considered

### Alternative 1: Build Public Registry First

Rejected. A public registry without local lock, scanner, authority metadata, and update gates would repeat the exact supply-chain risk Tank is trying to solve. Augur's first registry value should be private/team trust, not public marketplace growth.

### Alternative 2: Make Tank The Registry Backend

Rejected as the default decision. Tank may be a useful integration or code reference, but Augur's canonical source model is brain-layered and client-projected. A Tank backend would need an adapter anyway and could not replace Augur's brain ownership, Browse metadata, or enterprise policy.

### Alternative 3: Skip Registry And Only Keep Local Guardrails Forever

Rejected as a future direction. Local guardrails are enough for personal/project safety, but teams need approved catalogs, package history, provenance, and central policy when skills become shared organizational assets.

### Alternative 4: Claim Runtime Sandbox Through Manifest Permissions

Rejected. Declared permissions and install/update gates are useful, but they are not runtime sandboxing. Runtime enforcement must be separately built and verified at Augur-owned dispatch points plus client/OS layers.

## References

- Tank repository: <https://github.com/tankpkg/tank>
- Tank docs inspected 2026-05-28: `docs/product/product-brief.md`, `docs/core/architecture.md`, `docs/core/security.md`, `docs/reference/packages/mcp-reference.md`
- `docs/architecture-overview.md`
- `docs/architecture-skills.md`
- `docs/architecture-sync-agents.md`
- `docs/architecture-mcp-gateway.md`
- `docs/architecture-capability-exposure.md`
- `docs/architecture-dashboard.md`
- ADR-522: Plugin-Pack Multi-Target Plugin Assembly
- ADR-627: Loop Security (Auto Security Audit)
- ADR-735: Augur Enterprise Governance Layer
- ADR-754 and ADR-769: brain registry and project-brain foundation
- ADR-781 to ADR-783: harness layering, projection, CLI/MCP tier scoping
- ADR-788: Augur Skill Supply-Chain Guardrails

## Impact Manifest

```yaml
paths_renamed: []
apis_changed:
  - future package publish/install/update/remove/verify/audit command surfaces
  - future package registry MCP tools
  - future registry API endpoints
  - future runtime policy enforcement points
patterns_deprecated:
  - treating external skill distribution as simple file copy without package lifecycle
  - presenting declared permissions as runtime sandboxing
  - building a public marketplace before local/private trust gates
files_affected:
  - config/system/skill_supply_chain.yaml
  - config/system/capability_exposure.yaml
  - project-brain/capabilities/skills/plugin-pack/
  - project-brain/capabilities/skills/ai/scripts/sync_agents/
  - src/lib/
  - src/mcp/augur_mcp/
  - apps/dashboard/app/(views)/browse/
  - apps/dashboard/lib/browse/
  - docs/architecture-skills.md
  - docs/architecture-sync-agents.md
  - docs/architecture-mcp-gateway.md
  - docs/architecture-capability-exposure.md
```

## Implementation Prompt

Use this prompt only after ADR-788 is implemented and accepted as the local trust substrate.

```text
TeamCreate name="adr-789-trusted-skill-registry" purpose="Design and implement Augur's future trusted skill registry and runtime trust model on top of ADR-788 guardrails."

Context:
- ADR-789 is Future status and must not start until ADR-788 completion gates pass.
- Preserve Augur's local-first brain-layered source model.
- Do not replace SKILL.md, sync_agents, plugin-pack, Browse, or capability_exposure.yaml with a parallel system.
- Be explicit about what is shipped, what is advisory, and what is true runtime enforcement.

TaskCreate id="T0-prereq-audit" role="validator" model="sonnet" mode="pipeline" depends_on=[] instructions="
Confirm ADR-788 is implemented with real lockfile, integrity gate, authority metadata, scanner verdicts, and Browse/MCP/CLI surfaces. Abort if any prerequisite is missing."

TaskCreate id="T1-package-format" role="architect" model="opus" mode="pipeline" depends_on=["T0-prereq-audit"] instructions="
Define Augur skill package format, archive safety rules, brain-scope metadata, generated-output boundary, and compatibility with SKILL.md. Produce tests and migration notes."

TaskCreate id="T2-local-catalog" role="developer" model="sonnet" mode="pipeline" depends_on=["T1-package-format"] instructions="
Implement local file-backed catalog, package cache, and publish/install/update/remove/verify/audit lifecycle for project and user brain scopes."

TaskCreate id="T3-private-team-registry" role="developer" model="opus" mode="pipeline" depends_on=["T2-local-catalog"] instructions="
Design and implement private/team catalog APIs and policy integration. Defer public marketplace UX until private/team lifecycle works with audit events."

TaskCreate id="T4-full-scanner-history" role="security" model="opus" mode="pipeline" depends_on=["T2-local-catalog"] instructions="
Expand scanner stages, store findings and diffs across versions, and expose explainable verdict history through CLI/MCP/Browse."

TaskCreate id="T5-provenance" role="security" model="opus" mode="pipeline" depends_on=["T3-private-team-registry","T4-full-scanner-history"] instructions="
Add signing/provenance model, signature verification, revocation policy, and provenance display. Keep unsigned-package behavior explicit and policy-governed."

TaskCreate id="T6-runtime-trust" role="security" model="opus" mode="pipeline" depends_on=["T5-provenance"] instructions="
Map authority metadata to Augur-owned dispatch points: MCP, CLI, daemon, dashboard MCP route, sync/projection, and plugin-pack. Add client hooks and MDM/OS integrations where available. Verify no-bypass behavior."

TaskCreate id="T7-marketplace-ux" role="developer" model="sonnet" mode="pipeline" depends_on=["T3-private-team-registry","T4-full-scanner-history"] instructions="
Only after private/team registry trust is stable, add public discovery and marketplace surfaces. Keep trust state visible through existing Browse and skill/plugin detail surfaces."
```
