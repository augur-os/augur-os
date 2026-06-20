from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path


FORBIDDEN_STANDARD_PATTERNS = (
    "x-augur-",
    "x-augur:",
    "project-brain/",
    "Application Support/Augur",
)

CONTRACT_SCAN_DIRS = ("scripts", "references", "tests")
CONTRACT_TEXT_SUFFIXES = frozenset(
    {".applescript", ".bash", ".command", ".md", ".py", ".sh", ".swift", ".toml", ".yaml", ".yml", ".zsh"}
)
ROOT_CONTRACT_FILES = ("DESCRIPTION.md", "SKILL.md")
SKIP_CONTRACT_PATH_PARTS = frozenset({"__pycache__", "node_modules", "venv", ".venv"})
PROJECT_IMPORT_ROOTS = frozenset({"skills", "src"})
LLM_PROVIDER_IMPORT_ROOTS = frozenset({"anthropic", "google.generativeai", "openai"})

HARD_CODED_AUGUR_PATH_PATTERNS = (
    re.compile(r"/Users/[^/\s]+/Projects/(?:Augur|Au-vault)(?=$|[/'\"`\s])"),
    re.compile(r"/Users/[^/\s]+/Library/(?:Application Support|Logs|Caches)/Augur(?=$|[/'\"`\s])"),
)


@dataclass(frozen=True)
class StandardSkillContractReport:
    name: str
    path: Path
    status: str
    issues: tuple[str, ...]


@dataclass(frozen=True)
class SkillRootRole:
    tier: str
    brain_id: str
    root: Path


@dataclass(frozen=True)
class FullMigrationSkillReport:
    name: str
    path: Path
    status: str
    recommended_action: str
    roles: tuple[str, ...]
    issues: tuple[str, ...]


@dataclass(frozen=True)
class FullMigrationReport:
    physical_roots: tuple[Path, ...]
    skills: tuple[FullMigrationSkillReport, ...]


FULL_MIGRATION_SCOPE = frozenset(
    {
        "books",
        "file-manager",
        "document-extractor",
        "audio-ingest",
        "evals",
        "graph",
        "dream",
    }
)


@dataclass(frozen=True)
class FullMigrationGateReport:
    ok: bool
    blocked: tuple[str, ...]
    issues: tuple[str, ...]


def _is_standard_bundle(root: Path) -> bool:
    return (root / "DESCRIPTION.md").is_file() and any(root.glob("*/SKILL.md"))


def is_standard_core(skill_dir: Path) -> bool:
    """True if ``skill_dir`` is the core sub-directory of a standard bundle (ADR-040).

    A standard core lives one level inside a standard bundle: its parent holds the
    bundle ``DESCRIPTION.md`` and the core dir itself holds the portable ``SKILL.md``.
    Such cores are vendor-neutral by design and intentionally omit Augur frontmatter,
    so Augur-metadata completeness checks do not apply to them.
    """
    try:
        return (skill_dir.parent / "DESCRIPTION.md").is_file() and (skill_dir / "SKILL.md").is_file()
    except OSError:
        return False


def _is_relevant_contract_file(root: Path, path: Path) -> bool:
    relative_parts = path.relative_to(root).parts
    return not any(part.startswith(".") or part in SKIP_CONTRACT_PATH_PARTS for part in relative_parts)


def _read_contract_files(root: Path) -> list[Path]:
    candidates: list[Path] = []
    for filename in ROOT_CONTRACT_FILES:
        path = root / filename
        if path.is_file():
            candidates.append(path)

    candidates.extend(path for path in root.glob("*/SKILL.md") if path.is_file())

    for dirname in CONTRACT_SCAN_DIRS:
        scan_root = root / dirname
        if not scan_root.is_dir():
            continue
        candidates.extend(
            path
            for path in scan_root.rglob("*")
            if path.is_file()
            and path.suffix.lower() in CONTRACT_TEXT_SUFFIXES
            and _is_relevant_contract_file(root, path)
        )
    return sorted(set(candidates))


def _matches_module_root(module_name: str | None, roots: frozenset[str]) -> bool:
    return bool(module_name and any(module_name == root or module_name.startswith(f"{root}.") for root in roots))


def _is_augur_python_import(module_name: str | None) -> bool:
    return _matches_module_root(module_name, PROJECT_IMPORT_ROOTS)


def _is_llm_provider_import(module_name: str | None) -> bool:
    return _matches_module_root(module_name, LLM_PROVIDER_IMPORT_ROOTS)


def _python_import_coupling_issues(root: Path, path: Path, text: str) -> list[str]:
    if path.suffix != ".py":
        return []

    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError:
        return []

    lines = text.splitlines()
    issues: list[str] = []
    for node in ast.walk(tree):
        module_names: list[str] = []
        if isinstance(node, ast.ImportFrom):
            module_names.append(node.module or "")
            if node.module:
                module_names.extend(f"{node.module}.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.Import):
            module_names.extend(alias.name for alias in node.names)
        if not module_names:
            continue

        line = lines[node.lineno - 1].strip() if 0 < node.lineno <= len(lines) else "import"
        if any(_is_augur_python_import(module_name) for module_name in module_names):
            issues.append(
                "Augur import coupling found in "
                f"{path.relative_to(root).as_posix()}: {line}"
            )
        if any(_is_llm_provider_import(module_name) for module_name in module_names):
            issues.append(
                "external LLM provider import found in "
                f"{path.relative_to(root).as_posix()}: {line}"
            )
    return issues


def _hardcoded_augur_path_issues(root: Path, path: Path, text: str) -> list[str]:
    issues: list[str] = []
    for pattern in HARD_CODED_AUGUR_PATH_PATTERNS:
        for match in pattern.finditer(text):
            issues.append(
                "hardcoded Augur path found in "
                f"{path.relative_to(root).as_posix()}: {match.group(0)}"
            )
    return issues


def _contract_text_issues(root: Path, path: Path, text: str) -> list[str]:
    issues: list[str] = []
    for pattern in FORBIDDEN_STANDARD_PATTERNS:
        if pattern in text:
            issues.append(f"{pattern} found in {path.relative_to(root).as_posix()}")
    issues.extend(_hardcoded_augur_path_issues(root, path, text))
    issues.extend(_python_import_coupling_issues(root, path, text))
    return issues


def _has_augur_root_skill_contract(root: Path) -> bool:
    root_skill = root / "SKILL.md"
    if not root_skill.is_file():
        return False
    text = root_skill.read_text(encoding="utf-8", errors="replace")
    return bool(_contract_text_issues(root, root_skill, text))


def classify_standard_skill_contract(root: Path) -> StandardSkillContractReport:
    issues: list[str] = []
    is_standard = _is_standard_bundle(root)
    has_root_skill = (root / "SKILL.md").is_file()
    has_augur_skill = _has_augur_root_skill_contract(root)
    has_augur_runtime = (root / "augur").is_dir()
    has_mcp_source = (root / "scripts" / "mcp").exists()

    if is_standard:
        for path in _read_contract_files(root):
            text = path.read_text(encoding="utf-8", errors="replace")
            issues.extend(_contract_text_issues(root, path, text))
        status = (
            "mixed-needs-split"
            if issues or has_augur_runtime or has_root_skill or has_mcp_source
            else "standard-source-ready"
        )
        if has_augur_runtime:
            issues.append("augur/ runtime directory belongs outside canonical standard source")
        if has_root_skill:
            issues.append("root SKILL.md belongs to projection/runtime source")
        if has_mcp_source:
            issues.append("scripts/mcp/ source belongs outside canonical standard source")
        return StandardSkillContractReport(root.name, root, status, tuple(issues))

    if has_augur_skill or has_augur_runtime:
        return StandardSkillContractReport(root.name, root, "augur-platform-skill", tuple())

    return StandardSkillContractReport(
        root.name,
        root,
        "needs-projection-adapter",
        ("no DESCRIPTION.md plus subskill SKILL.md bundle found",),
    )


def scan_standard_skill_contracts(skill_roots: list[Path]) -> list[StandardSkillContractReport]:
    reports: list[StandardSkillContractReport] = []
    for skills_root in skill_roots:
        if not skills_root.is_dir():
            continue
        for skill_dir in sorted(path for path in skills_root.iterdir() if path.is_dir() and not path.name.startswith(".")):
            reports.append(classify_standard_skill_contract(skill_dir))
    return reports


def build_full_migration_report(roles: list[SkillRootRole]) -> FullMigrationReport:
    roles_by_root: dict[Path, list[str]] = {}
    physical_roots: list[Path] = []
    seen: set[Path] = set()
    for role in roles:
        root = Path(role.root)
        resolved = root.resolve()
        roles_by_root.setdefault(resolved, []).append(f"{role.tier}:{role.brain_id}")
        if resolved in seen:
            continue
        seen.add(resolved)
        physical_roots.append(root)

    skills: list[FullMigrationSkillReport] = []
    for root in physical_roots:
        if not root.is_dir():
            continue
        root_roles = tuple(roles_by_root.get(root.resolve(), ()))
        for report in scan_standard_skill_contracts([root]):
            skills.append(
                FullMigrationSkillReport(
                    name=report.name,
                    path=report.path,
                    status=report.status,
                    recommended_action=_recommended_action(report.status),
                    roles=root_roles,
                    issues=report.issues,
                )
            )

    return FullMigrationReport(
        physical_roots=tuple(physical_roots),
        skills=tuple(sorted(skills, key=lambda item: (item.name, item.path.as_posix()))),
    )


def evaluate_full_migration_gate(report: FullMigrationReport) -> FullMigrationGateReport:
    blocked: list[str] = []
    issues: list[str] = []
    by_name: dict[str, list[FullMigrationSkillReport]] = {}
    for item in report.skills:
        by_name.setdefault(item.name, []).append(item)
    for name in sorted(FULL_MIGRATION_SCOPE):
        items = by_name.get(name, [])
        if not items:
            blocked.append(name)
            issues.append(f"{name} is missing from the full migration report")
            continue
        is_blocked = False
        for item in items:
            if item.status == "mixed-needs-split":
                is_blocked = True
                issues.append(f"{name} remains mixed-needs-split at {item.path.as_posix()}")
            elif item.status not in {"standard-source-ready", "augur-platform-skill"}:
                is_blocked = True
                issues.append(
                    f"{name} has unsupported full migration status {item.status} at {item.path.as_posix()}"
                )
        if is_blocked:
            blocked.append(name)
    return FullMigrationGateReport(ok=not blocked, blocked=tuple(blocked), issues=tuple(issues))


def _recommended_action(status: str) -> str:
    return {
        "standard-source-ready": "keep-standard",
        "mixed-needs-split": "split-standard-and-adapter",
        "augur-platform-skill": "keep-platform",
        "needs-projection-adapter": "add-projection-adapter",
        "split-deferred": "split-deferred",
    }.get(status, "review")
