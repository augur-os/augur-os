"""auto-vault-structure-guard: Domains-layout structure guard.

Flags legacy top-level folders that have reappeared at the vault root,
unexpected root files outside the brain-contract set, and test-artifact
name patterns in content areas.  Report-only — never auto-fixes.

Only activates when BRAIN.yaml declares ``layout: domains``; vaults on the
legacy knowledge layout are left untouched.
"""
from __future__ import annotations

import re
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

from pathlib import Path

from src.lib.brain_layout import MACHINE_DIR, ROOT_BRAIN_FILES, brain_layout
from src.lib.brain_manifest import brain_skeleton_top_dirs
from src.lib.ops_protocol import FixResult, OpsContext, ScanResult, make_issue

name = "auto-vault-structure-guard"

# Machine dirs relocated under _augur/ in the domains layout that must not
# reappear at the vault root.
LEGACY_TOP_DIRS = {
    "knowledge", "drafts", "capabilities", "config", "memory", "prompts",
    "activity", "decisions", "instructions", "voice-memos", "workflows",
    "system", "specs", "reports", "policies", "plans", "integrations", "dev",
}

# Infra dirs valid at the vault root in the domains layout, derived from the
# brain-init skeleton so guard and skeleton stay in sync by construction.
# profile is a real vault dir served by browse but intentionally not part of
# the brain-contract skeleton.
INFRA_TOP_DIRS = set(brain_skeleton_top_dirs(layout="domains")) | {"profile"}

# Substrings in a filename that identify test/verification artifacts.
# "url-www-iana-org" is the capture slug of the example-domain junk captures
# (e.g. 2026-06-01-url-www-iana-org-help-example-domains.md); a bare "iana"
# would also flag legit iana.org source captures and names like adriana.md.
TEST_ARTIFACT_MARKERS = ("-verification", "example-domain", "url-www-iana-org")

# --- naming-standard checks (spec 2026-06-12) ---
NAME_MAX = 40
EVENT_NAME_DIRS = {"linkedin", "pipeline", "meetings", "daily"}
_DATE_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}-")
_URL_FRAGMENT = re.compile(r"-(https?|www)-|-com-|-org-|-io-")


def scan_structure(vault: Path) -> list[str]:
    """Scan a vault root for structure violations.

    Returns a list of human-readable finding strings.  Returns an empty list
    when the vault uses the legacy knowledge layout (guard does not apply).
    """
    if brain_layout(vault) != "domains":
        return []

    findings: list[str] = []

    # --- top-level entries ---
    for entry in sorted(vault.iterdir()):
        if entry.name.startswith(".") or entry.name in INFRA_TOP_DIRS:
            continue
        if entry.is_file():
            if entry.name not in ROOT_BRAIN_FILES:
                findings.append(f"unexpected root file: {entry.name}")
            continue
        # It's a directory (or symlink-to-directory).
        if entry.name in LEGACY_TOP_DIRS:
            findings.append(f"legacy top-level folder reappeared: {entry.name}")

    # --- test-artifact patterns in content files ---
    for md in vault.rglob("*.md"):
        rel = md.relative_to(vault)
        # Skip machine dir entirely.
        if rel.parts and rel.parts[0] == MACHINE_DIR:
            continue
        # Skip symlinks.  The `files` parts-check is currently unreachable —
        # rglob does not recurse into symlinked dirs on CPython 3.11+ — and is
        # kept as belt-and-suspenders against future rglob/links behavior
        # changes (e.g. follow_symlinks options or real `files` dirs).
        if md.is_symlink() or "files" in rel.parts:
            continue
        if any(marker in md.name for marker in TEST_ARTIFACT_MARKERS):
            findings.append(f"test artifact in content area: {rel}")
        # Naming checks skip wiki/: wiki names are generator-owned (slug
        # formula in ingest/scripts/wiki_concept_pages.py); naming governance
        # for wiki happens generator-side — see the follow-up note in the
        # 2026-06-12 naming spec. Structural checks above still apply.
        if rel.parts and rel.parts[0] == "wiki":
            continue
        stem = md.stem
        if len(stem) > NAME_MAX:
            findings.append(f"name too long ({len(stem)} > {NAME_MAX}): {rel}")
        if _DATE_NAME.match(stem) and not (set(rel.parts) & EVENT_NAME_DIRS):
            findings.append(f"dated name outside event dirs: {rel}")
        if _URL_FRAGMENT.search(stem):
            findings.append(f"url fragment in name: {rel}")

    return findings


# ---------------------------------------------------------------------------
# Hygiene scan/fix protocol (OpsContext surface for loop integration)
# ---------------------------------------------------------------------------


def _get_vault(project_root: Path | None = None) -> Path:
    from src.config.paths import get_configured_vault_dir
    return get_configured_vault_dir(project_root)


def scan(ctx: OpsContext) -> ScanResult:
    """Check the configured vault for structure violations (report-only)."""
    vault_dir = _get_vault(ctx.project_root)
    if not vault_dir.is_dir():
        return ScanResult(
            issues=[],
            summary="Vault directory not found — skipping structure guard",
            severity="info",
        )

    raw = scan_structure(vault_dir)
    issues = [
        make_issue(
            category="structure-violation",
            detail=finding,
            kind="manual",
            root_cause_type="manual_debt",
            fixability="manual",
            finding_band="structural",
        )
        for finding in raw
    ]
    severity = "error" if issues else "info"
    return ScanResult(
        issues=issues,
        summary=f"{len(issues)} structure violation(s) found (report-only)",
        severity=severity,
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Structure guard is report-only; no auto-fixes are applied."""
    return FixResult(
        success=True,
        summary=f"{len(issues)} structure violation(s) reported — manual review required",
        fix_type="report",
    )
