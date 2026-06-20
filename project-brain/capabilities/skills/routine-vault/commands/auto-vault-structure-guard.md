---
x-augur-runner: orchestrator
---
# auto-vault-structure-guard

Domains-layout structure guard — flags legacy top-level folders reappearing at the vault root, unexpected root files, and test-artifact name patterns in content areas. Report-only, never auto-fixes. Only active when the vault BRAIN.yaml declares `layout: domains`.

- callable: `scripts/structure_guard.py`
- loop: `hardening`
- focus: legacy machine folders at root, unexpected root files, test artifacts in content areas, naming-standard violations

## Naming rules (spec 2026-06-12)

Each `.md` filename stem in the vault content area must satisfy all three constraints:

- **Length** — stem must be ≤ 40 characters. Finding: `name too long (N > 40): <path>`
- **No dates outside event dirs** — a stem starting with `YYYY-MM-DD-` is only allowed when an ancestor directory is one of the designated event dirs: `linkedin`, `pipeline`, `meetings`, `daily`. Finding: `dated name outside event dirs: <path>`
- **No URL fragments** — a stem must not contain URL-derived noise substrings such as `-https-`, `-www-`, `-com-`, `-org-`, or `-io-`. Finding: `url fragment in name: <path>`

**Wiki exemption:** `wiki/` is exempt from the naming checks (only — the structural and test-artifact checks still apply there). Wiki names are generator-owned: the slug formula in `ingest/scripts/wiki_concept_pages.py` produces the `how-should-X-be-used` shape by contract, and renaming wiki files would break ~1,400 path-qualified links before the next compile regenerates the old names anyway. Naming governance for wiki happens generator-side — see the follow-up note in the 2026-06-12 naming spec.

Violations are report-only. Fix by renaming the file (see `scripts/migrations/apply_renames.py` for batch rename tooling with wikilink rewrite).
