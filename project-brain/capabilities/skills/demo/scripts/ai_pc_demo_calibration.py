from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_project_root = Path(__file__).resolve().parents[3]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from src.lib.extraction import extract, get_extraction_policy


def score_file(path: Path) -> dict[str, Any]:
    policy = get_extraction_policy()
    result = extract(str(path), max_tier=1)
    text = result.markdown.strip() if result.success else ""
    score = 0
    if text:
        score += 1
    if any(char.isdigit() for char in text):
        score += 1
    if len(text.split()) >= 4:
        score += 1
    return {
        "path": str(path),
        "success": result.success,
        "method": f"document-extractor:{result.tier_used}",
        "ocr_applied": result.ocr_applied,
        "needs_llm": result.needs_llm,
        "cloud_allowed": bool(policy["cloud_escalation_allowed"]),
        "text_present": bool(text),
        "score": score,
    }


def score_folder(path: Path) -> dict[str, Any]:
    files = [item for item in sorted(path.iterdir()) if item.is_file()]
    results = [score_file(item) for item in files]
    return {
        "folder": str(path),
        "files": results,
        "average_score": (
            sum(item["score"] for item in results) / len(results) if results else 0.0
        ),
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    args = parser.parse_args(argv)
    target = Path(args.path)
    payload = score_folder(target) if target.is_dir() else score_file(target)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
