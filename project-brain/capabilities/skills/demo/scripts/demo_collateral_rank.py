from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.config.paths import get_vault_dir
from src.lib.frontmatter_utils import parse_frontmatter


REQUIRED_SECTIONS = (
    "## Bottom Line",
    "## Live Proof",
    "## What To Show",
    "## Investor Takeaway",
    "## Verification Snapshot",
)

LEAK_PATTERNS = (
    "/Users/",
    "Candidate wiki file:",
    "Source synthesis:",
    "Retained cluster:",
    "Open source synthesis:",
    "Open candidate wiki page:",
    "Traceback",
    "raw JSON",
    "metadata dump",
    "missing path",
)

DEMO_TERMS: dict[str, tuple[str, ...]] = {
    "demo_01_wiki_llm_cross_agent_ask": (
        "retained",
        "Wiki Ingest And Compilation Commands",
        "Codex",
        "Claude",
        "Status:",
    ),
    "demo_02_discover_gui_web_capture": (
        "command",
        "IANA-managed Reserved Domains",
        "webpage",
        "Browse",
        "Status:",
    ),
    "demo_03_offload_transcription_airplane": (
        "transcript",
        "offline",
        "Gemini",
        "faster-whisper",
        "Status:",
    ),
    "demo_04_compound_dry_run": (
        "dry run",
        "retained",
        "wiki",
        "mutated",
        "Status:",
    ),
    "demo_05_airplane_safety_evidence": (
        "Cloud calls: 0",
        "local",
        "OpenVINO",
        "faster-whisper",
        "Status:",
    ),
    "demo_06_brain_manifest_architecture": (
        "BRAIN.yaml",
        "capabilities/skills",
        "personal brain",
        "project brain",
        "Status:",
    ),
}


def _contains(text: str, term: str) -> bool:
    return term.casefold() in text.casefold()


def _score_metadata(metadata: dict[str, Any], failures: list[str]) -> int:
    score = 0
    if metadata.get("type") == "workflow-example-artifact":
        score += 6
    else:
        failures.append("frontmatter type is not workflow-example-artifact")
    if str(metadata.get("demo_id") or "").startswith("demo_"):
        score += 4
    else:
        failures.append("frontmatter demo_id is missing")
    if str(metadata.get("title") or "").strip():
        score += 3
    else:
        failures.append("frontmatter title is missing")
    tags = metadata.get("tags")
    if isinstance(tags, list) and "example" in tags:
        score += 2
    else:
        failures.append("frontmatter tags do not include example")
    return score


def _score_structure(body: str, failures: list[str]) -> int:
    score = 5 if body.lstrip().startswith("# ") else 0
    if score == 0:
        failures.append("artifact has no visible H1")
    for section in REQUIRED_SECTIONS:
        if section in body:
            score += 4
        else:
            failures.append(f"missing section: {section.removeprefix('## ')}")
    return score


def _score_demo_terms(demo_id: str, body: str, failures: list[str]) -> int:
    terms = DEMO_TERMS.get(demo_id, ())
    if not terms:
        failures.append(f"no rank rubric terms for {demo_id or 'unknown workflow example'}")
        return 0

    score = 0
    for term in terms:
        if _contains(body, term):
            score += 5
        else:
            failures.append(f"missing workflow example evidence term: {term}")
    return score


def _score_readability(body: str, failures: list[str]) -> int:
    leaks = [pattern for pattern in LEAK_PATTERNS if pattern in body]
    if leaks:
        failures.append(f"implementation leakage in visible body: {', '.join(leaks)}")
        return 0
    if len(body.split()) < 90:
        failures.append("artifact body is too thin for judge-facing collateral")
        return 10
    return 20


def _score_actionability(body: str, failures: list[str]) -> int:
    score = 0
    if "Search Browse for:" in body or "Open in Browse:" in body:
        score += 5
    else:
        failures.append("missing Browse search/open instruction")
    if "## What To Show" in body:
        score += 5
    if "Status: pass" in body or "Status: partial-pass" in body:
        score += 5
    else:
        failures.append("missing final status snapshot")
    return score


def score_demo_collateral_path(path: Path | str) -> dict[str, Any]:
    artifact_path = Path(path)
    failures: list[str] = []
    if not artifact_path.exists():
        return {
            "path": str(artifact_path),
            "score": 0,
            "status": "fail",
            "failures": ["artifact does not exist"],
        }

    metadata, body = parse_frontmatter(artifact_path, include_sidecar_config=False)
    demo_id = str(metadata.get("demo_id") or "")
    score = (
        _score_metadata(metadata, failures)
        + _score_structure(body, failures)
        + _score_demo_terms(demo_id, body, failures)
        + _score_readability(body, failures)
        + _score_actionability(body, failures)
    )
    return {
        "path": str(artifact_path),
        "demo_id": demo_id,
        "title": metadata.get("title"),
        "score": score,
        "status": "pass" if score >= 90 and not failures else "fail",
        "failures": failures,
    }


def score_demo_collateral_dir(directory: Path | str | None = None) -> dict[str, Any]:
    root = Path(directory) if directory is not None else get_vault_dir() / "notes" / "examples" / "artifacts"
    cards = sorted(root.glob("demo-*.md")) if root.exists() else []
    results = [score_demo_collateral_path(card) for card in cards]
    return {
        "success": bool(results) and all(result["score"] >= 90 for result in results),
        "directory": str(root),
        "count": len(results),
        "results": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rank judge-facing workflow example collateral cards.")
    parser.add_argument(
        "--directory",
        default="",
        help="Directory containing demo-*.md collateral cards. Defaults to the Augur vault workflow examples artifact folder.",
    )
    parser.add_argument("--min-score", type=int, default=90)
    args = parser.parse_args(argv)

    payload = score_demo_collateral_dir(args.directory or None)
    payload["min_score"] = args.min_score
    payload["success"] = bool(payload["results"]) and all(
        result["score"] >= args.min_score for result in payload["results"]
    )
    print(json.dumps(payload, indent=2, default=str))
    return 0 if payload["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
