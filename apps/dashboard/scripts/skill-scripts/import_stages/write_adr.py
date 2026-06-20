"""Stage 3: WriteADR -- generate an ADR document from the blueprint for user review."""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

from workflow_runner import RunState, Stage


def _slugify(text: str) -> str:
    """Convert text to kebab-case slug."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower())
    return slug.strip("-") or "data"


def _first_summary_paragraph(markdown: str, max_chars: int = 300) -> str:
    """Pull a one-paragraph summary out of generated ADR markdown."""
    in_section = False
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("## Context") or stripped.startswith("## Decision"):
            in_section = True
            continue
        if not in_section:
            continue
        if not stripped or stripped.startswith("|") or stripped.startswith("#"):
            if stripped.startswith("#"):
                in_section = False
            continue
        condensed = re.sub(r"\s+", " ", stripped)
        return condensed[:max_chars]
    return ""


def _strategy_to_connection_mode(mode: str) -> str:
    """Map a file strategy mode to a connections.yaml integration mode."""
    mapping = {
        "render-table": "page-candidate",
        "stat-card": "summary",
        "ai-analyze": "ai-analyze",
        "open-external": "open-external",
        "rendered-content": "page-candidate",
        "ignore": "ignore",
    }
    return mapping.get(mode, "open-external")


class WriteADRStage(Stage):
    """Generate an ADR document from the blueprint for user review."""

    @property
    def name(self) -> str:
        return "write_adr"

    @property
    def description(self) -> str:
        return "Generate ADR for user review before code generation"

    def plan(
        self,
        state: RunState,
        previous_output: dict[str, Any] | None = None,
        user_answers: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        blueprint = state.context.get("blueprint")
        if not blueprint:
            return {}
        return {"steps": ["find_next_adr_number", "generate_adr", "write_adr_file"]}

    def execute(
        self,
        state: RunState,
        plan: dict[str, Any],
    ) -> dict[str, Any]:
        blueprint = state.context.get("blueprint", {})
        flow = state.context.get("flow_analysis", {})
        folder = state.context.get("folder", "")
        hub_id = blueprint.get("hub", {}).get("id", "unknown")
        hub_title = blueprint.get("hub", {}).get("title", hub_id.title())

        # Find next ADR number from the central index (ADR-642).
        from src.config.paths import get_runtime_dir
        from src.lib.adr_utils import find_next_adr_number, get_adr_dir, upsert_adr_entry
        decisions_dir = get_adr_dir()
        decisions_dir.mkdir(parents=True, exist_ok=True)
        next_num = find_next_adr_number(decisions_dir)

        adr_slug = f"ADR-{next_num:03d}-import-{hub_id}"
        # Stage the ADR body under the runtime dir so the user can review the
        # full markdown before the import proceeds; the durable record lives
        # in adrs-index.json.
        runtime_dir = get_runtime_dir() / "adr-extracts" / f"ADR-{next_num:03d}"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        adr_path = runtime_dir / f"{adr_slug}.md"

        # Build ADR content
        adr_content = _build_import_adr(
            adr_num=next_num,
            hub_id=hub_id,
            hub_title=hub_title,
            folder=folder,
            flow=flow,
            blueprint=blueprint,
            adr_dir=decisions_dir,
        )

        adr_path.write_text(adr_content, encoding="utf-8")

        # Persist a stub entry in the central JSON index. The first paragraph
        # of the body is enough for browse/search; the full body lives in the
        # runtime extract until the user promotes it.
        decision_summary = _first_summary_paragraph(adr_content) or f"Import {hub_title} hub from {folder}"
        upsert_adr_entry(
            decisions_dir,
            {
                "adr_number": f"ADR-{next_num:03d}",
                "title": f"Import {hub_title} Hub from External Data",
                "state": "live",
                "status": "Proposed",
                "date": date.today().isoformat(),
                "deciders": ["User"],
                "related": ["ADR-086"],
                "hub": hub_id,
                "tags": ["import", "hub", hub_id],
                "decision_summary": decision_summary,
                "status_notes": "",
                "impact": {
                    "paths_renamed": [],
                    "apis_changed": [],
                    "patterns_deprecated": [],
                    "files_affected": [],
                },
                "spec_file": None,
                "plan_file": None,
                "superseded_by": None,
            },
        )

        # Store ADR path in context for later stages
        state.context["adr_path"] = str(adr_path)
        state.context["adr_number"] = next_num

        return {
            "adr_path": str(adr_path),
            "adr_number": next_num,
            "adr_slug": adr_slug,
        }

    def validate(
        self,
        state: RunState,
        artifacts: dict[str, Any],
    ) -> tuple[bool, str | None]:
        adr_path = artifacts.get("adr_path")
        if not adr_path or not Path(adr_path).exists():
            return False, f"ADR file not created: {adr_path}"
        return True, None

    def generate_questions(
        self,
        state: RunState,
        artifacts: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Prompt user to review the ADR before proceeding."""
        return [
            {
                "id": "adr_approved",
                "text": (
                    f"ADR written to {artifacts.get('adr_path', '?')}. "
                    "Review and edit the ADR, then approve to proceed with code generation."
                ),
                "type": "yes_no",
                "default": "yes",
                "required": True,
            },
        ]


def _build_import_adr(
    *,
    adr_num: int,
    hub_id: str,
    hub_title: str,
    folder: str,
    flow: dict[str, Any],
    blueprint: dict[str, Any],
    adr_dir: Path | None = None,
) -> str:
    """Build the ADR markdown content for an import."""
    if adr_dir is None:
        from src.lib.adr_utils import get_adr_dir
        adr_dir = get_adr_dir()
    today = date.today().isoformat()
    slug = f"import-{hub_id}"

    # --- Scan summary ---
    tabs = flow.get("suggested_tabs", [])
    stat_cards = flow.get("stat_cards", [])
    actions = flow.get("actions", [])
    file_strategies = flow.get("file_strategies", [])

    # Build directory summary table from file strategies
    dir_summary: dict[str, dict[str, Any]] = {}
    for fs in file_strategies:
        parts = Path(fs.get("path", "")).parts
        dir_name = parts[0] if parts else "(root)"
        if dir_name not in dir_summary:
            dir_summary[dir_name] = {
                "count": 0,
                "types": set(),
                "mode": fs.get("mode", ""),
            }
        dir_summary[dir_name]["count"] += 1
        ext = Path(fs.get("path", "")).suffix.lower()
        if ext:
            dir_summary[dir_name]["types"].add(ext)

    dir_rows = ""
    for d, info in sorted(dir_summary.items()):
        types_str = ", ".join(sorted(info["types"])) or "mixed"
        dir_rows += f"| {d} | {info['count']} | {types_str} |\n"

    # --- Tab table ---
    tab_rows = ""
    bp_tabs = blueprint.get("tabs", [])
    for t in bp_tabs:
        source = t.get("source_files", t.get("source_file", ""))
        if isinstance(source, list):
            source = ", ".join(source)
        tab_rows += f"| {t.get('id', '')} | {t.get('label', '')} | {t.get('type', '')} | {source} |\n"

    # --- Stat card table ---
    card_rows = ""
    for c in stat_cards:
        card_rows += (
            f"| {c.get('label', '')} | {c.get('source_file', '')} | "
            f"{c.get('cell', c.get('column', ''))} | {c.get('format', 'auto')} |\n"
        )

    # --- Action table ---
    action_rows = ""
    bp_actions = blueprint.get("actions", actions)
    for a in bp_actions:
        action_rows += (
            f"| {a.get('label', a.get('id', ''))} | "
            f"{a.get('dispatch', a.get('flow', a.get('mode', '')))} | "
            f"{a.get('file', a.get('target', ''))} |\n"
        )

    # --- Generated files table ---
    skill_dir = f"project-brain/capabilities/skills/{hub_id}"
    generated_files = [
        ("SKILL.md", "Skill manifest"),
        ("dashboard.yaml", "Hub configuration (tabs, actions, modals)"),
        ("dashboard/page.tsx", "Overview page with ExternalDataCards"),
        ("dashboard/layout.tsx", "Hub layout with tab navigation"),
        ("dashboard/loading.tsx", "Skeleton loading state"),
    ]
    for t in bp_tabs:
        if t.get("id") != "overview":
            generated_files.append((f"dashboard/{t['id']}/page.tsx", f"{t.get('label', '')} tab component"))
    generated_files.extend(
        [
            ("api/health/route.ts", "Health check endpoint"),
            ("api/data/route.ts", "Data fetching for rendered tabs"),
            ("data/connections.yaml", "External data source connection config"),
        ]
    )

    gen_rows = ""
    for fpath, purpose in generated_files:
        gen_rows += f"| `{skill_dir}/{fpath}` | {purpose} |\n"

    # --- Connection YAML preview ---
    conn_integrations = ""
    for fs in file_strategies:
        if fs.get("mode") != "ignore":
            conn_mode = _strategy_to_connection_mode(fs.get("mode", "open-external"))
            conn_integrations += (
                f"      - id: {_slugify(Path(fs['path']).stem)}\n"
                f"        file: {fs['path']}\n"
                f"        mode: {conn_mode}\n"
            )

    # --- Build the ADR ---
    return f"""# ADR-{adr_num:03d}: Import {hub_title} Hub from External Data

**Status**: Proposed
**Date**: {today}
**Deciders**: User
**Related**: ADR-086 (Hub Data Bridge)

## Context

Importing external data from `{folder}` into Augur as the **{hub_title}** dashboard hub.

The `/import` skill scanned the source folder and generated a hub blueprint. This ADR
documents the proposed hub structure for review before code generation proceeds.

### Scan Results

| Metric | Value |
|--------|-------|
| Source path | `{folder}` |
| Total files | {len(file_strategies)} |
| Suggested tabs | {len(tabs)} |
| Stat cards | {len(stat_cards)} |
| Actions | {len(actions)} |

### Directory Structure

| Directory | Files | Types |
|-----------|-------|-------|
{dir_rows}
## Decision

### Hub Configuration

| Field | Value |
|-------|-------|
| Hub ID | `{hub_id}` |
| Title | {hub_title} |
| Bundle | `{bundle}` |
| Icon | {blueprint.get("hub", {}).get("icon", "FolderOpen")} |

### Tabs

| ID | Label | Type | Source |
|----|-------|------|--------|
{tab_rows}
### Stat Cards

| Label | Source File | Cell/Column | Format |
|-------|------------|-------------|--------|
{card_rows if card_rows else "| *(none detected)* | | | |" + chr(10)}
### Actions

| Action | Flow | Target |
|--------|------|--------|
{action_rows if action_rows else "| *(none detected)* | | |" + chr(10)}
### External Data Connection

```yaml
version: 1
hub: {hub_id}
connections:
  - id: {hub_id}-folder
    source_type: folder
    source_path: {folder}
    integrations:
{conn_integrations if conn_integrations else "      # (no integrations)"}
```

### Generated Files

| File | Purpose |
|------|---------|
{gen_rows}
## Consequences

### Positive

- External data from `{folder}` immediately accessible in dashboard
- ExternalDataCards and FileActions provide consistent UX
- Connection config enables live data refresh

### Negative

- {len(generated_files)} new files added to the codebase
- External folder path is hardcoded in connections.yaml (not portable)

### Neutral

- Existing hub pages (if any) are not modified
- Plugin follows standard skill structure

## Alternatives Considered

### Alternative 1: Manual Hub Creation

Create all files by hand without `/import`. Rejected because it duplicates the
mechanical work that the import pipeline automates.

### Alternative 2: Symlink-Based Integration

Symlink external files into the plugin data directory. Rejected because it breaks
the data separation principle and complicates backups.

## References

- ADR-086: Hub Data Bridge
- `/import` skill: `project-brain/capabilities/skills/ai/augur/skills/import/SKILL.md`
- ExternalDataCards: `apps/dashboard/components/bridge/ExternalDataCards.tsx`
- FileActions: `apps/dashboard/components/bridge/FileActions.tsx`

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.
> Auto-generated by `/import`. Edit if needed before running.

You are implementing **ADR-{adr_num:03d}: Import {hub_title} Hub**.

Read the full ADR: `{adr_dir}/ADR-{adr_num:03d}-{slug}.md`

### Phase 1: Code Generation
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | Generate plugin files from import blueprint | `{skill_dir}/` |
| 1.2 | developer | low | Write connections.yaml with external data mappings | `{skill_dir}/data/connections.yaml` |

### Phase 2: Dashboard Integration
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | frontend | medium | Create tab components from blueprint | `{skill_dir}/dashboard/` |
| 2.2 | frontend | low | Add ExternalDataCards to overview page | `{skill_dir}/dashboard/page.tsx` |
| 2.3 | developer | low | Create API routes for data fetching | `{skill_dir}/api/` |

### Phase 3: Auto-Connect
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | devops | low | POST connection to bridge API | `{skill_dir}/data/connections.yaml` |
| 3.2 | devops | low | Mount plugin pages and rebuild dashboard | `apps/dashboard/` |

### Final Phase: Verification

| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run `npm run build` in `apps/dashboard/` |
| V.2 | validator | low | Verify hub loads at `localhost:3000/{hub_id}` |

### Completion Criteria

- [ ] All plugin files generated in `{skill_dir}/`
- [ ] `npm run build` passes
- [ ] Hub accessible at `/{hub_id}`
- [ ] ExternalDataCards render connected data
- [ ] ADR status updated to Accepted
"""
