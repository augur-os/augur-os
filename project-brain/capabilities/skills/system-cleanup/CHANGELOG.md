# Changelog

All notable changes to the system-cleanup skill will be documented in this file.

## [1.1.0] - 2026-06-11

### Changed
- Adopted into `project-brain/capabilities/skills/system-cleanup/` as a
  selective port of the staged r3 draft (ADR-805 native-first, ADR-813
  command ladder).
- SKILL.md rewritten: retired `x-augur-hub`/`x-augur-tab`/`x-augur-group`/
  `x-augur-release` fields stripped (ADR-802); MCP tool, dashboard-page, and
  ops-board block declarations dropped (nothing ships this round); the one
  command is declared via `x-augur-commands`.
- MCP tool modules (`scripts/mcp/tools_scan|stats|execute.py`) converted to
  plain CLI scripts (`cleanup_scan.py`, `cleanup_stats.py`,
  `cleanup_execute.py`); the dead `augur_mcp` package imports disappeared
  with the conversion (no MCP registration remains).
- **Executor rewritten to trash-safe semantics**: the staged executor
  hard-deleted (`shutil.rmtree`/`unlink`) the entire category ROOT (e.g. all
  of `~/Library/Caches`) and silently ignored its `items` parameter. The
  ported executor moves individual scanned items to the OS Trash via
  `send2trash` (prior art: file-manager-augur `scripts/trash.py`), is
  dry-run by default (`--confirm` gate), validates `--items` against the
  scan result, skips protected paths (repo, vault/documents stores via
  `src.config.paths`, `~/Documents`, home, outside-home), and refuses the
  report-only `trash` category.
- `~/Documents` removed from the large-files scan dirs (it is a protected
  root, so scan results there would never be actionable).
- Category size estimation switched from full `rglob` to `du`-backed sizing
  for usable wall-clock time on real cache trees.

### Added
- `/cleanup` command orchestrating stats overview, per-category scan, grouped
  user confirmation, reversible execution, and an honest report.
- `augur/tests/` smoke + behavior tests: scanner on a tmp fixture,
  execute-refuses-without-confirmation, protected-path guard, item
  validation, report-only trash category, side-effect-free scan.

### Removed (excluded from the port)
- `scripts/tab_scorer.py` — dead hub-era machinery writing `order` values
  into augur.yaml for the retired `/ops-tabs` surface (ADR-802).
- `scripts/mcp/tools_permissions.py` and `scripts/mcp/_common.py` permission
  probing — screen-recording/microphone/calendar/Notes/Mail/tesseract checks
  entangled with the apple skill and daemon inbox config; onboarding
  territory, not disk cleanup.
- Hub-era SKILL.md machinery: `x-augur-dashboard-pages`, ops-board block,
  API-route table, `x-augur-cli-integrations` (osascript/tesseract were for
  the excluded permission probing), `x-augur-data-deps: daemon`.
- Staged auto-generated tests (broken `skills.system-cleanup` import paths)
  and `evals/evals.json` (asserted the excluded MCP tools); `evals/rank.json`
  kept verbatim as a historical record.

## [1.0.0] - 2026-03-27

### Added
- Initial staged draft: MCP scan/stats/execute/permissions tools, dashboard
  page and ops-board block, tab maturity scorer.
