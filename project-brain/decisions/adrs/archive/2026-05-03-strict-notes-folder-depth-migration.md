# Strict Notes Folder Depth Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforce a strict, Obsidian-first folder-depth policy for `Au-vault/notes/` and migrate the obvious deep or duplicated folders without moving protected runtime roots.

**Architecture:** Add an Augur-owned scanner that measures `notes/` depth and reports duplicated `notes` layers, config/template directories under notes, and skinny deep folder chains. Use that scanner to guide a focused vault migration commit, then update any real path references in Augur/Au-vault and verify MCP/Browse readers still see the migrated data.

**Tech Stack:** Python 3.11, pytest, git, Au-vault markdown/YAML data, Augur `src.config.paths` helpers.

---

## File Structure

**Augur repo changes**

- Create `scripts/check_notes_depth.py`: strict notes-depth scanner with allowlisted dense collection paths.
- Create `tests/scripts/test_check_notes_depth.py`: unit tests for skinny folders, duplicated `notes` layers, config/template folders, allowlists, and CLI exit behavior.
- Modify `docs/superpowers/specs/2026-05-03-strict-notes-folder-depth-design.md`: only if the implementation finds a concrete mismatch between the accepted spec and live path reality.
- Modify code/tests only where a moved path is a real dependency.

**Au-vault changes**

- Move tracked files with `git -C ~/Projects/Au-vault mv`.
- Move config/template files from `notes/` to `config/`.
- Update vault-owned docs and note links that reference moved paths.
- Commit Au-vault moves separately from Augur scanner/code changes.

**Move Set For First Strict Pass**

Use this reviewed move set as the first pass:

| Source | Target |
| --- | --- |
| `notes/augur/advisor/design/docs/architecture/llm_journey_map.md` | `notes/augur/advisor/llm-journey-map.md` |
| `notes/books/notes/*.md` | `notes/books/*.md` |
| `notes/career/notes/hard-skills/*.md` | `notes/career/hard-skills/*.md` |
| `notes/career/notes/learning/scoring-formulas.md` | `notes/career/learning/scoring-formulas.md` |
| `notes/career/notes/proposals/2026-04-29-samsung-ai-kickoff-pricing-draft.md` | `notes/career/proposals/2026-04-29-samsung-ai-kickoff-pricing-draft.md` |
| `notes/career/notes/sessions/2026-04-29-samsung-ai-kickoff-proposal.md` | `notes/career/sessions/2026-04-29-samsung-ai-kickoff-proposal.md` |
| `notes/lifestyle/eisenhower/notes/*.md` | `notes/lifestyle/eisenhower/*.md` |
| `notes/lifestyle/notes/notion-notes.md` | `notes/lifestyle/knowledge/notion-notes.md` |
| `notes/lifestyle/notes/_templates/idea.md` | `config/lifestyle/templates/idea.md` |
| `notes/lifestyle/ideas/_config/config.yaml` | `config/lifestyle/ideas/config.yaml` |
| `notes/lifestyle/recipe-manager/config/settings.yaml` | `config/recipe-manager/settings.yaml` |
| `notes/venture/content/linkedin/notes/2026-04-24-firmware-ai-adoption-thesis.md` | `notes/venture/content/linkedin/2026-04-24-firmware-ai-adoption-thesis.md` |
| `notes/venture/notes/*.md` | `notes/venture/*.md` |

Dense collections that remain after the first pass:

- `notes/augur/platform-admin/setup/ollama/`
- `notes/health/virtual-doctor/medications/`
- `notes/health/virtual-doctor/symptoms/`
- `notes/lifestyle/recipe-manager/recipes/perfected/`
- `notes/lifestyle/recipe-manager/recipes/to-try/`
- `notes/venture/content/linkedin/assets/`
- `notes/venture/content/linkedin/context/`
- `notes/venture/content/linkedin/posts/`

## Task 1: Add Strict Notes-Depth Scanner

**Files:**
- Create: `scripts/check_notes_depth.py`
- Create: `tests/scripts/test_check_notes_depth.py`

- [ ] **Step 1: Write failing scanner tests**

Create `tests/scripts/test_check_notes_depth.py` with:

```python
from pathlib import Path

from scripts.check_notes_depth import (
    DEFAULT_ALLOWED_DEEP_DIRS,
    NotesDepthIssue,
    check_notes_depth,
)


def _write(path: Path, text: str = "content") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_reports_skinny_deep_folder_chain(tmp_path: Path) -> None:
    notes = tmp_path / "notes"
    _write(notes / "augur" / "advisor" / "design" / "docs" / "architecture" / "llm.md")

    issues = check_notes_depth(notes, allowed_deep_dirs=set())

    assert NotesDepthIssue(
        kind="skinny_deep_dir",
        path=Path("augur/advisor/design"),
        message="Directory has exactly one file descendant at depth 3.",
    ) in issues


def test_reports_repeated_notes_layer(tmp_path: Path) -> None:
    notes = tmp_path / "notes"
    _write(notes / "career" / "notes" / "learning" / "scoring-formulas.md")

    issues = check_notes_depth(notes, allowed_deep_dirs=set())

    assert NotesDepthIssue(
        kind="repeated_notes_layer",
        path=Path("career/notes/learning/scoring-formulas.md"),
        message="Path contains a nested 'notes' folder under the notes root.",
    ) in issues


def test_reports_config_and_template_dirs_under_notes(tmp_path: Path) -> None:
    notes = tmp_path / "notes"
    _write(notes / "lifestyle" / "ideas" / "_config" / "config.yaml")
    _write(notes / "lifestyle" / "notes" / "_templates" / "idea.md")

    issues = check_notes_depth(notes, allowed_deep_dirs=set())

    assert NotesDepthIssue(
        kind="config_under_notes",
        path=Path("lifestyle/ideas/_config/config.yaml"),
        message="Config or template path lives under notes.",
    ) in issues
    assert NotesDepthIssue(
        kind="config_under_notes",
        path=Path("lifestyle/notes/_templates/idea.md"),
        message="Config or template path lives under notes.",
    ) in issues


def test_allows_dense_collection_dirs(tmp_path: Path) -> None:
    notes = tmp_path / "notes"
    _write(notes / "lifestyle" / "recipe-manager" / "recipes" / "to-try" / "one.md")
    _write(notes / "lifestyle" / "recipe-manager" / "recipes" / "to-try" / "two.md")

    issues = check_notes_depth(notes, allowed_deep_dirs=DEFAULT_ALLOWED_DEEP_DIRS)

    assert not issues


def test_missing_notes_root_is_an_issue(tmp_path: Path) -> None:
    issues = check_notes_depth(tmp_path / "notes", allowed_deep_dirs=set())

    assert issues == [
        NotesDepthIssue(
            kind="missing_notes_root",
            path=Path("."),
            message="Notes root does not exist.",
        )
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m pytest -q tests/scripts/test_check_notes_depth.py
```

Expected: fail because `scripts/check_notes_depth.py` does not exist.

- [ ] **Step 3: Implement scanner**

Create `scripts/check_notes_depth.py`:

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config.paths import get_vault_dir  # noqa: E402

CONFIG_DIR_NAMES = {"config", "_config", "_templates"}
DEFAULT_ALLOWED_DEEP_DIRS = {
    Path("augur/platform-admin/setup/ollama"),
    Path("health/virtual-doctor/medications"),
    Path("health/virtual-doctor/symptoms"),
    Path("lifestyle/recipe-manager/recipes/perfected"),
    Path("lifestyle/recipe-manager/recipes/to-try"),
    Path("venture/content/linkedin/assets"),
    Path("venture/content/linkedin/context"),
    Path("venture/content/linkedin/posts"),
}


@dataclass(frozen=True, order=True)
class NotesDepthIssue:
    kind: str
    path: Path
    message: str


def _is_hidden(rel_path: Path) -> bool:
    return any(part.startswith(".") for part in rel_path.parts)


def _is_allowed(rel_path: Path, allowed_deep_dirs: set[Path]) -> bool:
    return any(rel_path == allowed or allowed in rel_path.parents for allowed in allowed_deep_dirs)


def _files(notes_root: Path) -> list[Path]:
    return sorted(
        path.relative_to(notes_root)
        for path in notes_root.rglob("*")
        if path.is_file() and not _is_hidden(path.relative_to(notes_root))
    )


def check_notes_depth(
    notes_root: Path,
    *,
    allowed_deep_dirs: set[Path] | None = None,
    min_skinny_dir_depth: int = 3,
) -> list[NotesDepthIssue]:
    allowed = set(DEFAULT_ALLOWED_DEEP_DIRS if allowed_deep_dirs is None else allowed_deep_dirs)
    if not notes_root.exists():
        return [
            NotesDepthIssue(
                kind="missing_notes_root",
                path=Path("."),
                message="Notes root does not exist.",
            )
        ]

    issues: set[NotesDepthIssue] = set()
    files = _files(notes_root)

    for rel_file in files:
        if "notes" in rel_file.parts:
            issues.add(
                NotesDepthIssue(
                    kind="repeated_notes_layer",
                    path=rel_file,
                    message="Path contains a nested 'notes' folder under the notes root.",
                )
            )
        if any(part in CONFIG_DIR_NAMES for part in rel_file.parts):
            issues.add(
                NotesDepthIssue(
                    kind="config_under_notes",
                    path=rel_file,
                    message="Config or template path lives under notes.",
                )
            )

    for directory in sorted(path for path in notes_root.rglob("*") if path.is_dir()):
        rel_dir = directory.relative_to(notes_root)
        if _is_hidden(rel_dir) or _is_allowed(rel_dir, allowed):
            continue
        if len(rel_dir.parts) < min_skinny_dir_depth:
            continue
        descendant_files = [
            rel_file for rel_file in files if rel_file.parent == rel_dir or rel_dir in rel_file.parents
        ]
        if len(descendant_files) == 1:
            issues.add(
                NotesDepthIssue(
                    kind="skinny_deep_dir",
                    path=rel_dir,
                    message=f"Directory has exactly one file descendant at depth {len(rel_dir.parts)}.",
                )
            )

    return sorted(issues)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Au-vault notes folder depth against the strict contract.")
    parser.add_argument("--notes-root", type=Path, default=get_vault_dir() / "notes")
    args = parser.parse_args()

    issues = check_notes_depth(args.notes_root)
    if issues:
        print("Strict notes-depth issues:")
        for issue in issues:
            print(f"- {issue.kind}: {issue.path.as_posix()} - {issue.message}")
        return 1

    print("Notes folder depth matches strict contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run scanner tests**

Run:

```bash
python3 -m pytest -q tests/scripts/test_check_notes_depth.py
```

Expected: `5 passed`.

- [ ] **Step 5: Run scanner against live vault and capture current failures**

Run:

```bash
python3 scripts/check_notes_depth.py || true
```

Expected: output includes the current duplicated `notes` layers and config/template paths. This is the baseline that the vault move task must clear.

- [ ] **Step 6: Commit scanner**

Run:

```bash
git add scripts/check_notes_depth.py tests/scripts/test_check_notes_depth.py
git commit -m "test(vault): add strict notes depth scanner"
```

Expected: one Augur commit.

## Task 2: Apply Planned Au-vault Moves

**Files:**
- Move tracked files inside `~/Projects/Au-vault`
- Modify vault markdown files that contain links to moved paths
- Modify vault skill reference docs that describe old path structure

- [ ] **Step 1: Confirm Au-vault starts clean**

Run:

```bash
git -C ~/Projects/Au-vault status --short --branch
```

Expected:

```text
## main...origin/main
```

- [ ] **Step 2: Create target directories**

Run:

```bash
mkdir -p \
  ~/Projects/Au-vault/notes/augur/advisor/architecture \
  ~/Projects/Au-vault/notes/career/hard-skills \
  ~/Projects/Au-vault/notes/career/learning \
  ~/Projects/Au-vault/notes/career/proposals \
  ~/Projects/Au-vault/notes/career/sessions \
  ~/Projects/Au-vault/config/lifestyle/ideas \
  ~/Projects/Au-vault/config/lifestyle/templates \
  ~/Projects/Au-vault/config/recipe-manager
```

Expected: command exits 0.

- [ ] **Step 3: Move single-file deep advisor note**

Run:

```bash
git -C ~/Projects/Au-vault mv \
  notes/augur/advisor/design/docs/architecture/llm_journey_map.md \
  notes/augur/advisor/llm-journey-map.md
```

Expected: command exits 0.

- [ ] **Step 4: Move books notes up one level**

Run:

```bash
for path in ~/Projects/Au-vault/notes/books/notes/*.md; do
  git -C ~/Projects/Au-vault mv "notes/books/notes/$(basename "$path")" "notes/books/$(basename "$path")"
done
```

Expected: all book notes move to `notes/books/*.md`.

- [ ] **Step 5: Move career notes out of duplicated notes layer**

Run:

```bash
for path in ~/Projects/Au-vault/notes/career/notes/hard-skills/*.md; do
  git -C ~/Projects/Au-vault mv "notes/career/notes/hard-skills/$(basename "$path")" "notes/career/hard-skills/$(basename "$path")"
done
git -C ~/Projects/Au-vault mv \
  notes/career/notes/learning/scoring-formulas.md \
  notes/career/learning/scoring-formulas.md
git -C ~/Projects/Au-vault mv \
  notes/career/notes/proposals/2026-04-29-samsung-ai-kickoff-pricing-draft.md \
  notes/career/proposals/2026-04-29-samsung-ai-kickoff-pricing-draft.md
git -C ~/Projects/Au-vault mv \
  notes/career/notes/sessions/2026-04-29-samsung-ai-kickoff-proposal.md \
  notes/career/sessions/2026-04-29-samsung-ai-kickoff-proposal.md
```

Expected: no files remain under `notes/career/notes/`.

- [ ] **Step 6: Move lifestyle/eisenhower and lifestyle note/template paths**

Run:

```bash
for path in ~/Projects/Au-vault/notes/lifestyle/eisenhower/notes/*.md; do
  git -C ~/Projects/Au-vault mv "notes/lifestyle/eisenhower/notes/$(basename "$path")" "notes/lifestyle/eisenhower/$(basename "$path")"
done
git -C ~/Projects/Au-vault mv \
  notes/lifestyle/notes/notion-notes.md \
  notes/lifestyle/knowledge/notion-notes.md
git -C ~/Projects/Au-vault mv \
  notes/lifestyle/notes/_templates/idea.md \
  config/lifestyle/templates/idea.md
git -C ~/Projects/Au-vault mv \
  notes/lifestyle/ideas/_config/config.yaml \
  config/lifestyle/ideas/config.yaml
git -C ~/Projects/Au-vault mv \
  notes/lifestyle/recipe-manager/config/settings.yaml \
  config/recipe-manager/settings.yaml
```

Expected: no files remain under `notes/lifestyle/notes/`, `notes/lifestyle/ideas/_config/`, or `notes/lifestyle/recipe-manager/config/`.

- [ ] **Step 7: Move venture notes out of duplicated notes layers**

Run:

```bash
git -C ~/Projects/Au-vault mv \
  notes/venture/content/linkedin/notes/2026-04-24-firmware-ai-adoption-thesis.md \
  notes/venture/content/linkedin/2026-04-24-firmware-ai-adoption-thesis.md
for path in ~/Projects/Au-vault/notes/venture/notes/*.md; do
  git -C ~/Projects/Au-vault mv "notes/venture/notes/$(basename "$path")" "notes/venture/$(basename "$path")"
done
```

Expected: no files remain under `notes/venture/content/linkedin/notes/` or `notes/venture/notes/`.

- [ ] **Step 8: Remove empty directories and macOS metadata residue**

Run:

```bash
find ~/Projects/Au-vault/notes -name .DS_Store -delete
find ~/Projects/Au-vault/notes -type d -empty -delete
```

Expected: empty source directories from the moves are removed. `git status` still shows only planned tracked moves and text edits.

- [ ] **Step 9: Update vault text references to canonical paths**

Run the reference sweep:

```bash
rg -n "notes/(books|career|lifestyle|venture).*/notes/|career-ops/notes|llm_journey_map|firmware-ai-adoption-thesis|recipe-manager/config|ideas/_config" ~/Projects/Au-vault -g '!wiki/**' -g '!.git'
```

Apply focused edits with `apply_patch` for real references outside `wiki/`:

```markdown
# Expected edits
- `skills/career-ops/SKILL.md`: change `notes/hard-skills/` and `notes/learning/` descriptions to `hard-skills/` and `learning/` under `notes/career/`.
- `skills/lifestyle/references/data-structure.md`: update `notes/notion-notes.md`, `_templates/idea.md`, and recipe-manager config descriptions to new canonical locations.
- `notes/venture/content/linkedin/posts/2026-04-24-firmware-is-not-behind.md`: change `related_notes: [notes/2026-04-24-firmware-ai-adoption-thesis.md]` to `related_notes: [../2026-04-24-firmware-ai-adoption-thesis.md]`.
- `notes/career/proposals/2026-04-29-samsung-ai-kickoff-pricing-draft.md`: change old `career-ops/notes/sessions/...` references to `notes/career/sessions/...`.
```

Expected: the second `rg` run outside `wiki/` returns only the strict-depth design/plan docs or no active vault references.

- [ ] **Step 10: Run strict scanner against live vault**

Run:

```bash
python3 scripts/check_notes_depth.py
```

Expected:

```text
Notes folder depth matches strict contract
```

- [ ] **Step 11: Commit Au-vault migration**

Run:

```bash
git -C ~/Projects/Au-vault status --short
git -C ~/Projects/Au-vault diff --check
git -C ~/Projects/Au-vault add -A
git -C ~/Projects/Au-vault commit -m "chore(vault): flatten strict notes folder depth"
```

Expected: one Au-vault commit with tracked moves and reference edits.

## Task 3: Update Code Contracts For Moved Config Paths

**Files:**
- Inspect and modify only if references exist:
  - `~/Projects/Au-vault/skills/lifestyle/scripts/mcp/_shared.py`
  - `~/Projects/Au-vault/skills/lifestyle/augur/tests/*`
  - Augur path/helper tests that assert vault-relative layouts

- [ ] **Step 1: Search for code references to moved config paths**

Run:

```bash
rg -n "recipe-manager/config|ideas/_config|lifestyle/notes|career/notes|books/notes|linkedin/notes" \
  ~/Projects/Augur/.worktrees/obsidian-vault-root-migration \
  ~/Projects/Au-vault \
  -g '!wiki/**' -g '!docs/superpowers/**' -g '!.git'
```

Expected: no code references to moved paths, or a short list of real callers to update.

- [ ] **Step 2: If lifestyle config readers use old paths, update them**

If the search finds a real reader in `skills/lifestyle/scripts/mcp/_shared.py`, change it to use `get_vault_config_dir()` for config and keep recipe notes under `get_own_data_dir(__file__) / "recipe-manager" / "recipes"`.

Use this pattern:

```python
from src.config.paths import get_vault_config_dir
from src.lib.skill_paths import get_own_data_dir


def _recipe_settings_path() -> Path:
    return get_vault_config_dir() / "recipe-manager" / "settings.yaml"


def _lifestyle_ideas_config_path() -> Path:
    return get_vault_config_dir() / "lifestyle" / "ideas" / "config.yaml"
```

Expected: config readers no longer look under `notes/lifestyle/.../config`.

- [ ] **Step 3: Add or update tests for any changed reader**

If Step 2 changes a reader, add a test in the owning Au-vault skill test folder. The test should create a temporary vault with `config/recipe-manager/settings.yaml`, monkeypatch the vault path helper used by the reader, and assert the reader loads that file instead of a notes path.

Use this assertion shape:

```python
assert loaded_settings["source_path"].endswith("config/recipe-manager/settings.yaml")
```

Expected: the test fails before the reader update and passes after it.

- [ ] **Step 4: Run impacted code tests**

Run:

```bash
PYTHONPATH=~/Projects/Augur/.worktrees/obsidian-vault-root-migration:~/Projects/Au-vault \
  python3 -m pytest -q \
  ~/Projects/Au-vault/skills/lifestyle/augur/tests \
  ~/Projects/Au-vault/skills/career-ops/augur/tests \
  ~/Projects/Au-vault/skills/books/augur/tests \
  ~/Projects/Au-vault/skills/content/augur/tests/test_linkedin_writer.py \
  ~/Projects/Au-vault/skills/content/augur/tests/test_linkedin_writer_tools.py
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit code-contract updates if any**

If files changed in Augur:

```bash
git status --short
git add -A
git commit -m "fix(vault): align readers with strict notes depth"
```

If files changed in Au-vault after the migration commit:

```bash
git -C ~/Projects/Au-vault status --short
git -C ~/Projects/Au-vault add -A
git -C ~/Projects/Au-vault commit -m "fix(vault): align skill readers with strict notes depth"
```

Expected: no uncommitted reader/reference changes remain.

## Task 4: Full Verification And Push

**Files:**
- No planned source edits unless verification exposes a real blocker.

- [ ] **Step 1: Run Augur verification**

Run:

```bash
python3 -m pytest -q \
  tests/scripts/test_check_notes_depth.py \
  tests/scripts/test_check_obsidian_vault_roots.py \
  tests/src \
  tests/test_skill_paths.py \
  tests/mcp/test_core_hub_wrappers.py \
  tests/mcp/test_hub_vault_notes.py \
  tests/mcp/test_hub_recent.py \
  tests/mcp/test_shared_config_paths.py
```

Expected: all selected tests pass.

- [ ] **Step 2: Run Au-vault impacted suite**

Run:

```bash
PYTHONPATH=~/Projects/Augur/.worktrees/obsidian-vault-root-migration:~/Projects/Au-vault \
  python3 -m pytest -q \
  ~/Projects/Au-vault/skills/lifestyle/augur/tests \
  ~/Projects/Au-vault/skills/career-ops/augur/tests \
  ~/Projects/Au-vault/skills/books/augur/tests \
  ~/Projects/Au-vault/skills/content/augur/tests/test_linkedin_writer.py \
  ~/Projects/Au-vault/skills/content/augur/tests/test_linkedin_writer_tools.py \
  ~/Projects/Au-vault/skills/ingest/augur/tests/test_wiki_scanner.py
```

Expected: all selected tests pass.

- [ ] **Step 3: Run generated-surface and vault checks**

Run:

```bash
python3 -m skills.ai.scripts.sync_agents check
python3 apps/dashboard/scripts/generate_registry.py --check --quiet
python3 scripts/check_obsidian_vault_roots.py
python3 scripts/check_notes_depth.py
git diff --check
git -C ~/Projects/Au-vault diff --check
```

Expected:

```text
Generated agent files are up to date
Registry is up to date
Vault roots match Obsidian-first contract
Notes folder depth matches strict contract
```

Both diff checks exit 0.

- [ ] **Step 4: Run vault hygiene scan**

Run:

```bash
python3 - <<'PY'
from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path
from src.lib.ops_protocol import OpsContext

module_path = Path("skills/loop-repo/scripts/vault_hygiene_ops.py")
spec = spec_from_file_location("vault_hygiene_ops", module_path)
module = module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)
result = module.scan(OpsContext(project_root=Path.cwd(), difficulty=1))
print(result.health, result.severity, result.summary)
for issue in result.issues:
    print(issue.get("severity"), issue.get("kind"), issue.get("file"), "-", issue.get("message"))
raise SystemExit(0 if result.health == "verified" else 1)
PY
```

Expected: `verified`. If the only issue is unpushed vault commits, push the vault before the final status check.

- [ ] **Step 5: Push both repos**

Run:

```bash
git push
git -C ~/Projects/Au-vault push origin main
```

Expected: Augur branch and Au-vault `main` push successfully.

- [ ] **Step 6: Final post-push status**

Run:

```bash
git status --short --branch
git -C ~/Projects/Au-vault status --short --branch
python3 scripts/check_notes_depth.py
```

Expected:

```text
## work/obsidian-vault-root-migration...origin/work/obsidian-vault-root-migration
## main...origin/main
Notes folder depth matches strict contract
```

## Task 5: Handoff Notes

**Files:**
- No file changes.

- [ ] **Step 1: Summarize committed changes**

Report:

- Augur commits created.
- Au-vault commits created.
- Number of moved vault files.
- Whether any code references required updates.
- Verification commands and pass counts.
- Any allowed dense folders that remain by policy.

- [ ] **Step 2: Name intentional leftovers**

Report these as intentional if still present:

- root temporary review folders: `apple`, `content`, `growth`, `updater`, `remote-access`
- dense `notes/` collections listed in this plan
- compiled `wiki/` source citations if they still reference old source locations; those should be refreshed by the wiki compiler/reindex flow rather than hand-edited in this migration
