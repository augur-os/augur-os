# routine-vault golden fixtures

These directories mirror real-world bloat patterns. Tests in
`tests/test_hygiene_e2e.py` copy them into `tmp_path` and exercise
the full scan + apply pipeline against them.

| Fixture | Shape | Tested behavior |
|---|---|---|
| fixture_websites_versioned/ | 50 fake `.zip` files matching `guriqo-com-V*.zip` and `augur-run-V*.zip` patterns | scan returns all; apply moves N stale, keeps current; `.augur-ignore` written |
| fixture_logos_mixed/ | guriqo-logo.png, guriqo-logo.svg, augur-logo.png, augur-logo.svg | scan returns all four; the agent's job to recognize two artifact groups |
| fixture_format_variants/ | augur-vision-1.pdf, augur-vision-1.pptx (same logical version, different format) | scan returns both; rubric instructs the agent NOT to mark either as stale |
| fixture_deploy_root/ | .augur-lifecycle.yaml with `deploy_root: true` + a few .zip files | scan returns config; apply refuses every move with `deploy_root` |
| fixture_milestone_pinned/ | .milestones.json pinning one .pptx + several other .pptx files | scan returns pins; apply refuses the pinned file |
| fixture_renamed_iteration/ | two Markdown files with frontmatter replacement metadata | Tier 2 renamed-iteration prompt candidate |
| fixture_variant_suffix/ | two banner image variants with role suffixes | Tier 2 variant-suffix prompt candidate |
| fixture_mixed_version_scheme/ | zip files using both `v33-1` and `V10032` schemes | Tier 2 mixed-version prompt candidate |
| fixture_conceptual_supersession/ | two Markdown files with `replaces` / `superseded_by` metadata | Tier 3 content-inspection prompt candidate |
| fixture_cached_known_group/ | lifecycle YAML with cached `highest_version` group | no question; cache can drive known-group moves |
| fixture_lifecycle_malformed_groups/ | lifecycle YAML with invalid strategy | scan returns warning and ignores cache |

All fake artifact bytes are minimal (1-100 bytes per file). The
fixtures exist for plumbing tests, not for content tests.

**Binary-named files are generated, not tracked** (ADR-814: no binary
suffixes under project-brain/). Only text content (`.augur-lifecycle.yaml`,
`.milestones.json`, `*.md`, `*.svg`) is committed; the fake `.zip` / `.pptx`
/ `.pdf` / `.png` placeholders are written by `build_fixtures.py`.
`test_hygiene_e2e.py` calls `ensure_fixtures()` automatically; for manual
eval runs use `python build_fixtures.py`.
