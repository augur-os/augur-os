#!/usr/bin/env python3
"""Pair `docs/superpowers/specs/*-design.md` and `docs/superpowers/plans/*.md`
files to ADR entries in `project-brain/decisions/adrs/adrs-index.json`.

Matching strategy:
 - Extract the date prefix and the topic keyword set from each spec/plan
   filename (e.g. ``2026-04-23-vault-owned-user-skills-and-pages-design.md``
   yields date 2026-04-23 + keywords {"vault", "owned", "user", "skills", ...}).
 - Compare every spec/plan against every ADR entry in the central index. A
   "strong match" requires (a) the spec/plan date is within ±14 days of the
   ADR's date and (b) at least 3 keywords overlap with the ADR title (or
   2 keywords if the ADR title is itself short).
 - On strong match: set the ADR's ``spec_file`` / ``plan_file`` field to
   the spec/plan basename. Don't move files.
 - Ambiguous matches (multiple ADR candidates with comparable strength) are
   reported but not applied.
 - Orphans (no candidate above the threshold) are reported.

Run:
    python3 scripts/pair_superpowers_to_adrs.py
    python3 scripts/pair_superpowers_to_adrs.py --apply  # write to JSON
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

ADR_INDEX = PROJECT_ROOT / "docs" / "adrs" / "adrs-index.json"
SPECS_DIR = PROJECT_ROOT / "docs" / "superpowers" / "specs"
PLANS_DIR = PROJECT_ROOT / "docs" / "superpowers" / "plans"

DATE_WINDOW_DAYS = 14
STRONG_THRESHOLD_KEYWORDS = 3
SHORT_TITLE_THRESHOLD = 2
SHORT_TITLE_WORDS = 4
STOP_WORDS = {
    "a", "an", "and", "or", "the", "of", "for", "to", "in", "on", "with",
    "from", "by", "as", "at", "is", "are", "be", "this", "that", "into",
    "via", "no", "not", "design", "plan", "spec",
}


def _extract_date(stem: str) -> date | None:
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", stem)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _keywords_from_basename(basename: str) -> set[str]:
    stem = Path(basename).stem
    # Strip the leading date prefix.
    stem = re.sub(r"^\d{4}-\d{2}-\d{2}-?", "", stem)
    # Strip a trailing -design suffix (specs only).
    stem = re.sub(r"-design$", "", stem)
    tokens = re.split(r"[^a-z0-9]+", stem.lower())
    return {t for t in tokens if t and t not in STOP_WORDS and len(t) > 2}


def _keywords_from_title(title: str) -> set[str]:
    tokens = re.split(r"[^a-z0-9]+", (title or "").lower())
    return {t for t in tokens if t and t not in STOP_WORDS and len(t) > 2}


def _adr_date(adr: dict) -> date | None:
    raw = str(adr.get("date") or "")
    return _extract_date(raw)


def _word_count(title: str) -> int:
    return len(re.split(r"\s+", (title or "").strip()))


def _score(spec_keywords: set[str], adr_keywords: set[str]) -> int:
    return len(spec_keywords & adr_keywords)


def _classify(
    file_basename: str,
    file_date: date | None,
    file_keywords: set[str],
    adrs: list[dict],
) -> tuple[str, list[dict]]:
    """Return ('strong'|'ambiguous'|'orphan', candidates)."""
    candidates: list[tuple[int, dict]] = []
    for adr in adrs:
        adr_date = _adr_date(adr)
        if file_date and adr_date and abs((file_date - adr_date).days) > DATE_WINDOW_DAYS:
            continue
        adr_keywords = _keywords_from_title(adr.get("title", ""))
        score = _score(file_keywords, adr_keywords)
        if score == 0:
            continue
        # Bias: short ADR titles need fewer keywords to match.
        threshold = STRONG_THRESHOLD_KEYWORDS
        if _word_count(adr.get("title", "")) <= SHORT_TITLE_WORDS:
            threshold = SHORT_TITLE_THRESHOLD
        if score >= threshold:
            candidates.append((score, adr))

    candidates.sort(key=lambda pair: pair[0], reverse=True)
    if not candidates:
        return "orphan", []
    if len(candidates) == 1:
        return "strong", [candidates[0][1]]
    top_score = candidates[0][0]
    top_band = [adr for s, adr in candidates if s >= top_score]
    if len(top_band) == 1:
        return "strong", top_band
    return "ambiguous", top_band[:5]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Write spec_file/plan_file to ADR entries.")
    parser.add_argument("--max-report", type=int, default=15, help="How many entries to print per category.")
    args = parser.parse_args()

    if not ADR_INDEX.exists():
        print(f"Central index not found: {ADR_INDEX}", file=sys.stderr)
        return 1

    adrs: list[dict] = json.loads(ADR_INDEX.read_text(encoding="utf-8"))
    by_number: dict[str, dict] = {a["adr_number"]: a for a in adrs if a.get("adr_number")}

    spec_files = sorted(p for p in SPECS_DIR.glob("*-design.md"))
    plan_files = sorted(p for p in PLANS_DIR.glob("*.md"))
    print(f"specs: {len(spec_files)}; plans: {len(plan_files)}; ADRs: {len(adrs)}")

    strong_spec: list[tuple[str, str]] = []  # (file_basename, adr_number)
    ambiguous_spec: list[tuple[str, list[str]]] = []
    orphan_spec: list[str] = []
    strong_plan: list[tuple[str, str]] = []
    ambiguous_plan: list[tuple[str, list[str]]] = []
    orphan_plan: list[str] = []

    for spec_path in spec_files:
        spec_keys = _keywords_from_basename(spec_path.name)
        spec_date = _extract_date(spec_path.name)
        category, candidates = _classify(spec_path.name, spec_date, spec_keys, adrs)
        if category == "strong":
            strong_spec.append((spec_path.name, candidates[0]["adr_number"]))
        elif category == "ambiguous":
            ambiguous_spec.append((spec_path.name, [c["adr_number"] for c in candidates]))
        else:
            orphan_spec.append(spec_path.name)

    for plan_path in plan_files:
        plan_keys = _keywords_from_basename(plan_path.name)
        plan_date = _extract_date(plan_path.name)
        category, candidates = _classify(plan_path.name, plan_date, plan_keys, adrs)
        if category == "strong":
            strong_plan.append((plan_path.name, candidates[0]["adr_number"]))
        elif category == "ambiguous":
            ambiguous_plan.append((plan_path.name, [c["adr_number"] for c in candidates]))
        else:
            orphan_plan.append(plan_path.name)

    print()
    print("=" * 70)
    print(f"specs strong:    {len(strong_spec)}")
    print(f"specs ambiguous: {len(ambiguous_spec)}")
    print(f"specs orphan:    {len(orphan_spec)}")
    print(f"plans strong:    {len(strong_plan)}")
    print(f"plans ambiguous: {len(ambiguous_plan)}")
    print(f"plans orphan:    {len(orphan_plan)}")

    print()
    print("Sample strong specs:")
    for fname, num in strong_spec[: args.max_report]:
        print(f"  {num} -> {fname}")
    print("Sample strong plans:")
    for fname, num in strong_plan[: args.max_report]:
        print(f"  {num} -> {fname}")

    if ambiguous_spec:
        print()
        print(f"Ambiguous specs (first {args.max_report}):")
        for fname, nums in ambiguous_spec[: args.max_report]:
            print(f"  {fname} -> {', '.join(nums)}")
    if ambiguous_plan:
        print()
        print(f"Ambiguous plans (first {args.max_report}):")
        for fname, nums in ambiguous_plan[: args.max_report]:
            print(f"  {fname} -> {', '.join(nums)}")

    if orphan_spec:
        print()
        print(f"Orphan specs (first {args.max_report}):")
        for fname in orphan_spec[: args.max_report]:
            print(f"  {fname}")
    if orphan_plan:
        print()
        print(f"Orphan plans (first {args.max_report}):")
        for fname in orphan_plan[: args.max_report]:
            print(f"  {fname}")

    if not args.apply:
        print()
        print("Dry-run. Pass --apply to write spec_file/plan_file fields.")
        return 0

    # Apply: write spec_file/plan_file fields. If multiple specs/plans land
    # on the same ADR, keep the earliest-dated file (heuristic — earliest
    # file for the topic is usually the canonical one).
    specs_for_adr: dict[str, str] = {}
    plans_for_adr: dict[str, str] = {}
    for fname, num in strong_spec:
        existing = specs_for_adr.get(num)
        if not existing or fname < existing:
            specs_for_adr[num] = fname
    for fname, num in strong_plan:
        existing = plans_for_adr.get(num)
        if not existing or fname < existing:
            plans_for_adr[num] = fname

    changed_count = 0
    spec_collisions: list[tuple[str, str, str]] = []  # (adr, fname, existing)
    plan_collisions: list[tuple[str, str, str]] = []

    for num, fname in specs_for_adr.items():
        adr = by_number.get(num)
        if not adr:
            continue
        existing = adr.get("spec_file")
        if existing and existing != fname:
            spec_collisions.append((num, fname, existing))
            continue
        if existing != fname:
            adr["spec_file"] = fname
            changed_count += 1

    for num, fname in plans_for_adr.items():
        adr = by_number.get(num)
        if not adr:
            continue
        existing = adr.get("plan_file")
        if existing and existing != fname:
            plan_collisions.append((num, fname, existing))
            continue
        if existing != fname:
            adr["plan_file"] = fname
            changed_count += 1

    if spec_collisions:
        print()
        print("Spec collisions (skipped — existing pointer was different):")
        for num, fname, existing in spec_collisions[: args.max_report]:
            print(f"  {num}: existing={existing}, candidate={fname}")
    if plan_collisions:
        print()
        print("Plan collisions (skipped — existing pointer was different):")
        for num, fname, existing in plan_collisions[: args.max_report]:
            print(f"  {num}: existing={existing}, candidate={fname}")

    ADR_INDEX.write_text(json.dumps(adrs, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print()
    print(f"Wrote {ADR_INDEX} ({changed_count} fields updated).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
