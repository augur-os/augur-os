# Harness Layering — C2: CLI & MCP Tier-Scoping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax. **Prerequisite: C1 (ADR-782) landed** — this consumes the layered stack + `get_managed_skill_source_dirs` routing.

**Goal:** Make `aug` subcommand discovery and MCP/capability exposure tier-aware — Global / User / Project can each contribute `aug` subcommands (most-specific-wins) and scope MCP/exposure — with project-level `.mcp.json` generation.

**Architecture:** `src/cli_plugins.py:discover_subcommands` enumerates subcommands from `get_project_brain_skills_dir` (single, global) today. C2 routes it through the layered skill source dirs (C1's `get_managed_skill_source_dirs`, now tier-ordered) so personal/project brains contribute subcommands, with a name→most-specific-tier merge. `config/system/capability_exposure.yaml` and `mcp_servers.yaml` gain an optional `scope: global|user|project` (default `global`, back-compatible); the resolver filters by active tiers. Project-scoped MCP servers generate a repo `.mcp.json` merged under the global HOME MCP config (project wins on name collision).

**Tech Stack:** Python 3.11+, `src/cli_plugins.py`, `src/config/paths.py` (`get_managed_skill_source_dirs`), `config/system/capability_exposure.yaml`, `config/system/mcp_servers.yaml`, the MCP manifest loader (`src/cli_config/manifest.py`). Implements ADR-783 (C2). TDD inner loop `uv run pytest <nodeid>`.

---

## File Structure

| File | Responsibility | Change |
|------|----------------|--------|
| `src/cli_plugins.py` | `discover_subcommands` | Enumerate across the layered (tier-ordered) skill source dirs; most-specific name wins |
| `tests/unit/test_cli_plugins_tiered.py` | **NEW** | Create |
| `config/system/capability_exposure.yaml` | exposure config | Add optional `scope:` per capability (default `global`) |
| `src/lib/capabilities/exposure_policy.py` | exposure resolver | Honor `scope` against active tiers |
| `tests/unit/test_exposure_scope.py` | **NEW** | Create |
| `src/lib/mcp_project_config.py` | **NEW** — project `.mcp.json` generator | Create |
| `tests/unit/test_mcp_project_config.py` | **NEW** | Create |

---

## Task 1: Tier-aware `discover_subcommands`

**Files:** Modify `src/cli_plugins.py`. Test: `tests/unit/test_cli_plugins_tiered.py`.

- [ ] **Step 1: failing test** — create `tests/unit/test_cli_plugins_tiered.py`: build two skill source dirs (one "global" with subcommand `foo`, one "user" with subcommand `bar` and an overriding `foo`), patch `cli_plugins`'s source-dir resolver to return them general→specific, assert `discover_subcommands()` returns `{foo: <user>, bar: <user>}` (most-specific `foo` wins) — i.e. names from all tiers, override resolved to the most-specific dir.

```python
def test_discover_subcommands_merges_tiers_most_specific_wins(tmp_path, monkeypatch):
    from src import cli_plugins
    glob = tmp_path / "global" / "skills"; user = tmp_path / "user" / "skills"
    for base, names in ((glob, ["foo"]), (user, ["foo", "bar"])):
        for n in names:
            d = base / n / "commands"; d.mkdir(parents=True)
            (d / f"{n}.md").write_text(f"---\nx-augur-export-command: true\nname: {n}\n---\n# /{n}\n")
    monkeypatch.setattr(cli_plugins, "_subcommand_source_dirs", lambda: [glob, user])  # general -> specific
    cmds = cli_plugins.discover_subcommands()
    assert set(cmds) >= {"foo", "bar"}
    assert str(cmds["foo"]).startswith(str(user))  # user tier overrides global
```

- [ ] **Step 2: Run → FAIL** (`_subcommand_source_dirs` / tiered behavior missing).
- [ ] **Step 3: Implement** — add `_subcommand_source_dirs()` returning `get_managed_skill_source_dirs()` (tier-ordered, general→specific, from C1) plus any client-native command dirs; rewrite `discover_subcommands` to iterate those in order and let later (more-specific) dirs overwrite earlier name entries. Preserve existing single-dir behavior when only one dir resolves.
- [ ] **Step 4: Run → PASS** + `uv run pytest tests/unit -q` (no regression to existing CLI discovery tests).
- [ ] **Step 5: Commit** `feat(cli): tier-aware aug subcommand discovery, most-specific wins (ADR-783 C2)`

---

## Task 2: `scope` field on capability exposure

**Files:** Modify `src/lib/capabilities/exposure_policy.py`; `config/system/capability_exposure.yaml` (doc the field). Test: `tests/unit/test_exposure_scope.py`.

- [ ] **Step 1: failing test** — `tests/unit/test_exposure_scope.py`: a capability record with `scope: project` is included when a project tier is active and excluded when only global/user are active; a record with no `scope` defaults to `global` (always included). Patch the active stack tiers.
- [ ] **Step 2: Run → FAIL**.
- [ ] **Step 3: Implement** — extend the exposure record model with `scope: str = "global"`; in `resolve_capability_records`, filter out `scope` values whose tier is not in the active stack (`{t.value for t in stack.ordered()}`). Default `global` always passes.
- [ ] **Step 4: Run → PASS** + regression.
- [ ] **Step 5: Commit** `feat(exposure): tier scope on capability_exposure (ADR-783 C2)`

---

## Task 3: Project-level `.mcp.json` generation

**Files:** Create `src/lib/mcp_project_config.py`. Test: `tests/unit/test_mcp_project_config.py`.

- [ ] **Step 1: failing test** — `tests/unit/test_mcp_project_config.py`: given a manifest with two servers, one `scope: project` and one `scope: global`, `generate_project_mcp_json(servers, dest)` writes a `.mcp.json` containing only the project-scoped server; collision with a global server name → project entry wins (documented). Assert JSON shape + that non-project entries are excluded.
- [ ] **Step 2: Run → FAIL**.
- [ ] **Step 3: Implement** — `generate_project_mcp_json(servers, dest)` filters `scope == "project"`, serializes the standard `.mcp.json` `{ "mcpServers": {...} }` shape (reuse the existing claude `.mcp.json` template/format), writes with the AUTO-GENERATED header marker (sync-safety).
- [ ] **Step 4: Run → PASS**.
- [ ] **Step 5: Commit** `feat(mcp): project-scoped .mcp.json generation (ADR-783 C2)`

---

## Completion Gate (C2)
- [ ] `uv run pytest tests/unit -q` green.
- [ ] **Real-data (rule 34):** from the live repo, `aug` (or `python -m src.cli --help`) lists subcommands sourced from all active tiers; add a temp project-tier subcommand and confirm it appears, a temp user-tier one and confirm it appears, with an override resolving to the most-specific. Generate the project `.mcp.json` and confirm a real client loads it (verify-harness/MCP check). Report the exact subcommands + their source tiers.

## Self-Review
**Spec coverage (ADR-783):** tier-aware subcommands (T1), tier-scoped exposure (T2), project `.mcp.json` (T3). ✔ **Placeholder scan:** none. **Type consistency:** `_subcommand_source_dirs()->list[Path]`; `discover_subcommands()->dict[str,Path]`; exposure record `scope:str="global"`; `generate_project_mcp_json(servers,dest)->Path`.

## Follow-on
C4 (manager UI) surfaces the tier of each subcommand/MCP entry; C5 verifies tier-scoping cross-client.
