"""Skill quality scorer used by adaptive loops and Browse enrichment.

This is intentionally a plain library module. The retired `skill-score` MCP
tool used to host the scorer inside the MCP server package, but local adaptive
loops still need the scoring function without importing FastMCP.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from src.config.paths import get_project_brain_skills_dir, get_project_root
from src.lib.frontmatter_utils import parse_frontmatter

_cache: dict[str, Any] = {}
_cache_ts = 0.0
_CACHE_TTL = 60.0

DEFAULT_WEIGHTS = {
    "instruction": 0.30,
    "product": 0.40,
    "ui": 0.15,
    "wiring": 0.15,
}
DEFAULT_THRESHOLDS = {
    "structural": {"B": 55, "C": 35, "D": 15},
    "behavioral": {
        "S": {"structural_min": 75, "pass_rate": 0.80, "confidence": "verified"},
        "A": {"structural_min": 65, "pass_rate": 0.60},
        "B+": {"pass_rate": 0.0},
    },
}

RUBRICS = {
    "domain-high": {"weights": {"instruction": 0.25, "product": 0.35, "ui": 0.20, "wiring": 0.20}},
    "domain-low": {"weights": {"instruction": 0.35, "product": 0.40, "ui": 0.05, "wiring": 0.20}},
    "command": {"weights": {"instruction": 0.50, "product": 0.25, "ui": 0.0, "wiring": 0.25}},
    "autoloop": {"weights": {"instruction": 0.20, "product": 0.30, "ui": 0.05, "wiring": 0.45}},
    "library-reference": {"weights": {"instruction": 0.60, "product": 0.20, "ui": 0.0, "wiring": 0.20}},
    "runbook": {"weights": {"instruction": 0.55, "product": 0.25, "ui": 0.0, "wiring": 0.20}},
    "template": {"weights": {"instruction": 0.40, "product": 0.35, "ui": 0.10, "wiring": 0.15}},
    "meta": {"weights": {"instruction": 0.50, "product": 0.30, "ui": 0.0, "wiring": 0.20}},
    "integration": {"weights": {"instruction": 0.35, "product": 0.35, "ui": 0.10, "wiring": 0.20}},
}


def _get_weights_config_path() -> Path:
    return (
        get_project_brain_skills_dir(get_project_root())
        / "auto-skill-quality"
        / "assets"
        / "seeds"
        / "skill-score-weights.yaml"
    )


def _load_weights() -> tuple[dict[str, float], dict[str, Any]]:
    config_path = _get_weights_config_path()
    if config_path.exists():
        try:
            import yaml

            cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            weights = cfg.get("weights", DEFAULT_WEIGHTS)
            thresholds = cfg.get("tier_thresholds", DEFAULT_THRESHOLDS)
            total = sum(weights.values())
            if abs(total - 1.0) > 0.01:
                weights = DEFAULT_WEIGHTS
            return dict(weights), thresholds
        except Exception:
            pass
    return DEFAULT_WEIGHTS.copy(), DEFAULT_THRESHOLDS.copy()


def _resolve_rubric(fm: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    skill_type = fm.get("x-augur-type", "domain")
    if skill_type == "domain":
        tools = len(fm.get("x-augur-mcp-tools", []))
        pages = len(fm.get("x-augur-dashboard-pages", []))
        name = "domain-high" if tools >= 8 or pages >= 3 else "domain-low"
    else:
        name = str(skill_type)
    if name not in RUBRICS:
        name = "domain-low"
    return name, RUBRICS[name]


def _read_behavioral(evals_dir: Path) -> dict[str, Any] | None:
    benchmark_file = evals_dir / "benchmark.json"
    evals_file = evals_dir / "evals.json"
    if not benchmark_file.exists():
        return None
    try:
        bm = json.loads(benchmark_file.read_text(encoding="utf-8"))
        summary = bm.get("run_summary", {}).get("with_skill", {})
        pass_rate = summary.get("pass_rate", {})
        mean_pass = pass_rate.get("mean", 0.0) if isinstance(pass_rate, dict) else pass_rate
        confidence = "seed"
        if evals_file.exists():
            evals_data = json.loads(evals_file.read_text(encoding="utf-8"))
            evals_list = evals_data.get("evals", [])
            if evals_list and all(item.get("confidence") == "verified" for item in evals_list):
                confidence = "verified"
        return {
            "confidence": confidence,
            "pass_rate": mean_pass,
            "eval_count": len(bm.get("runs", [])),
            "last_run": bm.get("metadata", {}).get("timestamp"),
        }
    except (json.JSONDecodeError, OSError, KeyError):
        return None


def _compute_tier(structural_score: float, evals_dir: Path, thresholds: dict[str, Any] | None = None) -> dict[str, Any]:
    t = thresholds or DEFAULT_THRESHOLDS
    structural = t.get("structural", DEFAULT_THRESHOLDS["structural"])
    behavioral_thresholds = t.get("behavioral", DEFAULT_THRESHOLDS["behavioral"])

    if structural_score >= structural.get("B", 55):
        base_tier = "B"
    elif structural_score >= structural.get("C", 35):
        base_tier = "C"
    elif structural_score >= structural.get("D", 15):
        base_tier = "D"
    else:
        base_tier = "F"

    behavioral = _read_behavioral(evals_dir)
    if behavioral is None or base_tier != "B":
        return {"tier": base_tier, "behavioral": behavioral}

    s_gate = behavioral_thresholds.get("S", {})
    a_gate = behavioral_thresholds.get("A", {})
    if (
        behavioral["confidence"] == s_gate.get("confidence", "verified")
        and behavioral["pass_rate"] >= s_gate.get("pass_rate", 0.80)
        and structural_score >= s_gate.get("structural_min", 75)
    ):
        return {"tier": "S", "behavioral": behavioral}
    if behavioral["pass_rate"] >= a_gate.get("pass_rate", 0.60) and structural_score >= a_gate.get(
        "structural_min", 65
    ):
        return {"tier": "A", "behavioral": behavioral}
    if behavioral["eval_count"] > 0:
        return {"tier": "B+", "behavioral": behavioral}
    return {"tier": "B", "behavioral": behavioral}


def _score_instruction(fm: dict[str, Any], body: str) -> dict[str, Any]:
    desc = fm.get("description", "") or ""
    desc_words = len(desc.split()) if desc.strip() else 0
    lines = body.strip().split("\n") if body.strip() else []
    body_lines = len(lines)
    sections = len(re.findall(r"^#{1,3}\s+", body, re.MULTILINE))

    desc_score = (
        25 if desc_words >= 20 else 15 if desc_words >= 10 else 8 if desc_words >= 5 else 3 if desc_words else 0
    )
    body_score = (
        30 if body_lines >= 100 else 22 if body_lines >= 50 else 15 if body_lines >= 20 else 5 if body_lines >= 5 else 0
    )
    section_score = 20 if sections >= 5 else 14 if sections >= 3 else 8 if sections >= 1 else 0

    has_examples = bool(re.search(r"(?i)(example|```)", body))
    has_references = bool(re.search(r"(?i)(references?/|scripts?/|assets?/)", body))
    has_workflow = bool(re.search(r"(?i)(workflow|step-by-step|procedure|process)", body))
    has_checklist = bool(re.search(r"(?i)(\[ \]|\[x\]|step \d|phase \d)", body))
    has_compat = "compatibility" in fm or "tools" in fm or "x-augur-tools" in str(fm)

    richness = sum(
        [
            8 if has_examples else 0,
            5 if has_references else 0,
            5 if has_workflow else 0,
            4 if has_checklist else 0,
            3 if has_compat else 0,
        ]
    )

    return {
        "score": min(100, desc_score + body_score + section_score + richness),
        "signals": {
            "desc_words": desc_words,
            "body_lines": body_lines,
            "sections": sections,
            "has_examples": has_examples,
            "has_references": has_references,
            "has_workflow": has_workflow,
            "has_checklist": has_checklist,
        },
    }


def _score_product(skill_dir: Path) -> dict[str, Any]:
    root = get_project_root()
    skill_name = skill_dir.name
    has_data = (skill_dir / "data").is_dir()
    has_scripts = (skill_dir / "scripts").is_dir()
    has_references = (skill_dir / "references").is_dir()
    has_actions = (
        any(
            path.suffix in {".yaml", ".yml", ".md"} and "action" in path.name.lower()
            for path in (skill_dir / "augur").rglob("*")
        )
        if (skill_dir / "augur").exists()
        else False
    )

    has_mcp = False
    mcp_dir = root / "src" / "mcp"
    if mcp_dir.exists():
        for py_file in mcp_dir.rglob("*.py"):
            try:
                content = py_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if f'name="{skill_name}' in content or f"name='{skill_name}" in content:
                has_mcp = True
                break

    has_api = False
    api_dir = root / "apps" / "dashboard" / "app" / "api"
    if api_dir.exists():
        for ts_file in api_dir.rglob("*.ts"):
            try:
                if skill_name in ts_file.read_text(encoding="utf-8", errors="replace"):
                    has_api = True
                    break
            except OSError:
                continue

    score = (
        (20 if has_data else 0)
        + (25 if has_mcp else 0)
        + (20 if has_api else 0)
        + (15 if has_actions else 0)
        + (10 if has_scripts else 0)
        + (10 if has_references else 0)
    )
    return {
        "score": min(100, score),
        "signals": {
            "has_data_dir": has_data,
            "has_mcp_tools": has_mcp,
            "has_api_routes": has_api,
            "has_actions": has_actions,
            "has_scripts": has_scripts,
            "has_references": has_references,
        },
    }


def _score_ui(fm: dict[str, Any]) -> dict[str, Any]:
    config = fm.get("x-augur-config") or {}
    pages = (config.get("contributions") or {}).get("pages") or []
    page_list = [page for page in pages if isinstance(page, dict)]
    if not page_list:
        return {"score": 0, "signals": {"page_count": 0, "mature_pages": 0, "custom_pages": 0, "page_states": []}}
    states = [page.get("state", "dev") for page in page_list]
    page_types = [page.get("page_type", "auto") for page in page_list]
    custom_count = sum(1 for page_type in page_types if page_type == "custom")
    mature_count = sum(1 for state in states if state == "mature")
    score = min(30, len(page_list) * 5)
    score += 40 if mature_count else 20 if all(state != "mock" for state in states) else 0
    score += 15 if custom_count else 0
    score += 15 if any(state != "mock" for state in states) else 0
    return {
        "score": min(100, score),
        "signals": {
            "page_count": len(page_list),
            "mature_pages": mature_count,
            "custom_pages": custom_count,
            "page_states": states,
        },
    }


def _score_wiring(skill_dir: Path) -> dict[str, Any]:
    root = get_project_root()
    skill_name = skill_dir.name
    has_api_route = False
    no_fs_bypasses = True
    has_mcp_tool = False
    no_fallback_masking = True

    api_dir = root / "apps" / "dashboard" / "app" / "api"
    if api_dir.exists():
        for ts_file in api_dir.rglob("*.ts"):
            try:
                content = ts_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if skill_name in content:
                has_api_route = True
                if re.search(r"import\s+.*\bfs\b|require\s*\(\s*['\"]fs['\"]|spawn|execSync|execFile", content):
                    no_fs_bypasses = False
                if re.search(r"gracefulFallback\s*:\s*\{\s*data\s*:\s*\{\s*\}", content):
                    no_fallback_masking = False

    mcp_dir = root / "src" / "mcp"
    if mcp_dir.exists():
        for py_file in mcp_dir.rglob("*.py"):
            try:
                content = py_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if re.search(rf'@mcp\.tool\(\s*name\s*=\s*["\'].*{re.escape(skill_name)}', content):
                has_mcp_tool = True
                break

    score = (
        (30 if has_api_route else 0)
        + (25 if no_fs_bypasses else 0)
        + (25 if has_mcp_tool else 0)
        + (20 if no_fallback_masking else 0)
    )
    return {
        "score": min(100, score),
        "signals": {
            "has_api_route": has_api_route,
            "no_fs_bypasses": no_fs_bypasses,
            "has_mcp_tool": has_mcp_tool,
            "no_fallback_masking": no_fallback_masking,
        },
    }


def score_all_skills(skill_name: str | None = None, hub: str | None = None) -> dict[str, Any]:
    global _cache, _cache_ts

    config_path = _get_weights_config_path()
    config_mtime = config_path.stat().st_mtime if config_path.exists() else 0
    if (
        skill_name is None
        and _cache
        and time.time() - _cache_ts < _CACHE_TTL
        and _cache.get("_config_mtime") == config_mtime
    ):
        output = _cache
        if hub:
            return {**output, "skills": [skill for skill in output["skills"] if skill["hub"] == hub]}
        return output

    weights, thresholds = _load_weights()
    results: list[dict[str, Any]] = []
    for skill_md in sorted(get_project_brain_skills_dir(get_project_root()).glob("*/SKILL.md")):
        skill_dir = skill_md.parent
        if skill_name and skill_dir.name != skill_name:
            continue
        try:
            fm, body = parse_frontmatter(skill_md)
        except Exception:
            fm, body = {}, ""

        instruction = _score_instruction(fm, body)
        product = _score_product(skill_dir)
        ui = _score_ui(fm)
        wiring = _score_wiring(skill_dir)
        rubric_name, rubric = _resolve_rubric(fm)
        skill_weights = rubric["weights"]
        composite = round(
            instruction["score"] * skill_weights["instruction"]
            + product["score"] * skill_weights["product"]
            + ui["score"] * skill_weights["ui"]
            + wiring["score"] * skill_weights["wiring"],
            1,
        )
        tier_result = _compute_tier(composite, skill_dir / "evals", thresholds)

        skill_hub = (fm.get("x-augur-config") or {}).get("hub", "system")
        if isinstance(skill_hub, dict):
            skill_hub = skill_hub.get("id", "system")
        elif isinstance(skill_hub, list):
            skill_hub = skill_hub[0] if skill_hub else "system"

        results.append(
            {
                "name": skill_dir.name,
                "hub": skill_hub,
                "score": composite,
                "tier": tier_result["tier"],
                "behavioral": tier_result["behavioral"],
                "rubric": rubric_name,
                "dimensions": {
                    "instruction": {
                        **instruction,
                        "weight": skill_weights["instruction"],
                        "weighted": round(instruction["score"] * skill_weights["instruction"], 1),
                    },
                    "product": {
                        **product,
                        "weight": skill_weights["product"],
                        "weighted": round(product["score"] * skill_weights["product"], 1),
                    },
                    "ui": {
                        **ui,
                        "weight": skill_weights["ui"],
                        "weighted": round(ui["score"] * skill_weights["ui"], 1),
                    },
                    "wiring": {
                        **wiring,
                        "weight": skill_weights["wiring"],
                        "weighted": round(wiring["score"] * skill_weights["wiring"], 1),
                    },
                },
            }
        )

    results.sort(key=lambda item: -item["score"])
    tier_dist: dict[str, int] = {}
    for result in results:
        tier_dist[result["tier"]] = tier_dist.get(result["tier"], 0) + 1
    avg = round(sum(result["score"] for result in results) / max(len(results), 1), 1)
    output = {
        "skills": results,
        "summary": {
            "total": len(results),
            "tier_distribution": tier_dist,
            "average_score": avg,
        },
        "weights": weights,
        "thresholds": thresholds,
        "_config_mtime": config_mtime,
    }
    if skill_name is None:
        _cache = output
        _cache_ts = time.time()
    if hub:
        return {**output, "skills": [skill for skill in output["skills"] if skill["hub"] == hub]}
    return output
