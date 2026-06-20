---
status: Proposed
date: 2026-05-28
deciders:
  - gsannikov
related:
  - ADR-490
  - ADR-522
  - ADR-605
  - ADR-627
  - ADR-635
  - ADR-638
  - ADR-734
  - ADR-735
  - ADR-776
  - ADR-781
  - ADR-782
  - ADR-783
hub: command
tags:
  - skills
  - supply-chain
  - security
  - tank
  - plugin-pack
  - capability-exposure
  - browse
superseded_by: null
spec_file: null
plan_file: null
---

# ADR-788: Augur Skill Supply-Chain Guardrails

## Decision summary

Augur will add a local-first skill and plugin supply-chain guardrail layer: an Augur lockfile, hard integrity verification, declared authority metadata, permission escalation checks, lightweight package/security scanning, MCP/CLI verification surfaces, and Browse badges on existing skill/plugin cards.

## Status notes

Proposed on 2026-05-28 after comparing Augur's existing skill projection and plugin-pack architecture with Tank's security-first skill package manager. This ADR is intentionally short-term and local-first. It does not create a public registry, a remote install service, runtime sandboxing, or signing infrastructure.

## Context

Tank is a security-first package manager and registry for AI agent skills. Its current repo ships a `skills.json` manifest, `skills.lock`, publish/install/update flows, install-time permission budgets, publish-time permission escalation checks, a scanner pipeline, registry surfaces, and an MCP server with package-management parity. Tank's own docs label runtime sandboxing and signing/provenance as planned, not shipped.

Augur already has adjacent architecture, but the pieces are not a supply-chain control plane:

- Skills are durable capability units under brain-owned `capabilities/skills/` roots and project into AI clients through `sync_agents`.
- Plugin packages are assembled for Claude Desktop/Cowork, Codex, Gemini, Copilot, and other clients through the plugin-pack and AI adapter pipeline.
- `config/system/capability_exposure.yaml` governs where capabilities appear, but not what authority a skill or plugin package needs.
- `external_skills.py` supports vendored external skill bundles with `pinned_sha`, but a mismatch only logs a warning and still proceeds.
- Browse can already carry per-item metadata, badges, findings, and actions on the existing file-card mechanism.
- ADR-627 already established offline security scanning concepts, and ADR-735 established the enterprise governance direction, but neither gives every external skill or generated plugin package a hard local install/projection gate.

The gap is therefore specific: Augur can project and package capabilities, but it does not yet treat skill sources and generated plugin bundles as supply-chain inputs with reproducible integrity, declared authority, and update-risk checks. This matters because agent skills are not passive content. A skill can guide an agent toward filesystem access, network calls, subprocess execution, MCP tool calls, and client configuration changes.

Tank's best short-term lesson is not "build a registry now." It is "put a lock, permission delta, and scanner verdict in front of skill installation and projection." Augur can adapt that lesson without abandoning its local-first, brain-layered model.

## Feature Comparison And Adaptation

| Tank feature | What it does | Augur today | Short-term Augur decision |
|---|---|---|---|
| `skills.json` manifest | Declares package metadata and permissions | `SKILL.md` frontmatter and skill-local metadata | Add Augur authority/package metadata around existing skill metadata. Do not replace `SKILL.md`. |
| `skills.lock` | Pins installed skills and hashes | `external_skills.yaml` has `pinned_sha`, warning-only verification | Add `augur-skills.lock.json` and fail closed on drift for guarded sources. |
| Permission model | Declares network, filesystem, subprocess authority | Capability exposure policy describes surfaces, not authority | Add declared authority classes to skills, external bundles, and plugin packages. |
| Permission escalation | Blocks risky new authority without the right version bump | No equivalent update gate | Adapt Tank's helper pattern as Augur-native permission escalation logic. |
| Install-time permission budget | Rejects packages above policy budget | No local trust budget | Add per-scope budgets for external/adopted skills and generated plugin exports. |
| Integrity verification | Verifies hash before install completes | Submodule SHA mismatch warns and proceeds | Make mismatch a blocking error unless explicitly overridden with audit record. |
| Safe archive extraction | Rejects path traversal, symlinks, hardlinks, oversized archives | Most sources are folders/submodules today | Add only if this ADR introduces packaged archive import; otherwise reserve for ADR-789. |
| Scanner pipeline | Structure, static, prompt injection, secrets, dependencies | Skill health, resolvability, capability drift, loop-security scans | Implement a lightweight local scanner: structure, authority cross-check, prompt-injection heuristics, secrets, dependency/script deltas. |
| Audit score/verdict | Summarizes package risk | Browse can display metadata, but no supply-chain verdict | Add verdicts and badges on existing skill/plugin Browse cards. |
| Registry and publish flow | Public/private package lifecycle | Augur is local-first, brain/project-first | Future only; explicitly out of scope here. |
| Signing/provenance | Planned in Tank | Not present | Future only; explicitly out of scope here. |
| Runtime sandbox | Planned in Tank | Not present | Future only; this ADR enforces at install/projection time. |

## Decision

### 1. Add An Augur Skill Lockfile

Create a local lockfile for skill and plugin supply-chain inputs, tentatively:

- `config/system/skill_supply_chain.yaml` for policy and budgets.
- `docs/generated/augur-skills.lock.json` or another generated committed location for reproducible lock output.
- Runtime cache copies under the configured runtime/cache helpers only when needed for local state, never as the source of truth.

The lockfile records at least:

- capability id and skill name
- source tier: global, user, team, project, external, adopted, generated plugin
- source path or upstream URL
- commit SHA or content digest
- declared authority
- scanner verdict and finding counts
- generated plugin target coverage when a skill is exported into client packages
- timestamp and generator version

The lockfile must be generated from canonical skill roots and plugin-package inputs. It must not become a hand-edited inventory.

### 2. Fail Closed On External Skill Integrity Drift

`external_skills.py` must stop treating a pinned SHA mismatch as a warning for guarded bundles. In guarded mode:

- missing source path fails projection
- unresolvable HEAD fails projection for external bundles that declare a pin
- HEAD mismatch fails projection
- override requires an explicit command or policy entry and emits an audit record

This is the highest-value immediate adaptation from Tank. It turns Augur's existing `pinned_sha` field from documentation into a real guardrail.

### 3. Add Declared Authority Metadata

Augur will introduce authority metadata for skill and plugin supply-chain checks. The minimum authority classes are:

- `filesystem.read`
- `filesystem.write`
- `network.outbound`
- `subprocess`
- `mcp.tools`
- `client.config`
- `secrets`
- `provider.call`

These classes are not a runtime sandbox claim. They are an install/projection/update contract. The initial enforcement happens before a skill is projected, adopted, exported, or packaged.

Authority metadata can be declared in skill frontmatter, skill-local config, external bundle config, or generated package metadata, but the effective normalized authority must be emitted into the lockfile and scanner report.

### 4. Add Permission Escalation Checks

Augur will adapt Tank's permission escalation pattern into an Augur-native module under `src/`:

- PATCH-level updates may not add new authority.
- MINOR-level updates may add lower-risk filesystem read/write authority only when policy allows.
- MAJOR-level updates may add authority but still require budget and scanner checks.
- Adding `network.outbound`, `subprocess`, `provider.call`, `client.config`, or broader MCP tool access is high risk and requires a major boundary or explicit approval.

Because Augur skills do not all have semver versions today, the first implementation must support both:

- version-aware comparison when a skill declares a version
- digest/commit-aware comparison when the source is only pinned by SHA

For SHA-only external bundles, any authority increase is treated as high risk unless the policy explicitly blesses the update.

### 5. Add A Lightweight Local Scanner

This ADR adopts a local subset of Tank's scanner pipeline:

1. structure validation: required files, frontmatter parse, source tier, generated-output boundary
2. static authority cross-check: declared authority versus observed scripts, command docs, MCP declarations, and package adapters
3. prompt-injection heuristics: obvious hostile instruction patterns in imported skills
4. secret scan: keys, tokens, credentials, private URLs, and credential-like literals
5. dependency/script delta: new dependency manifests, executable scripts, shell snippets, and network-capable code

The scanner must return a structured verdict:

- `fail`
- `flagged`
- `pass_with_notes`
- `pass`

The initial scanner is not a cloud service and must not call an LLM. If future scanner stages need judgment, they must dispatch through the existing agent/MCP model and remain separate from this deterministic gate.

### 6. Expose Verify/Audit Through Existing Surfaces

Add user-facing surfaces without creating a parallel dashboard:

- CLI or command: verify local skill supply-chain state.
- MCP tool: return structured guardrail status for dashboard and clients.
- Browse: attach verdicts, findings, authority badges, and actions to existing skill/plugin/capability cards.
- Plugin-pack page: show whether exported client packages are covered by the lock and scanner verdict.

Browse must follow ADR-776 and `docs/architecture-dashboard.md`: findings ride existing file cards through `BrowseItem.metadata` and detail panels. Do not create a bespoke supply-chain Browse mode unless it is a true manager surface.

### 7. Keep Runtime Sandbox, Public Registry, And Signing Out Of Scope

This ADR creates projection-time and install-time guardrails. It does not claim:

- runtime sandbox enforcement
- cryptographic signing/provenance
- public registry publication
- private/team registry federation
- remote scanner service

Those belong to ADR-789.

## Consequences

### Positive

- External skill drift becomes a blocking safety event instead of a warning.
- Augur gets a clear local trust story for skills and plugin packages before building a larger registry.
- Browse and plugin-pack become more honest: they can show why a skill is trusted, flagged, or blocked.
- The work reuses Augur's existing capability exposure, skill health, plugin-pack, Browse, and sync_agents architecture.
- Tank's most useful short-term security patterns are adapted without importing Tank's registry-centered product model.

### Negative

- Some existing external/adopted skills may fail until their authority metadata and lock entries are added.
- Skill authors must maintain one more piece of metadata.
- The first scanner will produce false positives, especially in command docs that describe risky commands for defensive purposes.
- The lockfile and scanner report can create merge churn if their format is not stable.

### Neutral

- This ADR improves install/projection trust, not runtime containment.
- The lockfile is a generated governance artifact, not a replacement for `SKILL.md`.
- The policy vocabulary overlaps with enterprise governance but stays local-first and personal/project friendly.

## Implementation Order

### Phase 1: Schema And Baseline Inventory

1. Define normalized authority classes and policy schema.
2. Add lockfile model and generator using existing path helpers and skill discovery.
3. Generate a baseline lock from real Augur project and private skill roots.
4. Add tests for parsing existing skills, external bundles, and generated plugin-package inputs.

### Phase 2: Integrity Enforcement

1. Change external bundle pin verification from warning-only to fail-closed in guarded mode.
2. Add explicit override policy with audit output.
3. Verify with a real external bundle and with a deliberately mismatched SHA fixture.

### Phase 3: Permission Escalation

1. Add authority-delta comparison module.
2. Support semver-aware and SHA-only comparisons.
3. Wire the gate into sync/projection and plugin-pack export paths.
4. Add tests for patch/minor/major update behavior and high-risk authority additions.

### Phase 4: Local Scanner

1. Implement deterministic scanner stages.
2. Normalize findings into verdicts.
3. Store scanner summary in the lockfile or adjacent generated report.
4. Run the scanner against real project skills and report useful non-empty findings or an explicit clean bill with sampled evidence.

### Phase 5: CLI, MCP, Browse, And Plugin-Pack Surfaces

1. Add a verify/audit command surface.
2. Add an MCP status tool for dashboard/client reads.
3. Attach verdict badges and detail-panel findings to existing Browse cards.
4. Add plugin-pack coverage/readiness output.
5. Run browser verification for any dashboard-visible changes.

### Phase 6: Closeout And Documentation

1. Update architecture docs for skill supply-chain guardrails.
2. Add generated instructions through `sync_agents`.
3. Run ADR value validation on the real skill roots, external bundles, and generated plugin packages.
4. Document remaining future work as ADR-789 scope, not TODO sprawl.

## Alternatives Considered

### Alternative 1: Adopt Tank Directly As Augur's Package Manager

Rejected for short-term work. Tank is registry-centered and TypeScript/Bun/Python-service oriented. Augur's core capability source is a local brain stack projected into many clients. Direct adoption would force Augur to fit a public package manager model before the local trust model is settled.

### Alternative 2: Keep Existing Warning-Only External Skill Pins

Rejected. A warning that still projects a mismatched external skill is not a supply-chain guardrail. It makes the failure visible in logs but leaves the user's clients with the untrusted content.

### Alternative 3: Build Runtime Sandbox First

Rejected for this ADR. Runtime sandboxing is larger, client-dependent, and not shipped in Tank either. The fastest defensible improvement is to prevent untrusted or escalated skill content from being projected in the first place.

### Alternative 4: Hide All Supply-Chain State In CLI Output

Rejected. Augur's dashboard and Browse are user-facing control surfaces. If a skill is blocked or flagged, the user should see that status on the skill/plugin card and in plugin-pack readiness, not only in a terminal log.

## References

- Tank repository: <https://github.com/tankpkg/tank>
- Tank product/security model inspected 2026-05-28: `docs/product/product-brief.md`, `docs/core/security.md`, `packages/internals-helpers/src/permission-escalation.ts`
- `docs/architecture-skills.md`
- `docs/architecture-sync-agents.md`
- `docs/architecture-capability-exposure.md`
- `docs/architecture-dashboard.md`
- `project-brain/capabilities/skills/ai/scripts/sync_agents/external_skills.py`
- `project-brain/capabilities/skills/plugin-pack/SKILL.md`
- `config/system/capability_exposure.yaml`
- ADR-522: Plugin-Pack Multi-Target Plugin Assembly
- ADR-627: Loop Security (Auto Security Audit)
- ADR-635 and ADR-638: Capability Inventory Policy and Control Plane
- ADR-735: Augur Enterprise Governance Layer
- ADR-776: Browse per-item actions for all tabs
- ADR-781 to ADR-783: Harness layering, projection, CLI/MCP tier scoping

## Impact Manifest

```yaml
paths_renamed: []
apis_changed:
  - project-brain/capabilities/skills/ai/scripts/sync_agents/external_skills.py
  - config/external_skills.yaml
  - config/system/capability_exposure.yaml
patterns_deprecated:
  - warning-only external skill pinned_sha mismatch handling
  - projecting external/adopted skills without normalized authority metadata
files_affected:
  - config/system/skill_supply_chain.yaml
  - docs/generated/augur-skills.lock.json
  - docs/generated/skill-manifest.json
  - project-brain/capabilities/skills/ai/scripts/sync_agents/external_skills.py
  - project-brain/capabilities/skills/ai/scripts/sync_agents/
  - project-brain/capabilities/skills/plugin-pack/
  - project-brain/capabilities/skills/auto-skill-quality/
  - apps/dashboard/app/(views)/browse/
  - apps/dashboard/lib/browse/
  - src/lib/
  - src/mcp/augur_mcp/
  - docs/architecture-skills.md
  - docs/architecture-capability-exposure.md
  - docs/architecture-dashboard.md
```

## Implementation Prompt

Use this prompt with `/adr implement ADR-788` after an implementation plan is written.

```text
TeamCreate name="adr-788-skill-supply-chain-guardrails" purpose="Implement local-first Augur skill and plugin supply-chain guardrails inspired by Tank while preserving Augur's brain-layered projection model."

Context:
- ADR-788 is the governing decision.
- Keep the implementation local-first. Do not build a registry, runtime sandbox, remote scanner service, or signing system.
- Reuse existing skill discovery, sync_agents, plugin-pack, capability exposure, Browse, and MCP/dashboard patterns.
- Dashboard-visible changes must flow through MCP and must be verified in a real browser.
- Value validation must run against real Augur skill roots, external bundle config, and generated plugin/package outputs.

TaskCreate id="T1-schema-lock" role="architect" model="sonnet" mode="pipeline" depends_on=[] instructions="
Define the authority vocabulary, policy schema, and lockfile model. Add tests that parse real project skills, private/user skill roots when present, external bundle config, and generated plugin inputs. Do not make the lockfile hand-edited source data."

TaskCreate id="T2-integrity-gate" role="developer" model="sonnet" mode="pipeline" depends_on=["T1-schema-lock"] instructions="
Change external skill pin handling from warning-only to fail-closed in guarded mode. Add explicit override handling and audit output. Include tests for missing source, unresolvable HEAD, matching SHA, and mismatched SHA."

TaskCreate id="T3-permission-escalation" role="security" model="sonnet" mode="pipeline" depends_on=["T1-schema-lock"] instructions="
Implement authority-delta checks adapted from Tank's permission escalation pattern. Support semver-aware and SHA-only sources. High-risk authority additions require major boundary or explicit approval."

TaskCreate id="T4-scanner" role="security" model="sonnet" mode="pipeline" depends_on=["T1-schema-lock"] instructions="
Implement deterministic scanner stages: structure validation, static authority cross-check, prompt-injection heuristics, secret scan, and dependency/script delta. Return fail, flagged, pass_with_notes, or pass with structured findings."

TaskCreate id="T5-surfaces" role="developer" model="sonnet" mode="pipeline" depends_on=["T2-integrity-gate","T3-permission-escalation","T4-scanner"] instructions="
Expose verify/audit through CLI or command, MCP status tool, plugin-pack readiness, and Browse card metadata/detail sections. Follow ADR-776: findings ride existing Browse items."

TaskCreate id="T6-validation" role="validator" model="sonnet" mode="pipeline" depends_on=["T5-surfaces"] instructions="
Run the required Augur auto-loops, generated index/sync steps, browser verification for dashboard-visible changes, stale-reference scans for the Impact Manifest, and real-data value validation against actual Augur skills and plugin outputs. Report findings honestly."
```
