"""Pre-merge demo proof summaries for /dev-merge."""
from __future__ import annotations

import argparse
from collections import deque
import importlib
import importlib.util
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


COMPOUND_WIKI_FLAGS = {"--com", "--compound-wiki"}
SKILLIFY_FLAGS = {"--skillify", "--skilify"}
CANONICAL_SKILL_PREFIX = "project-brain/capabilities/skills/"
GENERATED_SKILL_EXPORT_PREFIXES = (
    ".claude/skills/",
    ".codex/skills/",
    ".gemini/skills/",
)
PASSING_STATUSES = {"changed", "created", "updated", "reviewed", "verified-noop"}
BLOCKED_STATUS = "blocked"
COMPOUND_REVIEW_STATUSES = {"proposed", "no_durable_change", "blocked"}
COMPOUND_REVIEW_TARGET_TYPES = {
    "wiki",
    "existing_skill",
    "new_skill",
    "adr",
    "none",
}
COMPOUND_REVIEW_CONFIDENCE = {"high", "medium", "low"}
GENERIC_REVIEW_PHRASES = {
    "all tests passed",
    "everything worked",
    "tests passed",
    "the command ran",
    "the command completed successfully",
    "improve docs",
    "improve skills",
    "document this better",
}
HEALTHY_WIKI_VERDICTS = {"ok", "healthy"}
BLOCKING_WIKI_VERDICTS = {
    "blocked",
    "error",
    "compiler_state_error",
    "structure_broken",
    "empty",
    "structure_ok_compile_backlog",
    "current_low_coverage",
}


class GitInspectionError(RuntimeError):
    """Raised when Git change inspection cannot produce trustworthy results."""


@dataclass(frozen=True)
class DemoProofOptions:
    compound_wiki: bool = False
    skillify: bool = False

    @property
    def requested(self) -> bool:
        return self.compound_wiki or self.skillify


@dataclass(frozen=True)
class ChangedPath:
    status: str
    path: str


@dataclass
class ProofSummary:
    title: str
    status: str
    inputs_used: list[str] = field(default_factory=list)
    items_changed: list[str] = field(default_factory=list)
    what_changed: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    incident_gap: str = ""
    skill_path: str = ""
    vault_changes: str = ""

    @property
    def ok(self) -> bool:
        return self.status in PASSING_STATUSES and not self.blockers


@dataclass(frozen=True)
class QualityVerification:
    ok: bool
    evidence: str
    blocker: str = ""


@dataclass
class CompoundReviewProposal:
    status: str
    durable_lesson: str
    evidence: list[str] = field(default_factory=list)
    target_type: str = "none"
    target_artifact: str = ""
    next_action: str = ""
    confidence: str = "low"
    why_not: list[str] = field(default_factory=list)


@dataclass
class CompoundReviewValidation:
    ok: bool
    blockers: list[str] = field(default_factory=list)


@dataclass
class CompoundReviewEvidence:
    repo_root: str
    vault_root: str
    base_ref: str
    repo_changes: list[str] = field(default_factory=list)
    skill_roots_changed: list[str] = field(default_factory=list)
    wiki_status: str = ""
    wiki_evidence: list[str] = field(default_factory=list)
    skillify_status: str = ""
    skillify_evidence: list[str] = field(default_factory=list)
    incident_gap: str = ""
    transcript_snippets: list[str] = field(default_factory=list)
    missing_optional_sources: list[str] = field(default_factory=list)


@dataclass
class CompoundReviewResult:
    proposal: CompoundReviewProposal | None = None
    validation: CompoundReviewValidation = field(
        default_factory=lambda: CompoundReviewValidation(ok=True)
    )
    evidence_artifact_path: str = ""
    proposal_artifact_path: str = ""

    @property
    def ok(self) -> bool:
        return (
            bool(self.proposal)
            and self.proposal.status != "blocked"
            and self.validation.ok
        )

    @property
    def blockers(self) -> list[str]:
        if not self.proposal:
            if self.validation.blockers:
                return list(self.validation.blockers)
            return ["compound review proposal was not supplied by the native agent"]
        if self.proposal.status == "blocked":
            return [
                "compound review proposal status is blocked",
                *self.validation.blockers,
            ]
        if self.ok:
            return []
        if not self.validation.blockers:
            return ["compound review validation failed"]
        return list(self.validation.blockers)


@dataclass
class DemoProofResult:
    wiki: ProofSummary | None = None
    skillify: ProofSummary | None = None
    compound_review: CompoundReviewResult | None = None
    artifact_path: str = ""
    requested: DemoProofOptions = field(default_factory=DemoProofOptions)
    created_at: str = ""
    repo_root: str = ""
    vault_root: str = ""
    base_ref: str = ""

    @property
    def ok(self) -> bool:
        summaries = self._summaries_to_check()
        return (
            bool(summaries)
            and not self.blockers
            and all(summary.ok for summary in summaries)
        )

    @property
    def blockers(self) -> list[str]:
        values: list[str] = []
        if self.compound_review and not self.compound_review.ok:
            values.extend(self.compound_review.blockers)
        if self.requested.requested:
            if self.requested.compound_wiki:
                if self.wiki:
                    values.extend(self.wiki.blockers)
                else:
                    values.append("wiki proof was requested but no wiki summary was produced")
            if self.requested.skillify:
                if self.skillify:
                    values.extend(self.skillify.blockers)
                else:
                    values.append("skillify proof was requested but no skillify summary was produced")
        else:
            for summary in (self.wiki, self.skillify):
                if summary:
                    values.extend(summary.blockers)
        return values

    def _summaries_to_check(self) -> list[ProofSummary]:
        if self.requested.requested:
            summaries: list[ProofSummary] = []
            if self.requested.compound_wiki and self.wiki:
                summaries.append(self.wiki)
            if self.requested.skillify and self.skillify:
                summaries.append(self.skillify)
            return summaries
        return [summary for summary in (self.wiki, self.skillify) if summary]


def split_demo_proof_flags(args: Sequence[str]) -> tuple[DemoProofOptions, list[str]]:
    compound_wiki = False
    skillify = False
    remaining: list[str] = []
    for arg in args:
        if arg in COMPOUND_WIKI_FLAGS:
            compound_wiki = True
        elif arg in SKILLIFY_FLAGS:
            skillify = True
        else:
            remaining.append(arg)
    return DemoProofOptions(compound_wiki=compound_wiki, skillify=skillify), remaining


def parse_name_status(output: str) -> list[ChangedPath]:
    changes: list[ChangedPath] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status = parts[0]
        path = parts[-1]
        changes.append(ChangedPath(status=status, path=path))
    return changes


def parse_porcelain_status(output: str) -> list[ChangedPath]:
    changes: list[ChangedPath] = []
    for raw_line in output.splitlines():
        if len(raw_line) < 4:
            continue
        status = raw_line[:2].strip() or "M"
        path = raw_line[3:].strip()
        if status[0] in {"R", "C"} and " -> " in path:
            path = path.split(" -> ", 1)[1]
        if status == "??":
            status = "?"
        changes.append(ChangedPath(status=status, path=path))
    return changes


def _run_git(repo_root: Path, args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _raise_git_inspection_error(
    operation: str,
    repo_root: Path,
    base_ref: str,
    result: subprocess.CompletedProcess[str],
) -> None:
    detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
    raise GitInspectionError(
        f"Git inspection failed during {operation} for repo {repo_root} "
        f"against {base_ref}: {detail}"
    )


def collect_git_changes(
    repo_root: Path, base_ref: str = "origin/main"
) -> list[ChangedPath]:
    committed: list[ChangedPath] = []
    merge_base = _run_git(repo_root, ["merge-base", "HEAD", base_ref])
    if merge_base.returncode != 0:
        _raise_git_inspection_error("merge-base", repo_root, base_ref, merge_base)

    diff = _run_git(
        repo_root,
        ["diff", "--name-status", f"{merge_base.stdout.strip()}...HEAD"],
    )
    if diff.returncode != 0:
        _raise_git_inspection_error("diff --name-status", repo_root, base_ref, diff)
    committed = parse_name_status(diff.stdout)

    status = _run_git(repo_root, ["status", "--porcelain"])
    if status.returncode != 0:
        _raise_git_inspection_error("status --porcelain", repo_root, base_ref, status)
    uncommitted = parse_porcelain_status(status.stdout)

    seen: set[str] = set()
    merged: list[ChangedPath] = []
    for change in [*committed, *uncommitted]:
        if change.path not in seen:
            seen.add(change.path)
            merged.append(change)
    return merged


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _nested_mapping(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload.get(key)
    return value if isinstance(value, Mapping) else {}


def _query_count(value: Any) -> int:
    if isinstance(value, Mapping):
        return len(value)
    if isinstance(value, (list, tuple, set)):
        return len(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return 0
        numeric_count = _as_int(stripped)
        return numeric_count if numeric_count > 0 else 1
    return _as_int(value)


def _query_names(value: Any) -> list[str]:
    if isinstance(value, Mapping):
        return [str(key).strip() for key in value if str(key).strip()]
    if isinstance(value, (list, tuple, set)):
        names: list[str] = []
        for item in value:
            if isinstance(item, Mapping):
                for key in ("id", "name", "title", "query"):
                    candidate = str(item.get(key) or "").strip()
                    if candidate:
                        names.append(candidate)
                        break
                continue
            candidate = str(item).strip()
            if candidate:
                names.append(candidate)
        return names
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        return [] if _as_int(stripped) > 0 else [stripped]
    return []


def _string_values(value: Any, *, keys: Sequence[str] = ()) -> list[str]:
    if isinstance(value, Mapping):
        for key in keys:
            candidate = str(value.get(key) or "").strip()
            if candidate:
                return [candidate]
        return []
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    if isinstance(value, (list, tuple, set)):
        values: list[str] = []
        for item in value:
            values.extend(_string_values(item, keys=keys))
        return values
    return []


def _wiki_status_page_names(status_payload: Mapping[str, Any]) -> list[str]:
    compounding_health = _nested_mapping(status_payload, "compounding_health")
    candidates: list[str] = []
    for key in ("sample_pages", "current_pages", "concept_pages"):
        candidates.extend(_string_values(compounding_health.get(key), keys=("page", "path")))
    candidates.extend(_string_values(compounding_health.get("thin_pages"), keys=("page", "path")))
    return sorted(dict.fromkeys(candidates))


def _format_timestamp(value: Any) -> str:
    if isinstance(value, (int, float)) and value > 0:
        return (
            datetime.fromtimestamp(float(value), timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )
    if isinstance(value, str):
        stripped = value.strip()
        if stripped:
            return stripped
    return ""


def _wiki_freshness_timestamp(status_payload: Mapping[str, Any]) -> str:
    telemetry = _nested_mapping(status_payload, "telemetry")
    batches = _nested_mapping(status_payload, "batches")
    for value in (
        status_payload.get("last_extraction_ts"),
        telemetry.get("last_extraction_ts"),
        batches.get("last_batch_created"),
        status_payload.get("generated_at"),
        status_payload.get("created_at"),
    ):
        timestamp = _format_timestamp(value)
        if timestamp:
            return timestamp
    return ""


def _wiki_verdict_is_passable(
    normalized_verdict: str,
    status_payload: Mapping[str, Any],
) -> bool:
    if normalized_verdict in BLOCKING_WIKI_VERDICTS:
        return False
    return (
        normalized_verdict in HEALTHY_WIKI_VERDICTS
        or status_payload.get("healthy") is True
    )


def _wiki_change_paths(changes: Iterable[ChangedPath]) -> list[str]:
    wiki_paths: list[str] = []
    for change in changes:
        path = change.path.replace("\\", "/")
        if path.startswith("wiki/") and (
            path.endswith(".md")
            or path.endswith(".yaml")
            or path.endswith(".yml")
            or path.endswith(".json")
        ):
            wiki_paths.append(path)
    return sorted(dict.fromkeys(wiki_paths))


def _wiki_change_descriptions(paths: list[str]) -> list[str]:
    if not paths:
        return []
    markdown_pages = [path for path in paths if path.endswith(".md")]
    if len(markdown_pages) == len(paths):
        return ["durable wiki page changed"]
    if markdown_pages:
        return ["durable wiki file/page changed"]
    return ["durable wiki file changed"]


def _normalize_repo_path(path: str) -> str:
    return path.replace("\\", "/").removeprefix("./")


def _canonical_skill_root(path: str) -> str:
    normalized = _normalize_repo_path(path)
    if not normalized.startswith(CANONICAL_SKILL_PREFIX):
        return ""
    rest = normalized[len(CANONICAL_SKILL_PREFIX) :]
    parts = rest.split("/", 1)
    if len(parts) < 2:
        return ""
    skill_name, artifact_path = parts
    if not skill_name or not artifact_path:
        return ""
    return f"{CANONICAL_SKILL_PREFIX}{skill_name}"


def _artifact_category(path: str) -> str:
    normalized = _normalize_repo_path(path)
    root = _canonical_skill_root(normalized)
    relative = normalized.removeprefix(f"{root}/") if root else normalized
    if relative == "SKILL.md":
        return "SKILL.md"
    if relative == "config.yaml" or relative.startswith("config/"):
        return "config"
    if relative.startswith("commands/") and relative.endswith(".md"):
        return "command docs"
    if (
        relative.startswith("mcp/")
        or "/mcp/" in relative
        or "/tools/" in relative
    ):
        return "MCP wrappers"
    if relative.startswith("scripts/"):
        return "scripts"
    if relative.startswith("augur/tests/") or "/tests/" in relative:
        return "tests"
    if relative.startswith("augur/dashboard/") or relative.startswith("augur/pages/"):
        return "dashboard surfaces"
    if relative.startswith("prompts/"):
        return "prompts"
    if relative.startswith("assets/actions/") or relative.startswith("actions/"):
        return "actions"
    if relative.startswith("data/"):
        return "data"
    if relative.startswith("references/"):
        return "references"
    return "skill artifacts"


def _is_generated_skill_export(path: str) -> bool:
    normalized = _normalize_repo_path(path)
    return normalized.startswith(GENERATED_SKILL_EXPORT_PREFIXES)


def _is_added_status(status: str) -> bool:
    normalized = status.strip()
    return normalized == "?" or normalized.startswith("A")


def _is_deleted_status(status: str) -> bool:
    normalized = status.strip()
    return normalized.startswith("D")


def _load_skill_manifest(repo_root: Path | None) -> Mapping[str, Any]:
    if repo_root is None:
        return {}
    manifest_path = Path(repo_root) / "docs" / "generated" / "skill-manifest.json"
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, Mapping) else {}


def _manifest_skill_paths(manifest: Mapping[str, Any]) -> set[str]:
    skills = manifest.get("skills")
    paths: set[str] = set()
    if isinstance(skills, Mapping):
        iterable = skills.values()
    elif isinstance(skills, list):
        iterable = skills
    else:
        iterable = []
    for skill in iterable:
        if not isinstance(skill, Mapping):
            continue
        path = str(skill.get("path") or "").strip()
        if path:
            paths.add(_normalize_repo_path(path))
    return paths


def _load_capability_policy_skill_names(repo_root: Path | None) -> set[str]:
    if repo_root is None:
        return set()
    policy_path = Path(repo_root) / "config" / "system" / "capability_exposure.yaml"
    try:
        lines = policy_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return set()

    names: set[str] = set()
    for raw_line in lines:
        stripped = raw_line.strip()
        if stripped.startswith("skill:") and stripped.endswith(":"):
            skill_name = stripped[len("skill:") : -1].strip().strip("'\"")
            if skill_name:
                names.add(skill_name)
    return names


def _skill_name(root: str) -> str:
    return root.removeprefix(CANONICAL_SKILL_PREFIX)


def _skill_names(roots: Sequence[str]) -> list[str]:
    return [_skill_name(root) for root in roots]


def _behavior_categories(categories: Sequence[str]) -> list[str]:
    durable = {
        "SKILL.md",
        "command docs",
        "MCP wrappers",
        "scripts",
        "dashboard surfaces",
        "prompts",
        "actions",
        "config",
    }
    return [category for category in categories if category in durable]


def _incident_gap_for_skill(root: str, categories: Sequence[str], *, created: bool) -> str:
    skill = _skill_name(root)
    joined = ", ".join(_behavior_categories(categories)) or "skill artifacts"
    if created:
        return f"{skill} skill created with durable behavior: {joined}"
    return f"{skill} durable skill behavior changed: {joined}"


def _changes_for_root(changes: Sequence[ChangedPath], root: str) -> list[ChangedPath]:
    return [change for change in changes if _canonical_skill_root(change.path) == root]


def _categories_for_changes(changes: Sequence[ChangedPath]) -> list[str]:
    return sorted(dict.fromkeys(_artifact_category(change.path) for change in changes))


def _root_is_created(root: str, changes: Sequence[ChangedPath]) -> bool:
    root_paths = {change.path for change in changes}
    return f"{root}/SKILL.md" in root_paths and all(
        _is_added_status(change.status) for change in changes
    )


def _skill_path_summary(roots: Sequence[str]) -> str:
    return ", ".join(roots)


def _incident_gap_for_roots(
    roots: Sequence[str],
    canonical_changes: Sequence[ChangedPath],
) -> str:
    if not roots:
        return ""
    if len(roots) == 1:
        root = roots[0]
        root_changes = _changes_for_root(canonical_changes, root)
        return _incident_gap_for_skill(
            root,
            _categories_for_changes(root_changes),
            created=_root_is_created(root, root_changes),
        )

    parts: list[str] = []
    for root in roots:
        root_changes = _changes_for_root(canonical_changes, root)
        categories = _categories_for_changes(root_changes)
        behavior = ", ".join(_behavior_categories(categories)) or "skill artifacts"
        verb = "created" if _root_is_created(root, root_changes) else "changed"
        parts.append(f"{_skill_name(root)} {verb}: {behavior}")
    return "multiple durable skill behaviors changed: " + "; ".join(parts)


def _skillify_status_for_roots(
    roots: Sequence[str],
    canonical_changes: Sequence[ChangedPath],
) -> str:
    if roots and all(
        _root_is_created(root, _changes_for_root(canonical_changes, root))
        for root in roots
    ):
        return "created"
    return "updated"


def build_skillify_proof(
    repo_changes: Sequence[ChangedPath],
    repo_root: Path | None = None,
    quality_verifications: Mapping[str, QualityVerification] | None = None,
) -> ProofSummary:
    if not repo_changes:
        return ProofSummary(
            title="Skillify summary",
            status="verified-noop",
            inputs_used=["repo git changes"],
            what_changed=["no repo changes to skillify"],
            evidence=["no repo changes detected in the merge set"],
        )

    canonical_changes: list[ChangedPath] = []
    roots: list[str] = []
    generated_paths: list[str] = []
    capability_policy_touched = False
    skill_manifest_touched = False

    for change in repo_changes:
        path = _normalize_repo_path(change.path)
        if path == "config/system/capability_exposure.yaml":
            capability_policy_touched = True
        if path == "docs/generated/skill-manifest.json":
            skill_manifest_touched = True
        root = _canonical_skill_root(path)
        if root:
            canonical_changes.append(ChangedPath(status=change.status, path=path))
            if root not in roots:
                roots.append(root)
        elif _is_generated_skill_export(path):
            generated_paths.append(path)

    if not canonical_changes:
        if generated_paths:
            return ProofSummary(
                title="Skillify summary",
                status=BLOCKED_STATUS,
                inputs_used=["repo git changes"],
                items_changed=generated_paths,
                blockers=[
                    "only generated client skill exports changed",
                    "no canonical skill source changed in the merge set",
                ],
            )
        return ProofSummary(
            title="Skillify summary",
            status=BLOCKED_STATUS,
            inputs_used=["repo git changes"],
            blockers=["no canonical skill source changed in the merge set"],
        )

    canonical_paths = sorted(dict.fromkeys(change.path for change in canonical_changes))
    categories = sorted(dict.fromkeys(_artifact_category(path) for path in canonical_paths))
    evidence = [f"{len(canonical_paths)} canonical skill artifact(s) changed"]
    manifest_paths = _manifest_skill_paths(_load_skill_manifest(repo_root))
    capability_policy_skill_names = _load_capability_policy_skill_names(repo_root)
    manifested_roots = [root for root in roots if root in manifest_paths]
    policy_roots = [
        root for root in roots if _skill_name(root) in capability_policy_skill_names
    ]
    if capability_policy_touched:
        evidence.append("capability policy touched")
    if skill_manifest_touched:
        evidence.append("skill manifest touched")
    if manifested_roots:
        evidence.append(f"manifest entry present: {', '.join(_skill_names(manifested_roots))}")
    if policy_roots:
        evidence.append(
            f"capability policy entry present: {', '.join(_skill_names(policy_roots))}"
        )
    test_paths = [
        change.path
        for change in canonical_changes
        if not _is_deleted_status(change.status)
        and _artifact_category(change.path) == "tests"
    ]
    if test_paths:
        evidence.append(f"same-skill quality test artifact(s) changed: {len(test_paths)}")
    if generated_paths:
        evidence.append(
            "generated client exports also changed: "
            + ", ".join(sorted(dict.fromkeys(generated_paths)))
        )
    if len(roots) > 1:
        evidence.append(f"multiple skills changed: {', '.join(_skill_names(roots))}")

    status = _skillify_status_for_roots(roots, canonical_changes)
    incident_gap = _incident_gap_for_roots(roots, canonical_changes)
    skill_path = _skill_path_summary(roots)

    blockers: list[str] = []
    for root in roots:
        root_changes = _changes_for_root(canonical_changes, root)
        root_categories = _categories_for_changes(root_changes)
        root_behavior_categories = _behavior_categories(root_categories)
        root_non_deleted = [
            change for change in root_changes if not _is_deleted_status(change.status)
        ]
        skill = _skill_name(root)
        if not root_non_deleted:
            blockers.append(f"{skill} has only deletion/removal changes")
        if not root_behavior_categories:
            blockers.append(f"{skill} has no durable skill behavior artifact changed or created")
        route_proof_present = bool(
            root in manifest_paths or skill in capability_policy_skill_names
        )
        if not route_proof_present:
            blockers.append(f"{skill} has no routing proof")
        code_bearing = any(
            category in {"scripts", "MCP wrappers", "dashboard surfaces"}
            for category in root_behavior_categories
        )
        root_test_paths = [
            change.path
            for change in root_changes
            if not _is_deleted_status(change.status)
            and _artifact_category(change.path) == "tests"
        ]
        if code_bearing:
            quality_verification = (
                quality_verifications.get(root) if quality_verifications else None
            )
            if quality_verification:
                evidence.append(quality_verification.evidence)
                if not quality_verification.ok:
                    blockers.append(
                        quality_verification.blocker
                        or f"{skill} quality verification failed"
                    )
            elif quality_verifications is not None:
                blockers.append(
                    f"{skill} code-bearing changes need executable quality verification"
                )
            elif not root_test_paths:
                blockers.append(f"{skill} code-bearing changes need tests or quality proof")

    if blockers:
        return ProofSummary(
            title="Skillify summary",
            status=BLOCKED_STATUS,
            inputs_used=["repo git changes"],
            items_changed=canonical_paths,
            what_changed=categories,
            evidence=evidence,
            blockers=blockers,
            incident_gap=incident_gap,
            skill_path=skill_path,
        )

    return ProofSummary(
        title="Skillify summary",
        status=status,
        inputs_used=["repo git changes"],
        items_changed=canonical_paths,
        what_changed=categories,
        evidence=evidence,
        incident_gap=incident_gap,
        skill_path=skill_path,
    )


def _quality_roots_for_changes(repo_changes: Sequence[ChangedPath]) -> list[str]:
    canonical_changes: list[ChangedPath] = []
    roots: list[str] = []
    for change in repo_changes:
        path = _normalize_repo_path(change.path)
        root = _canonical_skill_root(path)
        if not root:
            continue
        canonical_change = ChangedPath(status=change.status, path=path)
        canonical_changes.append(canonical_change)
        if root not in roots:
            roots.append(root)

    quality_roots: list[str] = []
    for root in roots:
        root_changes = [
            change
            for change in _changes_for_root(canonical_changes, root)
            if not _is_deleted_status(change.status)
        ]
        categories = _categories_for_changes(root_changes)
        if any(
            category in {"scripts", "MCP wrappers", "dashboard surfaces"}
            for category in _behavior_categories(categories)
        ):
            quality_roots.append(root)
    return quality_roots


def _load_pytest_ops(repo_root: Path) -> Any:
    ops_path = (
        repo_root
        / "project-brain"
        / "capabilities"
        / "skills"
        / "routine-codebase"
        / "scripts"
        / "test_pytest_ops.py"
    )
    spec = importlib.util.spec_from_file_location(
        "_dev_merge_demo_proof_test_pytest_ops",
        ops_path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load auto-test-pytest ops from {ops_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _pytest_summary(stdout: str, stderr: str) -> str:
    stdout_lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    stderr_lines = [line.strip() for line in stderr.splitlines() if line.strip()]
    for line in reversed(stdout_lines):
        lowered = line.lower()
        if (
            " passed" in lowered
            or " failed" in lowered
            or " error" in lowered
            or " timed out" in lowered
        ):
            return line[-240:]
    for line in reversed(stderr_lines):
        lowered = line.lower()
        if (
            " failed" in lowered
            or " error" in lowered
            or " timed out" in lowered
        ):
            return line[-240:]
    lines = [*stdout_lines, *stderr_lines]
    return lines[-1][-240:] if lines else "no pytest output"


def _quality_verification_failure(skill: str, reason: str) -> QualityVerification:
    return QualityVerification(
        ok=False,
        evidence=f"quality verification failed: {skill}: {reason}",
        blocker=f"{skill} quality verification failed",
    )


def _run_skill_quality_verifications(
    repo_root: Path,
    roots: Sequence[str],
) -> dict[str, QualityVerification]:
    if not roots:
        return {}
    try:
        pytest_ops = _load_pytest_ops(repo_root)
    except Exception as exc:
        return {
            root: _quality_verification_failure(_skill_name(root), str(exc))
            for root in roots
        }

    verifications: dict[str, QualityVerification] = {}
    for root in roots:
        skill = _skill_name(root)
        test_dir = repo_root / root / "augur" / "tests"
        if not test_dir.is_dir():
            verifications[root] = _quality_verification_failure(
                skill,
                "missing augur/tests directory",
            )
            continue
        try:
            result = pytest_ops._run_pytest(repo_root, [test_dir], ["-q"], 300)
        except subprocess.TimeoutExpired:
            verifications[root] = _quality_verification_failure(
                skill,
                "pytest timed out after 300s",
            )
            continue
        except Exception as exc:
            verifications[root] = _quality_verification_failure(skill, str(exc))
            continue

        summary = _pytest_summary(result.stdout, result.stderr)
        if result.returncode == 0:
            verifications[root] = QualityVerification(
                ok=True,
                evidence=f"quality verification passed: {skill}: {summary}",
            )
        else:
            verifications[root] = _quality_verification_failure(
                skill,
                f"exit {result.returncode}; {summary}",
            )
    return verifications


def build_wiki_proof(
    status_payload: Mapping[str, Any],
    vault_changes: Iterable[ChangedPath],
) -> ProofSummary:
    verdict = str(status_payload.get("verdict") or "unknown").strip() or "unknown"
    normalized_verdict = verdict.lower()
    structure = _nested_mapping(status_payload, "structure")
    compiler = _nested_mapping(status_payload, "compiler")
    compounding = _nested_mapping(status_payload, "compounding")
    index = _nested_mapping(status_payload, "index")

    pages = _as_int(structure.get("pages"))
    entries = _as_int(index.get("entries", index.get("wiki_rag_entries")))
    queries = _query_count(compounding.get("queries"))
    query_names = _query_names(compounding.get("queries"))
    page_names = _wiki_status_page_names(status_payload)
    freshness_timestamp = _wiki_freshness_timestamp(status_payload)
    compiler_current = compiler.get("current") is True
    wiki_paths = _wiki_change_paths(vault_changes)
    passable_verdict = _wiki_verdict_is_passable(normalized_verdict, status_payload)

    evidence = [
        f"wiki-status verdict: {verdict}",
        f"wiki pages: {pages}",
        f"wiki index entries: {entries}",
    ]
    if "current" in compiler:
        evidence.append(f"wiki compiler current: {compiler_current}")
    if "queries" in compounding:
        evidence.append(f"compounding queries: {queries}")
    if query_names:
        evidence.append(f"compounding query ids: {', '.join(query_names[:5])}")
    if page_names:
        evidence.append(f"wiki page evidence: {', '.join(page_names[:5])}")
    if freshness_timestamp:
        evidence.append(f"current evidence timestamp: {freshness_timestamp}")

    has_named_wiki_evidence = bool(wiki_paths or page_names or query_names)
    blockers: list[str] = []
    if not passable_verdict and not wiki_paths:
        if not has_named_wiki_evidence:
            blockers.append("no named durable wiki page or compounding query evidence found")
        if not freshness_timestamp:
            blockers.append("no current evidence timestamp found for wiki verified-noop")
        if blockers:
            return ProofSummary(
                title="Wiki compounding summary",
                status=BLOCKED_STATUS,
                inputs_used=["wiki-status payload", "vault git changes"],
                items_changed=wiki_paths,
                evidence=evidence,
                blockers=blockers,
                vault_changes="none",
            )
        return ProofSummary(
            title="Wiki compounding summary",
            status="verified-noop",
            inputs_used=["wiki-status payload", "vault git changes"],
            items_changed=[
                "no durable wiki changes to compound",
                *(f"wiki page evidence: {path}" for path in page_names[:5]),
                *(f"compounding query present: {query}" for query in query_names[:5]),
            ],
            what_changed=["no durable wiki changes to compound"],
            evidence=evidence,
            vault_changes="none",
        )

    if not passable_verdict:
        blockers.append(f"wiki-status verdict is {normalized_verdict}")

    if not has_named_wiki_evidence:
        blockers.append("no named durable wiki page or compounding query evidence found")
    verified_noop_candidate = (
        passable_verdict
        and not wiki_paths
        and pages > 0
        and compiler_current
        and has_named_wiki_evidence
    )
    if verified_noop_candidate and not freshness_timestamp:
        blockers.append("no current evidence timestamp found for wiki verified-noop")

    if blockers:
        return ProofSummary(
            title="Wiki compounding summary",
            status=BLOCKED_STATUS,
            inputs_used=["wiki-status payload", "vault git changes"],
            items_changed=wiki_paths,
            evidence=evidence,
            blockers=blockers,
            vault_changes="none",
        )

    if wiki_paths:
        return ProofSummary(
            title="Wiki compounding summary",
            status="changed",
            inputs_used=["wiki-status payload", "vault git changes"],
            items_changed=wiki_paths,
            what_changed=_wiki_change_descriptions(wiki_paths),
            evidence=evidence,
            vault_changes="committed by normal /dev-merge full vault path",
        )

    if passable_verdict and pages > 0 and compiler_current:
        items_changed = [
            *(f"wiki page current: {path}" for path in page_names[:5]),
            *(f"compounding query current: {query}" for query in query_names[:5]),
        ]
        return ProofSummary(
            title="Wiki compounding summary",
            status="verified-noop",
            inputs_used=["wiki-status payload", "vault git changes"],
            items_changed=items_changed,
            evidence=evidence,
            vault_changes="none",
        )

    return ProofSummary(
        title="Wiki compounding summary",
        status=BLOCKED_STATUS,
        inputs_used=["wiki-status payload", "vault git changes"],
        evidence=evidence,
        blockers=["wiki status did not prove changed or current compounding output"],
        vault_changes="none",
    )


def _review_text_is_specific(value: str) -> bool:
    normalized = " ".join(value.strip().lower().split())
    generic_key = normalized.rstrip(".")
    return (
        bool(normalized)
        and generic_key not in GENERIC_REVIEW_PHRASES
        and len(normalized) >= 24
    )


def _review_evidence_is_specific(value: str) -> bool:
    normalized = " ".join(value.strip().lower().split())
    if not _review_text_is_specific(normalized):
        return False
    tokens = set(re.findall(r"[a-z0-9_:-]+", normalized))
    has_path_or_artifact = "/" in normalized or any(
        suffix in normalized for suffix in (".md", ".py", ".yaml", ".yml", ".json")
    )
    has_count = any(char.isdigit() for char in normalized)
    has_named_test = "test_" in normalized or "::test" in normalized
    has_observed_failure = bool(
        tokens
        & {
            "blocked",
            "error",
            "failed",
            "failure",
            "missing",
            "skipped",
        }
    )
    has_domain_marker = bool(
        tokens
        & {
            "codex",
            "frontmatter",
            "parser",
            "skill",
            "wiki",
            "yaml",
        }
    )
    return (
        has_path_or_artifact
        or has_count
        or has_named_test
        or has_observed_failure
        or has_domain_marker
    )


def validate_compound_review_proposal(
    proposal: CompoundReviewProposal,
) -> CompoundReviewValidation:
    blockers: list[str] = []
    status = proposal.status.strip()
    target_type = proposal.target_type.strip()
    confidence = proposal.confidence.strip()

    if status not in COMPOUND_REVIEW_STATUSES:
        blockers.append(
            f"status must be one of: {', '.join(sorted(COMPOUND_REVIEW_STATUSES))}"
        )
    if target_type not in COMPOUND_REVIEW_TARGET_TYPES:
        blockers.append(
            f"target_type must be one of: {', '.join(sorted(COMPOUND_REVIEW_TARGET_TYPES))}"
        )
    if confidence not in COMPOUND_REVIEW_CONFIDENCE:
        blockers.append(
            f"confidence must be one of: {', '.join(sorted(COMPOUND_REVIEW_CONFIDENCE))}"
        )
    if not _review_text_is_specific(proposal.durable_lesson):
        blockers.append("durable_lesson must be specific")
    if status == "proposed" and not proposal.target_artifact.strip():
        blockers.append("target_artifact is required for proposed review")
    if status == "proposed" and target_type == "none":
        blockers.append("target_type cannot be none for proposed review")
    if status == "no_durable_change" and target_type != "none":
        blockers.append("no_durable_change must use target_type none")
    if status == "no_durable_change" and proposal.target_artifact.strip():
        blockers.append("no_durable_change must not set target_artifact")
    if status != "blocked" and len(proposal.evidence) < 2:
        blockers.append("non-blocked review requires at least two evidence items")
    if len(proposal.evidence) < 2 and confidence == "high":
        blockers.append("high confidence requires at least two evidence items")
    for item in proposal.evidence:
        if not _review_evidence_is_specific(item):
            blockers.append(f"evidence item is too generic: {item}")
    if status == "proposed" and not _review_text_is_specific(proposal.next_action):
        blockers.append("next_action must be specific for proposed review")
    specific_why_not = [
        item for item in proposal.why_not if _review_text_is_specific(item)
    ]
    if status == "proposed" and not specific_why_not:
        blockers.append("proposed review requires at least one specific why_not reason")
    for item in proposal.why_not:
        if not _review_text_is_specific(item):
            blockers.append(f"why_not reason is too generic: {item}")
    return CompoundReviewValidation(ok=not blockers, blockers=blockers)


def _format_list(label: str, values: Sequence[str]) -> list[str]:
    if not values:
        return [f"- {label}: none"]
    return [f"- {label}: {', '.join(values)}"]


def render_summary(summary: ProofSummary) -> str:
    lines = [summary.title, f"- Status: {summary.status}"]
    if summary.incident_gap:
        lines.append(f"- Incident/gap captured: {summary.incident_gap}")
    if summary.skill_path:
        lines.append(f"- Skill affected: {summary.skill_path}")
    lines.extend(_format_list("Inputs used", summary.inputs_used))
    lines.extend(_format_list("Items changed", summary.items_changed))
    lines.extend(_format_list("What changed", summary.what_changed))
    lines.extend(_format_list("Evidence", summary.evidence))
    if summary.vault_changes:
        lines.append(f"- Vault changes: {summary.vault_changes}")
    if summary.blockers:
        lines.extend(_format_list("Blockers", summary.blockers))
    return "\n".join(lines)


def render_compound_review(result: CompoundReviewResult) -> str:
    lines = ["Compound review"]
    proposal = result.proposal
    if proposal:
        lines.append(f"- Status: {proposal.status}")
        lines.append(f"- Durable lesson: {proposal.durable_lesson}")
        lines.extend(_format_list("Evidence", proposal.evidence))
        lines.append(f"- Target type: {proposal.target_type}")
        lines.append(f"- Target artifact: {proposal.target_artifact or 'none'}")
        lines.append(f"- Next action: {proposal.next_action or 'none'}")
        lines.append(f"- Confidence: {proposal.confidence}")
        lines.extend(_format_list("Why not", proposal.why_not))
    else:
        lines.append("- Status: blocked")
    if result.evidence_artifact_path:
        lines.append(f"- Evidence artifact: {result.evidence_artifact_path}")
    if result.proposal_artifact_path:
        lines.append(f"- Proposal artifact: {result.proposal_artifact_path}")
    if result.blockers:
        lines.extend(_format_list("Blockers", result.blockers))
    return "\n".join(lines)


def render_demo_proof(result: DemoProofResult) -> str:
    lines = ["Demo proof summary before merge", ""]
    if result.compound_review:
        lines.append(render_compound_review(result.compound_review))
        lines.append("")
    if result.wiki:
        lines.append(render_summary(result.wiki))
        lines.append("")
    if result.skillify:
        lines.append(render_summary(result.skillify))
        lines.append("")
    if result.ok:
        lines.append("Result: proof passed; continuing /dev-merge full")
    else:
        lines.append("Result: blocked before merge")
        for blocker in result.blockers:
            lines.append(f"Reason: {blocker}")
    if result.artifact_path:
        lines.append(f"Artifact: {result.artifact_path}")
    return "\n".join(lines).rstrip() + "\n"


def write_demo_proof_artifact(result: DemoProofResult, runtime_dir: Path) -> Path:
    artifact_dir = Path(runtime_dir) / "dev-merge" / "demo-proof"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    artifact = artifact_dir / f"{stamp}.json"
    result.artifact_path = str(artifact)
    if not result.created_at:
        result.created_at = (
            datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )
    artifact.write_text(
        json.dumps(_result_payload(result), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return artifact


def write_compound_review_evidence_artifact(
    evidence: CompoundReviewEvidence,
    runtime_dir: Path,
) -> Path:
    artifact_dir = Path(runtime_dir) / "dev-merge" / "compound-review"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    artifact = artifact_dir / f"{stamp}-evidence.json"
    artifact.write_text(
        json.dumps(asdict(evidence), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return artifact


def _result_payload(result: DemoProofResult) -> dict[str, Any]:
    payload = asdict(result)
    payload["ok"] = result.ok
    payload["blockers"] = result.blockers
    return payload


def _project_root_from_markers(start: Path) -> Path | None:
    for parent in [Path(start), *Path(start).parents]:
        if (parent / "docs" / "agent-topics").is_dir() and (
            parent / "project-brain" / "capabilities" / "skills"
        ).is_dir():
            return parent
    return None


def _find_project_root(start: Path) -> Path:
    try:
        from src.config.paths import get_project_root

        return Path(get_project_root())
    except Exception:
        pass

    found = _project_root_from_markers(start)
    if found is not None:
        return found
    return Path(start)


def _default_runtime_dir() -> Path:
    try:
        from src.config.paths import get_runtime_dir

        return Path(get_runtime_dir())
    except Exception:
        return Path.cwd() / ".augur-runtime"


def _default_vault_dir() -> Path:
    try:
        from src.config.paths import get_vault_dir

        return Path(get_vault_dir())
    except Exception:
        return Path.cwd()


def _blocked_git_summary(title: str, error: GitInspectionError) -> ProofSummary:
    detail = str(error).strip() or "unknown Git inspection failure"
    message = (
        detail if "Git inspection" in detail else f"Git inspection failure: {detail}"
    )
    return ProofSummary(
        title=title,
        status=BLOCKED_STATUS,
        inputs_used=["git changes"],
        evidence=[message],
        blockers=[message],
    )


def _blocked_wiki_status_payload(reason: str) -> Mapping[str, Any]:
    return {
        "verdict": "blocked",
        "healthy": False,
        "structure": {"pages": 0},
        "compiler": {"current": False, "error": reason},
        "index": {"entries": 0},
    }


def _add_sys_path(path: Path) -> None:
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)


def _bootstrap_cli_import_paths(repo_root: Path | None = None) -> Path:
    resolved_root = (
        Path(repo_root)
        if repo_root is not None
        else (
            _project_root_from_markers(Path.cwd())
            or _project_root_from_markers(Path(__file__).resolve())
            or _find_project_root(Path.cwd())
        )
    )
    _add_sys_path(resolved_root)
    _add_sys_path(resolved_root / "src" / "mcp")
    _add_sys_path(resolved_root / "project-brain" / "capabilities")
    return resolved_root


def _import_wiki_status_module(repo_root: Path) -> Any:
    _bootstrap_cli_import_paths(repo_root)
    return importlib.import_module("skills.wiki.scripts.wiki_status")


def _load_wiki_status(repo_root: Path, vault_root: Path) -> Mapping[str, Any]:
    try:
        wiki_status = _import_wiki_status_module(repo_root)
        payload = wiki_status.build_wiki_status(wiki_dir=vault_root / "wiki")
        if not isinstance(payload, Mapping):
            return _blocked_wiki_status_payload(
                "wiki status builder returned non-object payload"
            )
        result = dict(payload)
        load_queries = getattr(wiki_status, "load_compounding_queries", None)
        if callable(load_queries):
            compounding = result.get("compounding")
            compounding_payload = (
                dict(compounding) if isinstance(compounding, Mapping) else {}
            )
            compounding_payload["queries"] = load_queries(vault_root)
            result["compounding"] = compounding_payload
        return result
    except Exception as exc:
        return _blocked_wiki_status_payload(
            f"wiki status import/build failed: {exc}"
        )


def _changed_path_label(change: ChangedPath) -> str:
    return f"{change.status} {_normalize_repo_path(change.path)}"


def _skill_roots_from_changes(changes: Sequence[ChangedPath]) -> list[str]:
    roots: list[str] = []
    for change in changes:
        root = _canonical_skill_root(_normalize_repo_path(change.path))
        if root and root not in roots:
            roots.append(root)
    return roots


def _transcript_snippets(transcript_path: Path | None) -> tuple[list[str], list[str]]:
    if transcript_path is None:
        return [], []
    if not transcript_path.is_file():
        return [], [f"transcript not found: {transcript_path}"]
    snippets: deque[str] = deque(maxlen=12)
    try:
        with transcript_path.open(encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if stripped:
                    snippets.append(stripped)
    except (OSError, UnicodeError) as exc:
        return [], [f"transcript unreadable: {transcript_path}: {exc}"]
    return list(snippets), []


def build_compound_review_evidence(
    repo_root: Path,
    vault_root: Path,
    base_ref: str,
    repo_changes: Sequence[ChangedPath],
    wiki_summary: ProofSummary | None = None,
    skillify_summary: ProofSummary | None = None,
    transcript_path: Path | None = None,
) -> CompoundReviewEvidence:
    snippets, missing = _transcript_snippets(transcript_path)
    return CompoundReviewEvidence(
        repo_root=str(repo_root),
        vault_root=str(vault_root),
        base_ref=base_ref,
        repo_changes=[_changed_path_label(change) for change in repo_changes],
        skill_roots_changed=_skill_roots_from_changes(repo_changes),
        wiki_status=wiki_summary.status if wiki_summary else "",
        wiki_evidence=list(wiki_summary.evidence) if wiki_summary else [],
        skillify_status=skillify_summary.status if skillify_summary else "",
        skillify_evidence=list(skillify_summary.evidence) if skillify_summary else [],
        incident_gap=skillify_summary.incident_gap if skillify_summary else "",
        transcript_snippets=snippets,
        missing_optional_sources=missing,
    )


def build_demo_proof(
    options: DemoProofOptions,
    repo_root: Path,
    vault_root: Path,
    base_ref: str,
) -> DemoProofResult:
    result = DemoProofResult(
        requested=options,
        created_at=(
            datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        ),
        repo_root=str(repo_root),
        vault_root=str(vault_root),
        base_ref=base_ref,
    )
    repo_changes: list[ChangedPath] = []
    vault_changes: list[ChangedPath] = []
    repo_error: GitInspectionError | None = None
    vault_error: GitInspectionError | None = None

    if options.skillify:
        try:
            repo_changes = collect_git_changes(repo_root, base_ref=base_ref)
        except GitInspectionError as exc:
            repo_error = exc

    if options.compound_wiki and (vault_root / ".git").exists():
        try:
            vault_changes = collect_git_changes(vault_root, base_ref=base_ref)
        except GitInspectionError as exc:
            vault_error = exc

    if options.compound_wiki:
        if vault_error:
            result.wiki = _blocked_git_summary("Wiki compounding summary", vault_error)
            result.wiki.vault_changes = "inspection failed"
        else:
            result.wiki = build_wiki_proof(
                status_payload=_load_wiki_status(repo_root, vault_root),
                vault_changes=vault_changes,
            )

    if options.skillify:
        if repo_error:
            result.skillify = _blocked_git_summary("Skillify summary", repo_error)
        else:
            quality_roots = _quality_roots_for_changes(repo_changes)
            quality_verifications = _run_skill_quality_verifications(
                repo_root,
                quality_roots,
            )
            result.skillify = build_skillify_proof(
                repo_changes=repo_changes,
                repo_root=repo_root,
                quality_verifications=quality_verifications,
            )

    return result


def load_compound_review_proposal(path: Path) -> CompoundReviewProposal:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("compound review proposal must be a JSON object")
    evidence = payload.get("evidence", [])
    why_not = payload.get("why_not", [])
    return CompoundReviewProposal(
        status=str(payload.get("status", "")).strip(),
        durable_lesson=str(payload.get("durable_lesson", "")).strip(),
        evidence=[str(item).strip() for item in evidence if str(item).strip()]
        if isinstance(evidence, list)
        else [],
        target_type=str(payload.get("target_type", "none")).strip(),
        target_artifact=str(payload.get("target_artifact", "")).strip(),
        next_action=str(payload.get("next_action", "")).strip(),
        confidence=str(payload.get("confidence", "low")).strip(),
        why_not=[str(item).strip() for item in why_not if str(item).strip()]
        if isinstance(why_not, list)
        else [],
    )


def attach_compound_review(
    result: DemoProofResult,
    repo_root: Path,
    vault_root: Path,
    base_ref: str,
    runtime_dir: Path,
    proposal_json: Path | None,
    transcript_path: Path | None = None,
) -> None:
    repo_changes: list[ChangedPath] = []
    validation_blockers: list[str] = []
    try:
        repo_changes = collect_git_changes(repo_root, base_ref=base_ref)
    except GitInspectionError as exc:
        repo_changes = []
        validation_blockers.append(
            f"compound review repo changes could not be inspected: {exc}"
        )
    evidence = build_compound_review_evidence(
        repo_root=repo_root,
        vault_root=vault_root,
        base_ref=base_ref,
        repo_changes=repo_changes,
        wiki_summary=result.wiki,
        skillify_summary=result.skillify,
        transcript_path=transcript_path,
    )
    evidence.missing_optional_sources.extend(validation_blockers)
    evidence_artifact = write_compound_review_evidence_artifact(evidence, runtime_dir)
    if proposal_json is None:
        result.compound_review = CompoundReviewResult(
            validation=CompoundReviewValidation(
                ok=not validation_blockers,
                blockers=validation_blockers,
            ),
            evidence_artifact_path=str(evidence_artifact)
        )
        return
    try:
        proposal = load_compound_review_proposal(proposal_json)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        result.compound_review = CompoundReviewResult(
            validation=CompoundReviewValidation(
                ok=False,
                blockers=[
                    f"compound review proposal could not be loaded: {proposal_json}: {exc}"
                ],
            ),
            evidence_artifact_path=str(evidence_artifact),
            proposal_artifact_path=str(proposal_json),
        )
        return
    validation = validate_compound_review_proposal(proposal)
    if validation_blockers:
        validation = CompoundReviewValidation(
            ok=False,
            blockers=[*validation.blockers, *validation_blockers],
        )
    result.compound_review = CompoundReviewResult(
        proposal=proposal,
        validation=validation,
        evidence_artifact_path=str(evidence_artifact),
        proposal_artifact_path=str(proposal_json),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--com",
        "--compound-wiki",
        action="store_true",
        dest="compound_wiki",
    )
    parser.add_argument(
        "--skillify",
        "--skilify",
        action="store_true",
        dest="skillify",
    )
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--vault-root", type=Path)
    parser.add_argument("--runtime-dir", type=Path)
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--json", action="store_true", dest="json_output")
    parser.add_argument("--compound-review", action="store_true")
    parser.add_argument("--review-proposal-json", type=Path)
    parser.add_argument("--review-transcript", type=Path)
    args = parser.parse_args(argv)

    if (args.review_proposal_json or args.review_transcript) and not args.compound_review:
        parser.error("--review-proposal-json/--review-transcript require --compound-review")

    options = DemoProofOptions(
        compound_wiki=bool(args.compound_wiki),
        skillify=bool(args.skillify),
    )
    if not options.requested:
        parser.error("at least one proof flag is required: --com or --skillify")

    repo_root = _bootstrap_cli_import_paths(args.repo_root)
    vault_root = args.vault_root if args.vault_root is not None else _default_vault_dir()
    runtime_dir = (
        args.runtime_dir if args.runtime_dir is not None else _default_runtime_dir()
    )

    result = build_demo_proof(
        options=options,
        repo_root=repo_root,
        vault_root=vault_root,
        base_ref=args.base_ref,
    )
    if args.compound_review:
        attach_compound_review(
            result=result,
            repo_root=repo_root,
            vault_root=vault_root,
            base_ref=args.base_ref,
            runtime_dir=runtime_dir,
            proposal_json=args.review_proposal_json,
            transcript_path=args.review_transcript,
        )
    write_demo_proof_artifact(result, runtime_dir=runtime_dir)
    if args.json_output:
        print(json.dumps(_result_payload(result), indent=2, sort_keys=True))
    else:
        print(render_demo_proof(result), end="")
    return 0 if result.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
