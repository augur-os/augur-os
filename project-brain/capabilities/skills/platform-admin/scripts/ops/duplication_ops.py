"""auto-duplication: detect duplicate auto-command implementations."""
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
import ast
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from difflib import SequenceMatcher

import yaml

from src.config.paths import get_all_client_skill_dirs
from src.lib.ops_protocol import FixResult, OpsContext, ScanResult, make_issue, write_report

name = "auto-duplication"

DIFFICULTY_SPEC = {
    0: "Surface check — count registered auto-command modules",
    1: "Content check — detect exact duplicate auto-command implementations",
    2: "Deep check — add metadata-aware near-duplicate detection",
    3: "Exhaustive — same as d2 with canonicalization",
    4: "Expert — same as d3",
}

_NEAR_DUPLICATE_THRESHOLD = 0.95


@dataclass(frozen=True)
class ModuleInfo:
    path: Path
    command_id: str
    bundle: str
    skill_name: str
    source_kind: str
    visibility: str
    loop_name: str
    contributes_to: str


def _root(project_root: Path) -> Path:
    return project_root.resolve()


def _client_skill_dirs(project_root: Path) -> list[Path]:
    local_dirs: list[Path] = []
    shared_skills = project_root / "project-brain" / "capabilities" / "skills"
    if shared_skills.is_dir():
        local_dirs.append(shared_skills)
    local_dirs.extend(sorted(path for path in project_root.glob("plugins/*/skills") if path.is_dir()))
    if local_dirs:
        return local_dirs
    return [path for path in get_all_client_skill_dirs(project_root) if path.is_dir()]


def _canonical_rel_path(project_root: Path, path: Path) -> Path:
    rel = path.resolve().relative_to(_root(project_root))
    # Canonical skill location after ADR-770: project-brain/capabilities/skills/<skill>/...
    canon = Path("project-brain") / "capabilities" / "skills"
    if (
        len(rel.parts) >= 4
        and rel.parts[0] == "project-brain"
        and rel.parts[1] == "capabilities"
        and rel.parts[2] == "skills"
    ):
        return rel
    if len(rel.parts) >= 2 and rel.parts[0] == "skills":
        skill = rel.parts[1]
        remainder = rel.parts[2:]
        return canon / skill / Path(*remainder) if remainder else canon / skill
    if len(rel.parts) >= 4 and rel.parts[0] == "plugins" and rel.parts[2] == "skills":
        skill = rel.parts[3]
        remainder = rel.parts[4:]
        return canon / skill / Path(*remainder) if remainder else canon / skill
    return rel


def _resolve_repo_path(project_root: Path, rel_path: str) -> Path:
    direct = project_root / rel_path
    if direct.exists():
        return direct
    rel = Path(rel_path)
    if (
        len(rel.parts) >= 4
        and rel.parts[0] == "project-brain"
        and rel.parts[1] == "capabilities"
        and rel.parts[2] == "skills"
    ):
        skill = rel.parts[3]
        remainder = rel.parts[4:]
        for legacy_root in sorted(project_root.glob("plugins/*/skills")):
            candidate = legacy_root / skill / Path(*remainder) if remainder else legacy_root / skill
            if candidate.exists():
                return candidate
    if len(rel.parts) >= 2 and rel.parts[0] == "skills":
        skill = rel.parts[1]
        remainder = rel.parts[2:]
        shared_candidate = project_root / "project-brain" / "capabilities" / "skills" / skill / Path(*remainder) if remainder else project_root / "project-brain" / "capabilities" / "skills" / skill
        if shared_candidate.exists():
            return shared_candidate
        for legacy_root in sorted(project_root.glob("plugins/*/skills")):
            candidate = legacy_root / skill / Path(*remainder) if remainder else legacy_root / skill
            if candidate.exists():
                return candidate
    return direct


def _rel(project_root: Path, path: Path) -> str:
    try:
        return _canonical_rel_path(project_root, path).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _standalone_skill_module(project_root: Path, skill_dir: Path, frontmatter: dict) -> Path | None:
    declared_callable = frontmatter.get("x-augur-callable")
    if isinstance(declared_callable, str) and declared_callable.endswith(".py"):
        resolved = _resolve_repo_path(project_root, declared_callable)
        if resolved.is_file():
            return resolved

    scripts_dir = skill_dir / "scripts"
    if not scripts_dir.is_dir():
        return None
    for py_file in sorted(scripts_dir.glob("*.py")):
        if py_file.name.startswith("_"):
            continue
        return py_file.resolve()
    return None


def _iter_ops_modules(project_root: Path) -> list[ModuleInfo]:
    modules: dict[Path, ModuleInfo] = {}
    for skills_dir in _client_skill_dirs(project_root):
        for yaml_path in sorted(skills_dir.glob("*/augur/augur.yaml")):
            try:
                data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
            except (OSError, yaml.YAMLError):
                continue
            commands = data.get("commands", [])
            contrib_commands = data.get("contributions", {}).get("commands", [])
            if not isinstance(commands, list):
                commands = []
            if isinstance(contrib_commands, list):
                commands = commands + contrib_commands
            plugin_root = yaml_path.parent.parent
            bundle = ""
            skill_name = plugin_root.name
            contributes_to = str(data.get("contributes_to", bundle))
            for cmd in commands:
                if not isinstance(cmd, dict):
                    continue
                if cmd.get("protocol") != "scan-fix":
                    continue
                callable_path = cmd.get("callable")
                if not isinstance(callable_path, str) or not callable_path.endswith(".py"):
                    continue
                module_path = (plugin_root / callable_path).resolve()
                if module_path.is_file():
                    modules[module_path] = ModuleInfo(
                        path=module_path,
                        command_id=str(cmd.get("id", module_path.stem)),
                        bundle=bundle,
                        skill_name=skill_name,
                        source_kind="augur-command",
                        visibility=str(cmd.get("visibility", "auto")),
                        loop_name=str((cmd.get("loop") or {}).get("name", "")),
                        contributes_to=contributes_to,
                    )

    for skills_dir in _client_skill_dirs(project_root):
        for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
            try:
                content = skill_md.read_text(encoding="utf-8")
            except OSError:
                continue
            if not content.startswith("---"):
                continue
            parts = content.split("---", 2)
            if len(parts) < 3:
                continue
            try:
                frontmatter = yaml.safe_load(parts[1]) or {}
            except yaml.YAMLError:
                continue
            if not isinstance(frontmatter.get("x-augur-loop"), dict):
                continue
            resolved = _standalone_skill_module(project_root, skill_md.parent, frontmatter)
            if resolved is None:
                continue
            if resolved in modules and modules[resolved].source_kind == "augur-command":
                continue
            augur_yaml = skill_md.parent / "augur" / "augur.yaml"
            bundle = ""
            contributes_to = bundle
            if augur_yaml.is_file():
                try:
                    augur_data = yaml.safe_load(augur_yaml.read_text(encoding="utf-8")) or {}
                except (OSError, yaml.YAMLError):
                    augur_data = {}
                contributes_to = str(augur_data.get("contributes_to", bundle))
            modules[resolved] = ModuleInfo(
                path=resolved,
                command_id=str(frontmatter.get("name", skill_md.parent.name)),
                bundle=bundle,
                skill_name=skill_md.parent.name,
                source_kind="skill-md",
                visibility=str(frontmatter.get("x-augur-visibility", "auto")),
                loop_name=str((frontmatter.get("x-augur-loop") or {}).get("name", "")),
                contributes_to=contributes_to,
            )
    return sorted(modules.values(), key=lambda info: str(info.path))


def _strip_module_docstring(content: str) -> str:
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return content
    if not tree.body:
        return content
    first = tree.body[0]
    if (
        isinstance(first, ast.Expr)
        and isinstance(getattr(first, "value", None), ast.Constant)
        and isinstance(first.value.value, str)
    ):
        lines = content.splitlines()
        start = first.lineno - 1
        end = getattr(first, "end_lineno", first.lineno) - 1
        del lines[start : end + 1]
        return "\n".join(lines).strip() + "\n"
    return content


def _normalized_content(path: Path) -> str:
    raw = path.read_text(encoding="utf-8", errors="replace")
    without_docstring = _strip_module_docstring(raw)
    lines = [line.rstrip() for line in without_docstring.splitlines()]
    return "\n".join(lines).strip() + "\n"


def _content_hash(path: Path) -> str:
    return hashlib.sha256(_normalized_content(path).encode("utf-8")).hexdigest()[:16]


def _canonical_sort_key(project_root: Path, info: ModuleInfo) -> tuple[int, int, int, int, int, int, str]:
    rel = _rel(project_root, info.path)
    is_adaptive = rel.startswith("project-brain/capabilities/skills/auto-")
    is_core_ops = "/scripts/ops/" in rel
    is_augur_command = info.source_kind == "augur-command"
    is_owner_bundle = info.bundle == info.contributes_to
    is_auto_visible = info.visibility == "auto"
    return (
        0 if is_augur_command else 1,
        1 if is_adaptive else 0,
        0 if is_core_ops else 1,
        0 if is_owner_bundle else 1,
        0 if is_auto_visible else 1,
        len(rel),
        rel,
    )


def _dotted_module(project_root: Path, path: Path) -> str:
    try:
        rel = _canonical_rel_path(project_root, path).with_suffix("")
    except ValueError:
        rel = path.resolve().with_suffix("")
    return ".".join(rel.parts)


_WRAPPER_CANONICAL_RE = re.compile(r"Canonical implementation:\s+([^\n]+)")


def _wrapper_canonical(path: Path) -> str | None:
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    match = _WRAPPER_CANONICAL_RE.search(content)
    if not match:
        return None
    return match.group(1).strip()


def _is_safe_canonicalization_target(
    project_root: Path,
    canonical: ModuleInfo,
    duplicate: ModuleInfo,
) -> bool:
    canonical_rel = _rel(project_root, canonical.path)
    duplicate_rel = _rel(project_root, duplicate.path)
    return (
        canonical.source_kind == "augur-command"
        and
        "/scripts/ops/" in canonical_rel
        and canonical.command_id == duplicate.command_id
        and canonical.path.name == duplicate.path.name
        and canonical_rel != duplicate_rel
        and _skill_dir_for_duplicate(project_root, duplicate) is not None
        and not duplicate_rel.startswith("project-brain/capabilities/skills/daemon/scripts/ops/")
        and not duplicate_rel.startswith("project-brain/capabilities/skills/devops/scripts/ops/")
        and not duplicate_rel.startswith("project-brain/capabilities/skills/platform-admin/scripts/ops/")
    )


def _skill_dir_for_duplicate(project_root: Path, duplicate: ModuleInfo) -> Path | None:
    try:
        rel = duplicate.path.resolve().relative_to(_root(project_root))
    except ValueError:
        return None
    if len(rel.parts) >= 5 and rel.parts[0] == "project-brain" and rel.parts[1] == "skills" and rel.parts[3] == "scripts":
        skill_dir = project_root / rel.parts[0] / rel.parts[1] / rel.parts[2]
        return skill_dir if (skill_dir / "SKILL.md").is_file() else None
    if len(rel.parts) >= 6 and rel.parts[0] == "plugins" and rel.parts[2] == "skills" and rel.parts[4] == "scripts":
        skill_dir = project_root / rel.parts[0] / rel.parts[1] / rel.parts[2] / rel.parts[3]
        return skill_dir if (skill_dir / "SKILL.md").is_file() else None
    return None


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def _common_line_summary(a: str, b: str, limit: int = 3) -> tuple[int, list[str]]:
    left = [line.strip() for line in a.splitlines() if line.strip()]
    right = {line.strip() for line in b.splitlines() if line.strip()}
    shared = [line for line in left if line in right]
    deduped: list[str] = []
    for line in shared:
        if line not in deduped:
            deduped.append(line)
    return len(deduped), deduped[:limit]


def _suggest_extraction_path(project_root: Path, canonical: ModuleInfo) -> str:
    rel = canonical.path.resolve().relative_to(_root(project_root))
    if "/scripts/ops/" in rel.as_posix():
        return rel.as_posix().replace("/scripts/ops/", "/scripts/ops/shared/")
    return rel.as_posix().replace("/scripts/", "/scripts/shared/")


def _set_skill_callable(skill_dir: Path, canonical_rel: str) -> None:
    skill_md = skill_dir / "SKILL.md"
    content = skill_md.read_text(encoding="utf-8")
    if not content.startswith("---"):
        raise ValueError(f"{skill_md} missing frontmatter")
    parts = content.split("---", 2)
    if len(parts) < 3:
        raise ValueError(f"{skill_md} frontmatter malformed")
    frontmatter = yaml.safe_load(parts[1]) or {}
    frontmatter["x-augur-callable"] = canonical_rel
    updated = "---\n" + yaml.safe_dump(frontmatter, sort_keys=False).rstrip() + "\n---" + parts[2]
    skill_md.write_text(updated, encoding="utf-8")


def scan(ctx: OpsContext) -> ScanResult:
    modules = _iter_ops_modules(ctx.project_root)
    if ctx.difficulty < 1:
        return ScanResult(
            issues=[],
            summary=f"{len(modules)} auto-command module(s) registered",
            severity="info",
        )

    by_hash: dict[str, list[ModuleInfo]] = {}
    normalized_by_rel: dict[str, str] = {}
    by_key: dict[str, list[ModuleInfo]] = {}
    for info in modules:
        try:
            normalized = _normalized_content(info.path)
        except OSError:
            continue
        content_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
        by_hash.setdefault(content_hash, []).append(info)
        normalized_by_rel[_rel(ctx.project_root, info.path)] = normalized
        by_key.setdefault(info.command_id or info.path.name, []).append(info)

    issues: list[dict] = []
    max_groups = int(ctx.config.get("max_groups", 50))
    seen_rel_paths: set[str] = set()
    for content_hash, infos in sorted(by_hash.items()):
        if len(infos) < 2:
            continue
        ordered = sorted(infos, key=lambda info: _canonical_sort_key(ctx.project_root, info))
        canonical = ordered[0]
        duplicates = ordered[1:]
        duplicate_rels = [_rel(ctx.project_root, info.path) for info in duplicates]
        canonical_rel = _rel(ctx.project_root, canonical.path)
        safe_duplicates = [
            _rel(ctx.project_root, info.path)
            for info in duplicates
            if _is_safe_canonicalization_target(ctx.project_root, canonical, info)
        ]
        issue = make_issue(
            category=name,
            kind="actionable" if safe_duplicates else "manual",
            root_cause_type="repo_bug" if safe_duplicates else "manual_debt",
            fixability="skill-callable" if safe_duplicates else "manual-review",
            path=canonical_rel,
            detail=f"duplicate implementation group rooted at {canonical_rel}",
            content_hash=content_hash,
            canonical=canonical_rel,
            canonical_command_id=canonical.command_id,
            duplicates=duplicate_rels,
            safe_duplicates=safe_duplicates,
            duplicate_count=len(duplicate_rels),
        )
        issues.append(issue)
        seen_rel_paths.add(canonical_rel)
        seen_rel_paths.update(duplicate_rels)
        if len(issues) >= max_groups:
            break

    if ctx.difficulty >= 2:
        for key, infos in sorted(by_key.items()):
            if len(infos) < 2:
                continue
            ordered = sorted(infos, key=lambda info: _canonical_sort_key(ctx.project_root, info))
            canonical = ordered[0]
            canonical_rel = _rel(ctx.project_root, canonical.path)
            canonical_content = normalized_by_rel.get(canonical_rel, "")
            if not canonical_content:
                continue
            for info in ordered[1:]:
                rel = _rel(ctx.project_root, info.path)
                if rel in seen_rel_paths:
                    continue
                other_content = normalized_by_rel.get(rel, "")
                similarity = _similarity(canonical_content, other_content)
                if similarity < _NEAR_DUPLICATE_THRESHOLD or similarity >= 1.0:
                    continue
                common_count, common_lines = _common_line_summary(canonical_content, other_content)
                seen_rel_paths.add(rel)
                issues.append(
                    make_issue(
                        category=name,
                        kind="manual",
                        root_cause_type="manual_debt",
                        fixability="root-extraction",
                        path=canonical_rel,
                        detail=f"near-duplicate implementation group rooted at {canonical_rel}",
                        canonical=canonical_rel,
                        canonical_command_id=canonical.command_id,
                        duplicates=[f"{rel}:{similarity:.3f}"],
                        duplicate_count=1,
                        similarity_threshold=_NEAR_DUPLICATE_THRESHOLD,
                        extract_to=_suggest_extraction_path(ctx.project_root, canonical),
                        common_line_count=common_count,
                        common_lines=common_lines,
                    )
                )
                if len(issues) >= max_groups:
                    break
            if len(issues) >= max_groups:
                break

    info_by_rel = {
        _rel(ctx.project_root, info.path): info
        for info in modules
    }
    for info in modules:
        rel = _rel(ctx.project_root, info.path)
        if rel in seen_rel_paths:
            continue
        canonical_rel = _wrapper_canonical(info.path)
        if not canonical_rel:
            continue
        canonical = _resolve_repo_path(ctx.project_root, canonical_rel)
        if not canonical.is_file():
            continue
        canonical_info = info_by_rel.get(canonical_rel)
        if canonical_info is None:
            canonical_info = ModuleInfo(
                path=canonical,
                command_id=info.command_id,
                bundle="",
                skill_name="",
                source_kind="augur-command",
                visibility="auto",
                loop_name=info.loop_name,
                contributes_to="",
            )
        if not _is_safe_canonicalization_target(ctx.project_root, canonical_info, info):
            continue
        issues.append(
            make_issue(
                category=name,
                kind="actionable",
                root_cause_type="repo_bug",
                fixability="skill-callable",
                path=canonical_rel,
                detail=f"wrapper duplicate should be replaced by canonical callable {canonical_rel}",
                canonical=canonical_rel,
                canonical_command_id=canonical_info.command_id,
                duplicates=[rel],
                safe_duplicates=[rel],
                duplicate_count=1,
            )
        )
        if len(issues) >= max_groups:
            break

    actionable = sum(1 for issue in issues if issue.get("kind") == "actionable")
    manual = sum(1 for issue in issues if issue.get("kind") == "manual")
    summary = f"{len(issues)} duplicate implementation group(s)"
    if issues:
        summary += f"; {actionable} auto-fixable, {manual} manual"
    return ScanResult(
        issues=issues,
        summary=summary,
        severity="warning" if issues else "info",
        health="degraded" if issues else "verified",
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    if ctx.dry_run:
        return FixResult(success=True, summary=f"Dry run: would process {len(issues)} duplicate group(s)")

    changes: list[str] = []
    actions: list[dict] = []
    remaining: list[dict] = []
    info_by_rel = {
        _rel(ctx.project_root, info.path): info
        for info in _iter_ops_modules(ctx.project_root)
    }

    for issue in issues:
        canonical_rel = issue.get("canonical", "")
        safe_duplicates = issue.get("safe_duplicates", [])
        content_hash = issue.get("content_hash", "")
        if not canonical_rel or not isinstance(safe_duplicates, list) or not safe_duplicates:
            remaining.append(issue)
            continue

        canonical = _resolve_repo_path(ctx.project_root, canonical_rel)
        if not canonical.is_file():
            remaining.append(issue)
            continue

        for duplicate_rel in safe_duplicates:
            duplicate = _resolve_repo_path(ctx.project_root, duplicate_rel)
            if not duplicate.is_file():
                continue
            duplicate_info = info_by_rel.get(duplicate_rel)
            if duplicate_info is None:
                remaining.append(issue)
                continue
            skill_dir = _skill_dir_for_duplicate(ctx.project_root, duplicate_info)
            if skill_dir is None:
                remaining.append(issue)
                continue
            wrapper_target = _wrapper_canonical(duplicate)
            if wrapper_target is None:
                try:
                    current_hash = _content_hash(duplicate)
                except OSError:
                    remaining.append(issue)
                    continue
                if current_hash != content_hash:
                    remaining.append(issue)
                    continue
            elif wrapper_target != canonical_rel:
                remaining.append(issue)
                continue

            try:
                _set_skill_callable(skill_dir, canonical_rel)
                duplicate.unlink()
            except (OSError, ValueError):
                remaining.append(issue)
                continue
            changes.extend(
                [
                    _rel(ctx.project_root, skill_dir / "SKILL.md"),
                    duplicate_rel,
                ]
            )
            actions.append({"canonicalized": duplicate_rel, "canonical": canonical_rel})

        unresolved_duplicates = [
            rel for rel in issue.get("duplicates", []) or [] if rel not in changes
        ]
        if unresolved_duplicates:
            updated = dict(issue)
            updated["duplicates"] = unresolved_duplicates
            updated["safe_duplicates"] = [rel for rel in safe_duplicates if rel in unresolved_duplicates]
            remaining.append(updated)

    report_path = write_report(
        ctx,
        "duplication-latest.json",
        {
            "fixed_groups": len(actions),
            "remaining_groups": len(remaining),
            "actions": actions,
            "remaining": remaining,
        },
    )
    return FixResult(
        success=True,
        actions=[*actions, {"report": str(report_path)}],
        changes=changes,
        summary=f"Canonicalized {len(actions)} duplicate module(s); {len(remaining)} group(s) remain",
        fix_type="code-fix" if changes else "report",
    )
