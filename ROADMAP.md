# Roadmap

Augur is a local-first personal AI operating system. This roadmap is the public release plan: what's shipped, what's in flight, and what's next. Dates are phase-level targets, not per-feature commitments.

How to read this:

- `[shipped]` — landed in main, behavior verified.
- `[in-flight]` — actively being built, ADR or PR open.
- `[planned]` — scoped, not started.

Each item links to its ADR or implementation plan. ADRs live in the private architecture repo; PRs and CI runs are visible on GitHub.

## Phase 1 — Soft launch (April 2026, now)

Theme: prove the harness on macOS, finish the architecture for Windows.

- [shipped]   Native macOS: install path, dashboard, MCP gateway, curated skill library across six hubs (adaptive, brain, career, command, life, studio)
- [shipped]   MCP-native multi-client: Claude Code, Codex, Cursor, Gemini, Copilot, Ollama
- [shipped]   Local dashboard at localhost:3000
- [shipped]   Wiki compiler (concept-first) and ingest pipeline   <!-- ADR-559/560/561/564 -->
- [shipped]   Browse workbench redesign + skills tab               <!-- ADR-540/541/554 -->
- [shipped]   Security autoloop (S1–S5 + Tank CLI)                 <!-- loop-security -->
- [shipped]   Gemini extension support                             <!-- ADR-553 -->
- [shipped]   Runtime IDE registry — design landed; integration follow-on in flight  <!-- ADR-562 -->
- [shipped]   MVP staged release payloads                          <!-- ADR-557 -->
- [in-flight] Vault user surfaces (phase 1)                        <!-- 2026-04-23 plan -->
- [in-flight] Windows native: architecture done, validation pending <!-- ADR-550 -->

## Phase 2 — MVP release (May 2026)

Theme: tighten validation, ship a version a non-developer can install.

- [planned]  npx-based one-command install on macOS
- [planned]  Windows GA after validation passes
- [planned]  Open-source brain/inbox/wiki insights surface         <!-- ADR-564 -->
- [planned]  Sync managed-output purge for clean re-installs       <!-- ADR-558 -->
- [planned]  Documented upgrade and rollback paths

## Phase 3 — Monthly cadence (June 2026 onward)

Theme: predictable shipping, fold validated platforms into the public story.

- [planned]  Monthly release train
- [planned]  Public Windows support claim once validation is green
- [planned]  Skill group and release enablement                    <!-- ADR-551 -->
- [planned]  Continued autoloop expansion (security, ops, repo)

## Enterprise and commercial

Commercial deployment, rollout support, and organization-wide infrastructure go through Guriqo. See https://guriqo.com.
