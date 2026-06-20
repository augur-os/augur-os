# Frontend Anti-Patterns

## Single-Skill Audit Discovery

**Issue**: Dashboard hardening audit only scanned the hub owner skill for actions, MCP modules, and data directories, missing all contributing skills in multi-skill bundles.
**Root Cause**: Generated registry stores `skillId: hub.owner` (single value). Audit read only that skill instead of iterating all skills in the bundle.
**Solution**: Use `discover_bundle_skills()` to list all skills, then `discover_action_yamls()` to scan `augur/data/actions/*.yaml` across all of them. Score functions must also iterate `allSkills` for MCP and data checks.

**Anti-Pattern**:
```python
skill_id = hub_entry.get("skillId", "")  # Only gets owner
data_dir = project_root / "plugins" / plugin_id / "skills" / skill_id / "data"
```

**Correct**:
```python
all_skills = discover_bundle_skills(project_root, plugin_id)
for sk in all_skills:
    data_dir = project_root / "plugins" / plugin_id / "skills" / sk / "augur" / "data"
```

## Action Wiring Scope Drift

**Issue**: Action wiring checks reported green while real broken actions still existed across skills.
**Root Cause**: Verifier scanned legacy `dashboard.yaml` actions instead of distributed `augur/data/actions/*.yaml`.
**Solution**: Discover and validate action YAMLs across all skills, then check dispatch/backend targets (`endpoint`, `mcp_tool`, `mcp_tools`, `script_path`, `href`).

**Anti-Pattern**:
```python
for dashboard_yaml in find_dashboard_yamls(root):
    actions = load(dashboard_yaml).get("actions", [])
```

**Correct**:
```python
for action_file in root.glob("plugins/*/skills/*/augur/data/actions/*.yaml"):
    actions = parse_actions(action_file)
    validate_dispatch_targets(actions)
```

## Mount Header Rigidity

**Issue**: Mount verification failed noisily even when mounts were valid.
**Root Cause**: Parser expected a single header format and treated metadata variance as hard errors.
**Solution**: Parse both `Source:` and `SOURCE file at:` mount headers; treat missing source metadata as warnings, not stale-mount failures.

**Anti-Pattern**:
```python
for line in content.splitlines()[:10]:
    if "Source:" in line:
        return line.split("Source:")[1].strip()
issues.append("No source path in header")
```

**Correct**:
```python
source_path = parse_source_header_variants(content)
if not source_path:
    warnings.append("No source path in header")
```
