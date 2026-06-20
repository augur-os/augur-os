# Brain Archive Git-History Purge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make git-aware Browse Sweep archive brain-owned vault and skill targets by committing and pushing an archive move, then purging the archived payload while preserving `archive/_ledger/sweep.jsonl` recovery events.

**Architecture:** Extend the existing loop-hygiene git-aware archive path instead of adding a second archive system. `git_archive.py` owns validation, git move, ledger events, commit, push, and purge. `hygiene_apply.py` routes git-managed Sweep targets to the new lifecycle. `archive_index.py` folds the append-only ledger into Browse Archive entries, and the Browse MCP index points at brain archive roots instead of only legacy `archive/sweep` ledgers. The legacy move-only functions remain available for compatibility, but git-aware Sweep uses `git-history-purge`.

**Tech Stack:** Python 3.11+, git CLI through `subprocess.run`, pytest, Augur Browse MCP indexing.

**Source of truth:** `docs/adrs/ADR-749-brain-archive-git-history-purge.md` and `docs/superpowers/specs/2026-05-14-brain-archive-git-history-purge-design.md`.

**Test policy:** Per AGENTS.md rules 19 and 29, whole-suite verification and commit-readiness go through `/auto-test-pytest`, `/auto-test-dashboard`, and `/auto-lint`. The per-step `pytest` invocations below are for focused TDD red-green work on the touched tests only.

---

## File Structure

**Archive lifecycle:**
- Modify: `shared-vault/skills/loop-hygiene/scripts/git_archive.py`
- Test: `shared-vault/skills/loop-hygiene/augur/tests/test_git_archive.py`

**Sweep apply routing:**
- Modify: `shared-vault/skills/loop-hygiene/scripts/hygiene_apply.py`
- Test: `shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_apply.py`

**Archive index and Browse cache:**
- Modify: `shared-vault/skills/loop-hygiene/scripts/archive_index.py`
- Modify: `src/mcp/augur_framework/tools/infrastructure/browse/index.py`
- Test: `shared-vault/skills/loop-hygiene/augur/tests/test_archive_index.py`

**Docs and metadata:**
- Modify: `shared-vault/skills/loop-hygiene/SKILL.md`
- Modify: `docs/adrs/ADR-749-brain-archive-git-history-purge.md` only if implementation status notes change during implementation.

---

## Phase 1 - Git-History Purge Lifecycle

### Task 1: Add the push-gated archive lifecycle API

**Files:**
- Modify: `shared-vault/skills/loop-hygiene/scripts/git_archive.py`
- Test: `shared-vault/skills/loop-hygiene/augur/tests/test_git_archive.py`

- [ ] **Step 1: Add failing tests for the successful two-commit flow**

Append focused tests near the existing `apply_git_archive` tests. Reuse the existing `_init_repo`, `_commit_file`, and `_git` helpers.

```python
def _init_bare_remote(tmp_path: Path) -> Path:
    remote = tmp_path / "remote.git"
    result = subprocess.run(
        ["git", "init", "--bare", str(remote)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return remote


def _configure_origin(repo: Path, remote: Path) -> None:
    assert _git(repo, "remote", "add", "origin", str(remote)).returncode == 0
    branch = _git(repo, "branch", "--show-current").stdout.strip()
    assert branch
    assert _git(repo, "push", "-u", "origin", branch).returncode == 0


def test_git_history_purge_commits_pushes_deletes_payload_and_preserves_ledger(tmp_path):
    repo = _init_repo(tmp_path)
    remote = _init_bare_remote(tmp_path)
    source = _commit_file(repo, "notes/topic/page.md", "# Old note\n")
    _configure_origin(repo, remote)

    result = mod.apply_git_history_purge_archive(
        repo_root=repo,
        source_path=source,
        source_tab="notes",
        source_kind="vault-notes",
        reason="superseded",
        artifact_group="uart-debug",
        apply_run_id="run-1",
        brain_id="private",
    )

    assert result["status"] == "succeeded"
    assert result["archive_mode"] == "git-history-purge"
    assert result["git_action"] == "mv+purge"
    assert result["archive_pushed"] is True
    assert result["purge_pushed"] is True
    assert result["archive_commit"]
    assert result["purge_commit"]
    assert result["archive_commit"] != result["purge_commit"]

    archived_rel = result["archived_path"]
    assert archived_rel.startswith("archive/sweep/notes/")
    assert not source.exists()
    assert not (repo / archived_rel).exists()
    assert (repo / "archive" / "_ledger" / "sweep.jsonl").is_file()

    events = [
        json.loads(line)
        for line in (repo / "archive" / "_ledger" / "sweep.jsonl").read_text().splitlines()
    ]
    assert [event["event"] for event in events] == ["archive_prepared", "purged"]
    assert events[0]["archive_record_id"] == events[1]["archive_record_id"]
    assert events[0]["original_path"] == "notes/topic/page.md"
    assert events[0]["archived_path"] == archived_rel
    assert events[1]["archive_commit"] == result["archive_commit"]
    assert "purge_commit" not in events[1]
    assert "git restore --source=" + result["archive_commit"] in events[1]["recovery_hint"]

    remote_log = subprocess.run(
        ["git", "--git-dir", str(remote), "log", "--oneline", "--all"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert remote_log.returncode == 0
    assert "archive sweep payload" in remote_log.stdout
    assert "purge swept archive payload" in remote_log.stdout
```

- [ ] **Step 2: Run the new test and confirm it fails**

Run:

```bash
.venv/bin/python -m pytest shared-vault/skills/loop-hygiene/augur/tests/test_git_archive.py::test_git_history_purge_commits_pushes_deletes_payload_and_preserves_ledger -v
```

Expected: fails because `apply_git_history_purge_archive` does not exist.

- [ ] **Step 3: Implement the lifecycle in `git_archive.py`**

Keep `apply_git_archive()` and `preview_git_archive()` unchanged for compatibility. Add a new public function:

```python
LEDGER_REL_PATH = Path("archive") / "_ledger" / "sweep.jsonl"
ARCHIVE_SWEEP_ROOT = Path("archive") / "sweep"
GIT_HISTORY_PURGE_MODE = "git-history-purge"


def apply_git_history_purge_archive(
    *,
    repo_root: Path,
    source_path: Path,
    source_tab: str,
    source_kind: str,
    reason: str,
    artifact_group: str | None,
    apply_run_id: str,
    brain_id: str = "default",
    remote: str = "origin",
    branch: str | None = None,
) -> dict[str, Any]:
    """Move, commit, push, purge, commit, and push a brain archive payload."""
```

Implementation requirements:

- Call `_prepare_git_archive(...)` with `refusal_status="refused"` and reuse its safety checks.
- Compute a stable `archive_record_id` before writing ledger events. Use only deterministic values available before the commits:

  ```python
  archive_record_id = _archive_record_id(
      apply_run_id=apply_run_id,
      original_rel=original_rel,
      archived_rel=archived_rel,
  )
  ```

- Run `git mv -- <original_rel> <archived_rel>`.
- Append one JSON object to `archive/_ledger/sweep.jsonl` with `event: "archive_prepared"` and all fields required by the spec.
- Stage only the moved payload and the ledger:

  ```python
  git add -- archive/_ledger/sweep.jsonl <archived_rel>
  ```

- Commit with message:

  ```text
  archive sweep payload: <basename>
  ```

- Read the archive commit SHA with `git rev-parse HEAD`.
- Push the selected branch to the selected remote. If `branch is None`, derive it from `git branch --show-current`.
- Only after the archive push succeeds, delete the archived payload path.
- Append a `purged` event containing the pushed `archive_commit`, `archive_pushed: true`, and a recovery hint.
- Stage the deleted payload and the ledger, commit with:

  ```text
  purge swept archive payload: <basename>
  ```

- Push the purge commit.
- Return a result containing:

  ```python
  {
      "status": "succeeded",
      "archive_mode": "git-history-purge",
      "git_action": "mv+purge",
      "from": original_rel,
      "to": archived_rel,
      "original_path": str(resolved_source_path),
      "archived_path": archived_rel,
      "repo_root": str(resolved_repo_root),
      "ledger_path": "archive/_ledger/sweep.jsonl",
      "archive_record_id": archive_record_id,
      "archive_commit": archive_commit,
      "archive_pushed": True,
      "purge_commit": purge_commit,
      "purge_pushed": True,
      "purged": True,
      "reason": reason,
      "artifact_group": artifact_group,
      "apply_run_id": apply_run_id,
      "brain_id": brain_id,
      "source_kind": source_kind,
      "recovery_hint": recovery_hint,
  }
  ```

Add private helpers for small operations instead of inlining shell handling:

- `_append_ledger_event(repo_root: Path, event: dict[str, Any]) -> None`: create `archive/_ledger/` when needed and append compact JSON plus a trailing newline.
- `_commit_staged(repo_root: Path, message: str) -> tuple[bool, str, str]`: run `git commit -m <message>`, then `git rev-parse HEAD`; return `(True, sha, "")` on success and `(False, "", error)` on failure.
- `_current_branch(repo_root: Path) -> tuple[bool, str, str]`: run `git branch --show-current`; return an error when detached or empty.
- `_push_branch(repo_root: Path, remote: str, branch: str) -> tuple[bool, str]`: run `git push <remote> <branch>` and return the git error text on failure.
- `_delete_archived_payload(repo_root: Path, archived_rel: str) -> tuple[bool, str | None]`: delete only a file or empty directory below `archive/sweep/`; return an error for any path outside that root.
- `_archive_record_id(apply_run_id: str, original_rel: str, archived_rel: str) -> str`: return a stable `sha256:`-prefixed id over those three values.
- `_recovery_hint_for_commit(archive_commit: str, archived_rel: str, original_rel: str) -> str`: return both archive-path and original-path recovery commands in one concise sentence.

`_delete_archived_payload` must refuse any path that is not below `archive/sweep/`. It must never delete `archive/_ledger/`.

- [ ] **Step 4: Run the focused success test**

Run:

```bash
.venv/bin/python -m pytest shared-vault/skills/loop-hygiene/augur/tests/test_git_archive.py::test_git_history_purge_commits_pushes_deletes_payload_and_preserves_ledger -v
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/loop-hygiene/scripts/git_archive.py shared-vault/skills/loop-hygiene/augur/tests/test_git_archive.py
git commit -m "feat(loop-hygiene): add git-history purge archive lifecycle"
```

### Task 2: Make failures stop before destructive purge

**Files:**
- Modify: `shared-vault/skills/loop-hygiene/scripts/git_archive.py`
- Test: `shared-vault/skills/loop-hygiene/augur/tests/test_git_archive.py`

- [ ] **Step 1: Add failing tests for archive-push and purge-push failures**

Add tests that monkeypatch `_push_branch` to fail at specific phases.

```python
def test_git_history_purge_keeps_payload_when_archive_push_fails(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path)
    source = _commit_file(repo, "notes/topic/page.md", "# Old note\n")
    push_calls = []

    def fail_archive_push(repo_root: Path, remote: str, branch: str):
        push_calls.append((remote, branch))
        return False, "network down"

    monkeypatch.setattr(mod, "_push_branch", fail_archive_push)

    result = mod.apply_git_history_purge_archive(
        repo_root=repo,
        source_path=source,
        source_tab="notes",
        source_kind="vault-notes",
        reason="superseded",
        artifact_group=None,
        apply_run_id="run-archive-push-fail",
        brain_id="private",
    )

    assert result["status"] == "partial"
    assert result["failure_phase"] == "archive_push"
    assert result["archive_pushed"] is False
    assert result["purged"] is False
    assert push_calls
    assert not source.exists()
    assert (repo / result["archived_path"]).exists()

    events = [
        json.loads(line)
        for line in (repo / "archive" / "_ledger" / "sweep.jsonl").read_text().splitlines()
    ]
    assert [event["event"] for event in events] == ["archive_prepared"]
```

```python
def test_git_history_purge_reports_local_purge_when_purge_push_fails(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path)
    source = _commit_file(repo, "notes/topic/page.md", "# Old note\n")
    call_count = {"push": 0}

    def fail_second_push(repo_root: Path, remote: str, branch: str):
        call_count["push"] += 1
        if call_count["push"] == 1:
            return True, ""
        return False, "remote rejected"

    monkeypatch.setattr(mod, "_push_branch", fail_second_push)

    result = mod.apply_git_history_purge_archive(
        repo_root=repo,
        source_path=source,
        source_tab="notes",
        source_kind="vault-notes",
        reason="superseded",
        artifact_group=None,
        apply_run_id="run-purge-push-fail",
        brain_id="private",
    )

    assert result["status"] == "partial"
    assert result["failure_phase"] == "purge_push"
    assert result["archive_pushed"] is True
    assert result["purged"] is True
    assert result["purge_pushed"] is False
    assert not (repo / result["archived_path"]).exists()
    assert (repo / "archive" / "_ledger" / "sweep.jsonl").is_file()
```

- [ ] **Step 2: Run the failure tests and confirm they fail**

Run:

```bash
.venv/bin/python -m pytest \
  shared-vault/skills/loop-hygiene/augur/tests/test_git_archive.py::test_git_history_purge_keeps_payload_when_archive_push_fails \
  shared-vault/skills/loop-hygiene/augur/tests/test_git_archive.py::test_git_history_purge_reports_local_purge_when_purge_push_fails \
  -v
```

Expected: fail until partial-state handling is implemented.

- [ ] **Step 3: Implement explicit partial-state results**

Archive push failure result must include:

```python
{
    "status": "partial",
    "failure_phase": "archive_push",
    "archive_commit": archive_commit,
    "archive_pushed": False,
    "purged": False,
    "purge_commit": None,
    "purge_pushed": False,
    "recovery_hint": (
        f"Archive commit {archive_commit} is local only. Resolve push failure, "
        f"then run git -C {resolved_repo_root} push {remote} {branch}. "
        f"Do not delete {archived_rel} until that push succeeds."
    ),
}
```

Purge push failure result must include:

```python
{
    "status": "partial",
    "failure_phase": "purge_push",
    "archive_pushed": True,
    "purged": True,
    "purge_commit": purge_commit,
    "purge_pushed": False,
    "recovery_hint": (
        f"Purge commit {purge_commit} is local only. Push it with "
        f"git -C {resolved_repo_root} push {remote} {branch}. "
        f"Recovery payload is preserved in archive commit {archive_commit}."
    ),
}
```

- [ ] **Step 4: Run the focused git archive suite**

Run:

```bash
.venv/bin/python -m pytest shared-vault/skills/loop-hygiene/augur/tests/test_git_archive.py -v
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/loop-hygiene/scripts/git_archive.py shared-vault/skills/loop-hygiene/augur/tests/test_git_archive.py
git commit -m "test(loop-hygiene): cover push-gated archive purge failures"
```

### Task 3: Add preview, skills tab, and product-skill refusal

**Files:**
- Modify: `shared-vault/skills/loop-hygiene/scripts/git_archive.py`
- Test: `shared-vault/skills/loop-hygiene/augur/tests/test_git_archive.py`

- [ ] **Step 1: Add failing tests**

```python
def test_preview_git_history_purge_archive_has_no_side_effects(tmp_path):
    repo = _init_repo(tmp_path)
    source = _commit_file(repo, "skills/team-skill/SKILL.md", "# Skill\n")
    before = _git(repo, "status", "--porcelain").stdout

    result = mod.preview_git_history_purge_archive(
        repo_root=repo,
        source_path=source,
        source_tab="skills",
        source_kind="brain-skill",
        reason="superseded",
        artifact_group="team-skill",
        apply_run_id="run-preview",
        brain_id="firmware-team",
    )

    assert result["status"] == "would_succeed"
    assert result["archive_mode"] == "git-history-purge"
    assert result["git_action"] == "mv+purge"
    assert result["archived_path"].startswith("archive/sweep/skills/")
    assert not (repo / "archive").exists()
    assert _git(repo, "status", "--porcelain").stdout == before
```

```python
def test_git_history_purge_refuses_core_augur_product_skill(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "pyproject.toml").write_text("[project]\nname = \"augur\"\n")
    _git(repo, "add", "pyproject.toml")
    _git(repo, "commit", "-m", "add project marker")
    source = _commit_file(repo, "shared-vault/skills/core-skill/SKILL.md", "# Core\n")

    result = mod.apply_git_history_purge_archive(
        repo_root=repo,
        source_path=source,
        source_tab="skills",
        source_kind="brain-skill",
        reason="superseded",
        artifact_group="core-skill",
        apply_run_id="run-core-refusal",
        brain_id="project",
    )

    assert result["status"] == "refused"
    assert result["refusal_category"] == "core_product_skill"
    assert source.exists()
```

- [ ] **Step 2: Run tests and confirm they fail**

Run:

```bash
.venv/bin/python -m pytest \
  shared-vault/skills/loop-hygiene/augur/tests/test_git_archive.py::test_preview_git_history_purge_archive_has_no_side_effects \
  shared-vault/skills/loop-hygiene/augur/tests/test_git_archive.py::test_git_history_purge_refuses_core_augur_product_skill \
  -v
```

Expected: fail until preview and skills-tab handling exist.

- [ ] **Step 3: Implement preview and refusal**

Change:

```python
ALLOWED_SOURCE_TABS = {"sources", "notes", "pages", "skills"}
```

Add:

```python
def preview_git_history_purge_archive(
    *,
    repo_root: Path,
    source_path: Path,
    source_tab: str,
    source_kind: str,
    reason: str,
    artifact_group: str | None,
    apply_run_id: str,
    brain_id: str = "default",
    remote: str = "origin",
    branch: str | None = None,
) -> dict[str, Any]:
    """Side-effect-free preview of the git-history purge archive decision."""
```

Preview returns `would_succeed` with no filesystem, git index, commit, or ledger changes.

Add a guard after `_prepare_git_archive` returns its plan:

```python
if _is_core_product_skill_target(plan["repo_root"], plan["original_rel"]):
    return _refused(
        "core_product_skill",
        repo_root=plan["repo_root"],
        source_path=plan["source_path"],
        reason=reason,
        artifact_group=artifact_group,
        apply_run_id=apply_run_id,
        original_rel=plan["original_rel"],
        archived_rel=plan["archived_rel"],
        archived_path=plan["archived_path"],
        status=refusal_status,
    )
```

Use this helper:

```python
def _is_core_product_skill_target(repo_root: Path, original_rel: str) -> bool:
    return (
        original_rel.startswith("shared-vault/skills/")
        and (repo_root / "pyproject.toml").is_file()
        and (repo_root / "docs" / "adrs").is_dir()
    )
```

Update `_recovery_hint()` for `invalid_source_tab` and `core_product_skill`.

- [ ] **Step 4: Run the focused git archive suite**

Run:

```bash
.venv/bin/python -m pytest shared-vault/skills/loop-hygiene/augur/tests/test_git_archive.py -v
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/loop-hygiene/scripts/git_archive.py shared-vault/skills/loop-hygiene/augur/tests/test_git_archive.py
git commit -m "feat(loop-hygiene): preview and guard brain archive purge targets"
```

---

## Phase 2 - Route Sweep Apply Through Git-History Purge

### Task 4: Replace git-aware apply routing with the new lifecycle

**Files:**
- Modify: `shared-vault/skills/loop-hygiene/scripts/hygiene_apply.py`
- Test: `shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_apply.py`

- [ ] **Step 1: Update or add failing routing tests**

Add a test next to `test_hygiene_apply_selection_git_aware_calls_git_archive`. The test should use a bare remote and assert that the target is no longer left staged under `archive/sweep`.

```python
def test_hygiene_apply_selection_git_aware_uses_git_history_purge(tmp_path):
    repo = _init_repo(tmp_path)
    remote = _init_bare_remote(tmp_path)
    source = _commit_file(repo, "notes/page.md", "# stale\n")
    _configure_origin(repo, remote)

    selection = _write_selection(
        tmp_path,
        [
            {
                "id": "note-1",
                "path": str(source),
                "target_repository_root": str(repo),
                "source_tab": "notes",
                "kind": "vault-notes",
                "archive_mode": "git-aware",
                "reason": "superseded",
                "artifact_group": "firmware",
            }
        ],
    )

    result = mod.hygiene_apply_selection(selection)

    item = result["items"][0]
    assert item["status"] == "archived"
    assert item["archive_mode"] == "git-history-purge"
    assert item["archive_commit"]
    assert item["purge_commit"]
    assert not source.exists()
    assert not (repo / item["archived_path"]).exists()
    assert (repo / "archive" / "_ledger" / "sweep.jsonl").is_file()
    assert _git(repo, "status", "--porcelain").stdout == ""
```

- [ ] **Step 2: Run the routing test and confirm it fails**

Run:

```bash
.venv/bin/python -m pytest shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_apply.py::test_hygiene_apply_selection_git_aware_uses_git_history_purge -v
```

Expected: fail because `hygiene_apply_selection` still calls `apply_git_archive()`.

- [ ] **Step 3: Modify `hygiene_apply.py`**

Replace loader functions:

```python
def _load_apply_git_history_purge_archive():
    return _load_git_archive_module().apply_git_history_purge_archive


def _load_preview_git_history_purge_archive():
    return _load_git_archive_module().preview_git_history_purge_archive
```

In the real apply path for `archive_mode == "git-aware"`, call:

```python
result = apply_git_history_purge_archive(
    repo_root=Path(target["target_repository_root"]),
    source_path=Path(target["path"]),
    source_tab=str(target["source_tab"]),
    source_kind=str(target.get("kind") or target.get("source_kind") or target["source_tab"]),
    reason=str(target.get("reason") or "Archived by Sweep"),
    artifact_group=target.get("artifact_group"),
    apply_run_id=apply_run_id,
    brain_id=str(target.get("brain_id") or target.get("target_repository_id") or "default"),
)
```

Keep dry-run side-effect-free by calling `preview_git_history_purge_archive(...)`.

Update `_git_archive_record()` so records include the lifecycle result fields:

```python
"archive_mode": result.get("archive_mode") or "git-history-purge",
"ledger_path": result.get("ledger_path"),
"archive_record_id": result.get("archive_record_id"),
"archive_commit": result.get("archive_commit"),
"archive_pushed": result.get("archive_pushed"),
"purge_commit": result.get("purge_commit"),
"purge_pushed": result.get("purge_pushed"),
"purged": result.get("purged"),
"brain_id": result.get("brain_id"),
"source_kind": result.get("source_kind") or target.get("kind"),
```

Partial results should become item status `needs_attention`, not `archived`, because the operator must resolve push state:

```python
if result.get("status") == "partial":
    item["status"] = "needs_attention"
    item["failure_phase"] = result.get("failure_phase")
```

- [ ] **Step 4: Run focused apply tests**

Run:

```bash
.venv/bin/python -m pytest shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_apply.py -v
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/loop-hygiene/scripts/hygiene_apply.py shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_apply.py
git commit -m "feat(loop-hygiene): route git-aware sweep to history purge"
```

---

## Phase 3 - Archive Index Reads the Append-Only Ledger

### Task 5: Fold `archive/_ledger/sweep.jsonl` events into Browse records

**Files:**
- Modify: `shared-vault/skills/loop-hygiene/scripts/archive_index.py`
- Test: `shared-vault/skills/loop-hygiene/augur/tests/test_archive_index.py`

- [ ] **Step 1: Add failing ledger-folding tests**

```python
def test_reads_git_history_purge_ledger_events(tmp_path):
    repo = tmp_path / "brain"
    repo.mkdir()
    ledger = repo / "archive" / "_ledger" / "sweep.jsonl"
    ledger.parent.mkdir(parents=True)
    archived_rel = "archive/sweep/notes/2026-05-14/notes/page.md"
    ledger.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "event": "archive_prepared",
                        "archive_record_id": "run-1-notes-page",
                        "brain_id": "private",
                        "source_kind": "vault-notes",
                        "source_tab": "notes",
                        "original_path": "notes/page.md",
                        "archived_path": archived_rel,
                        "reason": "superseded",
                        "artifact_group": "firmware",
                        "apply_run_id": "run-1",
                        "archived_at": "2026-05-14T10:00:00Z",
                    }
                ),
                json.dumps(
                    {
                        "event": "purged",
                        "archive_record_id": "run-1-notes-page",
                        "brain_id": "private",
                        "archived_path": archived_rel,
                        "archive_commit": "abc123",
                        "archive_pushed": True,
                        "purged_at": "2026-05-14T10:02:00Z",
                        "recovery_hint": "git restore --source=abc123 -- " + archived_rel,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = mod.collect_sweep_archive_entries(documents_dir=tmp_path / "docs", ledger_roots=[repo / "archive"])

    assert result["warnings"] == []
    entries = result["entries"]
    assert len(entries) == 1
    entry = entries[0]
    assert entry["archive_mode"] == "git-history-purge"
    assert entry["archive_record_id"] == "run-1-notes-page"
    assert entry["brain_id"] == "private"
    assert entry["original_path"] == str(repo / "notes/page.md")
    assert entry["archived_path"] == str(repo / archived_rel)
    assert entry["purged"] is True
    assert entry["archive_commit"] == "abc123"
    assert entry["recovery_hint"].startswith("git restore --source=abc123")
```

- [ ] **Step 2: Run the new test and confirm it fails**

Run:

```bash
.venv/bin/python -m pytest shared-vault/skills/loop-hygiene/augur/tests/test_archive_index.py::test_reads_git_history_purge_ledger_events -v
```

Expected: fails because `_ledger_paths()` only finds legacy `sweep-ledger.jsonl`.

- [ ] **Step 3: Implement ledger discovery and folding**

Update constants:

```python
VALID_SOURCE_TABS = {"sources", "notes", "pages", "skills"}
GIT_HISTORY_PURGE_RECOVERY_HINT = (
    "Use the recovery command from the sweep ledger to restore this payload from git history."
)
```

Update `_ledger_paths()` so each root can be any of:

- the exact file `archive/_ledger/sweep.jsonl`;
- an `archive/` directory containing `_ledger/sweep.jsonl`;
- a legacy directory containing `sweep-ledger.jsonl`.

Add event folding helpers:

- `_collect_git_history_purge_events(ledger_root: Path, ledger: Path, warnings: list[dict[str, Any]]) -> list[dict[str, Any]]`: read JSONL safely, skip blank lines, add `malformed_json` or `malformed_record` warnings with file and line number, and return only events whose `event` field is `archive_prepared` or `purged`.
- `_fold_git_history_purge_records(repo_root: Path, ledger: Path, events: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> list[dict[str, Any]]`: group by `archive_record_id`, validate safe relative `original_path` and `archived_path`, select the first valid `archive_prepared` plus the newest matching `purged`, and emit Browse-shaped archive entries.

Fold by `archive_record_id`. A record is visible when it has a valid `archive_prepared` event. If a matching `purged` event exists, set:

```python
"purged": True,
"archive_commit": purged.get("archive_commit"),
"archive_pushed": bool(purged.get("archive_pushed")),
"purged_at": str(purged.get("purged_at") or ""),
"recovery_hint": str(purged.get("recovery_hint") or GIT_HISTORY_PURGE_RECOVERY_HINT),
```

If there is no `purged` event, set `purged: False` and keep the existing archived path recovery behavior.

Keep all existing legacy `sweep-ledger.jsonl` behavior passing.

- [ ] **Step 4: Run archive index tests**

Run:

```bash
.venv/bin/python -m pytest shared-vault/skills/loop-hygiene/augur/tests/test_archive_index.py -v
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/loop-hygiene/scripts/archive_index.py shared-vault/skills/loop-hygiene/augur/tests/test_archive_index.py
git commit -m "feat(loop-hygiene): index git-history purge archive ledger"
```

### Task 6: Point Browse cache signatures at new brain archive roots

**Files:**
- Modify: `src/mcp/augur_framework/tools/infrastructure/browse/index.py`
- Test: `shared-vault/skills/loop-hygiene/augur/tests/test_archive_index.py`

- [ ] **Step 1: Add failing Browse signature tests**

Extend the existing Browse index tests around `_sweep_ledger_file_signature`.

```python
def test_browse_sweep_ledger_signature_includes_new_archive_ledger(tmp_path):
    archive_root = tmp_path / "archive"
    ledger = archive_root / "_ledger" / "sweep.jsonl"
    ledger.parent.mkdir(parents=True)
    ledger.write_text("{}\n", encoding="utf-8")

    signature = browse_index._sweep_ledger_file_signature(archive_root)

    assert len(signature) == 1
    assert signature[0][0].endswith("archive/_ledger/sweep.jsonl")
```

Update or add a test for `sweep_archive_entries()` so `ledger_roots` passed to the archive module include:

```python
project_root / "archive"
get_vault_dir() / "archive"
```

and not only:

```python
project_root / "archive" / "sweep"
get_vault_dir() / "archive" / "sweep"
```

- [ ] **Step 2: Run the focused Browse index tests and confirm they fail**

Run:

```bash
.venv/bin/python -m pytest \
  shared-vault/skills/loop-hygiene/augur/tests/test_archive_index.py::test_browse_sweep_ledger_signature_includes_new_archive_ledger \
  -v
```

Expected: fails until Browse signature discovery sees `archive/_ledger/sweep.jsonl`.

- [ ] **Step 3: Update Browse ledger-root logic**

In `_sweep_ledger_file_signature(root)`, detect both filenames:

```python
if ledger_root.is_file():
    return [(str(ledger_root), ledger_root.stat().st_mtime_ns)] if ledger_root.name in {"sweep-ledger.jsonl", "sweep.jsonl"} else []
```

When scanning a directory, collect both:

```python
candidates = list(ledger_root.rglob("sweep-ledger.jsonl"))
new_ledger = ledger_root / "_ledger" / "sweep.jsonl"
if new_ledger.is_file():
    candidates.append(new_ledger)
```

In `sweep_archive_entries()`, pass archive roots:

```python
ledger_roots = [
    project_root / "archive",
    get_vault_dir() / "archive",
]
```

Keep the archive index backward-compatible so legacy `archive/sweep/sweep-ledger.jsonl` is still found under those roots.

- [ ] **Step 4: Run focused archive and Browse index tests**

Run:

```bash
.venv/bin/python -m pytest shared-vault/skills/loop-hygiene/augur/tests/test_archive_index.py -v
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/augur_framework/tools/infrastructure/browse/index.py shared-vault/skills/loop-hygiene/augur/tests/test_archive_index.py
git commit -m "feat(browse): include brain archive ledger roots"
```

---

## Phase 4 - Documentation and Verification

### Task 7: Update loop-hygiene skill docs

**Files:**
- Modify: `shared-vault/skills/loop-hygiene/SKILL.md`

- [ ] **Step 1: Document the new archive invariant**

Add a concise section near the Sweep archive behavior:

```markdown
### Git-History Purge Archive

For git-managed brain targets, Sweep uses `git-history-purge`:

1. move the payload under `archive/sweep/...`;
2. append `archive_prepared` to `archive/_ledger/sweep.jsonl`;
3. commit and push the archive move;
4. delete only the archived payload under `archive/sweep/...`;
5. append `purged` with the pushed `archive_commit`;
6. commit and push the purge.

The ledger is never deleted by purge. If the archive move push fails, the payload
remains under `archive/sweep/...` and the run reports `needs_attention`.
```

- [ ] **Step 2: Commit**

```bash
git add shared-vault/skills/loop-hygiene/SKILL.md
git commit -m "docs(loop-hygiene): document git-history purge archive"
```

### Task 8: Run verification loops and prepare ADR completion notes

- [ ] **Step 1: Run focused regression tests**

Run:

```bash
.venv/bin/python -m pytest \
  shared-vault/skills/loop-hygiene/augur/tests/test_git_archive.py \
  shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_apply.py \
  shared-vault/skills/loop-hygiene/augur/tests/test_archive_index.py \
  -v
```

Expected: all pass.

- [ ] **Step 2: Run required auto-loop verification**

Run through the repo command surfaces, not raw whole-suite commands:

```bash
/auto-test-pytest
/auto-lint
```

If implementation changes Browse/dashboard generated data or config in a way that triggers dashboard rebuild, also run:

```bash
/auto-test-dashboard
```

Expected: all applicable loops pass or report honest, unrelated existing failures with evidence.

- [ ] **Step 3: Update ADR-749 only after implementation is actually complete**

When all implementation tasks and verification pass, update:

```yaml
status: Implemented
```

and add a short status note naming the key commits. Then run:

```bash
python .github/scripts/adr_upsert_live.py
python .github/scripts/generate_adr_index.py
python src/lib/index/unified_indexer.py --category adrs
PYTHONPATH="$PWD/shared-vault:$PWD:$PWD/src/mcp" python3 -m skills.ai.scripts.sync_agents sync agents all
```

Commit:

```bash
git add docs/adrs/ADR-749-brain-archive-git-history-purge.md docs/generated/adr-index.md src/lib/index/indexes/adrs-index.json
git commit -m "docs(adr): mark ADR-749 implemented"
```

Do not mark ADR-749 implemented while any push-gate, ledger-folding, or Browse indexing requirement remains incomplete.

---

## Recovery and Safety Checklist

- [ ] Archive purge never deletes `archive/_ledger/`.
- [ ] Purge never runs before the archive move commit has pushed successfully.
- [ ] `purged` ledger events store `archive_commit`, not a self-referential purge commit SHA.
- [ ] Archive push failure leaves payload present under `archive/sweep/...`.
- [ ] Purge push failure reports local-only purge commit and does not claim full success.
- [ ] Browse Archive shows purged records from `archive/_ledger/sweep.jsonl`.
- [ ] Legacy `archive/sweep/sweep-ledger.jsonl` entries remain readable.
- [ ] Core Augur product skills under `shared-vault/skills/` in the Augur product repo are refused by this flow.
- [ ] Focused tests and required auto-loops have been run before implementation closeout.
