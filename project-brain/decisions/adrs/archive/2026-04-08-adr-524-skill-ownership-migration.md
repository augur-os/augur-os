# ADR-524 Skill Ownership Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate Augur from location-based skill provenance to the `augur | external | adopted` ownership model, with enabled-client-only repo-scoped exports and mandatory cleanup.

**Architecture:** Discovery becomes ownership-first: anything in `skills/` is managed, anything outside it is external inventory unless explicitly adopted. Sync becomes a pure export-and-cleanup layer driven by enabled client adapters, while Codex prompt mirrors and native skill exports remain separate explicit targets. Lifecycle commands and dashboard labels stop modeling `local/global` as state and instead expose ownership and upstream-aware adopted flows.

**Tech Stack:** Python 3.11, YAML frontmatter, MCP server tools, Next.js dashboard, Jest, pytest, `sync_agents`

---

### Task 1: Replace Source Semantics With Ownership In Discovery And MCP Models

**Files:**
- Modify: `src/plugins/skill_discovery.py`
- Modify: `src/mcp/augur_mcp/core/models.py`
- Modify: `src/mcp/augur_mcp/core/skills.py`
- Modify: `src/mcp/augur_mcp/core/__init__.py`
- Test: `skills/import/augur/tests/` or `src`-adjacent discovery tests already covering source/origin filters

- [ ] **Step 1: Write the failing discovery/model tests**

```python
def test_skill_record_uses_ownership_for_skills_dir(tmp_path: Path):
    skill_dir = tmp_path / "skills" / "seo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: seo\ndescription: SEO skill\nownership: adopted\nupstream:\n  repo: owner/seo\n---\n# SEO\n",
        encoding="utf-8",
    )

    records = _discover_all_skills_impl(tiers=(0,))
    record = next(r for r in records if r.name == "seo")

    assert record.ownership == "adopted"
    assert record.upstream == {"repo": "owner/seo"}
```

```python
def test_list_skills_filters_by_ownership_not_source():
    params = ListSkillsInput(ownership="external")
    payload = json.loads(list_skills_impl(params))
    assert payload["success"] is True
```

- [ ] **Step 2: Run the targeted tests to verify they fail on missing ownership support**

Run: `pytest skills/import/augur/tests -k "ownership or source" -v`

Expected: failures referencing missing `ownership` fields or still filtering by `source`

- [ ] **Step 3: Implement the minimal model changes**

```python
@dataclass(frozen=True)
class SkillRecord:
    name: str
    description: str
    path: Path
    ownership: str = "augur"
    upstream: dict = field(default_factory=dict)
    origin: str = ""
    scope: str | None = None
```

```python
def _infer_ownership(skill_path: Path, frontmatter: dict, *, origin: str) -> tuple[str, dict]:
    if skill_path.is_relative_to(get_skills_dir()):
        ownership = str(frontmatter.get("ownership") or "augur")
        upstream = frontmatter.get("upstream")
        return ownership, upstream if isinstance(upstream, dict) else {}
    return "external", {}
```

```python
class ListSkillsInput(BaseModel):
    ownership: str | None = None
```

- [ ] **Step 4: Update MCP payload shaping to emit ownership**

```python
items.append(
    {
        "name": skill.name,
        "description": skill.description,
        "ownership": getattr(skill, "ownership", "augur"),
        "upstream": getattr(skill, "upstream", {}) or {},
        "origin": getattr(skill, "origin", "") or "",
    }
)
```

- [ ] **Step 5: Run the targeted tests again**

Run: `pytest skills/import/augur/tests -k "ownership or source" -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/plugins/skill_discovery.py src/mcp/augur_mcp/core/models.py src/mcp/augur_mcp/core/skills.py src/mcp/augur_mcp/core/__init__.py skills/import/augur/tests
git commit -m "refactor(skills): model discovery around ownership"
```

### Task 2: Restrict Export To Enabled Clients And Make Cleanup Deterministic

**Files:**
- Modify: `skills/ai/scripts/sync_agents/skill_sync.py`
- Modify: `src/config/paths.py`
- Modify: `config/agents/ide_integrations.yaml`
- Test: `skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py`

- [ ] **Step 1: Write the failing export/cleanup tests**

```python
def test_sync_skips_disabled_clients_and_removes_managed_outputs(tmp_path):
    enabled = {"codex"}
    managed_copilot = tmp_path / ".github" / "copilot" / "seo.md"
    managed_copilot.parent.mkdir(parents=True)
    managed_copilot.write_text("<!-- AUGUR-GENERATED -->\n", encoding="utf-8")

    removed = cleanup_disabled_client_outputs(
        enabled_client_ids=enabled,
        managed_targets={"copilot": [managed_copilot]},
    )

    assert removed == 1
    assert not managed_copilot.exists()
```

```python
def test_codex_prompt_and_native_exports_are_separate_targets(tmp_path):
    assert get_codex_prompt_dir("project") == tmp_path / ".codex" / "prompts"
    assert get_codex_native_skills_dir("project") == tmp_path / ".codex" / "skills"
```

- [ ] **Step 2: Run the targeted tests to verify the cleanup gap**

Run: `pytest skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py -k "disabled or codex" -v`

Expected: FAIL with missing cleanup helper or incorrect target behavior

- [ ] **Step 3: Implement enabled-client-only export and cleanup**

```python
def _cleanup_disabled_targets(all_client_dirs, enabled_ids: set[str]) -> int:
    removed = 0
    for adapter_name, target_path, _has_subdirs in all_client_dirs:
        if adapter_name not in enabled_ids:
            removed += _remove_managed_outputs(target_path)
    return removed
```

```python
enabled_ids = {a.adapter_name for a in adapters}
cleanup_count = _cleanup_disabled_targets(client_dirs, enabled_ids)
logger.info("Cleaned %s managed outputs for disabled adapters", cleanup_count)
```

```python
def get_client_skill_dirs() -> dict[str, Path]:
    return {
        "claude-local": project_root / ".claude" / "skills",
        "gemini-local": project_root / ".gemini" / "skills",
        "opencode-local": project_root / ".opencode" / "skills",
    }
```

- [ ] **Step 4: Keep Codex explicit and repo-scoped**

```python
if "codex" in enabled_ids:
    prompt_dir = get_codex_prompt_dir("project")
    _sync_codex_prompt_dir(prompt_dir, sources)
    _sync_codex_native_skills(sources, scope="project")
```

- [ ] **Step 5: Run tests and a dry sync**

Run: `pytest skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py -k "disabled or codex" -v`

Expected: PASS

Run: `python3 -m skills.ai.scripts.sync_agents sync agents all`

Expected: disabled adapters skipped, managed stale outputs cleaned, enabled targets synced

- [ ] **Step 6: Commit**

```bash
git add skills/ai/scripts/sync_agents/skill_sync.py src/config/paths.py config/agents/ide_integrations.yaml skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py
git commit -m "fix(sync): export only to enabled repo-scoped clients"
```

### Task 3: Replace Eject/Reset With Adopted-Skill Lifecycle Primitives

**Files:**
- Modify: `src/mcp/augur_mcp/core/skill_lifecycle.py`
- Modify: `src/mcp/augur_mcp/core/__init__.py`
- Modify: `skills/import/SKILL.md`
- Modify: `skills/import/commands/skill-eject.md`
- Modify: `skills/import/commands/skill-reset.md`
- Modify: `skills/import/commands/skill-status.md`
- Test: `skills/import/augur/tests/` covering lifecycle operations

- [ ] **Step 1: Write the failing lifecycle tests**

```python
def test_adopt_skill_copies_external_skill_into_skills_with_ownership_and_upstream(tmp_path):
    result = adopt_skill("seo", source="codex-local", project_root=tmp_path)
    assert result["success"] is True
    meta, _ = parse_frontmatter(tmp_path / "skills" / "seo" / "SKILL.md")
    assert meta["ownership"] == "adopted"
    assert meta["upstream"]["source"] == "codex-local"
```

```python
def test_skill_status_reports_ownership_and_upstream(tmp_path):
    status = skill_status("seo", project_root=tmp_path)
    assert status["ownership"] in {"augur", "external", "adopted"}
```

- [ ] **Step 2: Run the lifecycle tests to confirm old command assumptions fail**

Run: `pytest skills/import/augur/tests -k "adopt or lifecycle or status" -v`

Expected: FAIL because only `eject/reset` semantics exist

- [ ] **Step 3: Implement adopted lifecycle helpers**

```python
def adopt_skill(name: str, source: str, project_root: Path) -> dict:
    target_dir = project_root / "skills" / name
    meta, body = parse_frontmatter(source_skill_md)
    meta["ownership"] = "adopted"
    meta["upstream"] = {"source": source, "version": str(meta.get("version", ""))}
    write_frontmatter(target_dir / "SKILL.md", meta, body)
    invalidate_discovery_cache()
    return {"success": True, "message": f"Skill '{name}' adopted into skills/{name}/"}
```

```python
def skill_status(name: str, project_root: Path) -> dict:
    return {
        "name": name,
        "ownership": ownership,
        "upstream": upstream,
        "location": str(path),
    }
```

- [ ] **Step 4: Rewire MCP registration and docs away from eject/reset**

```python
@mcp.tool(name="skill-adopt")
async def skill_adopt(name: str, source: str) -> str:
    return json.dumps(adopt_skill(name, source, get_project_root()))
```

```md
- `skill-adopt` — bring an external skill into `skills/` as `adopted`
- `skill-status` — show ownership, location, and upstream metadata
```

- [ ] **Step 5: Run lifecycle tests**

Run: `pytest skills/import/augur/tests -k "adopt or lifecycle or status" -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/mcp/augur_mcp/core/skill_lifecycle.py src/mcp/augur_mcp/core/__init__.py skills/import/SKILL.md skills/import/commands/skill-eject.md skills/import/commands/skill-reset.md skills/import/commands/skill-status.md skills/import/augur/tests
git commit -m "refactor(import): add adopted skill lifecycle"
```

### Task 4: Update Browse And Skill Detail UI To Use Ownership

**Files:**
- Modify: `apps/dashboard/app/(views)/browse/BrowseToolbar.tsx`
- Modify: `apps/dashboard/components/shared/BrowseDetailPanel.tsx`
- Modify: `apps/dashboard/lib/browse/types.ts`
- Modify: `apps/dashboard/lib/browse/useSkillDetail.ts`
- Modify: `apps/dashboard/app/api/skill-meta/[skillId]/route.ts`
- Test: `apps/dashboard` browse/detail tests near these modules

- [ ] **Step 1: Write the failing UI tests**

```tsx
it("shows ownership filters instead of local/global filters", () => {
  render(<BrowseToolbar state={stateWithSkills} />);
  expect(screen.getByText("Augur")).toBeInTheDocument();
  expect(screen.getByText("External")).toBeInTheDocument();
  expect(screen.getByText("Adopted")).toBeInTheDocument();
  expect(screen.queryByText("Local")).not.toBeInTheDocument();
});
```

```tsx
it("renders adopted ownership badge and upstream summary", async () => {
  expect(await screen.findByText("Adopted")).toBeInTheDocument();
  expect(screen.getByText(/owner\/seo/)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run the targeted UI tests**

Run: `pnpm --filter dashboard test -- --runInBand BrowseToolbar BrowseDetailPanel`

Expected: FAIL because the UI still exposes Local/Global and source-based detail labels

- [ ] **Step 3: Implement ownership-facing UI and API fields**

```ts
export type SkillOwnership = "augur" | "external" | "adopted";
```

```tsx
const sourceFilters = [
  { id: "augur", label: "Augur" },
  { id: "external", label: "External" },
  { id: "adopted", label: "Adopted" },
];
```

```ts
return NextResponse.json({
  ...payload,
  ownership,
  upstream,
});
```

- [ ] **Step 4: Remove `skill-eject` CTA wiring and replace it with adopted-aware detail rendering**

```tsx
const showAdoptAction = detail.ownership === "external";
const showUpstream = detail.ownership === "adopted" && detail.upstream;
```

- [ ] **Step 5: Run dashboard tests**

Run: `pnpm --filter dashboard test -- --runInBand BrowseToolbar BrowseDetailPanel`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add apps/dashboard/app/(views)/browse/BrowseToolbar.tsx apps/dashboard/components/shared/BrowseDetailPanel.tsx apps/dashboard/lib/browse/types.ts apps/dashboard/lib/browse/useSkillDetail.ts apps/dashboard/app/api/skill-meta/[skillId]/route.ts apps/dashboard
git commit -m "feat(browse): show skill ownership in dashboard"
```

### Task 5: Align Documentation, Generated Outputs, And Regression Checks

**Files:**
- Modify: `docs/creating-skills.md`
- Modify: `docs/agent-topics/SKILLS.md`
- Modify: `docs/generated/adr-index.md`
- Modify: `skills/import/SKILL.md`
- Modify: any updated generated client exports produced by `sync_agents`

- [ ] **Step 1: Write one failing doc-facing regression test or grep assertion**

```bash
rg -n "Platform Local|Platform Global|source: augur|x-augur-upstream" docs skills apps/dashboard src
```

Expected before fix: matches still exist in user-facing docs and commands that describe the old lifecycle

- [ ] **Step 2: Update docs to the ownership model**

```md
## Ownership

- `augur` — fully managed in `skills/`
- `external` — discovered outside `skills/`, shown for awareness only
- `adopted` — managed in `skills/` with upstream metadata
```

- [ ] **Step 3: Regenerate derived artifacts**

Run: `python .github/scripts/generate_adr_index.py`

Expected: `docs/generated/adr-index.md` refreshed

Run: `python3 -m skills.ai.scripts.sync_agents sync agents all`

Expected: enabled client exports refreshed and disabled managed leftovers removed

- [ ] **Step 4: Run final focused verification**

Run: `pytest skills/import/augur/tests skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py -v`

Expected: PASS

Run: `pnpm --filter dashboard test -- --runInBand BrowseToolbar BrowseDetailPanel`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add docs/creating-skills.md docs/agent-topics/SKILLS.md docs/generated/adr-index.md skills/import/SKILL.md .codex/prompts .codex/skills .gemini/skills .opencode/skills .github/copilot
git commit -m "docs: align skill docs with ownership model"
```

## Self-Review

- Spec coverage: discovery, export, cleanup, Codex split, ownership metadata, command migration, and UI language are each mapped to a task.
- Placeholder scan: no `TBD`, `TODO`, or “implement later” placeholders remain in the task steps.
- Type consistency: later tasks use `ownership` and `upstream` consistently and do not reintroduce `source` or local/global lifecycle terms as primary fields.
