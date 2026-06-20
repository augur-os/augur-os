# MCP Health Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `auto-mcp-health-audit` — a 4-phase auto-command that finds and fixes broken MCP wiring across all 474 proxy route toolName references.

**Architecture:** Single Python script implementing `OpsCommand` protocol (scan/fix). Phase 1 does static cross-referencing of route toolNames vs `@mcp.tool(name=...)` registrations. Phase 2 probes tools via HTTP. Phase 3 auto-fixes safe cases. Phase 4 writes a structured report. Difficulty d0-d4 gates which phases run.

**Tech Stack:** Python 3.11+, `src.lib.ops_protocol` (ScanResult/FixResult/make_issue), `src.config.paths`, `difflib` (fuzzy matching), `urllib.request` (HTTP probes — stdlib only, no deps)

**Spec:** `docs/superpowers/specs/2026-03-22-mcp-health-audit-design.md`

---

## File Structure

| Action | Path | Responsibility |
|--------|------|---------------|
| Create | `.claude/skills/auto-mcp-health-audit/SKILL.md` | Frontmatter with x-augur-loop config |
| Create | `.claude/skills/auto-mcp-health-audit/scripts/mcp_health_audit.py` | Main script: scan(), fix(), all 4 phases |
| Create | `.claude/skills/auto-mcp-health-audit/augur/tests/test_mcp_health_audit.py` | Unit tests for all phases |

---

### Task 1: Scaffold skill directory and write SKILL.md

**Files:**
- Create: `.claude/skills/auto-mcp-health-audit/SKILL.md`

- [ ] **Step 1: Create skill directory**

```bash
mkdir -p .claude/skills/auto-mcp-health-audit/scripts
mkdir -p .claude/skills/auto-mcp-health-audit/augur/tests
```

- [ ] **Step 2: Write SKILL.md**

Write `.claude/skills/auto-mcp-health-audit/SKILL.md`:

```markdown
---
x-augur-origin: augur
name: auto-mcp-health-audit
x-augur-type: autoloop
x-augur-tags: []
description: 'End-to-end MCP health audit — static wiring cross-reference, runtime probe, auto-fix, and report generation for adaptive engine and self-healing automation. Covers: auto-mcp-health-audit, scan'
x-augur-visibility: auto
x-augur-loop:
  name: testing
  tier: 2
  trigger: nightly
  trust: 0.05
  config:
    fix_timeout: 180
    max_turns: 8
x-augur-hub: adaptive
x-augur-tab: infrastructure
x-augur-plugin: augur-adaptive
---

# auto-mcp-health-audit

End-to-end MCP health audit with 4 phases: static wiring cross-reference, runtime probe, auto-fix safe cases, and structured report. Finds and fixes empty dashboard pages caused by broken MCP tool wiring.

## What This Does

Scans all ~474 proxy route `toolName` references in `_routes-{a,b,c}.ts` and cross-references them against actual `@mcp.tool(name=...)` registrations in Python. At higher difficulty, probes tools at runtime via HTTP and auto-fixes safe cases (typos, missing dirs).

## Difficulty Levels

| Level | Phases | Runtime |
|-------|--------|---------|
| 0 | Static wiring only | ~5s |
| 1 | Static + runtime probe | ~30-60s |
| 2 | Static + runtime + auto-fix | ~60-90s |
| 3 | d2 + transformResponse validation | ~2min |
| 4 | d3 + needs-args tool invocation | ~3min |

## Usage

```bash
/auto-mcp-health-audit          # Default difficulty
/auto-mcp-health-audit --d 2    # With auto-fix
```
```

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/auto-mcp-health-audit/
git commit -m "feat(auto-mcp-health-audit): scaffold skill directory and SKILL.md"
```

---

### Task 2: Phase 1a — Route toolName extraction

**Files:**
- Create: `.claude/skills/auto-mcp-health-audit/augur/tests/test_mcp_health_audit.py`
- Create: `.claude/skills/auto-mcp-health-audit/scripts/mcp_health_audit.py`

- [ ] **Step 1: Write failing test for route extraction**

Write `.claude/skills/auto-mcp-health-audit/augur/tests/test_mcp_health_audit.py`:

```python
"""Tests for auto-mcp-health-audit."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from src.lib.ops_protocol import OpsContext, ScanResult

# Dynamic import of script module
_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "mcp_health_audit.py"
_SPEC = importlib.util.spec_from_file_location("mcp_health_audit", _MODULE_PATH)
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _ctx(tmp_path: Path, difficulty: int = 0, **kw) -> OpsContext:
    return OpsContext(project_root=tmp_path, difficulty=difficulty, **kw)


# ── Phase 1a: Route toolName extraction ──


def test_extract_route_tool_names_basic(tmp_path: Path) -> None:
    """Extracts toolName values from _routes-*.ts files."""
    routes_dir = tmp_path / "apps" / "dashboard" / "app" / "api" / "[...proxy]"
    _write(
        routes_dir / "_routes-a.ts",
        '''export const ROUTES_A: RouteMap = {
  "browse/items": {
    GET: {
      toolName: "browse-index",
    },
  },
  "career/companies": {
    GET: {
      toolName: "get-career-companies",
      fallback: { success: true, data: [] },
    },
    POST: {
      toolName: "create-career-company",
    },
  },
};''',
    )

    result = mod.extract_route_tool_names(tmp_path)

    assert "browse-index" in result
    assert "get-career-companies" in result
    assert "create-career-company" in result
    # Each entry maps to list of route paths
    assert result["browse-index"] == ["browse/items"]
    assert result["get-career-companies"] == ["career/companies"]


def test_extract_route_tool_names_empty(tmp_path: Path) -> None:
    """Returns empty dict when no route files exist."""
    result = mod.extract_route_tool_names(tmp_path)
    assert result == {}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd ~/Projects/Augur && python -m pytest .claude/skills/auto-mcp-health-audit/augur/tests/test_mcp_health_audit.py::test_extract_route_tool_names_basic -v
```

Expected: FAIL — module doesn't exist yet.

- [ ] **Step 3: Write minimal implementation**

Write `.claude/skills/auto-mcp-health-audit/scripts/mcp_health_audit.py`:

```python
"""auto-mcp-health-audit: End-to-end MCP health audit with 4 phases."""

from __future__ import annotations

import re
from pathlib import Path

from src.config.paths import get_project_root
from src.lib.ops_protocol import (
    FixClassification,
    FixResult,
    OpsContext,
    ScanResult,
    classify_fix,
    evolution_gap,
    make_issue,
    write_report,
)

name = "auto-mcp-health-audit"

DIFFICULTY_SPEC = {
    0: "Static wiring cross-reference only",
    1: "Static + runtime probe via HTTP",
    2: "Static + runtime + auto-fix safe cases",
    3: "d2 + transformResponse field validation",
    4: "d3 + scaffolded-args invocation for needs-args tools",
}

_TOOL_NAME_RE = re.compile(r'toolName:\s*"\'["\']')

_PROXY_DIR = Path("apps/dashboard/app/api/[...proxy]")

# Top-level route keys are indented at exactly 2 spaces in the route files.
# Deeper-indented keys (fallback objects, nested configs) are skipped.
_ROUTE_PATH_RE = re.compile(r'^  "([^"]+)":\s*\{', re.MULTILINE)


def extract_route_tool_names(project_root: Path) -> dict[str, list[str]]:
    """Extract all toolName values from proxy route config files.

    Returns: dict mapping toolName -> list of route paths that reference it.
    """
    proxy_dir = project_root / _PROXY_DIR
    result: dict[str, list[str]] = {}

    for filepath in sorted(proxy_dir.glob("_routes-*.ts")):
        content = filepath.read_text()

        # Find top-level route paths (exactly 2-space indent) and their toolNames
        lines = content.split("\n")
        current_route = ""
        for line in lines:
            route_match = _ROUTE_PATH_RE.match(line)
            if route_match:
                current_route = route_match.group(1)

            tool_match = _TOOL_NAME_RE.search(line)
            if tool_match and current_route:
                tool_name = tool_match.group(1)
                result.setdefault(tool_name, [])
                if current_route not in result[tool_name]:
                    result[tool_name].append(current_route)

    return result
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd ~/Projects/Augur && python -m pytest .claude/skills/auto-mcp-health-audit/augur/tests/test_mcp_health_audit.py::test_extract_route_tool_names_basic .claude/skills/auto-mcp-health-audit/augur/tests/test_mcp_health_audit.py::test_extract_route_tool_names_empty -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/auto-mcp-health-audit/scripts/mcp_health_audit.py .claude/skills/auto-mcp-health-audit/augur/tests/test_mcp_health_audit.py
git commit -m "feat(auto-mcp-health-audit): Phase 1a — route toolName extraction"
```

---

### Task 3: Phase 1b — MCP registration extraction

**Files:**
- Modify: `.claude/skills/auto-mcp-health-audit/augur/tests/test_mcp_health_audit.py`
- Modify: `.claude/skills/auto-mcp-health-audit/scripts/mcp_health_audit.py`

- [ ] **Step 1: Write failing test for MCP registration extraction**

Append to test file:

```python
# ── Phase 1b: MCP registration extraction ──


def test_extract_mcp_registrations_basic(tmp_path: Path) -> None:
    """Extracts @mcp.tool(name=...) from Python files."""
    # Core tool (single-line decorator)
    core_dir = tmp_path / "src" / "mcp" / "augur_mcp" / "core"
    _write(
        core_dir / "skills.py",
        '''
@mcp.tool(name="list-skills")
async def list_skills_tool():
    pass

@mcp.tool(name="get-skill")
async def get_skill_tool():
    pass
''',
    )

    # Plugin tool (multi-line decorator)
    plugin_dir = tmp_path / ".claude" / "skills" / "scraper" / "scripts" / "mcp"
    _write(
        plugin_dir / "__init__.py",
        '''
@mcp.tool(
    name="get-scraper-status",
    annotations=tool_annotations(readOnlyHint=True),
)
async def get_scraper_status():
    pass
''',
    )

    # Plugin sub-module
    _write(
        plugin_dir / "_tools.py",
        '''
@mcp.tool(name="scrape-url")
async def scrape_url():
    pass
''',
    )

    result = mod.extract_mcp_registrations(tmp_path)

    assert "list-skills" in result
    assert "get-skill" in result
    assert "get-scraper-status" in result
    assert "scrape-url" in result
    # Values are file paths
    assert "skills.py" in result["list-skills"]


def test_extract_mcp_registrations_empty(tmp_path: Path) -> None:
    """Returns empty dict when no Python MCP files exist."""
    result = mod.extract_mcp_registrations(tmp_path)
    assert result == {}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd ~/Projects/Augur && python -m pytest .claude/skills/auto-mcp-health-audit/augur/tests/test_mcp_health_audit.py::test_extract_mcp_registrations_basic -v
```

Expected: FAIL — `extract_mcp_registrations` doesn't exist.

- [ ] **Step 3: Write implementation**

Add to `mcp_health_audit.py`:

```python
_MCP_BLOCK_RE = re.compile(r"@mcp\.tool\([^)]*\)", re.DOTALL)
_MCP_NAME_RE = re.compile(r'name\s*=\s*"\'["\']')

_MCP_GLOBS = [
    "src/mcp/augur_mcp/**/*.py",
    ".claude/skills/*/scripts/mcp/**/*.py",
    "plugins/*/skills/*/scripts/mcp/**/*.py",
]


def extract_mcp_registrations(project_root: Path) -> dict[str, str]:
    """Extract all @mcp.tool(name=...) registrations from Python files.

    Returns: dict mapping tool_name -> relative file path.
    """
    result: dict[str, str] = {}

    for glob_pattern in _MCP_GLOBS:
        for py_file in project_root.glob(glob_pattern):
            if py_file.name.startswith("test_"):
                continue
            try:
                content = py_file.read_text()
            except (OSError, UnicodeDecodeError):
                continue

            for block_match in _MCP_BLOCK_RE.finditer(content):
                name_match = _MCP_NAME_RE.search(block_match.group(0))
                if name_match:
                    tool_name = name_match.group(1)
                    rel_path = str(py_file.relative_to(project_root))
                    result[tool_name] = rel_path

    return result
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd ~/Projects/Augur && python -m pytest .claude/skills/auto-mcp-health-audit/augur/tests/test_mcp_health_audit.py::test_extract_mcp_registrations_basic .claude/skills/auto-mcp-health-audit/augur/tests/test_mcp_health_audit.py::test_extract_mcp_registrations_empty -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/auto-mcp-health-audit/scripts/mcp_health_audit.py .claude/skills/auto-mcp-health-audit/augur/tests/test_mcp_health_audit.py
git commit -m "feat(auto-mcp-health-audit): Phase 1b — MCP registration extraction"
```

---

### Task 4: Phase 1c-d — Cross-reference and fuzzy match

**Files:**
- Modify: `.claude/skills/auto-mcp-health-audit/augur/tests/test_mcp_health_audit.py`
- Modify: `.claude/skills/auto-mcp-health-audit/scripts/mcp_health_audit.py`

- [ ] **Step 1: Write failing tests**

Append to test file:

```python
# ── Phase 1c-d: Cross-reference and fuzzy match ──


def test_cross_reference_finds_mismatches(tmp_path: Path) -> None:
    """Detects toolNames in routes that have no MCP registration."""
    route_tools = {"browse-index": ["browse/items"], "fake-tool": ["fake/route"]}
    mcp_tools = {"browse-index": "src/mcp/core/browse.py"}

    result = mod.cross_reference(route_tools, mcp_tools)

    assert len(result["mismatches"]) == 1
    assert result["mismatches"][0]["tool_name"] == "fake-tool"
    assert len(result["wired"]) == 1
    assert "browse-index" in result["wired"]


def test_cross_reference_finds_orphans(tmp_path: Path) -> None:
    """Detects registered tools with no route consumer."""
    route_tools = {"browse-index": ["browse/items"]}
    mcp_tools = {
        "browse-index": "src/mcp/core/browse.py",
        "orphan-tool": "src/mcp/core/orphan.py",
    }

    result = mod.cross_reference(route_tools, mcp_tools)

    assert len(result["orphans"]) == 1
    assert result["orphans"][0]["tool_name"] == "orphan-tool"


def test_fuzzy_match_suggests_close_names(tmp_path: Path) -> None:
    """Suggests fuzzy matches for mismatched toolNames."""
    route_tools = {"get-career-company": ["career/companies"]}
    mcp_tools = {"get-career-companies": "src/mcp/career.py"}

    result = mod.cross_reference(route_tools, mcp_tools)

    assert len(result["mismatches"]) == 1
    mismatch = result["mismatches"][0]
    assert mismatch["closest_match"] == "get-career-companies"
    assert mismatch["distance"] <= 2
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/Projects/Augur && python -m pytest .claude/skills/auto-mcp-health-audit/augur/tests/test_mcp_health_audit.py::test_cross_reference_finds_mismatches -v
```

Expected: FAIL — `cross_reference` doesn't exist.

- [ ] **Step 3: Write implementation**

Add to `mcp_health_audit.py`:

```python
import difflib


def cross_reference(
    route_tools: dict[str, list[str]],
    mcp_tools: dict[str, str],
) -> dict[str, list[dict]]:
    """Cross-reference route toolNames against MCP registrations.

    Returns dict with keys: mismatches, wired, orphans.
    """
    registered_names = set(mcp_tools.keys())
    route_names = set(route_tools.keys())

    wired = route_names & registered_names
    mismatch_names = route_names - registered_names
    orphan_names = registered_names - route_names

    mismatches = []
    for tool_name in sorted(mismatch_names):
        entry: dict = {
            "tool_name": tool_name,
            "routes": route_tools[tool_name],
            "closest_match": None,
            "distance": None,
        }
        # Fuzzy match
        close = difflib.get_close_matches(tool_name, registered_names, n=1, cutoff=0.7)
        if close:
            candidate = close[0]
            # Compute Levenshtein-ish distance via SequenceMatcher
            ratio = difflib.SequenceMatcher(None, tool_name, candidate).ratio()
            # Approximate edit distance: len * (1 - ratio)
            approx_dist = round(max(len(tool_name), len(candidate)) * (1 - ratio))
            if approx_dist <= 2:
                entry["closest_match"] = candidate
                entry["distance"] = approx_dist

        mismatches.append(entry)

    orphans = [
        {"tool_name": t, "file": mcp_tools[t]} for t in sorted(orphan_names)
    ]

    return {
        "mismatches": mismatches,
        "wired": sorted(wired),
        "orphans": orphans,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd ~/Projects/Augur && python -m pytest .claude/skills/auto-mcp-health-audit/augur/tests/test_mcp_health_audit.py -k "cross_reference or fuzzy" -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/auto-mcp-health-audit/scripts/mcp_health_audit.py .claude/skills/auto-mcp-health-audit/augur/tests/test_mcp_health_audit.py
git commit -m "feat(auto-mcp-health-audit): Phase 1c-d — cross-reference and fuzzy match"
```

---

### Task 5: Phase 2 — Runtime probe

**Files:**
- Modify: `.claude/skills/auto-mcp-health-audit/augur/tests/test_mcp_health_audit.py`
- Modify: `.claude/skills/auto-mcp-health-audit/scripts/mcp_health_audit.py`

- [ ] **Step 1: Write failing tests**

Append to test file:

```python
# ── Phase 2: Runtime probe ──

from unittest.mock import patch, MagicMock
import json


def test_classify_probe_response_healthy() -> None:
    """200 with valid data = healthy."""
    result = mod.classify_probe_response(200, {"data": [1, 2, 3]})
    assert result["status"] == "healthy"


def test_classify_probe_response_fallback() -> None:
    """200 with _fallback: true = fallback-masked."""
    result = mod.classify_probe_response(200, {"_fallback": True, "_reason": "tool_error"})
    assert result["status"] == "fallback-masked"


def test_classify_probe_response_app_error() -> None:
    """200 with error field = app-error."""
    result = mod.classify_probe_response(200, {"error": "Something failed"})
    assert result["status"] == "app-error"


def test_classify_probe_response_500() -> None:
    """500 = runtime-error."""
    result = mod.classify_probe_response(500, {"error": "ImportError: no module named foo"})
    assert result["status"] == "runtime-error"


def test_fingerprint_error_import() -> None:
    """ImportError gets correct fingerprint."""
    assert mod.fingerprint_error("ImportError: No module named 'foo'") == "import-error"


def test_fingerprint_error_file_not_found() -> None:
    """FileNotFoundError gets correct fingerprint."""
    assert mod.fingerprint_error("FileNotFoundError: /path/to/data") == "missing-file"


def test_fingerprint_error_needs_args() -> None:
    """TypeError about missing argument = needs-args."""
    assert mod.fingerprint_error("TypeError: missing 1 required positional argument") == "needs-args"


def test_probe_all_tools_aborts_on_connection_error() -> None:
    """Stops probing when server is unreachable."""
    import urllib.error

    with patch.object(mod.urllib.request, "urlopen") as mock_urlopen:
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
        results = mod.probe_all_tools(["tool-a", "tool-b", "tool-c"])
        assert len(results) == 1  # Stopped after first failure
        assert results[0]["status"] == "connection-error"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/Projects/Augur && python -m pytest .claude/skills/auto-mcp-health-audit/augur/tests/test_mcp_health_audit.py -k "classify_probe or fingerprint" -v
```

Expected: FAIL

- [ ] **Step 3: Write implementation**

Add to `mcp_health_audit.py`:

```python
import json
import urllib.request
import urllib.error


def classify_probe_response(status_code: int, body: dict) -> dict:
    """Classify an MCP tool probe response.

    Returns dict with status, error_type, error_message.
    """
    if status_code == 200:
        if body.get("_fallback"):
            return {
                "status": "fallback-masked",
                "reason": body.get("_reason", "unknown"),
                "error_message": body.get("_error", ""),
            }
        if "error" in body and body["error"]:
            return {
                "status": "app-error",
                "error_message": str(body["error"]),
                "error_type": fingerprint_error(str(body["error"])),
            }
        return {"status": "healthy"}

    # Non-200
    error_msg = str(body.get("error", "Unknown error"))
    return {
        "status": "runtime-error",
        "error_message": error_msg,
        "error_type": fingerprint_error(error_msg),
    }


def fingerprint_error(error_msg: str) -> str:
    """Classify error message into a fingerprint category."""
    msg = error_msg.lower()
    if "importerror" in msg or "modulenotfounderror" in msg or "no module named" in msg:
        return "import-error"
    if "filenotfounderror" in msg or "no such file" in msg:
        return "missing-file"
    if "typeerror" in msg and "required" in msg and "argument" in msg:
        return "needs-args"
    if "keyerror" in msg:
        return "key-error"
    if "attributeerror" in msg:
        return "attribute-error"
    if "syntaxerror" in msg:
        return "syntax-error"
    return "unknown"


def probe_tool(tool_name: str, base_url: str = "http://localhost:3000") -> dict:
    """Probe a single MCP tool via HTTP POST.

    Returns: classification dict from classify_probe_response.
    """
    url = f"{base_url}/api/mcp/tool"
    payload = json.dumps({"tool": tool_name, "args": {}}).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read())
            result = classify_probe_response(resp.status, body)
            result["tool_name"] = tool_name
            return result
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read())
        except Exception:
            body = {"error": str(e)}
        result = classify_probe_response(e.code, body)
        result["tool_name"] = tool_name
        return result
    except urllib.error.URLError as e:
        return {
            "tool_name": tool_name,
            "status": "connection-error",
            "error_message": str(e.reason),
        }
    except TimeoutError:
        return {
            "tool_name": tool_name,
            "status": "timeout",
            "error_message": "Tool did not respond within 10s",
        }


def probe_all_tools(
    wired_tools: list[str], base_url: str = "http://localhost:3000"
) -> list[dict]:
    """Probe all wired tools and return classification results."""
    results = []
    for tool_name in wired_tools:
        result = probe_tool(tool_name, base_url)
        # Abort on connection error (server is down)
        if result["status"] == "connection-error":
            results.append(result)
            break
        results.append(result)
    return results
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd ~/Projects/Augur && python -m pytest .claude/skills/auto-mcp-health-audit/augur/tests/test_mcp_health_audit.py -k "classify_probe or fingerprint" -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/auto-mcp-health-audit/scripts/mcp_health_audit.py .claude/skills/auto-mcp-health-audit/augur/tests/test_mcp_health_audit.py
git commit -m "feat(auto-mcp-health-audit): Phase 2 — runtime probe and error fingerprinting"
```

---

### Task 6: Phase 3 — Auto-fix safe cases

**Files:**
- Modify: `.claude/skills/auto-mcp-health-audit/augur/tests/test_mcp_health_audit.py`
- Modify: `.claude/skills/auto-mcp-health-audit/scripts/mcp_health_audit.py`

- [ ] **Step 1: Write failing tests**

Append to test file:

```python
# ── Phase 3: Auto-fix ──


def test_fix_toolname_typo(tmp_path: Path) -> None:
    """Patches toolName typo in route file."""
    routes_dir = tmp_path / "apps" / "dashboard" / "app" / "api" / "[...proxy]"
    _write(
        routes_dir / "_routes-a.ts",
        '''export const ROUTES_A: RouteMap = {
  "career/companies": {
    GET: {
      toolName: "get-career-company",
    },
  },
};''',
    )

    changes = mod.fix_toolname_typo(
        project_root=tmp_path,
        wrong_name="get-career-company",
        correct_name="get-career-companies",
    )

    assert len(changes) == 1
    content = (routes_dir / "_routes-a.ts").read_text()
    assert "get-career-companies" in content
    assert "get-career-company" not in content


def test_fix_missing_data_dir(tmp_path: Path) -> None:
    """Creates missing data directory."""
    target = tmp_path / "some" / "data" / "dir"
    assert not target.exists()

    changes = mod.fix_missing_dir(str(target))

    assert len(changes) == 1
    assert target.exists()


def test_apply_safe_fixes_respects_limit(tmp_path: Path) -> None:
    """Aborts if a single fix would affect more than 3 files."""
    issues = [
        {
            "fix_type": "toolname-typo",
            "wrong_name": "a",
            "correct_name": "b",
            "affected_files": ["f1.ts", "f2.ts", "f3.ts", "f4.ts"],
        }
    ]

    result = mod.apply_safe_fixes(tmp_path, issues)
    assert result["skipped"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/Projects/Augur && python -m pytest .claude/skills/auto-mcp-health-audit/augur/tests/test_mcp_health_audit.py -k "fix_toolname or fix_missing or apply_safe" -v
```

Expected: FAIL

- [ ] **Step 3: Write implementation**

Add to `mcp_health_audit.py` (note: `classify_fix` and `FixClassification` are already imported in the initial import block):

```python
def fix_toolname_typo(
    project_root: Path, wrong_name: str, correct_name: str
) -> list[str]:
    """Replace a toolName typo in proxy route files. Returns list of changed files."""
    changed = []
    proxy_dir = project_root / _PROXY_DIR

    for filepath in sorted(proxy_dir.glob("_routes-*.ts")):
        if not filepath.exists():
            continue

        content = filepath.read_text()
        if wrong_name not in content:
            continue

        # Safety: classify_fix before applying
        classification, _ = classify_fix("code-fix", str(filepath), project_root)
        if classification == FixClassification.REVERTING:
            continue

        new_content = content.replace(
            f'toolName: "{wrong_name}"',
            f'toolName: "{correct_name}"',
        )
        if new_content != content:
            filepath.write_text(new_content)
            changed.append(str(filepath.relative_to(project_root)))

    return changed


def fix_missing_dir(dir_path: str) -> list[str]:
    """Create a missing directory. Returns list of created paths."""
    p = Path(dir_path)
    if not p.exists():
        p.mkdir(parents=True, exist_ok=True)
        return [str(p)]
    return []


def apply_safe_fixes(
    project_root: Path, fixable_issues: list[dict]
) -> dict[str, int]:
    """Apply all safe fixes. Returns counts of applied/skipped."""
    applied = 0
    skipped = 0
    all_changes: list[str] = []

    for issue in fixable_issues:
        fix_type = issue.get("fix_type", "")
        affected = issue.get("affected_files", [])

        # Safety: abort if fix touches too many files
        if len(affected) > 3:
            skipped += 1
            continue

        if fix_type == "toolname-typo":
            changes = fix_toolname_typo(
                project_root, issue["wrong_name"], issue["correct_name"]
            )
            all_changes.extend(changes)
            applied += 1 if changes else 0

        elif fix_type == "missing-dir":
            changes = fix_missing_dir(issue["dir_path"])
            all_changes.extend(changes)
            applied += 1 if changes else 0

        else:
            skipped += 1

    return {"applied": applied, "skipped": skipped, "changes": all_changes}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd ~/Projects/Augur && python -m pytest .claude/skills/auto-mcp-health-audit/augur/tests/test_mcp_health_audit.py -k "fix_toolname or fix_missing or apply_safe" -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/auto-mcp-health-audit/scripts/mcp_health_audit.py .claude/skills/auto-mcp-health-audit/augur/tests/test_mcp_health_audit.py
git commit -m "feat(auto-mcp-health-audit): Phase 3 — auto-fix safe cases"
```

---

### Task 7: Phase 4 — Report generation

**Files:**
- Modify: `.claude/skills/auto-mcp-health-audit/augur/tests/test_mcp_health_audit.py`
- Modify: `.claude/skills/auto-mcp-health-audit/scripts/mcp_health_audit.py`

- [ ] **Step 1: Write failing test**

Append to test file:

```python
# ── Phase 4: Report generation ──


def test_generate_report_markdown(tmp_path: Path) -> None:
    """Generates structured markdown report."""
    audit_data = {
        "phase1": {
            "route_count": 10,
            "registered_count": 8,
            "mismatches": [
                {
                    "tool_name": "fake-tool",
                    "routes": ["fake/route"],
                    "closest_match": "fake-tools",
                    "distance": 1,
                }
            ],
            "wired": ["browse-index"],
            "orphans": [{"tool_name": "orphan", "file": "src/orphan.py"}],
        },
        "phase2": {
            "healthy": [{"tool_name": "browse-index", "status": "healthy"}],
            "failures": [],
            "fallback_masked": [],
        },
        "phase3": {"applied": 0, "skipped": 0, "changes": []},
    }

    report = mod.generate_report(audit_data)

    assert "## Critical: Wiring Mismatches" in report
    assert "fake-tool" in report
    assert "## Healthy" in report
    assert "browse-index" in report
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd ~/Projects/Augur && python -m pytest .claude/skills/auto-mcp-health-audit/augur/tests/test_mcp_health_audit.py::test_generate_report_markdown -v
```

Expected: FAIL

- [ ] **Step 3: Write implementation**

Add to `mcp_health_audit.py`:

```python
from datetime import datetime, timezone


def generate_report(audit_data: dict) -> str:
    """Generate structured markdown report from audit data."""
    p1 = audit_data.get("phase1", {})
    p2 = audit_data.get("phase2", {})
    p3 = audit_data.get("phase3", {})

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    mismatches = p1.get("mismatches", [])
    failures = p2.get("failures", [])
    fallback_masked = p2.get("fallback_masked", [])
    healthy = p2.get("healthy", [])
    orphans = p1.get("orphans", [])

    lines = [
        "---",
        f"generated: {now}",
        f"phase1_routes: {p1.get('route_count', 0)}",
        f"phase1_registered: {p1.get('registered_count', 0)}",
        f"phase1_mismatches: {len(mismatches)}",
        f"phase2_healthy: {len(healthy)}",
        f"phase2_fallback_masked: {len(fallback_masked)}",
        f"phase2_errors: {len(failures)}",
        f"phase3_auto_fixed: {p3.get('applied', 0)}",
        f"phase3_needs_human: {p3.get('skipped', 0)}",
        "---",
        "",
    ]

    # Mismatches
    lines.append("## Critical: Wiring Mismatches")
    if mismatches:
        lines.append("| Route Path | toolName in Route | Closest Registration | Distance | Auto-Fixed? |")
        lines.append("|------------|-------------------|---------------------|----------|-------------|")
        for m in mismatches:
            routes = ", ".join(m.get("routes", []))
            closest = m.get("closest_match") or "—"
            dist = m.get("distance") if m.get("distance") is not None else "—"
            fixed = "Yes" if m.get("auto_fixed") else "No"
            lines.append(f"| {routes} | {m['tool_name']} | {closest} | {dist} | {fixed} |")
    else:
        lines.append("None found.")
    lines.append("")

    # Runtime failures
    lines.append("## Runtime Failures")
    if failures:
        lines.append("| Tool Name | Error Type | Error Message | Status |")
        lines.append("|-----------|-----------|---------------|--------|")
        for f in failures:
            lines.append(
                f"| {f.get('tool_name', '?')} | {f.get('error_type', '?')} | {f.get('error_message', '?')[:80]} | {f.get('status', '?')} |"
            )
    else:
        lines.append("None found.")
    lines.append("")

    # Fallback masked
    lines.append("## Fallback-Masked")
    if fallback_masked:
        lines.append("| Tool Name | Reason | Error |")
        lines.append("|-----------|--------|-------|")
        for f in fallback_masked:
            lines.append(
                f"| {f.get('tool_name', '?')} | {f.get('reason', '?')} | {f.get('error_message', '')[:80]} |"
            )
    else:
        lines.append("None found.")
    lines.append("")

    # Healthy
    lines.append("## Healthy")
    if healthy:
        tool_list = ", ".join(h["tool_name"] for h in healthy[:20])
        lines.append(f"{len(healthy)} tools healthy: {tool_list}")
        if len(healthy) > 20:
            lines.append(f"... and {len(healthy) - 20} more")
    else:
        lines.append("No tools probed.")
    lines.append("")

    # Orphans
    lines.append("## Orphan Tools")
    if orphans:
        lines.append("| Tool Name | File |")
        lines.append("|-----------|------|")
        for o in orphans:
            lines.append(f"| {o['tool_name']} | {o['file']} |")
    else:
        lines.append("None found.")

    return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd ~/Projects/Augur && python -m pytest .claude/skills/auto-mcp-health-audit/augur/tests/test_mcp_health_audit.py::test_generate_report_markdown -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/auto-mcp-health-audit/scripts/mcp_health_audit.py .claude/skills/auto-mcp-health-audit/augur/tests/test_mcp_health_audit.py
git commit -m "feat(auto-mcp-health-audit): Phase 4 — report generation"
```

---

### Task 8: OpsCommand protocol — scan() and fix()

**Files:**
- Modify: `.claude/skills/auto-mcp-health-audit/augur/tests/test_mcp_health_audit.py`
- Modify: `.claude/skills/auto-mcp-health-audit/scripts/mcp_health_audit.py`

- [ ] **Step 1: Write failing tests**

Append to test file:

```python
# ── OpsCommand protocol: scan() and fix() ──


def test_scan_d0_static_only(tmp_path: Path) -> None:
    """d0 scan does static wiring only, returns ScanResult."""
    routes_dir = tmp_path / "apps" / "dashboard" / "app" / "api" / "[...proxy]"
    _write(
        routes_dir / "_routes-a.ts",
        'export const ROUTES_A = { "x/y": { GET: { toolName: "real-tool" } } };',
    )
    mcp_dir = tmp_path / "src" / "mcp" / "augur_mcp" / "core"
    _write(
        mcp_dir / "tools.py",
        '@mcp.tool(name="real-tool")\nasync def f(): pass',
    )

    result = mod.scan(_ctx(tmp_path, difficulty=0))

    assert isinstance(result, ScanResult)
    assert result.health in ("verified", "degraded", "broken")


def test_scan_d0_finds_mismatch(tmp_path: Path) -> None:
    """d0 scan reports wiring mismatches as issues."""
    routes_dir = tmp_path / "apps" / "dashboard" / "app" / "api" / "[...proxy]"
    _write(
        routes_dir / "_routes-a.ts",
        'export const ROUTES_A = { "x/y": { GET: { toolName: "missing-tool" } } };',
    )
    # No MCP registrations at all

    result = mod.scan(_ctx(tmp_path, difficulty=0))

    assert result.health == "broken"
    assert len(result.issues) >= 1
    assert any(i["category"] == "wiring-mismatch" for i in result.issues)


def test_fix_returns_fix_result(tmp_path: Path) -> None:
    """fix() returns a FixResult."""
    issues = [
        make_issue(
            category="wiring-mismatch",
            detail="missing-tool not registered",
            path="apps/dashboard/app/api/[...proxy]/_routes-a.ts",
            kind="actionable",
        )
    ]

    result = mod.fix(_ctx(tmp_path, difficulty=2), issues)

    assert isinstance(result, FixResult)


def test_module_has_name_and_difficulty_spec() -> None:
    """Module exports name and DIFFICULTY_SPEC per OpsCommand protocol."""
    assert hasattr(mod, "name")
    assert mod.name == "auto-mcp-health-audit"
    assert hasattr(mod, "DIFFICULTY_SPEC")
    assert 0 in mod.DIFFICULTY_SPEC
    assert 4 in mod.DIFFICULTY_SPEC
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/Projects/Augur && python -m pytest .claude/skills/auto-mcp-health-audit/augur/tests/test_mcp_health_audit.py -k "test_scan or test_fix_returns or test_module_has" -v
```

Expected: FAIL — `scan` and `fix` don't exist yet.

- [ ] **Step 3: Write implementation**

Add to `mcp_health_audit.py`:

```python
def scan(ctx: OpsContext) -> ScanResult:
    """Run MCP health audit scan at the given difficulty level.

    d0: Static wiring cross-reference only
    d1: + Runtime probe via HTTP
    d2+: Same as d1 (fixes happen in fix())
    """
    project_root = ctx.project_root
    difficulty = ctx.difficulty
    issues: list[dict] = []

    # ── Phase 1: Static wiring audit (always) ──
    route_tools = extract_route_tool_names(project_root)
    mcp_tools = extract_mcp_registrations(project_root)
    xref = cross_reference(route_tools, mcp_tools)

    route_count = sum(len(v) for v in route_tools.values())
    registered_count = len(mcp_tools)

    # Report mismatches as issues
    for m in xref["mismatches"]:
        detail = f'{m["tool_name"]} referenced in routes [{", ".join(m["routes"])}] but not registered'
        if m.get("closest_match"):
            detail += f' (closest: {m["closest_match"]}, distance: {m["distance"]})'
        issues.append(
            make_issue(
                category="wiring-mismatch",
                detail=detail,
                path=", ".join(m["routes"]),
                kind="actionable",
                root_cause_type="repo_bug",
                fixability="auto" if m.get("closest_match") else "manual",
                closest_match=m.get("closest_match"),
                distance=m.get("distance"),
                wrong_name=m["tool_name"],
            )
        )

    # Orphans are informational
    for o in xref["orphans"]:
        issues.append(
            make_issue(
                category="orphan-tool",
                detail=f'{o["tool_name"]} registered in {o["file"]} but no route references it',
                path=o["file"],
                kind="maintenance",
            )
        )

    # Store audit data for report generation
    audit_data: dict = {
        "phase1": {
            "route_count": route_count,
            "registered_count": registered_count,
            "mismatches": xref["mismatches"],
            "wired": xref["wired"],
            "orphans": xref["orphans"],
        },
        "phase2": {"healthy": [], "failures": [], "fallback_masked": []},
        "phase3": {"applied": 0, "skipped": 0, "changes": []},
    }

    # ── Phase 2: Runtime probe (d >= 1) ──
    if difficulty >= 1 and xref["wired"]:
        probe_results = probe_all_tools(xref["wired"])

        for pr in probe_results:
            status = pr.get("status", "unknown")
            if status == "healthy":
                audit_data["phase2"]["healthy"].append(pr)
            elif status == "fallback-masked":
                audit_data["phase2"]["fallback_masked"].append(pr)
                issues.append(
                    make_issue(
                        category="fallback-masked",
                        detail=f'{pr["tool_name"]} returns fallback data: {pr.get("reason", "unknown")}',
                        kind="actionable",
                        root_cause_type="env_runtime",
                        error_message=pr.get("error_message", ""),
                    )
                )
            elif status == "needs-args":
                audit_data["phase2"].setdefault("needs_args", []).append(pr)
            elif status == "connection-error":
                issues.append(
                    make_issue(
                        category="server-down",
                        detail=f'MCP server unreachable: {pr.get("error_message", "")}',
                        kind="environment",
                    )
                )
                break
            elif status != "healthy":
                audit_data["phase2"]["failures"].append(pr)
                error_type = pr.get("error_type", fingerprint_error(pr.get("error_message", "")))
                fixability = "auto" if error_type == "missing-file" else "manual"
                issues.append(
                    make_issue(
                        category="runtime-failure",
                        detail=f'{pr["tool_name"]}: {pr.get("error_message", "unknown error")}',
                        kind="actionable",
                        root_cause_type="env_runtime",
                        fixability=fixability,
                        error_type=error_type,
                        tool_name=pr["tool_name"],
                    )
                )

    # ── Phase 4: Report (always) ──
    report_md = generate_report(audit_data)
    # JSON for machine consumption (ops_protocol pattern)
    write_report(ctx, "mcp-health-report.json", audit_data)
    # Markdown for human readability (spec requirement)
    from src.config.paths import get_runtime_dir
    report_dir = get_runtime_dir() / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "mcp-health-report.md").write_text(report_md)

    # Evolution gaps
    if not issues and difficulty >= 2:
        needs_args_count = len(audit_data["phase2"].get("needs_args", []))
        gap_detail = f"{len(xref['wired'])} tools wired and healthy."
        if needs_args_count:
            gap_detail += f" {needs_args_count} tools skipped (need args)."
        gap_detail += " Next: validate transformResponse field names match MCP output keys (d3)."
        issues.append(evolution_gap(gap_detail, category="evolution"))

    # Determine health
    mismatch_count = len([i for i in issues if i.get("category") == "wiring-mismatch"])
    failure_count = len([i for i in issues if i.get("category") in ("runtime-failure", "fallback-masked")])

    if mismatch_count > 0 or failure_count > 5:
        health = "broken"
        severity = "error"
    elif failure_count > 0:
        health = "degraded"
        severity = "warning"
    else:
        health = "verified"
        severity = "info"

    summary = (
        f"Routes: {route_count}, Registered: {registered_count}, "
        f"Mismatches: {mismatch_count}, "
        f"Runtime failures: {failure_count}, "
        f"Healthy: {len(audit_data['phase2']['healthy'])}"
    )

    return ScanResult(
        issues=issues,
        summary=summary,
        severity=severity,
        health=health,
        items_scanned=route_count,
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Apply safe fixes for issues found by scan().

    Only applies fixes at difficulty >= 2.
    """
    if ctx.difficulty < 2:
        return FixResult(
            success=True,
            actions=[],
            changes=[],
            summary="Auto-fix requires difficulty >= 2",
            fix_type="report",
        )

    fixable: list[dict] = []
    for issue in issues:
        cat = issue.get("category", "")

        if cat == "wiring-mismatch" and issue.get("closest_match"):
            # Count affected route files (max 3 per safety rule)
            proxy_dir = ctx.project_root / _PROXY_DIR
            affected = [f.name for f in proxy_dir.glob("_routes-*.ts")]
            fixable.append({
                "fix_type": "toolname-typo",
                "wrong_name": issue["wrong_name"],
                "correct_name": issue["closest_match"],
                "affected_files": affected,
            })

        elif cat == "runtime-failure" and issue.get("error_type") == "missing-file":
            # Extract dir path from error message
            error_msg = issue.get("detail", "")
            # Best-effort: look for path-like strings
            # In practice, the error message contains the missing path
            fixable.append({
                "fix_type": "missing-dir",
                "dir_path": "",  # Will need error message parsing
                "affected_files": [],
            })

    result = apply_safe_fixes(ctx.project_root, fixable)

    return FixResult(
        success=True,
        actions=[],
        changes=result.get("changes", []),
        summary=f"Applied {result.get('applied', 0)} fixes, skipped {result.get('skipped', 0)}",
        fix_type="code-fix" if result.get("applied", 0) > 0 else "report",
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd ~/Projects/Augur && python -m pytest .claude/skills/auto-mcp-health-audit/augur/tests/test_mcp_health_audit.py -v
```

Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/auto-mcp-health-audit/scripts/mcp_health_audit.py .claude/skills/auto-mcp-health-audit/augur/tests/test_mcp_health_audit.py
git commit -m "feat(auto-mcp-health-audit): OpsCommand protocol — scan() and fix() integration"
```

---

### Task 9: Integration test — run against real codebase

**Files:**
- No new files — runs the existing script against the real project

- [ ] **Step 1: Run d0 scan against real codebase**

```bash
cd ~/Projects/Augur && python -c "
from pathlib import Path
from src.lib.ops_protocol import OpsContext
import importlib.util

spec = importlib.util.spec_from_file_location('mod', '.claude/skills/auto-mcp-health-audit/scripts/mcp_health_audit.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

ctx = OpsContext(project_root=Path('.').resolve(), difficulty=0)
result = mod.scan(ctx)
print(f'Health: {result.health}')
print(f'Summary: {result.summary}')
print(f'Issues: {len(result.issues)}')
for i in result.issues[:10]:
    print(f'  [{i[\"category\"]}] {i[\"detail\"][:100]}')
"
```

Expected: Runs successfully. Review output — mismatches indicate real wiring problems to fix.

- [ ] **Step 2: Review output and fix any script bugs**

If the script crashes or produces unexpected output, debug and fix. Common issues:
- Regex not matching real route file format
- Path resolution issues
- Missing imports

- [ ] **Step 3: Run full test suite**

```bash
cd ~/Projects/Augur && python -m pytest .claude/skills/auto-mcp-health-audit/augur/tests/test_mcp_health_audit.py -v
```

Expected: ALL PASS

- [ ] **Step 4: Commit any fixes**

```bash
git add .claude/skills/auto-mcp-health-audit/
git commit -m "fix(auto-mcp-health-audit): integration fixes from real codebase run"
```

---

### Task 10: One-time sweep execution

**Files:**
- No new files — runs the audit and applies fixes

- [ ] **Step 1: Run d1 scan (static + runtime) if dashboard is running**

```bash
cd ~/Projects/Augur && python -c "
from pathlib import Path
from src.lib.ops_protocol import OpsContext
import importlib.util

spec = importlib.util.spec_from_file_location('mod', '.claude/skills/auto-mcp-health-audit/scripts/mcp_health_audit.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

ctx = OpsContext(project_root=Path('.').resolve(), difficulty=1)
result = mod.scan(ctx)
print(f'Health: {result.health}')
print(f'Summary: {result.summary}')
for i in result.issues:
    print(f'  [{i[\"category\"]}] {i[\"detail\"][:120]}')
"
```

- [ ] **Step 2: Review the report**

Check `~/Library/Application Support/Augur/state/reports/mcp-health-report.json` for the full report.

- [ ] **Step 3: Run d2 to apply safe fixes**

Only after reviewing the d1 report:

```bash
cd ~/Projects/Augur && python -c "
from pathlib import Path
from src.lib.ops_protocol import OpsContext
import importlib.util

spec = importlib.util.spec_from_file_location('mod', '.claude/skills/auto-mcp-health-audit/scripts/mcp_health_audit.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

ctx = OpsContext(project_root=Path('.').resolve(), difficulty=2)
result = mod.scan(ctx)
print(f'Summary: {result.summary}')

fixable = [i for i in result.issues if i.get('fixability') == 'auto']
if fixable:
    fix_result = mod.fix(ctx, fixable)
    print(f'Fix: {fix_result.summary}')
    for c in fix_result.changes:
        print(f'  Changed: {c}')
else:
    print('No auto-fixable issues found.')
"
```

- [ ] **Step 4: Review auto-fixed changes and commit**

```bash
git diff  # Review changes
git add -p  # Stage selectively
git commit -m "fix(mcp-wiring): auto-fix toolName mismatches from health audit"
```
