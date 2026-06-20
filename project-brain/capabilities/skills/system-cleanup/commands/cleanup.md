---
name: cleanup
description: "Disk cleanup walkthrough — scan macOS disk-waste categories, confirm per category with the user, reversibly trash approved items, report honestly. Usage: /cleanup [category] [--help]"
visibility: ops
x-augur-tags:
  - macos
  - disk
  - maintenance
x-augur-export-command: false
---

# /cleanup

Free disk space on macOS: show system pressure and category sizes, scan the
categories the user cares about, get explicit confirmation, then move approved
items to the OS Trash (reversible). Scripts live in
`project-brain/capabilities/skills/system-cleanup/scripts/`.

If invoked with `--help`, display this usage and stop — do not execute.

## Usage

- `/cleanup` — full walkthrough across all categories
- `/cleanup dev-artifacts` — scope to one category
- `/cleanup --help` — show usage and stop

## Workflow

1. **Overview.** Run
   `uv run python project-brain/capabilities/skills/system-cleanup/scripts/cleanup_stats.py --json`
   and present disk pressure plus category sizes sorted largest-first. If
   `$ARGUMENTS` names a category, skip straight to scanning it.
2. **Scan.** For each category worth pursuing (largest first, or the one the
   user named), run
   `uv run python .../scripts/cleanup_scan.py --category <id> --limit 25 --json`
   and show the biggest items with real sizes. Scans are read-only.
3. **Grouped confirmation.** Present the candidates grouped by category and
   ask the user explicitly which categories — or which individual items — to
   clean. Never proceed on silence or inference; no approval means stop after
   reporting. Remind the user that `trash` is report-only (Finder's Empty
   Trash) and that everything else is recoverable from the OS Trash.
4. **Execute.** For each approved category, run
   `uv run python .../scripts/cleanup_execute.py --category <id> [--items <paths>] --confirm --json`.
   Use `--items` when the user approved a subset. Never bypass the script
   with raw `rm`/`rm -rf`.
5. **Honest report.** Summarize per category: items trashed, space reclaimed,
   protected paths skipped, rejected items, and failures — straight from the
   script output, no rounding up. State explicitly that trashed items sit in
   the OS Trash until the user empties it, and name anything that was NOT
   cleaned and why.
