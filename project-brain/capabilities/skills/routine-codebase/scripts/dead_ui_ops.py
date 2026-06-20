"""auto-dead-ui: Detect unwired UI elements in dashboard pages."""
from __future__ import annotations


import importlib.util as _augur_importlib_util
import sys as _augur_sys
from pathlib import Path as _AugurPath

_augur_bootstrap_start = _AugurPath(__file__).resolve()
for _augur_bootstrap_parent in (_augur_bootstrap_start.parent, *_augur_bootstrap_start.parents):
    _augur_bootstrap_path = _augur_bootstrap_parent / "daemon" / "scripts" / "bootstrap_paths.py"
    if _augur_bootstrap_path.is_file():
        break
else:
    raise RuntimeError(f"Unable to locate shared skill bootstrap from {_augur_bootstrap_start}")

_augur_bootstrap_spec = _augur_importlib_util.spec_from_file_location(
    "_augur_shared_bootstrap_paths", _augur_bootstrap_path
)
if _augur_bootstrap_spec is None or _augur_bootstrap_spec.loader is None:
    raise RuntimeError(f"Unable to load shared skill bootstrap from {_augur_bootstrap_path}")
_augur_bootstrap_module = _augur_importlib_util.module_from_spec(_augur_bootstrap_spec)
_augur_sys.modules[_augur_bootstrap_spec.name] = _augur_bootstrap_module
_augur_bootstrap_spec.loader.exec_module(_augur_bootstrap_module)
_augur_bootstrap_module.ensure_project_paths(__file__)
import re
from pathlib import Path

import yaml

from src.config.paths import get_all_client_skill_dirs, get_skill_data_dir
from src.lib.ops_protocol import (
    OpsContext, ScanResult, find_api_routes, find_page_routes, report_only_fix,
)

name = "auto-dead-ui"

DIFFICULTY_SPEC = {
    0: "Surface check — count pages with interactive elements",
    1: "Content check — empty handlers, disabled buttons, missing action refs",
    2: "Deep check — broken link/fetch targets",
    3: "Exhaustive — buttons without handlers, contextless actions, shallow prompts, dead prompt paths",
}

# ---------------------------------------------------------------------------
# Regex patterns for detection
# ---------------------------------------------------------------------------
_EMPTY_HANDLER = re.compile(
    r'onClick\s*=\s*\{\s*\(\)\s*=>\s*\{\s*\}\s*\}', re.MULTILINE
)
_CONSOLE_ONLY = re.compile(
    r'onClick\s*=\s*\{\s*\(\)\s*=>\s*\{\s*console\.\w+\([^)]*\)\s*;?\s*\}\s*\}',
    re.MULTILINE,
)
_BUTTON_TAG = re.compile(r'<button\b([^>]*)>', re.MULTILINE)

_ACTION_REF = re.compile(r'runAction\([\'"]([^\'"]+)[\'"]\)')
_HREF_REF = re.compile(r'href=["\'](/[^"\']+)["\']')
_FETCH_REF = re.compile(r'fetch\([\'"](/api/[^\'"]+)[\'"]\)')
_ROUTER_PUSH = re.compile(r'router\.push\([\'"](/[^\'"]+)[\'"]\)')


def _strip_jsx_expressions(text: str) -> str:
    """Strip quoted strings and balanced JSX {...} expressions from attribute text.

    Unlike a simple regex that uses {[^}]*}, this handles nested braces (e.g.
    {saving || !newTitle.trim()} where the inner } from trim() would cause
    early termination) and backtick template literals with ${...} blocks.
    """
    result: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        # Skip double-quoted strings
        if ch == '"':
            j = i + 1
            while j < n and text[j] != '"':
                if text[j] == "\\":
                    j += 1  # skip escaped char
                j += 1
            i = j + 1
            continue
        # Skip single-quoted strings
        if ch == "'":
            j = i + 1
            while j < n and text[j] != "'":
                if text[j] == "\\":
                    j += 1
                j += 1
            i = j + 1
            continue
        # Skip balanced brace expressions (JSX)
        if ch == "{":
            depth = 1
            j = i + 1
            in_sq = in_dq = in_bt = False
            while j < n and depth > 0:
                c = text[j]
                if j > 0 and text[j - 1] == "\\":
                    j += 1
                    continue
                if c == "'" and not in_dq and not in_bt:
                    in_sq = not in_sq
                elif c == '"' and not in_sq and not in_bt:
                    in_dq = not in_dq
                elif c == "`" and not in_sq and not in_dq:
                    in_bt = not in_bt
                elif not in_sq and not in_dq and not in_bt:
                    if c == "{":
                        depth += 1
                    elif c == "}":
                        depth -= 1
                j += 1
            i = j
            continue
        result.append(ch)
        i += 1
    return "".join(result)
def _find_run_action_calls(content: str) -> list[tuple[int, str]]:
    """Find runAction({...}) calls by balanced-brace matching.

    Returns list of (char_offset, object_body) tuples.
    Handles nested braces from template literals and arrow functions.
    """
    results = []
    needle = "runAction("
    idx = 0
    while True:
        pos = content.find(needle, idx)
        if pos == -1:
            break
        # Skip past "runAction(" then find the opening {
        start = pos + len(needle)
        # Skip whitespace
        while start < len(content) and content[start] in " \t\n\r":
            start += 1
        if start >= len(content) or content[start] != "{":
            idx = pos + 1
            continue
        # Balanced-brace scan
        depth = 0
        i = start
        in_single = False
        in_double = False
        in_backtick = False
        while i < len(content):
            ch = content[i]
            # Handle escape sequences
            if i > 0 and content[i - 1] == "\\":
                i += 1
                continue
            if ch == "'" and not in_double and not in_backtick:
                in_single = not in_single
            elif ch == '"' and not in_single and not in_backtick:
                in_double = not in_double
            elif ch == "`" and not in_single and not in_double:
                in_backtick = not in_backtick
            elif not in_single and not in_double and not in_backtick:
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        body = content[start + 1 : i]
                        results.append((pos, body))
                        break
            i += 1
        idx = pos + 1
    return results

# Patterns for prop/state entity data that should be forwarded to actions
_ENTITY_PROPS = re.compile(
    r'(?:interface\s+\w+Props\s*\{|'    # TypeScript interface props
    r'(?:const|let)\s+\{)\s*'
    r'([^}]+)\}',
    re.MULTILINE,
)
# Words that indicate entity-specific data in props/state
_ENTITY_KEYWORDS = {
    "id", "name", "title", "company", "email", "subject",
    "ingredients", "tags", "category", "type", "status",
    "description", "content", "body", "url", "path",
    "recipeId", "habitId", "contractId", "goalId", "projectId",
}

# Generic descriptions that add no useful context for the AI agent
_GENERIC_DESC_PATTERNS = [
    re.compile(r'^[A-Z][a-z]+ (?:a |the )?(?:new )?\w+$'),  # "Add a thing", "Create item"
    re.compile(r'^[A-Z][a-z]+ \w+$'),  # "Add Contract", "Review NDA"
]

# Minimum useful description length (very short = likely just the label repeated)
_MIN_DESC_LENGTH = 30


def _find_page_files(project_root: Path) -> list[Path]:
    """Find all dashboard page and block component files."""
    files: list[Path] = []
    for skills_dir in get_all_client_skill_dirs(project_root):
        files.extend(skills_dir.glob("*/augur/dashboard/**/*.tsx"))
    files += list(project_root.glob("apps/dashboard/components/blocks/types/*.tsx"))
    return sorted(set(files))


def _find_action_ids(project_root: Path) -> set[str]:
    """Collect all defined action IDs from action yaml files."""
    ids: set[str] = set()
    for skills_dir in get_all_client_skill_dirs(project_root):
        for skill_dir in skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            try:
                actions_dir = get_skill_data_dir(skill_dir.name) / "actions"
            except Exception:
                continue
            for yaml_file in actions_dir.glob("*.yaml"):
                try:
                    data = yaml.safe_load(yaml_file.read_text())
                    if isinstance(data, dict) and data.get("id"):
                        ids.add(data["id"])
                    elif isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and item.get("id"):
                                ids.add(item["id"])
                except Exception:
                    continue
    return ids


def _extract_string_value(body: str, key: str) -> str:
    """Extract a string value for a given key from a JS object body."""
    # Match: key: 'value' or key: "value" or key: `value`
    m = re.search(
        rf'{key}\s*:\s*(?:'
        rf"'([^']*(?:\\.[^']*)*)'|"
        rf'"([^"]*(?:\\.[^"]*)*)"'
        rf')',
        body,
    )
    if m:
        return m.group(1) or m.group(2) or ""
    # Match template literal (just extract the static parts)
    m = re.search(rf'{key}\s*:\s*`([^`]*)`', body)
    if m:
        return m.group(1)
    return ""


def _extract_template_vars(body: str, key: str) -> list[str]:
    """Extract ${...} variable references from a template literal value."""
    m = re.search(rf'{key}\s*:\s*`([^`]*)`', body)
    if not m:
        return []
    template = m.group(1)
    return re.findall(r'\$\{([^}]+)\}', template)


def _has_entity_props(content: str) -> set[str]:
    """Detect entity-specific props/state in a component file."""
    found: set[str] = set()
    # Check interface Props definitions
    for m in re.finditer(r'interface\s+\w*Props\s*\{([^}]+)\}', content, re.DOTALL):
        block = m.group(1)
        for word in re.findall(r'(\w+)\s*[?:]', block):
            if word.lower().rstrip('s') in {k.lower() for k in _ENTITY_KEYWORDS}:
                found.add(word)
    # Check destructured props in function signature
    for m in re.finditer(r'(?:function\s+\w+|const\s+\w+\s*=)\s*\(\s*\{([^}]+)\}', content):
        block = m.group(1)
        for word in re.findall(r'(\w+)', block):
            if word.lower().rstrip('s') in {k.lower() for k in _ENTITY_KEYWORDS}:
                found.add(word)
    return found


def _check_action_prompt_quality(
    body: str, content: str, entity_props: set[str],
) -> list[str]:
    """Check if a runAction call has sufficient context quality.

    Returns a list of quality issues found.
    """
    issues: list[str] = []

    desc = _extract_string_value(body, "description")
    prompt = _extract_string_value(body, "prompt")
    label = _extract_string_value(body, "label")
    context_text = desc or prompt

    # Check 1: No description or prompt at all
    if not context_text:
        issues.append("no description or prompt — AI agent receives no context")
        return issues  # No point checking further

    # Check 2: Description is just the label repeated
    if desc and desc.strip().lower() == label.strip().lower():
        issues.append(f"description duplicates label '{label}' — adds no context")

    # Check 3: Description is too short to be useful
    if desc and not prompt and len(desc) < _MIN_DESC_LENGTH:
        # Allow if it contains template expressions (dynamic content)
        template_vars = _extract_template_vars(body, "description")
        if not template_vars:
            issues.append(
                f"description is only {len(desc)} chars with no dynamic data — "
                "likely too generic for the AI agent"
            )

    # Check 4: Component has entity props but action doesn't reference them
    if entity_props and context_text:
        # Check if any entity prop appears in description or prompt
        # (via template literal ${prop} or string concatenation)
        desc_vars = set(_extract_template_vars(body, "description"))
        prompt_vars = set(_extract_template_vars(body, "prompt"))
        all_vars = desc_vars | prompt_vars

        # If a context-aggregation variable is used (e.g. ${recipeContext},
        # ${contractSummary}), assume entity props are forwarded through it.
        context_var_names = {"context", "summary", "details", "info", "data"}
        has_context_proxy = any(
            any(cv in v.lower() for cv in context_var_names)
            for v in all_vars
        )
        if has_context_proxy:
            return issues  # Context proxy covers entity forwarding

        # Also check if the prop name appears literally in the context text
        referenced = set()
        for prop in entity_props:
            if prop in context_text or any(prop in v for v in all_vars):
                referenced.add(prop)

        unreferenced = entity_props - referenced
        # Only flag if significant entity data is available but not passed
        significant = unreferenced & {"id", "name", "title", "company", "subject", "email", "recipeId", "contractId"}
        if significant:
            issues.append(
                f"component has entity props [{', '.join(sorted(significant))}] "
                "not referenced in action description/prompt"
            )

    return issues


def scan(ctx: OpsContext) -> ScanResult:
    """Scan dashboard pages for unwired UI elements."""
    pages = _find_page_files(ctx.project_root)
    if not pages:
        return ScanResult(
            issues=[], summary="No dashboard pages found", severity="info"
        )

    # Cache page contents to avoid repeated file reads across difficulty levels
    page_cache: dict[Path, str] = {p: p.read_text(errors="replace") for p in pages}

    if ctx.difficulty < 1:
        # d0: surface count
        total_interactive = 0
        for content in page_cache.values():
            total_interactive += len(_EMPTY_HANDLER.findall(content))
            total_interactive += len(_ACTION_REF.findall(content))
            total_interactive += len(_HREF_REF.findall(content))
            total_interactive += len(_FETCH_REF.findall(content))
        return ScanResult(
            issues=[],
            summary=f"{len(pages)} pages, ~{total_interactive} interactive refs (d0 surface)",
            severity="info",
            health="verified",
        )

    issues: list[dict] = []

    # d1: empty handlers and missing action refs
    action_ids = _find_action_ids(ctx.project_root)
    for page in pages:
        content = page_cache[page]
        try:
            rel = str(page.relative_to(ctx.project_root))
        except ValueError:
            rel = str(page)

        # Empty onClick handlers
        for match in _EMPTY_HANDLER.finditer(content):
            line = content[: match.start()].count("\n") + 1
            issues.append({
                "type": "empty_handler",
                "file": rel,
                "line": line,
                "detail": "Empty onClick handler — button does nothing",
            })

        # Console-only handlers
        for match in _CONSOLE_ONLY.finditer(content):
            line = content[: match.start()].count("\n") + 1
            issues.append({
                "type": "console_only",
                "file": rel,
                "line": line,
                "detail": "onClick handler only logs to console",
            })

        # Permanently disabled buttons (bare `disabled` not `disabled={expr}`)
        for match in _BUTTON_TAG.finditer(content):
            attrs = match.group(1)
            # Strip quoted strings and JSX expressions to avoid matching
            # `disabled` inside classNames like "disabled:opacity-50"
            stripped = _strip_jsx_expressions(attrs)
            # Match bare `disabled` — not followed by `=` (conditional)
            if re.search(r"\bdisabled\b(?!\s*=)", stripped):
                line = content[: match.start()].count("\n") + 1
                issues.append({
                    "type": "permanently_disabled",
                    "file": rel,
                    "line": line,
                    "detail": "Button with bare `disabled` attribute — permanently non-interactive",
                })

        # Action refs to non-existent actions
        for match in _ACTION_REF.finditer(content):
            action_id = match.group(1)
            if action_id not in action_ids:
                line = content[: match.start()].count("\n") + 1
                issues.append({
                    "type": "missing_action",
                    "file": rel,
                    "line": line,
                    "action_id": action_id,
                    "detail": f"runAction('{action_id}') — action not defined in any actions/*.yaml",
                })

    # d2: broken link and fetch targets
    if ctx.difficulty >= 2:
        page_routes = find_page_routes(ctx.project_root, ctx.shared_snapshot)
        api_routes = find_api_routes(ctx.project_root, ctx.shared_snapshot)

        for page in pages:
            content = page_cache[page]
            try:
                rel = str(page.relative_to(ctx.project_root))
            except ValueError:
                rel = str(page)

            # Broken href links
            for match in _HREF_REF.finditer(content):
                href = match.group(1)
                # Skip anchors, external, dynamic routes
                if href.startswith("#") or "[" in href or href.startswith("/api/"):
                    continue
                # Normalize: /foo/bar -> check if route exists
                if href not in page_routes and not any(
                    href.startswith(r) for r in page_routes
                ):
                    line = content[: match.start()].count("\n") + 1
                    issues.append({
                        "type": "broken_link",
                        "file": rel,
                        "line": line,
                        "href": href,
                        "detail": f"href='{href}' — no matching page.tsx",
                    })

            # Broken fetch targets
            for match in _FETCH_REF.finditer(content):
                url = match.group(1)
                # Strip query params
                base_url = url.split("?")[0]
                if base_url not in api_routes and not any(
                    base_url.startswith(r) for r in api_routes
                ):
                    line = content[: match.start()].count("\n") + 1
                    issues.append({
                        "type": "broken_fetch",
                        "file": rel,
                        "line": line,
                        "url": url,
                        "detail": f"fetch('{url}') — no matching API route",
                    })

            # Broken router.push targets
            for match in _ROUTER_PUSH.finditer(content):
                target = match.group(1)
                if "[" in target or target.startswith("/api/"):
                    continue
                if target not in page_routes and not any(
                    target.startswith(r) for r in page_routes
                ):
                    line = content[: match.start()].count("\n") + 1
                    issues.append({
                        "type": "broken_router_push",
                        "file": rel,
                        "line": line,
                        "target": target,
                        "detail": f"router.push('{target}') — no matching page",
                    })

    # d3: buttons without handlers, action prompt quality, dead prompt paths
    if ctx.difficulty >= 3:
        for page in pages:
            content = page_cache[page]
            try:
                rel = str(page.relative_to(ctx.project_root))
            except ValueError:
                rel = str(page)

            # Buttons without onClick or type=submit
            for match in _BUTTON_TAG.finditer(content):
                attrs = match.group(1)
                if "onClick" in attrs or 'type="submit"' in attrs or "type='submit'" in attrs:
                    continue
                # Skip if disabled (already caught at d1)
                stripped = _strip_jsx_expressions(attrs)
                if re.search(r"\bdisabled\b", stripped):
                    continue
                line = content[: match.start()].count("\n") + 1
                issues.append({
                    "type": "button_no_handler",
                    "file": rel,
                    "line": line,
                    "detail": "Button without onClick or type=submit — no interaction wired",
                })

            # NOTE: Action prompt quality checks (contextless_action, shallow_action_prompt,
            # action_missing_entity_context) moved to auto-markdowns (ADR-263).

            # Prompt paths that reference non-existent files
            prompt_path_re = re.compile(
                r'prompt:\s*["\'].*?(plugins/[^\s"\']+)["\']', re.MULTILINE
            )
            for match in prompt_path_re.finditer(content):
                ref_path = match.group(1)
                if not (ctx.project_root / ref_path).exists():
                    line = content[: match.start()].count("\n") + 1
                    issues.append({
                        "type": "dead_prompt_path",
                        "file": rel,
                        "line": line,
                        "path": ref_path,
                        "detail": f"Action prompt references '{ref_path}' — path doesn't exist",
                    })

    severity = "warning" if issues else "info"
    return ScanResult(
        issues=issues,
        summary=f"{len(issues)} dead UI element(s) across {len(pages)} pages",
        severity=severity,
        items_scanned=len(pages),
    )


def fix(ctx: OpsContext, issues: list[dict]):
    return report_only_fix(ctx, "dead-ui-latest.json", issues, noun="dead UI element")
