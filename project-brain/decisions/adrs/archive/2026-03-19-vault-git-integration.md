# Vault Git Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automate vault git commits, pushes, health checks, binary eviction, and recovery so the vault is always backed up and clean.

**Architecture:** Enhance 4 existing skills (auto-vault-hygiene, auto-repo-sync, onboard, dev-merge) + add 1 MCP tool (vault-status) + add 1 Claude Code hook (Stop). No new skills created. Vault config stored in `config/system/vault.yaml`.

**Tech Stack:** Python (ops_protocol pattern), shell (git commands), YAML config, TypeScript (MCP tool registration)

**Spec:** `docs/superpowers/specs/2026-03-19-vault-git-integration-design.md`

---

### Task 1: Vault .gitignore and config/system/vault.yaml

**Files:**
- Create: `get_vault_dir()/.gitignore`
- Create: `config/system/vault.yaml`

- [ ] **Step 1: Create vault .gitignore**

```
.DS_Store
__pycache__/
*.pyc
._*
_cache/
_config/
```

Write this to `get_vault_dir()/.gitignore`.

- [ ] **Step 2: Create vault.yaml config**

```yaml
vault:
  remote: https://github.com/gsannikov/augur-vault.git
  path: get_vault_dir()
```

Write this to `config/system/vault.yaml`.

- [ ] **Step 3: Commit .gitignore in vault repo**

```bash
cd get_vault_dir() && git add .gitignore && git commit -m "chore: add .gitignore for text-only vault policy"
```

- [ ] **Step 4: Remove newly-ignored files from vault tracking**

```bash
cd get_vault_dir() && git rm -r --cached --ignore-unmatch '*.pyc' '__pycache__' '.DS_Store' '._*' '_cache' '_config' 2>/dev/null; git diff --cached --quiet || git commit -m "chore: remove ignored files from tracking"
```

- [ ] **Step 5: Commit vault.yaml in Augur repo**

```bash
git add config/system/vault.yaml && git commit -m "feat: add vault.yaml config for vault git integration"
```

---

### Task 2: Post-Session Local Commit Hook

**Files:**
- Modify: `.claude/settings.json` (add Stop hook)

- [ ] **Step 1: Read current .claude/settings.json**

Check existing hooks structure. The file has hooks for PreCompact, SubagentStop, SessionStart, WorktreeCreate, PostToolUse, WorktreeRemove, SessionEnd.

- [ ] **Step 2: Add Stop hook for vault auto-commit**

Add to the `hooks` object in `.claude/settings.json`:

```json
"Stop": [{
  "command": "bash -c 'cd get_vault_dir() && git add -u && git diff --cached --quiet || git commit -m \"vault: auto-commit $(date +%Y-%m-%d-%H%M)\"'",
  "timeout": 10000
}]
```

- [ ] **Step 3: Verify hook fires**

Run a test: modify a tracked file in the vault, then verify the hook would work:

```bash
cd get_vault_dir() && echo "# test" >> memory/MEMORY.md && git add -u && git diff --cached --quiet || echo "WOULD_COMMIT"
```

Then revert the test change:
```bash
cd get_vault_dir() && git checkout -- memory/MEMORY.md
```

- [ ] **Step 4: Commit**

```bash
git add .claude/settings.json && git commit -m "feat: add Stop hook for vault auto-commit"
```

---

### Task 3: Extend auto-repo-sync for Vault Repo

**Files:**
- Modify: `.claude/skills/daemon/scripts/ops/repo_sync.py`
- Modify: `.claude/skills/auto-repo-sync/SKILL.md` (update difficulty spec)

- [ ] **Step 1: Read config/system/vault.yaml in repo_sync.py**

Add a helper to load vault config and return the vault path:

```python
def _get_vault_path() -> Path | None:
    """Read vault path from config/system/vault.yaml."""
    try:
        import yaml
        config_path = Path(__file__).resolve()
        # Walk up to project root
        project_root = config_path
        while project_root.name != "Augur" and project_root != project_root.parent:
            project_root = project_root.parent
        vault_yaml = project_root / "config" / "system" / "vault.yaml"
        if not vault_yaml.exists():
            return None
        data = yaml.safe_load(vault_yaml.read_text())
        raw_path = data.get("vault", {}).get("path", "")
        if not raw_path:
            return None
        return Path(raw_path).expanduser()
    except Exception:
        return None
```

- [ ] **Step 2: Modify scan() to check both repos**

After the existing project root scan, add vault scanning:

```python
# Scan vault repo if configured
vault_path = _get_vault_path()
if vault_path and vault_path.exists() and (vault_path / ".git").exists():
    vault_status = _git_status(vault_path)
    if vault_status:
        lines = vault_status.splitlines()
        summary_parts.append(f"vault dirty ({len(lines)} paths)")
        if ctx.difficulty >= 1:
            issues.append({
                "type": "vault_uncommitted",
                "count": len(lines),
                "detail": vault_status,
                "repo": "vault",
            })

    vault_unpushed = _git_unpushed(vault_path)
    if vault_unpushed:
        commits = vault_unpushed.splitlines()
        issues.append({
            "type": "vault_unpushed",
            "count": len(commits),
            "detail": vault_unpushed,
            "repo": "vault",
        })
        summary_parts.append(f"vault: {len(commits)} unpushed commit(s)")
```

- [ ] **Step 3: Modify fix() to handle vault issues**

After the existing project fix logic, add vault fix logic:

```python
# Fix vault issues
vault_path = _get_vault_path()
if vault_path and vault_path.exists():
    vault_uncommitted = [i for i in issues if i.get("repo") == "vault" and i["type"] == "vault_uncommitted"]
    if vault_uncommitted:
        commit_status = _git_commit(vault_path, "chore(auto): vault-sync auto-commit")
        if commit_status == "committed":
            actions.append({"action": "vault_commit", "success": True})
            changes.append("Committed vault changes")

    if ctx.difficulty >= 3:
        vault_unpushed = [i for i in issues if i.get("repo") == "vault" and i["type"] == "vault_unpushed"]
        if vault_unpushed or vault_uncommitted:
            pushed = _git_push(vault_path)
            if pushed:
                actions.append({"action": "vault_push", "success": True})
                changes.append("Pushed vault to remote")
            else:
                actions.append({"action": "vault_push", "success": False})
                errors.append("vault git push failed")
```

- [ ] **Step 4: Update auto-repo-sync SKILL.md difficulty spec**

Add d3 description to the SKILL.md frontmatter or description section.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/daemon/scripts/ops/repo_sync.py .claude/skills/auto-repo-sync/SKILL.md
git commit -m "feat: extend auto-repo-sync to track vault repo with d3 push"
```

---

### Task 4: Expand auto-vault-hygiene Health Checks

**Files:**
- Modify: `.claude/skills/auto-vault-hygiene/scripts/vault_hygiene_ops.py`
- Modify: `.claude/skills/auto-vault-hygiene/SKILL.md`

This is the largest task. The existing script has 4 difficulty tiers (d0-d4). We expand to 7 checks across the same tiers.

- [ ] **Step 1: Add binary extension list and helper**

At the top of `vault_hygiene_ops.py`, after imports:

```python
import shutil
import subprocess

BINARY_EXTENSIONS = {
    ".m4a", ".xlsx", ".docx", ".png", ".svg", ".jpg", ".jpeg",
    ".pdf", ".zip", ".tar", ".gz", ".mp3", ".mp4", ".wav",
}

def _is_binary(path: Path) -> bool:
    return path.suffix.lower() in BINARY_EXTENSIONS

def _get_registered_plugins() -> set[str]:
    """Get all x-augur-plugin values from .claude/skills/*/SKILL.md."""
    from src.config.paths import get_project_root
    import yaml as _yaml
    plugins = set()
    skills_dir = get_project_root() / ".claude" / "skills"
    if not skills_dir.exists():
        return plugins
    for skill_dir in skills_dir.iterdir():
        if not skill_dir.is_dir() or skill_dir.name.startswith("."):
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            continue
        try:
            content = skill_md.read_text()
            if not content.startswith("---"):
                continue
            end = content.index("---", 3)
            fm = _yaml.safe_load(content[3:end])
            if isinstance(fm, dict) and fm.get("x-augur-plugin"):
                plugins.add(fm["x-augur-plugin"])
        except Exception:
            continue
    return plugins

ALLOWED_TOP_DIRS = {"config", "memory"}
```

- [ ] **Step 2: Add binary eviction scan and fix at d0/d2**

In `scan()`, add after the existing d0 check:

```python
# d0: binary files in vault (text-only policy)
for f in vault.rglob("*"):
    if f.is_file() and _is_binary(f):
        issues.append({
            "file": str(f.relative_to(vault)),
            "message": f"binary file in vault: {f.name} — will be evicted to Documents",
            "severity": "warning",
            "kind": "binary_eviction",
        })
```

In `fix()`, add binary eviction handler:

```python
# Binary eviction (d2+)
binary_issues = [i for i in issues if i.get("kind") == "binary_eviction"]
if binary_issues and ctx.difficulty >= 2:
    from src.config.paths import get_skill_documents_dir
    for issue in binary_issues:
        src_path = vault / issue["file"]
        if not src_path.exists():
            continue
        # Determine skill from path: {plugin}/{skill}/...
        parts = Path(issue["file"]).parts
        if len(parts) >= 2:
            skill_name = parts[1]
            try:
                dest_dir = get_skill_documents_dir(skill_name)
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest = dest_dir / src_path.name
                shutil.move(str(src_path), str(dest))
                # Commit the removal immediately
                subprocess.run(
                    ["git", "add", "-u"],
                    cwd=str(vault), capture_output=True,
                )
                subprocess.run(
                    ["git", "commit", "-m", f"vault: evict binary {src_path.name} to Documents"],
                    cwd=str(vault), capture_output=True,
                )
                actions.append({"action": "evict_binary", "file": issue["file"], "dest": str(dest)})
                changes.append(f"Evicted {src_path.name} to Documents")
            except Exception as e:
                logger.warning(f"Failed to evict {src_path.name}: {e}")
```

- [ ] **Step 3: Add orphan dirs check at d0**

```python
# d0: orphan vault dirs (no matching skill in .claude/skills/)
registered_plugins = _get_registered_plugins()
for d in vault.iterdir():
    if not d.is_dir() or d.name.startswith("."):
        continue
    if d.name in ALLOWED_TOP_DIRS:
        continue
    for skill_dir in d.iterdir():
        if not skill_dir.is_dir():
            continue
        # Check if this skill exists in .claude/skills/
        from src.config.paths import get_project_root
        if not (get_project_root() / ".claude" / "skills" / skill_dir.name).exists():
            issues.append({
                "file": str(skill_dir.relative_to(vault)),
                "message": f"orphan vault dir: no matching skill in .claude/skills/{skill_dir.name}",
                "severity": "info",
                "kind": "maintenance",
            })
```

- [ ] **Step 4: Add stale files check at d0**

```python
# d0: stale files (not modified in 90+ days) and empty dirs
import time
ninety_days_ago = time.time() - (90 * 86400)
stale_count = 0
for f in vault.rglob("*"):
    if f.is_file() and not f.name.startswith(".") and f.stat().st_mtime < ninety_days_ago:
        stale_count += 1
if stale_count > 0:
    issues.append({
        "file": "vault-wide",
        "message": f"{stale_count} files not modified in 90+ days",
        "severity": "info",
        "kind": "maintenance",
    })

# Empty dirs
for d in vault.rglob("*"):
    if d.is_dir() and not any(d.iterdir()) and d.name not in SKIP_DIRS:
        issues.append({
            "file": str(d.relative_to(vault)),
            "message": "empty directory",
            "severity": "info",
            "kind": "maintenance",
        })
```

- [ ] **Step 5: Add large file guard at d1**

```python
if ctx.difficulty >= 1:
    # Large file guard (>1MB)
    for f in vault.rglob("*"):
        if f.is_file() and f.stat().st_size > 1_000_000:
            issues.append({
                "file": str(f.relative_to(vault)),
                "message": f"large file: {f.stat().st_size / 1_000_000:.1f}MB — review if this belongs in vault",
                "severity": "warning",
                "kind": "maintenance",
            })
```

- [ ] **Step 6: Add cross-reference and plugin alignment checks at d1**

```python
if ctx.difficulty >= 1:
    # Cross-reference: skills with x-augur-plugin but missing vault dir
    from src.config.paths import get_project_root
    skills_dir = get_project_root() / ".claude" / "skills"
    for skill_dir in skills_dir.iterdir():
        if not skill_dir.is_dir() or skill_dir.name.startswith("."):
            continue
        # Check if skill has vault data referenced in git history
        skill_vault = None
        try:
            from src.config.paths import get_skill_vault_dir
            skill_vault = get_skill_vault_dir(skill_dir.name)
        except ValueError:
            continue
        # Only flag if dir previously existed (check git log)
        if skill_vault and not skill_vault.exists():
            result = subprocess.run(
                ["git", "log", "--oneline", "-1", "--", str(skill_vault.relative_to(vault))],
                cwd=str(vault), capture_output=True, text=True,
            )
            if result.stdout.strip():
                issues.append({
                    "file": str(skill_vault.relative_to(vault)),
                    "message": f"vault dir was deleted but skill {skill_dir.name} still references it",
                    "severity": "warning",
                    "kind": "maintenance",
                })

    # Plugin alignment: unknown top-level dirs
    for d in vault.iterdir():
        if not d.is_dir() or d.name.startswith("."):
            continue
        if d.name not in registered_plugins and d.name not in ALLOWED_TOP_DIRS:
            issues.append({
                "file": d.name,
                "message": f"unknown top-level dir '{d.name}' — not a registered x-augur-plugin value",
                "severity": "info",
                "kind": "maintenance",
            })
```

- [ ] **Step 7: Add repo size check at d1**

```python
if ctx.difficulty >= 1:
    # Repo size monitoring
    git_dir = vault / ".git"
    if git_dir.exists():
        git_size = sum(f.stat().st_size for f in git_dir.rglob("*") if f.is_file())
        if git_size > 100_000_000:  # 100MB
            issues.append({
                "file": ".git",
                "message": f".git dir is {git_size / 1_000_000:.0f}MB — running git gc recommended",
                "severity": "warning",
                "kind": "actionable",
            })
```

Add git gc to fix():

```python
# Repo size fix (d1+)
git_size_issues = [i for i in issues if ".git dir is" in i.get("message", "")]
if git_size_issues and ctx.difficulty >= 1:
    subprocess.run(
        ["git", "gc", "--aggressive"],
        cwd=str(vault), capture_output=True, timeout=120,
    )
    actions.append({"action": "git_gc", "success": True})
    changes.append("Ran git gc --aggressive on vault")
```

- [ ] **Step 8: Update DIFFICULTY_SPEC and evolution gap**

Update the `DIFFICULTY_SPEC` dict at the top:

```python
DIFFICULTY_SPEC = {
    0: "Surface — binary detection, orphan dirs, stale files",
    1: "Content — large file guard, cross-refs, plugin alignment, repo size, config.yaml check",
    2: "Deep — binary eviction to Documents, duplicate folders",
    3: "Exhaustive — full structure audit, nested self-duplicates",
    4: "Expert — evolution gaps for untested areas",
}
```

Update the evolution gap message at d4 to reflect the new checks.

- [ ] **Step 9: Update SKILL.md with new check descriptions**

- [ ] **Step 10: Commit**

```bash
git add .claude/skills/auto-vault-hygiene/
git commit -m "feat: expand auto-vault-hygiene with 7 health checks and binary eviction"
```

---

### Task 5: Add vault-status MCP Tool

**Files:**
- Create: `src/mcp/augur_mcp/tools/internal/vault_status.py`
- Modify: MCP tool registration entry point (wherever tools are collected)

- [ ] **Step 1: Find the MCP tool registration entry point**

Check where `register_context_tools` is called and how to add a new tool module.

- [ ] **Step 2: Create vault_status.py**

```python
"""vault-status MCP tool — returns vault git state for dashboard."""
from __future__ import annotations

import subprocess
from pathlib import Path

from augur_mcp.logging import get_entity_logger

logger = get_entity_logger("mcp")


def _get_vault_path() -> Path | None:
    """Read vault path from config/system/vault.yaml."""
    try:
        import yaml
        from augur_mcp.compat import get_project_root
        vault_yaml = Path(get_project_root()) / "config" / "system" / "vault.yaml"
        if not vault_yaml.exists():
            return None
        data = yaml.safe_load(vault_yaml.read_text())
        raw_path = data.get("vault", {}).get("path", "")
        return Path(raw_path).expanduser() if raw_path else None
    except Exception:
        return None


def _run_git(vault: Path, *args: str) -> str:
    """Run a git command in the vault, return stdout or empty string on error."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(vault), capture_output=True, text=True, timeout=10,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""


def register_vault_tools(mcp, config: dict):
    """Register vault status tool."""

    @mcp.tool(name="vault-status", description="Get vault git status, sync state, and health summary")
    def vault_status() -> dict:
        vault = _get_vault_path()

        if not vault or not vault.exists():
            return {"state": "missing", "message": "Vault directory not found. Run onboard --full to create."}

        if not (vault / ".git").exists():
            return {"state": "no_git", "message": "Vault exists but is not a git repo. Run git init."}

        # Git status
        status_output = _run_git(vault, "status", "--porcelain")
        uncommitted = len(status_output.splitlines()) if status_output else 0

        # Last commit
        last_commit = _run_git(vault, "log", "-1", "--format=%ci")

        # Push status
        unpushed = _run_git(vault, "log", "--oneline", "@{u}..HEAD")
        unpushed_count = len(unpushed.splitlines()) if unpushed else 0
        has_remote = bool(_run_git(vault, "remote", "get-url", "origin"))

        # Repo size
        import os
        git_dir = vault / ".git"
        git_size = sum(
            f.stat().st_size for f in git_dir.rglob("*") if f.is_file()
        ) if git_dir.exists() else 0

        # Recent commits
        recent = _run_git(vault, "log", "--oneline", "-5")

        return {
            "state": "ok",
            "uncommitted": uncommitted,
            "status": "clean" if uncommitted == 0 else f"{uncommitted} uncommitted changes",
            "last_commit": last_commit or "no commits",
            "push_status": "up to date" if unpushed_count == 0 and has_remote else f"{unpushed_count} commits ahead",
            "has_remote": has_remote,
            "repo_size_mb": round(git_size / 1_000_000, 1),
            "recent_commits": recent.splitlines() if recent else [],
        }
```

- [ ] **Step 3: Register in MCP tool collection**

Find the entry point that calls `register_*_tools()` and add:

```python
from augur_mcp.tools.internal.vault_status import register_vault_tools
register_vault_tools(mcp, config)
```

- [ ] **Step 4: Test the tool**

```bash
cd ~/Projects/Augur && python3 -c "
from src.mcp.augur_mcp.tools.internal.vault_status import _get_vault_path, _run_git
vault = _get_vault_path()
print('vault:', vault)
print('exists:', vault.exists() if vault else False)
"
```

- [ ] **Step 5: Commit**

```bash
git add src/mcp/augur_mcp/tools/internal/vault_status.py
git commit -m "feat: add vault-status MCP tool for dashboard observability"
```

---

### Task 6: Include Vault in dev-merge --push

**Files:**
- Modify: `.claude/skills/dev-merge/multi-repo.md`
- Modify: `.claude/skills/devops/scripts/sync_repos.py` (if it exists and handles multi-repo)

- [ ] **Step 1: Update multi-repo.md to include vault**

Add vault to the multi-repo push documentation:

```markdown
## Repositories

1. **Augur** (main project): `~/Projects/Augur`
2. **Vault** (personal data): `get_vault_dir()` — auto-detected from `config/system/vault.yaml`
```

- [ ] **Step 2: Check sync_repos.py for repo list and add vault**

Read `.claude/skills/devops/scripts/sync_repos.py` and add vault to its repo detection.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/dev-merge/multi-repo.md .claude/skills/devops/scripts/sync_repos.py
git commit -m "feat: include vault repo in dev-merge --push multi-repo cycle"
```

---

### Task 7: Onboard Vault Recovery

**Files:**
- Modify: `.claude/skills/onboard/SKILL.md`

- [ ] **Step 1: Add vault recovery section to onboard SKILL.md**

In the migration mode section, add:

```markdown
## Vault Recovery

During `--migrate` or `--full`:
1. Check if `get_vault_dir()/` exists
2. If missing, verify GitHub auth: `gh auth status`
3. Read remote from `config/system/vault.yaml`
4. Clone: `git clone <remote> get_vault_dir()`
5. Validate: top-level dirs match registered `x-augur-plugin` values
```

- [ ] **Step 2: Add --connect vault mode**

```markdown
## Connect Vault

`onboard --connect vault <repo-url>`:
1. Set remote in `config/system/vault.yaml`
2. If `get_vault_dir()/` is not a git repo, run `git init && git remote add origin <url>`
3. If already a repo, update remote: `git remote set-url origin <url>`
```

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/onboard/SKILL.md
git commit -m "feat: add vault recovery and --connect vault to onboard"
```

---

### Task 8: Evict Existing Binaries from Vault

**Files:**
- No code changes — operational task using the new auto-vault-hygiene

- [ ] **Step 1: Run binary scan on current vault**

```bash
cd get_vault_dir() && find . -type f \( -name "*.m4a" -o -name "*.xlsx" -o -name "*.docx" -o -name "*.png" -o -name "*.svg" -o -name "*.jpg" -o -name "*.pdf" \) | head -20
```

- [ ] **Step 2: Manually evict binaries to Documents**

For each binary found, move it:
```bash
# Example for a file at augur-knowledge/ai_bridge/demo/recording.m4a
mkdir -p ~/Documents/Augur/augur-knowledge/ai_bridge/
mv get_vault_dir()/augur-knowledge/ai_bridge/demo/recording.m4a ~/Documents/Augur/augur-knowledge/ai_bridge/
```

- [ ] **Step 3: Commit the removals in vault**

```bash
cd get_vault_dir() && git add -u && git commit -m "vault: evict binary files to ~/Documents/Augur/"
```

- [ ] **Step 4: Push vault**

```bash
cd get_vault_dir() && git push
```

---

### Task 9: Integration Test

- [ ] **Step 1: Verify auto-vault-hygiene scan runs clean**

```bash
cd ~/Projects/Augur && python3 -c "
from src.lib.ops_protocol import OpsContext
from pathlib import Path
import importlib.util
spec = importlib.util.spec_from_file_location('vault_hygiene', '.claude/skills/auto-vault-hygiene/scripts/vault_hygiene_ops.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
ctx = OpsContext(project_root=Path('.').resolve(), difficulty=2, dry_run=False)
result = mod.scan(ctx)
print(result.summary)
for i in result.issues[:5]:
    print(f'  {i[\"severity\"]}: {i[\"message\"]}')
"
```

- [ ] **Step 2: Verify auto-repo-sync detects vault state**

```bash
cd ~/Projects/Augur && python3 -c "
from src.lib.ops_protocol import OpsContext
from pathlib import Path
import importlib.util
spec = importlib.util.spec_from_file_location('repo_sync', '.claude/skills/daemon/scripts/ops/repo_sync.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
ctx = OpsContext(project_root=Path('.').resolve(), difficulty=0, dry_run=False)
result = mod.scan(ctx)
print(result.summary)
"
```

- [ ] **Step 3: Verify vault-status MCP tool returns valid data**

Test via direct Python import or MCP call.

- [ ] **Step 4: Verify `python -m skills.ai.scripts.sync_agents check` still passes**

```bash
python3 .claude/skills/ai_bridge/scripts/sync_agents/__main__.py --check
```

- [ ] **Step 5: Final commit and push vault**

```bash
cd get_vault_dir() && git add -A && git diff --cached --quiet || git commit -m "vault: post-integration-test state"
cd get_vault_dir() && git push
```
