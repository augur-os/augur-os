"""Product dimension fixer — create dirs, scaffold files, generate seeds and evals."""
from __future__ import annotations

import re
from pathlib import Path


def fix_product(skill_name: str, skill_dir: Path, signals: dict, ctx_info: dict) -> list[str]:
    """Create missing directories, scaffold files, generate seeds."""
    changes: list[str] = []

    # 1. Create missing directories.
    # Skill fallback data belongs in assets/seeds/; user-editable data lives in the vault.
    # scripts/ and references/ are allowed at skill root.
    dir_mappings = {
        "data": ("assets/seeds", "has_data_dir"),
        "scripts": ("scripts", "has_scripts"),
        "references": ("references", "has_references"),
    }
    for dirname, (target_path, signal_key) in dir_mappings.items():
        if not signals.get(signal_key, True):  # default True = don't create if signal missing
            dir_path = skill_dir / target_path
            if not dir_path.exists():
                dir_path.mkdir(parents=True, exist_ok=True)
                (dir_path / ".gitkeep").touch()
                changes.append(f"created {target_path}/")

    # 2. Generate seed data when the seed directory is empty.
    seed_dir = skill_dir / "assets" / "seeds"
    if seed_dir.exists() and not any(f for f in seed_dir.iterdir() if f.name != ".gitkeep"):
        seed_files = _generate_seeds(skill_name, ctx_info, skill_dir)
        if seed_files:
            for filename, content in seed_files.items():
                (seed_dir / filename).write_text(content)
            changes.append(f"generated {len(seed_files)} seed files in assets/seeds/")

    # 3. Scaffold browse-actions.yaml if missing and skill has augur/ dir.
    # Convention: augur/browse-actions.yaml (scorer detects "action" in name).
    # TODO_OUTDATED(ADR-807): browse-actions.yaml is retired — generic card buttons
    # are now baker DEFAULT_CARD_ACTIONS and skill-specific card actions live in
    # augur/actions.yaml. Re-point this scaffolder to emit augur/actions.yaml
    # (unified schema, surfaces:[card]) instead of re-creating the dead source.
    augur_dir = skill_dir / "augur"
    if not signals.get("has_actions", True) and augur_dir.exists():
        action_file = augur_dir / "browse-actions.yaml"
        if not action_file.exists():
            action_content = _scaffold_action(skill_name, ctx_info)
            if action_content:
                action_file.write_text(action_content)
                changes.append("scaffolded browse-actions.yaml")

    return changes


def _extract_tsx_fields(dashboard_dir: Path) -> list[str]:
    """Extract data field names from .tsx page components via regex.

    Looks for patterns like:
    - data.fieldName / item.fieldName / entry.fieldName
    - Interface/type property declarations: fieldName: type;
    - Destructuring: { fieldName, fieldName2 }
    Returns a deduplicated, sorted list of likely data field names.
    """
    fields: list[str] = []
    seen: set[str] = set()

    # Patterns for accessing data properties: data.foo, item.foo, entry.foo, result.foo
    accessor_pattern = re.compile(
        r'\b(?:data|item|entry|result|row|record)\s*\.\s*([a-zA-Z_][a-zA-Z0-9_]*)\b'
    )
    # Interface / type property: fieldName: SomeType;  or  readonly fieldName?: Type
    prop_pattern = re.compile(
        r'^\s*(?:readonly\s+)?([a-zA-Z_][a-zA-Z0-9_]*)\??\s*:\s*[A-Za-z]',
        re.MULTILINE,
    )
    # Destructuring inside JSX / function params: { name, status, createdAt }
    destructure_pattern = re.compile(
        r'\{\s*((?:[a-zA-Z_][a-zA-Z0-9_]*\s*,?\s*)+)\}'
    )

    # Common React/TypeScript keywords to skip
    skip_words = {
        "children", "className", "style", "key", "ref", "type", "id",
        "onClick", "onChange", "onSubmit", "onBlur", "onFocus",
        "React", "FC", "ReactNode", "string", "number", "boolean",
        "undefined", "null", "void", "any", "never", "unknown",
        "true", "false", "default", "export", "import", "return",
        "const", "let", "var", "function", "interface", "type",
        "extends", "implements", "class", "enum",
        "props", "state", "ctx", "context", "params", "args",
        "error", "loading", "isLoading", "setLoading",
        "useState", "useEffect", "useCallback", "useMemo",
        "map", "filter", "find", "forEach", "reduce", "length",
        "toString", "valueOf", "then", "catch", "finally",
        "href", "src", "alt", "target", "rel",
        "px", "em", "rem", "vh", "vw",
        "t", "e", "i", "k", "v",  # single-letter vars
    }

    tsx_files = list(dashboard_dir.rglob("*.tsx"))
    if not tsx_files:
        return fields

    for tsx_file in tsx_files:
        try:
            content = tsx_file.read_text(errors="replace")
        except Exception:
            continue

        for match in accessor_pattern.finditer(content):
            field = match.group(1)
            if field not in skip_words and field not in seen and len(field) > 1:
                seen.add(field)
                fields.append(field)

        for match in prop_pattern.finditer(content):
            field = match.group(1)
            if field not in skip_words and field not in seen and len(field) > 1:
                seen.add(field)
                fields.append(field)

        for match in destructure_pattern.finditer(content):
            for part in match.group(1).split(","):
                field = part.strip()
                if field and field not in skip_words and field not in seen and len(field) > 1:
                    seen.add(field)
                    fields.append(field)

    # Return sorted but preserve discovery order for first 20 unique fields
    return fields[:20]


def _fields_to_yaml_block(fields: list[str]) -> str:
    """Convert a list of field names into YAML key: value lines with placeholder values."""
    lines: list[str] = []
    for field in fields:
        # Guess a plausible placeholder value based on field name conventions
        lower = field.lower()
        if any(kw in lower for kw in ("at", "date", "time", "created", "updated", "expires")):
            value = '"2026-01-15"'
        elif any(kw in lower for kw in ("count", "total", "score", "num", "amount", "size")):
            value = "0"
        elif any(kw in lower for kw in ("is_", "has_", "enabled", "active", "visible", "show")):
            value = "true"
        elif any(kw in lower for kw in ("url", "href", "link", "path", "src")):
            value = '"https://example.com"'
        elif lower == "status":
            value = '"active"'
        elif lower in ("id", "uuid"):
            value = '"example-id-001"'
        else:
            value = f'"{field.replace("_", " ").title()} Example"'
        lines.append(f"{field}: {value}")
    return "\n".join(lines)


def _generate_seeds(skill_name: str, ctx_info: dict, skill_dir: Path | None = None) -> dict[str, str]:
    """Generate seed data files based on skill context.

    When skill_dir is provided, reads .tsx components in augur/dashboard/ to
    infer the data shape expected by the UI, producing field-accurate seed YAML.
    Falls back to a generic template when no .tsx files are found.
    """
    seeds: dict[str, str] = {}
    hub = ctx_info.get("hub", "system")
    purpose = ctx_info.get("purpose", "")

    pages = ctx_info.get("pages", [])
    if not pages and not purpose:
        return seeds

    # Attempt to infer fields from .tsx page components
    inferred_fields: list[str] = []
    if skill_dir is not None:
        dashboard_dir = skill_dir / "augur" / "dashboard"
        if dashboard_dir.exists():
            inferred_fields = _extract_tsx_fields(dashboard_dir)

    # Build the example data file
    if inferred_fields:
        # Field-accurate seed derived from component analysis
        extra_fields = _fields_to_yaml_block(inferred_fields)
        example = (
            "# Seed data for {skill_name} — auto-generated by auto-skill-quality\n"
            "_seeded: true\n"
            "_generated_by: auto-skill-quality\n"
            f"# Fields inferred from augur/dashboard/ .tsx components\n"
            f"{extra_fields}\n"
        )
    else:
        # Generic fallback when no .tsx components are present
        example = (
            f"# Seed data for {skill_name} — auto-generated by auto-skill-quality\n"
            "_seeded: true\n"
            "_generated_by: auto-skill-quality\n"
            f"name: Example {skill_name.replace('-', ' ').title()} Entry\n"
            f"description: Sample data for the {skill_name} skill\n"
            'created_at: "2026-01-15"\n'
            "status: active\n"
        )

    # Generate a manifest
    manifest = (
        f"# Seed data for {skill_name}\n"
        "# Auto-generated by auto-skill-quality loop\n"
        "tool: null  # No MCP tool — use file copy\n"
        "data_path: .\n"
        "files:\n"
        f"  - example-{skill_name}.yaml\n"
    )
    seeds["_seed.yaml"] = manifest
    seeds[f"example-{skill_name}.yaml"] = example

    return seeds


def _scaffold_action(skill_name: str, ctx_info: dict) -> str:
    """Generate a minimal browse-actions.yaml for the skill."""
    hub = ctx_info.get("hub", "system")
    title = skill_name.replace("-", " ").title()

    return (
        "categories:\n"
        "  skills:\n"
        f"    - id: {skill_name}-overview\n"
        f'      label: "Overview"\n'
        f'      icon: Info\n'
        f'      kind: ai\n'
        f'      template: "Tell me about the {title} skill at {{{{path}}}}. What does it do and how is it used?"\n'
    )


def _tool_to_action(tool_name: str) -> str:
    """Convert a hyphenated MCP tool name to a natural-language action phrase."""
    parts = tool_name.split("-")
    if len(parts) >= 2:
        verb = parts[0]
        noun = " ".join(parts[1:])
        return f"{verb} a {noun}"
    return f"use the {tool_name} feature"


def _make_seed(id_num: int, prompt: str, expected: str, expectations: list[str]) -> dict:
    """Create a single seed test-case entry in skill-creator schema."""
    return {
        "id": id_num,
        "prompt": prompt,
        "expected_output": expected,
        "files": [],
        "expectations": expectations,
        "confidence": "seed",
    }


def generate_seed_evals(skill_path: Path, fm: dict) -> dict:
    """Generate seed test cases from skill metadata, following skill-creator schema."""
    skill_type = fm.get("x-augur-type", "domain")
    name = fm.get("name", skill_path.name)
    description = fm.get("description", "")
    tools = fm.get("x-augur-mcp-tools", [])

    if not description:
        return {"skill_name": name, "evals": []}

    cases: list[dict] = []

    if skill_type == "command":
        cases.append(_make_seed(
            1, f"Run /{name} with default arguments",
            f"The /{name} command executes and returns a useful result",
            [f"The skill /{name} is triggered",
             "Output is non-empty and relevant to the command's purpose",
             "No errors or stack traces in output"],
        ))
        cases.append(_make_seed(
            2, f"Run /{name} --help",
            "Usage information with flags and examples",
            ["Output contains usage or syntax information",
             "Available flags or options are listed"],
        ))

    elif skill_type == "domain" and tools:
        for i, tool in enumerate(tools[:3]):
            cases.append(_make_seed(
                i + 1,
                f"Use the {name} skill to {_tool_to_action(tool)}",
                f"The {tool} MCP tool executes successfully",
                [f"The {tool} tool is called",
                 "Tool returns structured data without errors"],
            ))

    elif skill_type == "autoloop":
        cases.append(_make_seed(
            1, f"Run /{name} at difficulty 0 (scan only)",
            "Scan report with issues list",
            ["Returns a scan result with issues array",
             "No unhandled exceptions",
             "Follows ops_protocol format"],
        ))

    elif skill_type == "library-reference":
        cases.append(_make_seed(
            1,
            f"I'm working with code that uses patterns from {name}. What gotchas should I know about?",
            "References the skill's gotchas documentation",
            [f"The {name} skill is triggered",
             "Response references specific gotchas or patterns"],
        ))

    elif skill_type == "runbook":
        cases.append(_make_seed(
            1,
            f"Something related to {name.replace('-', ' ')} is broken. Help me troubleshoot.",
            "Step-by-step troubleshooting procedure",
            [f"The {name} skill is triggered",
             "Response contains numbered or ordered steps"],
        ))

    elif skill_type == "template":
        cases.append(_make_seed(
            1,
            f"Create a new project using the {name.replace('-', ' ')} template",
            "Files scaffolded from template",
            [f"The {name} skill is triggered",
             "Output files are created based on the template"],
        ))

    else:
        cases.append(_make_seed(
            1, f"Use the {name} skill: {description[:100]}",
            "The skill executes and produces relevant output",
            [f"The {name} skill is triggered",
             "Output is non-empty and relevant",
             "No errors or stack traces"],
        ))

    return {"skill_name": name, "evals": cases}
